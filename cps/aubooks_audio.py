"""
Read-only adapter for audio.db in Calibre-Web.

Provides safe access to audiobook status from the AU-Books audio index.
Never writes to audio.db. Falls back to 'not_available' on any error.
"""

import logging
import os
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

# Default path to audio.db — configurable via AUBOOKS_AUDIO_DB env var
_DEFAULT_AUDIO_DB = "/home/feninf/aubooks/audio.db"

# Status labels for Russian UI
STATUS_LABELS = {
    "queued": "В очереди",
    "processing": "Озвучивается…",
    "ready": "Готово",
    "failed": "Ошибка",
}

# Limit for finished jobs shown in tasks page
_FINISHED_LIMIT = 50


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
        'not_available' | 'queued' | 'processing' | 'ready' | 'failed'
    """
    rec = get_audio_record(book_id)
    if rec is None:
        return "not_available"
    return rec.get("status", "not_available")


def get_audio_record(book_id: int) -> dict | None:
    """
    Get full audio record for a book.

    Returns dict with keys: book_id, status, filename, opendrive_path, etc.
    Returns None if no record exists or on any error.
    """
    db_path = _get_db_path()

    if not db_path.exists():
        log.debug("audio.db not found at %s", db_path)
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
        return None
    except Exception as e:
        log.warning("Unexpected error reading audio.db for book_id=%d: %s", book_id, e)
        return None


def get_audio_jobs():
    """Get audio jobs for the tasks page.

    Returns list of dicts with safe fields for display.
    Shows all queued/processing + last _FINISHED_LIMIT ready/failed.
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
                "SELECT book_id, status, filename, filesize, duration, error, created_at, updated_at "
                "FROM audio WHERE status IN ('queued', 'processing') "
                "ORDER BY updated_at DESC"
            ).fetchall()

            # Get recent finished (ready/failed)
            finished = conn.execute(
                "SELECT book_id, status, filename, filesize, duration, error, created_at, updated_at "
                "FROM audio WHERE status IN ('ready', 'failed') "
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
