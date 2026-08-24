import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    if not SECRET_KEY or len(SECRET_KEY) < 32:
        raise RuntimeError('FLASK_SECRET_KEY must be set to a strong secret of at least 32 characters.')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # SQLite database path, resolved relative to the project root when needed.
    DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'database', 'splitstack.db'))
    if not os.path.isabs(DATABASE_PATH):
        DATABASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), DATABASE_PATH))

config = Config()
