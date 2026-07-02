from flask import Blueprint, request, jsonify, g
from models import LoanApplication, Supplement, Document, ReviewComment, User, Notification
from middleware.auth import login_required, role_required, audit_log
from app import db
from datetime import datetime
from sqlalchemy import text
import json

applications_bp = Blueprint('applications', __name__)

# Valid status transitions
STATUS_TRANSITIONS = {
    'draft': ['submitted', 'draft'],
    'submitted': ['under_review'],
    'under_review': ['pending_supplement', 'risk_assessment', 'rejected'],
    'pending_supplement': ['under_review', 'rejected'],
    'risk_assessment': ['approved', 'rejected'],
    'approved': ['disbursed'],
    'rejected': ['draft', 'archived'],
    'disbursed': ['archived'],
}


@applications_bp.route('', methods=['GET'])
@login_required
def list_applications():
    user = g.current_user

    if user.role == 'admin':
        query = LoanApplication.query
    elif user.role in ('officer', 'risk'):
        query = LoanApplication.query
    else:  # borrower
        query = LoanApplication.query.filter_by(borrower_id=user.id)

    # VULN-07: Raw query filter from query params
    status = request.args.get('status')
    if status:
        query = query.filter(LoanApplication.status == status)

    applications = query.order_by(LoanApplication.updated_at.desc()).all()
    return jsonify({
        'applications': [app.to_dict() for app in applications],
        'total': len(applications)
    }), 200


@applications_bp.route('/search', methods=['POST'])
@login_required
def search_applications():
    """
    Advanced search with JSON query.
    VULN-07: User-controlled JSON is merged into database query,
    allowing injection of additional filter conditions.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Search query required'}), 400

    user = g.current_user
    base_query = LoanApplication.query

    # Role-based filtering
    if user.role == 'borrower':
        base_query = base_query.filter(LoanApplication.borrower_id == user.id)

    # VULN-07: Directly using user input to construct query conditions
    if 'filters' in data:
        for field, value in data['filters'].items():
            if hasattr(LoanApplication, field):
                # VULN-07: This allows injection via JSON operators
                # Example: {"filters": {"status": "approved", "amount_requested": {"$gt": 100000000}}}
                col = getattr(LoanApplication, field)
                if isinstance(value, dict) and '$gt' in value:
                    base_query = base_query.filter(col > value['$gt'])

    applications = base_query.order_by(LoanApplication.updated_at.desc()).all()
    return jsonify({
        'applications': [app.to_dict() for app in applications],
        'total': len(applications)
    }), 200


@applications_bp.route('/<int:app_id>', methods=['GET'])
@login_required
def get_application(app_id):
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    # VULN-16: Too verbose — reveals total count when not found
    if not application:
        total = LoanApplication.query.count()
        return jsonify({
            'error': f'Application with ID {app_id} not found',
            'total_applications': total,
            'message': 'Please verify the application ID and try again.'
        }), 404

    # Authorization check
    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    result = application.to_dict()

    # Include supplements for reviewers
    if user.role in ('officer', 'risk', 'admin'):
        result['supplements'] = [s.to_dict() for s in application.supplements]

    # Include reviews
    result['reviews'] = [r.to_dict() for r in application.reviews]

    # Include borrower info
    borrower = User.query.get(application.borrower_id)
    if borrower:
        result['borrower'] = {
            'id': borrower.id,
            'full_name': borrower.full_name,
            'country': borrower.country,
            'department': borrower.department,
        }

    return jsonify({'application': result}), 200


@applications_bp.route('', methods=['POST'])
@login_required
@role_required('borrower')
def create_application():
    data = request.get_json()
    required = ['project_name', 'amount_requested', 'currency', 'term_months', 'sector']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # VULN-05: Amount validation is weak — accepts negative, scientific notation
    try:
        amount = float(data['amount_requested'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount format'}), 400

    # Generate app number
    year = datetime.utcnow().year
    month = datetime.utcnow().month
    count = LoanApplication.query.count() + 1
    app_no = f'IDB-{year}-{count:04d}'

    application = LoanApplication(
        app_no=app_no,
        borrower_id=g.current_user.id,
        project_name=data['project_name'],
        project_description=data.get('project_description', ''),
        sector=data.get('sector', ''),
        amount_requested=amount,
        currency=data.get('currency', 'USD'),
        term_months=int(data.get('term_months', 0)),
        purpose=data.get('purpose', ''),
        status='draft'
    )

    db.session.add(application)
    db.session.commit()

    audit_log('create_application', 'loan_application', application.id,
              f'Created application {app_no} for {amount} {data.get("currency", "USD")}')

    return jsonify({'application': application.to_dict(), 'message': 'Application created'}), 201


@applications_bp.route('/<int:app_id>', methods=['PUT'])
@login_required
def update_application(app_id):
    """Update application. Only draft applications can be edited."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    if application.status != 'draft':
        return jsonify({'error': 'Only draft applications can be modified'}), 400

    data = request.get_json()
    editable_fields = ['project_name', 'project_description', 'sector',
                       'amount_requested', 'currency', 'term_months', 'purpose']

    for field in editable_fields:
        if field in data:
            setattr(application, field, data[field])

    application.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'application': application.to_dict(), 'message': 'Application updated'}), 200


@applications_bp.route('/<int:app_id>/status', methods=['PUT'])
@login_required
def update_status(app_id):
    """
    Update application status.
    VULN-09: No enforcement of status transitions. A borrower can
    change status to 'disbursed' directly from 'draft' via this endpoint.
    """
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json()
    new_status = data.get('status')

    if not new_status:
        return jsonify({'error': 'status is required'}), 400

    # VULN-09: Status transition validation exists but can be easily bypassed
    # by not checking user role against the transition rules
    valid_next = STATUS_TRANSITIONS.get(application.status, [])
    if new_status not in valid_next:
        return jsonify({
            'error': f'Invalid status transition from {application.status} to {new_status}',
            'valid_transitions': valid_next
        }), 400

    # VULN-09: Missing role check — any authenticated user can trigger status changes
    old_status = application.status
    application.status = new_status

    # Update timestamps
    if new_status == 'submitted':
        application.submitted_at = datetime.utcnow()
    elif new_status == 'approved':
        application.approved_at = datetime.utcnow()
    elif new_status == 'disbursed':
        application.disbursed_at = datetime.utcnow()

    application.updated_at = datetime.utcnow()
    db.session.commit()

    audit_log('update_status', 'loan_application', application.id,
              f'Status changed from {old_status} to {new_status}')

    return jsonify({'application': application.to_dict(), 'message': 'Status updated'}), 200


@applications_bp.route('/<int:app_id>/approve', methods=['POST'])
@login_required
@role_required('officer', 'admin')
def approve_application(app_id):
    """
    Approve an application.
    VULN-10: Race condition — two officers can approve simultaneously,
    causing duplicate approval or bypassed checks.
    VULN-10: No optimistic locking or distributed lock.
    """
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if application.status not in ('submitted', 'under_review', 'pending_supplement'):
        return jsonify({'error': f'Cannot approve application in {application.status} status'}), 400

    # VULN-10: No lock — two concurrent approvals can proceed
    # VULN-10: No check if another officer already started reviewing

    if user.role == 'officer':
        application.officer_id = user.id

    # Simple approval — in real system would have more checks
    application.status = 'risk_assessment'
    application.reviewed_at = datetime.utcnow()
    application.updated_at = datetime.utcnow()
    db.session.commit()

    audit_log('approve_application', 'loan_application', application.id,
              f'Application {application.app_no} moved to risk assessment by {user.username}')

    # Create notification for risk analysts
    risk_users = User.query.filter_by(role='risk', is_active=True).all()
    for ru in risk_users:
        notif = Notification(user_id=ru.id, title='New Application for Risk Assessment',
                             message=f'Application {application.app_no} ({application.project_name}) requires risk assessment.',
                             type='task', related_type='loan_application', related_id=app_id)
        db.session.add(notif)
    db.session.commit()

    return jsonify({'message': 'Application moved to risk assessment', 'application': application.to_dict()}), 200


@applications_bp.route('/<int:app_id>/risk-assessment', methods=['POST'])
@login_required
@role_required('risk', 'admin')
def submit_risk_assessment(app_id):
    """Submit risk assessment for an application."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if application.status != 'risk_assessment':
        return jsonify({'error': 'Application is not in risk assessment phase'}), 400

    data = request.get_json()
    decision = data.get('decision', '')  # 'approved' or 'rejected'
    interest_rate = data.get('interest_rate', None)

    # VULN-11: Interest rate calculation has rounding issue
    # For very small amounts, the calculated annual interest may round to 0
    if interest_rate is not None:
        try:
            rate = float(interest_rate)
            if rate < 0 or rate > 50:
                return jsonify({'error': 'Interest rate must be between 0 and 50'}), 400
            application.interest_rate = rate
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid interest rate format'}), 400

    application.risk_analyst_id = user.id

    if decision == 'approved':
        application.status = 'approved'
        application.approved_at = datetime.utcnow()
    elif decision == 'rejected':
        application.rejection_reason = data.get('reason', 'Rejected by risk assessment')
        application.status = 'rejected'
    else:
        return jsonify({'error': 'Invalid decision. Use "approved" or "rejected".'}), 400

    application.updated_at = datetime.utcnow()
    db.session.commit()

    audit_log('risk_assessment', 'loan_application', application.id,
              f'Risk assessment: {decision}, rate={interest_rate}')

    return jsonify({'message': f'Risk assessment {decision}', 'application': application.to_dict()}), 200


@applications_bp.route('/<int:app_id>/supplements', methods=['POST'])
@login_required
@role_required('officer', 'risk', 'admin')
def request_supplement(app_id):
    """Request additional documentation from the borrower."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json()
    description = data.get('description', '')

    supplement = Supplement(
        application_id=app_id,
        requested_by=user.id,
        description=description,
        status='pending'
    )
    db.session.add(supplement)

    # Update application status
    application.status = 'pending_supplement'
    application.updated_at = datetime.utcnow()
    db.session.commit()

    # Notify borrower
    notif = Notification(
        user_id=application.borrower_id,
        title='Additional Information Required',
        message=f'Officer has requested additional information for application {application.app_no}: {description}',
        type='action_required',
        related_type='loan_application',
        related_id=app_id
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({'message': 'Supplement requested', 'supplement': supplement.to_dict()}), 201


@applications_bp.route('/<int:app_id>/supplements/<int:supp_id>/respond', methods=['POST'])
@login_required
@role_required('borrower')
def respond_supplement(app_id, supp_id):
    """Respond to a supplement request."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application or application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    supplement = Supplement.query.get(supp_id)
    if not supplement or supplement.application_id != app_id:
        return jsonify({'error': 'Supplement not found'}), 404

    data = request.get_json()
    # VULN-06: Stored XSS — response text is not sanitized
    supplement.response = data.get('response', '')
    supplement.status = 'responded'
    supplement.responded_at = datetime.utcnow()

    application.status = 'under_review'
    application.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'message': 'Supplement responded', 'supplement': supplement.to_dict()}), 200


@applications_bp.route('/<int:app_id>/review', methods=['POST'])
@login_required
@role_required('officer', 'risk', 'admin')
def add_review(app_id):
    """Add a review comment to an application."""
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json()

    review = ReviewComment(
        application_id=app_id,
        user_id=user.id,
        comment=data.get('comment', ''),
        rating=data.get('rating'),
        checklist=data.get('checklist')
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({'message': 'Review added', 'review': review.to_dict()}), 201


@applications_bp.route('/<int:app_id>/calculate-interest', methods=['POST'])
@login_required
def calculate_interest(app_id):
    """
    Calculate interest for a loan application.
    VULN-11: Rounding vulnerability — small amounts can result in 0 interest.
    """
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json()
    rate = data.get('rate', float(application.interest_rate or 2.0))
    months = data.get('months', application.term_months or 12)
    amount = float(data.get('amount', application.amount_requested or 1000000))

    # VULN-11: Simple interest calculation without proper rounding
    # For small amounts + low rates, total interest rounds to 0
    annual_interest = amount * (rate / 100)
    total_interest = annual_interest * (months / 12)

    return jsonify({
        'principal': amount,
        'annual_rate': rate,
        'term_months': months,
        'annual_interest': round(annual_interest, 2),
        'total_interest': round(total_interest, 2),
        'total_repayment': round(amount + total_interest, 2),
    }), 200
