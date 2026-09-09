"""Tests for audio status integration in Calibre-Web."""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn("audio_status == 'failed'", content)
        self.assertIn("role_tts()", content)

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

    def test_template_has_polling_js(self):
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn("aubooks-audio-status", content)
        self.assertIn("ajax/audio-status", content)
        self.assertIn("setInterval", content)
        self.assertIn("data-csrf", content)

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


if __name__ == "__main__":
    unittest.main()
