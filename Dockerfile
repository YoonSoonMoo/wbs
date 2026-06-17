FROM python:3.11-slim

WORKDIR /app

# 로그 즉시 출력 / pyc 생성 안 함
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 의존성 먼저 설치 (소스 변경과 무관하게 레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사 (.dockerignore로 .env/instance/.venv 등은 제외됨)
COPY . .

# SQLite DB가 저장될 영속 디렉터리 (compose에서 볼륨으로 마운트)
RUN mkdir -p /app/instance

ENV HOST=0.0.0.0 \
    PORT=5000 \
    FLASK_ENV=production \
    DATABASE_PATH=instance/wbs.db

EXPOSE 5000

# 프로덕션 WSGI 서버(waitress)로 create_app 팩토리를 구동.
# 앱 생성 시 init_db()가 마이그레이션을 자동 적용하고 관리자 계정을 생성한다.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--threads=8", "--call", "app:create_app"]
