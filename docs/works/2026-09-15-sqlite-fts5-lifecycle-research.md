# Исследование SQLite FTS5 для AU-Books
## Цель
Исследовать существующую поддержку `books_fts` в Calibre-Web и подготовить безопасный план внедрения без изменения рабочей DEV `metadata.db` и production.
## Текущая поддержка в коде
### Файлы и функции
- `cps/db.py:986` — `CalibreDB.search_query()` проверяет наличие `books_fts`, выполняет FTS-запрос и выбирает fallback.
- `cps/db.py:1092` — `CalibreDB.get_search_results()` добавляет сортировку и pagination.
- `cps/search.py:420` — `render_search_results()` вызывает `get_search_results()` и рендерит `search.html`.
- `cps/web.py:423` — `render_books_list()` получает query и вычисляет offset.
- `cps/db.py:685` — `setup_db()` создаёт in-memory schema `main`, а `metadata.db` подключает как schema `calibre`.
### FTS query path
Код проверяет таблицу запросом:
```sql
SELECT name FROM sqlite_master
WHERE type='table' AND name='books_fts';
```
При положительной проверке выполняется:
```sql
SELECT DISTINCT rowid
FROM books_fts
WHERE books_fts MATCH :term;
```
Весь term приводится к lower case, экранируются двойные кавычки, затем term заключается в кавычки как phrase query. Полученные `rowid` используются как `books.id` через `Books.id.in_(fts_ids)`.
### Fallback path
Если таблица не обнаружена, FTS завершился ошибкой или FTS вернул ноль строк, выполняется fallback с `LIKE '%term%'` по title, author, series, tags, publisher и текстовым custom columns.
### Критическая ошибка обнаружения schema
В нормальной конфигурации Calibre-Web `main` является in-memory DB, а `metadata.db` подключена как `calibre`. Поэтому текущий запрос к неуточнённой `sqlite_master` не видит таблицу в `metadata.db`:
```text
main.sqlite_master books_fts: 0
calibre.sqlite_master books_fts: 1
```
Неуточнённый запрос `FROM books_fts` умеет разрешить таблицу из attached schema, но до него код не доходит из-за отрицательной проверки.
### Кеш доступности
Результат проверки сохраняется в `_fts_available` на экземпляре `CalibreDB` и не сбрасывается в `reconnect_db()`. После появления или замены FTS требуется сброс кеша либо restart процесса.
## Upstream
Код FTS в `upstream/master:cps/db.py` функционально идентичен fork. В upstream также отсутствуют creator, schema, migration, CLI, startup hook, admin action, background task, trigger, тесты и документация для `books_fts`.
Исторически consumer-код появился в commit `a3b5d2ea` (`Optimize search performance for large libraries`), а проверки/экранирование были добавлены в `8544702b`. Создание и обслуживание таблицы в этих изменениях отсутствует.
## Ожидаемый schema contract
Upstream не определяет точный `CREATE VIRTUAL TABLE`, columns, tokenizer, `content`, `content_rowid` или triggers. Фактический контракт consumer-кода ограничен следующим:
1. Таблица называется `books_fts`.
2. Таблица поддерживает table-level `MATCH`.
3. Таблица имеет `rowid`.
4. `books_fts.rowid` точно соответствует `books.id`.
5. Все поля, которые должны участвовать в простом поиске, должны быть indexed columns таблицы, потому что используется table-level `books_fts MATCH`.
Следовательно, утверждать наличие «официальной schema Calibre-Web» нельзя: её нет.
## Существующий Calibre FTS
Calibre создаёт FTS5 для annotations, но не для books:
```sql
CREATE VIRTUAL TABLE annotations_fts USING fts5(
    searchable_text,
    content = 'annotations',
    content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 2'
);
```
Для `annotations_fts` существуют insert/delete/update triggers. Для `books_fts` аналогичного механизма нет.
## Creator и update method
FTS_CREATOR: отсутствует.
FTS_CREATE_METHOD: отсутствует.
FTS_UPDATE_METHOD: отсутствует.
Calibre-Web и Calibre не создают и не поддерживают `books_fts`; таблица является незавершённым consumer hook.
## SQLite на VPS1
```text
sqlite_version(): 3.37.2
sqlite_compileoption_used('ENABLE_FTS5'): 1
```
В `:memory:` успешно выполнены создание FTS5-таблицы, insert и Cyrillic MATCH. Рабочая `metadata.db` не использовалась для записи.
## Metadata sync AU-Books
### Текущий pipeline
1. `/home/feninf/bin/export-metadata-sync.sh:75-81` создаёт `/home/feninf/aubooks/sync-export/metadata.db` через SQLite `.backup` исходной `/home/feninf/aubooks/library/metadata.db`.
2. `/home/feninf/bin/export-metadata-sync.sh:87-99` проверяет только book count и отправляет export через rclone в OpenDrive.
3. `/home/feninf/bin/sync-pull-metadata.sh:97-112` скачивает файл и выполняет `PRAGMA integrity_check`.
4. `/home/feninf/bin/sync-pull-metadata.sh:114-134` заменяет production `metadata.db` через same-filesystem rename и перезапускает Calibre-Web.
5. DEV snapshot создаётся отдельным `.backup` во временный файл и атомарно заменяется в `scripts/update-dev-library-snapshot.sh:54-87`.
### Влияние изменений каталога
- Добавление книги: standalone FTS без rebuild не получает новую строку, возможен false negative.
- Удаление книги: FTS сохраняет stale rowid; base books query отфильтрует удалённый id, но индекс остаётся неконсистентным.
- Изменение title: старые tokens остаются, новые отсутствуют.
- Изменение author/series/tags/publisher или link-таблиц: aggregate text становится stale.
- Полная замена `metadata.db`: FTS исчезает, если её нет в новом файле; process также может сохранить старое `_fts_available` до restart.
- Неполный FTS особенно опасен: если он вернул хотя бы один id, fallback полностью пропускается, поэтому другие корректные совпадения скрываются.
## Рекомендуемый lifecycle
Выбран один вариант: **пересоздавать `books_fts` внутри приватного export candidate после каждого metadata sync и публиковать уже готовый единый `metadata.db` artifact**.
Причины:
- не изменяет canonical Calibre DB `/home/feninf/aubooks/library/metadata.db`;
- не требует сложных triggers на books и четырёх link-таблицах;
- FTS и metadata имеют одну generation и заменяются вместе;
- существующие SQLite backup, OpenDrive transfer и atomic replacement можно расширить проверками;
- локально построенная production-only FTS была бы потеряна при следующем полном sync.
Обязательное условие: VPS2 metadata должна быть логически read-only между sync. Локальные metadata edits на VPS2 необходимо запретить либо направлять в VPS1 source, иначе FTS устареет до следующего sync.
## Atomic rebuild
ATOMIC_REBUILD_POSSIBLE: YES.
Рекомендуемый sequence:
1. SQLite `.backup` source в новый private candidate в export directory.
2. В одной transaction создать и заполнить `books_fts` в candidate.
3. Проверить `integrity_check`, library UUID, book count, FTS row coverage, schema version и representative MATCH queries.
4. Установить финальные permissions.
5. Выполнить same-filesystem `rename()` candidate в export path.
6. Публиковать immutable/versioned artifact вместе с checksum manifest.
7. На получателе проверить manifest и FTS до atomic replacement и restart.
Все проверенные директории на VPS1 находятся на device `2049`, поэтому same-filesystem atomic rename возможен.
## Proof of concept
PoC выполнялся только на копии `/tmp/aubooks-fts-poc-metadata.db`; после измерений копия удалена.
### PoC schema
Это не upstream schema, а минимальная экспериментальная schema, выведенная из fallback fields:
```sql
CREATE VIRTUAL TABLE books_fts USING fts5(
    title,
    authors,
    series,
    tags,
    publishers,
    tokenize='unicode61 remove_diacritics 2'
);
```
Таблица standalone/contentful: `content` и `content_rowid` не используются. Insert явно устанавливает `rowid = books.id`. Authors, series, tags и publishers агрегированы через `group_concat` в CTE перед insert.
### Build result
```text
Books indexed: 122463
BUILD_TIME: 2.96 s
DB_SIZE_BEFORE: 436988928 bytes (416.75 MiB)
DB_SIZE_AFTER: 471771136 bytes (449.92 MiB)
Additional size: 34782208 bytes (33.17 MiB, +7.96%)
PRAGMA integrity_check: ok
```
На приватном candidate такой build не блокирует Calibre-Web. Построение на активной DB не рекомендуется.
### FTS query measurements
Выполнен тот же consumer query `SELECT DISTINCT rowid ... MATCH :term`, по одному разу на term:
| Query | FTS time | Results | Старый HTTP search |
|---|---:|---:|---:|
| `Маракх. Испытание` | 0.010558 s | 1 | 11.603487 s |
| `Маракх` | 0.000079 s | 1 | 9.965398 s |
| `Олег Куява` | 0.006629 s | 1 | 9.877234 s |
| `контрастов` | 0.003334 s | 6 | 10.903582 s |
| `xyznonexistent123` | 0.004068 s | 0 | 6.827157 s |
```text
OLD_MEDIAN: 9.965398 s
FTS_MEDIAN: 0.004068 s
Direct SQL speedup: approximately 2450x
```
Counts совпали с предыдущей диагностикой для всех пяти запросов.
Важно: это direct FTS timing, а не текущий Calibre-Web HTTP timing. В существующем consumer zero-result запрос всё равно перейдёт в медленный fallback; `xyznonexistent123` не ускорится до исправления этой логики.
## Backup, restore и deploy
- SQLite `.backup` сохраняет virtual table, shadow tables и данные FTS.
- Полная файловая замена сохраняет consistency только если FTS построена в заменяемом artifact.
- Export должен валидировать не только book count, но и FTS schema/row count/representative queries.
- Pull должен проверять checksum manifest, UUID и FTS до замены.
- Calibre-Web должен быть остановлен/fenced до финальной замены; после replacement требуется restart для нового inode и сброса `_fts_available`.
- FTS build не должен входить в application release deploy: это часть metadata export pipeline.
- Calibre source DB не должна получать AU-Books-specific таблицу.
## Риски текущего consumer-кода
1. Проверяется неправильная `sqlite_master`; FTS в attached `metadata.db` не обнаруживается.
2. Нулевой FTS result запускает медленный fallback.
3. Все FTS rowids загружаются через `.fetchall()` до pagination; популярный term может создать большой Python list и огромный SQL `IN`.
4. Phrase FTS не эквивалентен substring `LIKE '%term%'`; поиск части слова может изменить результаты.
5. FTS schema из пяти полей не покрывает текстовые custom columns fallback.
6. Неполный или stale FTS скрывает корректные fallback matches, если найден хотя бы один FTS row.
7. `_fts_available` не сбрасывается при reconnect.
## Рекомендуемая реализация
1. Добавить versioned builder script для приватного export candidate; не модифицировать source metadata.
2. Зафиксировать собственный schema contract AU-Books: `rowid=books.id`, title, authors, series, tags, publishers и агрегированный searchable custom text; tokenizer `unicode61 remove_diacritics 2`.
3. Всегда делать полный rebuild после каждого export snapshot; triggers не использовать.
4. Исправить probe на `calibre.sqlite_master` и явно обращаться к `calibre.books_fts`.
5. Различать состояния unavailable/error и valid zero-result; authoritative zero-result не должен запускать LIKE fallback.
6. Не загружать все rowids в Python: использовать SQL subquery/join с FTS и применять pagination в SQL.
7. Определить и протестировать семантику phrase/prefix поиска до переключения пользователей.
8. Добавить consistency manifest: schema version, library UUID, book count, FTS row count, checksum и generation timestamp.
9. Расширить export/pull validation и сделать общий lock/fencing с application deploy.
10. Добавить unit/integration tests для attached schema detection, zero results, stale/missing FTS, Unicode/Cyrillic, pagination и fallback on FTS error.
## Изменённые файлы
- `docs/works/2026-09-15-sqlite-fts5-lifecycle-research.md`
## Проверки
- Поиск всех `books_fts`, FTS5 и MATCH references в fork, upstream и git history.
- Проверка текущей и upstream реализации `search_query()`/`get_search_results()`.
- Проверка schema attachment и `sqlite_master` в `:memory:`.
- `sqlite_version()` и `sqlite_compileoption_used('ENABLE_FTS5')`.
- Создание и MATCH FTS5 в `:memory:`.
- Полный PoC build и пять запросов на `/tmp`-копии DEV metadata.
- `PRAGMA integrity_check` PoC и рабочей DEV metadata.
- Проверка mode/path рабочей DEV metadata: `0444`, `books_fts` отсутствует.
## Ограничения
- Production не проверялась и не изменялась.
- Точная upstream schema отсутствует; PoC schema является предложением AU-Books.
- Полный application HTTP path с FTS не тестировался, поскольку текущий probe требует code fix, а задача запрещает реализацию.
- Оценка build получена на DEV-копии и может отличаться на VPS2.
## Commit
Будет указан после создания commit отчёта.
## Production
Production VPS2 не затронут. Рабочая DEV `metadata.db` не изменялась.
