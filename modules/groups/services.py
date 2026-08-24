from database.db import query_db, execute_db
from modules.groups.settlement_service import simplify_debts
from modules.finance.services import validate_category
from datetime import datetime
from mysql.connector import Error

def is_group_member(group_id, user_id):
    return query_db(
        "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id), one=True
    ) is not None

def validate_group_users(group_id, user_ids):
    """Ensure every supplied user is a member of the group."""
    unique_ids = set(user_ids)
    if len(unique_ids) != len(user_ids):
        return False
    if not unique_ids:
        return False
    placeholders = ','.join(['%s'] * len(unique_ids))
    members = query_db(
        f"SELECT user_id FROM group_members WHERE group_id = %s AND user_id IN ({placeholders})",
        [group_id, *unique_ids]
    )
    return len(members) == len(unique_ids)

# ----------------------------------------------------
# Group Management
# ----------------------------------------------------
def get_user_groups(user_id):
    """Get all groups a user is a member of."""
    return query_db("""
        SELECT g.id, g.name, g.description, g.created_by, g.created_at,
               gm.role, u.name AS creator_name,
               (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS member_count,
               (SELECT COALESCE(SUM(amount), 0) FROM shared_expenses WHERE group_id = g.id) AS total_spent
        FROM `groups` g
        JOIN group_members gm ON g.id = gm.group_id
        JOIN users u ON g.created_by = u.id
        WHERE gm.user_id = %s
        ORDER BY g.created_at DESC
    """, (user_id,))

def get_group_details(user_id, group_id):
    """Get group details if user is an authorized member."""
    membership = query_db("""
        SELECT role FROM group_members WHERE group_id = %s AND user_id = %s
    """, (group_id, user_id), one=True)
    if not membership:
        return None, "You are not a member of this group."

    group_data = query_db("""
        SELECT g.*, u.name AS creator_name
        FROM `groups` g
        JOIN users u ON g.created_by = u.id
        WHERE g.id = %s
    """, (group_id,), one=True)
    group_data['user_role'] = membership['role']
    return group_data, None

def create_group(creator_id, name, description=None):
    """Create a new group and add the creator as an admin."""
    name = (name or '').strip()
    if not name:
        return None, "Group name is required."

    group_id = execute_db("""
        INSERT INTO `groups` (name, description, created_by)
        VALUES (%s, %s, %s)
    """, (name, description or '', creator_id))

    # Add creator as admin member
    execute_db("""
        INSERT INTO group_members (group_id, user_id, role)
        VALUES (%s, %s, 'admin')
    """, (group_id, creator_id))

    return group_id, None

def get_group_members(group_id):
    """List all members of a group."""
    return query_db("""
        SELECT gm.id AS membership_id, gm.user_id, gm.role, gm.joined_at,
               u.name, u.email
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = %s
        ORDER BY gm.role ASC, u.name ASC
    """, (group_id,))

def add_group_member_by_email(group_id, admin_user_id, member_email):
    """Add a registered user to the group by email address."""
    # Verify admin
    admin = query_db("SELECT role FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, admin_user_id), one=True)
    if not admin or admin['role'] != 'admin':
        return False, "Only group admins can add new members."

    member_email = (member_email or '').strip().lower()
    user_to_add = query_db("SELECT id, name FROM users WHERE email = %s", (member_email,), one=True)
    if not user_to_add:
        return False, f"No user found with email '{member_email}'. They must register first."

    # Check if already a member
    already = query_db("SELECT id FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_to_add['id']), one=True)
    if already:
        return False, f"{user_to_add['name']} is already a member of this group."

    execute_db("""
        INSERT INTO group_members (group_id, user_id, role)
        VALUES (%s, %s, 'member')
    """, (group_id, user_to_add['id']))

    return True, f"{user_to_add['name']} has been added to the group."

def remove_group_member(group_id, admin_user_id, target_user_id):
    """Remove a member from the group."""
    if admin_user_id == target_user_id:
        return False, "You cannot remove yourself. Use Leave Group instead."

    admin = query_db("SELECT role FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, admin_user_id), one=True)
    if not admin or admin['role'] != 'admin':
        return False, "Only group admins can remove members."

    execute_db("DELETE FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, target_user_id))
    return True, None

# ----------------------------------------------------
# Shared Expenses & Splitting
# ----------------------------------------------------
def get_group_expenses(group_id):
    """Get all shared expenses for a group."""
    expenses = query_db("""
        SELECT se.*, u.name AS payer_name,
               c.name AS category_name, c.icon AS category_icon, c.color AS category_color
        FROM shared_expenses se
        JOIN users u ON se.paid_by = u.id
        LEFT JOIN categories c ON se.category_id = c.id
        WHERE se.group_id = %s
        ORDER BY se.expense_date DESC, se.id DESC
    """, (group_id,))

    # Attach participants to each expense
    for exp in expenses:
        participants = query_db("""
            SELECT ep.user_id, ep.share_amount, u.name
            FROM expense_participants ep
            JOIN users u ON ep.user_id = u.id
            WHERE ep.shared_expense_id = %s
        """, (exp['id'],))
        exp['participants'] = participants

    return expenses

def add_shared_expense(group_id, paid_by_id, title, total_amount, category_id, expense_date, split_type, participant_shares, current_user_id=None):
    """
    Add a shared expense with equal, unequal, or custom split calculation.
    participant_shares: list of dicts [{'user_id': int, 'share_amount': float}]
    """
    title = (title or '').strip()
    if not title:
        return None, "Expense description/title is required."

    try:
        total_amount = float(total_amount)
        if total_amount <= 0:
            return None, "Expense total must be greater than zero."
    except (ValueError, TypeError):
        return None, "Invalid expense total amount."

    if not participant_shares or len(participant_shares) == 0:
        return None, "At least one participant must be included in the split."

    participant_ids = [p.get('user_id') for p in participant_shares]
    if not is_group_member(group_id, paid_by_id) or not validate_group_users(group_id, participant_ids):
        return None, "All expense participants must belong to this group."

    category_id, category_error = validate_category(current_user_id or paid_by_id, category_id, 'expense')
    if category_error:
        return None, category_error

    # Validate and calculate splits
    if split_type == 'equal':
        equal_share = round(total_amount / len(participant_shares), 2)
        # Adjust penny difference on first participant
        calculated_shares = []
        running_total = 0.0
        for i, p in enumerate(participant_shares):
            if i == len(participant_shares) - 1:
                share = round(total_amount - running_total, 2)
            else:
                share = equal_share
                running_total += share
            calculated_shares.append({'user_id': p['user_id'], 'share_amount': share})
        participant_shares = calculated_shares

    # Validate sum equals total_amount within 0.05
    sum_shares = sum(float(p['share_amount']) for p in participant_shares)
    if abs(sum_shares - total_amount) > 0.05:
        return None, f"Sum of participant shares (?{sum_shares:.2f}) must equal the total expense amount (?{total_amount:.2f})."

    if not expense_date:
        expense_date = datetime.now().strftime('%Y-%m-%d')

    # Insert shared expense record
    expense_id = execute_db("""
        INSERT INTO shared_expenses (group_id, paid_by, category_id, title, amount, split_type, expense_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (group_id, paid_by_id, cat_id, title, total_amount, split_type, expense_date))

    # Insert participants
    for p in participant_shares:
        execute_db("""
            INSERT INTO expense_participants (shared_expense_id, user_id, share_amount)
            VALUES (%s, %s, %s)
        """, (expense_id, p['user_id'], p['share_amount']))

    return expense_id, None

def delete_shared_expense(group_id, user_id, expense_id):
    """Delete a shared expense if user paid it or is an admin."""
    exp = query_db("SELECT * FROM shared_expenses WHERE id = %s AND group_id = %s", (expense_id, group_id), one=True)
    if not exp:
        return False, "Expense not found."
    
    admin = query_db("SELECT role FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id), one=True)
    if exp['paid_by'] != user_id and (not admin or admin['role'] != 'admin'):
        return False, "You do not have permission to delete this expense."

    execute_db("DELETE FROM shared_expenses WHERE id = %s", (expense_id,))
    return True, None

# ----------------------------------------------------
# Debt Calculation & Group Settlement Simplification
# ----------------------------------------------------
def calculate_group_balances(group_id):
    """
    Calculates each member's net balance within the group:
    Net Balance = (Total Paid in shared expenses + Total Settled as Payer)
                  - (Total Share Owed in expenses + Total Received as Payee in settlements)
    """
    members = get_group_members(group_id)
    balances = {m['user_id']: {'name': m['name'], 'email': m['email'], 'paid': 0.0, 'owed': 0.0, 'settled_paid': 0.0, 'settled_received': 0.0, 'balance': 0.0} for m in members}

    # 1. Total paid by each member
    paid_rows = query_db("""
        SELECT paid_by, COALESCE(SUM(amount), 0) AS total_paid
        FROM shared_expenses
        WHERE group_id = %s
        GROUP BY paid_by
    """, (group_id,))
    for r in paid_rows:
        if r['paid_by'] in balances:
            balances[r['paid_by']]['paid'] = float(r['total_paid'])

    # 2. Total owed by each member from participants
    owed_rows = query_db("""
        SELECT ep.user_id, COALESCE(SUM(ep.share_amount), 0) AS total_owed
        FROM expense_participants ep
        JOIN shared_expenses se ON ep.shared_expense_id = se.id
        WHERE se.group_id = %s
        GROUP BY ep.user_id
    """, (group_id,))
    for r in owed_rows:
        if r['user_id'] in balances:
            balances[r['user_id']]['owed'] = float(r['total_owed'])

    # 3. Factoring in completed settlements
    completed_settlements = query_db("""
        SELECT payer_id, payee_id, COALESCE(SUM(amount), 0) AS total_amount
        FROM settlements
        WHERE group_id = %s AND status = 'completed'
        GROUP BY payer_id, payee_id
    """, (group_id,))
    for s in completed_settlements:
        payer = s['payer_id']
        payee = s['payee_id']
        amt = float(s['total_amount'])
        if payer in balances:
            balances[payer]['settled_paid'] += amt
        if payee in balances:
            balances[payee]['settled_received'] += amt

    # 4. Final Net Balance
    for uid, data in balances.items():
        net = (data['paid'] + data['settled_paid']) - (data['owed'] + data['settled_received'])
        data['balance'] = round(net, 2)

    return balances

def get_group_settlement_plan(group_id):
    """Runs the debt simplification algorithm on the current group net balances."""
    balances = calculate_group_balances(group_id)
    simplification = simplify_debts(balances)
    return {
        'balances': balances,
        'simplified_settlements': simplification['settlements'],
        'original_debt_count': simplification['original_debt_count'],
        'simplified_count': simplification['simplified_count'],
        'transactions_saved': simplification['transactions_saved']
    }

def record_settlement_payment(group_id, payer_id, payee_id, amount, current_user_id=None):
    """Mark a debt settlement as completed."""
    if current_user_id is None or not is_group_member(group_id, current_user_id):
        return None, "You are not authorized to record settlements for this group."
    if payer_id == payee_id or not validate_group_users(group_id, [payer_id, payee_id]):
        return None, "Settlement payer and payee must be different group members."

    try:
        amount = float(amount)
        if amount <= 0:
            return None, "Settlement amount must be positive."
    except (ValueError, TypeError):
        return None, "Invalid settlement amount."

    balances = calculate_group_balances(group_id)
    payer_balance = balances[payer_id]['balance']
    payee_balance = balances[payee_id]['balance']
    outstanding = min(max(0.0, -payer_balance), max(0.0, payee_balance))
    if outstanding <= 0 or amount > outstanding + 0.005:
        return None, "Settlement amount exceeds the outstanding debt."

    sid = execute_db("""
        INSERT INTO settlements (group_id, payer_id, payee_id, amount, status, settled_at)
        VALUES (%s, %s, %s, %s, 'completed', NOW())
    """, (group_id, payer_id, payee_id, amount))
    return sid, None

def get_settlement_history(group_id):
    """Get historical settlements for the group."""
    return query_db("""
        SELECT s.*, u1.name AS payer_name, u2.name AS payee_name
        FROM settlements s
        JOIN users u1 ON s.payer_id = u1.id
        JOIN users u2 ON s.payee_id = u2.id
        WHERE s.group_id = %s
        ORDER BY s.settled_at DESC, s.id DESC
    """, (group_id,))
