from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.api_project import api_project_bp
from app.routes.api_wbs import api_wbs_bp
from app.routes.api_import_export import api_import_export_bp
from app.routes.api_users import api_users_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_project_bp, url_prefix='/api/projects')
    app.register_blueprint(api_wbs_bp, url_prefix='/api/wbs')
    app.register_blueprint(api_import_export_bp, url_prefix='/api/io')
    app.register_blueprint(api_users_bp, url_prefix='/api/users')
