# Eager loading карточек главной AU-Books
## Цель
Устранить N+1 SQL-запросы relationships при рендеринге 60 карточек GET `/` без изменения отображаемых данных и шаблона.
## Что изучено
- Запрос главной в `render_books_list()` и `CalibreDB.fill_indexpage()`.
- Обращения карточки к `Books.authors`, `Books.series`, `Books.ratings` и `Books.data`.
- SQLAlchemy statements второго прогретого GET `/` через событие `before_cursor_execute` на копии DEV settings DB и той же read-only library DB.
## Изменённые файлы
- `cps/db.py`.
- `cps/web.py`.
- `tests/test_aubooks_home_eager_loading.py`.
- `docs/works/2026-09-14-aubooks-home-eager-loading.md`.
## Что изменено
- В `fill_indexpage()` добавлен opt-in параметр `load_card_relations`.
- При включённом параметре основной запрос использует `selectinload` для authors, series, ratings и data.
- Режим включается только для существующего `text_catalog=True`, используемого главной AU-Books.
- Шаблон карточки, внешний вид и набор данных не изменены.
## Результат
- До изменения: 254 SQL-запроса, включая по 60 lazy-запросов authors, series, ratings и data.
- После изменения: 18 SQL-запросов; четыре bulk-запроса заменили 240 lazy-запросов.
- Медиана пяти прогретых DEV-запросов до изменения: 1.154 с.
- Медиана пяти прогретых DEV-запросов после изменения: 0.958 с.
- Главная возвращает HTTP 200 и содержит 60 карточек, author/series metadata и genre sidebar.
## Тесты
- `.venv/bin/python -m pytest -q tests/test_aubooks_home_eager_loading.py tests/test_aubooks_sidebar_cache.py tests/test_aubooks_theme_templates.py tests/test_aubooks_genres.py`: 149 passed, 245 subtests passed.
- `.venv/bin/python -m py_compile cps/db.py cps/web.py tests/test_aubooks_home_eager_loading.py`: успешно.
## Известные ограничения
- Оставшиеся 18 SQL-запросов и другие endpoint не оптимизировались в рамках задачи.
- Cold request после рестарта включает заполнение genre sidebar cache и не использовался для сравнения.
## Commit
Текущий commit, включающий этот отчёт.
