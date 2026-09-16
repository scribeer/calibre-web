"""Tests for OpenDrive download fallback (ebook + audio)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestComputeOpendrivePath(unittest.TestCase):
    """Test cps/opendrive.py compute_opendrive_path."""

    def test_book_1(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(1, "FB2"), "calibre-books-v2/1/1.fb2")

    def test_book_99(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(99, "FB2"), "calibre-books-v2/1/99.fb2")

    def test_book_100(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(100, "FB2"), "calibre-books-v2/100/100.fb2")

    def test_book_100_epub(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(100, "EPUB"), "calibre-books-v2/100/100.epub")

    def test_book_1000(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(1000, "FB2"), "calibre-books-v2/1000/1000.fb2")

    def test_lowercase_format(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(100, "fb2"), "calibre-books-v2/100/100.fb2")

    def test_book_10_bucket(self):
        from cps.opendrive import compute_opendrive_path
        self.assertEqual(compute_opendrive_path(10, "FB2"), "calibre-books-v2/1/10.fb2")


class TestOpendriveCoverPath(unittest.TestCase):
    """Test cps/opendrive.py _opendrive_cover_path."""

    def test_book_1(self):
        from cps.opendrive import _opendrive_cover_path
        self.assertEqual(_opendrive_cover_path(1), "calibre-books-v2/1/1.jpg")

    def test_book_10(self):
        from cps.opendrive import _opendrive_cover_path
        self.assertEqual(_opendrive_cover_path(10), "calibre-books-v2/1/10.jpg")

    def test_book_100(self):
        from cps.opendrive import _opendrive_cover_path
        self.assertEqual(_opendrive_cover_path(100), "calibre-books-v2/100/100.jpg")

    def test_book_99999(self):
        from cps.opendrive import _opendrive_cover_path
        self.assertEqual(_opendrive_cover_path(99999), "calibre-books-v2/99900/99999.jpg")


class TestFetchEbookFromOpendrive(unittest.TestCase):
    """Test cps/opendrive.py fetch_ebook_from_opendrive with mocked rclone."""

    @patch("cps.opendrive.subprocess.run")
    def test_success(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(b"fake fb2 content")
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_ebook_from_opendrive
        local_path, cleanup = fetch_ebook_from_opendrive(10, "FB2")

        self.assertIsNotNone(local_path)
        self.assertTrue(os.path.isfile(local_path))
        self.assertTrue(local_path.endswith("10.fb2"))
        self.assertTrue(callable(cleanup))

        cleanup()
        self.assertFalse(os.path.exists(local_path))

    @patch("cps.opendrive.subprocess.run")
    def test_rclone_not_found(self, mock_run):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "ERROR 404: file not found"
        mock_run.return_value = result

        from cps.opendrive import fetch_ebook_from_opendrive
        local_path, cleanup = fetch_ebook_from_opendrive(999, "FB2")

        self.assertIsNone(local_path)
        self.assertIsNone(cleanup)

    @patch("cps.opendrive.subprocess.run")
    def test_empty_file(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                pass
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_ebook_from_opendrive
        local_path, cleanup = fetch_ebook_from_opendrive(10, "FB2")

        self.assertIsNone(local_path)

    @patch("cps.opendrive.subprocess.run")
    def test_cleanup_removes_file_and_dir(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(b"test")
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_ebook_from_opendrive
        local_path, cleanup = fetch_ebook_from_opendrive(10, "FB2")
        parent_dir = os.path.dirname(local_path)

        self.assertTrue(os.path.isfile(local_path))
        self.assertTrue(os.path.isdir(parent_dir))

        cleanup()
        self.assertFalse(os.path.exists(local_path))
        self.assertFalse(os.path.isdir(parent_dir))


class TestFetchCoverFromOpendrive(unittest.TestCase):
    """Test cps/opendrive.py fetch_cover_from_opendrive with mocked rclone."""

    def setUp(self):
        from cps.opendrive import _cover_cache
        _cover_cache.clear()

    def tearDown(self):
        from cps.opendrive import _cover_cache
        _cover_cache.clear()

    @patch("cps.opendrive.subprocess.run")
    def test_cover_exists(self, mock_run):
        JPEG_HEADER = b"\xff\xd8\xff\xe0"
        fake_data = JPEG_HEADER + b"\x00" * 100

        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(fake_data)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_cover_from_opendrive
        data, content_type = fetch_cover_from_opendrive(1)

        self.assertIsNotNone(data)
        self.assertEqual(len(data), 104)
        self.assertEqual(content_type, "image/jpeg")
        self.assertTrue(data.startswith(JPEG_HEADER))

    @patch("cps.opendrive.subprocess.run")
    def test_cover_not_found(self, mock_run):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "ERROR 404: file not found"
        mock_run.return_value = result

        from cps.opendrive import fetch_cover_from_opendrive
        data, content_type = fetch_cover_from_opendrive(999999)

        self.assertIsNone(data)
        self.assertIsNone(content_type)

    @patch("cps.opendrive.subprocess.run")
    def test_rclone_config_passed(self, mock_run):
        import os
        os.environ["RCLONE_CONFIG"] = "/tmp/test.conf"

        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_cover_from_opendrive
        fetch_cover_from_opendrive(1)

        env = mock_run.call_args.kwargs.get("env")
        self.assertIsNotNone(env)
        self.assertEqual(env["RCLONE_CONFIG"], "/tmp/test.conf")

        del os.environ["RCLONE_CONFIG"]

    @patch("cps.opendrive.subprocess.run")
    def test_rclone_failure_returns_none(self, mock_run):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "some rclone error"
        mock_run.return_value = result

        from cps.opendrive import fetch_cover_from_opendrive
        data, content_type = fetch_cover_from_opendrive(1)

        self.assertIsNone(data)
        self.assertIsNone(content_type)

    @patch("cps.opendrive.subprocess.run")
    def test_rclone_timeout_returns_none(self, mock_run):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="rclone", timeout=15)

        from cps.opendrive import fetch_cover_from_opendrive
        data, content_type = fetch_cover_from_opendrive(1)

        self.assertIsNone(data)
        self.assertIsNone(content_type)

    @patch("cps.opendrive.subprocess.run")
    def test_empty_file_returns_none(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                pass
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_cover_from_opendrive
        data, content_type = fetch_cover_from_opendrive(1)

        self.assertIsNone(data)

    @patch("cps.opendrive.subprocess.run")
    def test_cache_hit_skips_rclone(self, mock_run):
        import time
        from cps.opendrive import fetch_cover_from_opendrive, _cover_cache

        _cover_cache[42] = {
            "data": b"\xff\xd8\xff\xe0cached",
            "content_type": "image/jpeg",
            "ts": time.time(),
        }

        data, content_type = fetch_cover_from_opendrive(42)

        mock_run.assert_not_called()
        self.assertEqual(data, b"\xff\xd8\xff\xe0cached")
        self.assertEqual(content_type, "image/jpeg")

    @patch("cps.opendrive.subprocess.run")
    def test_correct_remote_path_for_book_1(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        from cps.opendrive import fetch_cover_from_opendrive
        fetch_cover_from_opendrive(1)

        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "rclone")
        self.assertEqual(cmd[1], "copyto")
        self.assertEqual(cmd[2], "opendrive_content:calibre-books-v2/1/1.jpg")
        self.assertIn("--no-traverse", cmd)


class TestAudioOpendrivePath(unittest.TestCase):
    """Test audio download uses od_path from DB, not computed path."""

    def test_opendrive_path_used(self):
        """download_audiobook should use opendrive_path from audio.db."""
        from cps.aubooks_audio import get_audio_record
        import sqlite3

        tmp = Path(tempfile.mktemp(suffix=".db"))
        try:
            from audio_index import init_db
            sys_path_added = False
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aubooks"))
                sys_path_added = True
            except Exception:
                pass
            init_db(tmp)
            conn = sqlite3.connect(str(tmp))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (42, 'ready', 'test.m4b', 'Audiobooks/2026/09/test.m4b', 'abc', 1000, datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            with patch("cps.aubooks_audio._get_db_path", return_value=tmp):
                rec = get_audio_record(42)
                self.assertIsNotNone(rec)
                self.assertEqual(rec["opendrive_path"], "Audiobooks/2026/09/test.m4b")
                self.assertEqual(rec["status"], "ready")
        finally:
            tmp.unlink(missing_ok=True)

    def test_od_path_not_used_as_computed(self):
        """Verify opendrive_path is not overridden by computed calibre-books-v2 path."""
        from cps.aubooks_audio import get_audio_record
        import sqlite3

        tmp = Path(tempfile.mktemp(suffix=".db"))
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aubooks"))
            from audio_index import init_db
            init_db(tmp)
            conn = sqlite3.connect(str(tmp))
            conn.execute(
                "INSERT INTO audio (book_id, status, filename, opendrive_path, sha256, filesize, created_at, updated_at) "
                "VALUES (42, 'ready', 'test.m4b', 'Audiobooks/2026/09/test.m4b', 'abc', 1000, datetime('now'), datetime('now'))"
            )
            conn.commit()
            conn.close()

            with patch("cps.aubooks_audio._get_db_path", return_value=tmp):
                rec = get_audio_record(42)
                od_path = rec.get("opendrive_path")
                # Must be the actual od_path, not a computed calibre-books-v2 path
                self.assertTrue(od_path.startswith("Audiobooks/"))
                self.assertNotIn("calibre-books-v2", od_path)
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
