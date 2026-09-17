"""Regression tests for ready audiobook downloads from OpenDrive."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cps.aubooks_audio import (
    AudioRemoteMissingError,
    AudioRemoteUnavailableError,
    AudioTempStorageError,
    InvalidAudioPathError,
    audiobook_accel_uri,
    fetch_audiobook_from_opendrive,
    schedule_audiobook_cleanup,
)


class TestFetchAudiobookFromOpendrive(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.mkdtemp(prefix="aubooks_test_audio_root_")
        self.env = patch.dict(
            os.environ, {"AUBOOKS_AUDIO_TEMP_DIR": self.temp_root}, clear=False
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def _successful_run(self, data=b"m4b-data"):
        def run(command, **kwargs):
            Path(command[3]).write_bytes(data)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        return run

    @patch("cps.aubooks_audio.shutil.disk_usage",
           return_value=SimpleNamespace(free=10 * 1024 * 1024 * 1024))
    @patch("cps.aubooks_audio.subprocess.run")
    def test_ready_remote_uses_trusted_path_and_explicit_config(self, run, _disk_usage):
        run.side_effect = self._successful_run()
        env = {
            "AUBOOKS_BOOKS_REMOTE": "opendrive_content:calibre-books-v2",
            "RCLONE_CONFIG": "/opt/calibre-web/config/rclone/rclone.conf",
        }
        with patch.dict(os.environ, env, clear=False):
            local_path, cleanup = fetch_audiobook_from_opendrive(
                "Audiobooks/2026/09/test.m4b", 8
            )

        command = run.call_args.args[0]
        self.assertEqual(
            command[2], "opendrive_content:Audiobooks/2026/09/test.m4b"
        )
        self.assertEqual(
            run.call_args.kwargs["env"]["RCLONE_CONFIG"],
            "/opt/calibre-web/config/rclone/rclone.conf",
        )
        self.assertEqual(Path(local_path).read_bytes(), b"m4b-data")
        self.assertRegex(
            audiobook_accel_uri(local_path),
            r"^/static/aubooks-audio/download_[^/]+/test\.m4b$",
        )
        temp_dir = Path(local_path).parent
        cleanup()
        self.assertFalse(temp_dir.exists())
        cleanup()

    @patch("cps.aubooks_audio.subprocess.run")
    def test_invalid_stored_path_is_rejected_before_rclone(self, run):
        invalid_paths = (
            "../secret.m4b",
            "/Audiobooks/secret.m4b",
            "other:remote.m4b",
            "Audiobooks/../../secret.m4b",
            "Audiobooks/2026/09/file.mp3",
            "Audiobooks\\2026\\09\\file.m4b",
        )
        for remote_path in invalid_paths:
            with self.subTest(remote_path=remote_path):
                with self.assertRaises(InvalidAudioPathError):
                    fetch_audiobook_from_opendrive(remote_path, 1)
        run.assert_not_called()

    @patch("cps.aubooks_audio.shutil.disk_usage",
           return_value=SimpleNamespace(free=10 * 1024 * 1024 * 1024))
    @patch("cps.aubooks_audio.subprocess.run")
    def test_remote_missing_cleans_temp(self, run, _disk_usage):
        run.return_value = SimpleNamespace(
            returncode=1, stdout="", stderr="ERROR 404: file not found"
        )
        temp_dir = tempfile.mkdtemp(prefix="aubooks_test_missing_")
        with patch("cps.aubooks_audio.tempfile.mkdtemp", return_value=temp_dir):
            with self.assertRaises(AudioRemoteMissingError):
                fetch_audiobook_from_opendrive(
                    "Audiobooks/2026/09/missing.m4b", 10
                )
        self.assertFalse(Path(temp_dir).exists())

    @patch("cps.aubooks_audio.shutil.disk_usage",
           return_value=SimpleNamespace(free=10 * 1024 * 1024 * 1024))
    @patch("cps.aubooks_audio.subprocess.run")
    def test_rclone_failure_cleans_temp(self, run, _disk_usage):
        run.return_value = SimpleNamespace(
            returncode=1, stdout="", stderr="storage unavailable"
        )
        temp_dir = tempfile.mkdtemp(prefix="aubooks_test_failure_")
        with patch("cps.aubooks_audio.tempfile.mkdtemp", return_value=temp_dir):
            with self.assertRaises(AudioRemoteUnavailableError):
                fetch_audiobook_from_opendrive(
                    "Audiobooks/2026/09/test.m4b", 10
                )
        self.assertFalse(Path(temp_dir).exists())

    @patch("cps.aubooks_audio.shutil.disk_usage",
           return_value=SimpleNamespace(free=10 * 1024 * 1024 * 1024))
    @patch("cps.aubooks_audio.subprocess.run")
    def test_rclone_timeout_cleans_temp(self, run, _disk_usage):
        run.side_effect = subprocess.TimeoutExpired("rclone", 1800)
        temp_dir = tempfile.mkdtemp(prefix="aubooks_test_timeout_")
        with patch("cps.aubooks_audio.tempfile.mkdtemp", return_value=temp_dir):
            with self.assertRaises(AudioRemoteUnavailableError):
                fetch_audiobook_from_opendrive(
                    "Audiobooks/2026/09/test.m4b", 10
                )
        self.assertFalse(Path(temp_dir).exists())

    @patch("cps.aubooks_audio.shutil.disk_usage",
           return_value=SimpleNamespace(free=1))
    @patch("cps.aubooks_audio.subprocess.run")
    def test_insufficient_temp_space_fails_before_rclone(self, run, _disk_usage):
        with self.assertRaises(AudioTempStorageError):
            fetch_audiobook_from_opendrive(
                "Audiobooks/2026/09/test.m4b", 238395628
            )
        run.assert_not_called()

    @patch("cps.aubooks_audio.shutil.disk_usage",
           return_value=SimpleNamespace(free=10 * 1024 * 1024 * 1024))
    @patch("cps.aubooks_audio.subprocess.run")
    def test_size_mismatch_is_rejected_and_cleaned(self, run, _disk_usage):
        run.side_effect = self._successful_run(b"short")
        with self.assertRaises(AudioRemoteUnavailableError):
            fetch_audiobook_from_opendrive(
                "Audiobooks/2026/09/test.m4b", 238395628
            )

    def test_scheduled_cleanup_runs(self):
        marker = Path(self.temp_root) / "marker"
        marker.write_text("temporary", encoding="ascii")
        timer = schedule_audiobook_cleanup(marker.unlink, delay=0.01)
        timer.join(timeout=1)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
