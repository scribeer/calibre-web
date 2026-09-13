"""Regression tests: AU-Books registration allows weak passwords."""

import re
import unittest
from pathlib import Path

WEB_PY_PATH = Path(__file__).parent.parent / "cps" / "web.py"
TEMPLATE_PATH = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "register.html"


def read_web_source():
    return WEB_PY_PATH.read_text()


def read_register_template():
    return TEMPLATE_PATH.read_text()


class TestRegisterPostAllowsWeakPasswords(unittest.TestCase):
    """Verify register_post() does NOT call valid_password() for user-chosen passwords."""

    def test_no_valid_password_call_in_register_post(self):
        src = read_web_source()
        # Password validation now lives in the shared registration helper.
        match = re.search(
            r'def _register_user\(.*?\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        self.assertIsNotNone(match, "register_post function not found")
        body = match.group(1)
        self.assertNotIn(
            'valid_password(',
            body,
            "register_post must NOT call valid_password() — weak passwords are allowed",
        )

    def test_empty_password_rejected(self):
        src = read_web_source()
        match = re.search(
            r'def _register_user\(.*?\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        body = match.group(1)
        self.assertIn(
            'Password cannot be empty',
            body,
            "register_post must reject empty passwords",
        )

    def test_password_mismatch_rejected(self):
        src = read_web_source()
        match = re.search(
            r'def _register_user\(.*?\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        body = match.group(1)
        self.assertIn(
            'Passwords do not match',
            body,
            "register_post must reject mismatched passwords",
        )


class TestRegisterTemplate(unittest.TestCase):
    """Verify register.html has required fields."""

    def test_has_password_field(self):
        html = read_register_template()
        self.assertIn('name="password"', html)

    def test_has_confirm_password_field(self):
        html = read_register_template()
        self.assertIn('name="confirm_password"', html)

    def test_no_minlength_attribute(self):
        html = read_register_template()
        self.assertNotIn('minlength', html,
                         "register template must not enforce minlength")

    def test_has_username_field(self):
        html = read_register_template()
        self.assertIn('name="name"', html)

    def test_has_email_field(self):
        html = read_register_template()
        self.assertIn('name="email"', html)

    def test_has_csrf_token(self):
        html = read_register_template()
        self.assertIn('csrf_token', html)

    def test_has_login_link(self):
        html = read_register_template()
        self.assertIn('web.login', html)

    def test_extends_theme_layout(self):
        html = read_register_template()
        self.assertIn("extends theme('layout.html')", html)


if __name__ == '__main__':
    unittest.main()
