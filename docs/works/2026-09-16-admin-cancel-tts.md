# Admin Cancel TTS — optimistic concurrency, cleanup retry, fail-closed staging

## Цель

Закрыть три review findings в admin-only кнопке «Отменить озвучивание»:
1. stale form race — старая страница может отменить replacement job
2. partial cleanup retry — cancelled без завершённого cleanup невозможно повторить
3. remote staging fail-closed — rclone ls failure не должен считаться отсутствием объекта

## Что было изучено

- Текущий flow: browser → POST `/audio/cancel/<book_id>` → local DB read → dispatcher `POST /cancel` → runtime `aubook-remote.sh cancel-job` → `cleanup_cancelled_job` → `rclone deletefile`.
- `make_job` в tests вызывает `queue_job` автоматически;的竞争 с `skip_db=True` для replacement jobs.
- `cmd_cancel` в `aubook-remote.sh` валидирует exact `book_id + job_id` через audio.db; stale旧 job correctly returns `conflict`.

## Изменённые файлы

### `/home/feninf/bin/tts-dispatcher.py`
- `_cancel_exact()`: `cancelled` добавлен в allowed statuses для retry cleanup.
- Если `cancelled` + `_cancel_runtime` вернул `not_found` → immediate `already_cancelled`.
- Post-conflict recheck: `cancelled` → `already_cancelled` (.cleanup уже был выполнен до conflict).

### `/home/feninf/bin/aubook-remote.sh`
- `cleanup_cancelled_job()`: `rclone ls` заменён на `rclone lsf` родительского каталога + `grep -Fxq`.
- Listing failure (exit non-zero) → `return 1` (fail-closed), local artifacts preserved.
- Listing success + absent → OK, no delete needed.
- Listing success + present → `rclone deletefile`.

### `/home/feninf/calibre-web/cps/tasks_status.py`
- Добавлен `cancel_job_id` (observed job_id) для конкретной строки в JSON.

### `/home/feninf/calibre-web/cps/themes/aubooks/templates/tasks.html`
- Hidden field `job_id` с `row.cancel_job_id` в cancel form.

### `/home/feninf/calibre-web/cps/web.py`
- `cancel_audio_job()`: `request.form.get("job_id") != record["job_id"]` → stale message, dispatcher НЕ вызывается.

### `/home/feninf/calibre-web/cps/aubooks_tts.py`
- `CancelResult` и `cancel_job()` для JSON transport в dispatcher.

### `/home/feninf/aubooks/audio_index.py`
- `mark_cancelled()` записывает `error="Cancelled by administrator"`.

## Тесты

### VPS1 `/home/feninf/bin/tests/test_tts_cancellation.py`
- `test_cancelled_exact_job_retries_incomplete_runtime_cleanup` — dispatcher retries cleanup for `cancelled` status.
- `test_cancel_staging_error_preserves_local_artifacts` — `rclone lsf` exit 1 → cleanup_failed, local artifacts preserved.
- `test_cancel_staging_timeout_preserves_local_artifacts` — `rclone lsf` hang → cleanup_failed.
- `test_cancel_staging_absent_with_successful_listing_is_success` — empty listing → OK, no delete.
- `test_cancel_staging_present_is_deleted` — listing matches → deleted.
- `test_cancelled_job_retries_incomplete_cleanup` — first cancel fails, second succeeds, third idempotent.
- `test_cancelled_retry_does_not_touch_replacement_job` — old cancelled + replacement job → conflict, replacement untouched.
- `skip_db=True` parameter added to `make_job` for replacement job scenarios.

### VPS1 audio_index: 173 passed
### VPS2 focused suite: 96 passed (transport + cancellation + audio)

## Три закрытых review findings

### 1. STALE UI FORM / REPLACEMENT JOB RACE
- `tasks_status.py` передаёт `cancel_job_id` для конкретной строки.
- `tasks.html` отправляет hidden `job_id` с observed value.
- `web.py` сверяет `request.form.get("job_id") != record["job_id"]` → stale/conflict, dispatcher НЕ вызывается.
- Browser `job_id` используется ТОЛЬКО как compare value, не как target.

### 2. REPEATED CANCEL AFTER PARTIAL CLEANUP FAILURE
- `tts-dispatcher.py` `_cancel_exact()`: `cancelled` status → retry runtime cleanup, не immediate `already_cancelled`.
- `_cancel_runtime` возвращает `not_found` → `already_cancelled` (cleanup завершён).
- `_cancel_runtime` возвращает `cleanup_failed` → controlled error, можно повторить.

### 3. REMOTE STAGING CLEANUP MUST FAIL CLOSED
- `rclone lsf` родительского каталога + `grep -Fxq` exact filename.
- Exit 0 + absent → success (no delete).
- Exit 0 + present → delete.
- Exit non-zero / timeout → fail-closed, local artifacts preserved, `cleanup_failed`.

## Известные ограничения

- `book_id=6528` не тестировался и не затрагивался.
- Известные несвязанные dirty-helper/invite-test failures не исправлялись.
- Production deploy ещё не выполнен.

## Результаты тестов

- VPS1 `test_tts_cancellation.py`: 40 passed, 9 subtests
- VPS1 `aubooks/tests/`: 173 passed, 12 subtests
- VPS2 `test_aubooks_tts_transport.py` + `test_aubooks_tts_cancellation.py` + `test_aubooks_audio.py`: 96 passed, 10 subtests
- `bash -n aubook-remote.sh`: OK
- `py_compile tts-dispatcher.py`: OK
- `git diff --check`: clean (all three repos)
