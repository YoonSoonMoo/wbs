import io

from flask import Blueprint, jsonify, request, send_file

from app.auth import admin_required, api_login_required
from app.services import backup_service

api_admin_bp = Blueprint('api_admin', __name__)


@api_admin_bp.route('/backup', methods=['GET'])
@api_login_required
@admin_required
def backup():
    data = backup_service.create_backup_bytes()
    return send_file(
        io.BytesIO(data),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=backup_service.backup_filename(),
    )


@api_admin_bp.route('/restore', methods=['POST'])
@api_login_required
@admin_required
def restore():
    if 'file' not in request.files:
        return jsonify({'error': '백업 파일이 필요합니다.'}), 400

    data = request.files['file'].read()
    if not data:
        return jsonify({'error': '빈 파일입니다.'}), 400

    try:
        backup_service.restore_from_bytes(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    return jsonify({'message': '복원이 완료되었습니다.'})
