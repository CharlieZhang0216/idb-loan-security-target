from flask import Blueprint, request, jsonify, g, send_file, current_app
from middleware.auth import login_required, role_required, audit_log
from models import Document, LoanApplication
from app import db
import os
import uuid
import hashlib
import magic  # python-magic

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
    'image/jpeg',
    'image/png',
    'image/svg+xml',  # VULN-17: SVG allowed — SVG XSS possible
}


@documents_bp.route('/upload/<int:app_id>', methods=['POST'])
@login_required
@role_required('borrower', 'admin')
def upload_document(app_id):
    """Upload a document to an application."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    original_name = file.filename
    file_data = file.read()
    file.seek(0)

    # VULN-17: MIME type check but SVG is allowed — SVG files can contain XSS
    mime_type = magic.from_buffer(file_data, mime=True)
    if mime_type not in ALLOWED_MIME:
        return jsonify({'error': f'File type {mime_type} not allowed'}), 400

    # VULN-17: No file content scanning for embedded scripts
    file_size = len(file_data)
    file_hash = hashlib.sha256(file_data).hexdigest()

    # Generate unique filename
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else 'bin'
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    # Save file
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(app_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)
    file.save(file_path)

    # Record in database
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
        description=description
    )
    db.session.add(doc)
    db.session.commit()

    audit_log('upload_document', 'document', doc.id,
              f'Uploaded {original_name} to application {app_id}')

    return jsonify({'document': doc.to_dict(), 'message': 'Document uploaded'}), 201


@documents_bp.route('/<int:doc_id>', methods=['GET'])
@login_required
def get_document(doc_id):
    """Download a document."""
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    # Check access
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
        download_name=doc.original_name
    )


@documents_bp.route('/application/<int:app_id>', methods=['GET'])
@login_required
def list_documents(app_id):
    """List all documents for an application."""
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
    """Delete a document. VULN-13: File on disk is not deleted."""
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404

    user = g.current_user
    application = LoanApplication.query.get(doc.application_id)
    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    # VULN-13: Only deletes DB record, file remains on disk
    db.session.delete(doc)
    db.session.commit()

    return jsonify({'message': 'Document deleted'}), 200
