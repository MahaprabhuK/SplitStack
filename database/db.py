import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar

from flask import g, has_app_context
from config import config

_transaction_db = ContextVar('transaction_db', default=None)


def get_db():
    """Return the request-scoped SQLite connection or a standalone connection."""
    active_transaction = _transaction_db.get()
    if active_transaction is not None:
        return active_transaction
    if has_app_context():
        if 'db' not in g:
            g.db = sqlite3.connect(config.DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
        return g.db

    db = sqlite3.connect(config.DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def close_db(e=None):
    """Close the request-scoped database connection."""
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            db.close()


def query_db(query, args=(), one=False):
    """Execute a SELECT query and return sqlite3.Row results."""
    is_app_ctx = has_app_context() or _transaction_db.get() is not None
    db = get_db()
    try:
        cursor = db.execute(query, args)
        rows = cursor.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        if not is_app_ctx:
            db.close()


def execute_db(query, args=(), commit=True):
    """Execute a write query and return its inserted ID or affected row count."""
    is_app_ctx = has_app_context() or _transaction_db.get() is not None
    db = get_db()
    try:
        cursor = db.execute(query, args)
        if commit:
            db.commit()
        return cursor.lastrowid or cursor.rowcount
    finally:
        if not is_app_ctx:
            db.close()


@contextmanager
def transaction():
    """Commit a multi-step operation atomically, rolling back on failure."""
    owns_connection = not has_app_context() and _transaction_db.get() is None
    db = get_db()
    token = _transaction_db.set(db) if owns_connection else None
    try:
        db.execute('BEGIN')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if token is not None:
            _transaction_db.reset(token)
            db.close()


def init_db():
    """Create the SQLite database and tables without deleting existing data."""
    try:
        os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
        with sqlite3.connect(config.DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys = ON')
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r', encoding='utf-8') as schema_file:
                db.executescript(schema_file.read())

            count = db.execute(
                'SELECT COUNT(*) FROM categories WHERE user_id IS NULL'
            ).fetchone()[0]
            if count == 0:
                default_categories = [
                    ('Food & Dining', 'expense', 'utensils', '#f59e0b'),
                    ('Transportation', 'expense', 'car', '#3b82f6'),
                    ('Shopping', 'expense', 'shopping-bag', '#ec4899'),
                    ('Bills & Utilities', 'expense', 'file-invoice-dollar', '#ef4444'),
                    ('Entertainment', 'expense', 'film', '#8b5cf6'),
                    ('Education', 'expense', 'graduation-cap', '#10b981'),
                    ('Healthcare', 'expense', 'heartbeat', '#06b6d4'),
                    ('Travel', 'expense', 'plane', '#6366f1'),
                    ('Salary / Income', 'income', 'wallet', '#10b981'),
                    ('Other', 'expense', 'ellipsis-h', '#64748b')
                ]
                db.executemany(
                    'INSERT INTO categories (name, type, icon, color) VALUES (?, ?, ?, ?)',
                    default_categories
                )
                db.commit()
        print('SQLite database initialized successfully with schema and default seed data.')
        return True
    except sqlite3.Error:
        print('Database initialization failed. Check the SQLite database path and permissions.')
        return False
