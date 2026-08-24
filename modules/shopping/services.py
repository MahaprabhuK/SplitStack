from database.db import query_db, execute_db
from datetime import datetime

def get_user_shopping_lists(user_id):
    """Get personal shopping lists and lists shared through groups the user is part of."""
    return query_db("""
        SELECT sl.*, g.name AS group_name, u.name AS creator_name,
               (SELECT COUNT(*) FROM shopping_items WHERE list_id = sl.id) AS total_items,
               (SELECT COUNT(*) FROM shopping_items WHERE list_id = sl.id AND is_purchased = TRUE) AS purchased_items
        FROM shopping_lists sl
        LEFT JOIN "groups" g ON sl.group_id = g.id
        JOIN users u ON sl.user_id = u.id
        WHERE sl.user_id = ? OR sl.group_id IN (SELECT group_id FROM group_members WHERE user_id = ?)
        ORDER BY sl.created_at DESC
    """, (user_id, user_id))

def get_shopping_list_details(user_id, list_id):
    """Get single shopping list and verify authorization."""
    sl = query_db("""
        SELECT sl.*, g.name AS group_name, u.name AS creator_name
        FROM shopping_lists sl
        LEFT JOIN "groups" g ON sl.group_id = g.id
        JOIN users u ON sl.user_id = u.id
        WHERE sl.id = ?
    """, (list_id,), one=True)
    if not sl:
        return None, "Shopping list not found."

    # Check access: creator or group member
    if sl['user_id'] != user_id:
        if sl['group_id']:
            membership = query_db("SELECT id FROM group_members WHERE group_id = ? AND user_id = ?", (sl['group_id'], user_id), one=True)
            if not membership:
                return None, "You do not have permission to view this shopping list."
        else:
            return None, "Unauthorized."

    return sl, None

def create_shopping_list(user_id, title, description=None, group_id=None):
    """Create shopping list."""
    title = (title or '').strip()
    if not title:
        return None, "List title is required."

    gid = int(group_id) if group_id and str(group_id).isdigit() else None
    if gid and not query_db("SELECT id FROM group_members WHERE group_id = ? AND user_id = ?", (gid, user_id), one=True):
        return None, "You must belong to the selected group."
    lid = execute_db("""
        INSERT INTO shopping_lists (user_id, group_id, title, description)
        VALUES (?, ?, ?, ?)
    """, (user_id, gid, title, description or ''))
    return lid, None

def delete_shopping_list(user_id, list_id):
    """Delete shopping list."""
    sl, err = get_shopping_list_details(user_id, list_id)
    if err:
        return False, err
    execute_db("DELETE FROM shopping_lists WHERE id = ?", (list_id,))
    return True, None

# ----------------------------------------------------
# Items & Financial Calculations
# ----------------------------------------------------
def get_shopping_items(list_id):
    """Get all items in a shopping list with calculations."""
    items = query_db("""
        SELECT si.*, u.name AS assigned_name
        FROM shopping_items si
        LEFT JOIN users u ON si.assigned_to = u.id
        WHERE si.list_id = ?
        ORDER BY si.is_purchased ASC, si.id ASC
    """, (list_id,))

    est_total = sum(float(i['quantity']) * float(i['estimated_price']) for i in items)
    act_total = sum(float(i['quantity']) * float(i['actual_price'] if i['actual_price'] is not None else i['estimated_price']) for i in items if i['is_purchased'])
    variance = act_total - est_total

    return {
        'items': items,
        'estimated_total': est_total,
        'actual_total': act_total,
        'difference': variance,
        'total_count': len(items),
        'purchased_count': sum(1 for i in items if i['is_purchased'])
    }

def add_shopping_item(user_id, list_id, item_name, quantity=1, estimated_price=0.0, assigned_to=None):
    """Add item to shopping list."""
    shopping_list, error = get_shopping_list_details(user_id, list_id)
    if error:
        return None, error
    item_name = (item_name or '').strip()
    if not item_name:
        return None, "Item name is required."

    qty = max(1, int(quantity or 1))
    est_price = max(0.0, float(estimated_price or 0.0))
    assigned = int(assigned_to) if assigned_to and str(assigned_to).isdigit() else None
    if assigned and (not shopping_list['group_id'] or not query_db(
        "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
        (shopping_list['group_id'], assigned), one=True
    )):
        return None, "Assigned user must belong to the shopping list group."

    iid = execute_db("""
        INSERT INTO shopping_items (list_id, item_name, quantity, estimated_price, assigned_to)
        VALUES (?, ?, ?, ?, ?)
    """, (list_id, item_name, qty, est_price, assigned))
    return iid, None

def toggle_shopping_item(user_id, list_id, item_id, actual_price=None):
    """Toggle item purchased state and optionally record actual price."""
    if not get_shopping_list_details(user_id, list_id)[0]:
        return False, "You do not have permission to modify this shopping list."
    item = query_db("SELECT * FROM shopping_items WHERE id = ? AND list_id = ?", (item_id, list_id), one=True)
    if not item:
        return False, "Item not found."

    new_status = not item['is_purchased']
    act_price = float(actual_price) if actual_price is not None and str(actual_price).strip() else item['actual_price']

    execute_db("""
        UPDATE shopping_items 
        SET is_purchased = ?, actual_price = ?
        WHERE id = ?
    """, (new_status, act_price, item_id))
    return True, None

def delete_shopping_item(user_id, list_id, item_id):
    """Delete an item from list."""
    if not get_shopping_list_details(user_id, list_id)[0]:
        return False, "You do not have permission to modify this shopping list."
    execute_db("DELETE FROM shopping_items WHERE id = ? AND list_id = ?", (item_id, list_id))
    return True, None
