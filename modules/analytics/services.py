from database.db import query_db
from datetime import datetime, timedelta

def get_analytics_overview(user_id):
    """Compile overall financial metrics for user."""
    # Lifetime Income
    inc_row = query_db("SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s", (user_id,), one=True)
    total_income = float(inc_row['total']) if inc_row else 0.0

    # Lifetime Personal Expenses
    exp_row = query_db("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s", (user_id,), one=True)
    total_expenses = float(exp_row['total']) if exp_row else 0.0

    # Shared Group Owed/Share
    grp_row = query_db("""
        SELECT COALESCE(SUM(ep.share_amount), 0) AS total_group_share
        FROM expense_participants ep
        JOIN shared_expenses se ON ep.shared_expense_id = se.id
        WHERE ep.user_id = %s
    """, (user_id,), one=True)
    total_group_spending = float(grp_row['total_group_share']) if grp_row else 0.0

    net_balance = total_income - (total_expenses + total_group_spending)
    savings_rate = round(((total_income - total_expenses) / total_income * 100), 1) if total_income > 0 else 0.0

    return {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'total_group_spending': total_group_spending,
        'net_balance': net_balance,
        'savings_rate': max(0.0, savings_rate)
    }

def get_category_breakdown(user_id, month=None, year=None):
    """Category ranking, totals, and percentages."""
    now = datetime.now()
    month = int(month) if month else now.month
    year = int(year) if year else now.year

    rows = query_db("""
        SELECT COALESCE(c.name, 'Uncategorized') AS category_name,
               COALESCE(c.color, '#6366f1') AS category_color,
               COALESCE(c.icon, 'tag') AS category_icon,
               COALESCE(SUM(e.amount), 0) AS total_amount
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = %s AND MONTH(e.expense_date) = %s AND YEAR(e.expense_date) = %s
        GROUP BY c.name, c.color, c.icon
        ORDER BY total_amount DESC
    """, (user_id, month, year))

    total_month_expense = sum(float(r['total_amount']) for r in rows)
    result = []
    for rank, r in enumerate(rows, 1):
        amt = float(r['total_amount'])
        pct = round((amt / total_month_expense * 100), 1) if total_month_expense > 0 else 0.0
        result.append({
            'rank': rank,
            'category_name': r['category_name'],
            'category_color': r['category_color'],
            'category_icon': r['category_icon'],
            'amount': amt,
            'percentage': pct
        })
    return result

def get_monthly_trend(user_id, months_count=6):
    """Last N months income vs expense trajectory."""
    now = datetime.now()
    trend = []

    for i in range(months_count - 1, -1, -1):
        # Calculate target month and year
        target_month = now.month - i
        target_year = now.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        m_name = datetime(target_year, target_month, 1).strftime('%b %Y')

        # Income
        inc_row = query_db("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM income
            WHERE user_id = %s AND MONTH(income_date) = %s AND YEAR(income_date) = %s
        """, (user_id, target_month, target_year), one=True)
        inc = float(inc_row['total']) if inc_row else 0.0

        # Expenses
        exp_row = query_db("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s
        """, (user_id, target_month, target_year), one=True)
        exp = float(exp_row['total']) if exp_row else 0.0

        savings = inc - exp

        trend.append({
            'month': m_name,
            'income': inc,
            'expense': exp,
            'savings': savings
        })

    return trend
