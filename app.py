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
import os

def create_app():
    """SplitStack Flask Application Factory."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['DEBUG'] = config.DEBUG
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 # 5MB Upload Limit

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
    app.run(host='0.0.0.0', port=5000, debug=config.DEBUG)
