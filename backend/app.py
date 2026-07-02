from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name
import os
import redis

db = SQLAlchemy()
redis_client = None
_app = None


def create_app(config_name=None):
    global _app, redis_client

    if _app is not None:
        return _app

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    db.init_app(app)

    with app.app_context():
        # Register routes
        from routes.auth import auth_bp
        from routes.applications import applications_bp
        from routes.documents import documents_bp
        from routes.reports import reports_bp
        from routes.admin_routes import admin_bp
        from routes.graphql_routes import graphql_bp

        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(applications_bp, url_prefix='/api/applications')
        app.register_blueprint(documents_bp, url_prefix='/api/documents')
        app.register_blueprint(reports_bp, url_prefix='/api/reports')
        app.register_blueprint(admin_bp, url_prefix='/api/admin')
        app.register_blueprint(graphql_bp, url_prefix='/graphql')

    try:
        redis_client = redis.from_url(app.config['REDIS_URL'], decode_responses=True)
        redis_client.ping()
    except Exception:
        redis_client = None

    # VULN-14: Swagger UI exposed in production
    # API docs accessible via Swagger UI (if flask-swagger-ui installed)

    # VULN-16: Overly verbose error messages
    @app.errorhandler(404)
    def not_found(error):
        from flask import jsonify
        return jsonify({'error': str(error), 'message': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        import traceback
        return jsonify({
            'error': 'Internal server error',
            'detail': str(error),
            'traceback': traceback.format_exc()
        }), 500

    _app = app
    return app


if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5001)
