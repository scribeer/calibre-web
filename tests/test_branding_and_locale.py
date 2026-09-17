"""Regression tests: AU-Books branding and Russian locale defaults."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_PY = ROOT / "cps" / "web.py"
HELPER_PY = ROOT / "cps" / "helper.py"
ABOUT_PY = ROOT / "cps" / "about.py"
SEARCH_PY = ROOT / "cps" / "search.py"
ERROR_HANDLER_PY = ROOT / "cps" / "error_handler.py"
CONFIG_SQL_PY = ROOT / "cps" / "config_sql.py"
OSD_XML = ROOT / "cps" / "templates" / "osd.xml"
FEED_XML = ROOT / "cps" / "templates" / "feed.xml"
INDEX_XML = ROOT / "cps" / "templates" / "index.xml"

STANDARD_STATS = ROOT / "cps" / "themes" / "standard" / "templates" / "stats.html"
STANDARD_HTTP_ERROR = ROOT / "cps" / "themes" / "standard" / "templates" / "http_error.html"
STANDARD_ADMIN = ROOT / "cps" / "themes" / "standard" / "templates" / "admin.html"
STANDARD_LOGVIEWER = ROOT / "cps" / "themes" / "standard" / "templates" / "logviewer.html"
STANDARD_CONFIG_EDIT = ROOT / "cps" / "themes" / "standard" / "templates" / "config_edit.html"
STANDARD_DETAIL = ROOT / "cps" / "themes" / "standard" / "templates" / "detail.html"
CALIBLUR_STATS = ROOT / "cps" / "themes" / "caliblur" / "templates" / "stats.html"
CALIBLUR_HTTP_ERROR = ROOT / "cps" / "themes" / "caliblur" / "templates" / "http_error.html"


def source(path):
    return path.read_text(encoding="utf-8")


class TestRussianLocaleDefault(unittest.TestCase):
    def test_register_user_sets_ru_locale(self):
        src = source(WEB_PY)
        match = re.search(
            r'def _register_user\(.*?\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        self.assertIsNotNone(match, "_register_user not found")
        body = match.group(1)
        self.assertIn('content.locale = "ru"', body,
                       "New users must get Russian locale by default")

    def test_invite_registration_does_not_override_locale(self):
        src = source(WEB_PY)
        match = re.search(
            r'def _register_user\(.*?\):(.*?)(?=\n@web\.route|\ndef [a-z])',
            src, re.DOTALL,
        )
        body = match.group(1)
        self.assertNotIn('invite_registration', body.split('content.locale')[1].split('\n')[0],
                         "Locale assignment must not depend on invite_registration")


class TestCalibreBrandingRemoved(unittest.TestCase):
    def test_no_calibre_web_in_about_versions(self):
        src = source(ABOUT_PY)
        self.assertNotIn("Calibre Web", src,
                         "about.py must not reference 'Calibre Web' as version label")

    def test_no_calibre_web_in_email_body(self):
        src = source(HELPER_PY)
        self.assertNotIn("sent via Calibre-Web", src,
                         "helper.py must not reference 'sent via Calibre-Web'")

    def test_no_calibre_web_in_registration_email(self):
        src = source(HELPER_PY)
        self.assertNotIn("Your account at Calibre-Web", src,
                         "helper.py must not reference 'Calibre-Web' in registration email")

    def test_no_calibre_web_in_email_subject(self):
        src = source(HELPER_PY)
        self.assertNotIn("Get Started with Calibre-Web", src,
                         "helper.py must not reference 'Calibre-Web' in email subject")

    def test_no_calibre_web_in_error_handler_realm(self):
        src = source(ERROR_HANDLER_PY)
        self.assertNotIn('realm="calibre-web"', src,
                         "error_handler.py must not use 'calibre-web' realm")

    def test_no_calibre_web_in_osd_description(self):
        src = source(OSD_XML)
        self.assertNotIn("Calibre-Web", src,
                         "osd.xml must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_feed_author_uri(self):
        src = source(FEED_XML)
        self.assertNotIn("janeczku/calibre-web", src,
                         "feed.xml must not reference upstream calibre-web")

    def test_no_calibre_web_in_index_author_uri(self):
        src = source(INDEX_XML)
        self.assertNotIn("janeczku/calibre-web", src,
                         "index.xml must not reference upstream calibre-web")

    def test_no_calibre_web_in_standard_stats(self):
        src = source(STANDARD_STATS)
        self.assertNotIn("Calibre-Web", src,
                         "standard stats.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_standard_http_error(self):
        src = source(STANDARD_HTTP_ERROR)
        self.assertNotIn("Calibre-Web", src,
                         "standard http_error.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_standard_admin_modals(self):
        src = source(STANDARD_ADMIN)
        self.assertNotIn("Calibre-Web", src,
                         "standard admin.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_standard_logviewer(self):
        src = source(STANDARD_LOGVIEWER)
        self.assertNotIn("Calibre-Web", src,
                         "standard logviewer.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_standard_config_edit(self):
        src = source(STANDARD_CONFIG_EDIT)
        self.assertNotIn("Calibre-Web", src,
                         "standard config_edit.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_standard_detail(self):
        src = source(STANDARD_DETAIL)
        self.assertNotIn("Calibre-Web", src,
                         "standard detail.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_caliblur_stats(self):
        src = source(CALIBLUR_STATS)
        self.assertNotIn("Calibre-Web", src,
                         "caliblur stats.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_caliblur_http_error(self):
        src = source(CALIBLUR_HTTP_ERROR)
        self.assertNotIn("Calibre-Web", src,
                         "caliblur http_error.html must not reference 'Calibre-Web'")

    def test_no_calibre_web_in_search_error(self):
        src = source(SEARCH_PY)
        self.assertNotIn("restart Calibre-Web", src,
                         "search.py must not reference 'restart Calibre-Web'")

    def test_config_default_title_is_aubooks(self):
        src = source(CONFIG_SQL_PY)
        self.assertIn("default='AU-Books'", src,
                       "config_calibre_web_title default must be 'AU-Books'")


if __name__ == "__main__":
    unittest.main()
