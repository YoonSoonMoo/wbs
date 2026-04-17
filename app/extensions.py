import logging
import os
import sqlite3

from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    # 버전 관리 테이블 초기화
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now','localtime')))"
    )
    db.commit()

    applied = {row[0] for row in db.execute("SELECT version FROM schema_version").fetchall()}

    migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')
    for filename in sorted(os.listdir(migrations_dir)):
        if not filename.endswith('.sql'):
            continue
        try:
            version = int(filename.split('_')[0])
        except (ValueError, IndexError):
            continue
        if version in applied:
            continue
        filepath = os.path.join(migrations_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            sql = f.read()
        try:
            db.executescript(sql)
            db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (version,))
            db.commit()
            logging.info(f"마이그레이션 적용: {filename}")
        except Exception as e:
            logging.error(f"마이그레이션 실패 {filename}: {e}")
            raise
