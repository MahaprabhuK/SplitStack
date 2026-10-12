from flask import Flask, render_template, g, session, request, abort
from config import config
from database.db import close_db, init_db
from modules.auth.utils import get_csrf_token, validate_csrf_token
from modules.auth.routes import auth_bp
from modules.auth.services import get_user_by_id
from modules.main.routes import main_bp
from modules.finance.routes import finance_bp
from modules.groups.routes import groups_bp
from modules.shopping.routes import shopping_bp
from modules.analytics.routes import analytics_bp
from modules.ocr.routes import ocr_bp
from werkzeug.middleware.proxy_fix import ProxyFix
import os

def create_app():
    """SplitStack Flask Application Factory."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['DEBUG'] = config.DEBUG
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 # 5MB Upload Limit

    # Secure reverse proxy configuration for environments like Render.
    # Trust 1 hop of X-Forwarded-For and X-Forwarded-Proto from Render's edge proxy.
    # Explicitly do not trust forwarded host (x_host=0) to prevent host header spoofing.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)

    # Session cookie security settings
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    secure_cookie_env = os.getenv('SESSION_COOKIE_SECURE')
    if secure_cookie_env is not None:
        app.config['SESSION_COOKIE_SECURE'] = secure_cookie_env.lower() in ('true', '1', 't')
    else:
        app.config['SESSION_COOKIE_SECURE'] = not config.DEBUG

    if not init_db():
        raise RuntimeError('Unable to initialize the application database.')

    # Register all modular blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(shopping_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(ocr_bp)

    # Register database teardown hook
    app.teardown_appcontext(close_db)

    # Load logged-in user into g.user on each request
    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        if user_id is None:
            g.user = None
        else:
            g.user = get_user_by_id(user_id)
            if g.user is None:
                # User was deleted or database reinitialized; purge stale session
                session.clear()

    @app.before_request
    def protect_state_changing_requests():
        if request.method == 'POST' and not validate_csrf_token(request.form.get('_csrf_token')):
            abort(400)

    # Context processor for templates
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {
            'current_user': g.user,
            'now_year': datetime.now().year,
            'csrf_token': get_csrf_token
        }

    # Custom Error Handlers
    @app.errorhandler(400)
    def bad_request_error(error):
        return render_template('errors/400.html'), 400

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    init_db()
    print(f" * SplitStack server running on http://127.0.0.1:5000 (Debug: {config.DEBUG})")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
