"""Rendered regressions for genres in the shared AU-Books book card."""

import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "cps" / "themes" / "aubooks" / "templates"
CSS = ROOT / "cps" / "static" / "css" / "aubooks.css"


class CardEntry:
    def __init__(self, book):
        self.Books = book

    def __getitem__(self, index):
        if index == 2:
            return False
        raise IndexError(index)


class TestAubooksBookCardGenres(unittest.TestCase):
    def setUp(self):
        self.genre_urls = {1: "/genre/fantastika", 2: "/genre/priklyucheniya", 3: "/genre/kosmos"}
        self.genre_calls = []
        environment = Environment(
            loader=FileSystemLoader(str(TEMPLATES)),
            autoescape=select_autoescape(("html",)),
        )
        environment.globals["_"] = lambda value: value
        environment.globals["url_for"] = self.url_for
        environment.filters["clean_string"] = lambda value: value
        environment.filters["formatfloat"] = lambda value, _digits: str(value)
        environment.filters["music"] = lambda _value: False
        self.card = environment.get_template("_book_card.html").module.book_card

    def url_for(self, endpoint, **values):
        if endpoint == "web.show_book":
            return "/book/{}".format(values["book_id"])
        if endpoint == "web.books_list" and values.get("data") == "author":
            return "/author/author"
        if endpoint == "web.books_list" and values.get("data") == "series":
            return "/series/series"
        if endpoint == "web.books_list" and values.get("data") == "category":
            self.genre_calls.append(values)
            return self.genre_urls[values["book_id"]]
        raise AssertionError((endpoint, values))

    def render(self, tags):
        book = SimpleNamespace(
            id=42,
            title="Unsafe <Title>",
            authors=[SimpleNamespace(id=7, name="Author & Writer")],
            series=[SimpleNamespace(id=8, name="Series <One>")],
            series_index=2,
            tags=tags,
            ratings=[],
            data=[],
            comments=[SimpleNamespace(text="Description & <em>details</em>")],
        )
        return str(self.card(CardEntry(book), show_annotation=True))

    def test_one_genre_renders_one_canonical_link(self):
        html = self.render([SimpleNamespace(id=1, name="Фантастика")])

        self.assertIn('<p class="genre"><span class="aubooks-meta-label">Жанр:</span>', html)
        self.assertIn('<a href="/genre/fantastika">Фантастика</a>', html)
        self.assertNotIn("/genre/stored/", html)
        self.assertEqual(self.genre_calls, [{
            "data": "category", "sort_param": "stored", "book_id": 1,
        }])

    def test_multiple_genres_share_one_comma_separated_row(self):
        html = self.render([
            SimpleNamespace(id=1, name="Фантастика"),
            SimpleNamespace(id=2, name="Приключения"),
            SimpleNamespace(id=3, name="Космическая фантастика"),
        ])

        self.assertEqual(html.count('<p class="genre">'), 1)
        self.assertIn(
            '<a href="/genre/fantastika">Фантастика</a><span>, </span>'
            '<a href="/genre/priklyucheniya">Приключения</a><span>, </span>'
            '<a href="/genre/kosmos">Космическая фантастика</a>',
            html,
        )
        self.assertNotIn("/genre/stored/", html)

    def test_no_genres_omits_genre_row_and_preserves_existing_content(self):
        html = self.render([])

        self.assertNotIn('<p class="genre">', html)
        self.assertNotIn("Жанр:", html)
        self.assertIn('<p class="author">', html)
        self.assertIn('<p class="series">', html)
        self.assertIn("Series &lt;One&gt;", html)
        self.assertIn('<div class="aubooks-book-annotation">Description &amp; details</div>', html)
        self.assertIn("Unsafe &lt;Title&gt;", html)

    def test_shared_card_and_mobile_wrapping_remain_available(self):
        for template_name in ("index.html", "author.html", "search.html"):
            template = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn("book_card", template, template_name)

        css = CSS.read_text(encoding="utf-8")
        self.assertIn(".aubooks-catalog-book .genre,", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertNotIn(".aubooks-catalog-book .genre {\n  white-space: nowrap", css)


if __name__ == "__main__":
    unittest.main()
