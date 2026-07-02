import jwt
from functools import wraps
from flask import request, jsonify, g
from models import User, AuditLog


def decode_token(token):
    """Decode JWT token. VULN-01: Uses hardcoded secret from .env.example"""
    from flask import current_app
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
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

        user = User.query.get(int(payload.get('sub')))
        if not user:
            return jsonify({'error': 'User not found', 'code': 'USER_NOT_FOUND'}), 401

        g.current_user = user
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
