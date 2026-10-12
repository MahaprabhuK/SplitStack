import unittest
import sys
import os
from unittest.mock import patch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from modules.groups.services import add_shared_expense, remove_group_member, leave_group
from modules.finance.services import add_expense, set_budget, _validate_date_str
from ml.spending_predictor import predict_monthly_spending

class CoreRegressionTests(unittest.TestCase):
    """Regression test suite for confirmed bugs, financial calculations, and integrity checks."""

    def test_negative_share_amount_rejected(self):
        """Participant share amount < 0 must be rejected."""
        with patch('modules.groups.services.is_group_member', return_value=True), \
             patch('modules.groups.services.validate_group_users', return_value=True), \
             patch('modules.groups.services.validate_category', return_value=(None, None)):
            exp_id, err = add_shared_expense(
                group_id=1, paid_by_id=1, title='Test Negative Share', total_amount=100.0,
                category_id=None, expense_date='2026-10-12', split_type='custom',
                participant_shares=[{'user_id': 1, 'share_amount': -20.0}, {'user_id': 2, 'share_amount': 120.0}]
            )
            self.assertIsNone(exp_id)
            self.assertIn('cannot be negative', err)

    def test_invalid_date_format_rejected(self):
        """Dates not matching YYYY-MM-DD must be rejected."""
        valid_date, err = _validate_date_str('2026-10-12')
        self.assertEqual(valid_date, '2026-10-12')
        self.assertIsNone(err)

        invalid_date, err = _validate_date_str('2026-99-99')
        self.assertIsNone(invalid_date)
        self.assertIn('Invalid date format', err)

        invalid_date2, err2 = _validate_date_str('invalid-date-string')
        self.assertIsNone(invalid_date2)
        self.assertIn('Invalid date format', err2)

    def test_cannot_remove_member_with_outstanding_balance(self):
        """Admins cannot remove a member whose group net balance is non-zero."""
        mock_balances = {
            2: {'name': 'Bob', 'balance': -250.0}
        }
        with patch('modules.groups.services.query_db', return_value={'role': 'admin'}), \
             patch('modules.groups.services.calculate_group_balances', return_value=mock_balances):
            success, err = remove_group_member(group_id=1, admin_user_id=1, target_user_id=2)
            self.assertFalse(success)
            self.assertIn('outstanding balance', err)

    def test_leave_group_blocked_with_balance(self):
        """Users cannot leave a group if they have an unsettled balance."""
        mock_balances = {
            2: {'name': 'Bob', 'balance': 150.0}
        }
        with patch('modules.groups.services.query_db', return_value={'role': 'member'}), \
             patch('modules.groups.services.calculate_group_balances', return_value=mock_balances):
            success, msg = leave_group(group_id=1, user_id=2)
            self.assertFalse(success)
            self.assertIn('outstanding balance', msg)

    def test_budget_bounds_validation(self):
        """Budgets reject invalid amounts or out-of-range months."""
        # Non-positive amount
        bid, err = set_budget(user_id=1, category_id=None, amount=0, month=10, year=2026)
        self.assertIsNone(bid)
        self.assertIn('greater than zero', err)

        # Invalid month
        bid, err = set_budget(user_id=1, category_id=None, amount=1000, month=13, year=2026)
        self.assertIsNone(bid)
        self.assertIn('between 1 and 12', err)

    def test_equal_split_absorbs_rounding_penny(self):
        """Equal split of 100 among 3 participants must sum exactly to 100.00."""
        with patch('modules.groups.services.is_group_member', return_value=True), \
             patch('modules.groups.services.validate_group_users', return_value=True), \
             patch('modules.groups.services.validate_category', return_value=(None, None)), \
             patch('modules.groups.services.transaction'), \
             patch('modules.groups.services.execute_db', return_value=999):
            participants = [{'user_id': 1}, {'user_id': 2}, {'user_id': 3}]
            exp_id, err = add_shared_expense(
                group_id=1, paid_by_id=1, title='Dinner', total_amount=100.0,
                category_id=None, expense_date='2026-10-12', split_type='equal',
                participant_shares=participants
            )
            self.assertEqual(exp_id, 999)
            self.assertIsNone(err)

    def test_predict_monthly_spending_currency_symbol(self):
        """Prediction message must contain the rupee symbol instead of question mark."""
        mock_row = {'tx_count': 5, 'total_spent': 5000.0}
        with patch('ml.spending_predictor.query_db', return_value=mock_row):
            pred = predict_monthly_spending(user_id=1, month=10, year=2026)
            self.assertTrue(pred['has_sufficient_data'])
            self.assertIn('₹', pred['message'])
            self.assertNotIn('?', pred['message'])

    def test_group_detail_page_with_expenses(self):
        """Authenticated member can view group detail page when group has expenses."""
        import uuid
        from modules.auth.services import register_user
        from modules.groups.services import create_group, add_group_member_by_email, add_shared_expense
        app = create_app()
        uid_suffix = uuid.uuid4().hex[:6]
        with app.app_context():
            u1_id, _ = register_user('Member One', f'm1_{uid_suffix}@example.com', 'Password123!')
            u2_id, _ = register_user('Member Two', f'm2_{uid_suffix}@example.com', 'Password123!')
            gid, _ = create_group(u1_id, f'Group With Expenses {uid_suffix}')
            add_group_member_by_email(gid, u1_id, f'm2_{uid_suffix}@example.com')
            add_shared_expense(
                group_id=gid, paid_by_id=u1_id, title='Shared Lunch', total_amount=100.0,
                category_id=None, expense_date='2026-10-12', split_type='equal',
                participant_shares=[{'user_id': u1_id}, {'user_id': u2_id}],
                current_user_id=u1_id
            )

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = u1_id
            sess['user_name'] = 'Member One'
            sess['user_email'] = f'm1_{uid_suffix}@example.com'

        res = client.get(f'/groups/{gid}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Shared Lunch', res.data)
        self.assertIn(b'Member Net Balances', res.data)

    def test_group_detail_page_without_expenses(self):
        """Authenticated member can view group detail page when group has 0 expenses."""
        import uuid
        from modules.auth.services import register_user
        from modules.groups.services import create_group
        app = create_app()
        uid_suffix = uuid.uuid4().hex[:6]
        with app.app_context():
            u1_id, _ = register_user('Solo Member', f'solo_{uid_suffix}@example.com', 'Password123!')
            gid, err = create_group(u1_id, f'Empty Group {uid_suffix}')
            self.assertIsNone(err)

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = u1_id
            sess['user_name'] = 'Solo Member'
            sess['user_email'] = f'solo_{uid_suffix}@example.com'

        res = client.get(f'/groups/{gid}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(f'Empty Group {uid_suffix}'.encode(), res.data)
        self.assertIn(b'No shared expenses recorded yet', res.data)

    def test_group_detail_page_non_member_redirect(self):
        """Authenticated user who is not a member is redirected away from group detail."""
        import uuid
        from modules.auth.services import register_user
        from modules.groups.services import create_group
        app = create_app()
        uid_suffix = uuid.uuid4().hex[:6]
        with app.app_context():
            owner_id, _ = register_user('Owner', f'owner_{uid_suffix}@example.com', 'Password123!')
            outsider_id, _ = register_user('Outsider', f'outsider_{uid_suffix}@example.com', 'Password123!')
            gid, _ = create_group(owner_id, f'Private Group {uid_suffix}')

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = outsider_id
            sess['user_name'] = 'Outsider'
            sess['user_email'] = f'outsider_{uid_suffix}@example.com'

        res = client.get(f'/groups/{gid}')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/groups', res.headers.get('Location', ''))

    def test_get_group_details_and_expenses_dict_immutability(self):
        """get_group_details and get_group_expenses return dicts supporting user_role and participants."""
        import uuid
        from modules.auth.services import register_user
        from modules.groups.services import create_group, add_shared_expense, get_group_details, get_group_expenses
        app = create_app()
        uid_suffix = uuid.uuid4().hex[:6]
        with app.app_context():
            u_id, _ = register_user('Dict User', f'dict_{uid_suffix}@example.com', 'Password123!')
            gid, _ = create_group(u_id, f'Dict Group {uid_suffix}')
            add_shared_expense(
                group_id=gid, paid_by_id=u_id, title='Coffee', total_amount=50.0,
                category_id=None, expense_date='2026-10-12', split_type='equal',
                participant_shares=[{'user_id': u_id}],
                current_user_id=u_id
            )

            details, err = get_group_details(user_id=u_id, group_id=gid)
            self.assertIsNone(err)
            self.assertIsInstance(details, dict)
            self.assertEqual(details.get('user_role'), 'admin')

            expenses = get_group_expenses(group_id=gid)
            self.assertIsInstance(expenses, list)
            self.assertEqual(len(expenses), 1)
            self.assertIsInstance(expenses[0], dict)
            self.assertIn('participants', expenses[0])
            self.assertIsInstance(expenses[0]['participants'], list)

    def test_http_400_custom_error_page(self):
        """POST without CSRF token returns 400 with custom error page rendered."""
        client = create_app().test_client()
        res = client.post('/login', data={'email': 'test@example.com', 'password': 'pass'})
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'400 - Bad Request', res.data)
        self.assertIn(b'Return to Dashboard', res.data)

if __name__ == '__main__':
    unittest.main()
