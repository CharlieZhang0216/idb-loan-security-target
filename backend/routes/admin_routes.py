from flask import Blueprint, request, jsonify, g, current_app, send_file
from middleware.auth import login_required, role_required, audit_log
from models import User, LoanApplication, SystemConfig, Notification, AuditLog, Document
from app import db
import base64
import hashlib
import io
import os
import pickle  # noqa: S403 — deliberately used for VULN-27 / VULN-35

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
    data = request.get_json() or {}
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

    data = request.get_json() or {}
    editable = ['email', 'role', 'full_name', 'country', 'department', 'employee_id', 'is_active']
    for field in editable:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify({'user': user.to_dict(include_sensitive=True)}), 200


@admin_bp.route('/reset-password', methods=['POST'])
def admin_reset_password():
    """
    Admin-level password reset — VULN-03 kept.
    """
    data = request.get_json() or {}
    token = data.get('admin_token', '')
    username = data.get('username', '')
    new_password = data.get('new_password', '')

    if token != current_app.config['ADMIN_RESET_TOKEN']:
        return jsonify({'error': 'Invalid admin token'}), 403

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.password_hash = (
        f'scrypt:32768:8:1$demo${hashlib.sha256(new_password.encode()).hexdigest()[:40]}'
    )
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
    """
    Update system configuration.

    VULN-38 (new): recursive dict merge into SystemConfig, and any keys
    starting with `_meta.` are written straight into current_app.config so
    a request body like {"_meta.SECRET_KEY": "xxx"} rotates the JWT secret
    at runtime — every existing token gets invalidated (denial-of-service)
    or, when combined with VULN-21, the attacker sets a secret they know.
    """
    data = request.get_json() or {}

    for key, value in data.items():
        if key.startswith('_meta.'):
            # Direct app.config write. Persisted only in memory; restart
            # clears it. Not audited.
            current_app.config[key[len('_meta.'):]] = value
            continue

        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            config.value = str(value)
            config.updated_by = g.current_user.id
        else:
            config = SystemConfig(key=key, value=str(value), updated_by=g.current_user.id)
            db.session.add(config)

    db.session.commit()
    return jsonify({'message': 'Config updated'}), 200


# ---------------------------------------------------------------------------
# Legacy backup import / restore  — VULN-27 / VULN-35 (Pickle RCE chain)
# ---------------------------------------------------------------------------

@admin_bp.route('/backup/import', methods=['POST'])
@login_required
@role_required('admin', 'officer')
def import_backup():
    """
    Import a legacy audit-log snapshot from an older on-prem deployment.

    The historical format was a pickled Python dict — kept for compatibility
    with member-country deployments that still export that shape.

    VULN-27: `pickle.loads` is called on user-controlled bytes when the
    ENABLE_LEGACY_BACKUP_IMPORT toggle is on (default). This is a classic
    unauthenticated-shape RCE — combined with VULN-24 (X-Effective-Role) an
    officer with a delegate token can reach this endpoint.

    Payload:
      {"data": "<base64-pickle>"}
    """
    if not current_app.config.get('ENABLE_LEGACY_BACKUP_IMPORT', True):
        return jsonify({'error': 'Legacy import disabled'}), 400

    body = request.get_json() or {}
    b64 = body.get('data', '')
    if not b64:
        return jsonify({'error': 'data is required'}), 400

    try:
        blob = base64.b64decode(b64)
    except Exception as e:
        return jsonify({'error': f'Not valid base64: {e}'}), 400

    # VULN-27: unsafe deserialization
    try:
        parsed = pickle.loads(blob)  # noqa: S301
    except Exception as e:
        return jsonify({'error': f'Failed to unpickle: {e}'}), 400

    audit_log('import_backup', 'system', 0, f'Imported {len(blob)} bytes legacy snapshot')
    # Return a summary so the exploiter gets confirmation of successful import.
    return jsonify({
        'imported': True,
        'kind': type(parsed).__name__,
        'preview': str(parsed)[:200],
    }), 200


@admin_bp.route('/backup/export', methods=['GET'])
@login_required
@role_required('admin')
def export_backup():
    """
    Export the audit-log table in the same legacy pickled shape so admins
    can round-trip snapshots between environments.
    """
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(1000).all()
    payload = [{
        'id': l.id,
        'user_id': l.user_id,
        'username': l.username,
        'action': l.action,
        'resource_type': l.resource_type,
        'resource_id': l.resource_id,
        'ip_address': l.ip_address,
        'created_at': l.created_at.isoformat() if l.created_at else None,
    } for l in logs]

    buf = io.BytesIO(pickle.dumps(payload))
    return send_file(buf, mimetype='application/octet-stream',
                     as_attachment=True, download_name='audit_snapshot.pkl')


@admin_bp.route('/audit-logs', methods=['GET'])
@login_required
@role_required('admin')
def get_audit_logs():
    """VULN-H kept: many critical actions are still not logged."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    user_id = request.args.get('user_id', type=int)

    query = AuditLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False,
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
    return jsonify({
        'users_total': User.query.count(),
        'users_active': User.query.filter_by(is_active=True).count(),
        'applications_total': LoanApplication.query.count(),
        'applications_pending': LoanApplication.query.filter(
            LoanApplication.status.in_(['submitted', 'under_review'])
        ).count(),
        'documents_total': Document.query.count(),
    }), 200
