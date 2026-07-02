from flask import Blueprint, request, jsonify, g, send_file, current_app, Response
from middleware.auth import login_required, role_required, audit_log
from models import Document, LoanApplication
from app import db
import os
import io
import uuid
import hashlib
import zipfile
import magic  # python-magic

# NOTE: lxml is imported without disabling entity resolution — VULN-32 (XXE).
from lxml import etree  # noqa: E402

documents_bp = Blueprint('documents', __name__)

ALLOWED_MIME = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/csv',
    'text/xml',
    'application/xml',
    'application/zip',
    'image/jpeg',
    'image/png',
    'image/svg+xml',  # VULN-17: SVG allowed — SVG XSS possible
}


def _application_can_write(application, user):
    if user.role == 'admin':
        return True
    if user.role == 'borrower' and application.borrower_id == user.id:
        return True
    return False


@documents_bp.route('/upload/<int:app_id>', methods=['POST'])
@login_required
@role_required('borrower', 'admin')
def upload_document(app_id):
    """Upload a document to an application."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if not _application_can_write(application, user):
        return jsonify({'error': 'Access denied'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    original_name = file.filename
    file_data = file.read()
    file.seek(0)

    mime_type = magic.from_buffer(file_data, mime=True)
    if mime_type not in ALLOWED_MIME:
        return jsonify({'error': f'File type {mime_type} not allowed'}), 400

    file_size = len(file_data)
    file_hash = hashlib.sha256(file_data).hexdigest()

    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else 'bin'
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(app_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)
    file.save(file_path)

    category = request.form.get('category', 'general')
    description = request.form.get('description', '')

    doc = Document(
        application_id=app_id,
        uploaded_by=user.id,
        filename=unique_name,
        original_name=original_name,
        file_path=file_path,
        file_type=mime_type,
        file_size=file_size,
        file_hash=file_hash,
        category=category,
        description=description,
    )
    db.session.add(doc)
    db.session.commit()

    audit_log('upload_document', 'document', doc.id,
              f'Uploaded {original_name} to application {app_id}')

    return jsonify({'document': doc.to_dict(), 'message': 'Document uploaded'}), 201


@documents_bp.route('/<int:doc_id>', methods=['GET'])
@login_required
def get_document(doc_id):
    """
    Download a document.

    VULN-13 kept: previous delete leaks files on disk.
    Bug fix: this endpoint used to be linked with a bare <a href> from the
    frontend and thus bypassed the axios auth interceptor. Now the frontend
    fetches with a Bearer token and this endpoint accepts either the header
    or a short-lived signed `?token=` query param — so scanners will not
    catch the query-param path unless they read the source. See VULN-30.
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    user = g.current_user
    application = LoanApplication.query.get(doc.application_id)
    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.exists(doc.file_path):
        return jsonify({'error': 'File not found on disk'}), 404

    return send_file(
        doc.file_path,
        mimetype=doc.file_type,
        as_attachment=True,
        download_name=doc.original_name,
    )


@documents_bp.route('/application/<int:app_id>', methods=['GET'])
@login_required
def list_documents(app_id):
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    user = g.current_user
    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    docs = Document.query.filter_by(application_id=app_id).order_by(Document.created_at.desc()).all()
    return jsonify({'documents': [d.to_dict() for d in docs]}), 200


@documents_bp.route('/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """
    Delete a document.

    Fix: also unlink the file on disk if the caller is admin, keeping the
    original VULN-13 (disk file is retained) for non-admins.
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    user = g.current_user
    application = LoanApplication.query.get(doc.application_id)
    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    file_path = doc.file_path
    db.session.delete(doc)
    db.session.commit()

    # VULN-13 kept: only admin cleans up disk. Borrowers still leak the file.
    if user.role == 'admin':
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass

    return jsonify({'message': 'Document deleted'}), 200


# ---------------------------------------------------------------------------
# XML / archive inspection endpoints
# ---------------------------------------------------------------------------

@documents_bp.route('/<int:doc_id>/inspect', methods=['POST'])
@login_required
@role_required('officer', 'risk', 'admin')
def inspect_document(doc_id):
    """
    Preview an uploaded XML/SVG document as pretty-printed text.

    VULN-32 (new): the XML parser is instantiated with resolve_entities=True
    and no_network=False. Uploading an XML with an external DTD will:
      - read local files (file:///etc/passwd)
      - probe internal HTTP endpoints (SSRF via http:// entity)
      - trigger billion-laughs against the parser (DoS)
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not doc.file_type or 'xml' not in doc.file_type and 'svg' not in doc.file_type:
        return jsonify({'error': 'Only XML/SVG documents can be inspected'}), 400

    if not os.path.exists(doc.file_path):
        return jsonify({'error': 'File not found on disk'}), 404

    with open(doc.file_path, 'rb') as f:
        raw = f.read()

    # VULN-32: dangerously permissive parser.
    parser = etree.XMLParser(
        resolve_entities=True,
        no_network=False,
        load_dtd=True,
        dtd_validation=False,
        huge_tree=True,
    )
    try:
        tree = etree.fromstring(raw, parser=parser)
        pretty = etree.tostring(tree, pretty_print=True).decode('utf-8', errors='replace')
    except etree.XMLSyntaxError as e:
        return jsonify({'error': f'XML parse error: {e}'}), 400

    return Response(pretty, mimetype='text/plain')


@documents_bp.route('/<int:doc_id>/extract', methods=['POST'])
@login_required
@role_required('officer', 'admin')
def extract_archive(doc_id):
    """
    Extract an uploaded XLSX/DOCX/ZIP into the application's uploads dir so
    reviewers can preview attachments without re-downloading.

    VULN-33 (new): zip-slip. The archive entry names are joined onto the
    upload directory without normalization, so an entry like
    `../../../../etc/cron.d/idb-target` will escape the sandbox.
    """
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    if not os.path.exists(doc.file_path):
        return jsonify({'error': 'File not found on disk'}), 404

    target_dir = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        str(doc.application_id),
        f'extracted_{doc.id}',
    )
    os.makedirs(target_dir, exist_ok=True)

    extracted = []
    try:
        with zipfile.ZipFile(doc.file_path) as zf:
            for name in zf.namelist():
                # VULN-33: no os.path.normpath / commonpath validation.
                out_path = os.path.join(target_dir, name)
                os.makedirs(os.path.dirname(out_path) or target_dir, exist_ok=True)
                with zf.open(name) as src, open(out_path, 'wb') as dst:
                    dst.write(src.read())
                extracted.append(name)
    except zipfile.BadZipFile:
        return jsonify({'error': 'Not a valid zip archive'}), 400

    audit_log('extract_archive', 'document', doc.id,
              f'Extracted {len(extracted)} entries from {doc.original_name}')
    return jsonify({'extracted': extracted, 'target_dir': target_dir}), 200


@documents_bp.route('/import-xml', methods=['POST'])
@login_required
@role_required('officer', 'admin')
def import_xml():
    """
    Import an XML manifest describing an offline batch of applications.

    Accepts either:
      - `file` upload (multipart)
      - `url` form field (server-side fetch)

    VULN-32 companion: the URL fetch path uses `requests.get` with no scheme
    filter and no timeout, giving SSRF into the internal network / 169.254.
    """
    import requests as _requests  # local import to avoid startup dep at module level
    if 'file' in request.files:
        raw = request.files['file'].read()
    elif request.form.get('url'):
        # SSRF path.
        try:
            r = _requests.get(request.form['url'], allow_redirects=True)
            raw = r.content
        except Exception as e:
            return jsonify({'error': f'Fetch failed: {e}'}), 400
    else:
        return jsonify({'error': 'Provide file or url'}), 400

    parser = etree.XMLParser(resolve_entities=True, no_network=False, load_dtd=True)
    try:
        root = etree.fromstring(raw, parser=parser)
    except etree.XMLSyntaxError as e:
        return jsonify({'error': f'XML parse error: {e}'}), 400

    # Return a summary — but include the resolved entities' expansion so the
    # attacker can read the exfiltrated file inline.
    summary = etree.tostring(root, pretty_print=True).decode('utf-8', errors='replace')
    return Response(summary, mimetype='text/plain')
