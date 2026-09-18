# Жанры в карточках книг и русская локаль

## Цель
Отобразить жанры в общем макете карточки книг на всех страницах со списками,
а также убедиться, что новые пользователи получают русскую локаль по умолчанию.

## Что было сделано

### Жанры в карточках
- Добавлен блок `<p class="genre">` в `_book_card.html` между серией и рейтингом.
- Жанры выводятся через запятую, каждый — ссылка на страницу жанра.
- Строка полностью скрыта, если у книги нет тегов (tags).
- CSS `.aubooks-catalog-book .genre` добавлен в общую группу селекторов.

### Предотвращение N+1
- `selectinload(Books.tags)` добавлен в `fill_indexpage_with_archived_books`
  (`db.py` ~line 911) — домашняя, автор, серия, жанр, издатель.
- `selectinload(Books.tags)` добавлен в базовый запрос `get_search_results`
  (`db.py` ~line 1046).
- `selectinload(db.Books.tags)` добавлен в продвинутый поиск (`search.py` ~line 368).

### Русская локаль
- `_register_user()` в `web.py:1577` устанавливает `content.locale = "ru"`
  для каждого нового пользователя безусловно.
- Существующие пользователи не затронуты.
- Смена локали доступна через `/me`.

## Изменённые файлы
- `cps/themes/aubooks/templates/_book_card.html` — жанры в карточке
- `cps/static/css/aubooks.css` — стили жанров
- `cps/db.py` — selectinload для tags
- `cps/search.py` — selectinload для tags в продвинутом поиске
- `tests/test_aubooks_book_card_genres.py` — новые тесты (8)
- `tests/test_aubooks_home_eager_loading.py` — тесты eager loading
- `tests/test_invite_registration.py` — тесты сохранения локали

## Тесты
- `test_aubooks_book_card_genres`: 16 passed (8 тестов с subtests)
- `test_aubooks_home_eager_loading`: включая проверку selectinload для tags
- `test_invite_registration`: 28 passed (включая 2 новых теста локали)
- Всего AU-Books suite: 396 passed, 261 subtests

## Деплой
- Коммит `7ca93428bdf1d84587c797402de25efa8d0e733a` в ветке `aubooks`.
- Push в origin.
- Деплой на VPS2: `deployed-manifest.json` подтверждает SHA, сервис `active`.

## Production acceptance
- Домашняя: строки `<p class="genre">` присутствуют, ссылки ведут на `/genre/<slug>`.
- Автор: жанры отображаются.
- Серия: жанры отображаются.
- Жанровая страница: 60 строк жанров.
- Детали книги: жанры в сайдбаре, SEO redirect работает.
- Нет URL `/genre/stored/` — все ссылки канонические.
- FTS5: таблицы `books_fts` присутствуют.
- Сервис: `active`, без traceback в journal.

## Известные ограничения
- Прямой POST на `/register/<token>` возвращает "unknown error" —
  предположительно проблема с конфигурацией registration domain в production DB,
  не связана с данными изменениями. Локаль новой регистрации подтверждена юнит-тестами.
- Поиск (`/search/?query=...`) возвращает 404 на прямой GET —
  предсуществующая проблема (nginx routing), не связана с данными изменениями.

## Commit
`7ca93428bdf1d84587c797402de25efa8d0e733a` — Add genre row to book cards; eager-load tags to prevent N+1
