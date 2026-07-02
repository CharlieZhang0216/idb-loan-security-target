from flask import Blueprint, request, jsonify, g, current_app
from middleware.auth import login_required, role_required, audit_log
from models import User, LoanApplication, SystemConfig, Notification, AuditLog, Document
from app import db

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
@login_required
@role_required('admin')
def list_users():
    users = User.query.all()
    return jsonify({'users': [u.to_dict(include_sensitive=True) for u in users]}), 200


@admin_bp.route('/users', methods=['POST'])
@login_required
@role_required('admin')
def create_user():
    data = request.get_json()
    required = ['username', 'email', 'role', 'full_name']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    user = User(
        username=data['username'],
        email=data['email'],
        password_hash='scrypt:32768:8:1$salt$temp_hash',
        role=data['role'],
        full_name=data['full_name'],
        country=data.get('country'),
        department=data.get('department'),
        employee_id=data.get('employee_id'),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'user': user.to_dict(include_sensitive=True)}), 201


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@role_required('admin')
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    editable = ['email', 'role', 'full_name', 'country', 'department', 'employee_id', 'is_active']
    for field in editable:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify({'user': user.to_dict(include_sensitive=True)}), 200


@admin_bp.route('/reset-password', methods=['POST'])
def admin_reset_password():
    """
    Admin-level password reset.
    VULN-03 continued: Only needs admin token (from .env) to reset ANY user.
    No MFA, no email verification, no second factor.
    """
    data = request.get_json()
    token = data.get('admin_token', '')
    username = data.get('username', '')
    new_password = data.get('new_password', '')

    # VULN-03: Admin reset token is hardcoded in .env.example
    if token != current_app.config['ADMIN_RESET_TOKEN']:
        return jsonify({'error': 'Invalid admin token'}), 403

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    import hashlib
    user.password_hash = f'scrypt:32768:8:1$salt${hashlib.sha256(new_password.encode()).hexdigest()}'
    db.session.commit()

    return jsonify({'message': f'Password reset for {username}'}), 200


@admin_bp.route('/config', methods=['GET'])
@login_required
@role_required('admin')
def get_config():
    configs = SystemConfig.query.all()
    return jsonify({'config': {c.key: c.value for c in configs}}), 200


@admin_bp.route('/config', methods=['PUT'])
@login_required
@role_required('admin')
def update_config():
    data = request.get_json()
    for key, value in data.items():
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            config.value = str(value)
            config.updated_by = g.current_user.id
        else:
            config = SystemConfig(key=key, value=str(value), updated_by=g.current_user.id)
            db.session.add(config)

    db.session.commit()
    return jsonify({'message': 'Config updated'}), 200


@admin_bp.route('/audit-logs', methods=['GET'])
@login_required
@role_required('admin')
def get_audit_logs():
    """Get audit logs. VULN-H: Many critical actions are NOT logged."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    user_id = request.args.get('user_id', type=int)

    query = AuditLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'logs': [{
            'id': log.id,
            'user_id': log.user_id,
            'username': log.username,
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        } for log in logs.items],
        'page': logs.page,
        'total': logs.total,
        'pages': logs.pages,
    }), 200


@admin_bp.route('/stats', methods=['GET'])
@login_required
@role_required('admin')
def admin_stats():
    """Admin dashboard statistics."""
    return jsonify({
        'users_total': User.query.count(),
        'users_active': User.query.filter_by(is_active=True).count(),
        'applications_total': LoanApplication.query.count(),
        'applications_pending': LoanApplication.query.filter(
            LoanApplication.status.in_(['submitted', 'under_review'])
        ).count(),
        'documents_total': Document.query.count(),
    }), 200
