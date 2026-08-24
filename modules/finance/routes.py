from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from modules.auth.utils import login_required
from modules.finance.services import (
    get_categories, add_category, delete_category,
    get_expenses, get_expense, add_expense, update_expense, delete_expense,
    get_incomes, get_income, add_income, update_income, delete_income,
    get_budgets, set_budget, delete_budget,
    get_recurring_payments, add_recurring_payment, toggle_recurring_payment, delete_recurring_payment
)
from datetime import datetime

finance_bp = Blueprint('finance', __name__, template_folder='../../templates')

# =========================================================================
# Expenses Routes
# =========================================================================

@finance_bp.route('/expenses')
@login_required
def expenses():
    """View all personal expenses with filtering, search, and sorting."""
    user_id = session['user_id']
    category_id = request.args.get('category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    payment_method = request.args.get('payment_method')
    search = request.args.get('search')
    sort = request.args.get('sort', 'date_desc')

    expense_list = get_expenses(
        user_id=user_id,
        category_id=int(category_id) if category_id and category_id.isdigit() else None,
        start_date=start_date,
        end_date=end_date,
        payment_method=payment_method,
        search=search,
        sort=sort
    )
    categories = get_categories(user_id, cat_type='expense')
    total_amount = sum(float(e['amount']) for e in expense_list)

    return render_template(
        'finance/expenses.html',
        expenses=expense_list,
        categories=categories,
        total_amount=total_amount,
        selected_category=category_id,
        start_date=start_date,
        end_date=end_date,
        payment_method=payment_method,
        search=search,
        sort=sort
    )

@finance_bp.route('/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense_route():
    """Add a new expense."""
    user_id = session['user_id']
    categories = get_categories(user_id, cat_type='expense')

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount')
        description = request.form.get('description', '').strip()
        expense_date = request.form.get('expense_date')
        payment_method = request.form.get('payment_method', 'upi')

        cat_id = int(category_id) if category_id and category_id.isdigit() else None
        expense_id, error = add_expense(user_id, cat_id, amount, description, expense_date, payment_method)
        if error:
            flash(error, 'danger')
            return render_template('finance/expense_form.html', categories=categories, form_data=request.form, is_edit=False)

        flash('Expense recorded successfully!', 'success')
        return redirect(url_for('finance.expenses'))

    today_str = datetime.now().strftime('%Y-%m-%d')
    return render_template('finance/expense_form.html', categories=categories, form_data={'expense_date': today_str}, is_edit=False)

@finance_bp.route('/expenses/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense_route(expense_id):
    """Edit an existing expense."""
    user_id = session['user_id']
    expense = get_expense(user_id, expense_id)
    if not expense:
        flash('Expense not found or unauthorized.', 'danger')
        return redirect(url_for('finance.expenses'))

    categories = get_categories(user_id, cat_type='expense')

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount')
        description = request.form.get('description', '').strip()
        expense_date = request.form.get('expense_date')
        payment_method = request.form.get('payment_method', 'upi')

        cat_id = int(category_id) if category_id and category_id.isdigit() else None
        success, error = update_expense(user_id, expense_id, cat_id, amount, description, expense_date, payment_method)
        if error:
            flash(error, 'danger')
            return render_template('finance/expense_form.html', categories=categories, form_data=request.form, is_edit=True, expense=expense)

        flash('Expense updated successfully!', 'success')
        return redirect(url_for('finance.expenses'))

    return render_template('finance/expense_form.html', categories=categories, form_data=expense, is_edit=True, expense=expense)

@finance_bp.route('/expenses/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense_route(expense_id):
    """Delete an expense."""
    user_id = session['user_id']
    success, error = delete_expense(user_id, expense_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Expense deleted successfully.', 'info')
    return redirect(url_for('finance.expenses'))

# =========================================================================
# Income Routes
# =========================================================================

@finance_bp.route('/income')
@login_required
def income():
    """View all income records with search and filters."""
    user_id = session['user_id']
    category_id = request.args.get('category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')

    income_list = get_incomes(
        user_id=user_id,
        category_id=int(category_id) if category_id and category_id.isdigit() else None,
        start_date=start_date,
        end_date=end_date,
        search=search
    )
    categories = get_categories(user_id, cat_type='income')
    total_amount = sum(float(i['amount']) for i in income_list)

    return render_template(
        'finance/income.html',
        incomes=income_list,
        categories=categories,
        total_amount=total_amount,
        selected_category=category_id,
        start_date=start_date,
        end_date=end_date,
        search=search
    )

@finance_bp.route('/income/add', methods=['GET', 'POST'])
@login_required
def add_income_route():
    """Add new income record."""
    user_id = session['user_id']
    categories = get_categories(user_id, cat_type='income')

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount')
        source = request.form.get('source', '').strip()
        income_date = request.form.get('income_date')

        cat_id = int(category_id) if category_id and category_id.isdigit() else None
        income_id, error = add_income(user_id, cat_id, amount, source, income_date)
        if error:
            flash(error, 'danger')
            return render_template('finance/income_form.html', categories=categories, form_data=request.form, is_edit=False)

        flash('Income recorded successfully!', 'success')
        return redirect(url_for('finance.income'))

    today_str = datetime.now().strftime('%Y-%m-%d')
    return render_template('finance/income_form.html', categories=categories, form_data={'income_date': today_str}, is_edit=False)

@finance_bp.route('/income/edit/<int:income_id>', methods=['GET', 'POST'])
@login_required
def edit_income_route(income_id):
    """Edit income record."""
    user_id = session['user_id']
    inc = get_income(user_id, income_id)
    if not inc:
        flash('Income record not found or unauthorized.', 'danger')
        return redirect(url_for('finance.income'))

    categories = get_categories(user_id, cat_type='income')

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        amount = request.form.get('amount')
        source = request.form.get('source', '').strip()
        income_date = request.form.get('income_date')

        cat_id = int(category_id) if category_id and category_id.isdigit() else None
        success, error = update_income(user_id, income_id, cat_id, amount, source, income_date)
        if error:
            flash(error, 'danger')
            return render_template('finance/income_form.html', categories=categories, form_data=request.form, is_edit=True, income=inc)

        flash('Income updated successfully!', 'success')
        return redirect(url_for('finance.income'))

    return render_template('finance/income_form.html', categories=categories, form_data=inc, is_edit=True, income=inc)

@finance_bp.route('/income/delete/<int:income_id>', methods=['POST'])
@login_required
def delete_income_route(income_id):
    """Delete income record."""
    user_id = session['user_id']
    success, error = delete_income(user_id, income_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Income record deleted successfully.', 'info')
    return redirect(url_for('finance.income'))

# =========================================================================
# Categories Routes
# =========================================================================

@finance_bp.route('/categories')
@login_required
def categories():
    """Manage system and custom user categories."""
    user_id = session['user_id']
    cat_list = get_categories(user_id)
    return render_template('finance/categories.html', categories=cat_list)

@finance_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category_route():
    """Add custom category."""
    user_id = session['user_id']
    name = request.form.get('name', '').strip()
    cat_type = request.form.get('type', 'expense')
    icon = request.form.get('icon', 'tag')
    color = request.form.get('color', '#6366f1')

    cat_id, error = add_category(user_id, name, cat_type, icon, color)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Category "{name}" added successfully!', 'success')
    return redirect(url_for('finance.categories'))

@finance_bp.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required
def delete_category_route(category_id):
    """Delete custom category safely."""
    user_id = session['user_id']
    success, error = delete_category(user_id, category_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Category deleted safely.', 'info')
    return redirect(url_for('finance.categories'))

# =========================================================================
# Budget Routes
# =========================================================================

@finance_bp.route('/budgets')
@login_required
def budgets():
    """View and manage category & monthly budgets with live progress."""
    user_id = session['user_id']
    now = datetime.now()
    month = int(request.args.get('month', now.month))
    year = int(request.args.get('year', now.year))

    budget_list = get_budgets(user_id, month, year)
    categories = get_categories(user_id, cat_type='expense')
    
    total_budget = sum(float(b['budget_limit']) for b in budget_list if b['category_id'] is not None)
    total_spent = sum(float(b['spent']) for b in budget_list if b['category_id'] is not None)

    return render_template(
        'finance/budgets.html',
        budgets=budget_list,
        categories=categories,
        month=month,
        year=year,
        total_budget=total_budget,
        total_spent=total_spent,
        month_name=datetime(year, month, 1).strftime('%B %Y')
    )

@finance_bp.route('/budgets/set', methods=['POST'])
@login_required
def set_budget_route():
    """Set or update a budget limit."""
    user_id = session['user_id']
    category_id = request.form.get('category_id')
    amount = request.form.get('amount')
    month = request.form.get('month')
    year = request.form.get('year')

    bid, error = set_budget(user_id, category_id, amount, month, year)
    if error:
        flash(error, 'danger')
    else:
        flash('Budget saved successfully!', 'success')
    return redirect(url_for('finance.budgets', month=month, year=year))

@finance_bp.route('/budgets/delete/<int:budget_id>', methods=['POST'])
@login_required
def delete_budget_route(budget_id):
    """Delete a budget."""
    user_id = session['user_id']
    success, error = delete_budget(user_id, budget_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Budget removed successfully.', 'info')
    return redirect(url_for('finance.budgets'))

# =========================================================================
# Recurring Payments Routes
# =========================================================================

@finance_bp.route('/recurring')
@login_required
def recurring():
    """View recurring payments."""
    user_id = session['user_id']
    payments = get_recurring_payments(user_id)
    categories = get_categories(user_id, cat_type='expense')
    total_monthly_recurring = sum(
        float(p['amount']) * (4.33 if p['frequency'] == 'weekly' else (1/12 if p['frequency'] == 'yearly' else 1))
        for p in payments if p['is_active']
    )
    return render_template(
        'finance/recurring.html',
        payments=payments,
        categories=categories,
        total_monthly=total_monthly_recurring
    )

@finance_bp.route('/recurring/add', methods=['POST'])
@login_required
def add_recurring_route():
    """Add recurring payment schedule."""
    user_id = session['user_id']
    name = request.form.get('name')
    amount = request.form.get('amount')
    category_id = request.form.get('category_id')
    frequency = request.form.get('frequency', 'monthly')
    start_date = request.form.get('start_date')
    next_due_date = request.form.get('next_due_date')

    rid, error = add_recurring_payment(user_id, category_id, name, amount, frequency, start_date, next_due_date)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Recurring payment "{name}" scheduled successfully!', 'success')
    return redirect(url_for('finance.recurring'))

@finance_bp.route('/recurring/toggle/<int:recurring_id>', methods=['POST'])
@login_required
def toggle_recurring_route(recurring_id):
    """Toggle active status."""
    user_id = session['user_id']
    success, error = toggle_recurring_payment(user_id, recurring_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Recurring payment status updated.', 'info')
    return redirect(url_for('finance.recurring'))

@finance_bp.route('/recurring/delete/<int:recurring_id>', methods=['POST'])
@login_required
def delete_recurring_route(recurring_id):
    """Delete recurring payment."""
    user_id = session['user_id']
    success, error = delete_recurring_payment(user_id, recurring_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Recurring payment removed.', 'info')
    return redirect(url_for('finance.recurring'))
