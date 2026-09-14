# Оптимизация GET /category
## Цель
Найти измеренный bottleneck страницы категорий и устранить его минимально без изменения содержимого страницы.
## Что изучено
- SQL statements и длительность второго прогретого GET `/category` через SQLAlchemy events на копии DEV settings DB и той же read-only `metadata.db`.
- `category_list()`, построение AU genre trees и рендер `list.html`/layout.
- Участие COUNT/GROUP BY, genre tree, template и SEO.
## Диагностика
- До изменения выполнялось 11 SQL-запросов за 0.563 с при полном test-client request 0.862 с.
- Основной `Tags JOIN books_tags_link JOIN Books GROUP BY Tags.id` занимал 0.282 с.
- Отдельный `Books LEFT JOIN books_tags_link LEFT JOIN Tags COUNT(*)` для книг без жанра занимал 0.279 с.
- `build_genre_tree` занимал около 5.6 мс, `build_sidebar_genre_tree` 4.0 мс, `generate_char_list` 1.4 мс, render path около 153 мс.
- SEO-запросы на странице отсутствуют.
## Изменённые файлы
- `cps/web.py`.
- `docs/works/2026-09-14-category-aggregate-query.md`.
## Что изменено
- Два полных aggregate-запроса объединены в один `Books LEFT JOIN books_tags_link LEFT JOIN Tags GROUP BY Tags.id`.
- Строка с `Tags IS NULL` используется для прежнего счётчика книг без жанра; остальные строки остаются прежними genre entries.
- Сохранён прежний `ORDER BY Tags.name`, включая порядок tag IDs в compound URL.
## Результат
- После изменения выполняется 9 SQL-запросов; измеренное SQL-время 0.408 с, полный test-client request 0.674 с.
- Медиана пяти прогретых DEV-запросов снизилась с 0.710 с до 0.622 с.
- GET `/category` возвращает HTTP 200 и прежние 299688 байт.
- SHA-256 HTML до и после совпадает: `0e3c6e85dfa16818875fe7ee65e5c35970667e5aca5160a18eb3e98aaae8f843`.
## Тесты
- `.venv/bin/python -m pytest -q tests/test_aubooks_genres.py tests/test_aubooks_guest_sidebar.py tests/test_aubooks_sidebar_cache.py tests/test_aubooks_theme_templates.py`: 148 passed, 245 subtests passed.
- `.venv/bin/python -m py_compile cps/web.py`: успешно.
- DEV GET `/category`: HTTP 200; byte-for-byte comparison с baseline успешен.
## Известные ограничения
- Оставшийся основной aggregate SQL не изменялся далее, поскольку он формирует требуемые counts всех жанров.
- Другие endpoint, SEO, UI/CSS, TTS и OpenDrive не изменялись.
## Commit
Текущий commit, включающий этот отчёт.
