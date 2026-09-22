"""Focused regression tests for TTS chunk recovery and resume validation."""

import asyncio
import importlib.util
import io
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tts_processor.py"
_SPEC = importlib.util.spec_from_file_location("tts_processor", _SCRIPT_PATH)
tts_processor = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tts_processor)


class SynthChunkRetryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_path = Path(self.temp_dir.name) / "part_0001.mp3"
        self.log_fp = io.StringIO()
        self.progress = MagicMock()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_timeout_with_valid_mp3_returns_success(self):
        save = AsyncMock(side_effect=TimeoutError("synthesis timed out"))
        valid = MagicMock(return_value=True)
        remove = MagicMock()
        sleep = AsyncMock()

        with patch.object(tts_processor, "MAX_RETRIES_PER_CHUNK", 2), \
                patch.object(tts_processor, "tts_save", save), \
                patch.object(tts_processor, "is_valid_chunk", valid), \
                patch.object(tts_processor, "_remove_invalid_chunk", remove), \
                patch.object(tts_processor.asyncio, "sleep", sleep):
            result = await tts_processor.synth_chunk_with_retries(
                "text", "voice", self.out_path, 1, self.log_fp, self.progress
            )

        self.assertTrue(result)
        save.assert_awaited_once()
        valid.assert_called_once_with(self.out_path)
        remove.assert_not_called()
        sleep.assert_not_awaited()

    async def test_timeout_without_file_retries_and_fails(self):
        save = AsyncMock(side_effect=[TimeoutError("first"), TimeoutError("second")])
        valid = MagicMock(return_value=False)
        remove = MagicMock(return_value=True)
        sleep = AsyncMock()

        with patch.object(tts_processor, "MAX_RETRIES_PER_CHUNK", 2), \
                patch.object(tts_processor, "tts_save", save), \
                patch.object(tts_processor, "is_valid_chunk", valid), \
                patch.object(tts_processor, "_remove_invalid_chunk", remove), \
                patch.object(tts_processor.asyncio, "sleep", sleep):
            result = await tts_processor.synth_chunk_with_retries(
                "text", "voice", self.out_path, 1, self.log_fp, self.progress
            )

        self.assertFalse(result)
        self.assertEqual(save.await_count, 2)
        self.assertEqual(valid.call_count, 2)
        self.assertEqual(remove.call_count, 2)
        sleep.assert_awaited_once()

    async def test_invalid_partial_is_removed_before_retry(self):
        save = AsyncMock(side_effect=[TimeoutError("partial"), None])
        valid = MagicMock(side_effect=[False, True])
        remove = MagicMock(return_value=True)
        sleep = AsyncMock()

        with patch.object(tts_processor, "MAX_RETRIES_PER_CHUNK", 2), \
                patch.object(tts_processor, "tts_save", save), \
                patch.object(tts_processor, "is_valid_chunk", valid), \
                patch.object(tts_processor, "_remove_invalid_chunk", remove), \
                patch.object(tts_processor.asyncio, "sleep", sleep):
            result = await tts_processor.synth_chunk_with_retries(
                "text", "voice", self.out_path, 1, self.log_fp, self.progress
            )

        self.assertTrue(result)
        self.assertEqual(save.await_count, 2)
        remove.assert_called_once_with(self.out_path, self.log_fp)
        sleep.assert_awaited_once()

    async def _run_process_file_with_existing_part(self, valid_existing):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            input_dir = base / "input"
            temp_dir = base / "temp_book"
            final_dir = base / "final"
            input_dir.mkdir()
            temp_dir.mkdir()
            final_dir.mkdir()
            input_path = input_dir / "book.txt"
            input_path.write_text("chunk text", encoding="utf-8")
            part_path = temp_dir / "part_0001.mp3"
            part_path.write_bytes(b"partial" if not valid_existing else b"audio")
            progress = MagicMock()
            progress.done = 0
            log_path = final_dir / "book.tts.log"

            save = AsyncMock(return_value=True)
            valid = MagicMock(return_value=valid_existing)
            remove = MagicMock(return_value=True)
            patches = (
                ("TEMP_BASE_DIR", base),
                ("FINAL_DIR", final_dir),
                ("JPG_DIR", base / "jpg"),
                ("OPF_DIR", base / "opf"),
                ("UPLOAD_DIR", final_dir),
                ("CONCURRENCY", 1),
                ("TASK_WINDOW", 1),
                ("DELAY_BETWEEN_REQUESTS", 0),
                ("MAX_CONSECUTIVE_FAILURES", 3),
                ("VOICE_BALANCE", "off"),
                ("LOUDNORM", "off"),
                ("FALLBACK_MINUTES", 0),
            )
            with ExitStack() as stack:
                for name, value in patches:
                    stack.enter_context(patch.object(tts_processor, name, value))
                stack.enter_context(patch.object(
                    tts_processor, "build_chunk_plan",
                    return_value=([("chunk", "voice")], []),
                ))
                stack.enter_context(patch.object(
                    tts_processor, "extract_tags_and_lang_from_opf",
                    return_value=("Author", "Title", "rus"),
                ))
                stack.enter_context(patch.object(tts_processor, "load_json", return_value={}))
                stack.enter_context(patch.object(tts_processor, "save_json"))
                stack.enter_context(patch.object(tts_processor, "is_valid_chunk", valid))
                stack.enter_context(patch.object(tts_processor, "_remove_invalid_chunk", remove))
                stack.enter_context(patch.object(tts_processor, "probe_duration", return_value=1.0))
                stack.enter_context(patch.object(tts_processor, "LiveProgress", return_value=progress))
                stack.enter_context(patch.object(tts_processor, "synth_chunk_with_retries", save))
                stack.enter_context(patch.object(tts_processor, "write_ffmetadata", return_value=1))
                stack.enter_context(patch.object(tts_processor, "measure_loudnorm", return_value=None))
                stack.enter_context(patch.object(tts_processor, "balance_voices"))
                stack.enter_context(patch.object(tts_processor, "build_m4b", return_value=True))
                stack.enter_context(patch.object(tts_processor.shutil, "move"))
                stack.enter_context(patch.object(tts_processor.shutil, "rmtree"))
                await tts_processor.process_file(input_dir, "book.txt")

            self.assertEqual(log_path.exists(), False)
            return save, valid, remove

    async def test_valid_existing_part_is_not_resynthesized(self):
        save, valid, remove = await self._run_process_file_with_existing_part(True)

        save.assert_not_awaited()
        valid.assert_called_once()
        remove.assert_not_called()

    async def test_invalid_existing_part_is_resynthesized(self):
        save, valid, remove = await self._run_process_file_with_existing_part(False)

        save.assert_awaited_once()
        self.assertEqual(valid.call_count, 1)
        remove.assert_called_once()


if __name__ == "__main__":
    unittest.main()
