"""pytest 공통 픽스처.

테스트용 Flask 앱은 임시 파일 SQLite DB를 사용한다.
(TestingConfig의 ':memory:' 는 요청마다 커넥션이 새로 열리는 이 앱 구조와
호환되지 않으므로, 여기서 DATABASE 경로를 덮어쓴다.)
"""
from __future__ import annotations

import os
import tempfile

import pytest

from app import create_app
from app.config import Config, TestingConfig
from app.extensions import get_db, init_db
from app.services import auth_service


ADMIN_EMAIL = 'admin@test.local'
ADMIN_PASSWORD = 'admin1234'
ADMIN_NAME = 'TestAdmin'


@pytest.fixture
def app(monkeypatch):
    db_fd, db_path = tempfile.mkstemp(suffix='.sqlite')
    os.close(db_fd)

    # config 클래스 속성은 import 시점에 평가되므로, 환경변수가 아니라 속성 자체를 덮어쓴다.
    monkeypatch.setattr(TestingConfig, 'DATABASE', db_path, raising=False)
    monkeypatch.setattr(Config, 'ADMIN_EMAIL', ADMIN_EMAIL, raising=False)
    monkeypatch.setattr(Config, 'ADMIN_PASSWORD', ADMIN_PASSWORD, raising=False)
    monkeypatch.setattr(Config, 'ADMIN_NAME', ADMIN_NAME, raising=False)

    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """애플리케이션 컨텍스트 안에서 DB 커넥션을 돌려준다."""
    with app.app_context():
        init_db()
        yield get_db()


def _login_form(client, email, password):
    return client.post(
        '/login',
        data={'email': email, 'password': password},
        follow_redirects=False,
    )


@pytest.fixture
def admin_client(app, client):
    """최초 관리자(ADMIN_EMAIL) 로 로그인된 test client."""
    resp = _login_form(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert resp.status_code in (302, 303), resp.data
    return client


def _create_user(app, name, email, password, role='viewer', is_active=True):
    with app.app_context():
        uid = auth_service.register_user(name, email, password, role=role)
        if not is_active:
            auth_service.set_user_active(uid, False)
        return uid


@pytest.fixture
def developer_user(app):
    return _create_user(app, 'dev1', 'dev@test.local', 'pw1234', role='developer')


@pytest.fixture
def viewer_user(app):
    return _create_user(app, 'view1', 'view@test.local', 'pw1234', role='viewer')


@pytest.fixture
def developer_client(app, developer_user):
    c = app.test_client()
    _login_form(c, 'dev@test.local', 'pw1234')
    return c


@pytest.fixture
def viewer_client(app, viewer_user):
    c = app.test_client()
    _login_form(c, 'view@test.local', 'pw1234')
    return c


@pytest.fixture
def anonymous_client(app):
    return app.test_client()


@pytest.fixture
def project_id(admin_client):
    """admin 계정으로 프로젝트 하나를 만든 뒤 id를 반환."""
    resp = admin_client.post(
        '/api/projects',
        json={
            'name': '테스트 프로젝트',
            'description': 'pytest',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        },
    )
    assert resp.status_code == 201, resp.data
    return resp.get_json()['id']


@pytest.fixture
def project_with_members(admin_client, developer_user, viewer_user):
    resp = admin_client.post(
        '/api/projects',
        json={
            'name': '멤버 프로젝트',
            'members': [
                {'user_id': developer_user, 'role': 'developer'},
                {'user_id': viewer_user, 'role': 'viewer'},
            ],
        },
    )
    assert resp.status_code == 201
    return resp.get_json()['id']


@pytest.fixture
def wbs_item(admin_client, project_id):
    """기본 WBS 항목 한 개를 생성해 id를 반환."""
    resp = admin_client.post(
        f'/api/wbs/{project_id}/items',
        json={
            'task_name': '루트 태스크',
            'category': '개발',
            'assignee': 'TestAdmin',
            'plan_start': '2026-04-01',
            'plan_end': '2026-04-10',
            'effort': 5.0,
            'progress': 0,
        },
    )
    assert resp.status_code == 201, resp.data
    return resp.get_json()['id']
