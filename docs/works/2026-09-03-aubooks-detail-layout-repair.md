# 2026-09-03: AU-Books Detail Layout Repair

## Цель

Исправить regression в detail pages: обложки исчезли и layout сломался после commit `a542ac91`.

## Причина

Коммит `a542ac91` добавил CSS Grid на Bootstrap `.row`:

```css
.aubooks-main .single .row {
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr);
}
```

Это конфликтует с Bootstrap `.col-xs-5` / `.col-sm-3`, которые задают явную ширину `width: 41.6667%`. С Grid ширина cover-колонки определяется через auto-sizing, но Bootstrap `.col-xs-5` переопределяет это → изображение загружается (naturalWidth=570), но рендерится 2×2px.

Playwright показал: `.cover` computed width = 0px, изображение 2×2px, grid columns `572px 508px` (image squished).

## Исправление

Заменена структура DOM: Bootstrap `.row`/`.col-*` → собственный `.aubooks-detail-layout` wrapper с CSS Grid.

**Было (detail.html):**
```html
<div class="row">
    <div class="col-sm-3 col-lg-3 col-xs-5 aubooks-detail-cover-column">
    <div class="col-sm-9 col-lg-9 book-meta">
```

**Стало:**
```html
<div class="aubooks-detail-layout">
    <div class="aubooks-detail-cover-column">
    <div class="aubooks-detail-content book-meta">
```

**CSS (aubooks.css):**
```css
.aubooks-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr);
  gap: 0 1.5rem;
  align-items: start;
}
.aubooks-detail-content { min-width: 0; }
```

## Playwright результаты

| Экран | Cover left | Content left | scrollWidth | Гориз. скролл |
|---|---|---|---|---|
| 1366×768 | 255 | 842 | 1366 | нет |
| 390×844 | 52.5 | 30 | 390 | нет |

## Файлы

| Файл | Изменение |
|---|---|
| `cps/themes/aubooks/templates/detail.html` | `.row` → `.aubooks-detail-layout`, col classes removed |
| `cps/static/css/aubooks.css` | Grid rules updated to `.aubooks-detail-layout`, mobile `grid-template-columns: 1fr` |
| `tests/test_aubooks_genres.py` | 5 regression tests в `AubooksDetailTemplateTest` |

## Проверки

- 37 tests OK (test_aubooks_genres, test_seo_urls, test_seo_db)
- 10 Jinja templates parsed OK
- `git diff --check` clean
