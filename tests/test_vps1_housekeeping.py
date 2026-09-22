import json
import os
import subprocess
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "vps1-housekeeping.sh"
FTS_GENERATION = "9345aa9df713b711698884e48bb5d415c741f3f299582319f026794dcd6c9a45"


def write_executable(path, content):
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def environment(tmp_path):
    home = tmp_path / "home"
    base = home / "aubooks"
    generations = base / "sync-export" / "generations"
    jobs = base / "jobs"
    state = home / ".local" / "state" / "aubooks"
    tmp_root = tmp_path / "tmp"
    bin_dir = tmp_path / "bin"
    for path in (generations, jobs, state, tmp_root, bin_dir):
        path.mkdir(parents=True)
    export_lock = base / "export-metadata-sync.lock"
    export_lock.touch()
    remote = bin_dir / "aubook-remote"
    audio = bin_dir / "audio-index-runtime.py"
    write_executable(
        remote,
        "#!/usr/bin/env bash\ncat \"$JOBS_DIR/$2/status\"\n",
    )
    write_executable(
        audio,
        """#!/usr/bin/env python3
import json
import os
import sys
job_id = sys.argv[-1]
statuses = json.loads(os.environ.get("DURABLE_STATUSES", "{}"))
if sys.argv[1] == "exact-status":
    print("EXACT_STATUS=" + statuses.get(job_id, "mismatch"))
elif sys.argv[1] == "submission-get":
    value = statuses.get(os.environ.get("CURRENT_JOB_ID", ""), "mismatch")
    print(json.dumps({"status": value, "job_id": os.environ.get("CURRENT_JOB_ID")}))
else:
    raise SystemExit(1)
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "BASE_AUBOOKS_DIR": str(base),
            "GENERATIONS_DIR": str(generations),
            "JOBS_DIR": str(jobs),
            "EXPORT_LOCK_FILE": str(export_lock),
            "AUBOOK_REMOTE": str(remote),
            "AUDIO_INDEX_RUNTIME": str(audio),
            "TMP_ROOT": str(tmp_root),
            "HOUSEKEEPING_STATE_DIR": str(state),
            "HOUSEKEEPING_LOG_FILE": str(state / "housekeeping.log"),
            "HOUSEKEEPING_LOCK_FILE": str(state / "housekeeping.lock"),
            "HOUSEKEEPING_DF_TARGET": str(tmp_path),
            "OPENCODE_DB": str(home / ".local" / "share" / "opencode" / "opencode.db"),
            "DURABLE_STATUSES": "{}",
        }
    )
    return env


def run_housekeeping(env, mode="--apply"):
    return subprocess.run(
        [str(SCRIPT), mode],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def make_generation(root, name, age_hours):
    path = root / name
    path.mkdir()
    (path / "data").write_bytes(b"x")
    stamp = time.time() - age_hours * 3600
    os.utime(path, (stamp, stamp))
    return path


def generation_name(number):
    return f"{number:064x}"


def test_sync_export_retention_and_unrelated_file(environment):
    root = Path(environment["GENERATIONS_DIR"])
    old = make_generation(root, generation_name(1), 100)
    newest = make_generation(root, generation_name(2), 1)
    second = make_generation(root, generation_name(3), 2)
    fts = make_generation(root, FTS_GENERATION, 200)
    unrelated = root / "README"
    unrelated.write_text("keep", encoding="utf-8")

    result = run_housekeeping(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not old.exists()
    assert newest.exists() and second.exists() and fts.exists()
    assert unrelated.exists()


def make_job(root, job_id, state, age_hours, book_id="1", cancelled_complete=False):
    job = root / job_id
    job.mkdir()
    status = job / "status"
    status.write_text(f"STATE={state}\nBOOK_ID={book_id}\n", encoding="utf-8")
    (job / "control.lock").touch()
    (job / "payload").write_bytes(b"payload")
    if cancelled_complete:
        (job / "CANCEL_COMPLETE").touch()
    stamp = time.time() - age_hours * 3600
    os.utime(status, (stamp, stamp))
    return job


def test_tts_retention_policy(environment):
    jobs = Path(environment["JOBS_DIR"])
    cases = {
        "running": ("RUNNING", 100, "processing", True),
        "queued": ("QUEUED", 100, "queued", True),
        "durable-processing": ("FAILED", 100, "processing", True),
        "unknown": ("MYSTERY", 100, "failed", True),
        "interrupted-recent": ("INTERRUPTED", 48, "failed", True),
        "interrupted-old": ("INTERRUPTED", 73, "failed", False),
        "done-ready": ("DONE", 25, "ready", False),
        "done-not-ready": ("DONE", 100, "failed", True),
    }
    statuses = {}
    paths = {}
    for index, (name, (state, age, durable, _kept)) in enumerate(cases.items(), 1):
        paths[name] = make_job(jobs, name, state, age, str(index))
        statuses[name] = durable
    environment["DURABLE_STATUSES"] = json.dumps(statuses)

    result = run_housekeeping(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    for name, (_state, _age, _durable, kept) in cases.items():
        assert paths[name].exists() is kept, name


def make_fake_opencode(path, sessions, calls_file, malformed=False):
    payload = "not-json" if malformed else json.dumps(sessions)
    write_executable(
        path,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
calls = Path({str(calls_file)!r})
with calls.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["session", "list"]:
    print({payload!r})
elif sys.argv[1:3] == ["session", "delete"] and os.environ.get("FAIL_SESSION_DELETE") == "1":
    raise SystemExit(1)
""",
    )


def configure_large_opencode(environment, tmp_path, sessions, malformed=False):
    db = Path(environment["OPENCODE_DB"])
    db.parent.mkdir(parents=True)
    with db.open("wb") as stream:
        stream.truncate(769 * 1024 * 1024)
    calls = tmp_path / "opencode-calls"
    command = tmp_path / "bin" / "opencode"
    make_fake_opencode(command, sessions, calls, malformed=malformed)
    environment["OPENCODE_BIN"] = str(command)
    return calls


def read_calls(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sessions_for_retention():
    now_ms = int(time.time() * 1000)
    old_ms = now_ms - 31 * 24 * 3600 * 1000
    recent_ms = now_ms - 10 * 24 * 3600 * 1000
    sessions = [
        {"id": f"ses_{index:03d}", "created": old_ms, "updated": old_ms + index}
        for index in range(100)
    ]
    sessions.append({"id": "ses_recent", "created": recent_ms, "updated": recent_ms})
    return sessions


def test_opencode_below_threshold_does_not_list_sessions(environment, tmp_path):
    db = Path(environment["OPENCODE_DB"])
    db.parent.mkdir(parents=True)
    db.write_bytes(b"small")
    calls = tmp_path / "calls"
    command = tmp_path / "bin" / "opencode"
    make_fake_opencode(command, [], calls)
    environment["OPENCODE_BIN"] = str(command)

    result = run_housekeeping(environment)

    assert result.returncode == 0
    assert read_calls(calls) == []


def test_opencode_retention_uses_cli_delete_not_sql(environment, tmp_path):
    calls = configure_large_opencode(environment, tmp_path, sessions_for_retention())
    environment["HOUSEKEEPING_FREE_BYTES_OVERRIDE"] = str(10 * 1024**3)

    result = run_housekeeping(environment)
    calls_made = read_calls(calls)

    assert result.returncode == 0, result.stdout + result.stderr
    deletes = [call for call in calls_made if call[:2] == ["session", "delete"]]
    assert deletes == [["session", "delete", "ses_000"]]
    assert not any("DELETE" in " ".join(call) for call in calls_made if call[0] == "db")
    assert ["db", "PRAGMA wal_checkpoint(TRUNCATE);"] in calls_made
    assert ["db", "VACUUM;"] in calls_made
    assert ["session", "delete", "ses_recent"] not in calls_made


def test_opencode_malformed_json_fails_safe(environment, tmp_path):
    calls = configure_large_opencode(environment, tmp_path, [], malformed=True)

    result = run_housekeeping(environment)

    assert result.returncode == 0
    assert not any(call[:2] == ["session", "delete"] for call in read_calls(calls))
    assert "malformed session JSON" in result.stdout


def test_opencode_insufficient_space_skips_vacuum(environment, tmp_path):
    calls = configure_large_opencode(environment, tmp_path, sessions_for_retention())
    environment["HOUSEKEEPING_FREE_BYTES_OVERRIDE"] = "1"

    result = run_housekeeping(environment)
    calls_made = read_calls(calls)

    assert result.returncode == 0
    assert ["db", "PRAGMA wal_checkpoint(TRUNCATE);"] in calls_made
    assert ["db", "VACUUM;"] not in calls_made
    assert "WARNING VACUUM skipped" in result.stdout


def test_opencode_delete_failure_stops_without_sql(environment, tmp_path):
    calls = configure_large_opencode(environment, tmp_path, sessions_for_retention())
    environment["FAIL_SESSION_DELETE"] = "1"

    result = run_housekeeping(environment)
    calls_made = read_calls(calls)

    assert result.returncode == 1
    assert ["session", "delete", "ses_000"] in calls_made
    assert not any(call[0] == "db" for call in calls_made)


def test_duplicate_tts_identity_fields_fail_safe(environment):
    jobs = Path(environment["JOBS_DIR"])
    job = make_job(jobs, "duplicate-id", "DONE", 100, "1")
    with (job / "status").open("a", encoding="utf-8") as status:
        status.write("BOOK_ID=2\n")
    environment["DURABLE_STATUSES"] = json.dumps({"duplicate-id": "ready"})

    result = run_housekeeping(environment)

    assert result.returncode == 0
    assert job.exists()
    assert "unknown durable state" in result.stdout


def test_export_lock_skips_generation_cleanup(environment):
    root = Path(environment["GENERATIONS_DIR"])
    candidates = [make_generation(root, generation_name(index), 100 + index) for index in range(1, 5)]
    holder = subprocess.Popen(
        ["flock", environment["EXPORT_LOCK_FILE"], "sleep", "10"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.2)
        result = run_housekeeping(environment)
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    assert result.returncode == 0
    assert "metadata export is running" in result.stdout
    assert all(path.exists() for path in candidates)


def test_dry_run_deletes_nothing(environment, tmp_path):
    root = Path(environment["GENERATIONS_DIR"])
    candidates = [make_generation(root, generation_name(index), 100 + index) for index in range(1, 5)]
    job = make_job(Path(environment["JOBS_DIR"]), "old-interrupted", "INTERRUPTED", 100)
    environment["DURABLE_STATUSES"] = json.dumps({"old-interrupted": "failed"})
    tmp_candidate = Path(environment["TMP_ROOT"]) / "calibre_test_old"
    tmp_candidate.mkdir()
    stamp = time.time() - 49 * 3600
    os.utime(tmp_candidate, (stamp, stamp))
    calls = configure_large_opencode(environment, tmp_path, sessions_for_retention())

    result = run_housekeeping(environment, "--dry-run")

    assert result.returncode == 0
    assert all(path.exists() for path in candidates)
    assert job.exists() and tmp_candidate.exists()
    assert not any(call[:2] == ["session", "delete"] or call[0] == "db" for call in read_calls(calls))
    assert "DELETE(dry-run)" in result.stdout


def test_path_safety_keeps_symlinks_outside_roots(environment, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_text("keep", encoding="utf-8")
    generation_link = Path(environment["GENERATIONS_DIR"]) / generation_name(9)
    generation_link.symlink_to(outside, target_is_directory=True)
    tmp_link = Path(environment["TMP_ROOT"]) / "calibre_test_escape"
    tmp_link.symlink_to(outside, target_is_directory=True)

    result = run_housekeeping(environment)

    assert result.returncode == 0
    assert marker.exists()
    assert generation_link.is_symlink() and tmp_link.is_symlink()


def test_flock_second_instance_skips_cleanup(environment):
    root = Path(environment["GENERATIONS_DIR"])
    candidates = [make_generation(root, generation_name(index), 100 + index) for index in range(1, 5)]
    lock_path = environment["HOUSEKEEPING_LOCK_FILE"]
    holder = subprocess.Popen(
        ["flock", lock_path, "sleep", "10"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.2)
        result = run_housekeeping(environment)
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    assert result.returncode == 0
    assert "another instance" in result.stdout
    assert all(path.exists() for path in candidates)
