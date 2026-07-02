from flask import Blueprint, request, jsonify, g
from graphene import ObjectType, String, Int, Float, List, Field, Schema
from middleware.auth import login_required
from models import User, LoanApplication
from app import db
from sqlalchemy import text
import json

graphql_bp = Blueprint('graphql', __name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class UserType(ObjectType):
    id = Int()
    username = String()
    email = String()
    role = String()
    full_name = String()
    country = String()
    department = String()
    employee_id = String()
    # NOTE: `notes` is a stored profile field written via /api/auth/me
    # (VULN-26 mass assignment). It is surfaced verbatim into `admin_report`
    # via raw SQL — completing the second-order SQLi (VULN-37).
    notes = String()


class ApplicationType(ObjectType):
    id = Int()
    app_no = String()
    project_name = String()
    project_description = String()
    sector = String()
    amount_requested = String()
    currency = String()
    term_months = Int()
    status = String()
    borrower_id = Int()
    borrower = Field(UserType)
    officer_id = Int()
    risk_analyst_id = Int()
    approved_at = String()
    created_at = String()
    updated_at = String()

    def resolve_borrower(self, info):
        return User.query.get(self.borrower_id)


class Query(ObjectType):
    applications = List(ApplicationType, status=String())
    application = Field(ApplicationType, id=Int(required=True))
    users = List(UserType)
    user = Field(UserType, id=Int())

    # VULN-15 kept
    admin_all_users = List(UserType)
    admin_system_health = String()

    # VULN-36 (new): admin_report accepts a `filter` string that is
    # interpolated into a raw SQL WHERE clause. Combined with GraphQL
    # aliasing, the attacker can call this once per alias in a single
    # request, evading naive per-endpoint rate-limits.
    admin_report = String(filter=String())

    def resolve_applications(self, info, status=None):
        query = LoanApplication.query
        if status:
            query = query.filter(LoanApplication.status == status)
        return query.order_by(LoanApplication.updated_at.desc()).limit(50).all()

    def resolve_application(self, info, id):
        return LoanApplication.query.get(id)

    def resolve_users(self, info):
        return User.query.limit(20).all()

    def resolve_user(self, info, id):
        return User.query.get(id)

    def resolve_admin_all_users(self, info):
        # VULN-15 kept: no role check
        return User.query.all()

    def resolve_admin_system_health(self, info):
        return json.dumps({
            'status': 'healthy',
            'database': 'connected',
            'redis': 'connected',
            'version': '2.4.1',
        })

    def resolve_admin_report(self, info, filter=None):
        # VULN-36 second-order SQLi via `notes` -> `filter` reflection.
        f = filter or "1=1"
        try:
            rows = db.session.execute(
                text(f"SELECT id, username, notes FROM users WHERE {f}")
            ).fetchall()
            return json.dumps([{'id': r[0], 'username': r[1], 'notes': r[2]} for r in rows])
        except Exception as e:
            return json.dumps({'error': str(e)})


schema = Schema(query=Query)


# ---------------------------------------------------------------------------
# HTTP wiring
# ---------------------------------------------------------------------------

@graphql_bp.route('', methods=['POST'])
@login_required
def graphql_endpoint():
    """
    GraphQL endpoint.

    VULN-36 companion (batch bypass): if the request body is a JSON list,
    we execute each query in the list independently. This lets the client
    smuggle multiple queries in a single POST — including alias-heavy ones
    that hit `admin_all_users` many times, effectively bypassing per-endpoint
    rate limits and audit-log volume alerts.
    """
    data = request.get_json()
    if isinstance(data, list):
        out = []
        for entry in data:
            q = (entry or {}).get('query', '')
            if not q:
                out.append({'error': 'query required'})
                continue
            r = schema.execute(q, variable_values=(entry or {}).get('variables'))
            out.append({'data': r.data, 'errors': [str(e) for e in (r.errors or [])]})
        return jsonify(out), 200

    if not data:
        return jsonify({'error': 'Body required'}), 400
    query_str = data.get('query', '')
    if not query_str:
        return jsonify({'error': 'Query required'}), 400

    result = schema.execute(query_str, variable_values=data.get('variables'))
    if result.errors:
        return jsonify({'errors': [str(e) for e in result.errors]}), 400

    return jsonify({'data': result.data}), 200


@graphql_bp.route('/schema', methods=['GET'])
def graphql_schema():
    """VULN-15 kept: schema introspection endpoint exposed."""
    return jsonify({'schema': str(schema)}), 200
