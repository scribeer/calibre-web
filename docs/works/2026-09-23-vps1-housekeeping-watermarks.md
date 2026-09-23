# Watermark cleanup VPS1
## Цель
Доработать существующий `scripts/vps1-housekeeping.sh`, чтобы root filesystem автоматически удерживал минимум 8 GiB свободного места, а при pressure/critical watermark очищал только доказуемо воспроизводимые и неактивные данные.
## Что изучено
- Существующий `scripts/vps1-housekeeping.sh` и его текущие retention checks.
- Существующие user service/timer и `deploy/vps1/install-housekeeping.sh`.
- Только известные крупные targets: `aubooks/jobs`, sync-export generations, разрешённые `/tmp` patterns, известные cache roots и OpenCode DB/WAL.
- Durable status для тяжёлого failed publish job через штатный `audio-index-runtime.py exact-status`.
## Изменённые файлы
- `scripts/vps1-housekeeping.sh`.
- `tests/test_vps1_housekeeping.py`.
- `docs/works/2026-09-23-vps1-housekeeping-watermarks.md`.
## Что изменено
- Добавлены watermark levels: normal при свободном месте не менее 8 GiB, pressure ниже 8 GiB, critical ниже 6 GiB.
- В pressure/critical автоматически удаляются payload `out`, `work`, source и временные markers только terminal TTS jobs с подтверждённым durable status; metadata/status job сохраняется.
- Активные jobs защищены lock, live process identity и свежим heartbeat.
- `/tmp` теперь поддерживает известные AU-Books/test/OpenCode prefixes, direct-child canonical validation, age policy и skip sockets/in-use paths.
- Добавлен cleanup disposable cache roots `pip`, HuggingFace, Torch, uv и Datalab models. В pressure удаляются неиспользуемые cache entries; в normal действует возрастная retention.
- Старые OpenCode `*.tmp` очищаются отдельно; `bin` и `models.json` не затрагиваются.
- Sync-export policy сохранена: две newest generations и FTS5 generation `9345aa9...`.
- OpenCode sessions не удалялись; при 0 удалений checkpoint/VACUUM не запускались.
## Production результат
- До cleanup: `5,710,135,296` байт свободно, pressure/critical режим.
- Первый apply удалил TTS payload на `2,808,012,327` байт.
- Последующий pressure apply удалил disposable cache/OpenCode temp на `279,428,225` байт.
- После cleanup: `8,798,228,480` байт свободно, `8.19 GiB`, root usage `71%`.
- Sync-export: `1.4G`, сохранены ровно три generations: две newest и FTS5.
- Jobs: `2.5G` до cleanup, `261M` после. Job `20260921_010400_3340201` уменьшен с `2.3G` до metadata около `400K`.
- Job `20260923_012721_3647763` около `260M` сохранён: durable exact status `mismatch`, поэтому автоматическое удаление не разрешено.
- `/tmp`: `1.1G`; разрешённых старых targets для удаления не было.
- Cache: `14M` после удаления Datalab model cache и старого OpenCode `.tmp`.
- OpenCode: 26 sessions, 0 candidates, 0 deletions, checkpoint/VACUUM не выполнялись.
- `covers.tar.gz` housekeeping script не содержит и не удалял. Пост-проверка пути вернула `No such file`; это расхождение с ранее сообщённым наличием файла, восстановление или ручное удаление не выполнялось.
## Systemd
- `install-housekeeping.sh` выполнен после изменения.
- Timer: `LoadState=loaded`, `UnitFileState=enabled`, `ActiveState=active`, `SubState=waiting`.
- Следующий запуск: `2026-09-24 00:07:06 UTC`.
- Ручной `systemctl --user start aubooks-vps1-housekeeping.service`: `Result=success`, `ExecMainStatus=0`.
- Повторный systemd запуск не удалил ничего неожиданного.
## Тесты
- `python3 -m pytest -q tests/test_vps1_housekeeping.py`: 17 passed.
- `bash -n scripts/vps1-housekeeping.sh`: успешно.
- `git diff --check`: успешно.
- CI green: [AU-Books CI #35895471205](https://github.com/scribeer/calibre-web/actions/runs/35895471205).
## Commit
- Watermark implementation: `f23dce9d`.
- Disposable cache pressure fix: `6a551ad6`.
