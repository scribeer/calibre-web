"""Focused regressions for AU-Books-only presentation behavior."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AU_TEMPLATES = ROOT / "cps" / "themes" / "aubooks" / "templates"
STANDARD_TEMPLATES = ROOT / "cps" / "themes" / "standard" / "templates"
AU_CSS = ROOT / "cps" / "static" / "css" / "aubooks.css"


def source(path):
    return path.read_text(encoding="utf-8")


class TestAubooksDetailActions(unittest.TestCase):
    def test_download_and_audio_share_action_row(self):
        template = source(AU_TEMPLATES / "detail.html")
        start = template.index('<div class="btn-toolbar aubooks-detail-actions"')
        end = template.index('<div class="more-stuff">', start)
        actions = template[start:end]

        self.assertIn('class="aubooks-detail-action-row"', actions)
        self.assertIn('id="Download"', actions)
        self.assertIn('id="aubooks-audio-status"', actions)

        css = source(AU_CSS)
        self.assertIn(".aubooks-detail-action-row", css)
        self.assertIn("flex-wrap: wrap", css)

    def test_ebook_reader_action_is_hidden_only_in_au_theme(self):
        aubooks = source(AU_TEMPLATES / "detail.html")
        standard = source(STANDARD_TEMPLATES / "detail.html")

        self.assertNotIn("entry.reader_list", aubooks)
        self.assertNotIn('id="read-in-browser"', aubooks)
        self.assertNotIn('id="readbtn"', aubooks)
        self.assertIn("entry.reader_list", standard)
        self.assertIn('id="read-in-browser"', standard)
        self.assertIn('id="readbtn"', standard)


class TestAubooksShelfPresentation(unittest.TestCase):
    def test_shelf_appears_before_genre_navigation(self):
        layout = source(AU_TEMPLATES / "layout.html")
        shelf_pos = layout.index("public-shelves")
        genre_pos = layout.index("Все жанры")
        self.assertLess(shelf_pos, genre_pos)

    def test_shelf_appears_exactly_once(self):
        layout = source(AU_TEMPLATES / "layout.html")
        self.assertEqual(layout.count("public-shelves"), 1)

    def test_standard_fallback_keeps_cover_markup(self):
        shelf = source(STANDARD_TEMPLATES / "shelf.html")
        self.assertIn('<div class="cover">', shelf)
        self.assertIn("image.book_cover(entry.Books)", shelf)
        self.assertIn('class="title"', shelf)

    def test_au_css_shows_shelf_covers_and_uses_link_palette(self):
        css = source(AU_CSS)
        self.assertIn("body.shelf .display-flex .book .cover", css)
        self.assertIn("body.shelf .book .meta .title", css)
        self.assertIn("color: var(--aubooks-link)", css)
        self.assertIn("color: var(--aubooks-link-hover)", css)


class TestAubooksSidebarAndColors(unittest.TestCase):
    def test_sidebar_has_genre_navigation_without_category_heading(self):
        layout = source(AU_TEMPLATES / "layout.html")
        self.assertNotIn("aubooks-sidebar-genres-heading", layout)
        self.assertNotIn("Категория", layout)
        self.assertNotIn("Категории", layout)
        self.assertIn("Все жанры", layout)
        self.assertIn("aubooks-sidebar-genres", layout)

    def test_visible_genre_terminology_is_consistent(self):
        for name in ("layout.html", "list.html", "index.html", "detail.html"):
            template = source(AU_TEMPLATES / name)
            self.assertNotIn("Категория", template, name)
            self.assertNotIn("Категории", template, name)
        self.assertIn("Жанры", source(AU_TEMPLATES / "list.html"))
        self.assertIn("Жанры", source(AU_TEMPLATES / "index.html"))
        self.assertIn("Жанры", source(AU_TEMPLATES / "detail.html"))

    def test_dark_muted_palette_is_light_and_disabled_is_separate(self):
        css = source(AU_CSS)
        self.assertIn("--aubooks-text-muted: #b8b8b8", css)
        self.assertIn("--aubooks-text-subtle: #9c9c9c", css)
        self.assertIn("--aubooks-disabled-text: #777777", css)
        self.assertIn("color: var(--aubooks-disabled-text)", css)


if __name__ == "__main__":
    unittest.main()
