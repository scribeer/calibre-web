# 2026-09-15 — Диагностика медленного поиска в AU-Books

## Цель

Найти root cause медленного поиска на AU-Books DEV, не внося оптимизаций.

## Добавленные TODO

- `docs/works/2026-09-15-aubooks-epub-tts-todo.md` — EPUB TTS (функциональный bug, высокий приоритет).
- `docs/works/2026-09-15-aubooks-search-performance-todo.md` — производительность поиска (performance bug, высокий приоритет).

## Маршруты и обработчики поиска

SEARCH_ROUTE: `/search` → redirect → `/search/stored?query=<term>`
SEARCH_HANDLER: `cps/web.py:books_list` → `render_books_list` → `render_search_results` → `calibre_db.get_search_results`

Файлы:
- `cps/search.py` — Blueprint search, `simple_search()`, `advanced_search()`, `render_search_results()`, `render_adv_search_results()`
- `cps/web.py` — `books_list()`, `render_books_list()`
- `cps/db.py` — `search_query()`, `get_search_results()`

Шаблоны:
- `cps/themes/aubooks/templates/search.html`
- `cps/themes/standard/templates/search.html`
- `cps/themes/standard/templates/search_form.html`

## Размер библиотеки

BOOK_COUNT: 122463
AUTHOR_COUNT: 63225
SERIES_COUNT: 26233
TAG_COUNT: 1316

## Проверки DEV

| Query | STATUS | TIME_TOTAL | RESULT_COUNT | RESPONSE_SIZE |
|---|---|---|---|---|
| `Маракх. Испытание` (точное название) | 200 | 11.60s | 1 | 123462 |
| `Маракх` (часть названия) | 200 | 9.97s | 1 | 123326 |
| `Олег Куява` (автор) | 200 | 9.88s | 1 | 123307 |
| `контрастов` (редкое слово) | 200 | 10.90s | 6 | 132677 |
| `xyznonexistent123` (без результатов) | 200 | 6.83s | 0 | 121525 |

SLOWEST_QUERY: `Маракх. Испытание`
SLOWEST_TIME: 11.60s

## Разделение времени

Получено через временное логирование в `cps/db.py` и `cps/search.py`:

- SQL_TIME: ~10.0s
- PYTHON_TIME: ~0.000s
- TEMPLATE_TIME: ~1.0s

**Вывод:** основной bottleneck — выполнение SQL-запроса. Python-обработка и рендеринг шаблона незначительны.

## SQL поиска

Основной запрос (для `query=Маракх`, page 1):

```sql
SELECT books.id, books.title, books.sort, books.author_sort, books.timestamp,
       books.pubdate, books.series_index, books.last_modified, books.path,
       books.has_cover, books.uuid, archived_book.is_archived, book_read_link.read_status
FROM books
LEFT OUTER JOIN book_read_link ON book_read_link.user_id = 2 AND book_read_link.book_id = books.id
LEFT OUTER JOIN archived_book ON books.id = archived_book.book_id AND archived_book.user_id = 2
LEFT OUTER JOIN books_series_link ON books.id = books_series_link.book
LEFT OUTER JOIN series ON series.id = books_series_link.series
WHERE true AND (
  books.id IN (SELECT books_tags_link.book FROM books_tags_link JOIN tags ON books_tags_link.tag = tags.id WHERE lower(lower(tags.name)) LIKE lower('%маракх%'))
  OR books.id IN (SELECT books_series_link.book FROM books_series_link JOIN series ON books_series_link.series = series.id WHERE lower(lower(series.name)) LIKE lower('%маракх%'))
  OR books.id IN (SELECT books_authors_link.book FROM books_authors_link JOIN authors ON books_authors_link.author = authors.id WHERE lower(lower(authors.name)) LIKE lower('%маракх%'))
  OR books.id IN (SELECT books_publishers_link.book FROM books_publishers_link JOIN publishers ON books_publishers_link.publisher = publishers.id WHERE lower(lower(publishers.name)) LIKE lower('%маракх%'))
  OR lower(lower(books.title)) LIKE lower('%маракх%')
)
ORDER BY books.timestamp DESC
LIMIT 61
```

Характеристики:
- LIKE / ILIKE: используется `lower(lower(...)) LIKE lower('%term%')`
- Все LIKE-условия с ведущим wildcard `%`
- JOIN: LEFT OUTER JOIN с books_series_link и series
- Подзапросы IN для tags, series, authors, publishers
- OR между всеми условиями
- ORDER BY books.timestamp DESC
- LIMIT 61 (books_per_page=60 + 1)
- Отсутствует OFFSET для первой страницы

## Pagination

SEARCH_PAGINATED: YES
PAGE_SIZE: 60 (config_books_per_page)
SQL_LIMIT: 61 (LIMIT+1 pattern для оценки наличия следующей страницы)
SQL_OFFSET: 0 на первой странице

Backend загружает `offset + limit + 1` строк. Для первой страницы — 61 строка. Это не загрузка всех совпадений, но SQL-запрос всё равно должен просканировать большую часть таблицы из-за ведущего wildcard.

## EXPLAIN QUERY PLAN

```
(6, 0, 0, 'SCAN books')
(11, 0, 0, 'LIST SUBQUERY 1')
(14, 11, 0, 'SCAN books_tags_link')
(16, 11, 0, 'SEARCH tags USING INTEGER PRIMARY KEY (rowid=?)')
(35, 0, 0, 'LIST SUBQUERY 2')
(38, 35, 0, 'SCAN books_series_link')
(40, 35, 0, 'SEARCH series USING INTEGER PRIMARY KEY (rowid=?)')
(59, 0, 0, 'LIST SUBQUERY 3')
(62, 59, 0, 'SCAN books_authors_link')
(64, 59, 0, 'SEARCH authors USING INTEGER PRIMARY KEY (rowid=?)')
(83, 0, 0, 'LIST SUBQUERY 4')
(86, 83, 0, 'SCAN books_publishers_link')
(88, 83, 0, 'SEARCH publishers USING INTEGER PRIMARY KEY (rowid=?)')
(108, 0, 0, 'SEARCH books_series_link USING INDEX sqlite_autoindex_books_series_link_1 (book=?)')
(129, 0, 0, 'USE TEMP B-TREE FOR ORDER BY')
```

INDEXES_USED:
- `sqlite_autoindex_books_series_link_1` для внешнего JOIN
- PRIMARY KEY lookups в tags/series/authors/publishers внутри подзапросов

FULL_TABLE_SCAN:
- `SCAN books` — полный перебор 122463 книг
- `SCAN books_tags_link`, `SCAN books_series_link`, `SCAN books_authors_link`, `SCAN books_publishers_link` — сканирование link-таблиц в подзапросах

TEMP_BTREE: YES — `USE TEMP B-TREE FOR ORDER BY`

## Indexes в metadata.db

books:
- `books_idx` на `sort`
- `authors_idx` на `author_sort`

authors:
- `sqlite_autoindex_authors_1` (UNIQUE, likely id)
- `authors_idx` на `author_sort`

tags:
- `tags_idx` на `name`
- `sqlite_autoindex_tags_1` (UNIQUE)

series:
- `series_idx` на `name`
- `sqlite_autoindex_series_1` (UNIQUE)

publishers:
- `publishers_idx` на `name`
- `sqlite_autoindex_publishers_1` (UNIQUE)

Link-таблицы имеют индексы по book и по связанному id.

Проблема: индексы по `name`/`sort` не используются, потому что условия `LIKE '%term%'` имеют ведущий wildcard.

## N+1 и eager loading

N_PLUS_ONE: NO
- `search_query()` использует `selectinload(Books.authors)`
- `render_search_results()` передаёт `load_comments=True`, что добавляет `selectinload(Books.comments)`
- SQLAlchemy выполняет 1 основной запрос + 2 дополнительных запроса (authors, comments) вместо N+1

Время Python-обработки ~0.000s, поэтому N+1 не является bottleneck.

## Сравнение с upstream

Код `search_query()` и `get_search_results()` в `cps/db.py` идентичен upstream `janeczku/calibre-web` master.

AU-Books изменения в поиске:
- `common_filters()` принимает параметр `user`
- `get_search_results()` принимает `load_comments`
- `render_search_results()` передаёт `load_comments=True`
- `render_adv_search_results()` добавляет `selectinload(Books.comments)`

Эти изменения направлены на устранение N+1 и не влияют на производительность основного SQL.

SLOWNESS_SOURCE: BOTH
- Upstream behavior: медленный алгоритм поиска с `LIKE '%term%'`
- AU-Books behavior: большая библиотека (122k книг) делает upstream-алгоритм катастрофически медленным

## Root cause

1. FTS5 таблица `books_fts` отсутствует в metadata.db, поэтому код всегда использует fallback-поиск.
2. Fallback-поиск использует `LIKE '%term%'` по title, authors, tags, series, publishers.
3. Ведущий wildcard `%` не позволяет SQLite использовать B-tree indexes.
4. SQLite выполняет `SCAN books` по всей таблице (122k строк) и запускает коррелированные подзапросы для каждой строки.
5. Дополнительно создаётся TEMP B-TREE для ORDER BY.

## Рекомендуемое исправление

Минимальное решение: создать и поддерживать FTS5-таблицу `books_fts`, которая уже предусмотрена кодом Calibre-Web.

План:
1. Создать виртуальную таблицу `books_fts` в metadata.db с колонками, которые покрывают title, author_sort, tags, series, publishers.
2. Заполнить её существующими данными.
3. Обновлять при добавлении/изменении книг.
4. Убедиться, что `search_query()` использует FTS5 fallback.

Альтернативы (если FTS5 недоступен):
- Создать отдельные lookup-таблицы с токенами для поиска.
- Переписать поиск на UNION отдельных запросов по каждой сущности.

## Связанные файлы

- `cps/db.py` — `search_query()`, `get_search_results()`
- `cps/search.py` — `render_search_results()`, `render_adv_search_results()`
- `cps/web.py` — `books_list()`, `render_books_list()`
- `cps/themes/aubooks/templates/search.html`
- `cps/themes/standard/templates/search.html`

## Production

Production VPS2 не затронут. Никаких изменений в metadata.db не внесено.
