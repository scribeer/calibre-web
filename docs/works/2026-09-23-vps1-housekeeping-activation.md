# Активация автоматического housekeeping на VPS1
## Цель
Выполнить безопасный production cleanup по утверждённой retention-политике, активировать ежедневный user timer и проверить установленный systemd service ручным smoke test.
## Что изучено
- Точный HEAD ветки `aubooks`: `2a8ac956653312c3aec9446dd6dadfd92d1118f9`.
- Состояние `aubooks-vps1-housekeeping.timer` и `aubooks-vps1-housekeeping.service`.
- Production dry-run, apply-отчёт, итоговые размеры и housekeeping log.
## Изменённые файлы
- `docs/works/2026-09-23-vps1-housekeeping-activation.md`.
- Runtime-код, retention thresholds и systemd units не изменялись.
## Что выполнено
- Установлено, что timer уже был active/waiting и успешно запускал service в `2026-09-23 00:05 UTC`; ошибок unit/install helper не обнаружено.
- Dry-run предложил удалить только generations `0c09318bce5bad8fc9192893020e57187894a5485e5b20def2655efe00996682` и `2d3cb3b96e6b330b58051e5c216da330c78e6eda940abc3c73166eeb1da7fd60`.
- Apply удалил эти две старые generations и освободил `965151624` байта.
- Сохранены две newest generations и специальная FTS5 generation `9345aa9df713b711698884e48bb5d415c741f3f299582319f026794dcd6c9a45`.
- TTS cleanup освободил 0 байт; крупные jobs `20260921_010400_3340201` и `20260923_012721_3647763` сохранены.
- OpenCode: 25 sessions, 0 candidates, 0 deletions; checkpoint и VACUUM не выполнялись.
- `/tmp`: 0 удалений. `covers.tar.gz` сохранён без изменений.
- Выполнены `daemon-reload` и `enable --now`; timer подтверждён как loaded/enabled/active/waiting.
- Ручной запуск systemd service завершился `Result=success`, `ExecMainStatus=0`; повторный cleanup освободил 0 байт.
## Результаты
- Root filesystem: `85%`, около `4.3G` свободно до apply; `82%`, около `5.2G` после apply.
- Sync-export: `2.3G` до, `1.4G` после.
- Jobs: `2.5G` до и после.
- `/tmp`: `1.4G` до apply; итоговое измерение `1.5G` из-за параллельной активности, housekeeping ничего там не удалял.
- Следующий запуск timer: `2026-09-24 00:03:36 UTC`.
## Тесты
- Production `scripts/vps1-housekeeping.sh --dry-run`: безопасный список кандидатов.
- Production `scripts/vps1-housekeeping.sh --apply`: успешно.
- `systemctl --user start aubooks-vps1-housekeeping.service`: успешно.
- Повторный apply через unit: 0 неожиданных удалений.
## Известные ограничения
- Housekeeping намеренно не удаляет TTS jobs без однозначного durable разрешения.
- OpenCode DB не уменьшается при отсутствии session candidates.
## Commit
- Runtime baseline: `2a8ac956653312c3aec9446dd6dadfd92d1118f9`.
