"""
Transport abstraction for AU-Books TTS queue.

Provides a clean API for Calibre-Web to submit books for TTS processing.
The actual transport (local subprocess, SSH, API) is configurable.

Current implementation: local subprocess calling aubook-remote.sh start-book-id.
"""

import logging
import os
import subprocess

log = logging.getLogger(__name__)

# Default path to the pipeline entry point
_DEFAULT_AUBOOK_REMOTE = os.path.join(os.path.expanduser("~"), "bin", "aubook-remote.sh")


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


# Exit code → user-facing message mapping
_EXIT_MESSAGES = {
    2: "This book is already being processed.",
    3: "Audio is already available.",
    4: "Book not found in the TTS library.",
    5: "No supported source format available for TTS.",
    6: "Previous attempt failed. Please try again later.",
    7: "Source file is missing from the library.",
}


def queue_book(book_id: int, voice: int = 1, publish: bool = True,
               remote_path: str | None = None) -> QueueResult:
    """Submit a book for TTS processing.

    Args:
        book_id: Calibre book ID.
        voice: Voice choice (1=female, 2=male).
        publish: Whether to publish to OpenDrive after TTS.
        remote_path: Path to aubook-remote.sh. If None, uses default.

    Returns:
        QueueResult with success/error information.
    """
    remote = remote_path or _DEFAULT_AUBOOK_REMOTE

    if not os.path.isfile(remote):
        log.error("Pipeline not found: %s", remote)
        return QueueResult(False, 1, "Audio generation service is unavailable.")

    cmd = [remote, "start-book-id", str(book_id), str(voice)]
    if publish:
        cmd.append("publish")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        log.error("Pipeline executable not found: %s", remote)
        return QueueResult(False, 1, "Audio generation service is unavailable.")
    except subprocess.TimeoutExpired:
        log.error("Pipeline timed out for book %d", book_id)
        return QueueResult(False, 1, "Audio generation service timed out.")
    except OSError as e:
        log.error("Failed to start pipeline for book %d: %s", book_id, e)
        return QueueResult(False, 1, "Could not start audio generation.")

    exit_code = proc.returncode
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if exit_code == 0:
        # Parse JOB=<id> from stdout
        job_id = ""
        for line in stdout.splitlines():
            if line.startswith("JOB="):
                job_id = line[4:]
                break
        log.info("TTS job queued for book %d: %s", book_id, job_id)
        return QueueResult(True, 0, "", job_id)

    # Non-zero exit: map exit code to message
    error_msg = _EXIT_MESSAGES.get(exit_code, "Audio generation failed.")
    # Append stderr detail for logging (not shown to user)
    if stderr:
        log.warning("TTS queue failed for book %d (exit %d): %s", book_id, exit_code, stderr)

    return QueueResult(False, exit_code, error_msg)
