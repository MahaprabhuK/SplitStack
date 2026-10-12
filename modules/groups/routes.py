from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from modules.auth.utils import login_required
from modules.groups.services import (
    leave_group,
    get_user_groups, get_group_details, create_group, get_group_members,
    add_group_member_by_email, remove_group_member,
    get_group_expenses, add_shared_expense, delete_shared_expense,
    calculate_group_balances, get_group_settlement_plan,
    record_settlement_payment, get_settlement_history
)
from modules.finance.services import get_categories
from datetime import datetime

groups_bp = Blueprint('groups', __name__, template_folder='../../templates')

@groups_bp.route('/groups')
@login_required
def groups_list():
    """List all user groups."""
    user_id = session['user_id']
    user_groups = get_user_groups(user_id)
    return render_template('groups/groups.html', groups=user_groups)

@groups_bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group_route():
    """Create new shared group."""
    user_id = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        group_id, error = create_group(user_id, name, description)
        if error:
            flash(error, 'danger')
            return render_template('groups/group_create.html', name=name, description=description)

        flash(f'Group "{name}" created successfully!', 'success')
        return redirect(url_for('groups.group_detail_route', group_id=group_id))

    return render_template('groups/group_create.html')

@groups_bp.route('/groups/<int:group_id>')
@login_required
def group_detail_route(group_id):
    """Group details, shared expenses, member balances."""
    user_id = session['user_id']
    group, error = get_group_details(user_id, group_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('groups.groups_list'))

    members = get_group_members(group_id)
    expenses = get_group_expenses(group_id)
    settlement_plan = get_group_settlement_plan(group_id)

    total_group_spent = sum(float(e['amount']) for e in expenses)

    return render_template(
        'groups/group_detail.html',
        group=group,
        members=members,
        expenses=expenses,
        balances=settlement_plan['balances'],
        settlements=settlement_plan['simplified_settlements'],
        original_debts=settlement_plan['original_debt_count'],
        simplified_debts=settlement_plan['simplified_count'],
        saved_debts=settlement_plan['transactions_saved'],
        total_group_spent=total_group_spent,
        current_user_id=user_id
    )

@groups_bp.route('/groups/<int:group_id>/members/add', methods=['POST'])
@login_required
def add_member_route(group_id):
    """Add member by registered email."""
    user_id = session['user_id']
    email = request.form.get('email', '').strip()
    success, msg = add_group_member_by_email(group_id, user_id, email)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('groups.group_detail_route', group_id=group_id))

@groups_bp.route('/groups/<int:group_id>/members/remove/<int:target_user_id>', methods=['POST'])
@login_required
def remove_member_route(group_id, target_user_id):
    """Remove member from group."""
    user_id = session['user_id']
    success, error = remove_group_member(group_id, user_id, target_user_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Member removed from group.', 'info')
    return redirect(url_for('groups.group_detail_route', group_id=group_id))

@groups_bp.route('/groups/<int:group_id>/expenses/add', methods=['GET', 'POST'])
@login_required
def add_group_expense_route(group_id):
    """Add shared expense with equal, unequal, or custom split calculation."""
    user_id = session['user_id']
    group, error = get_group_details(user_id, group_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('groups.groups_list'))

    members = get_group_members(group_id)
    categories = get_categories(user_id, cat_type='expense')

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        amount = request.form.get('amount')
        category_id = request.form.get('category_id')
        try:
            paid_by = int(request.form.get('paid_by', user_id))
        except (TypeError, ValueError):
            flash('Invalid payer selection.', 'danger')
            return render_template('groups/shared_expense_form.html', group=group, members=members, categories=categories, form_data=request.form)
        expense_date = request.form.get('expense_date')
        split_type = request.form.get('split_type', 'equal')

        # Read participant checkboxes / custom amounts
        participant_ids = request.form.getlist('participants')
        if not participant_ids:
            flash('Please select at least one participant for this expense.', 'danger')
            return render_template('groups/shared_expense_form.html', group=group, members=members, categories=categories, form_data=request.form)

        participant_shares = []
        if split_type == 'equal':
            participant_shares = [{'user_id': int(pid), 'share_amount': 0.0} for pid in participant_ids]
        elif split_type == 'custom':
            for pid in participant_ids:
                share_val = request.form.get(f'share_{pid}', '0')
                try:
                    share_amt = max(0.0, float(share_val or 0))
                except ValueError:
                    share_amt = 0.0
                participant_shares.append({'user_id': int(pid), 'share_amount': share_amt})
        elif split_type == 'unequal':
            # Unequal split via percentages with safe parsing
            pcts = {}
            for pid in participant_ids:
                try:
                    pcts[pid] = max(0.0, float(request.form.get(f'percent_{pid}', 0) or 0))
                except ValueError:
                    pcts[pid] = 0.0
            total_pct = sum(pcts.values())
            try:
                tot_amt = float(amount or 0)
            except ValueError:
                tot_amt = 0.0
            running_sum = 0.0
            for idx, pid in enumerate(participant_ids):
                if idx == len(participant_ids) - 1 and total_pct > 0:
                    share_amt = round(tot_amt - running_sum, 2)
                else:
                    share_amt = round((pcts[pid] / total_pct * tot_amt) if total_pct > 0 else 0, 2)
                    running_sum += share_amt
                participant_shares.append({'user_id': int(pid), 'share_amount': share_amt})

        expense_id, err = add_shared_expense(group_id, paid_by, title, amount, category_id, expense_date, split_type, participant_shares, user_id)
        if err:
            flash(err, 'danger')
            return render_template('groups/shared_expense_form.html', group=group, members=members, categories=categories, form_data=request.form)

        flash('Shared expense recorded and split among members!', 'success')
        return redirect(url_for('groups.group_detail_route', group_id=group_id))

    today_str = datetime.now().strftime('%Y-%m-%d')
    return render_template('groups/shared_expense_form.html', group=group, members=members, categories=categories, form_data={'expense_date': today_str})

@groups_bp.route('/groups/<int:group_id>/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_group_expense_route(group_id, expense_id):
    """Delete shared expense."""
    user_id = session['user_id']
    success, error = delete_shared_expense(group_id, user_id, expense_id)
    if error:
        flash(error, 'danger')
    else:
        flash('Shared expense removed.', 'info')
    return redirect(url_for('groups.group_detail_route', group_id=group_id))

@groups_bp.route('/groups/<int:group_id>/settlements')
@login_required
def settlements_route(group_id):
    """Detailed debt settlement overview and history."""
    user_id = session['user_id']
    group, error = get_group_details(user_id, group_id)
    if error:
        flash(error, 'danger')
        return redirect(url_for('groups.groups_list'))

    settlement_plan = get_group_settlement_plan(group_id)
    history = get_settlement_history(group_id)

    return render_template(
        'groups/settlements.html',
        group=group,
        balances=settlement_plan['balances'],
        simplified_settlements=settlement_plan['simplified_settlements'],
        original_debts=settlement_plan['original_debt_count'],
        simplified_debts=settlement_plan['simplified_count'],
        saved_debts=settlement_plan['transactions_saved'],
        history=history,
        current_user_id=user_id
    )

@groups_bp.route('/groups/<int:group_id>/settlements/record', methods=['POST'])
@login_required
def record_settlement_route(group_id):
    """Mark a simplified settlement debt as paid."""
    user_id = session['user_id']
    try:
        payer_id = int(request.form.get('payer_id'))
        payee_id = int(request.form.get('payee_id'))
        amount = float(request.form.get('amount', 0))
    except (TypeError, ValueError):
        flash('Invalid settlement details.', 'danger')
        return redirect(url_for('groups.settlements_route', group_id=group_id))

    sid, error = record_settlement_payment(group_id, payer_id, payee_id, amount, user_id)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Settlement of ₹{amount:.2f} marked as paid successfully!', 'success')
    return redirect(url_for('groups.settlements_route', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group_route(group_id):
    """Leave a group if member has zero debt balance."""
    user_id = session['user_id']
    success, msg = leave_group(group_id, user_id)
    if success:
        flash(msg, 'info')
        return redirect(url_for('groups.groups_list'))
    else:
        flash(msg, 'danger')
        return redirect(url_for('groups.group_detail_route', group_id=group_id))
