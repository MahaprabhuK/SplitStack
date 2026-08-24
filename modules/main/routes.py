from flask import Blueprint, render_template, redirect, url_for, session, g
from modules.auth.utils import login_required
from database.db import query_db
from modules.finance.services import get_expenses, get_budgets
from modules.groups.services import get_user_groups
from modules.analytics.insights_service import generate_smart_insights
from ml.spending_predictor import predict_monthly_spending, assess_budget_risk
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
    """Comprehensive main financial dashboard."""
    user_id = session['user_id']
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    # 1. Income (Current Month)
    income_res = query_db("""
        SELECT COALESCE(SUM(amount), 0) AS total 
        FROM income 
        WHERE user_id = %s AND MONTH(income_date) = %s AND YEAR(income_date) = %s
    """, (user_id, current_month, current_year), one=True)
    total_income = float(income_res['total']) if income_res else 0.0

    # 2. Expenses (Current Month)
    expense_res = query_db("""
        SELECT COALESCE(SUM(amount), 0) AS total 
        FROM expenses 
        WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s
    """, (user_id, current_month, current_year), one=True)
    total_expenses = float(expense_res['total']) if expense_res else 0.0

    # 3. Net Balance & Savings
    net_balance = total_income - total_expenses
    savings_amount = max(0.0, net_balance)
    savings_rate = round((net_balance / total_income * 100), 1) if total_income > 0 else 0.0

    # 4. User Groups
    user_groups = get_user_groups(user_id)
    group_count = len(user_groups)

    # 5. Active Category Budgets
    active_budgets = get_budgets(user_id, current_month, current_year)

    # 6. Recent Transactions (Last 5)
    recent_expenses = get_expenses(user_id=user_id, sort='date_desc')[:6]

    # 7. Smart Financial Insights
    insights = generate_smart_insights(user_id)

    # 8. ML Spending Prediction
    spending_prediction = predict_monthly_spending(user_id)
    budget_risks = assess_budget_risk(user_id)

    stats = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': net_balance,
        'savings_amount': savings_amount,
        'savings_rate': max(0.0, savings_rate),
        'group_count': group_count,
        'current_month_name': now.strftime('%B %Y')
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        budgets=active_budgets,
        groups=user_groups,
        recent_expenses=recent_expenses,
        insights=insights,
        prediction=spending_prediction,
        budget_risks=budget_risks,
        month=current_month,
        year=current_year
    )
