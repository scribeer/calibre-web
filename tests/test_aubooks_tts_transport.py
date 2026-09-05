"""Tests for cps/aubooks_tts.py HTTP transport."""

import json
import unittest
from unittest.mock import patch
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from cps.aubooks_tts import queue_book, QueueResult


class _MockDispatcher(BaseHTTPRequestHandler):
    """Mock dispatcher that returns predefined responses based on book_id."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        body = json.loads(raw)
        book_id = body.get("book_id")

        if book_id == 99:
            self._respond(409, {"ok": False, "code": 409, "error": "Book is already queued."})
        elif book_id == 404:
            self._respond(404, {"ok": False, "code": 404, "error": "Book not found."})
        elif book_id == 500:
            self._respond(500, {"ok": False, "code": 5, "error": "No supported source format."})
        else:
            self._respond(200, {"ok": True, "book_id": book_id, "job_id": f"MOCK_JOB_{book_id}"})

    def _respond(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _GarbageDispatcher(BaseHTTPRequestHandler):
    """Returns invalid JSON."""

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"not json at all")

    def log_message(self, *args):
        pass


class _SlowDispatcher(BaseHTTPRequestHandler):
    """Never responds (for timeout testing)."""

    def do_POST(self):
        time.sleep(9999)

    def log_message(self, *args):
        pass


def _start_mock(handler_class):
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


class TestQueueBookHTTP(unittest.TestCase):
    """Test queue_book via mock HTTP dispatcher."""

    def setUp(self):
        self.server, self.port = _start_mock(_MockDispatcher)
        self._env = patch.dict("os.environ", {"TTS_DISPATCH_URL": f"http://127.0.0.1:{self.port}"})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self.server.shutdown()

    def test_success(self):
        result = queue_book(42)
        self.assertTrue(result.success)
        self.assertEqual(result.job_id, "MOCK_JOB_42")

    def test_duplicate_409(self):
        result = queue_book(99)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 409)
        self.assertIn("queued", result.error_message.lower())

    def test_not_found_404(self):
        result = queue_book(404)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 404)

    def test_pipeline_error(self):
        result = queue_book(500)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 5)


class TestQueueBookErrors(unittest.TestCase):
    """Test queue_book error handling."""

    def test_dispatcher_unavailable(self):
        with patch.dict("os.environ", {"TTS_DISPATCH_URL": "http://127.0.0.1:1"}):
            result = queue_book(1)
        self.assertFalse(result.success)
        self.assertIn("unavailable", result.error_message.lower())

    def test_malformed_json_response(self):
        server, port = _start_mock(_GarbageDispatcher)
        try:
            with patch.dict("os.environ", {"TTS_DISPATCH_URL": f"http://127.0.0.1:{port}"}):
                result = queue_book(1)
            self.assertFalse(result.success)
        finally:
            server.shutdown()

    def test_timeout(self):
        server, port = _start_mock(_SlowDispatcher)
        try:
            with patch.dict("os.environ", {"TTS_DISPATCH_URL": f"http://127.0.0.1:{port}"}):
                result = queue_book(1)
            self.assertFalse(result.success)
        finally:
            server.shutdown()

    def test_preserves_queue_result_api(self):
        r = QueueResult(True, 0, "", "job_1")
        self.assertTrue(r.success)
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.error_message, "")
        self.assertEqual(r.job_id, "job_1")
        self.assertIn("success=True", repr(r))

    def test_voice_and_publish_params_accepted(self):
        """voice/publish params are accepted but ignored (dispatcher controls them)."""
        server, port = _start_mock(_MockDispatcher)
        try:
            with patch.dict("os.environ", {"TTS_DISPATCH_URL": f"http://127.0.0.1:{port}"}):
                result = queue_book(42, voice=2, publish=False)
            self.assertTrue(result.success)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
