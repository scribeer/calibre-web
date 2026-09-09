# -*- coding: utf-8 -*-

"""OpenDrive cover proxy for AU-Books.

Fetches covers from a local rclone HTTP proxy that serves the
OpenDrive calibre-books-v2 directory. Credentials stay in rclone
config and are never exposed to the browser.

Cover path on OpenDrive: calibre-books-v2/<bucket>/<book_id>.jpg
where bucket = 1 if book_id < 100 else (book_id // 100) * 100
Local proxy: http://127.0.0.1:19876/<bucket>/<book_id>.jpg
"""

import logging
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

PROXY_BASE_URL = "http://127.0.0.1:19876"
TIMEOUT_SECONDS = 10
CACHE_MAX_ENTRIES = 200
CACHE_TTL_SECONDS = 3600
DEFAULT_REMOTE_ROOT = "calibre-books-v2"

_cover_cache = {}


def _opendrive_cover_path(book_id):
    """Compute correct OpenDrive cover path with bucket."""
    bucket = 1 if book_id < 100 else (book_id // 100) * 100
    return f"{bucket}/{book_id}.jpg"


def fetch_cover_from_opendrive(book_id):
    cached = _cover_cache.get(book_id)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL_SECONDS:
        return cached["data"], cached["content_type"]

    cover_url = "{}/{}".format(PROXY_BASE_URL, _opendrive_cover_path(book_id))

    try:
        request = urllib.request.Request(cover_url)
        response = urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
        content_type = response.headers.get("Content-Type", "image/jpeg")
        data = response.read()
        response.close()

        if len(data) == 0:
            return None, None

        if len(_cover_cache) >= CACHE_MAX_ENTRIES:
            oldest_key = min(_cover_cache, key=lambda k: _cover_cache[k]["ts"])
            del _cover_cache[oldest_key]

        _cover_cache[book_id] = {
            "data": data,
            "content_type": content_type,
            "ts": time.time(),
        }
        return data, content_type
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.debug("Cover not found on OpenDrive for book %s", book_id)
        else:
            log.warning(
                "OpenDrive proxy HTTP %d for book %s: %s", e.code, book_id, e.reason
            )
        return None, None
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        log.warning("OpenDrive proxy request failed for book %s: %s", book_id, e)
        return None, None


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
