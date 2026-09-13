"""Hermetic contract tests for the production Calibre-Web deploy helper."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest


HELPER = Path(__file__).resolve().parent.parent / "deploy" / "vps2" / "deploy-calibre-web-release.sh"
VALID_SHA = "a" * 40


class DeployHelperTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.root = self.base / "opt" / "calibre-web"
        self.bundle = self.base / "bundle"
        self.fake_bin = self.base / "bin"
        self.command_log = self.base / "commands.log"
        self.previous = self.root / "releases" / ("b" * 40)

        for path in (
            self.root / "config",
            self.root / "library",
            self.root / "releases",
            self.root / "backups",
            self.previous,
            self.bundle,
            self.fake_bin,
        ):
            path.mkdir(parents=True, exist_ok=True)
        (self.root / "current").symlink_to(self.previous)

        self.app_db = self.root / "config" / "app.db"
        connection = sqlite3.connect(self.app_db)
        connection.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, config_theme INTEGER)")
        connection.execute("INSERT INTO settings (id, config_theme) VALUES (1, 3)")
        connection.commit()
        connection.close()
        (self.root / "config" / "gdrive.db").write_bytes(b"gdrive")
        (self.root / "library" / "metadata.db").write_bytes(b"metadata")

        self.wheel_name = "calibreweb-0.6.28b0-py3-none-any.whl"
        self.wheel = self.bundle / self.wheel_name
        self.wheel.write_bytes(b"synthetic wheel for preflight tests")
        self.write_bundle()
        self.write_fake_commands()

        self.env = os.environ.copy()
        self.env.update({
            "AUBOOKS_DEPLOY_ROOT": str(self.root),
            "AUBOOKS_MIN_FREE_KB": "1",
            "COMMAND_LOG": str(self.command_log),
            "PATH": str(self.fake_bin) + os.pathsep + self.env["PATH"],
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_bundle(self, manifest_sha=VALID_SHA):
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        manifest = {
            "repository": "scribeer/calibre-web",
            "commit_sha": manifest_sha,
            "ref": "refs/heads/aubooks",
            "run_id": "123",
            "run_attempt": "1",
            "wheel_filename": self.wheel_name,
            "wheel_sha256": digest,
            "package_version": "0.6.28b0",
            "python_version": "3.12.14",
            "build_time_utc": "2026-09-13T00:00:00Z",
        }
        request = {
            "commit_sha": VALID_SHA,
            "wheel_filename": self.wheel_name,
            "wheel_sha256": digest,
            "github_run_id": "123",
            "github_run_attempt": "1",
            "repository": "scribeer/calibre-web",
            "requested_by": "test",
            "requested_at_utc": "2026-09-13T00:00:00Z",
            "public_url": "https://au-books.net/",
        }
        (self.bundle / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.bundle / "deploy-request.json").write_text(json.dumps(request), encoding="utf-8")
        (self.bundle / "SHA256SUMS").write_text(
            "{}  {}\n".format(digest, self.wheel_name), encoding="ascii"
        )

    def write_fake_commands(self):
        fake_id = self.fake_bin / "id"
        fake_id.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ ${1:-} == -u ]]; then printf '0\\n'; "
            "elif [[ ${1:-} == calibre-web ]]; then exit 0; "
            "else exec /usr/bin/id \"$@\"; fi\n",
            encoding="utf-8",
        )
        fake_systemctl = self.fake_bin / "systemctl"
        fake_systemctl.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ ${1:-} == cat ]]; then exit 0; fi\n"
            "if [[ ${1:-} == show ]]; then printf 'calibre-web\\n'; exit 0; fi\n"
            "printf '%s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
            "exit 0\n",
            encoding="utf-8",
        )
        for path in (fake_id, fake_systemctl):
            path.chmod(0o755)

    def run_helper(self, *arguments):
        return subprocess.run(
            ["bash", str(HELPER), *arguments],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def run_dry(self):
        return self.run_helper(
            "--bundle-dir", str(self.bundle), "--commit-sha", VALID_SHA, "--dry-run"
        )

    def tree_snapshot(self):
        snapshot = []
        for path in sorted(self.root.rglob("*")):
            relative = str(path.relative_to(self.root))
            if path.is_symlink():
                snapshot.append((relative, "symlink", os.readlink(path)))
            elif path.is_file():
                snapshot.append((relative, "file", path.read_bytes()))
            else:
                snapshot.append((relative, "directory", None))
        return snapshot

    def test_invalid_sha_rejected(self):
        result = self.run_helper("--bundle-dir", str(self.bundle), "--commit-sha", "not-a-sha")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly 40", result.stderr)

    def test_missing_bundle_rejected(self):
        result = self.run_helper(
            "--bundle-dir", str(self.base / "missing"), "--commit-sha", VALID_SHA
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bundle directory does not exist", result.stderr)

    def test_checksum_mismatch_rejected(self):
        self.wheel.write_bytes(b"tampered wheel")
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wheel checksum mismatch", result.stderr)

    def test_manifest_sha_mismatch_rejected(self):
        self.write_bundle(manifest_sha="c" * 40)
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest commit SHA", result.stderr)

    def test_legacy_layout_requires_explicit_migration(self):
        (self.root / "current").unlink()
        result = self.run_helper("--bundle-dir", str(self.bundle), "--commit-sha", VALID_SHA)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INITIAL_MIGRATION_REQUIRED", result.stderr)

    def test_dry_run_does_not_change_filesystem_or_restart_service(self):
        before = self.tree_snapshot()
        result = self.run_dry()
        after = self.tree_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)
        self.assertFalse(self.command_log.exists())
        self.assertIn("DRY_RUN:", result.stdout)

    def test_config_theme_three_is_not_changed(self):
        result = self.run_dry()
        self.assertEqual(result.returncode, 0, result.stderr)
        connection = sqlite3.connect(self.app_db)
        try:
            theme = connection.execute("SELECT config_theme FROM settings").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(theme, 3)
        self.assertIn("CONFIG_THEME_ALREADY_3", result.stdout)

    def test_rollback_plan_records_previous_release(self):
        result = self.run_dry()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROLLBACK_PREVIOUS_RELEASE={}".format(self.previous), result.stdout)


if __name__ == "__main__":
    unittest.main()
