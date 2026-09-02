# 2026-09-02: AU-Books Detail Cover Regression Fix

## Цель

Вернуть обложки на detail pages после commit `a542ac91`, не ломая новый grid layout.

## Причина исчезновения обложек

CSS правило (sector 14, Cover button):

```css
.aubooks-cover-button img[data-failed="true"],
.aubooks-cover-button img:not([src]) {
  display: none;
}
```

Селектор `img:not([src])` скрывал `<img>` до того, как JS deferred loader (`aubooks-pages.js:loadDeferredCovers`) успевал скопировать `data-src` в `src`.

С Bootstrap grid (`col-sm-3`) скрытый image не влиял на ширину колонки (Bootstrap задаёт фиксированную ширину через percentages). Но с CSS Grid `minmax(0, auto)` ширина cover-колонки зависит от контента. `display: none` → нулевой контент → нулевая ширина → cover исчезает.

## Исправление

Удалён селектор `img:not([src])` из правила скрытия. Оставлен только `img[data-failed="true"]` для обработки ошибок загрузки.

**Было:**
```css
.aubooks-cover-button img[data-failed="true"],
.aubooks-cover-button img:not([src]) {
  display: none;
}
```

**Стало:**
```css
.aubooks-cover-button img[data-failed="true"] {
  display: none;
}
```

Fallback сохранён: `onerror` на `<img>` устанавливает `data-failed="true"` и добавляет класс `cover-unavailable` на колонку.

## Дополнительно

Исправлена ошибка в `group_tags()`: `category_tag_ids` собирал только первый tag_id на код. Теперь收集ляются все tag_ids (для compound URL).

## Файлы

| Файл | Изменение |
|---|---|
| `cps/static/css/aubooks.css` | Удалён `img:not([src])` из cover hiding rule |
| `cps/aubooks_genres.py` | `group_tags()`: `category_tag_ids`收集ляет все tag_ids |
| `tests/test_aubooks_genres.py` | 2 regression test для `category_tag_ids` |

## Проверки

### Cover endpoint
- `/cover/35395/og` → 200, image/jpeg, 19501 bytes

### DOM
- Detail page: cover `<img>` с `data-src`, без `src` (deferred loading)
- `cover-unavailable` class отсутствует
- Grid layout: `grid-template-columns: minmax(0, auto) minmax(0, 1fr)`

### Tests
- 33 tests OK (test_seo_urls, test_seo_db, test_aubooks_genres)
- 10 Jinja templates parsed OK
