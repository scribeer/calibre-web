# Исправление скачивания готовых аудиокниг
## Цель
Устранить production 500 при скачивании готовой M4B через Calibre-Web без ручных правок active release и без изменения storage architecture.
## Что изучено
- Production release `d2fe40f8d15bf1fd73965e1c7ee01991b8a09041`.
- Route `cps.web.download_audiobook` и read-only adapter `cps.aubooks_audio`.
- Запись `book_id=1` в `/opt/calibre-web/data/audio.db`.
- Application log `/opt/calibre-web/config/calibre-web.log`.
- Production environment `AUBOOKS_BOOKS_REMOTE`, `RCLONE_CONFIG`, `AUBOOKS_AUDIO_DB`.
- Доступ пользователя `calibreweb` к M4B через существующий rclone remote.
## Причина
Route использовал hardcoded remote `opendrive:`, которого нет в production `rclone.conf`. Реальный remote называется `opendrive_content`. `rclone` завершался с ошибкой `didn't find section in config file`, после чего route выполнял `abort(500)` на строке 2154. Кроме того, unconditional `finally` удалял temp path до завершения отдачи Flask response.
## Изменённые файлы
- `cps/aubooks_audio.py`
- `cps/web.py`
- `tests/test_aubooks_audio_download.py`
- `tests/test_aubooks_user_permissions.py`
- `docs/works/2026-09-17-fix-audiobook-download.md`
## Что изменено
- Remote name безопасно извлекается из существующего `AUBOOKS_BOOKS_REMOTE`; remote path берётся только из local `audio.db`.
- Допускаются только относительные `Audiobooks/.../*.m4b` без traversal, backslash и remote injection.
- Добавлены disk preflight, explicit `RCLONE_CONFIG`, проверка размера и timeout.
- M4B скачивается во временный release-local файл; Flask возвращает `X-Accel-Redirect`, а существующий nginx `/static/` отдаёт body без буферизации Tornado WSGI в Python RAM.
- Cleanup запускается daemon timer после передачи управления nginx и выполняется также после client disconnect; при ошибках temp удаляется сразу.
- Row missing, not ready, invalid path, remote missing, rclone/storage failure и database failure имеют отдельные controlled responses и технические логи.
## Тесты
- Focused audiobook tests: 36 passed, 6 subtests.
- Полный AU-Books regression набор: 405 passed, 261 subtests.
- `py_compile`: успешно.
- `git diff --check`: успешно.
- Production acceptance выявил, что Tornado WSGI выполняет `b"".join(response)` и при нескольких больших M4B может быть убит OOM killer. Поэтому body передан существующему nginx static handler через `X-Accel-Redirect`.
## Ограничения
- Каждый download сначала временно сохраняет полный M4B на VPS2; постоянного хранения и Python RAM buffering нет. Cleanup delay составляет 30 секунд после передачи файла nginx.
## Commit
- Fix commit: `f2cedcfc4bd477d567ff0a3c375c8326706d48ab`.
- Streaming cleanup fix: `7e327e92e733c5a4baba413b452088ded8551660`.
