from flask import Blueprint, request, jsonify, g
from graphene import ObjectType, String, Int, Float, List, Field, Schema
from middleware.auth import login_required
from models import User, LoanApplication
from app import db
import json

graphql_bp = Blueprint('graphql', __name__)


# GraphQL schema
class UserType(ObjectType):
    id = Int()
    username = String()
    email = String()
    role = String()
    full_name = String()
    country = String()
    department = String()
    employee_id = String()


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


# VULN-15: GraphQL introspection enabled — allows schema enumeration
# VULN-15: Admin-only queries are visible via introspection
class Query(ObjectType):
    applications = List(ApplicationType, status=String())
    application = Field(ApplicationType, id=Int(required=True))
    users = List(UserType)
    user = Field(UserType, id=Int())

    # VULN-15: These admin queries are visible in schema introspection
    # but there's no role check in the resolvers
    admin_all_users = List(UserType)
    admin_system_health = String()

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
        app = LoanApplication.query.get(id)
        if app:
            return User.query.get(app.borrower_id)
        return None

    def resolve_admin_all_users(self, info):
        # VULN-15: No role check — any authenticated user can query
        return User.query.all()

    def resolve_admin_system_health(self, info):
        return json.dumps({
            'status': 'healthy',
            'database': 'connected',
            'redis': 'connected',
            'version': '2.4.1'
        })


schema = Schema(query=Query)


@graphql_bp.route('', methods=['POST'])
@login_required
def graphql_endpoint():
    """GraphQL endpoint."""
    data = request.get_json()
    query_str = data.get('query', '')

    if not query_str:
        return jsonify({'error': 'Query required'}), 400

    result = schema.execute(query_str)
    if result.errors:
        return jsonify({'errors': [str(e) for e in result.errors]}), 400

    return jsonify({'data': result.data}), 200


@graphql_bp.route('/schema', methods=['GET'])
def graphql_schema():
    """VULN-15: GraphQL schema introspection endpoint exposed."""
    return jsonify({'schema': str(schema)}), 200
