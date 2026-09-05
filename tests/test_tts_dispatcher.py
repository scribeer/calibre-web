"""Tests for tts-dispatcher.py HTTP server."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from http.server import HTTPServer
import threading
import urllib.request
import urllib.error

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bin"))

# Import dispatcher module
import importlib.util
spec = importlib.util.spec_from_file_location("tts_dispatcher", str(Path(__file__).parent.parent.parent / "bin" / "tts-dispatcher.py"))
dispatcher_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatcher_mod)


def _tmp_db():
    return Path(tempfile.mktemp(suffix=".db"))


class TestValidation(unittest.TestCase):
    """Test book_id validation logic."""

    def _post(self, body_dict, port):
        payload = json.dumps(body_dict).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/queue",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read()), exc.code

    def _post_raw(self, raw_bytes, port):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/queue",
            data=raw_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read()), exc.code

    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), dispatcher_mod._Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()

    def test_valid_book_id(self):
        with patch.object(dispatcher_mod, "_dispatch", return_value={"ok": True, "book_id": 42, "job_id": "JOB_42"}):
            data, status = self._post({"book_id": 42}, self.port)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["book_id"], 42)

    def test_zero_rejected(self):
        data, status = self._post({"book_id": 0}, self.port)
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_negative_rejected(self):
        data, status = self._post({"book_id": -5}, self.port)
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_string_rejected(self):
        data, status = self._post({"book_id": "42"}, self.port)
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_bool_rejected(self):
        data, status = self._post({"book_id": True}, self.port)
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_float_rejected(self):
        data, status = self._post({"book_id": 3.14}, self.port)
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_missing_field(self):
        data, status = self._post({}, self.port)
        self.assertEqual(status, 400)
        self.assertIn("book_id", data["error"].lower())

    def test_empty_body(self):
        data, status = self._post_raw(b"", self.port)
        self.assertEqual(status, 400)

    def test_invalid_json(self):
        data, status = self._post_raw(b"not json", self.port)
        self.assertEqual(status, 400)

    def test_wrong_endpoint(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/other",
            data=b'{"book_id": 1}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                status = resp.status
        except urllib.error.HTTPError as exc:
            result = json.loads(exc.read())
            status = exc.code
        self.assertEqual(status, 404)

    def test_array_body_rejected(self):
        data, status = self._post({"book_id": [1, 2]}, self.port)
        self.assertEqual(status, 400)

    def test_null_book_id_rejected(self):
        data, status = self._post({"book_id": None}, self.port)
        self.assertEqual(status, 400)


class TestDuplicateCheck(unittest.TestCase):
    """Test audio.db duplicate protection."""

    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), dispatcher_mod._Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()

    def test_duplicate_queued(self):
        db = _tmp_db()
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE audio (book_id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("INSERT INTO audio VALUES (99, 'queued')")
        conn.commit()
        conn.close()
        with patch.object(dispatcher_mod, "AUDIO_DB", db):
            data, status = self._post({"book_id": 99})
        self.assertEqual(status, 409)
        self.assertFalse(data["ok"])
        self.assertIn("queued", data["error"].lower())
        db.unlink(missing_ok=True)

    def test_duplicate_processing(self):
        db = _tmp_db()
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE audio (book_id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("INSERT INTO audio VALUES (99, 'processing')")
        conn.commit()
        conn.close()
        with patch.object(dispatcher_mod, "AUDIO_DB", db):
            data, status = self._post({"book_id": 99})
        self.assertEqual(status, 409)
        db.unlink(missing_ok=True)

    def test_duplicate_ready(self):
        db = _tmp_db()
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE audio (book_id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("INSERT INTO audio VALUES (99, 'ready')")
        conn.commit()
        conn.close()
        with patch.object(dispatcher_mod, "AUDIO_DB", db):
            data, status = self._post({"book_id": 99})
        self.assertEqual(status, 409)
        db.unlink(missing_ok=True)

    def test_failed_allows_retry(self):
        db = _tmp_db()
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE audio (book_id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("INSERT INTO audio VALUES (99, 'failed')")
        conn.commit()
        conn.close()
        with patch.object(dispatcher_mod, "AUDIO_DB", db), \
             patch.object(dispatcher_mod, "_dispatch", return_value={"ok": True, "book_id": 99, "job_id": "J"}):
            data, status = self._post({"book_id": 99})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        db.unlink(missing_ok=True)

    def _post(self, body_dict):
        payload = json.dumps(body_dict).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/queue",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read()), exc.code


class TestDispatchMocked(unittest.TestCase):
    """Test _dispatch function with mocked subprocess."""

    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), dispatcher_mod._Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()

    def _post(self, body_dict):
        payload = json.dumps(body_dict).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/queue",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read()), resp.status
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read()), exc.code

    def test_successful_dispatch(self):
        mock_proc = MagicMock(returncode=0, stdout="OK=queued\nJOB=20260905_120000_111\n", stderr="")
        with patch.object(dispatcher_mod, "AUBOOK_REMOTE", "/bin/true"), \
             patch("subprocess.run", return_value=mock_proc):
            data, status = self._post({"book_id": 123})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["job_id"], "20260905_120000_111")

    def test_failed_dispatch(self):
        mock_proc = MagicMock(returncode=4, stdout="", stderr="not found")
        with patch.object(dispatcher_mod, "AUBOOK_REMOTE", "/bin/true"), \
             patch("subprocess.run", return_value=mock_proc):
            data, status = self._post({"book_id": 999})
        self.assertEqual(status, 500)
        self.assertFalse(data["ok"])
        self.assertIn("not found", data["error"].lower())

    def test_pipeline_not_found(self):
        with patch.object(dispatcher_mod, "AUBOOK_REMOTE", "/nonexistent/path"):
            data, status = self._post({"book_id": 1})
        self.assertEqual(status, 500)
        self.assertFalse(data["ok"])

    def test_subprocess_timeout(self):
        with patch.object(dispatcher_mod, "AUBOOK_REMOTE", "/bin/true"), \
             patch("subprocess.run", side_effect=dispatcher_mod.subprocess.TimeoutExpired("cmd", 30)):
            data, status = self._post({"book_id": 1})
        self.assertEqual(status, 500)
        self.assertIn("timed out", data["error"].lower())

    def test_no_shell_true(self):
        """Verify subprocess.run is called with shell=False."""
        mock_proc = MagicMock(returncode=0, stdout="JOB=test\n", stderr="")
        with patch.object(dispatcher_mod, "AUBOOK_REMOTE", "/bin/true"), \
             patch("subprocess.run", return_value=mock_proc) as mock_run:
            self._post({"book_id": 1})
        _, kwargs = mock_run.call_args
        self.assertFalse(kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main()
