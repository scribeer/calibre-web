# 2026-09-02: AU-Books Detail Layout and Category Links

## Цель

1. Сделать верхнеуровневые категории кликабельными в genre hierarchy
2. Исправить layout detail page: убрать перекрытие h1 и обложки

## Изменения

### 1. Кликабельные категории

**Backend** (`aubooks_genres.py`):
- `group_tags()`: добавлен `category_tag_ids` в каждую группу — список tag_id для compound URL
- `build_sidebar_genre_tree()`: добавлен `category_tag_ids` в каждую группу sidebar

**Detail page** (`detail.html`):
- `<span class="aubooks-genre-category">` → `<a class="aubooks-genre-category" href="...">`
- URL: `group.category_tag_ids|join('+')` → `/category/stored/123+456+789`

**Sidebar** (`layout.html`):
- `<summary>{{group.category}}</summary>` → `<summary><a href="...">{{group.category}}</a></summary>`
- Ссылка внутри `<summary>`: клик по тексту → переход, клик по стрелке → toggle

**CSS** (`aubooks.css`):
- `summary a`: inherit color, no underline; hover → link color + underline

### 2. Detail layout fix

**Проблема**: `#title` had `width: 133.333333%; margin-left: -33.333333%` — h1 визуально заходил в область обложки.

**Решение** — CSS Grid:
```css
.aubooks-main .single .row {
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr);
  gap: 0 1.5rem;
}
.aubooks-main .single .book-meta {
  min-width: 0;
}
```

**Mobile** (`max-width: 767px`):
```css
.aubooks-main .single .row {
  grid-template-columns: 1fr;
}
.aubooks-main .single .aubooks-detail-cover-column {
  max-width: 300px;
  margin: 0 auto;
}
```

Удалено: `width: 133.333333%; margin-left: -33.333333%` из `#title`.

## Результаты

### Tests
- 31 tests OK
- 10 Jinja templates parsed OK
- git diff --check OK

### DOM Smoke
- Detail: 2 category links (Фантастика, Другие жанры), both return 200
- Sidebar: 21 category links, all return 200
- Фантастика: 64 tag_ids in compound URL
- No duplicate tag_ids in any URL
- CSS Grid present, title overlap removed
- Cover and content are separate grid columns
