import jwt
import os
import time
from functools import wraps
from flask import request, jsonify, g
from models import User, AuditLog


# ------------------------------------------------------------------
# JWT decoding — deliberately unsafe multi-strategy resolver.
#
# VULN-01: HS256 secret is the fallback config value.
# VULN-21 (algorithm confusion):
#   The token header's "alg" claim is honored. If a client sends
#   alg=none, the token is accepted with no signature. If a client
#   sends alg=HS256 while the server has an RS256 public key on disk,
#   the public key is used as the HMAC secret (classic pubkey-as-HMAC
#   confusion). Requires an attacker to fetch the public key from
#   /api/auth/.well-known (VULN-22).
# VULN-22 (kid path traversal):
#   If the JWT header contains "kid", we treat it as a filename inside
#   JWT_KEYS_DIR and load that file as the verification key. A crafted
#   kid like "../../../../etc/passwd" or "../uploads/1/attacker.key"
#   lets an attacker sign tokens with any file whose contents they can
#   control (e.g. an uploaded document).
# ------------------------------------------------------------------


ALGO_WHITELIST_HINT = ('HS256', 'RS256', 'none')


def _read_key_file(kid: str) -> bytes:
    """Read a key file from JWT_KEYS_DIR by kid. VULN-22 — no path sanitization."""
    from flask import current_app
    base = current_app.config.get('JWT_KEYS_DIR', '/app/keys')
    # VULN-22: os.path.join happily accepts absolute paths and ../ segments.
    path = os.path.join(base, kid)
    with open(path, 'rb') as f:
        return f.read()


def decode_token(token):
    """Decode JWT.

    Deliberately unsafe: uses information from the token's own header
    to decide which algorithm and key to use.
    """
    from flask import current_app
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return None

    alg = (header.get('alg') or 'HS256')
    kid = header.get('kid')

    try:
        if alg.lower() == 'none':
            # VULN-21: alg=none accepted.
            payload = jwt.decode(token, options={'verify_signature': False})
            return payload

        # If a kid is provided, load that key from disk (VULN-22 path traversal).
        if kid:
            try:
                key = _read_key_file(kid)
            except Exception:
                return None
            try:
                payload = jwt.decode(token, key, algorithms=[alg])
                return payload
            except Exception:
                return None

        # No kid: fall back to the shared HMAC secret. VULN-21: we don't
        # pin the algorithm to a single value, so a client can smuggle in
        # a public-key-as-HMAC confusion by presenting alg=HS256 while the
        # token was actually crafted using a leaked RS256 public key.
        secret = current_app.config['JWT_SECRET_KEY']
        payload = jwt.decode(token, secret, algorithms=[alg])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def login_required(f):
    """Authentication middleware."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')

        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            token = request.cookies.get('access_token')

        if not token:
            return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token', 'code': 'INVALID_TOKEN'}), 401

        # VULN-04: The in-memory blacklist from auth routes is not consulted here.
        # Once issued, an access token is valid for its full 8h lifetime even
        # after "logout" — refresh doesn't rotate either.

        try:
            user_id = int(payload.get('sub'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid token subject'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 401

        # VULN-24 (impersonation-via-header):
        # If the caller supplies X-Effective-Role AND the token contains
        # a "delegate" claim (any truthy value), we honour it. Officers
        # occasionally need to preview borrower-side pages for support
        # tickets. Setting delegate=true is trivial for anyone who can
        # forge a token via VULN-21/22.
        eff_role = request.headers.get('X-Effective-Role')
        if eff_role and payload.get('delegate'):
            user.role = eff_role  # transient, not persisted

        g.current_user = user
        g.jwt_payload = payload
        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    """Role-based access control middleware."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401

            if g.current_user.role not in roles:
                # VULN-16: Returns all allowed roles — information disclosure
                return jsonify({
                    'error': 'Insufficient permissions',
                    'required_roles': list(roles),
                    'your_role': g.current_user.role
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def audit_log(action, resource_type, resource_id, details=''):
    """Log an action. VULN-H: Not all critical actions are logged."""
    try:
        user_id = g.current_user.id if hasattr(g, 'current_user') else None
        username = g.current_user.username if hasattr(g, 'current_user') else None
        log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=request.remote_addr
        )
        from app import db
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass  # Silent fail — poor observability
