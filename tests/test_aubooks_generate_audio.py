"""Tests for generate-audio POST route and transport abstraction."""

import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aubooks"))
from audio_index import init_db

TEMPLATE_PATH = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates" / "detail.html"
WEB_PY_PATH = Path(__file__).parent.parent / "cps" / "web.py"
TTS_PATH = Path(__file__).parent.parent / "cps" / "aubooks_tts.py"


def tmp_db():
    return Path(tempfile.mktemp(suffix=".db"))


def read_template():
    return TEMPLATE_PATH.read_text()


def read_web_source():
    return WEB_PY_PATH.read_text()


def read_tts_source():
    return TTS_PATH.read_text()


# --- Transport abstraction tests ---

class TestTransportAbstraction(unittest.TestCase):
    """Test cps/aubooks_tts.py transport layer."""

    def test_queue_book_function_exists(self):
        """queue_book function should be defined."""
        source = read_tts_source()
        self.assertIn("def queue_book(", source)

    def test_queue_book_returns_queued_result(self):
        """Successful queue should return QueueResult with success=True."""
        source = read_tts_source()
        self.assertIn("QueueResult(True", source)

    def test_uses_http_post(self):
        source = read_tts_source()
        self.assertIn("urllib.request.Request", source)
        self.assertIn('method="POST"', source)

    def test_no_shell_true(self):
        """Transport should not use shell=True."""
        source = read_tts_source()
        self.assertNotIn("shell=True", source)

    def test_queue_payload_has_book_and_owner(self):
        source = read_tts_source()
        self.assertIn('"book_id": book_id', source)
        self.assertIn('"requested_by_user_id": requested_by_user_id', source)

    def test_queue_book_signature_requires_book_and_owner(self):
        import inspect
        from cps.aubooks_tts import queue_book
        params = list(inspect.signature(queue_book).parameters)
        self.assertEqual(params, ["book_id", "requested_by_user_id"])

    def test_json_content_type_is_set(self):
        source = read_tts_source()
        self.assertIn('"Content-Type": "application/json"', source)

    def test_timeout_handled(self):
        """HTTP transport timeouts should be caught."""
        source = read_tts_source()
        self.assertIn("TimeoutError", source)

    def test_url_error_handled(self):
        source = read_tts_source()
        self.assertIn("urllib.error.URLError", source)

    def test_unexpected_transport_error_handled(self):
        source = read_tts_source()
        self.assertIn("except Exception", source)

    def test_dispatch_url_configurable(self):
        source = read_tts_source()
        self.assertIn("TTS_DISPATCH_URL", source)
        self.assertIn("_DEFAULT_DISPATCH_URL", source)


# --- Route tests ---

class TestGenerateAudioRoute(unittest.TestCase):
    """Test the generate_audio route structure."""

    def test_route_no_local_source_lookup(self):
        """Route should NOT call _find_tts_source."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("_find_tts_source", func_source)
        self.assertNotIn("_TTS_SOURCE_FORMATS", func_source)

    def test_route_no_popen(self):
        """Route should NOT directly use subprocess.Popen."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("subprocess.Popen", func_source)

    def test_route_calls_queue_book(self):
        """Route should call queue_book from the transport layer."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("queue_book", func_source)

    def test_route_checks_result_success(self):
        """Route should check result.success."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("result.success", func_source)

    def test_route_no_mark_failed(self):
        """Route should NOT directly call mark_failed (pipeline handles it)."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("mark_failed", func_source)

    def test_route_no_create_queued(self):
        """Route should NOT directly call create_queued (pipeline handles it)."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("create_queued", func_source)

    def test_route_no_reset_for_retry(self):
        """Route should NOT directly call reset_for_retry (pipeline handles it)."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("reset_for_retry", func_source)


class TestGenerateAudioStatusChecks(unittest.TestCase):
    """Test status validation logic."""

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
    """Test audio index duplicate protection."""

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
            self.assertIn("Cannot reset", str(ctx.exception))
        finally:
            p.unlink(missing_ok=True)


class TestTemplateFormStructure(unittest.TestCase):
    """Test template audio button forms."""

    def test_not_available_has_post_form(self):
        content = read_template()
        forms = re.findall(r'<form[^>]*generate_audio[^>]*>.*?</form>', content, re.DOTALL)
        self.assertEqual(len(forms), 3)
        self.assertIn('class="btn btn-default"', forms[2])

    def test_failed_has_post_form(self):
        content = read_template()
        idx = content.find("aubooks_audio_status == 'failed'")
        self.assertGreater(idx, 0)
        section = content[idx:content.find("{% else %}", idx)]
        self.assertIn('method="POST"', section)
        self.assertIn("csrf_token", section)
        self.assertIn("generate_audio", section)

    def test_queued_no_form(self):
        content = read_template()
        idx = content.find("aubooks_audio_status == 'queued'")
        self.assertGreater(idx, 0)
        section = content[idx:idx+300]
        self.assertNotIn('<form', section)

    def test_processing_no_form(self):
        content = read_template()
        idx = content.find("aubooks_audio_status == 'processing'")
        self.assertGreater(idx, 0)
        next_section_start = content.find('{% elif', idx)
        section = content[idx:next_section_start]
        self.assertNotIn('<form', section)

    def test_ready_no_form(self):
        content = read_template()
        idx = content.find("aubooks_audio_status == 'ready'")
        self.assertGreater(idx, 0)
        section = content[idx:idx+500]
        self.assertNotIn("generate_audio", section)

    def test_csrf_token_in_forms(self):
        content = read_template()
        form_pattern = re.compile(
            r'<form[^>]*generate_audio[^>]*>.*?</form>', re.DOTALL
        )
        forms = form_pattern.findall(content)
        self.assertEqual(len(forms), 3)
        for form in forms:
            self.assertIn("csrf_token", form)

    def test_no_href_hash(self):
        content = read_template()
        self.assertNotIn('href="#"', content)

    def test_buttons_are_submit(self):
        content = read_template()
        form_pattern = re.compile(
            r'<form[^>]*generate_audio[^>]*>.*?</form>', re.DOTALL
        )
        forms = form_pattern.findall(content)
        for form in forms:
            self.assertIn('type="submit"', form)

    def test_authentication_gates_not_available_button(self):
        content = read_template()
        self.assertIn("{% if current_user.is_authenticated %}", content)
        self.assertNotIn("current_user.role_tts()", content)


class TestAuthAndPermissions(unittest.TestCase):
    """Test route authorization."""

    def test_route_requires_post(self):
        source = read_web_source()
        idx = source.find('"/books/<int:book_id>/generate-audio"')
        self.assertGreater(idx, 0)
        after = source[idx:idx+100]
        self.assertIn("POST", after)

    def test_route_uses_registered_user_policy(self):
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("can_generate_tts", func_source)
        self.assertNotIn("current_user.role_tts", func_source)

    def test_route_has_user_login_required(self):
        source = read_web_source()
        idx = source.find("def generate_audio")
        self.assertGreater(idx, 0)
        decorator_area = source[max(0, idx-300):idx+50]
        self.assertIn("user_login_required", decorator_area)


class TestErrorHandling(unittest.TestCase):
    """Test error handling."""

    def test_no_traceback_in_route(self):
        """Route should not contain traceback handling."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertNotIn("traceback", func_source.lower())

    def test_flash_messages_are_user_friendly(self):
        """Flash messages should use _() for translations."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn('_(', func_source)

    def test_result_error_message_used(self):
        """Route should use result.error_message for flash."""
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("result.error_message", func_source)


class TestRouteSignature(unittest.TestCase):
    """Test route function signature."""

    def test_route_accepts_book_id(self):
        source = read_web_source()
        self.assertIn("def generate_audio(book_id):", source)

    def test_uses_redirect_prg(self):
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("redirect(url_for(", func_source)
        self.assertIn("code=303", func_source)

    def test_book_exists_check(self):
        source = read_web_source()
        idx = source.find("def generate_audio")
        func_source = source[idx:idx+3000]
        self.assertIn("get_filtered_book", func_source)
        self.assertIn("abort(404)", func_source)


if __name__ == "__main__":
    unittest.main()
