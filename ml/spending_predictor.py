from database.db import query_db
from datetime import datetime
import calendar

def predict_monthly_spending(user_id):
    """
    Predicts remaining and total monthly spending using linear daily spending velocity
    and past month moving averages.
    """
    now = datetime.now()
    month = now.month
    year = now.year
    day_of_month = now.day
    total_days_in_month = calendar.monthrange(year, month)[1]

    # Retrieve current month transactions count and sum
    curr_spent_row = query_db("""
        SELECT COUNT(*) AS tx_count, COALESCE(SUM(amount), 0) AS total_spent
        FROM expenses
        WHERE user_id = %s AND MONTH(expense_date) = %s AND YEAR(expense_date) = %s
    """, (user_id, month, year), one=True)

    tx_count = curr_spent_row['tx_count'] if curr_spent_row else 0
    total_spent = float(curr_spent_row['total_spent']) if curr_spent_row else 0.0

    if tx_count < 3:
        return {
            'has_sufficient_data': False,
            'message': 'Not enough historical transactions this month to generate a reliable forecast (Requires at least 3 transactions).',
            'current_spent': total_spent,
            'projected_total': total_spent,
            'daily_average': 0.0,
            'confidence': 'Low'
        }

    # Linear daily velocity calculation
    daily_avg = total_spent / max(1, day_of_month)
    projected_total = daily_avg * total_days_in_month
    remaining_projected = max(0.0, projected_total - total_spent)

    return {
        'has_sufficient_data': True,
        'message': f'Based on your daily average spending of ?{daily_avg:.2f}, you are on track to spend ?{projected_total:.2f} by the end of {now.strftime("%B")}.',
        'current_spent': round(total_spent, 2),
        'projected_total': round(projected_total, 2),
        'remaining_projected': round(remaining_projected, 2),
        'daily_average': round(daily_avg, 2),
        'days_remaining': total_days_in_month - day_of_month,
        'confidence': 'Estimated (Velocity Model)'
    }

def assess_budget_risk(user_id):
    """Evaluates risk of exceeding active budgets before month end."""
    now = datetime.now()
    prediction = predict_monthly_spending(user_id)
    
    budgets = query_db("""
        SELECT b.amount AS limit_amount, COALESCE(c.name, 'Overall') AS category_name
        FROM budgets b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.user_id = %s AND b.month = %s AND b.year = %s
    """, (user_id, now.month, now.year))

    risks = []
    for b in budgets:
        limit_val = float(b['limit_amount'])
        proj = prediction['projected_total']
        if proj > limit_val:
            risks.append({
                'category': b['category_name'],
                'risk_level': 'High Risk',
                'description': f'Projected spending (?{proj:.2f}) exceeds target limit (?{limit_val:.2f}).'
            })
        elif proj > (0.85 * limit_val):
            risks.append({
                'category': b['category_name'],
                'risk_level': 'Moderate Risk',
                'description': f'Projected spending will utilize {round(proj/limit_val*100)}% of your target limit.'
            })

    return risks
