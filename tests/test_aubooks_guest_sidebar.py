"""Regression tests: AU-Books guest sidebar navigation."""

import unittest
from pathlib import Path

WEB_PY_PATH = Path(__file__).parent.parent / "cps" / "web.py"


def read_web_source():
    return WEB_PY_PATH.read_text()


class TestGuestCategoryAccess(unittest.TestCase):
    """Verify anonymous users can access /category without 404."""

    def test_category_list_allows_anonymous(self):
        src = read_web_source()
        # Find category_list function
        import re
        match = re.search(
            r'def category_list\(\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        self.assertIsNotNone(match, "category_list function not found")
        body = match.group(1)
        # Should check is_anonymous OR check_visibility
        self.assertIn(
            "current_user.is_anonymous",
            body,
            "category_list should allow anonymous users via is_anonymous check",
        )


if __name__ == '__main__':
    unittest.main()
