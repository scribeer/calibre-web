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
_INVALID_RESPONSE = "Audio generation service returned an invalid response."
_QUEUE_REJECTED = "Audio generation service rejected the request."
_CANCEL_REJECTED = "Audio generation service could not cancel the job."


def _read_json_response(response, operation):
    try:
        raw = response.read().decode("utf-8")
    except Exception as exc:
        log.warning("Invalid dispatcher response encoding for %s: %s", operation, exc)
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        log.warning("Invalid dispatcher JSON for %s: %r", operation, raw)
        return None
    if not isinstance(data, dict):
        log.warning("Invalid dispatcher response type for %s: %r", operation, data)
        return None
    return data


def _response_code(data, default):
    code = data.get("code", default)
    return code if isinstance(code, int) and not isinstance(code, bool) else default


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


class CancelResult:
    """Machine-readable result of a cancel_job call."""

    __slots__ = ("success", "exit_code", "error_message", "status")

    def __init__(self, success: bool, exit_code: int = 0,
                 error_message: str = "", status: str = ""):
        self.success = success
        self.exit_code = exit_code
        self.error_message = error_message
        self.status = status


def queue_book(book_id: int, requested_by_user_id: int) -> QueueResult:
    """Submit a book for TTS processing via HTTP dispatcher.

    Args:
        book_id: Calibre book ID.
        requested_by_user_id: Calibre-Web user ID from the authenticated
                              server-side session.

    Returns:
        QueueResult with success/error information.
    """
    if (not isinstance(book_id, int) or isinstance(book_id, bool)
            or not isinstance(requested_by_user_id, int) or isinstance(requested_by_user_id, bool)):
        return QueueResult(False, 1, _INVALID_RESPONSE)

    dispatch_url = os.environ.get("TTS_DISPATCH_URL", _DEFAULT_DISPATCH_URL)
    url = f"{dispatch_url}/queue"

    payload = json.dumps({
        "book_id": book_id,
        "requested_by_user_id": requested_by_user_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = _read_json_response(resp, "queue")
    except urllib.error.HTTPError as exc:
        data = _read_json_response(exc, "queue HTTP error")
        if data is not None:
            log.warning("Dispatcher rejected queue request: %r", data)
        return QueueResult(False, _response_code(data, exc.code) if data else exc.code, _QUEUE_REJECTED)
    except urllib.error.URLError as exc:
        log.error("Dispatcher unavailable: %s", exc)
        return QueueResult(False, 1, "Audio generation service is unavailable.")
    except TimeoutError:
        log.error("Dispatcher timed out for book %d", book_id)
        return QueueResult(False, 1, "Audio generation service timed out.")
    except Exception as exc:
        log.error("Dispatcher communication failed for book %d: %s", book_id, exc)
        return QueueResult(False, 1, "Audio generation service is unavailable.")

    if data is None:
        return QueueResult(False, 1, _INVALID_RESPONSE)
    if data.get("ok") is True:
        job_id = data.get("job_id", "")
        if not isinstance(job_id, str) or not job_id:
            log.warning("Dispatcher queue success omitted a valid job_id: %r", data)
            return QueueResult(False, 1, _INVALID_RESPONSE)
        log.info("TTS job queued for book %d: %s", book_id, job_id)
        return QueueResult(True, 0, "", job_id)
    if data.get("ok") is False:
        log.warning("Dispatcher rejected queue request: %r", data)
        return QueueResult(False, _response_code(data, 1), _QUEUE_REJECTED)
    log.warning("Dispatcher queue response omitted a boolean ok field: %r", data)
    return QueueResult(False, 1, _INVALID_RESPONSE)


def cancel_job(book_id: int, job_id: str) -> CancelResult:
    """Cancel the trusted current book/job pair via the dispatcher."""
    if (not isinstance(book_id, int) or isinstance(book_id, bool)
            or not isinstance(job_id, str) or not job_id):
        return CancelResult(False, 1, _INVALID_RESPONSE)

    dispatch_url = os.environ.get("TTS_DISPATCH_URL", _DEFAULT_DISPATCH_URL)
    payload = json.dumps({"book_id": book_id, "job_id": job_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{dispatch_url}/cancel",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = _read_json_response(resp, "cancel")
    except urllib.error.HTTPError as exc:
        data = _read_json_response(exc, "cancel HTTP error")
        status = data.get("status", "") if data else ""
        if data is not None:
            log.warning("Dispatcher rejected cancellation: %r", data)
        return CancelResult(False, _response_code(data, exc.code) if data else exc.code,
                            _CANCEL_REJECTED, status)
    except urllib.error.URLError as exc:
        log.error("Dispatcher unavailable while cancelling book %d: %s", book_id, exc)
        return CancelResult(False, 1, "Audio generation service is unavailable.", "unavailable")
    except TimeoutError:
        log.error("Dispatcher timed out while cancelling book %d", book_id)
        return CancelResult(False, 1, "Audio generation service timed out.", "timeout")
    except Exception as exc:
        log.error("Dispatcher cancellation failed for book %d: %s", book_id, exc)
        return CancelResult(False, 1, "Audio generation service is unavailable.", "unavailable")

    if data is None:
        return CancelResult(False, 1, _INVALID_RESPONSE)
    status = data.get("status", "")
    if data.get("ok") is True and status in (
            "cancelled", "already_cancelled", "already_failed"):
        return CancelResult(True, 0, "", status)
    if data.get("ok") is False:
        log.warning("Dispatcher rejected cancellation: %r", data)
        return CancelResult(False, _response_code(data, 1), _CANCEL_REJECTED, status)
    log.warning("Invalid dispatcher cancellation result: %r", data)
    return CancelResult(False, 1, _INVALID_RESPONSE)
