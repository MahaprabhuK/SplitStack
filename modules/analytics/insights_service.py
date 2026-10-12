from database.db import query_db, execute_db
from datetime import datetime, timedelta

def generate_smart_insights(user_id):
    """
    Generates data-driven financial insights by analyzing transactions,
    comparing month-over-month metrics, and checking budgets.
    """
    insights = []
    now = datetime.now()
    curr_m = now.month
    curr_y = now.year
    prev_m = 12 if curr_m == 1 else curr_m - 1
    prev_y = curr_y - 1 if curr_m == 1 else curr_y

    # 1. Month-over-Month Personal Spending Comparison
    curr_exp = query_db("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ? AND CAST(strftime('%m', expense_date) AS INTEGER) = ? AND CAST(strftime('%Y', expense_date) AS INTEGER) = ?", (user_id, curr_m, curr_y), one=True)
    prev_exp = query_db("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ? AND CAST(strftime('%m', expense_date) AS INTEGER) = ? AND CAST(strftime('%Y', expense_date) AS INTEGER) = ?", (user_id, prev_m, prev_y), one=True)

    c_total = float(curr_exp['total']) if curr_exp else 0.0
    p_total = float(prev_exp['total']) if prev_exp else 0.0

    if p_total > 0 and c_total > 0:
        diff_pct = round(((c_total - p_total) / p_total * 100), 1)
        if diff_pct > 0:
            insights.append({
                'type': 'spending_trend',
                'icon': 'arrow-trend-up',
                'color': 'danger',
                'title': 'Spending Increase',
                'message': f'Your expenses this month (₹{c_total:.2f}) have increased by {diff_pct}% compared to last month (₹{p_total:.2f}).'
            })
        else:
            insights.append({
                'type': 'spending_trend',
                'icon': 'arrow-trend-down',
                'color': 'emerald',
                'title': 'Spending Reduction',
                'message': f'Great job! Your spending is {abs(diff_pct)}% lower than last month.'
            })

    # 2. Top Spending Category Highlight
    top_cat = query_db("""
        SELECT c.name, SUM(e.amount) AS total
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND CAST(strftime('%m', e.expense_date) AS INTEGER) = ? AND CAST(strftime('%Y', e.expense_date) AS INTEGER) = ?
        GROUP BY c.name
        ORDER BY total DESC
        LIMIT 1
    """, (user_id, curr_m, curr_y), one=True)

    if top_cat:
        insights.append({
            'type': 'top_category',
            'icon': 'chart-pie',
            'color': 'indigo',
            'title': 'Highest Spending Category',
            'message': f'{top_cat["name"]} is currently your highest expense category this month (₹{float(top_cat["total"]):.2f}).'
        })

    # 3. Upcoming Recurring Payments
    upcoming = query_db("""
        SELECT name, amount, next_due_date
        FROM recurring_payments
        WHERE user_id = ? AND is_active = 1 AND next_due_date BETWEEN date('now') AND date('now', '+7 days')
    """, (user_id,))
    if upcoming:
        count = len(upcoming)
        total_due = sum(float(u['amount']) for u in upcoming)
        insights.append({
            'type': 'recurring_alert',
            'icon': 'bell',
            'color': 'amber',
            'title': 'Upcoming Scheduled Bills',
            'message': f'You have {count} recurring payment(s) totaling ₹{total_due:.2f} due within the next 7 days.'
        })

    return insights
