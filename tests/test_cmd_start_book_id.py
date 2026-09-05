#!/usr/bin/env python3
"""Regression tests for cmd_start_book_id OpenDrive fallback logic.

Tests that find_source.py exit code 5 triggers OpenDrive fallback,
while exit code 4 and unexpected codes do not.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


BIN_DIR = Path(__file__).resolve().parent.parent.parent / "bin"
REMOTE_SH = BIN_DIR / "aubook-remote.sh"


def _run_test(
    book_id: int,
    find_rc: int,
    fetch_rc: int = 0,
    fetch_creates_file: bool = True,
    find_source_exists: bool = True,
    fetch_exists: bool = True,
    publish: bool = False,
) -> tuple[int, str, str]:
    """Run cmd_start_book_id with mocked scripts.

    Returns (exit_code, stdout, stderr).
    """
    with tempfile.TemporaryDirectory() as tmp:
        jobs_dir = Path(tmp) / "jobs"
        jobs_dir.mkdir()

        # Mock find_source.py
        find_source = Path(tmp) / "find_source.py"
        if find_source_exists:
            find_source.write_text(
                f"#!/usr/bin/env python3\n"
                f"import sys\n"
                f"sys.exit({find_rc})\n"
            )
            find_source.chmod(0o755)

        # Mock fetch_source_from_opendrive.py
        fetch_source = Path(tmp) / "fetch_source_from_opendrive.py"
        if fetch_exists:
            if fetch_creates_file and fetch_rc == 0:
                fetch_source.write_text(
                    "#!/usr/bin/env python3\n"
                    "import sys, os\n"
                    "dest = sys.argv[2]\n"
                    "out = os.path.join(dest, 'source.fb2')\n"
                    "with open(out, 'w') as f: f.write('fake')\n"
                    "print(out)\n"
                )
            else:
                fetch_source.write_text(
                    f"#!/usr/bin/env python3\n"
                    f"import sys\n"
                    f"sys.exit({fetch_rc})\n"
                )
            fetch_source.chmod(0o755)

        # Mock audio_index_ops.py
        aio = Path(tmp) / "audio_index_ops.py"
        aio.write_text("#!/usr/bin/env python3\nprint('STATUS=')\n")
        aio.chmod(0o755)

        # Mock aubook-publish-opendrive.py (for publish flag)
        publish_script = Path(tmp) / "aubook-publish-opendrive.py"
        publish_script.write_text("#!/usr/bin/env python3\nprint('PUBLISH OK')\n")
        publish_script.chmod(0o755)

        env = os.environ.copy()
        env.update({
            "BASE_AUBOOKS_DIR": str(tmp),
            "AUBOOK_BIN": str(tmp),
            "VENV_PYTHON": "/usr/bin/python3",
            "JOBS": str(jobs_dir),
            "FIND_SOURCE": str(find_source) if find_source_exists else "",
            "FETCH_SOURCE": str(fetch_source) if fetch_exists else "",
            "AUDIO_INDEX_OPS": str(aio),
            "PUBLISH": str(publish_script),
        })

        pub_arg = " publish" if publish else ""
        script = f"""
source <(head -952 "{REMOTE_SH}")

# Override cmd_start to just print success
cmd_start() {{
    echo "JOB=test_job"
    return 0
}}

cmd_start_book_id {book_id} 1{pub_arg}
"""
        result = subprocess.run(
            ["bash", "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        return result.returncode, result.stdout, result.stderr


class TestExitCode5TriggersFetch(unittest.TestCase):
    """Exit code 5 from find_source.py must trigger OpenDrive fetch."""

    def test_exit5_calls_fetch_and_cmd_start(self):
        rc, stdout, stderr = _run_test(
            book_id=27408, find_rc=5, fetch_rc=0, fetch_creates_file=True,
        )
        self.assertNotEqual(rc, 5, f"Should not exit 5; stderr={stderr}")
        self.assertIn("JOB=", stdout, f"cmd_start should be called; stderr={stderr}")

    def test_exit5_fetch_script_missing(self):
        rc, stdout, stderr = _run_test(
            book_id=27408, find_rc=5, fetch_exists=False,
        )
        self.assertEqual(rc, 7, f"Should exit 7; stderr={stderr}")

    def test_exit5_fetch_fails(self):
        rc, stdout, stderr = _run_test(
            book_id=27408, find_rc=5, fetch_rc=1,
        )
        self.assertEqual(rc, 7, f"Should exit 7; stderr={stderr}")

    def test_exit5_fetch_remote_missing(self):
        rc, stdout, stderr = _run_test(
            book_id=27408, find_rc=5, fetch_rc=6,
        )
        self.assertEqual(rc, 6, f"Should exit 6; stderr={stderr}")

    def test_exit5_with_publish(self):
        rc, stdout, stderr = _run_test(
            book_id=27408, find_rc=5, fetch_rc=0,
            fetch_creates_file=True, publish=True,
        )
        self.assertNotEqual(rc, 5, f"Should not exit 5; stderr={stderr}")
        self.assertIn("JOB=", stdout, f"cmd_start should be called; stderr={stderr}")


class TestExitCode4IsFatal(unittest.TestCase):
    """Exit code 4 from find_source.py must NOT trigger OpenDrive fetch."""

    def test_exit4_fatal(self):
        rc, stdout, stderr = _run_test(book_id=99999, find_rc=4)
        self.assertEqual(rc, 4, f"Should exit 4; stderr={stderr}")
        self.assertNotIn("JOB=", stdout, "cmd_start should NOT be called")


class TestExitCode0LocalFile(unittest.TestCase):
    """Exit code 0 with valid file must use local source, no OpenDrive."""

    def test_local_file_used(self):
        rc, stdout, stderr = _run_test(book_id=100, find_rc=0)
        self.assertEqual(rc, 0, f"Should exit 0; stderr={stderr}")
        self.assertIn("JOB=", stdout, "cmd_start should be called")


class TestUnexpectedExitCode(unittest.TestCase):
    """Unexpected exit codes should fall through to OpenDrive."""

    def test_exit1_falls_through(self):
        rc, stdout, stderr = _run_test(
            book_id=999, find_rc=1, fetch_rc=0, fetch_creates_file=True,
        )
        self.assertEqual(rc, 0, f"Should succeed via OpenDrive; stderr={stderr}")
        self.assertIn("JOB=", stdout, "cmd_start should be called")


if __name__ == "__main__":
    unittest.main()
