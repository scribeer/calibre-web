# 2026-09-03: AU-Books Parent Category 500 Fix

## Цель

Исправить 500 Internal Server Error на `/category/<slug>`.

## Точная причина 500

Route `/category/<slug>` registered AFTER `/category/<sort_param>` (from `books_list` loop at line 836-842). Flask matched `/category/fantastika` against `/category/<sort_param>` first, sending it to `books_list` with `sort_param='fantastika'`, not to `category_by_slug`.

The existing breadcrumb template at `index.html:10` then tried to build `url_for('web.category_by_slug', ...)`, but this endpoint was never called — it was the wrong request path. The `BuildError` occurred in the child genre page breadcrumb when `aubooks_genre.category_slug` was present but the route wasn't reachable.

**Fix:** Register `category_by_slug` via `web.add_url_rule()` BEFORE the `books_list` loop, so Flask matches `/category/<slug>` first.

## Traceback

```
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint
'web.category_by_slug' with values ['slug']. Did you mean 'web.category_list' instead?
```

At `index.html:10` in breadcrumb: `url_for('web.category_by_slug', slug=aubooks_genre.category_slug)`.

## Files Changed

| File | Change |
|---|---|
| `cps/web.py` | Moved `category_by_slug` before `books_list` loop, registered via `add_url_rule` |
| `cps/aubooks_genres.py` | Added `_slugify`, `CATEGORY_SLUGS`, `category_by_slug`, `build_category_slug_map` |
| `cps/aubooks_genres.py` | `build_sidebar_genre_tree` adds `category_slug` to each group |
| `cps/aubooks_genres.py` | `group_tags` adds `category_slug` to each group |
| `cps/themes/aubooks/templates/layout.html` | Sidebar parent links → `web.category_by_slug` |
| `cps/themes/aubooks/templates/detail.html` | Genre parent links → `web.category_by_slug` |
| `cps/themes/aubooks/templates/index.html` | Breadcrumb parent link → `web.category_by_slug` |
| `tests/test_aubooks_genres.py` | 10 new tests (slug helpers + templates) |

## HTTP Results

| URL | Status |
|---|---|
| `/category/fantastika` | 200 |
| `/category/detektivy-i-trillery` | 200 |
| `/category/spravochnaya-literatura` | 200 |
| `/category/unknown-slug` | 404 |

## Tests

- 47 tests OK (test_aubooks_genres, test_seo_urls, test_seo_db)
- Python compile OK
