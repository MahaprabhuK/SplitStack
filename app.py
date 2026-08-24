from flask import Flask, render_template, g, session
from config import config
from database.db import close_db, init_db
from modules.auth.routes import auth_bp
from modules.auth.services import get_user_by_id
from modules.main.routes import main_bp
import os

def create_app():
    """Application Factory."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['DEBUG'] = config.DEBUG

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Register database teardown
    app.teardown_appcontext(close_db)

    # Load authenticated user on each request
    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        if user_id is None:
            g.user = None
        else:
            g.user = get_user_by_id(user_id)

    # Context processor for templates (injects user and current year)
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {
            'current_user': g.user,
            'now_year': datetime.now().year
        }

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    return app

# Main entrypoint
app = create_app()

if __name__ == '__main__':
    # Initialize DB on first run
    init_db()
    print(f" * SplitStack running on http://127.0.0.1:5000 (Debug: {config.DEBUG})")
    app.run(host='0.0.0.0', port=5000, debug=config.DEBUG)
