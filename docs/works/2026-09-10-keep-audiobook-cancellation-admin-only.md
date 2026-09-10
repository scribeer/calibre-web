# Отмена озвучивания остаётся только у админа (runtime), пользовательская web-отмена удалена
## Цель
Продуктовое решение: пользователь не должен отменять TTS-задачи из Calibre-Web. Убрать web-отмену (endpoint, transport-клиент, поля JSON, кнопку/AJAX), сохранив runtime/admin отмену, `cancelled`-статус, requeue, владение (`requested_by_user_id`) и текущие permissions.
## Что было изучено
- `cps/web.py` `cancel_audio_job` (`/books/<book_id>/audio/jobs/<job_id>/cancel`, POST) — единственный пользовательский транспорт отмены.
- `cps/aubooks_tts.py` `cancel_job`/`CancelResult`/`_CANCEL_REJECTED` — HTTP-клиент `/cancel/<job_id>`; использовался только web-эндпоинтом.
- `cps/tasks_status.py` `get_tts_jobs_json` — поля `can_cancel`/`cancel_url` и вычисление владельца/админа.
- `cps/themes/aubooks/templates/tasks.html` — баннер `#tts-cancel-error`, форма `.tts-cancel-form`, кнопка `tts-cancel-btn`, confirm-диалог, AJAX-обработчик.
- `tests/`: `test_aubooks_tts_cancellation.py` (целиком про web-cancel), cancel-тесты в `test_aubooks_tts_transport.py`, `test_aubooks_user_permissions.py`, `test_aubooks_audio.py`; устаревшие payload-тесты в `test_tts_dispatcher.py`.
- `/home/feninf/bin/tts-dispatcher.py` `/cancel/<job_id>` и `/home/feninf/bin/aubook-remote.sh` `cancel-job` — runtime-отмена, НЕ удаляются.
## Изменения
- `cps/web.py`: удалён эндпоинт `cancel_audio_job`.
- `cps/aubooks_tts.py`: удалены `cancel_job`, `CancelResult`, `_CANCEL_REJECTED`, неиспользуемый `import urllib.parse`. `queue_book` и `QueueResult` без изменений.
- `cps/tasks_status.py`: убраны вычисление owner/can_cancel и поля `can_cancel`/`cancel_url`; удалён импорт `can_generate_tts`. JSON задач теперь: статус + метаданные + download_url без полей отмены.
- `cps/themes/aubooks/templates/tasks.html`: удалены баннер ошибки отмены, cancel-форма/кнопка, confirm-диалог и AJAX-обработчик; действия остаются: ready→«Скачать аудиокнигу», failed/cancelled→«Открыть книгу», прочее→дефис.
- `tests/`: удалён `test_aubooks_tts_cancellation.py` (удаление через `git rm`); убраны cancel-тесты транспорта (`test_cancel_posts_quoted_job_without_body`, `test_cancel_result_is_machine_readable`, `test_cancel_accepts_only_cancelled_success_statuses`, часть `test_transport_rejects_invalid_identifier_types_without_request`); убран `test_guest_tts_cancel_redirects_to_login`; в `test_aubooks_audio.py` cancel-тесты заменены на негативные (`test_no_cancel_button`, `test_action_keeps_download_and_open_actions`, `test_cancellation_fields_are_not_returned`).
- `tests/test_tts_dispatcher.py`: обновлён под текущий контракт очереди — payload `{book_id, requested_by_user_id}` в success-путях; `test_failed_dispatch` ожидает 404 (exit 4 → Book not found), а не 500. Валидация dispatcher не ослаблена.
- Обновлён `docs/works/2026-09-10-integration-check-tts-cancellation.md` — помечен как проверка до изменения продукта.
## Что сохранено
- `cancelled` — терминальный статус; tasks: «Отменено»; detail: cancelled → «Озвучить»; requeue отменённой задачи даёт новый `job_id` с владельцем = новый запросивший.
- Владение `requested_by_user_id` для истории/диагностики/квот/админа.
- Runtime/admin-отмена: dispatcher `/cancel/<job_id>` (safe path, exact-job), `aubook-remote.sh cancel-job` с identity-снапшотом и `kill -- -PGID`; process/session isolation; CAS-переходы в `audio_index.py`.
- Permissions AU-Books: любой зарегистрированный пользователь генерирует/скачивает; Guest видит действия и уходит в login с ссылкой на регистрацию.
## Проверки
- calibre-web: `test_aubooks_tts_transport.py`, `test_tts_dispatcher.py`, `test_aubooks_audio.py`, `test_aubooks_user_permissions.py`, `test_aubooks_generate_audio.py` — 164 passed + 3 subtests.
- aubooks: `test_audio_index` 27 OK, `test_audio_index_cancellation` 21 OK, `test_audio_index_pipeline` 39 OK.
- bin: `test_tts_cancellation` 15 OK.
- `py_compile` изменённых модулей — OK; `git diff --check` — чисто.
- Dead-code поиск по `cancel_audio_job`, `cancel_job(`, `can_cancel`, `tts-cancel`, «Отменить озвучивание этой книги?», `CancelResult`, `_CANCEL_REJECTED`, `"/cancel/"` — в Calibre-Web пользовательских путей нет (остались только негативные `assertNotIn` в тестах и dispatcher в `/home/feninf/bin`).
## Известные ограничения
- В dev/production реальные TTS-задания не запускались; runtime-отмена покрыта bin-сьютом на синтетических temp-заданиях.
- Журнал создан в том же коммите, что и изменения; hash см. `git log` (commit message `refactor: keep audiobook cancellation admin-only`).
- `tests/test_aubooks_audio.py` helper `_request` сохраняет параметры `admin`/`tts`, оставшиеся неиспользуемыми после удаления cancel-тестов (безвредно, минимальный diff).
## Git
Ветка `aubooks`, базовые коммиты `3b11cb5c`, `b6e4e1ef`. Push не выполнялся; production и сервис не затрагивались.