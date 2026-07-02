from flask import Blueprint, request, jsonify, g, current_app
from models import User, AuditLog
from middleware.auth import login_required, audit_log, decode_token
from app import db, redis_client
import jwt
import datetime
import uuid
import hashlib

auth_bp = Blueprint('auth', __name__)

# Simple in-memory token blacklist (weak — VULN-04)
# Real implementation should use Redis. This is here for the vulnerability.
_token_blacklist = set()


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    # VULN-F: No rate limiting on login attempts (RATELIMIT_ENABLED is False)
    # Password check — for demo, we check against known demo passwords by verifying
    # hash contains the SHA256 of the password
    import hashlib
    expected_hash = hashlib.sha256(password.encode()).hexdigest()[:40]
    stored = user.password_hash or ''
    if expected_hash not in stored:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403

    access_token = jwt.encode(
        {
            'sub': str(user.id),
            'username': user.username,
            'role': user.role,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=8),
            'jti': str(uuid.uuid4())
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    refresh_token = jwt.encode(
        {
            'sub': str(user.id),
            'type': 'refresh',
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30),
            'jti': str(uuid.uuid4())
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    user.last_login = datetime.datetime.utcnow()
    db.session.commit()

    audit_log('login', 'user', user.id, f'User {user.username} logged in')

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(include_sensitive=True)
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    data = request.get_json()
    refresh_token_str = data.get('refresh_token', '')

    if not refresh_token_str:
        return jsonify({'error': 'Refresh token required'}), 400

    payload = decode_token(refresh_token_str)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': 'Invalid refresh token'}), 401

    user = User.query.get(payload.get('sub'))
    if not user:
        return jsonify({'error': 'User not found'}), 401

    # VULN-04: Old tokens not invalidated — old JWT still works after refresh
    new_access_token = jwt.encode(
        {
            'sub': str(user.id),
            'username': user.username,
            'role': user.role,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=8),
            'jti': str(uuid.uuid4())
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    return jsonify({'access_token': new_access_token}), 200


@auth_bp.route('/sso/callback', methods=['GET'])
def sso_callback():
    """
    SSO callback endpoint.
    VULN-02: redirect parameter is not validated — open redirect to any URL including internal services
    """
    token = request.args.get('token', '')
    redirect = request.args.get('redirect', '/')

    # Mock SSO validation — accepts any token starting with 'sso-'
    if not token.startswith('sso-'):
        return jsonify({'error': 'Invalid SSO token'}), 401

    # VULN-02: No redirect validation — attacker can redirect to attacker.com
    # Also exploitable for internal SSRF: redirect=http://internal-service:8080/
    return f'<html><body><script>window.location.href="{redirect}?ssotoken={token}";</script></body></html>'


@auth_bp.route('/sso/token', methods=['POST'])
def sso_exchange():
    """Exchange SSO token for JWT."""
    data = request.get_json()
    sso_token = data.get('sso_token', '')

    if not sso_token:
        return jsonify({'error': 'SSO token required'}), 400

    # Mock: extract username from token format "sso-{username}-{timestamp}"
    parts = sso_token.split('-')
    if len(parts) < 3 or parts[0] != 'sso':
        return jsonify({'error': 'Invalid SSO token format'}), 401

    username = parts[1]
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    access_token = jwt.encode(
        {
            'sub': str(user.id),
            'username': user.username,
            'role': user.role,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=8),
            'jti': str(uuid.uuid4())
        },
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )

    return jsonify({'access_token': access_token, 'user': user.to_dict()}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    return jsonify({'user': g.current_user.to_dict(include_sensitive=True)}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Password reset endpoint.
    VULN-03: No identity verification beyond username + employee_id.
    Employee IDs are leaked in review comments (officer accounts).
    """
    data = request.get_json()
    username = data.get('username', '')
    employee_id = data.get('employee_id', '')
    new_password = data.get('new_password', '')

    # VULN-03: Weak verification — only needs username + employee_id
    # Employee IDs visible in: review comments (checklist JSON), user profile responses
    user = User.query.filter_by(username=username, employee_id=employee_id).first()
    if not user:
        return jsonify({'error': 'User not found or employee ID mismatch'}), 404

    # Password is stored as plaintext hash placeholder — in real app would be hashed
    user.password_hash = f'scrypt:32768:8:1$salt${hashlib.sha256(new_password.encode()).hexdigest()}'
    db.session.commit()

    audit_log('password_reset', 'user', user.id, f'Password reset for {user.username}')

    return jsonify({'message': 'Password reset successful. Please login with your new password.'}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        _token_blacklist.add(token)
    # VULN-04: Doesn't blacklist refresh token, only access token
    # VULN-04: Blacklist is in-memory only — lost on restart
    return jsonify({'message': 'Logged out successfully'}), 200
