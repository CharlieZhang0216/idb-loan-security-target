import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'idb-app-secret-key-prod-2024')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'idb-jwt-ultra-secret-key-2024!')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://idb_admin:idb_p@ss_2024@localhost:5432/idb_loan'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 3600,
    }

    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

    SSO_ENABLED = True
    SSO_SECRET = os.environ.get('SSO_SECRET', 'sso-shared-secret-do-not-leak')
    SSO_CALLBACK_URL = '/api/auth/sso/callback'

    RATELIMIT_ENABLED = False  # VULN-F: Rate limiting disabled in production

    DEBUG = False
    TESTING = False

    # Allowed file extensions for upload
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'jpg', 'jpeg', 'png'}

    # Admin reset token — VULN-03: weak reset mechanism
    ADMIN_RESET_TOKEN = os.environ.get('ADMIN_RESET_TOKEN', 'admin-master-reset-t0ken')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
