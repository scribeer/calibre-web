# SEO Sitemap для AU-Books

## Вывод

Sitemap для canonical book URLs **уже полностью реализован** в `cps/seo.py`. Дополнительные изменения не требуются.

## Архитектура

| Компонент | Реализация |
|---|---|
| Sitemap index | `/sitemap.xml` → XML sitemap index |
| Book sitemaps | `/sitemaps/books-<page>.xml` → XML urlset |
| Chunk size | 20000 URL на файл |
| Количество файлов | 7 (6 × 20000 + 1 × 2463) |
| Всего canonical URLs | 122463 |
| Streaming | Да (generator-based) |
| Cache | `Cache-Control: public, max-age=3600` |
| lastmod | Да (из `Books.last_modified`) |

## Что включено

- Только canonical book URLs: `/books/<author-slug>/<book-slug>`
- Абсолютные URL с правильным host
- XML escaping через `xml.sax.saxutils.escape`
- UTF-8 encoding
- Фильтрация через `calibre_db.common_filters` (скрытые/архивные книги исключены)

## Что исключено

- Legacy `/book/<id>` URLs
- Aliases (non-canonical routes)
- Search, login, admin, filters, pagination
- Internal utility routes

## HTTP проверки

| Endpoint | HTTP | Результат |
|---|---|---|
| `/sitemap.xml` | 200 | Sitemap index с 7 файлами |
| `/sitemaps/books-1.xml` | 200 | 20000 URLs |
| `/sitemaps/books-2.xml` | 200 | 20000 URLs |
| `/sitemaps/books-3.xml` | 200 | 20000 URLs |
| `/sitemaps/books-4.xml` | 200 | 20000 URLs |
| `/sitemaps/books-5.xml` | 200 | 20000 URLs |
| `/sitemaps/books-6.xml` | 200 | 20000 URLs |
| `/sitemaps/books-7.xml` | 200 | 2463 URLs |

## Примеры URL в sitemap

- Первый: `/books/georgiy-persikov/delo-o-medvezhem-posohe` (lastmod: 2025-04-01)
- Середина: `/books/lion-moiseevich-izmaylov/antologiya-satiry-i-yumora-rossii-xx-veka-tom-47-lion-izmaylov`
- Последний: `/books/illarion-pavliuk/knyha-emilia` (lastmod: 2026-08-20)
- Armenian: `/books/garzetta-egretta/lili`
- Collision suffix: `/books/egretta-garzetta/book-2`

## Производительность

| Запрос | Время |
|---|---|
| Sitemap index | 0.15s |
| Sitemap chunk (20000 URLs) | 3.58s |
| Sitemap chunk (2463 URLs) | 0.51s |

## Изменённые файлы

Нет — sitemap уже реализован в `cps/seo.py:163-229`.

## Что осталось для robots.txt

- Добавить `Sitemap: http://<host>/sitemap.xml` в robots.txt
- Настроить кэширование sitemap на уровне nginx/CDN
