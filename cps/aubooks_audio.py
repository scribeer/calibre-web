"""
Read-only adapter for audio.db in Calibre-Web.

Provides safe access to audiobook status from the AU-Books audio index.
Never writes to audio.db. Falls back to 'not_available' on any error.
"""

import logging
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

log = logging.getLogger(__name__)

# Default path to audio.db — configurable via AUBOOKS_AUDIO_DB env var
_DEFAULT_AUDIO_DB = "/home/feninf/aubooks/audio.db"

# Status labels for Russian UI
STATUS_LABELS = {
    "queued": "В очереди",
    "processing": "Озвучивается…",
    "ready": "Готово",
    "failed": "Ошибка",
    "cancelled": "Отменено",
}

# Limit for finished jobs shown in tasks page
_FINISHED_LIMIT = 50

_DEFAULT_BOOKS_REMOTE = "opendrive_content:calibre-books-v2"
_AUDIO_DOWNLOAD_RESERVE_BYTES = 64 * 1024 * 1024
_AUDIO_DOWNLOAD_TIMEOUT_SECONDS = 1800
_RCLONE_REMOTE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class AudioDownloadError(Exception):
    """Base class for expected audiobook download failures."""


class InvalidAudioPathError(AudioDownloadError):
    pass


class AudioRemoteMissingError(AudioDownloadError):
    pass


class AudioRemoteUnavailableError(AudioDownloadError):
    pass


class AudioTempStorageError(AudioDownloadError):
    pass


class AudioDatabaseError(AudioDownloadError):
    pass


def _validated_audio_path(remote_path: str) -> str:
    if not isinstance(remote_path, str) or not remote_path:
        raise InvalidAudioPathError("audio remote path is empty")

    path = PurePosixPath(remote_path)
    if (path.is_absolute() or len(path.parts) < 2 or path.parts[0] != "Audiobooks"
            or any(part in ("", ".", "..") for part in path.parts)
            or path.suffix.lower() != ".m4b" or ":" in remote_path or "\\" in remote_path):
        raise InvalidAudioPathError("audio remote path is outside Audiobooks or is not M4B")
    return path.as_posix()


def _audio_rclone_remote() -> str:
    books_remote = os.environ.get("AUBOOKS_BOOKS_REMOTE", _DEFAULT_BOOKS_REMOTE)
    remote_name, separator, remote_root = books_remote.partition(":")
    if not separator or not remote_root or not _RCLONE_REMOTE_RE.fullmatch(remote_name):
        raise AudioRemoteUnavailableError("AUBOOKS_BOOKS_REMOTE is invalid")
    return remote_name


def _rclone_env() -> dict:
    env = os.environ.copy()
    rclone_config = os.environ.get("RCLONE_CONFIG")
    if rclone_config:
        env["RCLONE_CONFIG"] = rclone_config
    return env


def fetch_audiobook_from_opendrive(remote_path: str, expected_size: int | None = None):
    """Download a trusted audio.db M4B path to temporary storage.

    Returns ``(local_path, cleanup)``. The caller must keep the file until the
    response is closed, then invoke the idempotent cleanup callback.
    """
    validated_path = _validated_audio_path(remote_path)
    remote_name = _audio_rclone_remote()

    try:
        expected_size = int(expected_size or 0)
    except (TypeError, ValueError):
        expected_size = 0

    try:
        free_bytes = shutil.disk_usage(tempfile.gettempdir()).free
    except OSError as exc:
        raise AudioTempStorageError("cannot inspect temporary storage") from exc
    required_bytes = max(expected_size, 0) + _AUDIO_DOWNLOAD_RESERVE_BYTES
    if free_bytes < required_bytes:
        raise AudioTempStorageError(
            "insufficient temporary storage: required={}, free={}".format(
                required_bytes, free_bytes
            )
        )

    try:
        dest_dir = tempfile.mkdtemp(prefix="aubooks_audio_")
    except OSError as exc:
        raise AudioTempStorageError("cannot create temporary directory") from exc
    local_path = os.path.join(dest_dir, PurePosixPath(validated_path).name)
    cleaned = False

    def cleanup():
        nonlocal cleaned
        if not cleaned:
            shutil.rmtree(dest_dir, ignore_errors=True)
            cleaned = True

    try:
        result = subprocess.run(
            [
                "rclone",
                "copyto",
                "{}:{}".format(remote_name, validated_path),
                local_path,
                "--no-traverse",
            ],
            capture_output=True,
            text=True,
            timeout=_AUDIO_DOWNLOAD_TIMEOUT_SECONDS,
            env=_rclone_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        cleanup()
        raise AudioRemoteUnavailableError("rclone invocation failed: {}".format(exc)) from exc

    if result.returncode != 0:
        cleanup()
        stderr = result.stderr.strip()
        if "not found" in stderr.lower() or "error 404" in stderr.lower():
            raise AudioRemoteMissingError(stderr or "remote M4B not found")
        raise AudioRemoteUnavailableError(stderr or "rclone returned a non-zero status")

    try:
        actual_size = os.path.getsize(local_path)
    except OSError as exc:
        cleanup()
        raise AudioRemoteUnavailableError("downloaded M4B is missing") from exc
    if actual_size == 0 or (expected_size > 0 and actual_size != expected_size):
        cleanup()
        raise AudioRemoteUnavailableError(
            "downloaded M4B size mismatch: expected={}, actual={}".format(
                expected_size, actual_size
            )
        )

    return local_path, cleanup


def _get_db_path() -> Path:
    """Get audio.db path from environment or default."""
    env_path = os.environ.get("AUBOOKS_AUDIO_DB")
    if env_path:
        return Path(env_path)
    return Path(_DEFAULT_AUDIO_DB)


def get_audio_status(book_id: int) -> str:
    """
    Get audio status for a book.

    Returns:
        'not_available' | 'queued' | 'processing' | 'ready' | 'failed' | 'cancelled'
    """
    rec = get_audio_record(book_id)
    if rec is None:
        return "not_available"
    return rec.get("status", "not_available")


def get_audio_record(book_id: int, raise_errors: bool = False) -> dict | None:
    """
    Get full audio record for a book.

    Returns dict with keys: book_id, status, filename, opendrive_path, etc.
    Returns None if no record exists or on any error. With ``raise_errors=True``,
    database access errors raise ``AudioDatabaseError`` instead.
    """
    db_path = _get_db_path()

    if not db_path.exists():
        log.debug("audio.db not found at %s", db_path)
        if raise_errors:
            raise AudioDatabaseError("audio.db not found at {}".format(db_path))
        return None

    try:
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
            timeout=5,
        )
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT * FROM audio WHERE book_id = ?", (book_id,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("Failed to read audio.db for book_id=%d: %s", book_id, e)
        if raise_errors:
            raise AudioDatabaseError("failed to read audio.db: {}".format(e)) from e
        return None
    except Exception as e:
        log.warning("Unexpected error reading audio.db for book_id=%d: %s", book_id, e)
        if raise_errors:
            raise AudioDatabaseError("unexpected audio.db error: {}".format(e)) from e
        return None


def get_audio_jobs():
    """Get audio jobs for the tasks page.

    Returns list of dicts with safe fields for display.
    Shows all queued/processing + last _FINISHED_LIMIT ready/failed/cancelled.
    Sorted by updated_at descending (newest first).
    """
    db_path = _get_db_path()

    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
            timeout=5,
        )
        conn.row_factory = sqlite3.Row
        try:
            # Get all active (queued/processing)
            active = conn.execute(
                "SELECT book_id, job_id, requested_by_user_id, status, filename, filesize, duration, "
                "error, created_at, updated_at "
                "FROM audio WHERE status IN ('queued', 'processing') "
                "ORDER BY updated_at DESC"
            ).fetchall()

            # Get recent finished history.
            finished = conn.execute(
                "SELECT book_id, job_id, requested_by_user_id, status, filename, filesize, duration, "
                "error, created_at, updated_at "
                "FROM audio WHERE status IN ('ready', 'failed', 'cancelled') "
                "ORDER BY updated_at DESC LIMIT ?", (_FINISHED_LIMIT,)
            ).fetchall()

            rows = list(active) + list(finished)
            return [dict(row) for row in rows]
        finally:
            conn.close()
    except sqlite3.Error as e:
        log.warning("Failed to read audio.db for jobs list: %s", e)
        return []
    except Exception as e:
        log.warning("Unexpected error reading audio.db for jobs list: %s", e)
        return []
