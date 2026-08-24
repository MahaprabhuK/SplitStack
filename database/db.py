import mysql.connector
from mysql.connector import Error
from flask import g, has_app_context
from config import config
import os

def get_db():
    """Get a database connection. Uses Flask 'g' if within application context, otherwise creates a direct connection."""
    if has_app_context():
        if 'db' not in g:
            g.db = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                autocommit=True
            )
        return g.db
    else:
        return mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            autocommit=True
        )

def close_db(e=None):
    """Close the database connection at the end of the request context."""
    if has_app_context():
        db = g.pop('db', None)
        if db is not None and db.is_connected():
            db.close()

def query_db(query, args=(), one=False):
    """Execute a SELECT query and return dictionary results."""
    is_app_ctx = has_app_context()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(query, args)
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv
    finally:
        cursor.close()
        if not is_app_ctx:
            db.close()

def execute_db(query, args=(), commit=True):
    """Execute an INSERT, UPDATE, or DELETE query and return the last row ID or affected rows."""
    is_app_ctx = has_app_context()
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(query, args)
        if commit and not db.autocommit:
            db.commit()
        last_id = cursor.lastrowid
        row_count = cursor.rowcount
        return last_id if last_id else row_count
    finally:
        cursor.close()
        if not is_app_ctx:
            db.close()

def init_db():
    """Initialize database and tables from schema.sql."""
    try:
        # First connect without specifying database to create database if needed
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.close()
        conn.close()

        # Now connect to the database and run schema statements
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        cursor = conn.cursor()
        
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # Execute statement by statement
            statements = [s.strip() for s in sql_script.split(';') if s.strip()]
            for stmt in statements:
                if stmt:
                    cursor.execute(stmt)
            conn.commit()

        # Seed default global categories if empty
        cursor.execute("SELECT COUNT(*) FROM categories WHERE user_id IS NULL")
        count = cursor.fetchone()[0]
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
            cursor.executemany(
                "INSERT INTO categories (name, type, icon, color) VALUES (%s, %s, %s, %s)",
                default_categories
            )
            conn.commit()

        cursor.close()
        conn.close()
        print("Database initialized successfully with schema and default seed data.")
        return True
    except Error:
        print("Database initialization failed. Check the configured database connection.")
        return False
