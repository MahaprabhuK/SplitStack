from werkzeug.security import generate_password_hash, check_password_hash
from database.db import query_db, execute_db
from mysql.connector import Error

def get_user_by_email(email):
    """Retrieve a user by email address."""
    email = (email or '').strip().lower()
    return query_db("SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s", (email,), one=True)

def get_user_by_id(user_id):
    """Retrieve a user by ID (without password hash)."""
    return query_db("SELECT id, name, email, created_at FROM users WHERE id = %s", (user_id,), one=True)

def register_user(name, email, password):
    """Register a new user with hashed password."""
    name = name.strip()
    email = email.strip().lower()
    
    # Check if user already exists
    existing = get_user_by_email(email)
    if existing:
        return None, "An account with this email already exists."

    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    try:
        user_id = execute_db(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash)
        )
        return user_id, None
    except Error as e:
        return None, f"Database error during registration: {e}"

def authenticate_user(email, password):
    """Authenticate user credentials and return user record if valid."""
    email = (email or '').strip().lower()
    user = get_user_by_email(email)
    
    if not user:
        return None, "No account found with this email address."
    
    if not check_password_hash(user['password_hash'], password):
        return None, "Invalid password. Please try again."
    
    return user, None
