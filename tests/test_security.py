import io
import unittest
from unittest.mock import patch

from flask import Flask

from app import create_app
from modules.auth.utils import get_csrf_token, validate_csrf_token
from modules.ocr.services import valid_image_content
from modules.groups.services import add_shared_expense, record_settlement_payment
from modules.shopping.services import add_shopping_item, toggle_shopping_item, delete_shopping_item, create_shopping_list
from modules.finance.services import validate_category


class SecurityUnitTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret-key-that-is-long-enough'

    def test_csrf_token_is_session_bound(self):
        with self.app.test_request_context('/'):
            token = get_csrf_token()
            self.assertTrue(validate_csrf_token(token))
            self.assertFalse(validate_csrf_token('wrong-token'))

    def test_post_without_csrf_token_is_rejected(self):
        client = create_app().test_client()
        response = client.post('/login', data={'email': 'user@example.com', 'password': 'password'})
        self.assertEqual(response.status_code, 400)

    def test_image_content_must_match_extension(self):
        png = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'payload')
        jpeg = io.BytesIO(b'\xff\xd8\xff' + b'payload')
        fake_png = io.BytesIO(b'not-an-image')
        self.assertTrue(valid_image_content(png, 'png'))
        self.assertTrue(valid_image_content(jpeg, 'jpg'))
        self.assertFalse(valid_image_content(fake_png, 'png'))

    def test_settlement_requires_requester_membership(self):
        with patch('modules.groups.services.is_group_member', return_value=False):
            sid, error = record_settlement_payment(1, 2, 3, 10, 4)
        self.assertIsNone(sid)
        self.assertIn('not authorized', error)

    def test_shared_expense_rejects_non_member_participant(self):
        with patch('modules.groups.services.is_group_member', return_value=True), \
             patch('modules.groups.services.validate_group_users', return_value=False):
            expense_id, error = add_shared_expense(1, 2, 'Dinner', 30, None, '2026-08-24', 'equal', [{'user_id': 3, 'share_amount': 30}], 2)
        self.assertIsNone(expense_id)
        self.assertIn('belong to this group', error)

    def test_category_must_be_global_or_owned(self):
        with patch('modules.finance.services.query_db', return_value=None):
            category_id, error = validate_category(4, 99, 'expense')
        self.assertIsNone(category_id)
        self.assertIn('Invalid category', error)

    def test_group_shopping_list_requires_membership(self):
        with patch('modules.shopping.services.query_db', return_value=None):
            list_id, error = create_shopping_list(4, 'Private Group List', group_id=99)
        self.assertIsNone(list_id)
        self.assertIn('belong to the selected group', error)

    def test_settlement_rejects_self_payment(self):
        with patch('modules.groups.services.is_group_member', return_value=True):
            sid, error = record_settlement_payment(1, 2, 2, 10, 4)
        self.assertIsNone(sid)
        self.assertIn('different', error)

    def test_settlement_rejects_payment_above_outstanding_debt(self):
        with patch('modules.groups.services.is_group_member', return_value=True), \
             patch('modules.groups.services.validate_group_users', return_value=True), \
             patch('modules.groups.services.calculate_group_balances', return_value={
                 2: {'balance': -10.0}, 3: {'balance': 10.0}
             }):
            sid, error = record_settlement_payment(1, 2, 3, 10.01, 4)
        self.assertIsNone(sid)
        self.assertIn('exceeds', error)

    def test_shopping_item_mutations_require_list_access(self):
        with patch('modules.shopping.services.get_shopping_list_details', return_value=(None, 'Unauthorized')):
            added, add_error = add_shopping_item(4, 10, 'Item')
            toggled, toggle_error = toggle_shopping_item(4, 10, 20)
            deleted, delete_error = delete_shopping_item(4, 10, 20)
        self.assertIsNone(added)
        self.assertFalse(toggled)
        self.assertFalse(deleted)
        self.assertTrue(add_error)
        self.assertTrue(toggle_error)
        self.assertTrue(delete_error)


if __name__ == '__main__':
    unittest.main()
