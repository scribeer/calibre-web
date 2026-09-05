"""
Transport abstraction for AU-Books TTS queue.

Provides a clean API for Calibre-Web to submit books for TTS processing.
The actual transport (local subprocess, SSH, API) is configurable.

Current implementation: HTTP dispatcher running outside mount namespace.
The dispatcher runs tts-dispatcher.py on localhost:18900 and delegates
to aubook-remote.sh start-book-id.
"""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

_DEFAULT_DISPATCH_URL = "http://127.0.0.1:18900"


class QueueResult:
    """Result of a queue_book call."""

    __slots__ = ("success", "exit_code", "error_message", "job_id")

    def __init__(self, success: bool, exit_code: int = 0, error_message: str = "", job_id: str = ""):
        self.success = success
        self.exit_code = exit_code
        self.error_message = error_message
        self.job_id = job_id

    def __repr__(self):
        return f"QueueResult(success={self.success}, exit_code={self.exit_code}, error={self.error_message!r})"


def queue_book(book_id: int, voice: int = 1, publish: bool = True,
               remote_path: str | None = None) -> QueueResult:
    """Submit a book for TTS processing via HTTP dispatcher.

    Args:
        book_id: Calibre book ID.
        voice: Voice choice (1=female, 2=male). Accepted for API
               compatibility but dispatcher always uses voice=1.
        publish: Whether to publish to OpenDrive after TTS. Accepted for
                 API compatibility but dispatcher always publishes.
        remote_path: Ignored (kept for backward compat). The dispatcher
                     URL is controlled by TTS_DISPATCH_URL env var.

    Returns:
        QueueResult with success/error information.
    """
    dispatch_url = os.environ.get("TTS_DISPATCH_URL", _DEFAULT_DISPATCH_URL)
    url = f"{dispatch_url}/queue"

    payload = json.dumps({"book_id": book_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            return QueueResult(False, exc.code, f"Dispatcher error (HTTP {exc.code}).")
        # HTTPError with valid JSON body
        return QueueResult(
            False,
            data.get("code", exc.code),
            data.get("error", f"Dispatcher error (HTTP {exc.code})."),
        )
    except urllib.error.URLError as exc:
        log.error("Dispatcher unavailable: %s", exc)
        return QueueResult(False, 1, "Audio generation service is unavailable.")
    except TimeoutError:
        log.error("Dispatcher timed out for book %d", book_id)
        return QueueResult(False, 1, "Audio generation service timed out.")
    except Exception as exc:
        log.error("Dispatcher communication failed for book %d: %s", book_id, exc)
        return QueueResult(False, 1, "Audio generation service is unavailable.")

    if data.get("ok"):
        job_id = data.get("job_id", "")
        log.info("TTS job queued for book %d: %s", book_id, job_id)
        return QueueResult(True, 0, "", job_id)

    return QueueResult(False, data.get("code", 1), data.get("error", "Unknown error."))
