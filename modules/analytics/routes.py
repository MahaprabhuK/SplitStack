from flask import Blueprint, render_template, request, session, jsonify
from modules.auth.utils import login_required
from modules.analytics.services import (
    get_analytics_overview, get_category_breakdown, get_monthly_trend
)
from modules.finance.services import get_budgets
from datetime import datetime

analytics_bp = Blueprint('analytics', __name__, template_folder='../../templates')

@analytics_bp.route('/analytics')
@login_required
def analytics_dashboard():
    """Render the comprehensive analytics dashboard."""
    user_id = session['user_id']
    now = datetime.now()
    month = int(request.args.get('month', now.month))
    year = int(request.args.get('year', now.year))

    overview = get_analytics_overview(user_id)
    categories = get_category_breakdown(user_id, month, year)
    monthly_trend = get_monthly_trend(user_id, months_count=6)
    budgets = get_budgets(user_id, month, year)

    month_name = datetime(year, month, 1).strftime('%B %Y')

    return render_template(
        'analytics/analytics.html',
        overview=overview,
        categories=categories,
        monthly_trend=monthly_trend,
        budgets=budgets,
        month=month,
        year=year,
        month_name=month_name
    )

# ----------------------------------------------------
# JSON API Endpoints for Dynamic Chart.js visualizations
# ----------------------------------------------------
@analytics_bp.route('/api/analytics/monthly')
@login_required
def api_monthly_trend():
    user_id = session['user_id']
    trend = get_monthly_trend(user_id, months_count=6)
    return jsonify(trend)

@analytics_bp.route('/api/analytics/categories')
@login_required
def api_categories_breakdown():
    user_id = session['user_id']
    now = datetime.now()
    month = int(request.args.get('month', now.month))
    year = int(request.args.get('year', now.year))
    cats = get_category_breakdown(user_id, month, year)
    return jsonify(cats)
