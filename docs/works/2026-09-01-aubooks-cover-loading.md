# Обложки и ISBN в AU-Books

## Цель
Сделать каталоги текстовыми (без обложек), оставить обложку на detail page с lazy load, убрать ISBN из UI.

## Что сделано

### 1. Catalog pages — обложки полностью убраны

**Затронутые страницы:** home, page 2, search, author, series, grid/list, pagination.

**Файлы:**
- `cps/themes/aubooks/templates/_book_card.html` — удалён `<div class="cover">` с `<img srcset>`. Карточка стала полностью текстовой (title → author → series → formats → rating).
- `cps/themes/aubooks/templates/grid.html` — удалены cover из entries. Остались title + count.
- `cps/themes/aubooks/templates/author.html` — удалены внешние cover (Goodreads images) из "More by" секции.

**Результат:** 0 `<img>` тегов, 0 cover requests на home/search/author pages. Все 64+ карточки — `aubooks-text-only`.

### 2. Detail page — cover с lazy load и fail-safe

**Файл:** `cps/themes/standard/templates/detail.html`

**Изменения:**
- Добавлен `loading="lazy"` — браузер загружает cover после основного контента
- Добавлен `decoding="async"` — декодирование не блокирует рендеринг
- Добавлен `onerror="this.parentElement.parentElement.style.display='none'"` — при ошибке загрузки cover container скрывается, страница остаётся рабочей

**Источник cover:** `/cover/<book_id>/og` — существующий endpoint Calibre-Web, отдающий cover.jpg из Calibre library. Не OpenDrive (интеграция отсутствует в кодовой базе).

**Порядок загрузки:** HTML → title/author/description/metadata → lazy cover image. Cover не блокирует FCP.

### 3. ISBN убран из UI

**Файл:** `cps/static/css/aubooks.css`

**Метод:** CSS `display: none` на класс `.identifiers`. HTML генерируется upstream шаблоном, но скрыт от пользователя.

**ISBN в JSON-LD:** Сохранён. Пример: `"isbn": "978-5-17-095683-8"` в structured data.

### 4. CSS для текстовых карточек

Добавлены стили:
- `.aubooks-text-only` — padding для карточек без обложек
- `.identifiers` — `display: none` для скрытия ISBN из UI
- `.aubooks-cover-button img[data-failed="true"]` — fallback при ошибке загрузки

## Проверки на DEV

| Страница | Cover <img> | Status |
|----------|-------------|--------|
| Home (/) | 0 | 200 |
| Page 2 (/page/2) | 0 | 200 |
| Search | 0 | 200 |
| Author | 0 | 200 |
| Detail (Гипнотизер) | 1 (lazy) | 200 |
| Detail (Дело о Медвежьем посохе) | 1 (lazy) | 200 |
| Detail (Окно для Деда Мороза) | 1 (lazy) | 200 |

### DOM/network inspection
- Home: 0 `<img>` тегов, 0 cover requests
- Search: 0 `<img>` тегов, 0 cover requests
- Detail: 1 `<img>` с `loading="lazy"` `decoding="async"` `onerror`
- Identifiers: `display: none` в CSS
- JSON-LD: ISBN сохранён для книг с ISBN

## Что НЕ изменилось
- canonical URLs, slug, sitemap, robots, redirects
- JSON-LD structured data (ISBN сохранён)
- metadata.db schema
- Business logic
- Heading hierarchy (h1 → author → toolbar)

## О/OpenDrive
OpenDrive интеграция отсутствует в кодовой базе Calibre-Web. Единственный remote storage — Google Drive через pydrive2. Cover загружаются из локальной Calibre library через `/cover/<id>/og`.

## Commit
`4e7e12d1 Make AU-Books catalog text-first`
