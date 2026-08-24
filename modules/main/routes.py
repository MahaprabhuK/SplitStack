from flask import Blueprint, render_template, redirect, url_for, session, g
from modules.auth.utils import login_required
from database.db import query_db
from datetime import datetime

main_bp = Blueprint('main', __name__, template_folder='../../templates')

@main_bp.route('/')
def index():
    """Root redirect route."""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main Financial Dashboard."""
    user_id = session['user_id']
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    # Phase 1: Retrieve basic stats or defaults
    # Monthly Income
    income_res = query_db(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s AND MONTH(income_date) = %s AND YEAR(income_date) = %s",
        (user_id, current_month, current_year),
        one=True
    )
    total_income = float(income_res['total']) if income_res else 0.0

    # Monthly Personal Expense
    expense_res = query_db(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s",
        (user_id, current_month, current_year),
        one=True
    )
    total_expenses = float(expense_res['total']) if expense_res else 0.0

    # Net Balance
    net_balance = total_income - total_expenses

    # Group counts
    group_count_res = query_db(
        "SELECT COUNT(*) AS count FROM group_members WHERE user_id = %s",
        (user_id,),
        one=True
    )
    group_count = group_count_res['count'] if group_count_res else 0

    stats = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': net_balance,
        'group_count': group_count,
        'current_month_name': now.strftime('%B %Y')
    }

    return render_template('dashboard.html', stats=stats)
