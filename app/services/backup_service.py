import os
import sqlite3
import tempfile
from datetime import datetime

from flask import current_app

from app.extensions import close_db, init_db

# 복원 파일이 갖춰야 할 최소 테이블 (시스템 백업이 맞는지 검증용)
REQUIRED_TABLES = {'schema_version', 'project', 'wbs_item', 'user'}


def _db_path():
    return current_app.config['DATABASE']


def _migrations_dir():
    # app.root_path = .../app  →  프로젝트 루트의 migrations/
    return os.path.join(os.path.dirname(current_app.root_path), 'migrations')


def _available_max_version():
    versions = []
    for fn in os.listdir(_migrations_dir()):
        if fn.endswith('.sql'):
            try:
                versions.append(int(fn.split('_')[0]))
            except (ValueError, IndexError):
                pass
    return max(versions) if versions else 0


def backup_filename():
    return 'wbs-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.db'


def create_backup_bytes():
    """현재 SQLite DB의 정합성 있는 스냅샷을 만들어 bytes로 반환한다.
    sqlite backup API를 쓰므로 WAL 상태와 무관하게 일관된 단일 파일이 나온다."""
    fd, tmp = tempfile.mkstemp(suffix='.db', dir=os.path.dirname(_db_path()))
    os.close(fd)
    src = sqlite3.connect(_db_path())
    try:
        dest = sqlite3.connect(tmp)
        try:
            src.backup(dest)
        finally:
            dest.close()
        with open(tmp, 'rb') as f:
            return f.read()
    finally:
        src.close()
        if os.path.exists(tmp):
            os.remove(tmp)


def _validate_backup(path):
    """업로드된 파일이 유효한 시스템 백업인지 검증한다. 문제가 있으면 ValueError."""
    con = sqlite3.connect(path)
    try:
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()
            names = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        except sqlite3.DatabaseError:
            raise ValueError('유효한 SQLite 백업 파일이 아닙니다.')

        if not ok or ok[0] != 'ok':
            raise ValueError('백업 파일 무결성 검사에 실패했습니다.')

        missing = REQUIRED_TABLES - names
        if missing:
            raise ValueError('백업에 필수 테이블이 없습니다: ' + ', '.join(sorted(missing)))

        row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
        backup_ver = (row[0] if row else 0) or 0
        avail = _available_max_version()
        if backup_ver > avail:
            raise ValueError(
                '백업 스키마 버전(%d)이 현재 앱(%d)보다 최신입니다. 앱을 먼저 업데이트하세요.'
                % (backup_ver, avail))
    finally:
        con.close()


def restore_from_bytes(data):
    """업로드된 백업 bytes를 검증한 뒤 라이브 DB 파일을 교체한다.
    구버전 백업이면 복원 후 마이그레이션을 적용해 최신 스키마로 올린다."""
    db_path = _db_path()
    # 교체 대상과 같은 디렉터리에 임시 파일 생성 (os.replace 원자성·동일 볼륨 보장)
    fd, tmp = tempfile.mkstemp(suffix='.db', dir=os.path.dirname(db_path))
    os.close(fd)
    try:
        with open(tmp, 'wb') as f:
            f.write(data)

        _validate_backup(tmp)

        # 현재 요청의 DB 연결을 닫고, 구 DB의 WAL/SHM 잔여 저널 제거
        close_db()
        for suffix in ('-wal', '-shm'):
            p = db_path + suffix
            if os.path.exists(p):
                os.remove(p)

        os.replace(tmp, db_path)  # 원자적 교체
        tmp = None

        # 구버전 백업 호환: 누락 마이그레이션 적용 + 관리자 보장
        init_db()
        from app.services.auth_service import ensure_admin_exists
        ensure_admin_exists()
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
