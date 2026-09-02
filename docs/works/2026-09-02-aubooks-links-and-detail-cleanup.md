# 2026-09-02: AU-Books Sort Controls, Detail Genres, Link Colors

## Цель

Три UI-изменения AU-Books:
1. Убрать кнопки сортировки из catalog pages
2. Перенести жанры после описания на detail page
3. Изменить цвет ссылок с зелёного на голубой

## Изменения

### 1. Убраны sort controls

Удалены `<nav class="filterheader aubooks-sort-controls">` из:

| Шаблон | Страницы |
|---|---|
| `index.html` | home, category result, series, hot, rated, discover |
| `author.html` | author books |
| `search.html` | search results |

Backend sorting logic и query params не изменены.

### 2. Detail: genres после description

Порядок в `.book-meta`:
1. Title (h1)
2. Author
3. Series
4. Languages
5. Publishing date
6. **Description (comments)** ← было до genres
7. **Genres** ← перенесены сюда
8. Download buttons
9. More stuff (shelves, edit)

Реализовано через переопределение `{% block body %}` в `detail.html`:
- `{% block book_tags %}{% endblock %}` — блокирует стандартный вставку тегов
- Полная копия body из standard/detail.html с reordered секциями
- Жанры сохраняют semantic hierarchy: Категория → Жанр

### 3. Цвет ссылок: зелёный → голубой

| Переменная | Было (light) | Стало (light) | Было (dark) | Стало (dark) |
|---|---|---|---|---|
| `--aubooks-link` | `#176b60` | `#1976d2` | `#4db8a4` | `#64b5f6` |
| `--aubooks-link-hover` | `#145c52` | `#1565c0` | `#6dcdb8` | `#90caf9` |

Изменены в трёх местах:
- `:root` (light mode)
- `[data-theme="dark"]` (dark mode)
- `@media (prefers-color-scheme: dark)` (no-JS dark)

Охвачены все link contexts через существующие CSS rules:
- Обычные links (`a` selector, section 6)
- Main content links (section 8)
- Book card title links (section 11)
- Sidebar genre links (section 7)
- Breadcrumbs (dark mode override)
- Pagination (dark mode override)

## Проверки

### Tests
- 31 tests OK (test_seo_urls, test_seo_db, test_aubooks_genres)
- 10 Jinja templates parsed OK

### DOM Smoke (anonymous DEV)
- Home: sort navs = 0
- Category result: sort navs = 0
- Detail: description idx=5, genres idx=6 (genres after description ✓)
- Link color: `#1976d2` (blue ✓)
- No green values (`#176b60`, `#145c52`, `#4db8a4`, `#6dcdb8`) in CSS ✓
- Genre links on detail page: working
