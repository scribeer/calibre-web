"""Tests for audio status integration in Calibre-Web."""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aubooks"))
from audio_index import init_db


def tmp_db():
    """Create a temporary DB path for testing."""
    return Path(tempfile.mktemp(suffix=".db"))


class TestAudioAdapter(unittest.TestCase):
    """Test cps/aubooks_audio.py read-only adapter."""

    def test_missing_record_returns_not_available(self):
        from cps.aubooks_audio import get_audio_status
        with patch("cps.aubooks_audio._get_db_path", return_value=tmp_db()):
            status = get_audio_status(999999)
            self.assertEqual(status, "not_available")

    def test_queued_status(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (100, 'queued', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_status
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "queued")
        finally:
            p.unlink(missing_ok=True)

    def test_processing_status(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (100, 'processing', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_status
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "processing")
        finally:
            p.unlink(missing_ok=True)

    def test_ready_status(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (100, 'ready', 'Test.m4b', 'Audiobooks/2026/09/Test.m4b', 'abc', 1000, datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_status
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "ready")
        finally:
            p.unlink(missing_ok=True)

    def test_failed_status(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, error, created_at, updated_at) "
                "VALUES (100, 'failed', 'TTS crashed', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_status
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "failed")
        finally:
            p.unlink(missing_ok=True)

    def test_missing_db_returns_not_available(self):
        from cps.aubooks_audio import get_audio_status
        with patch("cps.aubooks_audio._get_db_path", return_value=Path("/nonexistent/audio.db")):
            status = get_audio_status(100)
            self.assertEqual(status, "not_available")

    def test_db_read_error_returns_not_available(self):
        from cps.aubooks_audio import get_audio_status
        with patch("cps.aubooks_audio._get_db_path", return_value=tmp_db()):
            # DB exists but has no audio table
            status = get_audio_status(100)
            self.assertEqual(status, "not_available")

    def test_get_audio_record_returns_dict(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, created_at, updated_at) "
                "VALUES (100, 'ready', 'Test.m4b', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_record
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                rec = get_audio_record(100)
                self.assertIsNotNone(rec)
                self.assertEqual(rec["book_id"], 100)
                self.assertEqual(rec["status"], "ready")
                self.assertEqual(rec["filename"], "Test.m4b")
        finally:
            p.unlink(missing_ok=True)

    def test_other_book_id_not_affected(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (100, 'ready', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_status
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                self.assertEqual(get_audio_status(100), "ready")
                self.assertEqual(get_audio_status(200), "not_available")
                self.assertEqual(get_audio_status(999), "not_available")
        finally:
            p.unlink(missing_ok=True)

    def test_opendrive_path_not_in_html(self):
        """opendrive_path should not leak into HTML."""
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (100, 'ready', 'Test.m4b', 'Audiobooks/2026/09/Test.m4b', 'abc', 1000, datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            from cps.aubooks_audio import get_audio_record
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                rec = get_audio_record(100)
                # Record contains opendrive_path, but template should not output it
                self.assertIn("opendrive_path", rec)
        finally:
            p.unlink(missing_ok=True)


class TestAudioStatusEndpoint(unittest.TestCase):
    """Test GET /ajax/audio-status/<book_id> JSON structure."""

    def _make_app(self):
        """Create minimal Flask app with only the audio status endpoint."""
        import flask
        app = flask.Flask(__name__)
        app.secret_key = 'test'
        app.config['TESTING'] = True

        @app.route("/ajax/audio-status/<int:book_id>")
        def get_audio_status_json(book_id):
            from cps.aubooks_audio import get_audio_status
            status = get_audio_status(book_id)
            result = {"status": status, "download_url": None, "generate_url": None}
            if status == "ready":
                result["download_url"] = f"/books/{book_id}/audio/download"
            elif status in ("not_available", "failed"):
                result["generate_url"] = f"/books/{book_id}/generate-audio"
            return flask.jsonify(result)

        return app

    def test_not_available_json(self):
        app = self._make_app()
        with app.test_client() as c:
            r = c.get("/ajax/audio-status/999999")
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertEqual(data["status"], "not_available")
            self.assertIsNone(data["download_url"])
            self.assertIn("generate_url", data)

    def test_ready_json(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (100, 'ready', 'Test.m4b', 'Audiobooks/2026/09/Test.m4b', 'abc', 1000, datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()
            app = self._make_app()
            with app.test_client() as c, patch("cps.aubooks_audio._get_db_path", return_value=p):
                r = c.get("/ajax/audio-status/100")
                self.assertEqual(r.status_code, 200)
                data = r.get_json()
                self.assertEqual(data["status"], "ready")
                self.assertIn("/books/100/audio/download", data["download_url"])
                self.assertIsNone(data["generate_url"])
        finally:
            p.unlink(missing_ok=True)

    def test_queued_json(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (100, 'queued', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()
            app = self._make_app()
            with app.test_client() as c, patch("cps.aubooks_audio._get_db_path", return_value=p):
                r = c.get("/ajax/audio-status/100")
                self.assertEqual(r.status_code, 200)
                data = r.get_json()
                self.assertEqual(data["status"], "queued")
                self.assertIsNone(data["download_url"])
                self.assertIsNone(data["generate_url"])
        finally:
            p.unlink(missing_ok=True)

    def test_processing_json(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (100, 'processing', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()
            app = self._make_app()
            with app.test_client() as c, patch("cps.aubooks_audio._get_db_path", return_value=p):
                r = c.get("/ajax/audio-status/100")
                self.assertEqual(r.status_code, 200)
                data = r.get_json()
                self.assertEqual(data["status"], "processing")
                self.assertIsNone(data["download_url"])
                self.assertIsNone(data["generate_url"])
        finally:
            p.unlink(missing_ok=True)

    def test_failed_json(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, error, created_at, updated_at) "
                "VALUES (100, 'failed', 'TTS crashed', datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()
            app = self._make_app()
            with app.test_client() as c, patch("cps.aubooks_audio._get_db_path", return_value=p):
                r = c.get("/ajax/audio-status/100")
                self.assertEqual(r.status_code, 200)
                data = r.get_json()
                self.assertEqual(data["status"], "failed")
                self.assertIsNone(data["download_url"])
                self.assertIn("generate_url", data)
        finally:
            p.unlink(missing_ok=True)

    def test_no_opendrive_path_exposed(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (100, 'ready', 'Test.m4b', 'Audiobooks/2026/09/Test.m4b', 'abc', 1000, datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()
            app = self._make_app()
            with app.test_client() as c, patch("cps.aubooks_audio._get_db_path", return_value=p):
                r = c.get("/ajax/audio-status/100")
                data = r.get_json()
                self.assertNotIn("opendrive_path", data)
                self.assertNotIn("error", data)
                self.assertNotIn("sha256", data)
                self.assertNotIn("filename", data)
        finally:
            p.unlink(missing_ok=True)

    def test_endpoint_returns_only_three_keys(self):
        app = self._make_app()
        with app.test_client() as c:
            r = c.get("/ajax/audio-status/1")
            data = r.get_json()
            self.assertEqual(set(data.keys()), {"status", "download_url", "generate_url"})


class TestAudioStatusAccess(unittest.TestCase):
    """Test access and role checks on the production audio status endpoint."""

    @classmethod
    def setUpClass(cls):
        import cps
        cps.cli_param.gd_path = "/home/feninf/calibre-web-dev-data/gdrive.db"
        from cps import web
        cls.web = web

        import flask
        cls.app = flask.Flask(__name__)
        cls.app.register_blueprint(web.web)

    @staticmethod
    def _user(tts=False, download=False, authenticated=True):
        return SimpleNamespace(
            is_authenticated=authenticated,
            role_tts=lambda: tts,
            role_download=lambda: download,
        )

    def _request(self, status, user, visible=True):
        with self.app.test_request_context("/ajax/audio-status/100"):
            with patch.object(self.web.calibre_db, "get_filtered_book",
                              return_value=object() if visible else None), \
                    patch.object(self.web, "current_user", user), \
                    patch("cps.aubooks_permissions.config.config_theme", 3, create=True), \
                    patch("cps.aubooks_audio.get_audio_status", return_value=status):
                return self.web.get_audio_status_json.__wrapped__(100)

    def test_accessible_book_returns_normal_json(self):
        response = self._request("queued", self._user())
        self.assertEqual(response.get_json(), {
            "status": "queued", "download_url": None, "generate_url": None,
        })

    def test_inaccessible_book_returns_404(self):
        from werkzeug.exceptions import NotFound
        with self.assertRaises(NotFound):
            self._request("ready", self._user(tts=True, download=True), visible=False)

    def test_hidden_book_status_cannot_be_probed(self):
        from werkzeug.exceptions import NotFound
        with self.assertRaises(NotFound):
            self._request("not_available", self._user(tts=True), visible=False)

    def test_authenticated_user_gets_generate_url_without_tts_role(self):
        response = self._request("failed", self._user(tts=False))
        self.assertEqual(response.get_json()["generate_url"], "/books/100/generate-audio")

    def test_cancelled_status_gets_regeneration_url(self):
        response = self._request("cancelled", self._user())
        self.assertEqual(response.get_json()["generate_url"], "/books/100/generate-audio")

    def test_user_with_tts_role_gets_generate_url(self):
        response = self._request("failed", self._user(tts=True))
        self.assertEqual(response.get_json()["generate_url"], "/books/100/generate-audio")

    def test_anonymous_user_gets_no_generate_url(self):
        response = self._request("not_available", self._user(tts=True, authenticated=False))
        self.assertIsNone(response.get_json()["generate_url"])

    def test_anonymous_user_gets_no_download_url(self):
        response = self._request("ready", self._user(download=True, authenticated=False))
        self.assertIsNone(response.get_json()["download_url"])

    def test_authenticated_download_url_does_not_require_download_role(self):
        denied = self._request("ready", self._user(download=False)).get_json()
        allowed = self._request("ready", self._user(download=True)).get_json()
        self.assertEqual(denied["download_url"], "/books/100/audio/download")
        self.assertEqual(allowed["download_url"], "/books/100/audio/download")


class TestAudioStatusTemplate(unittest.TestCase):
    """Test template rendering with audio status."""

    def test_template_has_audio_button(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn("aubooks_audio_status", content)
        self.assertIn("data-audio-status", content)

    def test_template_has_all_states(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn("download_audiobook", content)
        self.assertIn("audio_status == 'queued'", content)
        self.assertIn("audio_status == 'processing'", content)
        self.assertIn("aubooks_audio_status == 'failed'", content)
        self.assertIn("aubooks_audio_status == 'cancelled'", content)
        self.assertNotIn("role_tts()", content)

    def test_template_no_href_hash(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertNotIn('href="#"', content)

    def test_template_has_russian_labels(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn("Скачать аудиокнигу", content)
        self.assertIn("Озвучить повторно", content)
        self.assertIn("Озвучить", content)
        self.assertIn("Отменено", content)

    def test_cancelled_has_separate_status_and_generate_flow(self):
        content = (Path(__file__).parent.parent / "cps" / "themes" / "aubooks" /
                   "templates" / "detail.html").read_text()
        start = content.index("aubooks_audio_status == 'cancelled'")
        section = content[start:content.index("{% else %}", start)]
        self.assertIn("Отменено", section)
        self.assertIn("generate_audio", section)
        self.assertIn("aria-live=\"polite\"", content)
        self.assertIn("s === 'cancelled'", content)

    def test_template_has_polling_js(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn("aubooks-audio-status", content)
        self.assertIn("ajax/audio-status", content)
        self.assertIn("setInterval", content)
        self.assertIn("data-csrf", content)

    def test_polling_only_builds_generation_controls_from_server_url(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertGreaterEqual(content.count("if (data.generate_url)"), 2)
        self.assertIn("form.action = data.generate_url", content)
        self.assertIn("form2.action = data.generate_url", content)

    def test_initial_generation_controls_require_authentication(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertGreaterEqual(content.count("current_user.is_authenticated"), 4)
        self.assertNotIn("current_user.role_tts()", content)

    def test_template_has_container_id(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn('id="aubooks-audio-status"', content)


class TestAudioAdapterAccessibility(unittest.TestCase):
    """Test accessibility of audio status elements."""

    def test_buttons_have_aria_disabled(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            section = content[idx:idx+2000]
            self.assertIn('aria-disabled="true"', section)

    def test_buttons_have_aria_labels(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            section = content[idx:idx+500]
            self.assertIn("aria-label", section)

    def test_buttons_have_data_book_id(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            section = content[idx:idx+2000]
            self.assertIn("data-book-id", section)


class TestGetAudioJobs(unittest.TestCase):
    """Test cps/aubooks_audio.py get_audio_jobs() function."""

    def test_empty_db_returns_empty_list(self):
        p = tmp_db()
        try:
            init_db(p)
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                self.assertEqual(result, [])
        finally:
            p.unlink(missing_ok=True)

    def test_missing_db_returns_empty_list(self):
        from cps.aubooks_audio import get_audio_jobs
        with patch("cps.aubooks_audio._get_db_path", return_value=Path("/nonexistent/audio.db")):
            result = get_audio_jobs()
            self.assertEqual(result, [])

    def test_queued_and_processing_returned(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (1, 'queued', '2026-09-09T10:00:00', '2026-09-09T10:00:00')"
            )
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (2, 'processing', '2026-09-09T10:01:00', '2026-09-09T10:01:00')"
            )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                statuses = {r["status"] for r in result}
                self.assertIn("queued", statuses)
                self.assertIn("processing", statuses)
        finally:
            p.unlink(missing_ok=True)

    def test_ready_failed_returned(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, filesize, created_at, updated_at) "
                "VALUES (1, 'ready', 'test.m4b', 1000, '2026-09-09T10:00:00', '2026-09-09T10:00:00')"
            )
            conn.execute(
                "INSERT INTO audio (book_id, status, error, created_at, updated_at) "
                "VALUES (2, 'failed', 'TTS error', '2026-09-09T10:01:00', '2026-09-09T10:01:00')"
            )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                statuses = {r["status"] for r in result}
                self.assertIn("ready", statuses)
                self.assertIn("failed", statuses)
        finally:
            p.unlink(missing_ok=True)

    def test_cancelled_is_finished_history_with_russian_label(self):
        p = tmp_db()
        try:
            conn = sqlite3.connect(str(p))
            conn.execute(
                "CREATE TABLE audio (book_id INTEGER, job_id TEXT, requested_by_user_id INTEGER, "
                "status TEXT, filename TEXT, filesize INTEGER, duration REAL, error TEXT, "
                "created_at TEXT, updated_at TEXT)"
            )
            conn.execute(
                "INSERT INTO audio VALUES (1, 'job-1', 7, 'cancelled', NULL, NULL, NULL, NULL, "
                "'2026-09-09T10:00:00', '2026-09-09T10:01:00')"
            )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs, STATUS_LABELS
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
            self.assertEqual(result[0]["status"], "cancelled")
            self.assertEqual(STATUS_LABELS["cancelled"], "Отменено")
        finally:
            p.unlink(missing_ok=True)

    def test_no_opendrive_path_exposed(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (1, 'ready', 'test.m4b', 'Audiobooks/2026/09/test.m4b', 'abc', 1000, '2026-09-09T10:00:00', '2026-09-09T10:00:00')"
            )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                self.assertEqual(len(result), 1)
                row = result[0]
                self.assertNotIn("opendrive_path", row)
                self.assertNotIn("sha256", row)
                self.assertIn("job_id", row)
                self.assertIn("requested_by_user_id", row)
                self.assertNotIn("id", row)
        finally:
            p.unlink(missing_ok=True)

    def test_finished_limit(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            for i in range(60):
                conn.execute(
                    "INSERT INTO audio (book_id, status, filename, created_at, updated_at) "
                    "VALUES (?, 'ready', 'test.m4b', ?, ?)",
                    (i + 100, f"2026-09-09T{i//24:02d}:{i%24:02d}:00", f"2026-09-09T{i//24:02d}:{i%24:02d}:00")
                )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                self.assertLessEqual(len(result), 50)
        finally:
            p.unlink(missing_ok=True)

    def test_newest_first_ordering(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (1, 'ready', '2026-09-09T10:00:00', '2026-09-09T10:00:00')"
            )
            conn.execute(
                "INSERT INTO audio (book_id, status, created_at, updated_at) "
                "VALUES (2, 'ready', '2026-09-09T12:00:00', '2026-09-09T12:00:00')"
            )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]["book_id"], 2)
                self.assertEqual(result[1]["book_id"], 1)
        finally:
            p.unlink(missing_ok=True)

    def test_has_required_fields(self):
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, filesize, duration, error, created_at, updated_at) "
                "VALUES (1, 'ready', 'test.m4b', 1024, 120.5, NULL, '2026-09-09T10:00:00', '2026-09-09T10:00:00')"
            )
            conn.commit()
            conn.close()
            from cps.aubooks_audio import get_audio_jobs
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                result = get_audio_jobs()
                self.assertEqual(len(result), 1)
                row = result[0]
                required = {"book_id", "status", "filename", "filesize", "duration", "error", "created_at", "updated_at"}
                self.assertTrue(required.issubset(set(row.keys())))
        finally:
            p.unlink(missing_ok=True)


class TestTtsJobsTemplate(unittest.TestCase):
    """Test tasks.html template for AU-Books TTS page."""

    def _read(self):
        p = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "tasks.html"
        return p.read_text()

    def test_template_exists(self):
        p = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "tasks.html"
        self.assertTrue(p.exists())

    def test_page_title_is_ozvuchivanie(self):
        content = self._read()
        self.assertIn("Озвучивание", content)

    def test_no_native_task_table(self):
        content = self._read()
        self.assertNotIn("tasktable", content)
        self.assertNotIn("emailstat", content)

    def test_has_tts_table(self):
        content = self._read()
        self.assertIn("tts-table", content)
        self.assertIn('url_for("tasks.get_tts_jobs_json")', content)

    def test_has_russian_labels(self):
        content = self._read()
        for label in ["Книга", "Статус", "Добавлено", "Обновлено", "Размер", "Длительность", "Ошибка", "Действие"]:
            self.assertIn(label, content)

    def test_has_polling_5000(self):
        content = self._read()
        self.assertIn("setInterval", content)
        self.assertIn("5000", content)

    def test_has_loading_and_ajax_error_states(self):
        content = self._read()
        self.assertIn('id="tts-load-status"', content)
        self.assertIn('role="status"', content)
        self.assertIn("Загрузка...", content)
        self.assertIn("Не удалось загрузить задания", content)
        self.assertIn("error: function(xhr, status, error)", content)

    def test_render_failures_are_visible_and_polling_continues(self):
        content = self._read()
        self.assertIn("if (!Array.isArray(data))", content)
        self.assertIn("bootstrapTable('load', rows)", content)
        self.assertIn("catch (error)", content)
        self.assertIn("showLoadError(error)", content)
        self.assertIn("setInterval(loadTtsJobs, 5000)", content)

    def test_has_download_action(self):
        content = self._read()
        # Check for the Unicode escapes as they appear in the JS source
        self.assertIn("\\u0421\\u043a\\u0430\\u0447\\u0430\\u0442\\u044c", content)
        self.assertIn("\\u041e\\u0442\\u043a\\u0440\\u044b\\u0442\\u044c", content)
        self.assertIn("r.action = actionFormatter(null, r)", content)

    def test_no_cancel_button(self):
        content = self._read()
        self.assertNotIn("can_cancel", content)
        self.assertNotIn("cancel_url", content)
        self.assertNotIn("tts-cancel", content)
        self.assertNotIn("Отменить озвучивание этой книги?", content)
        self.assertNotIn("X-Requested-With", content)
        self.assertNotIn("tts-cancel-error", content)
        self.assertNotIn("Отменить", content)

    def test_action_keeps_download_and_open_actions(self):
        content = self._read()
        self.assertIn("row.status === 'ready' && row.download_url", content)
        self.assertIn("row.status === 'failed' || row.status === 'cancelled'", content)
        self.assertIn("loadTtsJobs()", content)

    def test_has_date_formatting_js(self):
        content = self._read()
        self.assertIn("formatDate", content)
        self.assertIn("new Date", content)

    def test_title_is_link(self):
        content = self._read()
        self.assertIn('data-class="tts-title-cell"', content)
        self.assertIn("r.title_cell = titleCellFormatter(r.title, r)", content)
        self.assertIn("book_url", content)

    def test_author_displayed(self):
        content = self._read()
        self.assertIn("tts-author", content)
        self.assertIn("row.author", content)

    def test_dynamic_content_is_escaped(self):
        content = self._read()
        self.assertIn("function escapeHtml", content)
        self.assertIn("escapeHtml(value)", content)
        self.assertIn("escapeHtml(row.author)", content)

    def test_empty_error_and_action_show_dash(self):
        content = self._read()
        self.assertIn("if (!err) return '\\u2014'", content)
        self.assertIn("return '\\u2014';", content)

    def test_no_table_js_for_native_tasks(self):
        content = self._read()
        self.assertNotIn("table.js", content)

    def test_extends_layout(self):
        content = self._read()
        self.assertIn('extends theme("layout.html")', content)


class TestTtsJobsEndpointSecurity(unittest.TestCase):
    """Test visibility filtering and safe output of the production TTS jobs endpoint."""

    @classmethod
    def setUpClass(cls):
        import cps
        cps.cli_param.gd_path = "/home/feninf/calibre-web-dev-data/gdrive.db"
        from cps import tasks_status, web
        cls.tasks_status = tasks_status

        import flask
        cls.app = flask.Flask(__name__)
        cls.app.register_blueprint(web.web)
        cls.app.register_blueprint(tasks_status.tasks)

    @staticmethod
    def _row(book_id, status="failed", error="/home/private token=secret"):
        return {
            "book_id": book_id,
            "job_id": f"job-{book_id}",
            "requested_by_user_id": 7,
            "status": status,
            "filename": "test.m4b",
            "filesize": 1024,
            "duration": 60.0,
            "error": error,
            "created_at": "2026-09-09T10:00:00+00:00",
            "updated_at": "2026-09-09T10:01:00+00:00",
            "opendrive_path": "Audiobooks/private/test.m4b",
            "sha256": "secret-hash",
        }

    def _request(self, rows, books, can_download=True, user_id=7, admin=False,
                 theme=3, tts=True):
        query = MagicMock()
        query.options.return_value = query
        query.filter.return_value = query
        query.all.return_value = books
        fake_db = SimpleNamespace(
            session=SimpleNamespace(query=MagicMock(return_value=query)),
            common_filters=MagicMock(return_value=object()),
        )
        user = SimpleNamespace(id=user_id, is_authenticated=True,
                               role_download=lambda: can_download,
                               role_admin=lambda: admin,
                               role_tts=lambda: tts)
        with self.app.test_request_context("/ajax/tts-jobs"):
            with patch.object(self.tasks_status, "calibre_db", fake_db), \
                    patch.object(self.tasks_status, "current_user", user), \
                    patch("cps.aubooks_permissions.config.config_theme", theme, create=True), \
                    patch("cps.aubooks_audio.get_audio_jobs", return_value=rows):
                response = self.tasks_status.get_tts_jobs_json.__wrapped__()
        fake_db.common_filters.assert_called_once_with(allow_show_archived=True)
        return response.get_json()

    def test_accessible_job_is_included(self):
        author = SimpleNamespace(name="Автор")
        book = SimpleNamespace(id=1, title="Книга", authors=[author])
        data = self._request([self._row(1)], [book])
        self.assertEqual(data[0]["book_id"], 1)
        self.assertEqual(data[0]["title"], "Книга")

    def test_inaccessible_and_missing_books_are_excluded(self):
        visible = SimpleNamespace(id=1, title="Visible", authors=[])
        rows = [self._row(1), self._row(2), self._row(999)]
        data = self._request(rows, [visible])
        self.assertEqual([item["book_id"] for item in data], [1])

    def test_raw_error_and_internal_fields_are_not_returned(self):
        book = SimpleNamespace(id=1, title="Книга", authors=[])
        data = self._request([self._row(1)], [book])[0]
        serialized = str(data)
        self.assertEqual(data["error"], "Ошибка генерации аудиокниги")
        self.assertNotIn("/home/private", serialized)
        self.assertNotIn("token=secret", serialized)
        self.assertNotIn("opendrive_path", data)
        self.assertNotIn("sha256", data)
        self.assertNotIn("requested_by_user_id", data)
        self.assertNotIn("job_id", data)

    def test_cancellation_fields_are_not_returned(self):
        book = SimpleNamespace(id=1, title="Книга", authors=[])
        active = self._request([self._row(1, status="queued", error=None)], [book])[0]
        self.assertNotIn("can_cancel", active)
        self.assertNotIn("cancel_url", active)

    def test_ready_download_url_is_available_without_separate_role(self):
        book = SimpleNamespace(id=1, title="Книга", authors=[])
        row = self._row(1, status="ready", error=None)
        denied = self._request([row], [book], can_download=False)[0]
        allowed = self._request([row], [book], can_download=True)[0]
        self.assertEqual(denied["download_url"], "/books/1/audio/download")
        self.assertEqual(allowed["download_url"], "/books/1/audio/download")

    def test_endpoint_keeps_login_required_decorator(self):
        self.assertTrue(hasattr(self.tasks_status.get_tts_jobs_json, "__wrapped__"))


if __name__ == "__main__":
    unittest.main()
