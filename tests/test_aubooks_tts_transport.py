"""Tests for cps/aubooks_tts.py HTTP transport."""

import json
import unittest
from unittest.mock import MagicMock, patch
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from cps.aubooks_tts import cancel_job, queue_book, CancelResult, QueueResult


class _MockDispatcher(BaseHTTPRequestHandler):
    """Mock dispatcher that returns predefined responses based on book_id."""

    last_body = None

    def do_POST(self):
        if self.path.startswith("/cancel/"):
            self._respond(200, {"ok": True, "status": "cancelled"})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        body = json.loads(raw)
        type(self).last_body = body
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
        result = queue_book(42, 7)
        self.assertTrue(result.success)
        self.assertEqual(result.job_id, "MOCK_JOB_42")

    def test_duplicate_409(self):
        result = queue_book(99, 7)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 409)
        self.assertEqual(result.error_message, "Audio generation service rejected the request.")

    def test_not_found_404(self):
        result = queue_book(404, 7)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 404)

    def test_pipeline_error(self):
        result = queue_book(500, 7)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 5)


class TestQueueBookErrors(unittest.TestCase):
    """Test queue_book error handling."""

    @staticmethod
    def _response(body):
        response = MagicMock()
        response.read.return_value = json.dumps(body).encode("utf-8")
        response.__enter__.return_value = response
        return response

    def test_dispatcher_unavailable(self):
        with patch.dict("os.environ", {"TTS_DISPATCH_URL": "http://127.0.0.1:1"}):
            result = queue_book(1, 7)
        self.assertFalse(result.success)
        self.assertIn("unavailable", result.error_message.lower())

    def test_malformed_json_response(self):
        server, port = _start_mock(_GarbageDispatcher)
        try:
            with patch.dict("os.environ", {"TTS_DISPATCH_URL": f"http://127.0.0.1:{port}"}):
                result = queue_book(1, 7)
            self.assertFalse(result.success)
        finally:
            server.shutdown()

    def test_timeout(self):
        # Simulate urlopen timeout; a real slow server would hang server.shutdown().
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")), \
                patch.dict("os.environ", {"TTS_DISPATCH_URL": "http://127.0.0.1:18900"}):
            result = queue_book(1, 7)
        self.assertFalse(result.success)
        self.assertIn("timed out", result.error_message.lower())

    def test_preserves_queue_result_api(self):
        r = QueueResult(True, 0, "", "job_1")
        self.assertTrue(r.success)
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.error_message, "")
        self.assertEqual(r.job_id, "job_1")
        self.assertIn("success=True", repr(r))

    def test_queue_payload_contains_server_owner(self):
        server, port = _start_mock(_MockDispatcher)
        try:
            with patch.dict("os.environ", {"TTS_DISPATCH_URL": f"http://127.0.0.1:{port}"}):
                result = queue_book(42, 7)
            self.assertTrue(result.success)
            self.assertEqual(_MockDispatcher.last_body, {
                "book_id": 42,
                "requested_by_user_id": 7,
            })
        finally:
            server.shutdown()

    def test_cancel_posts_quoted_job_without_body(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"ok": True, "status": "cancelled"}).encode()
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", return_value=response) as open_url:
            result = cancel_job("job/with space")
        request = open_url.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.full_url.endswith("/cancel/job%2Fwith%20space"))
        self.assertIsNone(request.data)
        self.assertEqual(result.status, "cancelled")
        self.assertTrue(result.success)

    def test_cancel_result_is_machine_readable(self):
        result = CancelResult(False, 409, "already finished", "ready")
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 409)
        self.assertEqual(result.status, "ready")

    def test_queue_rejects_non_object_and_missing_job_id(self):
        for body in ([], {"ok": True}, {"ok": "true", "job_id": "job-1"}):
            with self.subTest(body=body), \
                    patch("urllib.request.urlopen", return_value=self._response(body)):
                result = queue_book(1, 7)
                self.assertFalse(result.success)
                self.assertIn("invalid response", result.error_message.lower())

    def test_cancel_accepts_only_cancelled_success_statuses(self):
        for status in ("cancelled", "already_cancelled"):
            with self.subTest(status=status), \
                    patch("urllib.request.urlopen",
                          return_value=self._response({"ok": True, "status": status})):
                result = cancel_job("job-1")
                self.assertTrue(result.success)
                self.assertEqual(result.status, status)
        with patch("urllib.request.urlopen",
                   return_value=self._response({"ok": True, "status": "ready"})):
            result = cancel_job("job-1")
        self.assertFalse(result.success)
        self.assertIn("invalid response", result.error_message.lower())

    def test_transport_rejects_invalid_identifier_types_without_request(self):
        with patch("urllib.request.urlopen") as open_url:
            queue_result = queue_book("1", 7)
            cancel_result = cancel_job(123)
        self.assertFalse(queue_result.success)
        self.assertFalse(cancel_result.success)
        open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
