# 2026-09-15 — Пагинация публичного каталога авторов /author

## Цель

Исправить страницу каталога авторов `/author` в AU-Books DEV:

1. Сделать `/author` доступной для anonymous browsing (Guest).
2. Заменить загрузку всех авторов на серверную пагинацию.

## Изучено

- Маршрут `/author` находится в `cps/web.py:1025`, обработчик `author_list()`, шаблон `list.html`.
- Подмаршрут `/author/stored/<id>` обрабатывается в `cps/web.py:912-915` через `books_list()`.
- Для Guest `current_user.check_visibility(constants.SIDEBAR_AUTHOR)` возвращает `False`, поэтому `/author` возвращала 404.
- В базе DEV 63225 записей в таблице `authors`; после применения `common_filters()` каталог использует 63224 автора.
- Текущий `author_list()` вызывал `.all()` и `copy.deepcopy()` для всех авторов, что делало страницу неработоспособной.

## Изменённые файлы

- `cps/web.py`
- `cps/themes/aubooks/templates/list.html`
- `cps/themes/standard/templates/list.html`
- `tests/test_aubooks_guest_sidebar.py`

## Что изменено

### `cps/web.py`

- Добавлено AU-Books-условие `is_aubooks_public = is_aubooks_active() and current_user.is_anonymous`.
- `/author` теперь доступна Guest при активной теме AU-Books и включённом anonymous browsing.
- Глобальная модель прав Calibre-Web не изменена: проверка `SIDEBAR_AUTHOR` сохранена для остальных случаев.
- Добавлена серверная пагинация: `page` query parameter, `per_page = 100`.
- Общее количество авторов получается отдельным `COUNT(DISTINCT authors.id)`.
- Запрос авторов использует `.offset(...).limit(per_page)`.
- Сортировка сохранена; добавлен вторичный ordering по `Authors.id` для стабильности.
- Некорректные номера страниц (<1 или больше максимума) приводятся к допустимому диапазону без 500.

### `cps/themes/aubooks/templates/list.html`

- Добавлен блок пагинации после списка авторов.
- Кнопки «Предыдущая» / «Следующая», текст «Страница X из Y».
- Неактивные кнопки на первой/последней странице отображаются как `<span>`, а не ссылки.
- Использованы `aria-label`, semantic HTML (`<nav>`, `<ul class="pager">`).

### `cps/themes/standard/templates/list.html`

- Добавлен минимальный аналогичный блок пагинации для обратной совместимости Standard theme.
- Другие списки (series, publisher и т.д.) не затронуты, так как блок обёрнут в `{% if pagination %}`.

### `tests/test_aubooks_guest_sidebar.py`

- Добавлен regression test `TestGuestAuthorAccess::test_author_list_allows_anonymous`.

## Тестирование

### Ручные проверки DEV

| URL | Статус | Время | Примечание |
|---|---|---|---|
| `/author` | 200 | ~1.09s | 100 авторов |
| `/author?page=2` | 200 | ~0.97s | 100 авторов |
| `/author?page=633` | 200 | ~1.21s | 24 автора (последняя страница) |
| `/author?page=999999` | 200 | — | приведено к последней странице |
| `/author?page=0` | 200 | — | приведено к странице 1 |
| `/` | 200 | — | — |
| `/login` | 200 | — | — |
| `/author/stored/<id>` | 200 | — | — |
| `/book/<id>` | 200 | — | после редиректа |

### Производительность

- 3 последовательных запроса `/author`: ~0.99s, ~1.00s, ~1.11s.
- Медиана: ~1.00s.
- Размер страницы: ~169 KB (100 авторов).
- Полный список 63224 авторов больше не загружается.

### Автотесты

- `tests/test_aubooks_guest_sidebar.py` — 2 passed.
- `tests/test_aubooks_theme_templates.py`, `tests/test_aubooks_home_eager_loading.py`, `tests/test_aubooks_genres.py`, `tests/test_seo_urls.py` — 159 passed, 245 subtests passed.
- Полный `pytest tests/` — 593 passed, 248 subtests passed, 44 failed в не связанных с изменением модулях (`test_calibre_web_deploy_helper.py`, `test_cmd_start_book_id.py`, `test_invite_admin.py`).

## Ограничения

- Алфавитный индекс (`charlist`) сохранён, но с пагинацией фильтрует только текущую страницу. Для корректной работы «перехода к букве» потребуется следующий шаг: серверная фильтрация по первой букве или отдельный URL-параметр.
- На DEV остаётся один автор с повреждённым именем (mojibake) на последней странице; это проблема данных, не кода.
- Время ответа ~1s ограничено производительностью SQL-запроса с `GROUP BY` и `OFFSET` на 122k книгах; можно ускорить индексом или materialized view, но это выходит за рамки минимального исправления.

## Commit

`431a62ec` — `fix(aubooks): paginate public author catalog`

## GitHub

Ветка `aubooks` pushed в `origin` (`https://github.com/scribeer/calibre-web.git`).

## Production

Production VPS2 не затронут.
