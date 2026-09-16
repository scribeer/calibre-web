# -*- coding: utf-8 -*-

"""OpenDrive cover fetcher for AU-Books.

Downloads covers directly from OpenDrive via rclone copyto.
Credentials stay in rclone config and are never exposed to the browser.

Cover path on OpenDrive: calibre-books-v2/<bucket>/<book_id>.jpg
where bucket = 1 if book_id < 100 else (book_id // 100) * 100
"""

import logging
import os
import subprocess
import tempfile
import time

log = logging.getLogger(__name__)

RCLONE_REMOTE = "opendrive_content"
CACHE_MAX_ENTRIES = 200
CACHE_TTL_SECONDS = 3600
DEFAULT_REMOTE_ROOT = "calibre-books-v2"
RCLONE_TIMEOUT_SECONDS = 15

_cover_cache = {}


def _opendrive_cover_path(book_id):
    """Compute correct OpenDrive cover path with bucket."""
    bucket = 1 if book_id < 100 else (book_id // 100) * 100
    return f"{DEFAULT_REMOTE_ROOT}/{bucket}/{book_id}.jpg"


def _rclone_env():
    env = os.environ.copy()
    rclone_conf = os.environ.get("RCLONE_CONFIG")
    if rclone_conf:
        env["RCLONE_CONFIG"] = rclone_conf
    return env


def fetch_cover_from_opendrive(book_id):
    cached = _cover_cache.get(book_id)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL_SECONDS:
        return cached["data"], cached["content_type"]

    remote_path = _opendrive_cover_path(book_id)
    full_remote = f"{RCLONE_REMOTE}:{remote_path}"
    tmp_dir = tempfile.mkdtemp(prefix="aubooks_cover_")
    local_path = os.path.join(tmp_dir, f"{book_id}.jpg")

    try:
        result = subprocess.run(
            [
                "rclone",
                "copyto",
                full_remote,
                local_path,
                "--no-traverse",
            ],
            capture_output=True,
            text=True,
            timeout=RCLONE_TIMEOUT_SECONDS,
            env=_rclone_env(),
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "not found" in stderr.lower() or "error 404" in stderr.lower():
                log.debug("Cover not found on OpenDrive for book %s", book_id)
            else:
                log.warning(
                    "rclone cover fetch failed for book %s: %s", book_id, stderr
                )
            return None, None

        if not os.path.isfile(local_path) or os.path.getsize(local_path) == 0:
            return None, None

        with open(local_path, "rb") as f:
            data = f.read()

        if len(data) == 0:
            return None, None

        if len(_cover_cache) >= CACHE_MAX_ENTRIES:
            oldest_key = min(_cover_cache, key=lambda k: _cover_cache[k]["ts"])
            del _cover_cache[oldest_key]

        _cover_cache[book_id] = {
            "data": data,
            "content_type": "image/jpeg",
            "ts": time.time(),
        }
        return data, "image/jpeg"

    except subprocess.TimeoutExpired:
        log.warning("rclone cover fetch timed out for book %s", book_id)
        return None, None
    except Exception as e:
        log.warning("Error fetching cover from OpenDrive for book %s: %s", book_id, e)
        return None, None
    finally:
        try:
            os.unlink(local_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


def compute_opendrive_path(book_id, fmt):
    """Compute OpenDrive remote path for a book source file."""
    bucket = 1 if book_id < 100 else (book_id // 100) * 100
    ext = fmt.lower()
    return f"{DEFAULT_REMOTE_ROOT}/{bucket}/{book_id}.{ext}"


def fetch_ebook_from_opendrive(book_id, fmt):
    """Fetch ebook file from OpenDrive using rclone.

    Returns (local_path, cleanup_callback) on success, or (None, None) on failure.
    The caller MUST call cleanup_callback() after using the file.
    """
    remote_path = compute_opendrive_path(book_id, fmt)
    dest_dir = tempfile.mkdtemp(prefix="aubooks_ebook_")
    local_path = os.path.join(dest_dir, f"{book_id}.{fmt.lower()}")

    try:
        result = subprocess.run(
            [
                "rclone",
                "copyto",
                f"opendrive:{remote_path}",
                local_path,
                "--no-traverse",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "not found" in stderr.lower() or "error 404" in stderr.lower():
                log.debug("Ebook not found on OpenDrive: %s", remote_path)
            else:
                log.warning("Failed to download ebook from OpenDrive: %s", stderr)
            os.rmdir(dest_dir)
            return None, None

        if not os.path.isfile(local_path) or os.path.getsize(local_path) == 0:
            os.rmdir(dest_dir)
            return None, None

        def cleanup():
            try:
                os.unlink(local_path)
            except OSError:
                pass
            try:
                os.rmdir(dest_dir)
            except OSError:
                pass

        return local_path, cleanup

    except Exception as e:
        log.warning("Error fetching ebook from OpenDrive: %s", e)
        try:
            os.rmdir(dest_dir)
        except OSError:
            pass
        return None, None
