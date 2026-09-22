"""Hermetic contract tests for the production Calibre-Web deploy stack."""

import hashlib
import io
import json
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import time
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
        self.audio_sync_dst = self.base / "home" / "foroforo" / "bin" / "sync-audio-db.sh"
        self.audio_sync_cron = self.base / "etc" / "cron.d" / "aubooks-audio-sync"
        self.tts_processor_dst = self.base / "home" / "feninf" / "bin" / "tts_processor.py"
        self.bash_env = self.base / "bash-env.sh"
        self.previous = self.root / "releases" / ("b" * 40)

        for path in (
            self.root / "config",
            self.root / "library",
            self.root / "releases",
            self.root / "backups",
            self.previous,
            self.bundle,
            self.fake_bin,
            self.audio_sync_dst.parent,
            self.audio_sync_cron.parent,
            self.tts_processor_dst.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.bash_env.write_text(
            "if [[ ${AUBOOKS_TEST_PATH_REWRITE:-0} == 1 ]]; then\n"
            "  set -T\n"
            "  __aubooks_rewrite_deploy_paths() {\n"
            "    if [[ ${FUNCNAME[1]:-} == install_audio_sync ]]; then\n"
            "      [[ ${sync_dst:-} != /home/foroforo/bin/sync-audio-db.sh ]] || sync_dst=\"$AUBOOKS_TEST_SYNC_DST\"\n"
            "      [[ ${cron_file:-} != /etc/cron.d/aubooks-audio-sync ]] || cron_file=\"$AUBOOKS_TEST_CRON_FILE\"\n"
            "    elif [[ ${FUNCNAME[1]:-} == install_tts_processor ]]; then\n"
            "      [[ ${TTS_PROCESSOR_DEST:-} != /home/feninf/bin/tts_processor.py ]] || TTS_PROCESSOR_DEST=\"$AUBOOKS_TEST_TTS_PROCESSOR_DEST\"\n"
            "    fi\n"
            "  }\n"
            "  trap __aubooks_rewrite_deploy_paths DEBUG\n"
            "fi\n",
            encoding="ascii",
        )
        (self.root / "current").symlink_to(self.previous)

        self.app_db = self.root / "config" / "app.db"
        connection = sqlite3.connect(self.app_db)
        connection.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, config_theme INTEGER)")
        connection.execute("INSERT INTO settings (id, config_theme) VALUES (1, 3)")
        connection.commit()
        connection.close()
        self.gdrive_db = self.root / "config" / "gdrive.db"
        with sqlite3.connect(self.gdrive_db) as connection:
            connection.execute("CREATE TABLE state (value TEXT)")
            connection.execute("INSERT INTO state VALUES ('gdrive-original')")
        self.metadata_db = self.root / "library" / "metadata.db"
        with sqlite3.connect(self.metadata_db) as connection:
            connection.execute("CREATE TABLE books (title TEXT)")
            connection.execute("INSERT INTO books VALUES ('metadata-original')")
        self.service_state = self.base / "service-state"
        self.service_pid = self.base / "service-pid"
        self.cgroup_root = self.base / "cgroup"
        self.service_cgroup = self.cgroup_root / "calibre-web.service"
        self.service_cgroup.mkdir(parents=True)
        self.cgroup_processes = self.service_cgroup / "cgroup.procs"
        self.service_state.write_text("active\n", encoding="ascii")
        self.service_pid.write_text("4242\n", encoding="ascii")
        self.cgroup_processes.write_text("4242\n", encoding="ascii")

        self.wheel_name = "calibreweb-0.6.28b0-py3-none-any.whl"
        self.wheel = self.bundle / self.wheel_name
        self.wheel.write_bytes(b"synthetic wheel for preflight tests")
        self.helper_name = "deploy-calibre-web-release.sh"
        self.helper = self.bundle / self.helper_name
        self.helper.write_text("#!/usr/bin/env bash\nexit 0\n")
        self.write_bundle()
        self.write_fake_commands()

        self.env = os.environ.copy()
        self.env.update({
            "AUBOOKS_DEPLOY_ROOT": str(self.root),
            "AUBOOKS_MIN_FREE_KB": "1",
            "AUBOOKS_HEALTH_STARTUP_TIMEOUT": "5",
            "AUBOOKS_HEALTH_RETRY_INTERVAL": "1",
            "AUBOOKS_CGROUP_ROOT": str(self.cgroup_root),
            "COMMAND_LOG": str(self.command_log),
            "HEALTH_TEST_STATE_DIR": str(self.base),
            "SERVICE_STATE_FILE": str(self.service_state),
            "SERVICE_PID_FILE": str(self.service_pid),
            "APP_DB": str(self.app_db),
            "GDRIVE_DB": str(self.gdrive_db),
            "METADATA_DB": str(self.metadata_db),
            "PATH": str(self.fake_bin) + os.pathsep + self.env["PATH"],
            "AUBOOKS_TEST_PATH_REWRITE": "1",
            "AUBOOKS_TEST_SYNC_DST": str(self.audio_sync_dst),
            "AUBOOKS_TEST_CRON_FILE": str(self.audio_sync_cron),
            "AUBOOKS_TEST_TTS_PROCESSOR_DEST": str(self.tts_processor_dst),
            "BASH_ENV": str(self.bash_env),
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_bundle(self, manifest_sha=VALID_SHA):
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        helper_digest = hashlib.sha256(self.helper.read_bytes()).hexdigest()
        sync_name = "sync-audio-db.sh"
        sync_content = "#!/usr/bin/env bash\necho sync\n"
        sync_digest = hashlib.sha256(sync_content.encode("utf-8")).hexdigest()
        tts_name = "tts_processor.py"
        tts_content = "#!/usr/bin/env python3\nprint('tts')\n"
        tts_digest = hashlib.sha256(tts_content.encode("utf-8")).hexdigest()
        manifest = {
            "repository": "scribeer/calibre-web",
            "commit_sha": manifest_sha,
            "ref": "refs/heads/aubooks",
            "run_id": "123",
            "run_attempt": "1",
            "wheel_filename": self.wheel_name,
            "wheel_sha256": digest,
            "helper_filename": self.helper_name,
            "helper_sha256": helper_digest,
            "sync_filename": sync_name,
            "sync_sha256": sync_digest,
            "tts_filename": tts_name,
            "tts_sha256": tts_digest,
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
            "{}  {}\n{}  {}\n{}  {}\n{}  {}\n".format(
                digest, self.wheel_name,
                helper_digest, self.helper_name,
                sync_digest, sync_name,
                tts_digest, tts_name,
            ),
            encoding="ascii",
        )
        (self.bundle / sync_name).write_text(sync_content, encoding="utf-8")
        (self.bundle / tts_name).write_text(tts_content, encoding="utf-8")

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
            "if [[ ${1:-} == show ]]; then\n"
            "  case \" $* \" in\n"
            "    *' --property=User '*) printf 'calibre-web\\n' ;;\n"
            "    *' --property=ActiveState '*) cat \"$SERVICE_STATE_FILE\" ;;\n"
            "    *' --property=MainPID '*) cat \"$SERVICE_PID_FILE\" ;;\n"
            "    *' --property=ControlGroup '*) printf '/calibre-web.service\\n' ;;\n"
            "    *' --property=UnitFileState '*) if [[ -e $HEALTH_TEST_STATE_DIR/service-masked ]]; then printf 'masked-runtime\\n'; else printf 'enabled\\n'; fi ;;\n"
            "    *) exit 1 ;;\n"
            "  esac\n"
            "  exit 0\n"
            "fi\n"
            "printf '%s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
            "if [[ ${1:-} == mask ]]; then : > \"$HEALTH_TEST_STATE_DIR/service-masked\"; exit 0; fi\n"
            "if [[ ${1:-} == unmask ]]; then\n"
            "  [[ -z ${FAIL_UNMASK:-} ]] || exit 1\n"
            "  counter=\"$HEALTH_TEST_STATE_DIR/unmask-count\"\n"
            "  count=0; [[ -f $counter ]] && read -r count < \"$counter\"\n"
            "  count=$((count + 1)); printf '%s\\n' \"$count\" > \"$counter\"\n"
            "  /usr/bin/rm -f \"$HEALTH_TEST_STATE_DIR/service-masked\"\n"
            "  if [[ $count -eq 1 && -n ${SIGNAL_ON_FIRST_UNMASK:-} ]]; then kill -s \"$SIGNAL_ON_FIRST_UNMASK\" \"$PPID\"; fi\n"
            "  exit 0\n"
            "fi\n"
            "if [[ ${1:-} == stop ]]; then\n"
            "  counter=\"$HEALTH_TEST_STATE_DIR/stop-count\"\n"
            "  count=0; [[ -f $counter ]] && read -r count < \"$counter\"\n"
            "  count=$((count + 1)); printf '%s\\n' \"$count\" > \"$counter\"\n"
            "  if [[ -n ${STOP_LEAVES_RUNNING:-} || ( -n ${FAIL_STOP_AFTER:-} && $count -gt $FAIL_STOP_AFTER ) ]]; then exit 1; fi\n"
            "  if [[ -n ${MUTATE_DBS_ON_STOP:-} ]]; then\n"
            "    /usr/bin/python3 - \"$APP_DB\" \"$GDRIVE_DB\" \"$METADATA_DB\" <<'PY'\n"
            "import sqlite3, sys\n"
            "with sqlite3.connect(sys.argv[1]) as db: db.execute('UPDATE settings SET config_theme = 7')\n"
            "with sqlite3.connect(sys.argv[2]) as db: db.execute(\"UPDATE state SET value = 'gdrive-at-stop'\")\n"
            "with sqlite3.connect(sys.argv[3]) as db: db.execute(\"UPDATE books SET title = 'metadata-at-stop'\")\n"
            "PY\n"
            "  fi\n"
            "  [[ -z ${CORRUPT_GDRIVE_ON_STOP:-} ]] || printf 'not a SQLite database' > \"$GDRIVE_DB\"\n"
            "  printf 'inactive\\n' > \"$SERVICE_STATE_FILE\"\n"
            "  printf '0\\n' > \"$SERVICE_PID_FILE\"\n"
            "  if [[ -n ${REMAINING_WORKER_AFTER_STOP:-} ]]; then printf '777\\n' > \"$AUBOOKS_CGROUP_ROOT/calibre-web.service/cgroup.procs\"; else : > \"$AUBOOKS_CGROUP_ROOT/calibre-web.service/cgroup.procs\"; fi\n"
            "  [[ -z ${SIGNAL_ON_STOP:-} ]] || kill -s \"$SIGNAL_ON_STOP\" \"$PPID\"\n"
            "  [[ -z ${STOP_EXIT_NONZERO:-} ]] || exit 1\n"
            "  exit 0\n"
            "fi\n"
            "if [[ ${1:-} == start || ${1:-} == restart ]]; then\n"
            "  [[ ! -e $HEALTH_TEST_STATE_DIR/service-masked ]] || exit 1\n"
            "  counter=\"$HEALTH_TEST_STATE_DIR/start-count\"\n"
            "  count=0; [[ -f $counter ]] && read -r count < \"$counter\"\n"
            "  count=$((count + 1)); printf '%s\\n' \"$count\" > \"$counter\"\n"
            "  if [[ $count -eq 1 && -n ${MUTATE_DBS_ON_FIRST_START:-} ]]; then\n"
            "    /usr/bin/python3 - \"$APP_DB\" \"$GDRIVE_DB\" \"$METADATA_DB\" <<'PY'\n"
            "import sqlite3, sys\n"
            "with sqlite3.connect(sys.argv[1]) as db: db.execute('UPDATE settings SET config_theme = 99')\n"
            "with sqlite3.connect(sys.argv[2]) as db: db.execute(\"UPDATE state SET value = 'gdrive-mutated'\")\n"
            "with sqlite3.connect(sys.argv[3]) as db: db.execute(\"UPDATE books SET title = 'metadata-mutated'\")\n"
            "PY\n"
            "  fi\n"
            "  if [[ $count -eq 1 && -n ${CREATE_SIDECARS_ON_FIRST_START:-} ]]; then\n"
            "    : > \"$APP_DB-wal\"; : > \"$GDRIVE_DB-shm\"; : > \"$METADATA_DB-journal\"\n"
            "  fi\n"
            "  if [[ $count -eq 1 && -n ${FAIL_FIRST_RESTART_FILE:-} && ! -e $FAIL_FIRST_RESTART_FILE ]]; then\n"
            "    : > \"$FAIL_FIRST_RESTART_FILE\"\n"
            "    printf 'failed\\n' > \"$SERVICE_STATE_FILE\"; printf '0\\n' > \"$SERVICE_PID_FILE\"; exit 1\n"
            "  fi\n"
            "  printf 'active\\n' > \"$SERVICE_STATE_FILE\"; printf '4242\\n' > \"$SERVICE_PID_FILE\"\n"
            "  printf '4242\\n' > \"$AUBOOKS_CGROUP_ROOT/calibre-web.service/cgroup.procs\"\n"
            "  if [[ $count -eq 1 && -n ${SIGNAL_ON_FIRST_START:-} ]]; then kill -s \"$SIGNAL_ON_FIRST_START\" \"$PPID\"; fi\n"
            "  exit 0\n"
            "fi\n"
            "if [[ ${1:-} == is-active ]]; then\n"
            "  counter=\"$HEALTH_TEST_STATE_DIR/service-checks\"\n"
            "  count=0; [[ -f $counter ]] && read -r count < \"$counter\"\n"
            "  count=$((count + 1)); printf '%s\\n' \"$count\" > \"$counter\"\n"
            "  if [[ -n ${SERVICE_FAIL_AFTER_CHECKS:-} && $count -gt $SERVICE_FAIL_AFTER_CHECKS ]]; then\n"
            "    printf 'failed\\n'; exit 3\n"
            "  fi\n"
            "  state=$(cat \"$SERVICE_STATE_FILE\")\n"
            "  printf '%s\\n' \"$state\"\n"
            "  [[ $state == active ]]\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake_install = self.fake_bin / "install"
        fake_install.write_text(
            "#!/usr/bin/env bash\n"
            "set -e\n"
            "if [[ \" $* \" == *\" -d \"* ]]; then mkdir -p \"${@: -1}\"; exit 0; fi\n"
            "cp \"${@: -2:1}\" \"${@: -1}\"\n",
            encoding="utf-8",
        )
        fake_runuser = self.fake_bin / "runuser"
        fake_runuser.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ -n ${SIGNAL_BEFORE_DESTRUCTIVE:-} && ! -e $HEALTH_TEST_STATE_DIR/pre-destructive-signal ]]; then\n"
            "  : > \"$HEALTH_TEST_STATE_DIR/pre-destructive-signal\"\n"
            "  kill -s \"$SIGNAL_BEFORE_DESTRUCTIVE\" \"$PPID\"\n"
            "fi\n"
            "shift 2\n"
            "[[ ${1:-} == -- ]] && shift\n"
            "if [[ ${1:-} == python3 && ${2:-} == -m && ${3:-} == venv ]]; then\n"
            "  venv=\"${@: -1}\"\n"
            "  mkdir -p \"$venv/bin\"\n"
            "  cat > \"$venv/bin/python\" <<'EOF'\n"
            "#!/usr/bin/env bash\n"
            "if [[ ${1:-} == -c ]]; then\n"
            "  venv_dir=\"$(cd \"$(dirname \"$0\")/..\" && pwd)\"\n"
            "  printf '%s\\n' \"$venv_dir/lib/python3.10/site-packages/calibreweb/cps/static\"\n"
            "fi\n"
            "exit 0\n"
            "EOF\n"
            "  /usr/bin/chmod +x \"$venv/bin/python\"\n"
            "  exit 0\n"
            "fi\n"
            "if [[ ${1:-} == python3 && ${2:-} == - && ${3:-} == */config/app.db ]]; then "
            "exec \"$@\"; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake_ss = self.fake_bin / "ss"
        fake_ss.write_text(
            "#!/usr/bin/env bash\n"
            "counter=\"$HEALTH_TEST_STATE_DIR/port-checks\"\n"
            "count=0; [[ -f $counter ]] && read -r count < \"$counter\"\n"
            "count=$((count + 1)); printf '%s\\n' \"$count\" > \"$counter\"\n"
            "if [[ -z ${PORT_NEVER:-} && $count -gt ${PORT_READY_AFTER:-0} ]]; then\n"
            "  printf 'LISTEN 0 128 127.0.0.1:8083 0.0.0.0:*\\n'\n"
            "fi\n",
            encoding="utf-8",
        )
        fake_curl = self.fake_bin / "curl"
        fake_curl.write_text(
            "#!/usr/bin/env bash\n"
            "url=\"${@: -1}\"\n"
            "if [[ $url == http://127.0.0.1:8083/ ]]; then\n"
            "  counter=\"$HEALTH_TEST_STATE_DIR/http-checks\"\n"
            "  count=0; [[ -f $counter ]] && read -r count < \"$counter\"\n"
            "  count=$((count + 1)); printf '%s\\n' \"$count\" > \"$counter\"\n"
            "  if [[ -n ${HTTP_NEVER:-} || $count -le ${HTTP_READY_AFTER:-0} ]]; then\n"
            "    printf 'connection refused\\n' >&2; exit 7\n"
            "  fi\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake_journalctl = self.fake_bin / "journalctl"
        fake_journalctl.write_text(
            "#!/usr/bin/env bash\nprintf 'test journal: service initialization\\n'\n",
            encoding="utf-8",
        )
        fake_chown = self.fake_bin / "chown"
        fake_chown.write_text(
            "#!/usr/bin/env bash\nprintf 'chown %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n",
            encoding="utf-8",
        )
        fake_chmod = self.fake_bin / "chmod"
        fake_chmod.write_text(
            "#!/usr/bin/env bash\nprintf 'chmod %s\\n' \"$*\" >> \"$COMMAND_LOG\"\n"
            "exec /usr/bin/chmod \"$@\"\n",
            encoding="utf-8",
        )
        fake_rm = self.fake_bin / "rm"
        fake_rm.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ -n ${FAIL_SIDECAR_DB:-} ]]; then\n"
            "  for argument in \"$@\"; do\n"
            "    if [[ $argument == *\"$FAIL_SIDECAR_DB\"-wal || $argument == *\"$FAIL_SIDECAR_DB\"-shm || $argument == *\"$FAIL_SIDECAR_DB\"-journal ]]; then exit 1; fi\n"
            "  done\n"
            "fi\n"
            "exec /usr/bin/rm \"$@\"\n",
            encoding="utf-8",
        )
        fake_mv = self.fake_bin / "mv"
        fake_mv.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ -n ${FAIL_ROLLBACK_SYMLINK_MOVE:-} && \" $* \" == *\"/.current.rollback \"* ]]; then exit 1; fi\n"
            "exec /usr/bin/mv \"$@\"\n",
            encoding="utf-8",
        )
        for path in (
            fake_id, fake_systemctl, fake_install, fake_runuser, fake_ss,
            fake_curl, fake_journalctl, fake_chown, fake_chmod, fake_rm, fake_mv,
        ):
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

    def run_live(self, **extra_env):
        env = self.env.copy()
        env.update(extra_env)
        return subprocess.run(
            [
                "bash", str(HELPER), "--bundle-dir", str(self.bundle),
                "--commit-sha", VALID_SHA,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
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

    def database_values(self):
        with sqlite3.connect(self.app_db) as connection:
            theme = connection.execute("SELECT config_theme FROM settings").fetchone()[0]
        with sqlite3.connect(self.gdrive_db) as connection:
            gdrive = connection.execute("SELECT value FROM state").fetchone()[0]
        with sqlite3.connect(self.metadata_db) as connection:
            metadata = connection.execute("SELECT title FROM books").fetchone()[0]
        return theme, gdrive, metadata

    def assert_candidate_start_signal_rolls_back(self, signal_name):
        result = self.run_live(
            SIGNAL_ON_FIRST_START=signal_name,
            MUTATE_DBS_ON_FIRST_START="1",
        )

        expected_status = {"HUP": 129, "INT": 130, "TERM": 143}[signal_name]
        self.assertEqual(result.returncode, expected_status)
        self.assertIn("interrupted by {}".format(signal_name), result.stderr)
        self.assertIn("Rollback completed", result.stderr)
        self.assertEqual(self.database_values(), (3, "gdrive-original", "metadata-original"))
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())

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
        self.assertIn("wheel", result.stderr)
        self.assertIn("checksum mismatch", result.stderr)

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

    def test_tts_processor_installed_from_bundle(self):
        result = self.run_live()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.tts_processor_dst.read_bytes(),
            b"#!/usr/bin/env python3\nprint('tts')\n",
        )
        self.assertIn("TTS processor installed:", result.stdout)

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

    def test_theme_change_preserves_app_db_owner_group_and_mode(self):
        with sqlite3.connect(self.app_db) as connection:
            connection.execute("UPDATE settings SET config_theme = 1")
        self.app_db.chmod(0o640)
        before = self.app_db.stat()

        result = self.run_live()

        self.assertEqual(result.returncode, 0, result.stderr)
        with sqlite3.connect(self.app_db) as connection:
            theme = connection.execute("SELECT config_theme FROM settings").fetchone()[0]
        after = self.app_db.stat()
        self.assertEqual(theme, 3)
        self.assertEqual(after.st_uid, before.st_uid)
        self.assertEqual(after.st_gid, before.st_gid)
        self.assertEqual(after.st_mode & 0o777, before.st_mode & 0o777)
        self.assertTrue(os.access(self.app_db, os.W_OK))
        command_log = self.command_log.read_text(encoding="utf-8")
        self.assertIn("chown {}:{} {}".format(before.st_uid, before.st_gid, self.app_db), command_log)
        self.assertIn("chmod 640 {}".format(self.app_db), command_log)

    def test_rollback_restores_theme_owner_group_mode_and_writability(self):
        with sqlite3.connect(self.app_db) as connection:
            connection.execute("UPDATE settings SET config_theme = 1")
        self.app_db.chmod(0o640)
        before = self.app_db.stat()
        fail_marker = self.base / "failed-first-restart"

        result = self.run_live(FAIL_FIRST_RESTART_FILE=str(fail_marker))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback completed", result.stderr)
        self.assertNotIn("Rollback encountered errors", result.stderr)
        with sqlite3.connect(self.app_db) as connection:
            theme = connection.execute("SELECT config_theme FROM settings").fetchone()[0]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        after = self.app_db.stat()
        self.assertEqual(theme, 1)
        self.assertEqual(integrity, "ok")
        self.assertEqual(after.st_uid, before.st_uid)
        self.assertEqual(after.st_gid, before.st_gid)
        self.assertEqual(after.st_mode & 0o777, before.st_mode & 0o777)
        self.assertTrue(os.access(self.app_db, os.W_OK))
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        command_log = self.command_log.read_text(encoding="utf-8")
        self.assertIn(
            "chown {}:{} {}".format(before.st_uid, before.st_gid, self.app_db),
            command_log,
        )
        self.assertIn(".app.db.rollback.{}".format(VALID_SHA), command_log)

    def test_health_check_waits_for_delayed_port(self):
        started = time.monotonic()
        result = self.run_live(PORT_READY_AFTER="2")
        elapsed = time.monotonic() - started

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(elapsed, 2)
        self.assertIn("Deployment completed", result.stdout)
        self.assertNotIn("Deployment failed", result.stderr)
        self.assertEqual(
            (self.base / "port-checks").read_text(encoding="ascii").strip(), "3"
        )

    def test_health_check_retries_http_after_port_listens(self):
        started = time.monotonic()
        result = self.run_live(HTTP_READY_AFTER="2")
        elapsed = time.monotonic() - started

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(elapsed, 2)
        self.assertEqual(
            (self.base / "http-checks").read_text(encoding="ascii").strip(), "3"
        )

    def test_health_check_fails_early_when_service_dies(self):
        started = time.monotonic()
        result = self.run_live(
            AUBOOKS_HEALTH_STARTUP_TIMEOUT="10",
            PORT_NEVER="1",
            SERVICE_FAIL_AFTER_CHECKS="1",
        )
        elapsed = time.monotonic() - started

        self.assertNotEqual(result.returncode, 0)
        self.assertLess(elapsed, 5)
        self.assertIn("service is not starting", result.stderr)
        self.assertIn("HEALTH_SERVICE_STATE=failed", result.stderr)

    def test_health_check_times_out_when_port_never_appears(self):
        result = self.run_live(
            AUBOOKS_HEALTH_STARTUP_TIMEOUT="2",
            PORT_NEVER="1",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out after 2s", result.stderr)
        self.assertIn("HEALTH_PORT_STATE=not-listening", result.stderr)
        self.assertIn("HEALTH_LAST_HTTP_RESULT=not-attempted", result.stderr)
        self.assertIn("HEALTH_JOURNAL_BEGIN", result.stderr)

    def test_rollback_health_check_waits_for_delayed_legacy_startup(self):
        with sqlite3.connect(self.app_db) as connection:
            connection.execute("UPDATE settings SET config_theme = 1")
        fail_marker = self.base / "failed-first-restart"

        result = self.run_live(
            FAIL_FIRST_RESTART_FILE=str(fail_marker),
            PORT_READY_AFTER="2",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback completed", result.stderr)
        self.assertNotIn("Rollback encountered errors", result.stderr)
        self.assertEqual(
            (self.base / "port-checks").read_text(encoding="ascii").strip(), "3"
        )

    def test_stop_success_without_stopped_state_touches_no_shared_state(self):
        before = self.database_values()

        result = self.run_live(STOP_LEAVES_RUNNING="1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not confirmed stopped", result.stderr)
        self.assertEqual(self.database_values(), before)
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        self.assertEqual(list((self.root / "backups").iterdir()), [])
        self.assertNotIn("start calibre-web.service", self.command_log.read_text(encoding="utf-8"))

    def test_nonzero_stop_with_confirmed_inactive_state_continues(self):
        result = self.run_live(STOP_EXIT_NONZERO="1")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("confirmed stopped", result.stderr)
        self.assertIn("Deployment completed", result.stdout)

    def test_stopped_main_pid_with_remaining_cgroup_worker_is_rejected(self):
        before = self.database_values()

        result = self.run_live(REMAINING_WORKER_AFTER_STOP="1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not confirmed stopped", result.stderr)
        self.assertEqual(self.database_values(), before)
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        self.assertEqual(list((self.root / "backups").iterdir()), [])
        self.assertFalse((self.base / "start-count").exists())

    def test_final_snapshots_include_state_written_during_stop(self):
        fail_marker = self.base / "failed-first-start"

        result = self.run_live(
            MUTATE_DBS_ON_STOP="1",
            MUTATE_DBS_ON_FIRST_START="1",
            FAIL_FIRST_RESTART_FILE=str(fail_marker),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.database_values(), (7, "gdrive-at-stop", "metadata-at-stop"))

    def test_post_stop_source_validation_failure_keeps_service_stopped(self):
        result = self.run_live(CORRUPT_GDRIVE_ON_STOP="1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("post-stop database source validation failed", result.stderr)
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        self.assertEqual(self.service_state.read_text(encoding="ascii").strip(), "inactive")
        self.assertTrue((self.base / "service-masked").exists())
        self.assertFalse((self.base / "start-count").exists())

    def test_service_is_runtime_masked_during_shared_state_changes(self):
        result = self.run_live()

        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.command_log.read_text(encoding="utf-8").splitlines()
        self.assertLess(commands.index("mask --runtime calibre-web.service"), commands.index("stop calibre-web.service"))
        self.assertLess(commands.index("stop calibre-web.service"), commands.index("unmask --runtime calibre-web.service"))
        self.assertLess(commands.index("unmask --runtime calibre-web.service"), commands.index("start calibre-web.service"))
        self.assertFalse((self.base / "service-masked").exists())

    def test_rollback_reapplies_runtime_mask_before_restore(self):
        fail_marker = self.base / "failed-first-start"

        result = self.run_live(FAIL_FIRST_RESTART_FILE=str(fail_marker))

        self.assertNotEqual(result.returncode, 0)
        commands = self.command_log.read_text(encoding="utf-8").splitlines()
        mask_indexes = [index for index, command in enumerate(commands) if command == "mask --runtime calibre-web.service"]
        stop_indexes = [index for index, command in enumerate(commands) if command == "stop calibre-web.service"]
        self.assertEqual(len(mask_indexes), 2)
        self.assertEqual(len(stop_indexes), 2)
        self.assertLess(mask_indexes[1], stop_indexes[1])

    def test_preexisting_runtime_mask_is_preserved(self):
        (self.base / "service-masked").touch()

        result = self.run_live()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pre-existing service mask", result.stderr)
        self.assertTrue((self.base / "service-masked").exists())
        commands = self.command_log.read_text(encoding="utf-8") if self.command_log.exists() else ""
        self.assertNotIn("stop calibre-web.service", commands)
        self.assertNotIn("unmask --runtime calibre-web.service", commands)

    def test_unmask_failure_after_switch_blocks_restart(self):
        result = self.run_live(FAIL_UNMASK="1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback encountered errors", result.stderr)
        self.assertEqual(self.database_values(), (3, "gdrive-original", "metadata-original"))
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        self.assertEqual(self.service_state.read_text(encoding="ascii").strip(), "inactive")
        self.assertTrue((self.base / "service-masked").exists())
        self.assertFalse((self.base / "start-count").exists())

    def test_signal_during_unmask_refences_service_before_rollback(self):
        result = self.run_live(SIGNAL_ON_FIRST_UNMASK="TERM")

        self.assertEqual(result.returncode, 143)
        self.assertIn("Rollback completed", result.stderr)
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        commands = self.command_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(commands.count("mask --runtime calibre-web.service"), 2)
        self.assertFalse((self.base / "service-masked").exists())

    def test_candidate_startup_mutations_in_all_databases_are_restored(self):
        fail_marker = self.base / "failed-first-start"

        result = self.run_live(
            MUTATE_DBS_ON_FIRST_START="1",
            FAIL_FIRST_RESTART_FILE=str(fail_marker),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback completed", result.stderr)
        self.assertEqual(self.database_values(), (3, "gdrive-original", "metadata-original"))
        backup_dir = next((self.root / "backups").iterdir())
        for database_name in ("app.db", "gdrive.db", "metadata.db"):
            with sqlite3.connect(backup_dir / database_name) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))

    def test_sqlite_backup_captures_committed_wal_content(self):
        connection = sqlite3.connect(self.gdrive_db)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("UPDATE state SET value = 'gdrive-in-wal'")
        connection.commit()
        fail_marker = self.base / "failed-first-start"
        try:
            result = self.run_live(
                MUTATE_DBS_ON_FIRST_START="1",
                FAIL_FIRST_RESTART_FILE=str(fail_marker),
            )
        finally:
            connection.close()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.database_values()[1], "gdrive-in-wal")

    def test_rollback_refuses_restore_when_candidate_cannot_be_stopped(self):
        result = self.run_live(
            AUBOOKS_HEALTH_STARTUP_TIMEOUT="2",
            HTTP_NEVER="1",
            FAIL_STOP_AFTER="1",
            MUTATE_DBS_ON_FIRST_START="1",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rollback blocked", result.stderr)
        self.assertIn("manual recovery is required", result.stderr)
        self.assertEqual(self.database_values(), (99, "gdrive-mutated", "metadata-mutated"))
        self.assertEqual((self.root / "current").resolve(), (self.root / "releases" / VALID_SHA).resolve())
        self.assertEqual((self.base / "start-count").read_text(encoding="ascii").strip(), "1")

    def test_sidecar_removal_failure_blocks_database_replace_and_restart(self):
        fail_marker = self.base / "failed-first-start"

        result = self.run_live(
            MUTATE_DBS_ON_FIRST_START="1",
            CREATE_SIDECARS_ON_FIRST_START="1",
            FAIL_FIRST_RESTART_FILE=str(fail_marker),
            FAIL_SIDECAR_DB="gdrive.db",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback encountered errors", result.stderr)
        self.assertEqual(self.database_values()[1], "gdrive-mutated")
        self.assertTrue(Path(str(self.gdrive_db) + "-shm").exists())
        self.assertEqual((self.base / "start-count").read_text(encoding="ascii").strip(), "1")

    def test_successful_rollback_removes_all_database_sidecars(self):
        fail_marker = self.base / "failed-first-start"

        result = self.run_live(
            MUTATE_DBS_ON_FIRST_START="1",
            CREATE_SIDECARS_ON_FIRST_START="1",
            FAIL_FIRST_RESTART_FILE=str(fail_marker),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback completed", result.stderr)
        self.assertEqual(self.database_values(), (3, "gdrive-original", "metadata-original"))
        for database in (self.app_db, self.gdrive_db, self.metadata_db):
            for suffix in ("-wal", "-shm", "-journal"):
                self.assertFalse(Path(str(database) + suffix).exists())

    def test_failed_restored_release_health_check_is_stopped(self):
        result = self.run_live(SERVICE_FAIL_AFTER_CHECKS="0")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback encountered errors", result.stderr)
        self.assertEqual(self.service_state.read_text(encoding="ascii").strip(), "inactive")
        self.assertEqual(self.service_pid.read_text(encoding="ascii").strip(), "0")
        self.assertEqual(self.cgroup_processes.read_text(encoding="ascii"), "")

    def test_symlink_restore_failure_blocks_restart(self):
        fail_marker = self.base / "failed-first-start"

        result = self.run_live(
            FAIL_FIRST_RESTART_FILE=str(fail_marker),
            FAIL_ROLLBACK_SYMLINK_MOVE="1",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback encountered errors", result.stderr)
        self.assertEqual((self.root / "current").resolve(), (self.root / "releases" / VALID_SHA).resolve())
        self.assertEqual((self.base / "start-count").read_text(encoding="ascii").strip(), "1")

    def test_signal_before_destructive_phase_does_not_run_rollback(self):
        result = self.run_live(SIGNAL_BEFORE_DESTRUCTIVE="TERM")

        self.assertEqual(result.returncode, 143)
        self.assertNotIn("starting rollback", result.stderr)
        self.assertEqual(self.database_values(), (3, "gdrive-original", "metadata-original"))
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        self.assertFalse(self.command_log.exists())

    def test_signal_after_confirmed_stop_restarts_original_service(self):
        result = self.run_live(SIGNAL_ON_STOP="TERM")

        self.assertEqual(result.returncode, 143)
        self.assertIn("interrupted by TERM", result.stderr)
        self.assertIn("Rollback completed", result.stderr)
        self.assertEqual(self.database_values(), (3, "gdrive-original", "metadata-original"))
        self.assertEqual((self.root / "current").resolve(), self.previous.resolve())
        self.assertEqual((self.base / "start-count").read_text(encoding="ascii").strip(), "1")

    def test_term_during_candidate_start_rolls_back(self):
        self.assert_candidate_start_signal_rolls_back("TERM")

    def test_int_during_candidate_start_rolls_back(self):
        self.assert_candidate_start_signal_rolls_back("INT")

    def test_hup_during_candidate_start_rolls_back(self):
        self.assert_candidate_start_signal_rolls_back("HUP")

    def test_multi_second_startup_does_not_trigger_rollback(self):
        started = time.monotonic()
        result = self.run_live(
            AUBOOKS_HEALTH_STARTUP_TIMEOUT="6",
            PORT_READY_AFTER="3",
        )
        elapsed = time.monotonic() - started

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(elapsed, 3)
        self.assertIn("Deployment completed", result.stdout)
        self.assertNotIn("Deployment failed", result.stderr)

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

    def test_new_sha256_format_with_helper_passes(self):
        result = self.run_dry()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_helper_checksum_missing_fails(self):
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        sync_name = "sync-audio-db.sh"
        sync_content = "#!/usr/bin/env bash\necho sync\n"
        sync_digest = hashlib.sha256(sync_content.encode("utf-8")).hexdigest()
        tts_name = "tts_processor.py"
        tts_content = "#!/usr/bin/env python3\nprint('tts')\n"
        tts_digest = hashlib.sha256(tts_content.encode("utf-8")).hexdigest()
        sums = "{}  {}\n{}  {}\n{}  {}\n".format(
            digest, self.wheel_name,
            sync_digest, sync_name,
            tts_digest, tts_name,
        )
        (self.bundle / "SHA256SUMS").write_text(sums, encoding="ascii")
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly 4 entries", result.stderr)

    def test_duplicate_helper_in_sha256sums_fails(self):
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        helper_digest = hashlib.sha256(self.helper.read_bytes()).hexdigest()
        sync_name = "sync-audio-db.sh"
        sync_content = "#!/usr/bin/env bash\necho sync\n"
        sync_digest = hashlib.sha256(sync_content.encode("utf-8")).hexdigest()
        tts_name = "tts_processor.py"
        tts_content = "#!/usr/bin/env python3\nprint('tts')\n"
        tts_digest = hashlib.sha256(tts_content.encode("utf-8")).hexdigest()
        sums = "{}  {}\n{}  {}\n{}  {}\n{}  {}\n".format(
            digest, self.wheel_name,
            helper_digest, self.helper_name,
            sync_digest, sync_name,
            tts_digest, tts_name,
        )
        sums += "{}  {}\n".format(helper_digest, self.helper_name)
        (self.bundle / "SHA256SUMS").write_text(sums, encoding="ascii")
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)

    def test_unknown_file_in_sha256sums_fails(self):
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        helper_digest = hashlib.sha256(self.helper.read_bytes()).hexdigest()
        sync_name = "sync-audio-db.sh"
        sync_content = "#!/usr/bin/env bash\necho sync\n"
        sync_digest = hashlib.sha256(sync_content.encode("utf-8")).hexdigest()
        tts_name = "tts_processor.py"
        tts_content = "#!/usr/bin/env python3\nprint('tts')\n"
        tts_digest = hashlib.sha256(tts_content.encode("utf-8")).hexdigest()
        sums = "{}  {}\n{}  {}\n{}  {}\n{}  {}\n".format(
            digest, self.wheel_name,
            helper_digest, self.helper_name,
            sync_digest, sync_name,
            tts_digest, tts_name,
        )
        sums += "abc123  evil.txt\n"
        (self.bundle / "SHA256SUMS").write_text(sums, encoding="ascii")
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected entry", result.stderr)

    def test_wrong_helper_checksum_fails(self):
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        sync_name = "sync-audio-db.sh"
        sync_content = "#!/usr/bin/env bash\necho sync\n"
        sync_digest = hashlib.sha256(sync_content.encode("utf-8")).hexdigest()
        tts_name = "tts_processor.py"
        tts_content = "#!/usr/bin/env python3\nprint('tts')\n"
        tts_digest = hashlib.sha256(tts_content.encode("utf-8")).hexdigest()
        sums = "{}  {}\n{}  {}\n{}  {}\n{}  {}\n".format(
            digest, self.wheel_name,
            sync_digest, sync_name,
            tts_digest, tts_name,
            "a" * 64, self.helper_name,
        )
        (self.bundle / "SHA256SUMS").write_text(sums, encoding="ascii")
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("helper", result.stderr)

    def test_wrong_wheel_checksum_fails(self):
        helper_digest = hashlib.sha256(self.helper.read_bytes()).hexdigest()
        sync_name = "sync-audio-db.sh"
        sync_content = "#!/usr/bin/env bash\necho sync\n"
        sync_digest = hashlib.sha256(sync_content.encode("utf-8")).hexdigest()
        tts_name = "tts_processor.py"
        tts_content = "#!/usr/bin/env python3\nprint('tts')\n"
        tts_digest = hashlib.sha256(tts_content.encode("utf-8")).hexdigest()
        sums = "{}  {}\n{}  {}\n{}  {}\n{}  {}\n".format(
            "b" * 64, self.wheel_name,
            helper_digest, self.helper_name,
            sync_digest, sync_name,
            tts_digest, tts_name,
        )
        (self.bundle / "SHA256SUMS").write_text(sums, encoding="ascii")
        result = self.run_dry()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wheel", result.stderr)


class DispatcherUploadTest(unittest.TestCase):
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
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, data in files.items():
                if isinstance(data, bytes):
                    content = data
                else:
                    content = data.encode("utf-8")
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        return buf.getvalue()

    def make_tar_from_path(self, name, data_bytes, **tarinfo_kwargs):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=name)
            info.size = len(data_bytes)
            for k, v in tarinfo_kwargs.items():
                setattr(info, k, v)
            tar.addfile(info, io.BytesIO(data_bytes))
        return buf.getvalue()

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
            "deploy-calibre-web-release.sh": "#!/usr/bin/env bash\n",
            "sync-audio-db.sh": "#!/usr/bin/env bash\necho sync\n",
            "tts_processor.py": "#!/usr/bin/env python3\nprint('tts')\n",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("upload {} OK".format(VALID_SHA).encode(), result.stdout)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertTrue(bundle.is_dir())
        self.assertEqual(len(list(bundle.iterdir())), 7)

    def test_upload_sets_helper_executable(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": "abc  {}\n".format(self.wheel_name),
            "artifact-manifest.json": "{}",
            "deploy-request.json": "{}",
            "deploy-calibre-web-release.sh": "#!/usr/bin/env bash\necho ok\n",
            "sync-audio-db.sh": "#!/usr/bin/env bash\necho sync\n",
            "tts_processor.py": "#!/usr/bin/env python3\nprint('tts')\n",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        helper = bundle / "deploy-calibre-web-release.sh"
        self.assertEqual(oct(helper.stat().st_mode)[-3:], "755")
        for name in (self.wheel_name, "SHA256SUMS", "artifact-manifest.json", "deploy-request.json", "sync-audio-db.sh", "tts_processor.py"):
            mode = oct((bundle / name).stat().st_mode)[-3:]
            self.assertTrue(int(mode, 8) & 0o111 == 0, "{} should not be executable, got {}".format(name, mode))

    def test_upload_rejects_traversal_path(self):
        tar_data = self.make_tar({"../etc/passwd": b"root:x:0:0:"})
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_absolute_path(self):
        tar_data = self.make_tar_from_path("/etc/passwd", b"rootxx")
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_symlink(self):
        tar_data = self.make_tar_from_path(
            "evil-symlink", b"",
            type=tarfile.SYMTYPE, linkname="/etc/passwd",
        )
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_hardlink(self):
        tar_data = self.make_tar_from_path(
            "evil-hardlink", b"",
            type=tarfile.LNKTYPE, linkname="/etc/passwd",
        )
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_fifo(self):
        tar_data = self.make_tar_from_path("evil-fifo", b"", type=tarfile.FIFOTYPE)
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_directory(self):
        tar_data = self.make_tar_from_path("subdir", b"", type=tarfile.DIRTYPE)
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_nested_path(self):
        tar_data = self.make_tar({"subdir/file.txt": b"data"})
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_upload_rejects_duplicate_filename(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for _ in range(2):
                info = tarfile.TarInfo(name="SHA256SUMS")
                info.size = 4
                tar.addfile(info, io.BytesIO(b"data"))
            info = tarfile.TarInfo(name="artifact-manifest.json")
            info.size = 2
            tar.addfile(info, io.BytesIO(b"{}"))
            info = tarfile.TarInfo(name="deploy-request.json")
            info.size = 2
            tar.addfile(info, io.BytesIO(b"{}"))
            info = tarfile.TarInfo(name="deploy-calibre-web-release.sh")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"exec"))
            info = tarfile.TarInfo(name="sync-audio-db.sh")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"sync"))
            info = tarfile.TarInfo(name="tts_processor.py")
            info.size = 3
            tar.addfile(info, io.BytesIO(b"tts"))
        result = self.run_dispatcher("upload {}".format(VALID_SHA), buf.getvalue())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"duplicate filename", result.stderr)

    def test_upload_rejects_two_wheels(self):
        tar_data = self.make_tar({
            "calibreweb-0.6.28a.whl": b"a",
            "calibreweb-0.6.28b.whl": b"b",
            "SHA256SUMS": b"s",
            "artifact-manifest.json": b"{}",
            "deploy-calibre-web-release.sh": b"#!/usr/bin/env bash\n",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)

    def test_upload_rejects_wrong_member_count(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": b"s",
            "artifact-manifest.json": b"{}",
            "deploy-request.json": b"{}",
            "deploy-calibre-web-release.sh": b"#!/usr/bin/env bash\n",
            "sync-audio-db.sh": b"#!/usr/bin/env bash\necho sync\n",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"expected exactly 7", result.stderr)

    def test_upload_rejects_unexpected_file(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": b"s",
            "artifact-manifest.json": b"{}",
            "deploy-request.json": b"{}",
            "deploy-calibre-web-release.sh": b"#!/usr/bin/env bash\n",
            "sync-audio-db.sh": b"#!/usr/bin/env bash\necho sync\n",
            "evil.txt": b"malicious",
        })
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"unexpected file", result.stderr)

    def test_upload_rejects_empty_archive(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            pass
        result = self.run_dispatcher("upload {}".format(VALID_SHA), buf.getvalue())
        self.assertNotEqual(result.returncode, 0)

    def test_upload_idempotent_rejected(self):
        tar_data = self.make_tar({
            self.wheel_name: b"wheel data",
            "SHA256SUMS": b"s",
            "artifact-manifest.json": b"{}",
            "deploy-request.json": b"{}",
            "deploy-calibre-web-release.sh": b"#!/usr/bin/env bash\n",
            "sync-audio-db.sh": b"#!/usr/bin/env bash\necho sync\n",
            "tts_processor.py": b"#!/usr/bin/env python3\nprint('tts')\n",
        })
        result1 = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertEqual(result1.returncode, 0, result1.stderr)
        result2 = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result2.returncode, 0)
        self.assertIn(b"already exists", result2.stderr)

    def test_failed_upload_cleans_staging(self):
        tar_data = self.make_tar({"bad.txt": b"bad"})
        result = self.run_dispatcher("upload {}".format(VALID_SHA), tar_data)
        self.assertNotEqual(result.returncode, 0)
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        self.assertFalse(bundle.exists())

    def test_deploy_before_upload_rejected(self):
        result = self.run_dispatcher("deploy {}".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"does not exist", result.stderr)


class RootWrapperTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.staging = self.base / "staging"
        self.staging.mkdir()
        self.fake_helper = self.base / "calibre-web-helper"
        self.fake_helper.write_text("#!/usr/bin/env bash\nprintf 'HELPER_INVOKED\\n'\n")
        self.fake_helper.chmod(0o755)
        self.env = os.environ.copy()
        self.env["STAGING_BASE"] = str(self.staging)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_wrapper(self, stdin_text):
        env = self.env.copy()
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER)],
            input=stdin_text,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result

    def test_no_arguments_accepted(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER), "extra"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepts no command-line arguments", result.stderr)

    def test_two_arguments_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER), "a", "b"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepts no command-line arguments", result.stderr)

    def test_empty_stdin_rejected(self):
        result = self.run_wrapper("")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty stdin", result.stderr)

    def test_invalid_sha_rejected(self):
        result = self.run_wrapper("not-a-sha\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("40 hexadecimal", result.stderr)

    def test_uppercase_sha_rejected(self):
        result = self.run_wrapper("A" * 40 + "\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("40 lowercase hexadecimal", result.stderr)

    def test_two_lines_rejected(self):
        result = self.run_wrapper("{}\nextra\n".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("trailing input", result.stderr)

    def test_no_newline_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT_WRAPPER)],
            input=VALID_SHA,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_valid_sha_derives_exact_path(self):
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        bundle.mkdir(parents=True)
        helper = bundle / "deploy-calibre-web-release.sh"
        helper.write_text("#!/usr/bin/env bash\nprintf 'HELPER_INVOKED\\n'\n")
        helper.chmod(0o755)
        result = self.run_wrapper("{}\n".format(VALID_SHA))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HELPER_INVOKED", result.stdout)

    def test_missing_bundle_rejected(self):
        result = self.run_wrapper("{}\n".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)

    def test_helper_missing_from_bundle_rejected(self):
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        bundle.mkdir(parents=True)
        result = self.run_wrapper("{}\n".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("helper is missing", result.stderr)

    def test_helper_symlink_rejected(self):
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        bundle.mkdir(parents=True)
        real_helper = self.base / "real-helper"
        real_helper.write_text("#!/usr/bin/env bash\n")
        real_helper.chmod(0o755)
        helper = bundle / "deploy-calibre-web-release.sh"
        helper.symlink_to(real_helper)
        result = self.run_wrapper("{}\n".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not be a symlink", result.stderr)

    def test_helper_unsafe_permissions_rejected(self):
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        bundle.mkdir(parents=True)
        helper = bundle / "deploy-calibre-web-release.sh"
        helper.write_text("#!/usr/bin/env bash\n")
        helper.chmod(0o777)
        result = self.run_wrapper("{}\n".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("world-writable", result.stderr)

    def test_helper_not_executable_rejected(self):
        bundle = self.staging / "aubooks-calibre-web-{}".format(VALID_SHA) / "deploy-bundle"
        bundle.mkdir(parents=True)
        helper = bundle / "deploy-calibre-web-release.sh"
        helper.write_text("#!/usr/bin/env bash\n")
        helper.chmod(0o644)
        result = self.run_wrapper("{}\n".format(VALID_SHA))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not executable", result.stderr)


class DispatcherScriptTest(unittest.TestCase):
    def test_no_scp_in_workflow(self):
        workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-production.yml"
        content = workflow.read_text()
        self.assertNotIn("scp ", content)

    def test_no_direct_remote_sudo(self):
        workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-production.yml"
        content = workflow.read_text()
        self.assertNotRegex(content, r"ssh.*sudo\s+/usr/local/sbin/aubooks-deploy-calibre-web")

    def test_only_upload_deploy_protocol(self):
        workflow = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-production.yml"
        content = workflow.read_text()
        self.assertIn("upload $COMMIT_SHA", content)
        self.assertIn("deploy $COMMIT_SHA", content)

    def test_dispatcher_script_exists(self):
        self.assertTrue(DISPATCHER.exists())
        self.assertTrue(os.access(DISPATCHER, os.X_OK))

    def test_root_wrapper_script_exists(self):
        self.assertTrue(ROOT_WRAPPER.exists())
        self.assertTrue(os.access(ROOT_WRAPPER, os.X_OK))

    def test_dispatcher_reads_ssh_original_command(self):
        content = DISPATCHER.read_text()
        self.assertIn("SSH_ORIGINAL_COMMAND", content)

    def test_root_wrapper_reads_stdin(self):
        content = ROOT_WRAPPER.read_text()
        self.assertIn("read -r", content)

    def test_root_wrapper_no_eval(self):
        content = ROOT_WRAPPER.read_text()
        self.assertNotIn("eval ", content)
        self.assertNotIn("bash -c", content)
        self.assertNotIn("sh -c", content)

    def test_dispatcher_no_eval(self):
        content = DISPATCHER.read_text()
        self.assertNotIn("eval ", content)
        self.assertNotIn("bash -c", content)
        self.assertNotIn("sh -c", content)


if __name__ == "__main__":
    unittest.main()
