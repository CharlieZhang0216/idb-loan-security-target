from app import db
from datetime import datetime
import hashlib


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    country = db.Column(db.String(64))
    department = db.Column(db.String(128))
    employee_id = db.Column(db.String(32), unique=True)
    phone = db.Column(db.String(32))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('LoanApplication', foreign_keys='LoanApplication.borrower_id', backref='borrower', lazy=True)
    assigned_applications = db.relationship('LoanApplication', foreign_keys='LoanApplication.officer_id', backref='officer', lazy=True)
    risk_applications = db.relationship('LoanApplication', foreign_keys='LoanApplication.risk_analyst_id', backref='risk_analyst', lazy=True)

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'full_name': self.full_name,
            'country': self.country,
            'department': self.department,
            'phone': self.phone,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            data['employee_id'] = self.employee_id
            data['last_login'] = self.last_login.isoformat() if self.last_login else None
        return data


class LoanApplication(db.Model):
    __tablename__ = 'loan_applications'

    id = db.Column(db.Integer, primary_key=True)
    app_no = db.Column(db.String(32), unique=True, nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_name = db.Column(db.String(256), nullable=False)
    project_description = db.Column(db.Text)
    sector = db.Column(db.String(64))
    amount_requested = db.Column(db.Numeric(18, 2))
    currency = db.Column(db.String(3), default='USD')
    term_months = db.Column(db.Integer)
    interest_rate = db.Column(db.Numeric(6, 4))
    purpose = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')
    officer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    risk_analyst_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    rejection_reason = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    disbursed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    supplements = db.relationship('Supplement', backref='application', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='application', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('ReviewComment', backref='application', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'app_no': self.app_no,
            'borrower_id': self.borrower_id,
            'project_name': self.project_name,
            'project_description': self.project_description,
            'sector': self.sector,
            'amount_requested': str(self.amount_requested) if self.amount_requested else None,
            'currency': self.currency,
            'term_months': self.term_months,
            'interest_rate': str(self.interest_rate) if self.interest_rate else None,
            'purpose': self.purpose,
            'status': self.status,
            'officer_id': self.officer_id,
            'risk_analyst_id': self.risk_analyst_id,
            'rejection_reason': self.rejection_reason,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'disbursed_at': self.disbursed_at.isoformat() if self.disbursed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Supplement(db.Model):
    __tablename__ = 'supplements'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('loan_applications.id'))
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    description = db.Column(db.Text)
    response = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)

    requester = db.relationship('User', foreign_keys=[requested_by])

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'requested_by': self.requested_by,
            'requester_name': self.requester.full_name if self.requester else None,
            'description': self.description,
            'response': self.response,
            'status': self.status,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
        }


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('loan_applications.id'))
    supplement_id = db.Column(db.Integer, db.ForeignKey('supplements.id'))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    filename = db.Column(db.String(256), nullable=False)
    original_name = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(64))
    file_size = db.Column(db.Integer)
    file_hash = db.Column(db.String(128))
    category = db.Column(db.String(64))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'supplement_id': self.supplement_id,
            'uploaded_by': self.uploaded_by,
            'uploader_name': self.uploader.full_name if self.uploader else None,
            'filename': self.filename,
            'original_name': self.original_name,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'category': self.category,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReviewComment(db.Model):
    __tablename__ = 'review_comments'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('loan_applications.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment = db.Column(db.Text)
    rating = db.Column(db.Integer)
    checklist = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'user_id': self.user_id,
            'reviewer_name': self.reviewer.full_name if self.reviewer else None,
            'comment': self.comment,
            'rating': self.rating,
            'checklist': self.checklist,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(64))
    action = db.Column(db.String(128))
    resource_type = db.Column(db.String(64))
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SystemConfig(db.Model):
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(256))
    message = db.Column(db.Text)
    type = db.Column(db.String(32), default='info')
    is_read = db.Column(db.Boolean, default=False)
    related_type = db.Column(db.String(64))
    related_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'related_type': self.related_type,
            'related_id': self.related_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
