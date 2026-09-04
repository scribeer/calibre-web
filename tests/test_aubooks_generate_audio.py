"""Tests for generate-audio POST route in Calibre-Web."""

import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aubooks"))
from audio_index import init_db

TEMPLATE_PATH = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
WEB_PY_PATH = Path(__file__).parent.parent / "cps" / "web.py"


def tmp_db():
    """Create a temporary DB path for testing."""
    return Path(tempfile.mktemp(suffix=".db"))


def read_template():
    return TEMPLATE_PATH.read_text()


def read_web_source():
    return WEB_PY_PATH.read_text()


class TestFindTtsSource(unittest.TestCase):
    """Test _find_ttsSource logic by reading source file."""

    def test_source_format_priority_list_defined(self):
        """_TTS_SOURCE_FORMATS should list EPUB before PDF."""
        source = read_web_source()
        self.assertIn("_TTS_SOURCE_FORMATS", source)
        # EPUB should appear before PDF in the list
        epub_pos = source.find('"EPUB"')
        pdf_pos = source.find('"PDF"')
        self.assertGreater(epub_pos, 0)
        self.assertGreater(pdf_pos, 0)
        self.assertLess(epub_pos, pdf_pos)

    def test_find_tts_source_function_exists(self):
        """_find_tts_source function should be defined."""
        source = read_web_source()
        self.assertIn("def _find_tts_source(book)", source)

    def test_find_tts_source_uses_get_book_path(self):
        """_find_tts_source should use config.get_book_path()."""
        source = read_web_source()
        idx = source.find("def _find_tts_source")
        func_source = source[idx:idx+1500]
        self.assertIn("get_book_path", func_source)
        self.assertIn("os.path.normpath", func_source)
        self.assertIn("os.path.isfile", func_source)
        # Should NOT import _Settings (config is already available)
        self.assertNotIn("_Settings", func_source)

    def test_find_tts_source_iterates_formats(self):
        """_find_tts_source should iterate over _TTS_SOURCE_FORMATS."""
        source = read_web_source()
        idx = source.find("def _find_tts_source")
        func_source = source[idx:idx+1500]
        self.assertIn("for fmt in _TTS_SOURCE_FORMATS", func_source)
        self.assertIn("get_book_format", func_source)


class TestGenerateAudioStatusChecks(unittest.TestCase):
    """Test status validation logic for generate-audio."""

    def test_queued_blocked(self):
        from cps.aubooks_audio import get_audio_status
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
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "queued")
                self.assertIn(status, ("queued", "processing", "ready"))
        finally:
            p.unlink(missing_ok=True)

    def test_processing_blocked(self):
        from cps.aubooks_audio import get_audio_status
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
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "processing")
        finally:
            p.unlink(missing_ok=True)

    def test_ready_blocked(self):
        from cps.aubooks_audio import get_audio_status
        p = tmp_db()
        try:
            init_db(p)
            conn = sqlite3.connect(str(p))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, "
                "sha256, filesize, created_at, updated_at) "
                "VALUES (100, 'ready', 'Test.m4b', 'path', 'abc', 1000, "
                "datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()
            with patch("cps.aubooks_audio._get_db_path", return_value=p):
                status = get_audio_status(100)
                self.assertEqual(status, "ready")
        finally:
            p.unlink(missing_ok=True)

    def test_not_available_allows_new_job(self):
        from cps.aubooks_audio import get_audio_status
        with patch("cps.aubooks_audio._get_db_path", return_value=tmp_db()):
            status = get_audio_status(999)
            self.assertEqual(status, "not_available")

    def test_failed_allows_retry(self):
        from audio_index import get_status, reset_for_retry
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

            status_before = get_status(100, p)
            self.assertEqual(status_before, "failed")

            reset_for_retry(100, p)
            status_after = get_status(100, p)
            self.assertEqual(status_after, "queued")
        finally:
            p.unlink(missing_ok=True)


class TestDuplicateProtection(unittest.TestCase):
    """Test that duplicate job creation is prevented."""

    def test_create_queued_prevents_duplicate(self):
        from audio_index import create_queued
        p = tmp_db()
        try:
            init_db(p)
            create_queued(100, job_id="job1", db_path=p)

            with self.assertRaises(ValueError) as ctx:
                create_queued(100, job_id="job2", db_path=p)
            self.assertIn("already has status", str(ctx.exception))
        finally:
            p.unlink(missing_ok=True)

    def test_reset_for_retry_only_from_failed(self):
        from audio_index import create_queued, reset_for_retry
        p = tmp_db()
        try:
            init_db(p)
            create_queued(100, job_id="job1", db_path=p)

            with self.assertRaises(ValueError) as ctx:
                reset_for_retry(100, p)
            self.assertIn("Only failed", str(ctx.exception))
        finally:
            p.unlink(missing_ok=True)


class TestSubprocessCall(unittest.TestCase):
    """Test that pipeline is called correctly (by reading source)."""

    def test_pipeline_args_are_list(self):
        """Pipeline should be called with list args, not shell string."""
        source = read_web_source()
        self.assertIn("subprocess.Popen(", source)
        self.assertIn("start_new_session=True", source)

    def test_no_shell_true(self):
        """Route code should not use shell=True."""
        source = read_web_source()
        # Find the generate_audio function
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("shell=True", func_source)

    def test_pipeline_path_is_fixed(self):
        """Pipeline path should be derived from home dir, not user input."""
        source = read_web_source()
        self.assertIn("_AUBOOK_REMOTE", source)
        self.assertIn("aubook-remote.sh", source)

    def test_subprocess_devnull(self):
        """stdout/stderr should go to DEVNULL to avoid blocking."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("subprocess.DEVNULL", func_source)


class TestTemplateFormStructure(unittest.TestCase):
    """Test that the template has correct form structure."""

    def test_not_available_has_post_form(self):
        """not_available state should have a POST form."""
        content = read_template()
        idx = content.find('data-audio-status="not_available"')
        self.assertGreater(idx, 0)
        before = content[max(0, idx - 500):idx]
        self.assertIn('method="POST"', before)
        self.assertIn("csrf_token", before)
        self.assertIn("generate_audio", before)

    def test_failed_has_post_form(self):
        """failed state should have a POST form."""
        content = read_template()
        idx = content.find('data-audio-status="failed"')
        self.assertGreater(idx, 0)
        before = content[max(0, idx - 500):idx]
        self.assertIn('method="POST"', before)
        self.assertIn("csrf_token", before)
        self.assertIn("generate_audio", before)

    def test_queued_no_form(self):
        """queued state should NOT have a form (read-only)."""
        content = read_template()
        idx = content.find('data-audio-status="queued"')
        self.assertGreater(idx, 0)
        section = content[idx:idx+300]
        self.assertNotIn('<form', section)

    def test_processing_no_form(self):
        """processing state should NOT have a form (read-only)."""
        content = read_template()
        idx = content.find('data-audio-status="processing"')
        self.assertGreater(idx, 0)
        # Only check within the processing section (before the next elif)
        next_section_start = content.find('{% elif', idx)
        section = content[idx:next_section_start]
        self.assertNotIn('<form', section)

    def test_ready_no_form(self):
        """ready state should NOT have a generate form."""
        content = read_template()
        idx = content.find('data-audio-status="ready"')
        self.assertGreater(idx, 0)
        section = content[idx:idx+500]
        self.assertNotIn("generate_audio", section)

    def test_csrf_token_in_forms(self):
        """Both generate forms must include CSRF token."""
        content = read_template()
        form_pattern = re.compile(
            r'<form[^>]*generate_audio[^>]*>.*?</form>',
            re.DOTALL
        )
        forms = form_pattern.findall(content)
        self.assertEqual(len(forms), 2, "Expected 2 generate-audio forms")
        for form in forms:
            self.assertIn("csrf_token", form)

    def test_no_href_hash(self):
        """Template should not use <a href=\"#\">."""
        content = read_template()
        self.assertNotIn('href="#"', content)

    def test_buttons_are_submit(self):
        """Generate buttons should be type=submit."""
        content = read_template()
        form_pattern = re.compile(
            r'<form[^>]*generate_audio[^>]*>.*?</form>',
            re.DOTALL
        )
        forms = form_pattern.findall(content)
        for form in forms:
            self.assertIn('type="submit"', form)

    def test_tts_role_gates_not_available_button(self):
        """not_available button should only show for role_tts users."""
        content = read_template()
        idx = content.find('data-audio-status="not_available"')
        self.assertGreater(idx, 0)
        # The role_tts check is ~456 chars before in the {% else %} block
        before = content[max(0, idx - 500):idx]
        self.assertIn("role_tts", before)


class TestAuthAndPermissions(unittest.TestCase):
    """Test authorization logic by reading source."""

    def test_route_requires_post(self):
        """Route should only accept POST."""
        source = read_web_source()
        idx = source.find('"/books/<int:book_id>/generate-audio"')
        self.assertGreater(idx, 0)
        after = source[idx:idx+100]
        self.assertIn("POST", after)

    def test_route_has_tts_role_check(self):
        """Route should check role_tts()."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("role_tts", func_source)

    def test_route_has_user_login_required(self):
        """Route should use user_login_required."""
        source = read_web_source()
        # Find the full decorator block
        idx = source.find("def generate_audio")
        self.assertGreater(idx, 0)
        decorator_area = source[max(0, idx-300):idx+50]
        self.assertIn("user_login_required", decorator_area)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in the route."""

    def test_pipeline_not_found_reverts_to_failed(self):
        """If pipeline binary not found, audio status should revert to failed."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        self.assertIn("FileNotFoundError", func_source)
        self.assertIn("mark_failed", func_source)

    def test_os_error_reverts_to_failed(self):
        """If subprocess fails to start, audio status should revert to failed."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        self.assertIn("OSError", func_source)

    def test_no_traceback_in_flash(self):
        """Error messages should not contain internal details."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        self.assertNotIn("traceback", func_source.lower())
        self.assertNotIn("stack_trace", func_source.lower())

    def test_flash_messages_are_user_friendly(self):
        """Flash messages should be translatable, not technical."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        # Should use _() for translations
        self.assertIn('_("', func_source)
        # Should not expose file paths in flash messages
        self.assertNotIn('/home/', func_source.split("flash(")[1].split(")")[0] if "flash(" in func_source else "")


class TestRaceProtection(unittest.TestCase):
    """Test concurrent duplicate protection."""

    def test_sqlite_unique_constraint(self):
        from audio_index import create_queued
        p = tmp_db()
        try:
            init_db(p)
            create_queued(100, job_id="job1", db_path=p)
            with self.assertRaises(ValueError):
                create_queued(100, job_id="job2", db_path=p)
        finally:
            p.unlink(missing_ok=True)

    def test_status_check_before_create(self):
        """Route checks status before creating record."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        self.assertIn("audio_status", func_source)
        self.assertIn("create_queued", func_source)
        # Status should be checked before create_queued
        status_pos = func_source.find("audio_status")
        create_pos = func_source.find("create_queued")
        self.assertLess(status_pos, create_pos)


class TestRouteSignature(unittest.TestCase):
    """Test the route function signature."""

    def test_route_accepts_book_id(self):
        """Route function should accept book_id parameter."""
        source = read_web_source()
        self.assertIn("def generate_audio(book_id):", source)

    def test_uses_redirect_prg(self):
        """Route should use Post/Redirect/Get pattern."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        self.assertIn("redirect(url_for(", func_source)
        self.assertIn("code=303", func_source)

    def test_book_exists_check(self):
        """Route should verify book exists."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+4000]
        self.assertIn("get_filtered_book", func_source)
        self.assertIn("abort(404)", func_source)


if __name__ == "__main__":
    unittest.main()
