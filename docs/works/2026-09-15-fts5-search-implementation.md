# Реализация FTS5-поиска AU-Books
## Цель
Подключить versioned AU-Books FTS5 artifact к простому поиску Calibre-Web без изменения canonical Calibre `metadata.db`, без загрузки всех FTS rowid в Python и с безопасным fallback для обычных библиотек.
## Что изучено
- Существующий `CalibreDB.search_query()` и attachment `metadata.db` под schema `calibre`.
- Upstream consumer hook `books_fts`, его ошибочный probe через `main.sqlite_master` и fallback через `LIKE '%term%'`.
- Текущая server-side pagination в `get_search_results()`.
- Поведение phrase MATCH для Unicode/кириллицы, пустого результата и ошибки FTS.
## Изменённые файлы
- `cps/db.py`
- `tests/test_books_fts.py`
- `docs/works/2026-09-15-aubooks-search-performance-todo.md`
## Что изменено
- Добавлен явный schema contract `aubooks_fts_schema` версии 1 и probe в attached schema `calibre`.
- FTS filter выполняется SQL-подзапросом по `books.id`; `.fetchall()` и Python-список всех rowid удалены.
- Нулевой валидный FTS result считается окончательным и больше не запускает медленный legacy fallback.
- Fallback сохранён только для отсутствующего/неподдерживаемого artifact и ожидаемой SQLite/SQLAlchemy operational error.
- Query нормализуется через NFC, whitespace collapse, lower case и безопасную FTS phrase quoting.
- Кеш доступности FTS сбрасывается при `reconnect_db()`.
## Проверки
- `.venv/bin/python -m pytest tests/test_books_fts.py -q`: 8 passed.
- HTTP на обычной DEV `metadata.db` без FTS после restart: 200, legacy fallback сохранился.
- Изолированный HTTP test с реальным FTS candidate: все 5 representative queries вернули 200; median 0.058197 s против прежних 9.965398 s, приблизительно 171x быстрее.
- Полный `.venv/bin/python -m pytest tests -q`: 602 passed, 44 failed. Все 44 сбоя находятся вне FTS-кода: deploy helper, invite routes и TTS shell extraction; FTS tests проходят.
- `git diff --check`: ошибок нет.
## Известные ограничения
- Production VPS2 не изменялась и продолжает использовать legacy search.
- Phrase/token FTS не эквивалентен произвольному substring по середине слова.
- Существующий pagination path запрашивает `offset + page_size + 1` строк и затем делает slice в Python; множество совпадений ограничивается SQL до этого этапа, но pagination отдельно не переписывалась.
- Рабочая DEV `metadata.db` не изменялась; FTS проверялся на отдельном candidate.
## Commit
`bf01965d` — `feat(aubooks): use versioned FTS5 search`.
