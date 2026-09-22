# Автоматическая очистка пользовательских данных VPS1
## Цель
Добавить единый безопасный housekeeping-механизм, который ограничивает рост sync-export generations, локальных TTS jobs, базы OpenCode и известных временных каталогов AU-Books в `/tmp`, не затрагивая системные логи и другие данные.
## Что изучено
- `/home/feninf/bin/export-metadata-sync.sh`: расположение generations и lock-файла metadata export.
- `/home/feninf/bin/aubook-remote.sh`: штатная команда `status`, локальные состояния jobs, `control.lock` и правила сопоставления с durable audio status.
- `/home/feninf/bin/audio-index-runtime.py`: контракт `exact-status` для точной пары book/job и делегирование `submission-get`.
- CLI OpenCode: `session list --format json`, `session delete` и `db` для checkpoint/VACUUM.
## Изменённые файлы
- `scripts/vps1-housekeeping.sh`.
- `deploy/vps1/aubooks-vps1-housekeeping.service`.
- `deploy/vps1/aubooks-vps1-housekeeping.timer`.
- `deploy/vps1/install-housekeeping.sh`.
- `tests/test_vps1_housekeeping.py`.
- `docs/works/2026-09-22-vps1-housekeeping.md`.
## Что изменено
- Добавлены режимы `--dry-run` по умолчанию и явный `--apply`, общий `flock`, ротация лога примерно на 1 MiB и отчёт `df` до/после.
- Sync-export сохраняет две самые новые hash-generation и фиксированную FTS5 generation; файлы, symlink и неизвестные каталоги не удаляются. При занятом lock metadata export секция пропускается.
- TTS cleanup получает локальное состояние штатной командой и требует однозначного совпадения с durable status точной job. Активные, `processing`, неизвестные и слишком свежие jobs сохраняются.
- OpenCode cleanup запускается только при DB больше 768 MiB, сохраняет 100 самых свежих и все sessions моложе 30 дней, удаляет только через `opencode session delete`, затем использует CLI для WAL checkpoint и VACUUM при достаточном месте.
- `/tmp` cleanup ограничен четырьмя заданными prefix patterns, возрастом более 48 часов и непосредственными каталогами внутри `/tmp`.
- Все удаления защищены canonical-path/direct-child проверками; safety failure приводит к `SKIP` соответствующей секции.
- Добавлены ежедневные `systemd --user` service/timer и helper установки без перезапуска TTS/OpenCode.
## Тесты
- `python3 -m pytest -q tests/test_vps1_housekeeping.py`: 12 passed.
- `bash -n scripts/vps1-housekeeping.sh`: успешно.
- `bash -n deploy/vps1/install-housekeeping.sh`: успешно.
- `git diff --check`: успешно.
- `shellcheck` не запускался: команда отсутствует на VPS1.
## Известные ограничения
- В dry-run точный объём освобождения OpenCode неизвестен до штатного удаления sessions и VACUUM; отчёт показывает кандидатов, размеры DB/WAL и помечает объём как `unknown`.
- `/var/log` намеренно не затрагивается.
- Реальный `--apply` в рамках первого развёртывания не выполняется без отдельного подтверждения.
## Commit
- Реализация и тесты: `378d2b72`.
