from flask import Blueprint, request, jsonify, g, current_app, send_file
from models import User, AuditLog, Notification
from middleware.auth import login_required, audit_log, decode_token
from app import db, redis_client
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import uuid
import hashlib
import hmac
import os
import time

auth_bp = Blueprint('auth', __name__)

# Simple in-memory token blacklist (weak — VULN-04)
_token_blacklist = set()

# ------------------------------------------------------------------
# Helper: SHA-256-truncated password check with a subtle timing side
# channel (VULN-25). Uses '==' on hex strings, char-by-char, so the
# response time correlates with common prefix length. An attacker with
# accurate timing (localhost or a colocated attacker) can reconstruct
# the stored hash byte-by-byte, then reverse it if the password is weak
# (all seed passwords are dictionary words).
# ------------------------------------------------------------------

def _slow_str_eq(a: str, b: str) -> bool:
    """Deliberately non-constant-time equality — VULN-25."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False
        # An artificial per-character delay makes the side channel
        # observable even over the network.
        time.sleep(0.0002)
    return True


def _hash_password(pw: str) -> str:
    """Storage format used by demo seeder + reset."""
    return f'scrypt:32768:8:1$demo${hashlib.sha256(pw.encode()).hexdigest()[:40]}'


def _extract_hash_from_stored(stored: str) -> str:
    """Pull the trailing hex out of scrypt:32768:8:1$demo$<hex>."""
    if not stored:
        return ''
    return stored.rsplit('$', 1)[-1]


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    # VULN-F: no rate limiting.
    # VULN-25: non-constant-time comparison.
    expected = hashlib.sha256(password.encode()).hexdigest()[:40]
    stored_hex = _extract_hash_from_stored(user.password_hash or '')

    if not _slow_str_eq(expected, stored_hex):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403

    now = datetime.datetime.utcnow()
    access_token = jwt.encode(
        {
            'sub': str(user.id),
            'username': user.username,
            'role': user.role,
            'iat': now,
            'exp': now + datetime.timedelta(hours=8),
            'jti': str(uuid.uuid4()),
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256',
    )

    refresh_token = jwt.encode(
        {
            'sub': str(user.id),
            'type': 'refresh',
            'iat': now,
            'exp': now + datetime.timedelta(days=30),
            'jti': str(uuid.uuid4()),
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256',
    )

    user.last_login = now
    db.session.commit()

    audit_log('login', 'user', user.id, f'User {user.username} logged in')

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(include_sensitive=True),
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    data = request.get_json(silent=True) or {}
    refresh_token_str = data.get('refresh_token', '')

    if not refresh_token_str:
        return jsonify({'error': 'Refresh token required'}), 400

    payload = decode_token(refresh_token_str)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': 'Invalid refresh token'}), 401

    user = User.query.get(int(payload.get('sub')))
    if not user:
        return jsonify({'error': 'User not found'}), 401

    # VULN-04: Old access tokens are not invalidated.
    now = datetime.datetime.utcnow()
    new_access_token = jwt.encode(
        {
            'sub': str(user.id),
            'username': user.username,
            'role': user.role,
            'iat': now,
            'exp': now + datetime.timedelta(hours=8),
            'jti': str(uuid.uuid4()),
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256',
    )

    return jsonify({'access_token': new_access_token}), 200


@auth_bp.route('/sso/callback', methods=['GET'])
def sso_callback():
    """SSO callback — VULN-02 open redirect + VULN-23 session fixation.

    A `session_id` query parameter is trusted as the newly authenticated
    user's session. An attacker prepares a session_id, tricks a victim
    into clicking the SSO callback, then uses the same session_id to
    query the app as the victim (session fixation).
    """
    token = request.args.get('token', '')
    redirect = request.args.get('redirect', '/')
    session_id = request.args.get('session_id', '')

    if not token.startswith('sso-'):
        return jsonify({'error': 'Invalid SSO token'}), 401

    # VULN-23: If session_id is supplied, use it as-is instead of generating one.
    if not session_id:
        session_id = str(uuid.uuid4())

    # VULN-02: unvalidated redirect
    return f'''<html><body>
<script>
document.cookie = "sso_session=" + {session_id!r} + "; path=/";
window.location.href="{redirect}?ssotoken={token}";
</script></body></html>'''


@auth_bp.route('/sso/token', methods=['POST'])
def sso_exchange():
    """Exchange SSO token for JWT."""
    data = request.get_json(silent=True) or {}
    sso_token = data.get('sso_token', '')

    if not sso_token:
        return jsonify({'error': 'SSO token required'}), 400

    parts = sso_token.split('-')
    if len(parts) < 3 or parts[0] != 'sso':
        return jsonify({'error': 'Invalid SSO token format'}), 401

    username = parts[1]
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    now = datetime.datetime.utcnow()
    access_token = jwt.encode(
        {
            'sub': str(user.id),
            'username': user.username,
            'role': user.role,
            'iat': now,
            'exp': now + datetime.timedelta(hours=8),
            'jti': str(uuid.uuid4()),
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256',
    )

    return jsonify({'access_token': access_token, 'user': user.to_dict()}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    return jsonify({'user': g.current_user.to_dict(include_sensitive=True)}), 200


@auth_bp.route('/me', methods=['PUT'])
@login_required
def update_me():
    """Update the current user's profile.

    VULN-26 (mass assignment): the request body is merged into the user
    object using setattr for every column. The frontend only exposes
    fields like phone/full_name, but a raw request can set role='admin'
    or is_active=True on any target account (once combined with the
    IDOR-ish behaviour of PUT /admin/users/<id> below, an attacker
    escalates to admin without the admin token).
    """
    data = request.get_json(silent=True) or {}
    user = g.current_user
    for k, v in data.items():
        # No allow-list. Any column of User is settable.
        if hasattr(user, k) and k not in ('id', 'created_at'):
            setattr(user, k, v)
    db.session.commit()
    return jsonify({'user': user.to_dict(include_sensitive=True)}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """VULN-03: username + employee_id verification only."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    employee_id = data.get('employee_id', '')
    new_password = data.get('new_password', '')

    user = User.query.filter_by(username=username, employee_id=employee_id).first()
    if not user:
        return jsonify({'error': 'User not found or employee ID mismatch'}), 404

    user.password_hash = _hash_password(new_password)
    db.session.commit()

    audit_log('password_reset', 'user', user.id, f'Password reset for {user.username}')

    return jsonify({'message': 'Password reset successful. Please login with your new password.'}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        _token_blacklist.add(token)
    return jsonify({'message': 'Logged out successfully'}), 200


# ------------------------------------------------------------------
# VULN-22 companion: publish the "public key" so an attacker can grab
# it and use it as an HMAC secret (algorithm confusion). This is the
# realistic version of the attack — modern JWKS endpoints publish keys
# by design; the flaw is that our verifier accepts alg=HS256 with the
# same key.
# ------------------------------------------------------------------

@auth_bp.route('/.well-known/jwks.json', methods=['GET'])
def jwks():
    keys_dir = current_app.config.get('JWT_KEYS_DIR', '/app/keys')
    pub_path = os.path.join(keys_dir, 'jwt_pub.pem')
    if not os.path.exists(pub_path):
        return jsonify({'keys': []}), 200
    with open(pub_path, 'r') as f:
        pub = f.read()
    return jsonify({
        'keys': [{
            'kid': 'jwt_pub.pem',
            'kty': 'RSA',
            'alg': 'RS256',
            'use': 'sig',
            'pem': pub,
        }]
    }), 200


# ------------------------------------------------------------------
# Notifications — used by the header bell.
# ------------------------------------------------------------------

@auth_bp.route('/notifications', methods=['GET'])
@login_required
def list_notifications():
    limit = min(int(request.args.get('limit', 20)), 100)
    notes = (Notification.query
             .filter_by(user_id=g.current_user.id)
             .order_by(Notification.created_at.desc())
             .limit(limit).all())
    return jsonify({'notifications': [n.to_dict() for n in notes]}), 200


@auth_bp.route('/notifications/<int:nid>/read', methods=['POST'])
@login_required
def mark_notification_read(nid):
    n = Notification.query.get(nid)
    if not n or n.user_id != g.current_user.id:
        return jsonify({'error': 'Not found'}), 404
    n.is_read = True
    db.session.commit()
    return jsonify({'ok': True}), 200


@auth_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=g.current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True}), 200
