"""Focused admin authorization tests for AU-Books TTS cancellation."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask, get_flashed_messages
from werkzeug.exceptions import Forbidden, Unauthorized


class TestCancelAudioJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cps
        cps.cli_param.gd_path = "/home/feninf/calibre-web-dev-data/gdrive.db"
        from cps import tasks_status, web
        cls.web = web
        cls.app = Flask(__name__)
        cls.app.secret_key = "test"
        cls.app.register_blueprint(web.web)
        cls.app.register_blueprint(tasks_status.tasks)

    @staticmethod
    def _user(admin=False):
        return SimpleNamespace(id=7, is_authenticated=True,
                               role_admin=MagicMock(return_value=admin))

    @staticmethod
    def _record(status="queued", job_id="job-1"):
        return {"book_id": 10, "job_id": job_id, "status": status}

    def _cancel(self, user, record, result=None):
        result = result or SimpleNamespace(
            success=True, exit_code=0, error_message="", status="cancelled")
        with self.app.test_request_context(
                "/audio/cancel/10", method="POST", data={"job_id": record.get("job_id", "")}), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_record", return_value=record), \
                patch("cps.aubooks_tts.cancel_job", return_value=result) as cancel, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.cancel_audio_job.__wrapped__(10)
            messages = get_flashed_messages()
        return response, messages, cancel

    def test_admin_cancels_trusted_active_job(self):
        for status in ("queued", "processing"):
            with self.subTest(status=status):
                response, messages, cancel = self._cancel(
                    self._user(admin=True), self._record(status=status))
                self.assertEqual(response.status_code, 303)
                self.assertIn("Озвучивание отменено.", messages)
                cancel.assert_called_once_with(10, "job-1")

    def test_normal_user_cannot_cancel(self):
        with self.assertRaises(Forbidden):
            self._cancel(self._user(admin=False), self._record())

    def test_anonymous_request_is_rejected_before_route(self):
        from cps import usermanagement

        def reject_anonymous(_view):
            def rejected(*_args, **_kwargs):
                raise Unauthorized()
            return rejected

        with self.app.test_request_context("/audio/cancel/10", method="POST"), \
                patch.object(usermanagement.config,
                             "config_allow_reverse_proxy_header_login", False, create=True), \
                patch.object(usermanagement, "login_required", side_effect=reject_anonymous), \
                patch.object(self.web.calibre_db, "get_filtered_book") as book_lookup:
            with self.assertRaises(Unauthorized):
                self.web.cancel_audio_job(10)
        book_lookup.assert_not_called()

    def test_ready_and_conflict_are_controlled(self):
        _, messages, cancel = self._cancel(self._user(admin=True), self._record(status="ready"))
        self.assertIn("Аудиокнига уже готова", messages)
        cancel.assert_not_called()

        conflict = SimpleNamespace(success=False, exit_code=409,
                                   error_message="private", status="stale_job")
        _, messages, cancel = self._cancel(
            self._user(admin=True), self._record(status="processing"), conflict)
        self.assertIn("Задание изменилось. Обновите страницу.", messages)
        cancel.assert_called_once_with(10, "job-1")

    def test_stale_form_does_not_cancel_replacement_job(self):
        with self.app.test_request_context(
                "/audio/cancel/10", method="POST", data={"job_id": "old-job"}), \
                patch.object(self.web, "current_user", self._user(admin=True)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_record",
                      return_value=self._record(status="processing", job_id="new-job")), \
                patch("cps.aubooks_tts.cancel_job") as cancel, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.cancel_audio_job.__wrapped__(10)
            messages = get_flashed_messages()
        self.assertEqual(response.status_code, 303)
        self.assertIn("Задание изменилось. Обновите страницу.", messages)
        cancel.assert_not_called()

    def test_dispatcher_error_is_safe(self):
        unavailable = SimpleNamespace(success=False, exit_code=1,
                                      error_message="secret detail", status="unavailable")
        _, messages, _ = self._cancel(self._user(admin=True), self._record(), unavailable)
        rendered = " ".join(messages)
        self.assertIn("Не удалось отменить озвучивание", rendered)
        self.assertNotIn("secret detail", rendered)

    def test_route_is_post_only_and_login_required(self):
        rule = next(rule for rule in self.app.url_map.iter_rules()
                    if rule.endpoint == "web.cancel_audio_job")
        self.assertEqual(rule.methods & {"GET", "POST"}, {"POST"})
        self.assertTrue(hasattr(self.web.cancel_audio_job, "__wrapped__"))

    def test_global_csrf_rejects_missing_token(self):
        try:
            from flask_wtf.csrf import CSRFProtect
        except ImportError:
            self.skipTest("flask-wtf is unavailable")
        app = Flask(__name__)
        app.secret_key = "csrf-test"
        app.config["WTF_CSRF_ENABLED"] = True
        app.register_blueprint(self.web.web)
        CSRFProtect(app)
        response = app.test_client().post("/audio/cancel/10")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
