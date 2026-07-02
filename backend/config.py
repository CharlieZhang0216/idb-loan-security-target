import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'idb-app-secret-key-prod-2024')

    # Symmetric fallback secret (VULN-01)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'idb-jwt-ultra-secret-key-2024!')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # RS256 pubkey path — used by kid-based key resolution (VULN-21/22)
    # If a JWT has header {"kid": "<path>"} we load that path from disk as the verification key.
    JWT_KEYS_DIR = os.environ.get('JWT_KEYS_DIR', '/app/keys')

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://idb_admin:idb_p%40ss_2024@localhost:5432/idb_loan'
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

    RATELIMIT_ENABLED = False  # VULN-F: Rate limiting disabled

    DEBUG = False
    TESTING = False

    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'jpg', 'jpeg', 'png'}

    # VULN-03: hardcoded admin reset token
    ADMIN_RESET_TOKEN = os.environ.get('ADMIN_RESET_TOKEN', 'admin-master-reset-t0ken')

    # Backup import feature toggle (VULN-27 chain)
    ENABLE_LEGACY_BACKUP_IMPORT = os.environ.get('ENABLE_LEGACY_BACKUP_IMPORT', 'true').lower() == 'true'


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
