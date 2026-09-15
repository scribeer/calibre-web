# 2026-09-15 — Server-side алфавитный фильтр для /author

## Цель

Исправить алфавитный индекс каталога авторов `/author` после введения пагинации: фильтр по первой букве должен работать на стороне сервера и применяться ко всему каталогу, а не к текущей странице из 100 авторов.

## Изучено

- Алфавитный индекс `charlist` строится от `query_char_list()` по первому символу `Authors.sort` в верхнем регистре.
- `filter_list.js` выполнял фильтрацию текущей страницы клиентски, что некорректно при пагинации.
- Для корректной работы необходим query param `char` и SQL-фильтр до применения `LIMIT/OFFSET`.

## Изменённые файлы

- `cps/web.py`
- `cps/themes/aubooks/templates/list.html`
- `cps/themes/standard/templates/list.html`
- `tests/test_aubooks_guest_sidebar.py`

## Что изменено

### `cps/web.py`

- Добавлено чтение query parameter `char`.
- Первый символ параметра приводится к верхнему регистру в Python.
- Сформирован `list_filter = and_(common_filters(), upper(substr(Authors.sort, 1, 1)) == char_param)`.
- Фильтр используется как в `COUNT(DISTINCT)`, так и в основном запросе авторов.
- Пагинация пересчитывается с учётом отфильтрованного количества.
- Параметр `char` передаётся в шаблон.

### `cps/themes/aubooks/templates/list.html`

- Для `data == 'author'` кнопки алфавита заменены на ссылки `/author?char=X`.
- Кнопка «Все» заменена на ссылку `/author`.
- Активная буква и «Все» подсвечиваются по текущему `char`.
- Пагинация сохраняет `char` в ссылках `page`.
- `filter_list.js` больше не загружается для `/author`, чтобы избежать конфликта клиентской фильтрации.

### `cps/themes/standard/templates/list.html`

- Добавлен аналогичный server-side блок для `/author` с минимальными средствами Standard theme.
- Остальные списки не затронуты.

### `tests/test_aubooks_guest_sidebar.py`

- Добавлен regression test `test_author_list_uses_server_side_char_filter`.

## Тестирование

### Ручные проверки DEV

| URL | Статус | Время | Примечание |
|---|---|---|---|
| `/author` | 200 | ~1.16s | полный каталог, 100 авторов |
| `/author?page=2` | 200 | ~1.01s | полный каталог, страница 2 |
| `/author?char=А` (Cyrillic) | 200 | ~0.79s | только авторы с sort на 'А' |
| `/author?char=А&page=2` | 200 | ~0.81s | страница 2 внутри буквы 'А' |
| `/author?char=A` (Latin) | 200 | ~0.71s | только авторы с sort на 'A'/'a' |
| `/author?char=%` | 200 | ~0.69s | пустой результат, 0 страниц, без 500 |

- Для `char=А` все 100 авторов на странице имеют `Authors.sort`, начинающийся с Cyrillic 'А' (ord 1040).
- Для `char=A` все 100 авторов имеют `Authors.sort`, начинающийся с Latin 'A' или 'a'.
- Для `char=А&page=2` пагинация показывает «Страница 2 из 31».

### Автотесты

- `tests/test_aubooks_guest_sidebar.py` — 3 passed.
- `tests/test_aubooks_theme_templates.py`, `tests/test_aubooks_home_eager_loading.py`, `tests/test_aubooks_genres.py`, `tests/test_seo_urls.py` — 162 passed, 245 subtests passed.

## Ограничения

- Кнопки сортировки asc/desc и sort_name на `/author` теперь не имеют клиентской обработки (filter_list.js отключён). Изменение направления сортировки возможно через настройки пользователя; полноценная server-side сортировка по клику — следующий возможный шаг.
- Алфавитные ссылки отображают все буквы, которые есть в каталоге, включая спецсимволы; это сохраняет существующее поведение `query_char_list`.

## Commit

`c40eafa0` — `fix(aubooks): make author alphabet filter server-side`

## GitHub

Ветка `aubooks` pushed в `origin`.

## Production

Production VPS2 не затронут.
