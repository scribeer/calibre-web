# Загрузка обложек с OpenDrive

## Цель
Detail page AU-Books должна получать обложки с OpenDrive через backend, не раскрывая credentials браузеру.

## Инфраструктура OpenDrive

### Найдено
- rclone remote: `opendrive:` (type=webdav, URL=https://webdav.opendrive.com)
- Каталог covers: `opendrive:calibre-books-v2/<book_id>/<book_id>.jpg`
- Пример: book ID 25916 → `calibre-books-v2/25916/25916.jpg`
- 41690 объектов, 29.18 GB
- Нет FUSE mount, нет существующей интеграции в Calibre-Web

### Архитектура

```
Browser
  → /cover/<book_id>/og  (Calibre-Web endpoint)
    → cps/opendrive.py  (in-memory cache, 200 entries, TTL 1h)
      → http://127.0.0.1:19876/<book_id>/<book_id>.jpg  (rclone proxy)
        → OpenDrive WebDAV (credentials в rclone config)
```

### rclone serve http proxy
- Persistent systemd user service: `rclone-opendrive-covers.service`
- `rclone serve http opendrive:calibre-books-v2 --addr 127.0.0.1:19876 --read-only`
- 24h directory cache, read-only, no auth on local port
- Автозапуск через systemd user

## Изменения

### Backend
- **`cps/opendrive.py`** (новый) — fetch cover from localhost proxy
  - urllib HTTP GET → 127.0.0.1:19876
  - In-memory cache: 200 entries, 1h TTL
  - Timeout 10s
  - Fail-safe: HTTPError 404, URLError, Timeout → return None
- **`cps/web.py`** — `get_cover()` пробует OpenDrive для `og` resolution, fallback на local
  - Импорт `Response` добавлен

### Frontend
- **`cps/themes/standard/templates/detail.html`**:
  - `src=` заменён на `data-src=` для deferred loading
  - Блок identifiers (ISBN) удалён из шаблона (не CSS!)
- **`cps/static/js/aubooks-pages.js`**:
  - `loadDeferredCovers()` — после `requestIdleCallback` или `window.load` назначает `src` из `data-src`
  - Не задерживает рендеринг h1/author/description/metadata/actions
- **`cps/static/css/aubooks.css`**:
  - Удалён `.identifiers { display: none }` (HTML удалён)
  - Фоллбэк: `img:not([src])` скрывает незагруженные обложки

### Systemd
- **`~/.config/systemd/user/rclone-opendrive-covers.service`** — persistent proxy

## Проверки

### 15 книг (все has_cover=1)
| Book ID | Source | Size |
|---------|--------|------|
| 1 | OpenDrive | 324KB |
| 2 | OpenDrive | 146KB |
| 4 | OpenDrive | 48KB |
| 5 | OpenDrive | 680KB |
| 6 | OpenDrive | 20KB |
| 7 | OpenDrive | 478KB |
| 9 | OpenDrive | 325KB |
| 10 | Generic fallback | 20KB |
| 11 | OpenDrive | 73KB |
| 12 | OpenDrive | 458KB |
| 13 | OpenDrive | 560KB |
| 15 | OpenDrive | 162KB |
| 16 | OpenDrive | 110KB |
| 17 | OpenDrive | 379KB |
| 18 | OpenDrive | 73KB |

### Deferred loading
- HTML: `<img data-src="/cover/ID/og" loading="lazy" decoding="async" onerror="...">`
- Нет `src=` — запрос cover не начинается до JS
- JS: `requestIdleCallback` → `window.load` → `loadDeferredCovers()`
- h1, author, description, metadata, actions рендерятся мгновенно

### Credentials
- Нет rclone, webdav, opendrive, fenreg, password в HTML
- Credentials в rclone config, не в PHP/Python config
- Proxy на localhost — credentials не покидают сервер

### ISBN
- Удалён из template (не CSS)
- Остался в JSON-LD: `"isbn": "978-5-17-095683-8"`

### Catalog pages
- Home: 0 `<img>`, 0 cover requests
- Search: 0 `<img>`, 0 cover requests

### Fail-safe
- OpenDrive 404 → fallback на generic cover
- Proxy недоступен → fallback на generic cover
- Timeout 10s → fallback на generic cover
- onerror в JS → скрывает broken cover

## Что НЕ изменилось
- Canonical URLs, slug, SEO mapping
- Sitemap, robots, redirects
- metadata.db
- Catalog pages (text-first)
- Heading hierarchy

## Commit
`4e7e12d1 Make AU-Books catalog text-first` (текущий)
Новый commit: `Load book covers from OpenDrive`
