from functools import wraps
from flask import session, redirect, url_for, flash, request, g
import hmac
import re
import secrets

CSRF_SESSION_KEY = '_csrf_token'

def get_csrf_token():
    """Return the session-bound CSRF token used by state-changing forms."""
    token = session.get(CSRF_SESSION_KEY)
    if token is None:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token

def validate_csrf_token(token):
    """Validate a submitted CSRF token without revealing token details."""
    expected = session.get(CSRF_SESSION_KEY)
    return bool(expected and token and hmac.compare_digest(expected, token))

def login_required(view_func):
    """Decorator to protect routes requiring authentication."""
    @wraps(view_func)
    def decorated_function(*args, **kwargs):
        if getattr(g, 'user', None) is None:
            session.clear()
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return view_func(*args, **kwargs)
    return decorated_function

def validate_registration(name, email, password, confirm_password):
    """Validate user registration inputs."""
    errors = []
    
    name = (name or '').strip()
    email = (email or '').strip()
    password = password or ''
    confirm_password = confirm_password or ''

    if not name:
        errors.append('Full name is required.')
    elif len(name) < 2 or len(name) > 100:
        errors.append('Name must be between 2 and 100 characters.')

    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not email:
        errors.append('Email address is required.')
    elif not re.match(email_regex, email):
        errors.append('Please provide a valid email address.')

    if not password:
        errors.append('Password is required.')
    elif len(password) < 6:
        errors.append('Password must be at least 6 characters long.')

    if password != confirm_password:
        errors.append('Passwords do not match.')

    return errors
