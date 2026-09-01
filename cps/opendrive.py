# -*- coding: utf-8 -*-

"""OpenDrive cover proxy for AU-Books.

Fetches covers from a local rclone HTTP proxy that serves the
OpenDrive calibre-books-v2 directory. Credentials stay in rclone
config and are never exposed to the browser.

Cover path on OpenDrive: calibre-books-v2/<book_id>/<book_id>.jpg
Local proxy: http://127.0.0.1:19876/<book_id>/<book_id>.jpg
"""

import logging
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

PROXY_BASE_URL = "http://127.0.0.1:19876"
COVER_PATH_TEMPLATE = "{book_id}/{book_id}.jpg"
TIMEOUT_SECONDS = 10
CACHE_MAX_ENTRIES = 200
CACHE_TTL_SECONDS = 3600

_cover_cache = {}


def fetch_cover_from_opendrive(book_id):
    cached = _cover_cache.get(book_id)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL_SECONDS:
        return cached["data"], cached["content_type"]

    cover_url = "{}/{}".format(PROXY_BASE_URL, COVER_PATH_TEMPLATE.format(book_id=book_id))

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
