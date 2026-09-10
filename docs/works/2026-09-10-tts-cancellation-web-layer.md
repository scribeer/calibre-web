# Web-слой авторизованной отмены озвучивания (Stage 2B)
## Цель
Аудит уже подготовленных (незакоммиченных) изменений Stage 2 в Calibre-Web против runtime-контракта Stage 2A и минимальное исправление/дополнение: отмена задачи из раздела «Озвучивание», где admin может отменить любую активную задачу, а обычный пользователь — только свою.
## Что изучено
- Callers очереди: единственный источник `queue_book()` — `web.generate_audio`, owner передаётся только из server-side `current_user.id`; dispatcher требует положительный `requested_by_user_id`. Не-пользовательских/legacy caller без owner не найдено (документы 2026-09-04/2026-09-05 описывают историческое поведение).
- Контракт `/cancel/<job_id>` из `/home/feninf/bin/tts-dispatcher.py`: safe regex `[A-Za-z0-9][A-Za-z0-9_.-]*` после urlsplit+unquote; статусы `cancelled`, `already_cancelled`, `conflict`, `invalid_id`, `not_found`, `identity_unconfirmed`, `termination_failed`, `cleanup_failed`, `runtime_error`, `timeout`.
- `cps/aubooks_tts.py` — `cancel_job()` c `CancelResult`; критические случаи (timeout, URLError, invalid JSON, HTTP error) возвращают безопасные generic-сообщения.
- `cps/aubooks_permissions.py` — тема AU: любой аутентифицированный; стандартная тема: legacy роли (не разламывать `04ffd08f`).
- `cps/tasks_status.py` `get_tts_jobs_json`, `cps/aubooks_audio.py` `get_audio_record`/`get_audio_jobs`, шаблоны `tasks.html`, `detail.html`, JS-поллинг detail.
## Что переиспользовано (без переписывания)
- `cancel_audio_job` в `cps/web.py` (POST, login, CSRF, canonical visibility, trusted job_id, policy admin/owner, legacy NULL).
- `cancel_job`/`CancelResult` transport и test transport.
- `can_cancel` в `get_tts_jobs_json`, `cancelled` label «Отменено», сокрытие owner/opendrive_path/sha256/PID/PGID/paths.
- Поведение detail.html (без кнопки отмены; cancelled → «Озвучить», guest → login).
- Tests: auth (owner/admin/other/legacy/hidden/CSRF/stale), guest login redirect, regeneration with server owner.
## Изменённые файлы
- `cps/themes/aubooks/templates/tasks.html`: кнопка отмены вынесена в классы `tts-cancel-form`/`tts-cancel-btn`; балка подтверждения «Отменить озвучивание этой книги?»; AJAX POST с CSRF (заголовок `X-Requested-With`), кнопка temporarily disabled, без full page reload, затем обновление через существующий `loadTtsJobs()`; контейнер `#tts-cancel-error` для безопасного показа ошибки; `failed|cancelled` → «Открыть книгу».
- `cps/web.py`: для AJAX-запроса endpoint возвращает JSON (`{ok:true,status:"cancelled"}` или `{ok:false,message}` со статусом 400), не перезагружая страницу; для обычного POST сохранён redirect 303 + flash.
- `tests/test_aubooks_tts_transport.py`: `test_timeout` больше не висит на реальном slow server (патч `urlopen` на `TimeoutError`), удалён `_SlowDispatcher`.
- `tests/test_aubooks_tts_cancellation.py`: добавлены AJAX JSON-тесты и тест `test_stale_cancel_after_replacement_never_touches_new_job` (S8 scenario).
- `tests/test_aubooks_audio.py`: `TestTtsJobsTemplate.test_cancel_uses_confirm_and_ajax_without_full_reload`.
## Проверки (tests)
- `test_aubooks_tts_cancellation.py` — 15 passed + 6 subtests (owner queued/processing, admin legacy/other, normal legacy FALSE, other FORBIDDEN, hidden 404, CSRF required, spoof owner, stale job, AJAX JSON, dispatcher error не протекает).
- `test_aubooks_tts_transport.py` — 14 passed + 5 subtests (cancel POST quoted no body, machine-readable result, только cancelled/already_cancelled как success, timeout/invalid JSON safe).
- `test_aubooks_user_permissions.py` — 22 passed (в т.ч. guest cancel → /login, regeneration `cancelled` → `queue_book(10, user.id)`).
- `test_aubooks_audio.py` + `test_aubooks_generate_audio.py` — 114 passed (+ tasks UI confirm/AJAX assertions).
- Регрессии сопредельных модулей — 163 passed + 245 subtests.
Итого 165 passed + 13 subtests в релевантных модулях, регрессии чисты.
## Ограничения
- Browser smoke отмены пропущен по п.10: `calibre-web-dev.service` разделяет реальный dispatcher (`TTS_DISPATCH_URL=http://127.0.0.1:18900`) и реальный `/home/feninf/aubooks/audio.db`; активных задач в реальной базе нет (только terminal `failed`), создание безопасной тестовой задачи потребовало бы реального dispatcher. Не-Cancel часть проверена unit-тестами шаблонов.
- `run-calibre-web-dev-isolated.sh` (файл-скрипт dev-сервиса) не изменялся.
- Production VPS2, `opencode-calibre-web.service`, реальные задачи, runtime `/home/feninf/bin`, `/home/feninf/aubooks` не затрагивались.
## Commit
Создан commit в ветке `aubooks` (см. ниже).