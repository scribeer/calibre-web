"""Regression tests: AU-Books uses dark theme exclusively.

Verifies that light theme is completely removed from AU-Books UI:
- CSS defaults to dark palette
- No theme selector in layout or admin config
- Inline script always sets data-theme="dark"
- JS has no theme switching logic
- Light palette is not present in CSS
"""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AU_TEMPLATES = ROOT / "cps" / "themes" / "aubooks" / "templates"
AU_CSS = ROOT / "cps" / "static" / "css" / "aubooks.css"
AU_JS = ROOT / "cps" / "static" / "js" / "aubooks-pages.js"
STANDARD_TEMPLATES = ROOT / "cps" / "themes" / "standard" / "templates"


def read(path):
    return path.read_text(encoding="utf-8")


class TestCSSDarkOnly(unittest.TestCase):
    """CSS: dark palette is the :root default, no light palette."""

    def setUp(self):
        self.css = read(AU_CSS)

    def test_root_uses_dark_colors(self):
        self.assertIn("--aubooks-bg: #000000;", self.css)
        self.assertIn("--aubooks-text: #e0e0e0;", self.css)
        self.assertIn("color-scheme: dark;", self.css)

    def test_no_light_palette_in_root(self):
        self.assertNotIn("--aubooks-bg: #f2f2f2;", self.css)
        self.assertNotIn("--aubooks-text: #333333;", self.css)

    def test_no_color_scheme_light(self):
        lines = self.css.split("\n")
        root_block_end = 0
        for i, line in enumerate(lines):
            if line.strip() == "}" and i < 60:
                root_block_end = i
                break
        root_section = "\n".join(lines[:root_block_end])
        self.assertNotIn("color-scheme: light", root_section)

    def test_no_data_theme_dark_variable_override(self):
        self.assertNotIn('[data-theme="dark"] {\n', self.css)

    def test_no_media_prefers_color_scheme_fallback(self):
        self.assertNotIn(":root:not([data-theme])", self.css)

    def test_html_color_scheme_is_dark(self):
        self.assertIn("html {\n  background-color: var(--aubooks-bg);\n  color-scheme: dark;\n}", self.css)


class TestLayoutDarkOnly(unittest.TestCase):
    """Layout template: no theme selector, inline script forces dark."""

    def setUp(self):
        self.layout = read(AU_TEMPLATES / "layout.html")

    def test_no_theme_selector_in_navbar(self):
        self.assertNotIn("aubooks-color-theme", self.layout)
        self.assertNotIn("aubooks-theme-control", self.layout)

    def test_no_system_light_dark_options(self):
        self.assertNotIn('value="system"', self.layout)
        self.assertNotIn('value="light"', self.layout)

    def test_inline_script_sets_dark(self):
        self.assertIn('document.documentElement.setAttribute("data-theme","dark")', self.layout)

    def test_inline_script_has_no_localStorage(self):
        self.assertNotIn("localStorage", self.layout)

    def test_inline_script_has_no_matchMedia(self):
        self.assertNotIn("matchMedia", self.layout)


class TestJavaScriptDarkOnly(unittest.TestCase):
    """JavaScript: no theme switching logic."""

    def setUp(self):
        self.js = read(AU_JS)

    def test_no_theme_switching_functions(self):
        self.assertNotIn("resolveTheme", self.js)
        self.assertNotIn("applyTheme", self.js)
        self.assertNotIn("syncSelect", self.js)
        self.assertNotIn("setTheme", self.js)
        self.assertNotIn("bindSystemListener", self.js)

    def test_no_localStorage_theme(self):
        self.assertNotIn("aubooks-theme", self.js)
        self.assertNotIn("STORAGE_KEY", self.js)

    def test_no_aubooks_color_theme_binding(self):
        self.assertNotIn("aubooks-color-theme", self.js)

    def test_no_cross_tab_sync(self):
        self.assertNotIn('addEventListener("storage"', self.js)

    def test_accessibility_features_preserved(self):
        self.assertIn("aubooksAnnounce", self.js)
        self.assertIn("loadDeferredCovers", self.js)


class TestAdminConfigDarkOnly(unittest.TestCase):
    """Admin config: theme selector replaced with static display."""

    def setUp(self):
        self.config = read(STANDARD_TEMPLATES / "config_view_edit.html")

    def test_no_theme_dropdown(self):
        self.assertNotIn('id="config_theme"', self.config)
        self.assertNotIn("config_theme", self.config.replace('<input type="hidden" name="config_theme" value="3">', ""))

    def test_hidden_theme_field_sends_aubooks(self):
        self.assertIn('<input type="hidden" name="config_theme" value="3">', self.config)

    def test_theme_label_shows_aubooks(self):
        self.assertIn("AU-Books", self.config)


class TestNoLightThemeActivation(unittest.TestCase):
    """Light theme cannot be activated via URL or any mechanism."""

    def test_no_light_data_theme_in_css(self):
        css = read(AU_CSS)
        self.assertNotIn('data-theme="light"', css)

    def test_no_system_data_theme_in_css(self):
        css = read(AU_CSS)
        self.assertNotIn('data-theme="system"', css)


if __name__ == "__main__":
    unittest.main()
