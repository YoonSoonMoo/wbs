"""/api/io (import/export) 엔드포인트 테스트."""
from __future__ import annotations

import io


def test_export_csv(admin_client, project_id, wbs_item):
    resp = admin_client.get(f'/api/io/{project_id}/export/csv')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    assert b'\xef\xbb\xbf' in resp.data[:3] or resp.data  # non-empty


def test_export_excel(admin_client, project_id, wbs_item):
    resp = admin_client.get(f'/api/io/{project_id}/export/excel')
    assert resp.status_code == 200
    assert 'spreadsheet' in resp.mimetype


def test_import_csv_missing_file(admin_client, project_id):
    resp = admin_client.post(f'/api/io/{project_id}/import/csv', data={})
    assert resp.status_code == 400


def test_import_paste_missing_text(admin_client, project_id):
    resp = admin_client.post(f'/api/io/{project_id}/import/paste', json={})
    assert resp.status_code == 400
