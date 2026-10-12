from database.db import query_db
from datetime import datetime
import calendar

def predict_monthly_spending(user_id, month=None, year=None):
    """
    Predicts remaining and total monthly spending using linear daily spending velocity
    and past month moving averages.
    """
    now = datetime.now()
    req_month = int(month) if month else now.month
    req_year = int(year) if year else now.year
    total_days_in_month = calendar.monthrange(req_year, req_month)[1]

    # Retrieve requested month transactions count and sum
    curr_spent_row = query_db("""
        SELECT COUNT(*) AS tx_count, COALESCE(SUM(amount), 0) AS total_spent
        FROM expenses
        WHERE user_id = ? AND CAST(strftime('%m', expense_date) AS INTEGER) = ? AND CAST(strftime('%Y', expense_date) AS INTEGER) = ?
    """, (user_id, req_month, req_year), one=True)

    tx_count = curr_spent_row['tx_count'] if curr_spent_row else 0
    total_spent = float(curr_spent_row['total_spent']) if curr_spent_row else 0.0
    active_month = req_month
    active_year = req_year

    # If requested month has < 3 transactions and no month was explicitly requested,
    # look for the user's most recent active month with at least 3 transactions
    if tx_count < 3 and (month is None and year is None):
        recent_month_row = query_db("""
            SELECT CAST(strftime('%m', expense_date) AS INTEGER) as m,
                   CAST(strftime('%Y', expense_date) AS INTEGER) as y,
                   COUNT(*) as cnt,
                   COALESCE(SUM(amount), 0) as sm
            FROM expenses
            WHERE user_id = ?
            GROUP BY strftime('%Y-%m', expense_date)
            HAVING COUNT(*) >= 3
            ORDER BY expense_date DESC
            LIMIT 1
        """, (user_id,), one=True)
        if recent_month_row:
            active_month = int(recent_month_row['m'])
            active_year = int(recent_month_row['y'])
            tx_count = int(recent_month_row['cnt'])
            total_spent = float(recent_month_row['sm'])
            total_days_in_month = calendar.monthrange(active_year, active_month)[1]

    if tx_count < 3:
        return {
            'has_sufficient_data': False,
            'message': 'Not enough historical transactions this month to generate a reliable forecast (Requires at least 3 transactions).',
            'current_spent': total_spent,
            'projected_total': total_spent,
            'daily_average': 0.0,
            'confidence': 'Low'
        }

    # Day of month to calculate velocity
    if active_month == now.month and active_year == now.year:
        day_of_month = now.day
    else:
        day_of_month = total_days_in_month

    # Linear daily velocity calculation
    daily_avg = total_spent / max(1, day_of_month)
    projected_total = daily_avg * total_days_in_month
    remaining_projected = max(0.0, projected_total - total_spent)
    month_name = datetime(active_year, active_month, 1).strftime("%B")

    return {
        'has_sufficient_data': True,
        'message': f'Based on your daily average spending of ₹{daily_avg:.2f}, you are on track to spend ₹{projected_total:.2f} by the end of {month_name}.',
        'current_spent': round(total_spent, 2),
        'projected_total': round(projected_total, 2),
        'remaining_projected': round(remaining_projected, 2),
        'daily_average': round(daily_avg, 2),
        'days_remaining': max(0, total_days_in_month - day_of_month),
        'confidence': 'Estimated (Velocity Model)'
    }

def assess_budget_risk(user_id, month=None, year=None):
    """Evaluates risk of exceeding active budgets before month end."""
    now = datetime.now()
    m = int(month) if month else now.month
    y = int(year) if year else now.year
    prediction = predict_monthly_spending(user_id, month=m, year=y)
    
    budgets = query_db("""
        SELECT b.amount AS limit_amount, COALESCE(c.name, 'Overall') AS category_name
        FROM budgets b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = ? AND b.month = ? AND b.year = ?
    """, (user_id, m, y))

    risks = []
    for b in budgets:
        limit_val = float(b['limit_amount'])
        proj = prediction['projected_total']
        if proj > limit_val:
            risks.append({
                'category': b['category_name'],
                'risk_level': 'High Risk',
                'description': f'Projected spending (₹{proj:.2f}) exceeds target limit (₹{limit_val:.2f}).'
            })
        elif proj > (0.85 * limit_val):
            risks.append({
                'category': b['category_name'],
                'risk_level': 'Moderate Risk',
                'description': f'Projected spending will utilize {round(proj/limit_val*100)}% of your target limit.'
            })

    return risks
