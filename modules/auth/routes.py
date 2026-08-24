from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from modules.auth.utils import login_required, validate_registration
from modules.auth.services import register_user, authenticate_user, get_user_by_id

auth_bp = Blueprint('auth', __name__, template_folder='../../templates')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User Registration Route."""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = validate_registration(name, email, password, confirm_password)
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', name=name, email=email)

        user_id, error = register_user(name, email, password)
        if error:
            flash(error, 'danger')
            return render_template('auth/register.html', name=name, email=email)

        flash('Registration successful! Please log in with your credentials.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User Login Route."""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    next_page = request.args.get('next')

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('auth/login.html', email=email, next=next_page)

        user, error = authenticate_user(email, password)
        if error:
            flash(error, 'danger')
            return render_template('auth/login.html', email=email, next=next_page)

        # Set session
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session.permanent = remember

        flash(f"Welcome back, {user['name']}!", 'success')
        return redirect(next_page if next_page and next_page.startswith('/') else url_for('main.dashboard'))

    return render_template('auth/login.html', next=next_page)

@auth_bp.route('/logout')
def logout():
    """User Logout Route."""
    user_name = session.get('user_name', 'User')
    session.clear()
    flash(f"Goodbye, {user_name}. You have been logged out safely.", 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """User Profile View."""
    user = get_user_by_id(session['user_id'])
    return render_template('auth/profile.html', user=user)
