"""Regression tests for the AU-Books registered-user permission policy."""

import json
import unittest
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from flask import Flask, get_flashed_messages, redirect, request, url_for
from jinja2 import DictLoader, Environment
from werkzeug.exceptions import Forbidden, InternalServerError, NotFound


class TestAubooksUserPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cps
        cps.cli_param.gd_path = "/home/feninf/calibre-web-dev-data/gdrive.db"
        from cps import aubooks_permissions, redirect as redirect_helpers, usermanagement, web

        cls.permissions = aubooks_permissions
        cls.redirect_helpers = redirect_helpers
        cls.usermanagement = usermanagement
        cls.web = web
        cls.app = Flask(__name__)
        cls.app.secret_key = "test"
        cls.app.register_blueprint(web.web)

    @staticmethod
    def _user(authenticated, download=False, tts=False, user_id=7, admin=False):
        return SimpleNamespace(
            id=user_id,
            is_authenticated=authenticated,
            role_download=MagicMock(return_value=download),
            role_tts=MagicMock(return_value=tts),
            role_admin=MagicMock(return_value=admin),
        )

    def _login_required(self, user):
        def decorator(func):
            @wraps(func)
            def guarded(*args, **kwargs):
                if user.is_authenticated:
                    return func(*args, **kwargs)
                return redirect(url_for("web.login", next=request.path))
            return guarded
        return decorator

    def _guest_request(self, endpoint, path, *args):
        guest = self._user(False)
        with self.app.test_request_context(path), \
                patch.object(self.web, "current_user", guest), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.usermanagement.config, "config_anonbrowse", 1, create=True), \
                patch.object(self.usermanagement.config, "config_allow_reverse_proxy_header_login", False,
                             create=True), \
                patch.object(self.usermanagement, "login_required", self._login_required(guest)):
            response = endpoint(*args)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlparse(response.location).path, "/login")
        self.assertEqual(parse_qs(urlparse(response.location).query)["next"], [path])

    def test_guest_ebook_download_redirects_to_login(self):
        with patch.object(self.web, "get_download_link") as download:
            self._guest_request(
                self.web.download_link,
                "/download/10/fb2/10.fb2",
                10, "fb2", "10.fb2",
            )
        download.assert_not_called()

    def test_guest_audio_download_redirects_to_login(self):
        with patch("cps.aubooks_audio.get_audio_record") as audio_record:
            self._guest_request(
                self.web.download_audiobook,
                "/books/10/audio/download",
                10,
            )
        audio_record.assert_not_called()

    def test_guest_tts_generate_redirects_to_login(self):
        with patch("cps.aubooks_tts.queue_book") as queue:
            self._guest_request(
                self.web.generate_audio,
                "/books/10/generate-audio",
                10,
            )
        queue.assert_not_called()

    def test_normal_user_can_download_ebook_without_download_role(self):
        user = self._user(True, download=False)
        with self.app.test_request_context("/download/10/fb2/10.fb2"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.usermanagement.config, "config_anonbrowse", 1, create=True), \
                patch.object(self.usermanagement.config, "config_allow_reverse_proxy_header_login", False,
                             create=True), \
                patch.object(self.web, "get_download_link", return_value="ebook"):
            response = self.web.download_link(10, "fb2", "10.fb2")
        self.assertEqual(response, "ebook")
        user.role_download.assert_not_called()

    def test_normal_user_can_generate_tts_without_tts_role(self):
        user = self._user(True, tts=False)
        queue_result = SimpleNamespace(success=True, job_id="job-1", exit_code=0, error_message="")
        with self.app.test_request_context("/books/10/generate-audio", method="POST"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_status", return_value="not_available"), \
                patch("cps.aubooks_tts.queue_book", return_value=queue_result) as queue, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.generate_audio.__wrapped__(10)
        self.assertEqual(response.status_code, 303)
        queue.assert_called_once_with(10, 7)
        user.role_tts.assert_not_called()

    def test_generate_audio_route_matches_real_queue_book_contract(self):
        user = self._user(True, user_id=7)
        response_body = MagicMock()
        response_body.read.return_value = json.dumps(
            {"ok": True, "book_id": 10, "job_id": "JOB-10"}
        ).encode("utf-8")
        response_body.__enter__.return_value = response_body
        with self.app.test_request_context("/books/10/generate-audio", method="POST"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_status", return_value="not_available"), \
                patch("urllib.request.urlopen", return_value=response_body) as open_url, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.generate_audio.__wrapped__(10)
        self.assertEqual(response.status_code, 303)
        request = open_url.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload, {"book_id": 10, "requested_by_user_id": 7})

    def test_cancelled_audio_can_be_regenerated_with_server_owner(self):
        user = self._user(True, user_id=12)
        queue_result = SimpleNamespace(success=True, job_id="job-2", exit_code=0, error_message="")
        with self.app.test_request_context("/books/10/generate-audio", method="POST"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_status", return_value="cancelled"), \
                patch("cps.aubooks_tts.queue_book", return_value=queue_result) as queue, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.generate_audio.__wrapped__(10)
        self.assertEqual(response.status_code, 303)
        queue.assert_called_once_with(10, 12)

    def test_queue_error_detail_is_not_flashed_verbatim(self):
        user = self._user(True)
        queue_result = SimpleNamespace(success=False, job_id="", exit_code=500,
                                       error_message="private dispatcher detail")
        with self.app.test_request_context("/books/10/generate-audio", method="POST"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_status", return_value="not_available"), \
                patch("cps.aubooks_tts.queue_book", return_value=queue_result), \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.generate_audio.__wrapped__(10)
            messages = " ".join(get_flashed_messages())
        self.assertEqual(response.status_code, 303)
        self.assertNotIn("private dispatcher detail", messages)
        self.assertIn("Unable to start audio generation", messages)

    def _download_audio(self, user, visible=True, run_side_effect=None):
        record = {
            "status": "ready",
            "opendrive_path": "Audiobooks/2026/09/test.m4b",
        }

        def successful_run(command, **kwargs):
            Path(command[3]).write_bytes(b"m4b")
            return SimpleNamespace(returncode=0, stderr="")

        with self.app.test_request_context("/books/10/audio/download"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book",
                             return_value=object() if visible else None), \
                patch("cps.aubooks_audio.get_audio_record", return_value=record) as audio_record, \
                patch.object(self.web.subprocess, "run",
                             side_effect=run_side_effect or successful_run):
            response = self.web.download_audiobook.__wrapped__(10)
            messages = get_flashed_messages()
        return response, messages, audio_record

    def test_normal_user_can_download_ready_audio_without_download_role(self):
        user = self._user(True, download=False)
        response, _, _ = self._download_audio(user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        response.close()
        user.role_download.assert_not_called()

    def test_hidden_audio_book_is_404_before_record_lookup(self):
        with self.app.test_request_context("/books/999999/audio/download"), \
                patch.object(self.web, "current_user", self._user(True)), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=None), \
                patch("cps.aubooks_audio.get_audio_record") as audio_record:
            with self.assertRaises(NotFound):
                self.web.download_audiobook.__wrapped__(999999)
            audio_record.assert_not_called()

    def test_audio_download_does_not_flash_internal_exception_details(self):
        user = self._user(True)
        record = {
            "status": "ready",
            "opendrive_path": "Audiobooks/2026/09/test.m4b",
        }
        with self.app.test_request_context("/books/10/audio/download"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 3, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_record", return_value=record), \
                patch.object(self.web.subprocess, "run",
                             side_effect=RuntimeError("/home/private/token")), \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            with self.assertRaises(InternalServerError):
                self.web.download_audiobook.__wrapped__(10)
            messages = " ".join(get_flashed_messages())
        self.assertNotIn("/home/private", messages)
        self.assertIn("Error downloading audio.", messages)

    def test_standard_theme_keeps_ebook_download_role(self):
        user = self._user(True, download=False)
        with self.app.test_request_context("/download/10/fb2/10.fb2"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 0, create=True), \
                patch.object(self.usermanagement.config, "config_anonbrowse", 1, create=True), \
                patch.object(self.usermanagement.config, "config_allow_reverse_proxy_header_login", False,
                             create=True), \
                patch.object(self.web, "get_download_link") as download:
            with self.assertRaises(Forbidden):
                self.web.download_link(10, "fb2", "10.fb2")
        user.role_download.assert_called_once_with()
        download.assert_not_called()

    def test_standard_theme_keeps_audio_download_role(self):
        user = self._user(True, download=False)
        with self.app.test_request_context("/books/10/audio/download"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 0, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book") as visible:
            with self.assertRaises(Forbidden):
                self.web.download_audiobook.__wrapped__(10)
        user.role_download.assert_called_once_with()
        visible.assert_not_called()

    def test_standard_theme_keeps_tts_role(self):
        user = self._user(True, tts=False)
        with self.app.test_request_context("/books/10/generate-audio", method="POST"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.permissions.config, "config_theme", 0, create=True), \
                patch.object(self.web.calibre_db, "get_filtered_book") as visible:
            with self.assertRaises(Forbidden):
                self.web.generate_audio.__wrapped__(10)
        user.role_tts.assert_called_once_with()
        visible.assert_not_called()


class TestSafeNextAndAubooksTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cps import redirect as redirect_helpers, web
        cls.redirect_helpers = redirect_helpers
        cls.app = Flask(__name__)
        cls.app.register_blueprint(web.web)

    def test_internal_next_is_preserved(self):
        with self.app.test_request_context("/login?next=/book/10"):
            self.assertEqual(
                self.redirect_helpers.get_redirect_location("/book/10", "web.index"),
                "/book/10",
            )

    def test_external_next_is_rejected(self):
        with self.app.test_request_context("/login?next=https://evil.example/book/10"):
            self.assertEqual(
                self.redirect_helpers.get_redirect_location("https://evil.example/book/10", "web.index"),
                "/",
            )

    def test_protocol_relative_next_is_rejected(self):
        with self.app.test_request_context("/login?next=//evil.example/book/10"):
            self.assertEqual(
                self.redirect_helpers.get_redirect_location("//evil.example/book/10", "web.index"),
                "/",
            )

    def test_post_only_next_is_rejected(self):
        with self.app.test_request_context("/login?next=/books/10/generate-audio"):
            self.assertEqual(
                self.redirect_helpers.get_redirect_location(
                    "/books/10/generate-audio", "web.index"
                ),
                "/",
            )

    def test_guest_detail_controls_and_login_registration_link(self):
        root = Path(__file__).parent.parent / "cps" / "themes"
        detail = (root / "aubooks" / "templates" / "detail.html").read_text()
        login = (root / "aubooks" / "templates" / "login.html").read_text()
        self.assertIn("Скачать книгу", detail)
        self.assertIn("Generate audio", detail)
        self.assertIn("aubooks_login_url", detail)
        self.assertIn("Don\\'t have an account? Register", login)
        self.assertIn("config.config_public_reg", login)

    def test_guest_polling_transitions_keep_login_actions(self):
        detail = (Path(__file__).parent.parent / "cps" / "themes" / "aubooks" /
                  "templates" / "detail.html").read_text()
        self.assertIn('data-login-url="{{ aubooks_login_url }}"', detail)
        self.assertEqual(detail.count("appendLoginLink("), 5)
        self.assertIn("'{{ _(\"Скачать аудиокнигу\") }}'", detail)
        self.assertIn("'{{ _(\"Озвучить повторно\") }}'", detail)
        self.assertIn("'{{ _(\"Озвучить\") }}'", detail)

    def test_registration_link_is_rendered_only_when_enabled(self):
        source = (Path(__file__).parent.parent / "cps" / "themes" / "aubooks" /
                  "templates" / "login.html").read_text()
        env = Environment(loader=DictLoader({
            "login.html": source,
            "layout.html": "{% block body %}{% endblock %}",
        }))
        env.globals.update(
            theme=lambda name: "layout.html",
            url_for=lambda endpoint: "/register",
            csrf_token=lambda: "token",
            _=lambda message: message,
        )
        context = {
            "next_url": "/",
            "username": "",
            "error": None,
            "mail": False,
            "oauth_check": {},
        }
        enabled = SimpleNamespace(
            config_public_reg=True, config_login_type=0, config_remote_login=False
        )
        disabled = SimpleNamespace(
            config_public_reg=False, config_login_type=0, config_remote_login=False
        )
        self.assertIn("Don't have an account? Register",
                      env.get_template("login.html").render(config=enabled, **context))
        self.assertNotIn("Don't have an account? Register",
                         env.get_template("login.html").render(config=disabled, **context))

    def test_standard_theme_is_untouched_by_aubooks_controls(self):
        root = Path(__file__).parent.parent / "cps" / "themes" / "standard" / "templates"
        self.assertNotIn("aubooks_login_url", (root / "detail.html").read_text())
        self.assertNotIn("Don't have an account? Register", (root / "login.html").read_text())


if __name__ == "__main__":
    unittest.main()
