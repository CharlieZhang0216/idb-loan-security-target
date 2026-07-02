from flask import Blueprint, request, jsonify, g
from models import LoanApplication, Supplement, Document, ReviewComment, User, Notification
from middleware.auth import login_required, role_required, audit_log
from app import db
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import json

applications_bp = Blueprint('applications', __name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
# NOTE: 'submitted' -> 'rejected' is included so that officers can quick-reject
# obviously-bad submissions from the review queue (fixes previous 400 error).
STATUS_TRANSITIONS = {
    'draft':               ['submitted', 'draft'],
    'submitted':           ['under_review', 'rejected'],
    'under_review':        ['pending_supplement', 'risk_assessment', 'rejected'],
    'pending_supplement':  ['under_review', 'rejected'],
    'risk_assessment':     ['approved', 'rejected'],
    'approved':            ['disbursed', 'rejected'],
    'rejected':            ['draft', 'archived'],
    'disbursed':           ['archived'],
    'archived':            [],
}

# Role -> statuses that role is allowed to move an application INTO.
# VULN-09 kept: still weak — admin bypasses everything, and the check happens
# only if the caller is not admin. Officer/risk share more transitions than
# strictly necessary. This is intentional for the target.
ROLE_ALLOWED_TARGETS = {
    'borrower': {'draft', 'submitted', 'archived'},
    'officer':  {'under_review', 'pending_supplement', 'risk_assessment', 'rejected', 'archived'},
    'risk':     {'approved', 'rejected', 'archived'},
    'admin':    None,  # None = wildcard
}


def _transition(application, new_status, user, extra_note=''):
    """
    Central state-transition helper.

    Returns (ok: bool, error_message: str | None).
    Callers are responsible for db.session.commit().
    """
    old_status = application.status
    valid_next = STATUS_TRANSITIONS.get(old_status, [])
    if new_status not in valid_next:
        return False, f'Invalid status transition from {old_status} to {new_status}'

    allowed = ROLE_ALLOWED_TARGETS.get(user.role)
    if allowed is not None and new_status not in allowed:
        return False, f'Role "{user.role}" cannot transition into "{new_status}"'

    application.status = new_status

    now = datetime.utcnow()
    if new_status == 'submitted' and not application.submitted_at:
        application.submitted_at = now
    elif new_status == 'under_review' and not application.reviewed_at:
        application.reviewed_at = now
    elif new_status == 'approved' and not application.approved_at:
        application.approved_at = now
    elif new_status == 'disbursed' and not application.disbursed_at:
        application.disbursed_at = now
    application.updated_at = now

    audit_log('transition', 'loan_application', application.id,
              f'{old_status} -> {new_status} by {user.username} {extra_note}'.strip())
    return True, None


def _next_app_no():
    """
    Generate the next application number using a Postgres sequence to avoid
    the count(*)+1 race that caused unique-constraint collisions when two
    borrowers submitted concurrently.

    The sequence `loan_app_no_seq` is created in db/init.sql. We fall back
    to a MAX(id)+1 read for local sqlite dev runs.
    """
    year = datetime.utcnow().year
    try:
        row = db.session.execute(text("SELECT nextval('loan_app_no_seq')")).scalar()
        return f'IDB-{year}-{int(row):04d}'
    except Exception:
        db.session.rollback()
        # Dev fallback — still not perfect, but won't crash on non-PG backends.
        max_id = db.session.query(db.func.coalesce(db.func.max(LoanApplication.id), 0)).scalar()
        return f'IDB-{year}-{int(max_id) + 1:04d}'


def _apply_method_override():
    """
    VULN-30: If the request carries `X-HTTP-Method-Override` we treat the
    request as if it were made with that method. This lets an attacker
    smuggle state-changing PUT/POST calls through GET requests that pass
    less strict CORS/CSRF review. We deliberately do this globally on
    application state endpoints only, so scanners looking at the OpenAPI
    spec will not see it.
    """
    override = request.headers.get('X-HTTP-Method-Override')
    if override:
        request.environ['REQUEST_METHOD'] = override.upper()


@applications_bp.before_request
def _before():
    _apply_method_override()


# ---------------------------------------------------------------------------
# List / search / detail
# ---------------------------------------------------------------------------

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

    # VULN-07 kept
    status = request.args.get('status')
    if status:
        query = query.filter(LoanApplication.status == status)

    # Cheap pagination so the applications view no longer has to N+1.
    try:
        page = max(int(request.args.get('page', 1)), 1)
        per_page = min(max(int(request.args.get('per_page', 50)), 1), 200)
    except ValueError:
        page, per_page = 1, 50

    total = query.count()
    applications = (query
                    .order_by(LoanApplication.updated_at.desc())
                    .offset((page - 1) * per_page)
                    .limit(per_page)
                    .all())

    # Batch load borrowers to eliminate N+1 in the frontend list view.
    borrower_ids = {a.borrower_id for a in applications if a.borrower_id}
    borrowers = {u.id: u for u in User.query.filter(User.id.in_(borrower_ids)).all()} if borrower_ids else {}

    items = []
    for app in applications:
        d = app.to_dict()
        b = borrowers.get(app.borrower_id)
        if b:
            d['borrower'] = {
                'id': b.id,
                'full_name': b.full_name,
                'country': b.country,
            }
        items.append(d)

    return jsonify({
        'applications': items,
        'total': total,
        'page': page,
        'per_page': per_page,
    }), 200


@applications_bp.route('/search', methods=['POST'])
@login_required
def search_applications():
    """
    Advanced search with JSON query.
    VULN-07 kept: user-controlled JSON is merged into database query.
    VULN-37 (new): the raw `sort` parameter is concatenated into ORDER BY.
    Use { "sort": "id) UNION SELECT ..." } for a second-order SQLi via the
    reports export path (see reports.py).
    """
    data = request.get_json() or {}

    user = g.current_user
    base_query = LoanApplication.query

    if user.role == 'borrower':
        base_query = base_query.filter(LoanApplication.borrower_id == user.id)

    if 'filters' in data:
        for field, value in data['filters'].items():
            if hasattr(LoanApplication, field):
                col = getattr(LoanApplication, field)
                if isinstance(value, dict) and '$gt' in value:
                    base_query = base_query.filter(col > value['$gt'])
                elif isinstance(value, dict) and '$in' in value:
                    base_query = base_query.filter(col.in_(value['$in']))
                elif isinstance(value, (str, int, float)):
                    base_query = base_query.filter(col == value)

    # VULN-37: sort field is stashed for later use in raw SQL by reports.
    sort = data.get('sort')
    if sort and isinstance(sort, str):
        # Persist the last search preference on the user for report re-use.
        # (See reports.export — this preference is later interpolated into
        # a raw SQL string.)
        pref = user.__dict__.setdefault('_report_prefs', {})
        pref['sort'] = sort

    applications = base_query.order_by(LoanApplication.updated_at.desc()).all()
    return jsonify({
        'applications': [app.to_dict() for app in applications],
        'total': len(applications),
    }), 200


@applications_bp.route('/<int:app_id>', methods=['GET'])
@login_required
def get_application(app_id):
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        # VULN-16 kept
        total = LoanApplication.query.count()
        return jsonify({
            'error': f'Application with ID {app_id} not found',
            'total_applications': total,
        }), 404

    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    result = application.to_dict()

    if user.role in ('officer', 'risk', 'admin'):
        result['supplements'] = [s.to_dict() for s in application.supplements]
    else:
        result['supplements'] = [
            s.to_dict() for s in application.supplements
            if s.requested_by == user.id or application.borrower_id == user.id
        ]

    result['reviews'] = [r.to_dict() for r in application.reviews]
    result['documents'] = [d.to_dict() for d in application.documents]

    borrower = User.query.get(application.borrower_id)
    if borrower:
        result['borrower'] = {
            'id': borrower.id,
            'full_name': borrower.full_name,
            'country': borrower.country,
            'department': borrower.department,
        }

    return jsonify({'application': result}), 200


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------

@applications_bp.route('', methods=['POST'])
@login_required
@role_required('borrower')
def create_application():
    data = request.get_json() or {}
    required = ['project_name', 'amount_requested', 'currency', 'term_months', 'sector']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # VULN-05 kept: still accepts scientific notation and negative values.
    # VULN-28 (new): negatives are explicitly PERMITTED here. Downstream
    # calculate-interest happily produces negative interest, meaning the
    # bank pays the borrower. See VULNERABILITIES.md for the arbitrage path.
    try:
        amount = float(data['amount_requested'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount format'}), 400

    # Retry a couple of times in case two borrowers race the same sequence
    # value under a fallback backend.
    for attempt in range(3):
        app_no = _next_app_no()
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
            status='draft',
        )
        db.session.add(application)
        try:
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            if attempt == 2:
                return jsonify({'error': 'Failed to allocate application number'}), 500

    audit_log('create_application', 'loan_application', application.id,
              f'Created application {app_no} for {amount} {data.get("currency", "USD")}')

    return jsonify({'application': application.to_dict(), 'message': 'Application created'}), 201


@applications_bp.route('/<int:app_id>', methods=['PUT'])
@login_required
def update_application(app_id):
    """
    Edit an application.

    Rule: only draft applications may be edited by borrowers.

    VULN-31 (new): the `currency` field is silently editable on APPROVED
    applications too, without re-approval. Combined with a favourable
    interest rate lock-in from a low-rate currency approval, an attacker
    can flip to a high-rate currency after approval and disburse under
    inconsistent terms. See VULNERABILITIES.md.
    """
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json() or {}

    if application.status == 'draft':
        editable_fields = ['project_name', 'project_description', 'sector',
                           'amount_requested', 'currency', 'term_months', 'purpose']
    elif application.status in ('approved', 'disbursed') and user.role == 'borrower':
        # VULN-31: currency post-approval flip.
        editable_fields = ['currency']
    else:
        return jsonify({'error': 'Only draft applications can be modified'}), 400

    for field in editable_fields:
        if field in data:
            setattr(application, field, data[field])

    application.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'application': application.to_dict(), 'message': 'Application updated'}), 200


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

@applications_bp.route('/<int:app_id>/status', methods=['PUT'])
@login_required
def update_status(app_id):
    """
    Update application status via the state machine.
    """
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json() or {}
    new_status = data.get('status')
    if not new_status:
        return jsonify({'error': 'status is required'}), 400

    if user.role == 'borrower' and application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    ok, err = _transition(application, new_status, user,
                          extra_note=f'via /status: {data.get("reason", "")}')
    if not ok:
        return jsonify({'error': err}), 400

    if new_status == 'rejected' and data.get('reason'):
        application.rejection_reason = data['reason']

    db.session.commit()
    return jsonify({'application': application.to_dict(), 'message': 'Status updated'}), 200


@applications_bp.route('/<int:app_id>/submit', methods=['POST'])
@login_required
@role_required('borrower')
def submit_application(app_id):
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404
    if application.borrower_id != g.current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    ok, err = _transition(application, 'submitted', g.current_user)
    if not ok:
        return jsonify({'error': err}), 400
    db.session.commit()
    return jsonify({'application': application.to_dict()}), 200


@applications_bp.route('/<int:app_id>/pick-up', methods=['POST'])
@login_required
@role_required('officer', 'admin')
def pick_up_application(app_id):
    """Officer claims an application for review."""
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    ok, err = _transition(application, 'under_review', g.current_user)
    if not ok:
        return jsonify({'error': err}), 400

    if g.current_user.role == 'officer':
        application.officer_id = g.current_user.id
    db.session.commit()
    return jsonify({'application': application.to_dict()}), 200


@applications_bp.route('/<int:app_id>/reject', methods=['POST'])
@login_required
@role_required('officer', 'risk', 'admin')
def reject_application(app_id):
    """Officer or risk analyst rejects the application."""
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json() or {}
    reason = data.get('reason', 'Rejected')

    ok, err = _transition(application, 'rejected', g.current_user, extra_note=f'reason={reason}')
    if not ok:
        return jsonify({'error': err}), 400

    application.rejection_reason = reason
    db.session.commit()

    # Notify borrower
    try:
        db.session.add(Notification(
            user_id=application.borrower_id,
            title='Application Rejected',
            message=f'{application.app_no} was rejected: {reason}',
            type='status',
            related_type='loan_application',
            related_id=app_id,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({'application': application.to_dict()}), 200


@applications_bp.route('/<int:app_id>/approve', methods=['POST'])
@login_required
@role_required('officer', 'admin')
def approve_application(app_id):
    """
    Officer moves an application into risk assessment.

    VULN-10 kept: no distributed lock.
    VULN-29 (new): the SELECT is done outside a transaction and the officer_id
    write happens without SELECT ... FOR UPDATE. Two officers approving in
    parallel will both write their own officer_id, and both notifications go
    out — but the last commit wins for the officer_id column. Combined with
    verb-tampering (VULN-30) an attacker can even trigger this via GET.
    """
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if application.status not in ('submitted', 'under_review', 'pending_supplement'):
        return jsonify({'error': f'Cannot approve application in {application.status} status'}), 400

    ok, err = _transition(application, 'risk_assessment', user)
    if not ok:
        return jsonify({'error': err}), 400

    if user.role == 'officer':
        application.officer_id = user.id

    db.session.commit()

    risk_users = User.query.filter_by(role='risk', is_active=True).all()
    for ru in risk_users:
        db.session.add(Notification(
            user_id=ru.id,
            title='New Application for Risk Assessment',
            message=f'Application {application.app_no} ({application.project_name}) requires risk assessment.',
            type='task',
            related_type='loan_application',
            related_id=app_id,
        ))
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

    data = request.get_json() or {}
    decision = data.get('decision', '')
    interest_rate = data.get('interest_rate', None)

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
        ok, err = _transition(application, 'approved', user)
    elif decision == 'rejected':
        application.rejection_reason = data.get('reason', 'Rejected by risk assessment')
        ok, err = _transition(application, 'rejected', user)
    else:
        return jsonify({'error': 'Invalid decision. Use "approved" or "rejected".'}), 400

    if not ok:
        return jsonify({'error': err}), 400

    db.session.commit()

    audit_log('risk_assessment', 'loan_application', application.id,
              f'Risk assessment: {decision}, rate={interest_rate}')

    return jsonify({'message': f'Risk assessment {decision}', 'application': application.to_dict()}), 200


@applications_bp.route('/<int:app_id>/disburse', methods=['POST'])
@login_required
@role_required('admin', 'officer')
def disburse_application(app_id):
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404
    ok, err = _transition(application, 'disbursed', g.current_user)
    if not ok:
        return jsonify({'error': err}), 400
    db.session.commit()
    return jsonify({'application': application.to_dict()}), 200


# ---------------------------------------------------------------------------
# Supplements & reviews
# ---------------------------------------------------------------------------

@applications_bp.route('/<int:app_id>/supplements', methods=['POST'])
@login_required
@role_required('officer', 'risk', 'admin')
def request_supplement(app_id):
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json() or {}
    description = data.get('description', '')

    supplement = Supplement(
        application_id=app_id,
        requested_by=user.id,
        description=description,
        status='pending',
    )
    db.session.add(supplement)

    ok, err = _transition(application, 'pending_supplement', user)
    if not ok:
        db.session.rollback()
        return jsonify({'error': err}), 400
    db.session.commit()

    db.session.add(Notification(
        user_id=application.borrower_id,
        title='Additional Information Required',
        message=f'Officer has requested additional information for application {application.app_no}: {description}',
        type='action_required',
        related_type='loan_application',
        related_id=app_id,
    ))
    db.session.commit()

    return jsonify({'message': 'Supplement requested', 'supplement': supplement.to_dict()}), 201


@applications_bp.route('/<int:app_id>/supplements/<int:supp_id>/respond', methods=['POST'])
@login_required
@role_required('borrower')
def respond_supplement(app_id, supp_id):
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application or application.borrower_id != user.id:
        return jsonify({'error': 'Access denied'}), 403

    supplement = Supplement.query.get(supp_id)
    if not supplement or supplement.application_id != app_id:
        return jsonify({'error': 'Supplement not found'}), 404

    data = request.get_json() or {}
    # VULN-06 kept: stored XSS via response text (rendered with v-html)
    supplement.response = data.get('response', '')
    supplement.status = 'responded'
    supplement.responded_at = datetime.utcnow()

    _transition(application, 'under_review', user, extra_note='supplement responded')
    db.session.commit()

    return jsonify({'message': 'Supplement responded', 'supplement': supplement.to_dict()}), 200


@applications_bp.route('/<int:app_id>/review', methods=['POST'])
@login_required
@role_required('officer', 'risk', 'admin')
def add_review(app_id):
    user = g.current_user
    application = LoanApplication.query.get(app_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json() or {}

    review = ReviewComment(
        application_id=app_id,
        user_id=user.id,
        comment=data.get('comment', ''),
        rating=data.get('rating'),
        checklist=data.get('checklist'),
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({'message': 'Review added', 'review': review.to_dict()}), 201


# ---------------------------------------------------------------------------
# Interest calculation
# ---------------------------------------------------------------------------

@applications_bp.route('/<int:app_id>/calculate-interest', methods=['POST'])
@login_required
def calculate_interest(app_id):
    """
    Calculate interest for a loan application.

    VULN-11 kept: rounding lets small amounts + low rates round to 0.
    VULN-28 (new companion): negative principals produce negative total
    interest — arbitrage path when combined with the create endpoint.
    """
    application = LoanApplication.query.get(app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json() or {}
    rate = data.get('rate', float(application.interest_rate or 2.0))
    months = data.get('months', application.term_months or 12)
    amount = float(data.get('amount', application.amount_requested or 1000000))

    annual_interest = amount * (float(rate) / 100)
    total_interest = annual_interest * (float(months) / 12)

    return jsonify({
        'principal': amount,
        'annual_rate': rate,
        'term_months': months,
        'annual_interest': round(annual_interest, 2),
        'total_interest': round(total_interest, 2),
        'total_repayment': round(amount + total_interest, 2),
    }), 200
