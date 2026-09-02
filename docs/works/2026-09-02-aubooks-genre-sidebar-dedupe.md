# 2026-09-02: AU Books Genre Sidebar Dedup & Annotations

## Цель

Исправить два регресса после добавления sidebar genre hierarchy:
1. Дубли подкатегорий в sidebar (одинаковые русские labels внутри одной категории)
2. Отсутствие аннотаций на genre/category result pages

## Что было изучено

### Дубли в sidebar

Причина: `MAPPED_TAG_NAMES = tuple(GENRES) + tuple(_LABEL_GENRES)` содержит оба типа имён:
- Flibusta codes: `det_action`, `det_irony`, ...
- Русские labels: `Боевик`, `Иронический детектив`, ...

Если в БД есть оба тега (и `det_action`, и `Боевик`), оба попадают в sidebar query.
`genre_for_tag` маппит оба на одинаковый label, но `build_sidebar_genre_tree` дедуплицировал по `tag_id`, а не по label.

Итого: 357 leaves → 96 duplicate entries → 261 уникальных после dedupe.

### Отсутствие аннотаций

`render_category_books` не передавал `load_comments=True` в `fill_indexpage` и не передавал `show_annotations=True` в `render_title_template`. Шаблон `index.html` использует `show_annotations|default(false)`, поэтому annotations не показывались.

## Изменения

### cps/aubooks_genres.py

`build_sidebar_genre_tree(tags)`:
- Дедупликация по `genre["code"]` вместо `genre["tag_id"]`
- При дубле: все tag_ids мержатся в `genre["tag_ids"]` (list)
- Каждый genre dict теперь содержит `tag_ids` (list) для compound URL

### cps/themes/aubooks/templates/layout.html

- Sidebar link: `book_id=genre.tag_ids|join('+')` вместо `book_id=genre.tag_id`
- Active state: `aubooks_sidebar_active_genre_id in genre.tag_ids`
- Related state: цикл по tag_ids с namespace для проверки пересечения

### cps/render_template.py

- `aubooks_sidebar_related_genre_ids`: расширен для включения всех `tag_ids` из каждого genre

### cps/web.py — render_category_books

- Парсинг `+`-separated tag_ids: `str(book_id).split('+')`
- Фильтрация через `or_(*[db.Tags.id == tid for tid in tag_ids])` — показывает книги с ЛЮБЫМ из matching tags
- `load_comments=True` для eager loading annotations
- `show_annotations=True` для отображения в шаблоне

### tests/test_aubooks_genres.py

Добавлены 4 regression tests:
- `test_sidebar_tree_deduplicates_same_label_from_code_and_russian_tag`
- `test_sidebar_tree_no_duplicate_labels_across_all_categories`
- `test_sidebar_tree_preserves_tag_id_for_url_generation`

## Результаты

### Tests

- 31 tests OK (test_seo_urls, test_seo_db, test_aubooks_genres)
- compileall OK
- 10 Jinja templates parsed OK
- git diff --check OK

### DOM Smoke

- Anonymous home: 261 leaves (was 357), 0 duplicates
- Compound URLs: `/category/stored/1245+2567` → 200
- Compound URL union: correctly shows books from both tags
- Genre result: 32 books, 30 annotations (books without comments show no annotation)
- 5 sidebar leaf links → all 200

### Дубли устранены

- 96 duplicate entries removed (357 → 261)
- Каждый label отображается ровно один раз в каждой категории
- Для merged标签: compound URL показывает union книг

### Аннотации восстановлены

- genre result pages теперь показывают annotations
- batch loading через `load_comments=True` (без N+1)
- пустые comments не ломают layout
