# 2026-09-02: AU Books Sidebar Genre Tree (21 categories)

## Цель

Сделать 21 маппинг-категорию из `aubooks_genres.py` видимой в AU sidebar на **всех страницах**, включая anonymous users. До этого меню показывалось только на `/category` для авторизованных пользователей с разрешённым Guest visibility, а на detail-страницах у активного leaf не было `aria-current`.

## Что было изучено

- `render_template.py` — `render_title_template` вызывается глобально и прокидывает `sidebar` list; `/category` index проверяет `g.allow_anonymous` и закрыт для Guest.
- Anonymous routing: `/category` → 404 для Guest, но `/category/stored/<tag_id>` → 200.
- Для detail-страницы (`/book/<id>`) context передаёт `aubooks_genre_groups` (похожие жанры), но sidebar получает только `sidebar` + `page`.
- `jinja2/filters.py:518` — macro `navigation` получает `active_genre_id` и `active_book_id`.

## Изменения

### Backend

| Файл | Что |
|---|---|
| `cps/aubooks_genres.py` | `MAPPED_TAG_NAMES` — tuple имён mapped tags. `build_sidebar_genre_tree(tags)` — строит все 21 группы из реальных тегов без counts/unknowns. |
| `cps/render_template.py` | `_get_aubooks_sidebar_genre_tree()` — eager bulk query через `g` cache, один запрос по `MAPPED_TAG_NAMES`. Автоматически прокидывает `aubooks_sidebar_genre_tree`, `aubooks_sidebar_active_genre_id`, `aubooks_sidebar_open_categories`, `aubooks_sidebar_related_genre_ids` для aubooks theme. |
| `cps/web.py` | `/category` — `entries` переконвертирован в `real_tag_entries` list перед `build_genre_tree`/`build_sidebar_genre_tree`, иначе generators exhausted. |

### Frontend

| Файл | Что |
|---|---|
| `cps/themes/aubooks/templates/layout.html` | Позиция原来的 `#nav_cat` заменена на native `<details>/<summary>` меню: 21 секция, active leaf с `aria-current="page"`, auto-open для active и related. Ссылка «Все категории» видна только если `check_visibility('cat')`. |
| `cps/static/css/aubooks.css` | `.aubooks-sidebar-genres` — жёсткие paddings `summary`/`a`, overflow `60vh` на mobile, `active-context` для жирного summary, `active`/`related` border-left 3px, `summary:focus-visible` в общий focus ring. |

### Tests

| Файл | Что |
|---|---|
| `tests/test_aubooks_genres.py` | 28 tests (setUp | all existing | `test_sidebar_tree_has_all_categories_and_only_real_mapped_tags` — 21 groups, sorted within, real-only). |

## Тесты

- `python -m unittest tests.test_seo_urls tests.test_seo_db tests.test_aubooks_genres` → OK (28 tests)
- `python -m compileall -q` → OK
- `python -c "from jinja2 import Environment; ..."` → 10 templates parsed
- `git diff --check` → OK

## HTTP/DOM Smoke

- Anonymous home: 21 `<details>` sections, 357 real mapped leaves, no broken `/category` index link.
- 10 random anonymous leaf links → all 200.
- `/category/stored/2469` (Боевая фантастика): one `aria-current="page"`, parent `details[open]` with `active-context`.
- `/book/35395` (Проклятый путь): 1 mapped category section open, 1 related leaf, no false `aria-current`.

## Известные ограничения

- На anonymous detail-книгах related genres показываются для mapped categories; если book принадлежит unmapped category — эта секция в sidebar не отобразится (по design).
- `build_sidebar_genre_tree` загружает все mapped tags из БД; при большом числе уникальных mapped tags время может вырасти (сейчас ~357 unique mapped tags — fast).
