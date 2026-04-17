from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.services.auth_service import login_user, register_user

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = login_user(email, password)
        if user and user.get('_inactive'):
            flash('비활성화된 계정입니다. 관리자에게 문의하세요.', 'error')
        elif user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            return redirect(url_for('main.index'))
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        if not name or not email or not password or not password_confirm:
            flash('모든 항목을 입력해주세요.', 'error')
        elif password != password_confirm:
            flash('비밀번호와 비밀번호 확인이 일치하지 않습니다.', 'error')
        elif len(password) < 4:
            flash('비밀번호는 4자 이상이어야 합니다.', 'error')
        else:
            try:
                register_user(name, email, password, role='viewer')
                flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
                return redirect(url_for('auth.login'))
            except ValueError as e:
                flash(str(e), 'error')
    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
