# Согласованные snapshots и fail-closed rollback баз данных
## Цель
Исключить повреждение или потерю изменений в production SQLite-базах при deploy, startup migration, неуспешном health check и прерывании процесса сигналом.
## Что изучено
- Порядок preflight, stop, backup, смены темы, переключения symlink, start и rollback в `deploy/vps2/deploy-calibre-web-release.sh`.
- Startup-инициализация `app.db` через `Base.metadata.create_all`, `migrate_Database` и `clean_database` в `cps/ub.py`.
- Условная и runtime-запись `gdrive.db` в `cps/gdriveutils.py`.
- Подключение и runtime-изменение Calibre `metadata.db` через `cps/db.py`, административные операции и фоновые задачи.
- Поведение systemd `ActiveState`, `MainPID`, `ControlGroup`, runtime mask и SQLite WAL/SHM/journal sidecars.
- Существующие герметичные deploy/security tests и fake-команды systemd, сети, пользователя и прав файлов.
## Изменённые файлы
- `deploy/vps2/deploy-calibre-web-release.sh`.
- `tests/test_calibre_web_deploy_helper.py`.
- `docs/works/2026-09-13-consistent-deploy-database-rollback.md`.
## Что изменено
- Candidate release полностью создаётся и проверяется до остановки production-сервиса.
- Перед stop helper устанавливает принадлежащий deploy runtime mask и не снимает заранее существующий operator mask.
- Остановка считается подтверждённой только при `ActiveState=inactive|failed`, `MainPID=0` и отсутствии процессов во всём unit cgroup, включая дочерние cgroups.
- Ненулевой код `systemctl stop` допускается только при фактически подтверждённой остановке; нулевой код при живом процессе блокирует любые операции с DB и symlink.
- После подтверждённого stop повторно проверяются пути и целостность всех трёх SQLite-баз.
- Финальные rollback snapshots `app.db`, `gdrive.db` и `metadata.db` создаются SQLite backup API только в остановленном и защищённом от активации состоянии.
- Для каждой базы сохраняются числовые UID/GID и mode; snapshots проверяются через `PRAGMA integrity_check`.
- Любой candidate start считается потенциально изменяющим DB, даже если `config_theme` уже равен `3`.
- Rollback повторно устанавливает runtime mask, подтверждает stop и только затем восстанавливает previous symlink и все три базы.
- Базы восстанавливаются через проверенный временный SQLite-файл; удаление `-wal`, `-shm` и `-journal` обязательно и проверяется до атомарной замены.
- Ошибка stop, fencing, symlink restore, DB restore, metadata restore или sidecar cleanup блокирует restart и требует ручного восстановления.
- Если восстановленный релиз не запускается или не проходит health check, helper снова блокирует активацию и подтверждает его остановку.
- `ERR`, `TERM`, `INT` и `HUP` используют единый нерекурсивный rollback path; для сигналов сохраняется ожидаемый exit status.
- Dry-run описание обновлено в соответствии с новым порядком и scope snapshots.
- Герметичные tests моделируют реальное состояние unit, cgroup workers, startup-запись во все DB, WAL, stop anomalies, runtime mask, sidecar/symlink failures и сигналы в критических окнах.
## Проверки
- `bash -n deploy/vps2/deploy-calibre-web-release.sh`.
- `python3 -m pytest tests/test_calibre_web_deploy_helper.py -q`: 92 passed.
- `git diff --check`.
- Повторный read-only review state machine после исправлений.
## Известные ограничения
- Production и VPS2 не изменялись; реальный deploy и restart не выполнялись.
- Snapshot `metadata.db` увеличивает необходимое место и длительность остановки, но нужен для полного rollback после доступного пользователям candidate startup.
- Три базы восстанавливаются последовательно, а не одной файловой транзакцией; при частичном отказе сервис остаётся заблокированным и остановленным для ручного восстановления.
- Проверка процессов рассчитана на доступный root-пользователю cgroup v2 filesystem в `/sys/fs/cgroup`; тесты используют отдельный герметичный cgroup root.
- В тестах systemd, сеть, смена пользователя и privileged `chown` заменены test doubles; SQLite backup, WAL и restore выполняются реально.
## Commit
Commit реализации: `908962ae4921ee1b6775316f973a44b4f04a1e69` (`fix: make deploy database rollback fail closed`).
