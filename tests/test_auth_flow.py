import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from database.db import init_db, execute_db
from modules.auth.services import register_user, get_user_by_email
from modules.auth.utils import get_csrf_token


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()
        # Clean up test user if present
        execute_db("DELETE FROM users WHERE email = ?", ('auth_test@example.com',))
        # Register a known test user
        self.user_id, self.err = register_user('Auth Tester', 'auth_test@example.com', 'ValidPass123!')
        self.assertIsNotNone(self.user_id)

    def tearDown(self):
        execute_db("DELETE FROM users WHERE email = ?", ('auth_test@example.com',))

    def _get_csrf_token(self, client):
        """Helper to get a valid CSRF token from the login page."""
        response = client.get('/login')
        self.assertEqual(response.status_code, 200)
        with client.session_transaction() as sess:
            return sess.get('_csrf_token')

    def test_successful_login(self):
        """User can log in with valid credentials and receives a valid session."""
        csrf_token = self._get_csrf_token(self.client)
        response = self.client.post('/login', data={
            'email': 'auth_test@example.com',
            'password': 'ValidPass123!',
            '_csrf_token': csrf_token
        }, follow_redirects=False)

        # Should redirect to dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get('Location'), '/dashboard')

        # Session must contain user credentials
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), self.user_id)
            self.assertEqual(sess.get('user_email'), 'auth_test@example.com')
            self.assertEqual(sess.get('user_name'), 'Auth Tester')

    def test_incorrect_password(self):
        """Login fails when an incorrect password is provided."""
        csrf_token = self._get_csrf_token(self.client)
        response = self.client.post('/login', data={
            'email': 'auth_test@example.com',
            'password': 'WrongPassword999!',
            '_csrf_token': csrf_token
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid password', response.data)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('user_id'))

    def test_unknown_user(self):
        """Login fails when the email does not exist in the database."""
        csrf_token = self._get_csrf_token(self.client)
        response = self.client.post('/login', data={
            'email': 'nonexistent_user@example.com',
            'password': 'SomePassword123!',
            '_csrf_token': csrf_token
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No account found with this email address', response.data)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('user_id'))

    def test_session_persistence_on_protected_routes(self):
        """A logged-in user maintains their session and can access protected views."""
        csrf_token = self._get_csrf_token(self.client)
        self.client.post('/login', data={
            'email': 'auth_test@example.com',
            'password': 'ValidPass123!',
            '_csrf_token': csrf_token
        }, follow_redirects=True)

        # Access protected dashboard
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Auth Tester', res.data)

        # Access protected profile
        res_profile = self.client.get('/profile')
        self.assertEqual(res_profile.status_code, 200)
        self.assertIn(b'Auth Tester', res_profile.data)

    def test_stale_session_cleared_and_allows_login(self):
        """When a session has a user_id that does not exist in the database,
        the application must clear the stale session and allow the user to view /login."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 99999999
            sess['user_name'] = 'Ghost User'
            sess['user_email'] = 'ghost@example.com'

        # Visiting /login must render the login page (200 OK), NOT redirect to /dashboard (302)
        login_res = self.client.get('/login')
        self.assertEqual(login_res.status_code, 200, "Stale session prevented user from viewing /login!")
        self.assertIn(b'Welcome Back', login_res.data)

        # Protected route should redirect to /login
        with self.client.session_transaction() as sess:
            sess['user_id'] = 99999999
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 302)
        self.assertIn('/login', dash_res.headers.get('Location', ''))

    def test_stale_session_cleared_on_root_index_redirects_to_login(self):
        """Root route / redirects to /login if session user_id does not exist in DB."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 99999999
        res = self.client.get('/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

    def test_logout_clears_session_safely(self):
        """User logout clears session and redirects to /login."""
        csrf_token = self._get_csrf_token(self.client)
        self.client.post('/login', data={
            'email': 'auth_test@example.com',
            'password': 'ValidPass123!',
            '_csrf_token': csrf_token
        }, follow_redirects=True)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), self.user_id)
            csrf_token_logout = sess.get('_csrf_token')

        logout_res = self.client.post('/logout', data={
            '_csrf_token': csrf_token_logout
        }, follow_redirects=False)
        self.assertEqual(logout_res.status_code, 302)
        self.assertIn('/login', logout_res.headers.get('Location', ''))

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('user_id'))

    def test_proxy_fix_recognizes_https(self):
        """ProxyFix correctly updates WSGI environ scheme to https from X-Forwarded-Proto header."""
        environ = {}

        def fake_start_response(status, headers):
            pass

        # WSGI environ mimicking Render reverse proxy
        test_environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/login',
            'SERVER_NAME': 'splitstack.onrender.com',
            'SERVER_PORT': '80',
            'wsgi.url_scheme': 'http',
            'HTTP_HOST': 'splitstack.onrender.com',
            'HTTP_X_FORWARDED_PROTO': 'https',
            'HTTP_X_FORWARDED_FOR': '203.0.113.195',
            'HTTP_X_FORWARDED_HOST': 'evil-host.com',
        }

        # Run through ProxyFix WSGI layer
        self.app.wsgi_app(test_environ, fake_start_response)

        # ProxyFix must have updated wsgi.url_scheme to https based on X-Forwarded-Proto
        self.assertEqual(test_environ.get('wsgi.url_scheme'), 'https')
        # ProxyFix must NOT have updated HTTP_HOST because x_host=0
        self.assertEqual(test_environ.get('HTTP_HOST'), 'splitstack.onrender.com')


if __name__ == '__main__':
    unittest.main()

