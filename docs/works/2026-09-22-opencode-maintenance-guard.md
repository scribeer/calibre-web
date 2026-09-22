# Ограничение OpenCode maintenance фактическими удалениями
## Цель
Исключить WAL checkpoint и VACUUM, если housekeeping не удалил ни одной OpenCode session в текущем запуске.
## Что изучено
- Только ветка OpenCode cleanup в `scripts/vps1-housekeeping.sh`.
- Только OpenCode regression tests в `tests/test_vps1_housekeeping.py`.
## Изменённые файлы
- `scripts/vps1-housekeeping.sh`.
- `tests/test_vps1_housekeeping.py`.
- `docs/works/2026-09-22-opencode-maintenance-guard.md`.
## Что изменено
- `PRAGMA wal_checkpoint(TRUNCATE)` и `VACUUM` выполняются только в режиме `--apply`, если в этом запуске успешно удалена хотя бы одна session.
- При нуле удалённых sessions выводится явный `KEEP`, SQL maintenance не запускается.
- Retention thresholds и остальные секции housekeeping не изменены.
- Добавлен regression test для DB больше 768 MiB, нуля кандидатов и достаточного свободного места.
## Тесты
- `python3 -m pytest -q tests/test_vps1_housekeeping.py`: 13 passed.
- `bash -n scripts/vps1-housekeeping.sh`: успешно.
- `git diff --check`: успешно.
## Известные ограничения
- Реальный `--apply` не выполнялся.
- User timer остаётся приостановленным до отдельного подтверждения.
## Commit
- Реализация и тест: `7b2711c7`.
