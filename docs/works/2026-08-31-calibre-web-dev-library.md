# Наполненная DEV-библиотека Calibre-Web
## Цель
Подключить Calibre-Web DEV на `127.0.0.1:8084` к реалистичным metadata AU-Books через отдельный консистентный snapshot, не предоставляя DEV доступ к исходной `metadata.db` как к рабочей базе.
## Исследованная инфраструктура VPS1
- Актуальная исходная Calibre metadata находится в `/home/feninf/aubooks/library/metadata.db`.
- Существующий `/home/feninf/bin/export-metadata-sync.sh` ежедневно создаёт `/home/feninf/aubooks/sync-export/metadata.db` командой SQLite `.backup`, проверяет количество книг и отдельно синхронизирует export. Cron запускает его в `04:00`.
- Source и daily export прошли `PRAGMA integrity_check` и содержат одинаковые 122463 книги, 63224 автора, 26233 серии, 114241 описания и library UUID `97255d4e-977a-416e-bd30-7c3cea837b92`.
- Calibre-Web соединяет `books.path` с library root, `data.name` и `data.format` для файлов книг; обложка ожидается как `<library>/<books.path>/cover.jpg`.
- Локальная source library на VPS1 содержит metadata, directory skeleton и только небольшой частичный набор обложек; файлов книг FB2/EPUB/MOBI в ней нет. Новый remote layout `calibre-books-v2/<shard>/<id>` напрямую несовместим со стандартным path resolver Calibre-Web.
- Metadata-only достаточно для catalog, authors, series, descriptions, search, pagination и detail. Для реальных cover/download/reader сценариев позже понадобится отдельный небольшой DEV subset в Calibre-compatible paths.
## Архитектура
```text
/home/feninf/aubooks/library/metadata.db (VPS1 source, read-only input)
    -> sqlite3 .backup
/home/feninf/calibre-web-dev-data/library/metadata.db (DEV snapshot, mode 0444)
    -> Calibre-Web DEV 127.0.0.1:8084
```
- DEV не использует source или daily export in place. Export нельзя подключать напрямую, потому что ежедневный script удаляет и пересоздаёт его.
- Точный рабочий путь DEV: `/home/feninf/calibre-web-dev-data/library/metadata.db`.
- Физические книги, directory tree и обложки не копировались. Отсутствующие обложки обслуживаются штатным generic cover.
- Перед переключением создан консистентный backup DEV app DB: `/home/feninf/calibre-web-dev-data/app-before-library-20260831T170752Z.db`.
## Реализация
- `scripts/update-dev-library-snapshot.sh` создаёт snapshot только через `sqlite3 -readonly ... .backup`, блокирует уже открытый DEV directory через `flock` без lockfile, использует приватный `mktemp`, full `integrity_check` готовой копии и atomic rename.
- Script запрещает symlink/hardlink source-destination, sidecar WAL/journal files, одинаковые source/destination и пустой snapshot; готовый snapshot получает mode `0444`.
- `scripts/verify-dev-library-isolation.sh` использует hardcoded DEV/source paths и проверяет отдельную DEV `app.db`, canonical path/inode/link count, read-only snapshot, `quick_check`, count/UUID и отключённые split storage, Google Drive, upload, metadata backup и cover generators.
- `scripts/run-calibre-web-dev-isolated.sh` запускается через unprivileged user/mount/PID namespace: source library и daily export скрыты пустым read-only bind mount, а DEV library смонтирована read-only.
- User unit `/home/feninf/.config/systemd/user/calibre-web-dev.service` запускает verifier через `ExecStartPre`, затем namespace launcher через `unshare --user --map-root-user --mount --pid --mount-proc`; при небезопасной конфигурации или mount setup DEV не стартует.
- Перед запуском Python `setpriv` очищает inherited, permitted, effective, bounding и ambient capabilities итогового процесса и включает `no_new_privs`, поэтому процесс не может снять защитные bind mounts. Private PID namespace не показывает host processes через `/proc`.
- DEV продолжает использовать отдельные `/home/feninf/calibre-web-dev-data/app.db`, `gdrive.db`, `cache/` и `calibre-web-dev.log`; bind остался `127.0.0.1:8084`.
- Внешний от Git пустой mask directory: `/home/feninf/calibre-web-dev-data/empty-source`, mode `0555`.
- Автоматический cron/systemd timer обновления snapshot не добавлялся.
## Обновление snapshot
```bash
cd /home/feninf/calibre-web
scripts/update-dev-library-snapshot.sh
systemctl --user restart calibre-web-dev.service
```
Restart обязателен, чтобы открытые SQLite connections перешли на новый inode. `ExecStartPre` автоматически повторит isolation check. Для ручной отдельной проверки используется `scripts/verify-dev-library-isolation.sh`.
## Проверки SQLite и изоляции
- Source и итоговый DEV snapshot: `PRAGMA integrity_check` — `ok`.
- Source и DEV snapshot совпадают по books `122463`, authors `63224`, series `26233`, comments `114241` и library UUID.
- DEV `app.db`: integrity `ok`, `config_calibre_dir=/home/feninf/calibre-web-dev-data/library`, UUID совпадает со snapshot, Google Drive и split storage отключены.
- DEV snapshot имеет mode `0444`; исходная database сохранила прежние size `436988928` и mtime `2026-08-27 17:59:56 UTC` после всех snapshot runs.
- Повторный update выполнен успешно, что подтверждает идемпотентность.
- Negative test с destination, равным source, корректно остановлен до lock/backup с сообщением `Refusing to replace the source database with itself`.
- Mount namespace содержит read-only masks для `/home/feninf/aubooks/library` и `/home/feninf/aubooks/sync-export`, а `/home/feninf/calibre-web-dev-data/library` виден процессу read-only; host process UID остаётся `feninf` (`1000`).
- Python имеет namespace PID `1`, все capability sets равны нулю, `NoNewPrivs=1`; отдельный `/proc` смонтирован внутри namespace.
- Runtime POST-попытки переключить `/admin/dbconfig` на source path и обойти mask через `/proc/1/root/...` отклонены как invalid; `config_calibre_dir` остался DEV-путём.
- `ExecStartPre` завершился `0/SUCCESS`; service active/running и читает только настроенный DEV snapshot.
## HTTP runtime
- Главная `/` — HTTP 200, 60 catalog entries плюс 4 random entries, доступна pagination на 2042 страницы.
- `/page/2` и `/page/3` — HTTP 200, текущие страницы корректно определяются как 2 и 3.
- Search `Новая Тьма` — HTTP 200 после штатного redirect, найдены реальные результаты.
- `/author`, `/author/stored/1`, `/series`, `/series/stored/1` под DEV admin session — HTTP 200 и содержат ожидаемые реальные author/series records.
- `/book/1` — HTTP 200; отображаются реальное название, автор, серия и description длиной около 750 символов.
- `/cover/1` — HTTP 200 `image/jpeg`; при отсутствии физической обложки возвращён generic cover.
- Во всех проверенных responses отсутствуют `Internal Server Error`, `TemplateNotFound` и template/runtime errors; journal после restart не содержит warning/error.
## Изменённые файлы
- `scripts/update-dev-library-snapshot.sh` — безопасное ручное обновление DEV snapshot.
- `scripts/verify-dev-library-isolation.sh` — fail-closed проверка DEV library перед стартом.
- `scripts/run-calibre-web-dev-isolated.sh` — filesystem isolation source и DEV snapshot во время работы service.
- `docs/works/2026-08-31-calibre-web-dev-library.md` — этот отчёт.
- Вне Git изменён DEV user unit: добавлены `ExecStartPre` verifier и изолированный `ExecStart` через `unshare`; созданы DEV snapshot и backup app DB. Database, books, cache и runtime-файлы в Git не добавлялись.
## Ограничения
- Download/readers и реальные covers не работают без физических файлов; для текущего metadata/UI/accessibility тестирования они не требуются.
- Source library остаётся доступна пользователю `feninf` для существующей инфраструктуры, но скрыта от mount namespace DEV; snapshot создаётся отдельным manual script через read-only source connection.
- Production VPS2 не открывался и не изменялся; remote sync не запускался; push не выполнялся.
## Commit
Scripts и отчёт будут зафиксированы отдельным commit; итоговый hash будет указан в результате задачи, поскольку commit не может содержать собственный hash.
