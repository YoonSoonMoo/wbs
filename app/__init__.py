import os

from flask import Flask, g, session

from app.config import config
from app.extensions import close_db, init_db


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])

    os.makedirs(app.instance_path, exist_ok=True)

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
        from app.services.auth_service import ensure_admin_exists
        ensure_admin_exists()

    from app.routes import register_blueprints
    register_blueprints(app)

    @app.context_processor
    def inject_user():
        return dict(
            current_user=g.get('user'),
            user_id=session.get('user_id'),
            user_name=session.get('user_name'),
            user_role=session.get('user_role'),
        )

    return app
