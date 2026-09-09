#!/usr/bin/env python3
"""Unit tests for fetch_source_from_opendrive.py"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "aubooks"))

from fetch_source_from_opendrive import (
    compute_opendrive_path,
    fetch_source,
    lookup_format,
)


class TestComputeOpendrivePath(unittest.TestCase):
    """Test bucket calculation and remote path generation."""

    def test_book_1(self):
        self.assertEqual(compute_opendrive_path(1, "FB2"), "calibre-books-v2/1/1.fb2")

    def test_book_99(self):
        self.assertEqual(compute_opendrive_path(99, "FB2"), "calibre-books-v2/1/99.fb2")

    def test_book_100(self):
        self.assertEqual(compute_opendrive_path(100, "FB2"), "calibre-books-v2/100/100.fb2")

    def test_book_128_epub(self):
        self.assertEqual(compute_opendrive_path(128, "EPUB"), "calibre-books-v2/100/128.epub")

    def test_book_1000(self):
        self.assertEqual(compute_opendrive_path(1000, "FB2"), "calibre-books-v2/1000/1000.fb2")

    def test_book_27408(self):
        self.assertEqual(compute_opendrive_path(27408, "FB2"), "calibre-books-v2/27400/27408.fb2")

    def test_book_37444(self):
        self.assertEqual(compute_opendrive_path(37444, "FB2"), "calibre-books-v2/37400/37444.fb2")

    def test_uppercase_format(self):
        self.assertEqual(compute_opendrive_path(100, "FB2"), "calibre-books-v2/100/100.fb2")
        self.assertEqual(compute_opendrive_path(100, "EPUB"), "calibre-books-v2/100/100.epub")

    def test_lowercase_format(self):
        self.assertEqual(compute_opendrive_path(100, "fb2"), "calibre-books-v2/100/100.fb2")


class TestLookupFormat(unittest.TestCase):
    """Test metadata.db format lookup."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "metadata.db"
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, path TEXT);
            CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER, format TEXT, name TEXT);
            INSERT INTO books VALUES (1, 'Test Book', 'Author/Test Book (1)');
            INSERT INTO data VALUES (1, 1, 'FB2', 'Test Book - Author');
            INSERT INTO books VALUES (2, 'EPUB Book', 'Author/EPUB Book (2)');
            INSERT INTO data VALUES (2, 2, 'EPUB', 'EPUB Book - Author');
            INSERT INTO books VALUES (3, 'Multi Format', 'Author/Multi (3)');
            INSERT INTO data VALUES (3, 3, 'FB2', 'Multi - Author');
            INSERT INTO data VALUES (4, 3, 'EPUB', 'Multi - Author');
            INSERT INTO books VALUES (999, 'No Format', 'Author/No Format (999)');
            INSERT INTO data VALUES (10, 999, 'PDF', 'No Format - Author');
        """)
        conn.close()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_fb2_book(self):
        fmt, err = lookup_format(1, self.db_path)
        self.assertIsNone(err)
        self.assertEqual(fmt, "FB2")

    def test_epub_book(self):
        fmt, err = lookup_format(2, self.db_path)
        self.assertIsNone(err)
        self.assertEqual(fmt, "EPUB")

    def test_multi_format_prefers_fb2(self):
        fmt, err = lookup_format(3, self.db_path)
        self.assertIsNone(err)
        self.assertEqual(fmt, "FB2")

    def test_book_not_found(self):
        fmt, err = lookup_format(99999, self.db_path)
        self.assertIsNone(fmt)
        self.assertIn("not found", err)

    def test_no_format(self):
        fmt, err = lookup_format(999, self.db_path)
        self.assertIsNone(fmt)
        self.assertIn("no supported format", err)

    def test_missing_db(self):
        fmt, err = lookup_format(1, Path("/nonexistent/db.db"))
        self.assertIsNone(fmt)
        self.assertIn("not found", err)


class TestFetchSource(unittest.TestCase):
    """Test fetch_source with mocked rclone."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "metadata.db"
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, path TEXT);
            CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER, format TEXT, name TEXT);
            INSERT INTO books VALUES (1, 'Test FB2', 'Author/Test (1)');
            INSERT INTO data VALUES (1, 1, 'FB2', 'Test - Author');
            INSERT INTO books VALUES (2, 'Test EPUB', 'Author/Test (2)');
            INSERT INTO data VALUES (2, 2, 'EPUB', 'Test - Author');
            INSERT INTO books VALUES (999, 'No Format', 'Author/No Format (999)');
            INSERT INTO data VALUES (10, 999, 'PDF', 'No Format - Author');
        """)
        conn.close()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_book_not_in_metadata(self):
        path, err, code = fetch_source(99999, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 4)

    def test_no_format(self):
        path, err, code = fetch_source(999, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 5)

    def test_dest_not_exists(self):
        path, err, code = fetch_source(1, "/nonexistent/dir", db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 1)

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_rclone_success(self, mock_run):
        # Create a fake downloaded file
        def side_effect(cmd, **kwargs):
            # cmd = ["rclone", "copyto", "remote:path", local_path, "--no-traverse"]
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(b"fake fb2 content")
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        path, err, code = fetch_source(1, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(err)
        self.assertEqual(code, 0)
        self.assertTrue(path.endswith("source.fb2"))
        self.assertTrue(os.path.isfile(path))

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_rclone_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError

        path, err, code = fetch_source(1, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 7)
        self.assertIn("rclone not found", err)

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_rclone_remote_missing(self, mock_run):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "ERROR 404: file not found"
        mock_run.return_value = result

        path, err, code = fetch_source(1, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 6)
        self.assertIn("not available", err)

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_rclone_error(self, mock_run):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "some rclone error"
        mock_run.return_value = result

        path, err, code = fetch_source(1, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 7)

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_zero_byte_file(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            # Create empty file
            with open(local_path, "wb") as f:
                pass
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        path, err, code = fetch_source(1, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 7)
        self.assertIn("empty", err)

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_rclone_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="rclone", timeout=120)

        path, err, code = fetch_source(1, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(path)
        self.assertEqual(code, 7)
        self.assertIn("timed out", err)

    @patch("fetch_source_from_opendrive.subprocess.run")
    def test_epub_download(self, mock_run):
        def side_effect(cmd, **kwargs):
            local_path = cmd[3]
            with open(local_path, "wb") as f:
                f.write(b"fake epub content")
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        path, err, code = fetch_source(2, self.tmp_dir, db_path=self.db_path)
        self.assertIsNone(err)
        self.assertEqual(code, 0)
        self.assertTrue(path.endswith("source.epub"))


if __name__ == "__main__":
    unittest.main()
