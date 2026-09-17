# Friendly metadata URLs and unified AU-Books titles

## Цель
Canonical URLs для публичных metadata book-list pages и единые AU-Books page titles.

## Изменённые файлы
- `cps/seo_db.py` — модель `SeoMetadataRoute` для persistent slug mappings
- `cps/seo.py` — `aubooks_page_title()`, `metadata_url()`, `resolve_metadata()`, `template_url_for()` override для metadata entities
- `cps/web.py` — `metadata_books()` route handler, legacy 301 redirects, seo_context propagation
- `cps/search.py` — canonical URL и seo_title для поиска
- `cps/themes/aubooks/templates/layout.html` — generic canonical via `{% block header %}`
- `tests/test_seo_db.py` — 3 новых теста для collision, persistence, independence

## Что реализовано
- Persistent slug mappings в app DB (`aubooks_seo_metadata_route`) для author, series, category/genre, publisher, language, rating
- Collision-safe slug generation: базовый slug без ID + deterministic `-<entity_key>` suffix при collision
- Новые routes:
  - `/author/<slug>`
  - `/series/<slug>`
  - `/genre/<slug>`
  - `/publisher/<slug>`
  - `/language/<slug>`
  - `/rating/<slug>`
- Legacy redirect: `/author/stored/<book_id>` → 301 на friendly URL
- `template_url_for()` override: все `url_for('web.books_list', data=<entity>, sort_param='stored', book_id=<id>)` автоматически генерируют friendly URL
- Unified titles: `aubooks_page_title()` генерирует title по шаблону
- Generic canonical URL через `layout.html` `{% block header %}`
- Sort parameter fallback: если slug совпадает с валидным sort param (stored, abc, zyx, etc.), делегирует в `books_list`

## Как проверено
- 170 unit tests pass (SEO, genres, sidebar cache, theme templates, eager loading)
- `python3 -m compileall` clean
- `git diff --check` clean
- Pre-existing failures (deploy helper, cmd_start, invite admin) unrelated

## Известные ограничения
- Slug маппинги создаются lazily при первом URL generation через template
- Прямой доступ к friendly URL без предварительного создания slug вернёт 404
- Канонический URL не включает search languages (locale-dependent)
