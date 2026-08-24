from database.db import query_db, execute_db
from datetime import datetime, date, timedelta
from mysql.connector import Error

# ----------------------------------------------------
# Categories Service
# ----------------------------------------------------
def get_categories(user_id=None, cat_type=None):
    """Fetch default global categories and user-specific categories."""
    query = """
        SELECT id, user_id, name, type, icon, color 
        FROM categories 
        WHERE (user_id IS NULL OR user_id = %s)
    """
    params = [user_id]
    if cat_type:
        query += " AND type = %s"
        params.append(cat_type)
    query += " ORDER BY (user_id IS NOT NULL), name ASC"
    return query_db(query, params)

def add_category(user_id, name, cat_type='expense', icon='tag', color='#6366f1'):
    """Add a custom category for a user."""
    name = (name or '').strip()
    if not name:
        return None, "Category name cannot be empty."
    if cat_type not in ('expense', 'income'):
        cat_type = 'expense'
    
    cat_id = execute_db(
        "INSERT INTO categories (user_id, name, type, icon, color) VALUES (%s, %s, %s, %s, %s)",
        (user_id, name, cat_type, icon or 'tag', color or '#6366f1')
    )
    return cat_id, None

def delete_category(user_id, category_id):
    """Delete a custom category safely, disassociating references first."""
    cat = query_db("SELECT * FROM categories WHERE id = %s AND user_id = %s", (category_id, user_id), one=True)
    if not cat:
        return False, "Category not found or cannot delete default system categories."
    
    # Set category_id = NULL in expenses, income, budgets
    execute_db("UPDATE expenses SET category_id = NULL WHERE category_id = %s", (category_id,))
    execute_db("UPDATE income SET category_id = NULL WHERE category_id = %s", (category_id,))
    execute_db("DELETE FROM budgets WHERE category_id = %s", (category_id,))
    execute_db("DELETE FROM categories WHERE id = %s AND user_id = %s", (category_id, user_id))
    return True, None

# ----------------------------------------------------
# Expenses Service
# ----------------------------------------------------
def get_expenses(user_id, category_id=None, start_date=None, end_date=None, payment_method=None, search=None, sort='date_desc'):
    """Get filtered and sorted expenses for a user."""
    query = """
        SELECT e.id, e.user_id, e.category_id, e.amount, e.description, e.expense_date, 
               e.payment_method, e.created_at,
               c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s
    """
    params = [user_id]

    if category_id:
        query += " AND e.category_id = %s"
        params.append(category_id)
    if start_date:
        query += " AND e.expense_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND e.expense_date <= %s"
        params.append(end_date)
    if payment_method:
        query += " AND e.payment_method = %s"
        params.append(payment_method)
    if search:
        query += " AND (e.description LIKE %s OR c.name LIKE %s)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])

    # Sorting
    sort_orders = {
        'date_desc': 'e.expense_date DESC, e.id DESC',
        'date_asc': 'e.expense_date ASC, e.id ASC',
        'amount_desc': 'e.amount DESC',
        'amount_asc': 'e.amount ASC',
        'category': 'c.name ASC'
    }
    query += f" ORDER BY {sort_orders.get(sort, 'e.expense_date DESC, e.id DESC')}"
    return query_db(query, params)

def get_expense(user_id, expense_id):
    """Get a single expense by ID ensuring ownership."""
    return query_db("""
        SELECT e.*, c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.id = %s AND e.user_id = %s
    """, (expense_id, user_id), one=True)

def add_expense(user_id, category_id, amount, description, expense_date, payment_method='upi'):
    """Add a personal expense."""
    try:
        amount = float(amount)
        if amount <= 0:
            return None, "Expense amount must be greater than zero."
    except (ValueError, TypeError):
        return None, "Please enter a valid expense amount."

    if not expense_date:
        expense_date = datetime.now().strftime('%Y-%m-%d')

    valid_methods = ('cash', 'card', 'upi', 'net_banking', 'other')
    if payment_method not in valid_methods:
        payment_method = 'upi'

    expense_id = execute_db("""
        INSERT INTO expenses (user_id, category_id, amount, description, expense_date, payment_method)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, category_id if category_id else None, amount, description or '', expense_date, payment_method))
    return expense_id, None

def update_expense(user_id, expense_id, category_id, amount, description, expense_date, payment_method):
    """Update an existing expense."""
    expense = get_expense(user_id, expense_id)
    if not expense:
        return False, "Expense not found or unauthorized."

    try:
        amount = float(amount)
        if amount <= 0:
            return False, "Expense amount must be greater than zero."
    except (ValueError, TypeError):
        return False, "Please enter a valid expense amount."

    execute_db("""
        UPDATE expenses 
        SET category_id = %s, amount = %s, description = %s, expense_date = %s, payment_method = %s
        WHERE id = %s AND user_id = %s
    """, (category_id if category_id else None, amount, description or '', expense_date, payment_method, expense_id, user_id))
    return True, None

def delete_expense(user_id, expense_id):
    """Delete an expense."""
    expense = get_expense(user_id, expense_id)
    if not expense:
        return False, "Expense not found or unauthorized."
    execute_db("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
    return True, None

# ----------------------------------------------------
# Income Service
# ----------------------------------------------------
def get_incomes(user_id, category_id=None, start_date=None, end_date=None, search=None):
    """Get income records for a user."""
    query = """
        SELECT i.id, i.user_id, i.category_id, i.amount, i.source, i.income_date, i.created_at,
               c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM income i
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.user_id = %s
    """
    params = [user_id]
    if category_id:
        query += " AND i.category_id = %s"
        params.append(category_id)
    if start_date:
        query += " AND i.income_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND i.income_date <= %s"
        params.append(end_date)
    if search:
        query += " AND (i.source LIKE %s OR c.name LIKE %s)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    query += " ORDER BY i.income_date DESC, i.id DESC"
    return query_db(query, params)

def get_income(user_id, income_id):
    """Get single income record."""
    return query_db("""
        SELECT i.*, c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM income i
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.id = %s AND i.user_id = %s
    """, (income_id, user_id), one=True)

def add_income(user_id, category_id, amount, source, income_date):
    """Add income record."""
    try:
        amount = float(amount)
        if amount <= 0:
            return None, "Income amount must be greater than zero."
    except (ValueError, TypeError):
        return None, "Please enter a valid income amount."

    source = (source or '').strip()
    if not source:
        return None, "Income source is required."

    if not income_date:
        income_date = datetime.now().strftime('%Y-%m-%d')

    income_id = execute_db("""
        INSERT INTO income (user_id, category_id, amount, source, income_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, category_id if category_id else None, amount, source, income_date))
    return income_id, None

def update_income(user_id, income_id, category_id, amount, source, income_date):
    """Update an income record."""
    inc = get_income(user_id, income_id)
    if not inc:
        return False, "Income record not found or unauthorized."
    try:
        amount = float(amount)
        if amount <= 0:
            return False, "Income amount must be greater than zero."
    except (ValueError, TypeError):
        return False, "Please enter a valid income amount."

    source = (source or '').strip()
    if not source:
        return False, "Income source is required."

    execute_db("""
        UPDATE income 
        SET category_id = %s, amount = %s, source = %s, income_date = %s
        WHERE id = %s AND user_id = %s
    """, (category_id if category_id else None, amount, source, income_date, income_id, user_id))
    return True, None

def delete_income(user_id, income_id):
    """Delete an income record."""
    inc = get_income(user_id, income_id)
    if not inc:
        return False, "Income record not found or unauthorized."
    execute_db("DELETE FROM income WHERE id = %s AND user_id = %s", (income_id, user_id))
    return True, None

# ----------------------------------------------------
# Budgets Service
# ----------------------------------------------------
def get_budgets(user_id, month=None, year=None):
    """Get category and overall budgets with actual spending progress for a given month/year."""
    now = datetime.now()
    month = int(month) if month else now.month
    year = int(year) if year else now.year

    budgets = query_db("""
        SELECT b.id, b.user_id, b.category_id, b.amount AS budget_limit, b.month, b.year,
               c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM budgets b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = %s AND b.month = %s AND b.year = %s
        ORDER BY (b.category_id IS NULL) DESC, c.name ASC
    """, (user_id, month, year))

    # Calculate actual spending for each budget
    result = []
    for b in budgets:
        cat_id = b['category_id']
        if cat_id is None:
            # Overall monthly budget
            spent_row = query_db("""
                SELECT COALESCE(SUM(amount), 0) AS total_spent
                FROM expenses
                WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s
            """, (user_id, month, year), one=True)
        else:
            # Category-specific budget
            spent_row = query_db("""
                SELECT COALESCE(SUM(amount), 0) AS total_spent
                FROM expenses
                WHERE user_id = %s AND category_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s
            """, (user_id, cat_id, month, year), one=True)

        spent = float(spent_row['total_spent']) if spent_row else 0.0
        limit_val = float(b['budget_limit'])
        remaining = limit_val - spent
        percent = (spent / limit_val * 100) if limit_val > 0 else 0.0

        if percent >= 100:
            status = 'danger'
            status_text = 'Budget Exceeded!'
        elif percent >= 90:
            status = 'warning'
            status_text = 'Critical (90%+ Spent)'
        elif percent >= 75:
            status = 'caution'
            status_text = 'Warning (75%+ Spent)'
        else:
            status = 'good'
            status_text = 'On Track'

        b_dict = dict(b)
        b_dict['spent'] = spent
        b_dict['remaining'] = remaining
        b_dict['percent'] = min(round(percent, 1), 100.0)
        b_dict['actual_percent'] = round(percent, 1)
        b_dict['status'] = status
        b_dict['status_text'] = status_text
        result.append(b_dict)

    return result

def set_budget(user_id, category_id, amount, month=None, year=None):
    """Set or update a budget for a category and month."""
    now = datetime.now()
    month = int(month) if month else now.month
    year = int(year) if year else now.year

    try:
        amount = float(amount)
        if amount <= 0:
            return None, "Budget limit must be greater than zero."
    except (ValueError, TypeError):
        return None, "Please enter a valid budget amount."

    cat_id = int(category_id) if category_id and str(category_id).isdigit() else None

    # Upsert budget
    existing = query_db("""
        SELECT id FROM budgets 
        WHERE user_id = %s AND ((category_id IS NULL AND %s IS NULL) OR (category_id = %s)) AND month = %s AND year = %s
    """, (user_id, cat_id, cat_id, month, year), one=True)

    if existing:
        execute_db("""
            UPDATE budgets SET amount = %s WHERE id = %s
        """, (amount, existing['id']))
        return existing['id'], None
    else:
        bid = execute_db("""
            INSERT INTO budgets (user_id, category_id, amount, month, year)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, cat_id, amount, month, year))
        return bid, None

def delete_budget(user_id, budget_id):
    """Delete a budget."""
    b = query_db("SELECT * FROM budgets WHERE id = %s AND user_id = %s", (budget_id, user_id), one=True)
    if not b:
        return False, "Budget not found or unauthorized."
    execute_db("DELETE FROM budgets WHERE id = %s AND user_id = %s", (budget_id, user_id))
    return True, None

# ----------------------------------------------------
# Recurring Payments Service
# ----------------------------------------------------
def get_recurring_payments(user_id):
    """Get all recurring payments for a user."""
    return query_db("""
        SELECT r.*, c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM recurring_payments r
        LEFT JOIN categories c ON r.category_id = c.id
        WHERE r.user_id = %s
        ORDER BY r.is_active DESC, r.next_due_date ASC
    """, (user_id,))

def add_recurring_payment(user_id, category_id, name, amount, frequency, start_date, next_due_date=None):
    """Add recurring payment schedule."""
    name = (name or '').strip()
    if not name:
        return None, "Payment name is required."

    try:
        amount = float(amount)
        if amount <= 0:
            return None, "Amount must be greater than zero."
    except (ValueError, TypeError):
        return None, "Please enter a valid amount."

    if frequency not in ('daily', 'weekly', 'monthly', 'yearly'):
        frequency = 'monthly'

    if not start_date:
        start_date = datetime.now().strftime('%Y-%m-%d')
    if not next_due_date:
        next_due_date = start_date

    cat_id = int(category_id) if category_id and str(category_id).isdigit() else None

    rid = execute_db("""
        INSERT INTO recurring_payments (user_id, category_id, name, amount, frequency, start_date, next_due_date, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
    """, (user_id, cat_id, name, amount, frequency, start_date, next_due_date))
    return rid, None

def toggle_recurring_payment(user_id, recurring_id):
    """Toggle active/inactive status."""
    rec = query_db("SELECT id, is_active FROM recurring_payments WHERE id = %s AND user_id = %s", (recurring_id, user_id), one=True)
    if not rec:
        return False, "Record not found."
    new_status = not rec['is_active']
    execute_db("UPDATE recurring_payments SET is_active = %s WHERE id = %s AND user_id = %s", (new_status, recurring_id, user_id))
    return True, None

def delete_recurring_payment(user_id, recurring_id):
    """Delete a recurring payment."""
    rec = query_db("SELECT id FROM recurring_payments WHERE id = %s AND user_id = %s", (recurring_id, user_id), one=True)
    if not rec:
        return False, "Record not found."
    execute_db("DELETE FROM recurring_payments WHERE id = %s AND user_id = %s", (recurring_id, user_id))
    return True, None
