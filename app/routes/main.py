import os
from flask import Blueprint, g, redirect, render_template, session, url_for

from app.auth import login_required
from app.models import project as project_model
from app.services.auth_service import get_project_role

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))
    return render_template('landing.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')


@main_bp.route('/project/<int:project_id>/wbs')
@login_required
def wbs_view(project_id):
    role = get_project_role(g.user['id'], project_id)
    if not role:
        return redirect(url_for('main.index'))
    project = project_model.get_project(project_id)
    app_version = os.environ.get('VERSION', '')
    return render_template('wbs.html', project_id=project_id, project_role=role, project_name=project['name'], app_version=app_version)


@main_bp.route('/project/<int:project_id>/gantt')
@login_required
def gantt_view(project_id):
    role = get_project_role(g.user['id'], project_id)
    if not role or role == 'viewer':
        return redirect(url_for('main.index'))
    project = project_model.get_project(project_id)
    return render_template('gantt.html', project_id=project_id, project_role=role, project_name=project['name'])
