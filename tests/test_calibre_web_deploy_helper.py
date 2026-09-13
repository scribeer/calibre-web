"""Hermetic contract tests for the production Calibre-Web deploy stack."""

import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest


HELPER = Path(__file__).resolve().parent.parent / "deploy" / "vps2" / "deploy-calibre-web-release.sh"
DISPATCHER = Path(__file__).resolve().parent.parent / "deploy" / "vps2" / "aubooks-deploy-dispatcher.sh"
ROOT_WRAPPER = Path(__file__).resolve().parent.parent / "deploy" / "vps2" / "aubooks-deploy-root.sh"
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

    def test_bundle_symlink_rejected(self):
        link = self.base / "symlink-bundle"
        link.symlink_to(self.bundle)
        result = self.run_helper("--bundle-dir", str(link), "--commit-sha", VALID_SHA)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not be a symlink", result.stderr)

    def test_unknown_argument_rejected(self):
        result = self.run_helper(
            "--bundle-dir", str(self.bundle),
            "--commit-sha", VALID_SHA,
            "--evil-flag", "value",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown argument", result.stderr)

    def test_bundle_dir_required(self):
        result = subprocess.run(
            ["bash", str(HELPER), "--commit-sha", VALID_SHA],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--bundle-dir", result.stderr)

    def test_commit_sha_required(self):
        result = subprocess.run(
            ["bash", str(HELPER), "--bundle-dir", str(self.bundle)],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--commit-sha", result.stderr)


class DispatcherTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.staging = self.base / "staging"
        self.staging.mkdir()
        self.wheel_name = "calibreweb-0.6.28b0-py3-none-any.whl"
        self.env = os.environ.copy()
        self.env.update({
            "AUBOOKS_DEPLOY_USER": "nobody",
            "STAGING_BASE": str(self.staging),
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_dispatcher(self, original_command, stdin_data=None):
        env = self.env.copy()
        env["SSH_ORIGINAL_COMMAND"] = original_command
        return subprocess.run(
            ["bash", str(DISPATCHER)],
            env=env,
            input=stdin_data,
            capture_output=True,
            timeout=15,
        )

    def make_tar(self, files):
        tar_path = self.base / "bundle.tar"
        with tarfile.open(tar_path, "w") as tar:
            for name, data in files.items():
                import io
                info = tarfile.TarInfo(name=name)
                if isinstance(data, bytes):
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
                else:
                    encoded = data.encode("utf-8")
                    info.size = len(encoded)
                    tar.addfile(info, io.BytesIO(encoded))
        return tar_path.read_bytes()

    def test_empty_command_rejected(self):
        result = self.run_dispatcher("")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"SSH_ORIGINAL_COMMAND is empty", result.stderr)

    def test_invalid_sha_rejected(self):
        result = self.run_dispatcher("upload not-a-sha")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"40 lowercase hexadecimal", result.stderr)

    def test_uppercase_sha_rejected(self):
        result = self.run_dispatcher("upload " + "A" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"40 lowercase hexadecimal", result.stderr)

    def test_extra_argument_rejected(self):
        result = self.run_dispatcher("upload {} extra".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"too many arguments", result.stderr)

    def test_unknown_verb_rejected(self):
        result = self.run_dispatcher("destroy {}".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"unknown verb", result.stderr)

    def test_upload_valid_bundle_accepted(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": "abc  {}\n".format(self.wheel_name),
            "artifact-manifest.json": "{}",
            "deploy-request.json": "{}",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("upload {} OK".format(VALID_SHA).encode(), result.stdout)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertTrue(bundle.is_dir())
        self.assertEqual(len(list(bundle.iterdir())), 4)

    def test_upload_rejects_extra_file(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": "abc  {}\n".format(self.wheel_name),
            "artifact-manifest.json": "{}",
            "deploy-request.json": "{}",
            "evil.txt": "malicious",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertEqual(sorted(f.name for f in bundle.iterdir()), sorted([
            "SHA256SUMS",
            "artifact-manifest.json",
            "deploy-request.json",
            self.wheel_name,
        ]))

    def test_upload_rejects_traversal_path(self):
        tar_data = self.make_tar({
            "../etc/passwd": "root:x:0:0:",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)

    def test_upload_rejects_symlink(self):
        tar_path = self.base / "bundle.tar"
        with tarfile.open(tar_path, "w") as tar:
            import io
            link = tarfile.TarInfo(name="evil-symlink")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tar.addfile(link)
        tar_data = tar_path.read_bytes()
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)

    def test_upload_rejects_absolute_path(self):
        tar_path = self.base / "bundle.tar"
        with tarfile.open(tar_path, "w") as tar:
            import io
            info = tarfile.TarInfo(name="/etc/passwd")
            info.size = 5
            tar.addfile(info, io.BytesIO(b"rootxx"))
        tar_data = tar_path.read_bytes()
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)

    def test_deploy_before_upload_rejected(self):
        result = self.run_dispatcher("deploy {}".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"does not exist", result.stderr)

    def test_upload_idempotent_rejected(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": "abc  {}\n".format(self.wheel_name),
            "artifact-manifest.json": "{}",
            "deploy-request.json": "{}",
        })
        result1 = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertEqual(result1.returncode, 0, result1.stderr)
        result2 = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result2.returncode, 0)
        self.assertIn(b"already exists", result2.stderr)


class RootWrapperTest(unittest.TestCase):
    def test_script_exists_and_executable(self):
        self.assertTrue(ROOT_WRAPPER.exists())
        self.assertTrue(os.access(ROOT_WRAPPER, os.X_OK))

    def test_requires_bundle_dir_and_sha(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--bundle-dir", result.stderr)

    def test_invalid_sha_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER), "--bundle-dir", "/tmp/x", "--commit-sha", "bad"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("40 lowercase hexadecimal", result.stderr)

    def test_path_mismatch_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER),
             "--bundle-dir", "/tmp/wrong-path",
             "--commit-sha", VALID_SHA],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("path mismatch", result.stderr)

    def test_unknown_argument_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER),
             "--bundle-dir", "/tmp/x",
             "--commit-sha", VALID_SHA,
             "--evil", "value"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown argument", result.stderr)


if __name__ == "__main__":
    unittest.main()
