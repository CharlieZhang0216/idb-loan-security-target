from flask import Blueprint, request, jsonify, g, send_file, current_app
from middleware.auth import login_required, role_required, audit_log
from models import LoanApplication, Document
from app import db, redis_client
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
import io
import requests

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/summary', methods=['GET'])
@login_required
def get_summary():
    """Get loan portfolio summary statistics."""
    total = LoanApplication.query.count()
    by_status = {}
    for status in ['draft', 'submitted', 'under_review', 'pending_supplement',
                    'risk_assessment', 'approved', 'rejected', 'disbursed', 'archived']:
        count = LoanApplication.query.filter_by(status=status).count()
        by_status[status] = count

    by_sector = db.session.query(
        LoanApplication.sector, db.func.count(LoanApplication.id)
    ).group_by(LoanApplication.sector).all()

    return jsonify({
        'total_applications': total,
        'by_status': by_status,
        'by_sector': [{'sector': s, 'count': c} for s, c in by_sector],
    }), 200


@reports_bp.route('/export', methods=['GET'])
@login_required
@role_required('officer', 'risk', 'admin')
def export_report():
    """
    Generate and download a report.
    VULN-08: SSRF via url parameter — fetches external resources on server side.
    """
    app_id = request.args.get('application_id')
    template_url = request.args.get('url', '')

    if template_url:
        # VULN-08: SSRF — server fetches arbitrary URLs
        # Can be used to access internal services: url=http://redis:6379/ or url=http://169.254.169.254/
        try:
            resp = requests.get(template_url, timeout=5, verify=False)
            template_content = resp.text[:10000]  # Truncate
        except Exception as e:
            return jsonify({'error': f'Failed to fetch template: {str(e)}'}), 500

        # Return the fetched content (SSRF response)
        return jsonify({
            'template_url': template_url,
            'template_content': template_content,
            'status': 'Template fetched successfully'
        }), 200

    # Standard PDF report
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 16)
    c.drawString(50, 800, "IDB Loan Application Report")

    c.setFont("Helvetica", 10)
    y = 760

    if app_id:
        application = LoanApplication.query.get(app_id)
        if application:
            c.drawString(50, y, f"Application: {application.app_no}")
            y -= 20
            c.drawString(50, y, f"Project: {application.project_name}")
            y -= 20
            c.drawString(50, y, f"Amount: {application.amount_requested} {application.currency}")
            y -= 20
            c.drawString(50, y, f"Status: {application.status}")
            y -= 20
    else:
        total = LoanApplication.query.count()
        c.drawString(50, y, f"Total Applications: {total}")

    c.save()
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='idb_loan_report.pdf'
    )


@reports_bp.route('/download', methods=['GET'])
@login_required
def download_file():
    """
    Download a file from the server.
    VULN-18: Path traversal — file parameter is not sanitized.
    Example: /api/reports/download?file=../../.env
    """
    filename = request.args.get('file', '')

    # VULN-18: No path sanitization — direct file access
    # Only checks if filename is not empty
    if not filename:
        return jsonify({'error': 'File parameter is required'}), 400

    # VULN-18: Constructs path with user input — path traversal possible
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    # Normalize but this doesn't prevent traversal with ../../
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        return jsonify({'error': f'File not found: {filename}'}), 404

    return send_file(file_path, as_attachment=True)


@reports_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """Get system statistics. VULN-F: No caching — hits DB on every call."""
    from sqlalchemy import func

    stats = {
        'users': {
            'total': User.query.count(),
            'by_role': {}
        },
        'applications': {
            'total': LoanApplication.query.count(),
            'total_amount': 0,
        }
    }

    from models import User
    for role in ['borrower', 'officer', 'risk', 'admin']:
        count = User.query.filter_by(role=role).count()
        stats['users']['by_role'][role] = count

    total_amount = db.session.query(func.sum(LoanApplication.amount_requested)).scalar()
    stats['applications']['total_amount'] = str(total_amount) if total_amount else '0'

    return jsonify(stats), 200
