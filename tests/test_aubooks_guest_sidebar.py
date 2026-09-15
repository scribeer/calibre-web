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


class TestGuestAuthorAccess(unittest.TestCase):
    """Verify anonymous users can access /author catalog without 404."""

    def test_author_list_allows_anonymous(self):
        src = read_web_source()
        import re
        match = re.search(
            r'def author_list\(\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        self.assertIsNotNone(match, "author_list function not found")
        body = match.group(1)
        # Should allow anonymous users when AU-Books theme is active
        self.assertIn(
            "current_user.is_anonymous",
            body,
            "author_list should allow anonymous users via is_anonymous check",
        )
        # Should use server-side pagination instead of loading all authors
        self.assertIn(
            ".limit(per_page)",
            body,
            "author_list should use SQL LIMIT for server-side pagination",
        )

    def test_author_list_uses_server_side_char_filter(self):
        src = read_web_source()
        import re
        match = re.search(
            r'def author_list\(\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        self.assertIsNotNone(match, "author_list function not found")
        body = match.group(1)
        # Should read char query parameter
        self.assertIn(
            "request.args.get('char'",
            body,
            "author_list should read char query parameter",
        )
        # Should apply char filter before LIMIT/OFFSET in SQL
        self.assertIn(
            "func.upper(func.substr(db.Authors.sort, 1, 1))",
            body,
            "author_list should filter authors by first character server-side",
        )


if __name__ == '__main__':
    unittest.main()
