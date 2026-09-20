"""Focused regressions for the public /help page and its sidebar entry."""

import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from flask_wtf.csrf import CSRFProtect, generate_csrf

import cps
from cps import ub
from cps.cw_login import AnonymousUserMixin


ROOT = Path(__file__).resolve().parent.parent
AU_TEMPLATES = ROOT / "cps" / "themes" / "aubooks" / "templates"
AU_CSS = ROOT / "cps" / "static" / "css" / "aubooks.css"


def source(name):
    return (AU_TEMPLATES / name).read_text(encoding="utf-8")


class TestAubooksHelpPageHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cps.cli_param.gd_path = ":memory:"
        from cps import web

        cls.web_module = web

    def setUp(self):
        self.config = type("TestConfig", (), {
            "config_theme": 3,
        })()

        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="help-page-test",
            TESTING=True,
            WTF_CSRF_ENABLED=True,
            RATELIMIT_ENABLED=False,
        )
        CSRFProtect(self.app)
        self.app.add_url_rule("/csrf", "csrf", lambda: generate_csrf())

        self.old_user_callback = cps.lm._user_callback
        self.old_request_callback = cps.lm._request_callback
        self.old_anonymous_user = cps.lm.anonymous_user
        self.old_session_protection = cps.lm.session_protection
        cps.lm.init_app(self.app)
        cps.lm.anonymous_user = AnonymousUserMixin
        cps.lm.session_protection = None
        cps.lm._user_callback = None
        cps.lm._request_callback = lambda req: None

        self.rendered = []
        self.theme = {"active": "aubooks"}

        def gettext(value, **kwargs):
            return value % kwargs if kwargs else value

        def render_template(template, **_context):
            self.rendered.append((template, _context))
            if template == "help.html":
                return "<h1>Помощь по сайту</h1>"
            return "some page"

        self.patchers = [
            patch.object(self.web_module, "config", self.config),
            patch.object(self.web_module, "get_active_theme_identifier",
                         side_effect=lambda: self.theme["active"]),
            patch.object(self.web_module, "_", side_effect=gettext),
            patch.object(self.web_module, "render_title_template",
                         side_effect=render_template),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.app.register_blueprint(self.web_module.web)
        self.client = self.app.test_client()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        cps.lm._user_callback = self.old_user_callback
        cps.lm._request_callback = self.old_request_callback
        cps.lm.anonymous_user = self.old_anonymous_user
        cps.lm.session_protection = self.old_session_protection

    def test_help_returns_200_without_redirect(self):
        response = self.client.get("/help")
        self.assertEqual(response.status_code, 200)

    def test_help_is_public_not_redirected_to_login(self):
        response = self.client.get("/help")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.status_code, 302)
        self.assertNotIn("/login", response.get_data(as_text=True).lower())

    def test_help_renders_au_template_with_page_setting(self):
        response = self.client.get("/help")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>Помощь по сайту</h1>", response.get_data(as_text=True))
        templates = [name for name, _context in self.rendered]
        self.assertIn("help.html", templates)
        found = next((_context for _name, _context in self.rendered if _name == "help.html"), {})
        self.assertEqual(found.get("page"), "help")
        self.assertEqual(found.get("title"), "Помощь по сайту")

    def test_help_aborts_for_non_au_theme(self):
        self.theme["active"] = "standard"
        response = self.client.get("/help")
        self.assertEqual(response.status_code, 404)


class TestAubooksHelpTemplate(unittest.TestCase):
    def test_has_single_h1_with_exact_title(self):
        html = source("help.html")
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('<h1 class="aubooks-page-title">Помощь по сайту</h1>', html)

    def test_has_all_sections(self):
        html = source("help.html")
        for heading in (
            "Регистрация",
            "Вход на сайт",
            "Если забыли пароль",
            "Изменить пароль",
            "Изменить адрес электронной почты",
            "Найти книгу",
            "Расширенный поиск",
            "Найти книгу по жанру",
            "Скачать электронную книгу",
            "Озвучить книгу",
            "Проверить состояние озвучивания",
            "Скачать готовую аудиокнигу",
            "Прослушать книгу в браузере",
            "Создать книжную полку",
            "Выйти с сайта",
        ):
            self.assertIn("<h2>{}</h2>".format(heading), html, heading)

    def test_uses_semantic_lists(self):
        html = source("help.html")
        self.assertIn("<ol>", html)
        self.assertIn("</ol>", html)
        self.assertIn("<ul>", html)
        self.assertIn("</ul>", html)
        self.assertGreaterEqual(html.count("<li>"), 30)

    def test_verbatim_quoted_phrases(self):
        html = source("help.html")
        for phrase in (
            "«Имя пользователя»",
            "«Адрес электронной почты»",
            "«Подтвердите пароль»",
            "«Забыли пароль ?»",
            "«Поиск в библиотеке»",
            "«Расширенный поиск»",
            "«Озвучить повторно»",
            "«В очереди» — книга ожидает озвучивания.",
            "«Задания»",
            "«Добавить на книжную полку»",
            "«Прослушать в браузере»",
        ):
            self.assertIn(phrase, html, phrase)

    def test_help_css_exists(self):
        css = AU_CSS.read_text(encoding="utf-8")
        self.assertIn(".aubooks-help", css)
        self.assertIn("max-width: 68ch", css)


class TestAubooksSidebarHelpEntry(unittest.TestCase):
    def test_sidebar_has_help_link(self):
        layout = source("layout.html")
        self.assertIn("Помощь</a>", layout)
        self.assertIn('href="{{url_for(\'web.help_page\')}}"', layout)

    def test_help_is_first_sidebar_item(self):
        layout = source("layout.html")
        scnd = layout.index('id="scnd-nav"')
        help_pos = layout.index('id="nav_help"')
        self.assertLess(scnd, help_pos, "help must be inside #scnd-nav")
        for marker in (
            "public-shelves",
            "nav_createshelf",
            "Все жанры",
            'id="nav_cat"',
        ):
            pos = layout.index(marker)
            self.assertLess(help_pos, pos, "Помощь must precede {}".format(marker))

    def test_help_item_has_question_icon(self):
        layout = source("layout.html")
        item = layout[layout.index('id="nav_help"'):]
        item = item[:item.index("</li>") + len("</li>")]
        self.assertIn("glyphicon-question-sign", item)

    def test_help_item_active_state(self):
        layout = source("layout.html")
        self.assertIn("{% if page == 'help' %} class=\"active\"", layout)
        self.assertIn("aria-current=\"page\"", layout)

    def test_other_sidebar_order_unchanged(self):
        layout = source("layout.html")
        self.assertLess(layout.index("public-shelves"), layout.index("nav_createshelf"))
        self.assertLess(layout.index("nav_createshelf"), layout.index("Все жанры"))


if __name__ == "__main__":
    unittest.main()