# Проект безопасной отмены TTS-задачи
## Цель
Спроектировать отмену одной генерации из раздела «Озвучивание»: администратор может отменить любую задачу, обычный пользователь — только созданную им. Не затрагивать другие TTS-процессы, production и уже выполняющуюся задачу во время аудита.
## Что изучено
- Путь запроса: `cps/web.py` → `cps/aubooks_tts.py` → localhost dispatcher → `aubook-remote.sh` → prepare/TTS/publish → `audio.db`.
- Хранение статусов в `/home/feninf/aubooks/audio_index.py` и фактическая схема `/home/feninf/aubooks/audio.db`.
- Создание job, `job_id`, `RUNNER_PID`, process group, heartbeat, reap, locking, prepare, synthesis и publish в `/home/feninf/bin`.
- Отображение задач и canonical visibility в `cps/tasks_status.py` и AU-шаблонах.
## Результат аудита
Безопасно определить владельца существующей или новой задачи невозможно: Web передаёт только `book_id`, а `audio.db` не хранит идентификатор пользователя. Восстанавливать владельца по IP, сессии, времени или книге нельзя.

Таблица `audio` содержит один row на `book_id`, `job_id` и `CHECK` только для `queued`, `processing`, `ready`, `failed`. Поэтому добавить состояние `cancelled` без migration нельзя.

Dispatcher не содержит собственной очереди или реестра процессов. `start-book-id` сразу создаёт detached session; долговечное состояние находится в `audio.db` и job directory. Перезапуск dispatcher не останавливает runner. `reap` способен возобновить abandoned job в новой session.

Текущий `aubook-remote.sh cancel` не подходит для Web API: он не проверяет владельца, не выполняет атомарный переход в `audio.db`, удаляет job directory, имеет fallback на одиночный PID и не защищён от гонок, PID reuse и последующего reap. Он также не гарантирует, что pipeline не запишет `ready` после отмены.
## Минимальная обязательная migration
1. Пересоздать таблицу `audio`, сохранив данные и индексы, поскольку SQLite не позволяет изменить существующий `CHECK` на месте.
2. Добавить nullable `requested_by_user_id INTEGER` без cross-database foreign key. Для legacy rows оставить `NULL`.
3. Добавить `cancelled` в допустимые статусы.
4. При создании или повторном запуске job атомарно записывать новый `job_id`, `requested_by_user_id` и `queued`. Значение поступает только из server-side `current_user.id`, а не из браузерного параметра.
5. Не выполнять migration над рабочей базой во время текущей активной генерации; сначала проверить её на временной копии.
## Предлагаемая модель отмены
- Endpoint принимает `job_id`, заново читает canonical book/job и требует authentication, AU permission и `current_user.role_admin() OR requested_by_user_id == current_user.id`.
- `requested_by_user_id IS NULL` означает legacy job: её может отменить только admin.
- В `BEGIN IMMEDIATE` выполнить compare-and-set `queued|processing → cancelled` для точного `job_id`. `cancelled → cancelled` идемпотентен; `ready|failed` не отменяются.
- После успешного перехода записать filesystem marker/state `CANCELLED`, проверить принадлежность сохранённого runner к ожидаемой session/job и послать `TERM` только его PGID. После ограниченного ожидания послать `KILL` только той же подтверждённой группе.
- Убрать fallback, который сигнализирует одиночный непроверенный PID. Для защиты от PID reuse хранить и сверять как минимум PID/PGID и Linux process start time.
- Runner и `reap` должны проверять durable `cancelled` перед prepare, после ожидания lock, между стадиями, перед upload и перед `ready`. Все transitions должны использовать compare-and-set, чтобы не перезаписать `cancelled`.
- Cleanup удаляет только artifacts этой job. Job metadata/status следует сохранять до завершения kill/cleanup; опубликованный ранее `ready` audiobook не удалять через cancel.
- Для upload использовать job-scoped staging и последнюю проверку cancellation перед promotion. Если процесс остановлен во время upload, удалить только staging object этой job.
- Повторная генерация после `cancelled` создаёт новый `job_id` и owner атомарным reset, не переиспользуя старую process identity.
## Гонки и восстановление
- Cancel до старта: durable status становится `cancelled`; runner при первом checkpoint завершается, `reap` его не возобновляет.
- Cancel во время synthesis/ffmpeg: сигнал получает только session данной job, включая её дочерние процессы.
- Cancel одновременно с completion: транзакционный compare-and-set определяет победителя. Если `ready` записан первым, cancel возвращает conflict; если `cancelled` записан первым, публикация и `ready` запрещены.
- Повторный cancel возвращает тот же конечный результат без повторного сигнала чужому или переиспользованному PID.
- Restart dispatcher ничего не меняет; решение о resume принимает `reap` по `audio.db`, где `cancelled` является terminal state.
## План изменений после согласования
- `/home/feninf/aubooks/audio_index.py` и `audio_index_ops.py`: migration, owner, cancelled и атомарные transitions.
- `/home/feninf/bin/tts-dispatcher.py` и `aubook-remote.sh`: owner propagation, адресная отмена, checkpoints, safe signaling и cleanup.
- `cps/aubooks_tts.py`, `cps/aubooks_audio.py`, `cps/web.py`, `cps/tasks_status.py`: server-side owner, endpoint, authorization и `can_cancel`.
- `cps/themes/aubooks/templates/tasks.html`: action только в разделе «Озвучивание»; cancelled отображается как повторно доступная генерация.
- Unit/integration tests для admin/user/guest, legacy rows, hidden books, double cancel, queued/processing/completed races, concurrent jobs и dispatcher restart; затем browser smoke в dev-сервисе.
## Изменённые файлы
- `docs/works/2026-09-10-tts-cancellation-design.md` — этот design note.
- Код, schema, runtime status и процессы не изменялись.
## Проверки
- Выполнены read-only inspection schema, process tree, job status и active rows.
- Сигналы процессам не отправлялись, тестовая генерация и migration не запускались.
## Ограничения
- Реализация остановлена до явного согласования schema/persistence migration.
- Существующая активная задача `20260910_034055_1074210` не изменялась и не отменялась.
## Commit
Commit не создавался.
