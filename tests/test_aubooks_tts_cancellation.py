"""Focused authorization tests for AU-Books TTS cancellation."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask, get_flashed_messages
from werkzeug.exceptions import Conflict, Forbidden, NotFound


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
    def _user(user_id=7, admin=False, tts=True):
        return SimpleNamespace(
            id=user_id,
            is_authenticated=True,
            role_admin=MagicMock(return_value=admin),
            role_tts=MagicMock(return_value=tts),
        )

    def _cancel(self, user, record, visible=True):
        result = SimpleNamespace(success=True, exit_code=0, error_message="", status="cancelled")
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-1/cancel", method="POST"), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.web.calibre_db, "get_filtered_book",
                             return_value=object() if visible else None) as filtered, \
                patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                patch("cps.aubooks_audio.get_audio_record", return_value=record) as audio_record, \
                patch("cps.aubooks_tts.cancel_job", return_value=result) as cancel, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.cancel_audio_job.__wrapped__(10, "job-1")
        return response, filtered, audio_record, cancel

    @staticmethod
    def _record(owner=7, status="queued", job_id="job-1"):
        return {
            "book_id": 10,
            "job_id": job_id,
            "requested_by_user_id": owner,
            "status": status,
        }

    def test_owner_can_cancel_exact_active_job(self):
        response, _, _, cancel = self._cancel(self._user(), self._record())
        self.assertEqual(response.status_code, 303)
        cancel.assert_called_once_with("job-1")

    def test_admin_can_cancel_other_users_and_legacy_jobs(self):
        for owner in (99, None):
            with self.subTest(owner=owner):
                _, _, _, cancel = self._cancel(self._user(admin=True), self._record(owner=owner))
                cancel.assert_called_once_with("job-1")

    def test_other_user_and_legacy_owner_are_forbidden(self):
        for owner in (99, None):
            with self.subTest(owner=owner), self.assertRaises(Forbidden):
                self._cancel(self._user(), self._record(owner=owner))

    def test_hidden_book_is_404_before_audio_lookup(self):
        with self.assertRaises(NotFound) as raised:
            self._cancel(self._user(admin=True), self._record(), visible=False)
        self.assertEqual(raised.exception.code, 404)
        # _cancel exits before returning, so verify ordering independently.
        with self.app.test_request_context("/books/10/audio/jobs/job-1/cancel", method="POST"), \
                patch.object(self.web, "current_user", self._user(admin=True)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=None), \
                patch("cps.aubooks_audio.get_audio_record") as audio_record:
            with self.assertRaises(NotFound):
                self.web.cancel_audio_job.__wrapped__(10, "job-1")
            audio_record.assert_not_called()

    def test_untrusted_or_finished_job_is_not_cancelled(self):
        with self.assertRaises(NotFound):
            self._cancel(self._user(admin=True), self._record(job_id="other"))
        with self.assertRaises(Conflict):
            self._cancel(self._user(admin=True), self._record(status="ready"))

    def test_stale_job_and_terminal_status_never_reach_dispatcher(self):
        cases = ((self._record(job_id="stale"), NotFound),
                 (self._record(status="cancelled"), Conflict))
        for record, error in cases:
            with self.subTest(error=error.__name__), \
                    self.app.test_request_context(
                        "/books/10/audio/jobs/job-1/cancel", method="POST"), \
                    patch.object(self.web, "current_user", self._user()), \
                    patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                    patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                    patch("cps.aubooks_audio.get_audio_record", return_value=record), \
                    patch("cps.aubooks_tts.cancel_job") as cancel:
                with self.assertRaises(error):
                    self.web.cancel_audio_job.__wrapped__(10, "job-1")
                cancel.assert_not_called()

    def test_owner_is_authorized_before_status_is_disclosed(self):
        with self.assertRaises(Forbidden):
            self._cancel(self._user(), self._record(owner=99, status="ready"))

    def test_standard_theme_tts_permission_is_required_even_for_admin(self):
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-1/cancel", method="POST"), \
                patch.object(self.web, "current_user", self._user(admin=True, tts=False)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_permissions.config.config_theme", 0, create=True), \
                patch("cps.aubooks_audio.get_audio_record") as audio_record, \
                patch("cps.aubooks_tts.cancel_job") as cancel:
            with self.assertRaises(Forbidden):
                self.web.cancel_audio_job.__wrapped__(10, "job-1")
            audio_record.assert_not_called()
            cancel.assert_not_called()

    def test_route_is_post_login_required_and_uses_global_csrf(self):
        rules = [rule for rule in self.app.url_map.iter_rules()
                 if rule.endpoint == "web.cancel_audio_job"]
        self.assertEqual(rules[0].methods & {"GET", "POST"}, {"POST"})
        self.assertTrue(hasattr(self.web.cancel_audio_job, "__wrapped__"))
        source = Path(self.web.__file__).read_text()
        start = source.index("def cancel_audio_job")
        self.assertNotIn("csrf.exempt", source[start - 300:start + 100])

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
        response = app.test_client().post("/books/10/audio/jobs/job-1/cancel")
        self.assertEqual(response.status_code, 400)

    def test_request_cannot_spoof_owner(self):
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-1/cancel", method="POST",
                data={"requested_by_user_id": "7"}), \
                patch.object(self.web, "current_user", self._user(user_id=7)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_audio.get_audio_record",
                      return_value=self._record(owner=99)), \
                patch("cps.aubooks_tts.cancel_job") as cancel:
            with self.assertRaises(Forbidden):
                self.web.cancel_audio_job.__wrapped__(10, "job-1")
            cancel.assert_not_called()

    def test_dispatcher_error_is_logged_but_not_flashed_verbatim(self):
        result = SimpleNamespace(success=False, exit_code=500,
                                 error_message="private dispatcher detail", status="")
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-1/cancel", method="POST"), \
                patch.object(self.web, "current_user", self._user()), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                patch("cps.aubooks_audio.get_audio_record", return_value=self._record()), \
                patch("cps.aubooks_tts.cancel_job", return_value=result), \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.cancel_audio_job.__wrapped__(10, "job-1")
            messages = " ".join(get_flashed_messages())
        self.assertEqual(response.status_code, 303)
        self.assertNotIn("private dispatcher detail", messages)
        self.assertIn("Unable to cancel audio generation", messages)

    def _ajax_request(self, user, record, result):
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-1/cancel", method="POST",
                headers={"X-Requested-With": "XMLHttpRequest"}), \
                patch.object(self.web, "current_user", user), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                patch("cps.aubooks_audio.get_audio_record", return_value=record), \
                patch("cps.aubooks_tts.cancel_job", return_value=result) as cancel, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            response = self.web.cancel_audio_job.__wrapped__(10, "job-1")
        return response, cancel

    def test_ajax_cancel_returns_json_without_page_redirect(self):
        result = SimpleNamespace(success=True, exit_code=0, error_message="", status="cancelled")
        response, cancel = self._ajax_request(self._user(), self._record(), result)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True, "status": "cancelled"})
        cancel.assert_called_once_with("job-1")

    def test_ajax_cancel_failure_returns_json_400_with_safe_message(self):
        result = SimpleNamespace(success=False, exit_code=500,
                                 error_message="private dispatcher detail", status="")
        response, cancel = self._ajax_request(self._user(), self._record(), result)
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertNotIn("private dispatcher detail", str(payload))
        self.assertIn("Unable to cancel audio generation", payload["message"])

    def test_stale_cancel_after_replacement_never_touches_new_job(self):
        # A created job-X; it was cancelled, then B requeued -> job-Y owned by B (id 12).
        # A holds a stale page and POSTs cancel with the old job-X.
        # The server compares against the trusted DB row (job-Y) and refuses.
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-X/cancel", method="POST"), \
                patch.object(self.web, "current_user", self._user(user_id=7)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                patch("cps.aubooks_audio.get_audio_record",
                      return_value=self._record(owner=12, status="processing", job_id="job-Y")), \
                patch("cps.aubooks_tts.cancel_job") as cancel:
            with self.assertRaises(NotFound):
                self.web.cancel_audio_job.__wrapped__(10, "job-X")
            cancel.assert_not_called()

        # Even with the correct new URL, old owner A (id 7) is forbidden for B's job.
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-Y/cancel", method="POST"), \
                patch.object(self.web, "current_user", self._user(user_id=7)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                patch("cps.aubooks_audio.get_audio_record",
                      return_value=self._record(owner=12, status="processing", job_id="job-Y")), \
                patch("cps.aubooks_tts.cancel_job") as cancel:
            with self.assertRaises(Forbidden):
                self.web.cancel_audio_job.__wrapped__(10, "job-Y")
            cancel.assert_not_called()

        # Admin may cancel the replacement job.
        admin_result = SimpleNamespace(success=True, exit_code=0, error_message="", status="cancelled")
        with self.app.test_request_context(
                "/books/10/audio/jobs/job-Y/cancel", method="POST"), \
                patch.object(self.web, "current_user", self._user(admin=True)), \
                patch.object(self.web.calibre_db, "get_filtered_book", return_value=object()), \
                patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                patch("cps.aubooks_audio.get_audio_record",
                      return_value=self._record(owner=12, status="processing", job_id="job-Y")), \
                patch("cps.aubooks_tts.cancel_job", return_value=admin_result) as cancel, \
                patch.object(self.web, "_", side_effect=lambda message, **kwargs: message):
            self.web.cancel_audio_job.__wrapped__(10, "job-Y")
            cancel.assert_called_once_with("job-Y")


if __name__ == "__main__":
    unittest.main()
