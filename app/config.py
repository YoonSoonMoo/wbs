import os

basedir = os.path.abspath(os.path.dirname(__file__))
projectdir = os.path.dirname(basedir)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE = os.path.join(projectdir, os.environ.get('DATABASE_PATH', 'instance/wbs.db'))
    ADMIN_NAME = os.environ.get('ADMIN_NAME', '관리자')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')

    # AI 어시스턴트 LLM 프로바이더 (GEMINI | GEMMA | LOCAL)
    # GEMINI/GEMMA: OpenAI 호환 엔드포인트, LOCAL: claude -p CLI
    AI_MODEL = os.environ.get('AI_MODEL', 'LOCAL').upper()
    AI_API_KEY = os.environ.get('AI_API_KEY', '')
    AI_BASE_URL = os.environ.get('AI_BASE_URL', '')
    AI_MODEL_NAME = os.environ.get('AI_MODEL_NAME', '')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DATABASE = ':memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
