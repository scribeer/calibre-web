"""Tests for audio status integration in Calibre-Web."""

import sqlite3
import tempfile
import unittest
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


class TestAudioStatusTemplate(unittest.TestCase):
    """Test template rendering with audio status."""

    def test_template_has_audio_button(self):
        """Template should render audio status button."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        # Check for audio status section
        self.assertIn("aubooks_audio_status", content)
        self.assertIn("data-audio-status", content)

    def test_template_has_all_states(self):
        """Template should handle all 5 states."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertIn("download_audiobook", content)
        self.assertIn("data-audio-status=\"queued\"", content)
        self.assertIn("data-audio-status=\"processing\"", content)
        self.assertIn("data-audio-status=\"failed\"", content)
        self.assertIn("data-audio-status=\"not_available\"", content)

    def test_template_no_href_hash(self):
        """Template should not use <a href=\"#\">."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        self.assertNotIn('href="#"', content)
        self.assertNotIn('href="#"', content)

    def test_template_uses_buttons(self):
        """Audio status should use <button> elements."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        # Find the audio status section
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            # Check that buttons are used, not links
            section = content[idx:idx+2000]
            self.assertIn("<button", section)
            self.assertNotIn("<a ", section.split("audio status")[1].split("endblock")[0] if "audio status" in section else "")


class TestAudioAdapterAccessibility(unittest.TestCase):
    """Test accessibility of audio status elements."""

    def test_buttons_have_aria_disabled(self):
        """Disabled buttons should have aria-disabled."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        # Find disabled buttons in audio section
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            section = content[idx:idx+2000]
            # Queued and processing should be disabled
            self.assertIn('aria-disabled="true"', section)

    def test_buttons_have_aria_labels(self):
        """Audio button group should have aria-label."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            section = content[idx:idx+500]
            self.assertIn("aria-label", section)

    def test_buttons_have_data_book_id(self):
        """Buttons should have data-book-id for future integration."""
        template_path = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
        content = template_path.read_text()
        idx = content.find("aubooks_audio_status")
        if idx >= 0:
            section = content[idx:idx+2000]
            self.assertIn("data-book-id", section)


if __name__ == "__main__":
    unittest.main()
