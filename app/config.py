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

    # 스케줄러(태스크 갱신 알림 메일)가 메일 내 링크에 사용할 서비스 기본 URL.
    # 요청 컨텍스트가 없어 request.host_url을 쓸 수 없으므로 환경변수로 지정.
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')


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
