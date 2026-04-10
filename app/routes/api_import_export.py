from flask import Blueprint, Response, jsonify, request, send_file

from app.auth import api_login_required, project_access_required
from app.services import import_export
from app.services.wbs_code_service import recalculate_codes

api_import_export_bp = Blueprint('api_import_export', __name__)


@api_import_export_bp.route('/<int:project_id>/export/csv', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def export_csv(project_id):
    csv_data = import_export.export_csv(project_id)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=wbs_{project_id}.csv'},
    )


@api_import_export_bp.route('/<int:project_id>/export/excel', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def export_excel(project_id):
    excel_data = import_export.export_excel(project_id)
    return send_file(
        excel_data,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'wbs_{project_id}.xlsx',
    )


@api_import_export_bp.route('/<int:project_id>/import/csv', methods=['POST'])
@api_login_required
@project_access_required('participant')
def import_csv(project_id):
    if 'file' not in request.files:
        return jsonify({'error': '파일이 필요합니다.'}), 400

    file = request.files['file']
    content = file.read().decode('utf-8-sig')
    count = import_export.import_csv(project_id, content)
    recalculate_codes(project_id)
    return jsonify({'message': f'{count}개 항목을 가져왔습니다.', 'count': count})


@api_import_export_bp.route('/<int:project_id>/import/paste', methods=['POST'])
@api_login_required
@project_access_required('participant')
def import_paste(project_id):
    data = request.get_json()
    if not data or not data.get('text'):
        return jsonify({'error': '붙여넣기 데이터가 없습니다.'}), 400

    count = import_export.import_paste_data(project_id, data['text'])
    recalculate_codes(project_id)
    return jsonify({'message': f'{count}개 항목을 가져왔습니다.', 'count': count})
