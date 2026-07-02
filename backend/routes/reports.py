from flask import Blueprint, request, jsonify, g, send_file, current_app, render_template_string
from middleware.auth import login_required, role_required, audit_log
from models import LoanApplication, Document, User
from app import db, redis_client
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from sqlalchemy import func, text
import os
import io
import requests

reports_bp = Blueprint('reports', __name__)

# Register a CJK-capable font once at import time so borrower project names
# with Chinese/Arabic/Cyrillic characters render properly on the exported PDF.
try:
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    _PDF_FONT = 'STSong-Light'
except Exception:
    _PDF_FONT = 'Helvetica'


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

    VULN-08 kept: SSRF via `url` parameter — fetches external resources.
    VULN-34 (new): `template` parameter is passed straight to Jinja's
    render_template_string, giving SSTI on the server. Combined with the
    SSRF above the attacker can pull a remote template and execute it.
    VULN-37 (new): the `sort` parameter comes from the previous JSON search
    (see applications.search) and is concatenated into ORDER BY of a raw
    SQL statement. Because it flows through the DB round-trip, this is a
    second-order SQL injection.
    """
    app_id = request.args.get('application_id')
    template_url = request.args.get('url', '')
    template = request.args.get('template', '')
    fmt = request.args.get('format', 'pdf').lower()

    # SSRF — fetch a remote template if a URL was supplied.
    if template_url and not template:
        try:
            resp = requests.get(template_url, timeout=5, verify=False)
            template = resp.text[:10000]
        except Exception as e:
            return jsonify({'error': f'Failed to fetch template: {str(e)}'}), 500

    # Read the "last search sort" preference from the caller — VULN-37 second-order.
    sort = getattr(g.current_user, '_report_prefs', {}).get('sort', 'id DESC')

    # Load rows using RAW SQL so the sort field is interpolated verbatim.
    try:
        rows = db.session.execute(
            text(f"SELECT id, app_no, project_name, amount_requested, currency, status "
                 f"FROM loan_applications ORDER BY {sort}")
        ).fetchall()
    except Exception:
        db.session.rollback()
        rows = []

    audit_log('export_report', 'report', 0, f'sort={sort} template_url={template_url}')

    # SSTI — if a template was supplied (via URL or query), render it against
    # the report context.
    if template:
        ctx = {
            'user': g.current_user,
            'rows': rows,
            'total': len(rows),
        }
        try:
            rendered = render_template_string(template, **ctx)
        except Exception as e:
            return jsonify({'error': f'Template render failed: {e}'}), 500
        if fmt == 'html':
            return rendered, 200, {'Content-Type': 'text/html'}
        return jsonify({'template': template, 'rendered': rendered}), 200

    # Otherwise emit a proper PDF (fixes previous unauth path — see auth.py).
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(_PDF_FONT, 16)
    c.drawString(50, 800, "IDB Loan Application Report")
    c.setFont(_PDF_FONT, 10)
    y = 760

    if app_id:
        application = LoanApplication.query.get(app_id)
        if application:
            for line in [
                f"Application: {application.app_no}",
                f"Project: {application.project_name}",
                f"Amount: {application.amount_requested} {application.currency}",
                f"Status: {application.status}",
                f"Borrower ID: {application.borrower_id}",
            ]:
                c.drawString(50, y, line)
                y -= 20
    else:
        c.drawString(50, y, f"Total applications: {len(rows)}")
        y -= 20
        for r in rows[:40]:
            c.drawString(50, y, f"{r[1]} — {r[2][:40]} ({r[3]} {r[4]}, {r[5]})")
            y -= 14
            if y < 60:
                c.showPage()
                c.setFont(_PDF_FONT, 10)
                y = 800

    c.save()
    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='idb_loan_report.pdf',
    )


@reports_bp.route('/download', methods=['GET'])
@login_required
def download_file():
    """
    Download a file from the server.
    VULN-18 kept: path traversal via `file` parameter.
    """
    filename = request.args.get('file', '')
    if not filename:
        return jsonify({'error': 'File parameter is required'}), 400

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        return jsonify({'error': f'File not found: {filename}'}), 404

    return send_file(file_path, as_attachment=True)


@reports_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """
    System statistics.

    Bug fix: previous version referenced `User` before its import, causing
    a NameError on the first request. All imports are now at module top.
    """
    stats = {
        'users': {
            'total': User.query.count(),
            'by_role': {},
        },
        'applications': {
            'total': LoanApplication.query.count(),
            'total_amount': 0,
        },
    }
    for role in ['borrower', 'officer', 'risk', 'admin']:
        stats['users']['by_role'][role] = User.query.filter_by(role=role).count()

    total_amount = db.session.query(func.sum(LoanApplication.amount_requested)).scalar()
    stats['applications']['total_amount'] = str(total_amount) if total_amount else '0'

    return jsonify(stats), 200
