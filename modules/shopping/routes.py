from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from modules.auth.utils import login_required
from modules.shopping.services import (
    get_user_shopping_lists, get_shopping_list_details, create_shopping_list, delete_shopping_list,
    get_shopping_items, add_shopping_item, toggle_shopping_item, delete_shopping_item
)
from modules.groups.services import get_user_groups, get_group_members, add_shared_expense
from modules.finance.services import add_expense, get_categories
from database.db import transaction
from datetime import datetime

shopping_bp = Blueprint('shopping', __name__, template_folder='../../templates')

@shopping_bp.route('/shopping')
@login_required
def shopping_lists_route():
    """List all shopping lists."""
    user_id = session['user_id']
    lists = get_user_shopping_lists(user_id)
    return render_template('shopping/shopping_lists.html', lists=lists)

@shopping_bp.route('/shopping/create', methods=['GET', 'POST'])
@login_required
def create_shopping_list_route():
    """Create a new shopping list (personal or for a group)."""
    user_id = session['user_id']
    groups = get_user_groups(user_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        group_id = request.form.get('group_id')

        lid, error = create_shopping_list(user_id, title, description, group_id)
        if error:
            flash(error, 'danger')
            return render_template('shopping/shopping_form.html', groups=groups, form_data=request.form)

        flash('Shopping list created!', 'success')
        return redirect(url_for('shopping.shopping_detail_route', list_id=lid))

    return render_template('shopping/shopping_form.html', groups=groups, form_data={})

@shopping_bp.route('/shopping/<int:list_id>')
@login_required
def shopping_detail_route(list_id):
    """View shopping list items, calculations, and progress."""
    user_id = session['user_id']
    sl, error = get_shopping_list_details(user_id, list_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('shopping.shopping_lists_route'))

    data = get_shopping_items(list_id)
    members = get_group_members(sl['group_id']) if sl['group_id'] else []

    return render_template(
        'shopping/shopping_detail.html',
        shopping_list=sl,
        items=data['items'],
        estimated_total=data['estimated_total'],
        actual_total=data['actual_total'],
        difference=data['difference'],
        total_count=data['total_count'],
        purchased_count=data['purchased_count'],
        members=members
    )

@shopping_bp.route('/shopping/<int:list_id>/items/add', methods=['POST'])
@login_required
def add_item_route(list_id):
    """Add item to shopping list."""
    name = request.form.get('item_name')
    qty = request.form.get('quantity', 1)
    est_price = request.form.get('estimated_price', 0)
    assigned_to = request.form.get('assigned_to')

    iid, error = add_shopping_item(session['user_id'], list_id, name, qty, est_price, assigned_to)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Added "{name}" to list.', 'success')
    return redirect(url_for('shopping.shopping_detail_route', list_id=list_id))

@shopping_bp.route('/shopping/<int:list_id>/items/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_item_route(list_id, item_id):
    """Toggle item purchased state."""
    act_price = request.form.get('actual_price')
    toggle_shopping_item(session['user_id'], list_id, item_id, act_price)
    return redirect(url_for('shopping.shopping_detail_route', list_id=list_id))

@shopping_bp.route('/shopping/<int:list_id>/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item_route(list_id, item_id):
    """Delete shopping item."""
    delete_shopping_item(session['user_id'], list_id, item_id)
    flash('Item removed.', 'info')
    return redirect(url_for('shopping.shopping_detail_route', list_id=list_id))

@shopping_bp.route('/shopping/<int:list_id>/convert-expense', methods=['POST'])
@login_required
def convert_expense_route(list_id):
    """Convert confirmed shopping total into a personal or shared group expense."""
    user_id = session['user_id']
    sl, error = get_shopping_list_details(user_id, list_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('shopping.shopping_lists_route'))

    data = get_shopping_items(list_id)
    amount_to_convert = data['actual_total'] if data['actual_total'] > 0 else data['estimated_total']

    if amount_to_convert <= 0:
        flash('Cannot convert an empty or ?0.00 shopping list to an expense.', 'warning')
        return redirect(url_for('shopping.shopping_detail_route', list_id=list_id))

    today_str = datetime.now().strftime('%Y-%m-%d')
    title = f"Shopping: {sl['title']}"

    if sl['group_id']:
        # Convert to shared group expense with equal split among group members
        members = get_group_members(sl['group_id'])
        participants = [{'user_id': m['user_id']} for m in members]
        add_shared_expense(sl['group_id'], user_id, title, amount_to_convert, None, today_str, 'equal', participants)
        flash(f'Converted ?{amount_to_convert:.2f} to a shared expense in {sl["group_name"]}!', 'success')
        return redirect(url_for('groups.group_detail_route', group_id=sl['group_id']))
    else:
        # Convert to personal expense
        with transaction():
            add_expense(user_id, None, amount_to_convert, title, today_str, 'upi', commit=False)
        flash(f'Converted ?{amount_to_convert:.2f} to personal expenses!', 'success')
        return redirect(url_for('finance.expenses'))

@shopping_bp.route('/shopping/<int:list_id>/delete', methods=['POST'])
@login_required
def delete_shopping_list_route(list_id):
    """Delete shopping list."""
    user_id = session['user_id']
    success, error = delete_shopping_list(user_id, list_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Shopping list deleted.', 'info')
    return redirect(url_for('shopping.shopping_lists_route'))
