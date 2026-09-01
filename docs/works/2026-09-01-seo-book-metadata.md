# SEO metadata для canonical book page AU-Books

## Вывод

SEO metadata для canonical detail page книги **уже полностью реализована** в существующем коде. Дополнительные изменения не требуются.

## Текущая реализация

### Backend: `cps/seo.py`

Функция `detail_context()` (строки 104-137) генерирует все SEO данные:

| Поле | Формат | Источник |
|---|---|---|
| `seo_title` | `Книга — Автор \| AU-Books` | `entry.title`, author names, `config.config_calibre_web_title` |
| `seo_description` | plain text, ≤160 chars | `_plain_text()` strips HTML from `entry.comments[0].text`; fallback `"title — authors"` |
| `canonical_url` | absolute URL | `external_url("seo.book_detail", ...)` |
| `seo_image` | cover URL | `external_url("web.get_cover", ...)` если `entry.has_cover` |
| `seo_json_ld` | schema.org Book dict | name, author[], description, url, inLanguage, image (conditional), isbn (conditional) |

### Frontend: `cps/themes/aubooks/templates/layout.html`

Строка 6: `<title>{% if seo_title %}{{seo_title}}{% else %}{{instance}} | {{title}}{% endif %}</title>`

### Frontend: `cps/themes/aubooks/templates/detail.html`

```html
{% block header %}
    <meta name="description" content="{{ seo_description }}">
    <link rel="canonical" href="{{ canonical_url }}">
    <meta property="og:type" content="book">
    <meta property="og:title" content="{{ entry.title }}">
    <meta property="og:description" content="{{ seo_description }}">
    <meta property="og:url" content="{{ canonical_url }}">
    <meta property="og:site_name" content="{{ instance }}">
    {% if seo_image %}<meta property="og:image" content="{{ seo_image }}">{% endif %}
    <script type="application/ld+json">{{ seo_json_ld|tojson }}</script>
{% endblock %}
```

### Rendering: `cps/web.py`

`render_book_detail()` (строки 1643-1690) вызывает `detail_context(entry, canonical_route)` и передаёт все поля через `**kwargs` в `render_title_template`.

## Проверенные metadata

### 1. `<title>`

| Книга | Результат |
|---|---|
| Дело о Медвежьем посохе | `Дело о Медвежьем посохе — Георгий Персиков \| AU-Books DEV` |
| Лили (арм.) | `Լիլի — Egretta Garzetta \| AU-Books DEV` |
| Стены из Хрусталя (2 автора) | `Стены из Хрусталя — Катя Коути, Кэрри Гринберг \| AU-Books DEV` |

### 2. `<meta name="description">`

- HTML description: strip HTML → plain text, ≤160 chars, truncation на word boundary
- Fallback (без description): `"Книга — Автор"`, ≤160 chars
- Пример без description: `Тайна Розенкрейцеров — Виталий Дмитриевич Гладкий...`

### 3. `<link rel="canonical">`

Всегда указывает на текущий SEO-friendly URL:
`http://127.0.0.1:8084/books/georgiy-persikov/delo-o-medvezhem-posohe`

Legacy URL `/book/1` → 301 → canonical URL.

### 4. Open Graph

- `og:type` = `book`
- `og:title` = book title (без truncate)
- `og:description` = same as meta description
- `og:url` = canonical URL
- `og:site_name` = instance name
- `og:image` = only if `has_cover` is true

### 5. JSON-LD Schema.org Book

```json
{
  "@context": "https://schema.org",
  "@type": "Book",
  "name": "Дело о Медвежьем посохе",
  "author": [{"@type": "Person", "name": "Георгий Персиков"}],
  "description": "По завершении Русско-японской войны...",
  "url": "http://127.0.0.1:8084/books/georgiy-persikov/delo-o-medvezhem-posohe",
  "inLanguage": "rus",
  "isbn": "978-5-17-095683-8",
  "image": "http://127.0.0.1:8084/cover/1/og"
}
```

- `isbn` — только если реальный ISBN есть в identifiers
- `image` — только если `has_cover`
- `inLanguage` — string или array
- Валидный JSON, Unicode escaped через Python `json.dumps`

## Проверенные edge cases

| Случай | Книг проверено | Результат |
|---|---|---|
| RU с description + ISBN | 3 | OK |
| RU без description | 3 | Fallback "title — author" |
| RU с HTML description | 2 | HTML stripped, plain text |
| Armenian Unicode | 1 | Unicode preserved |
| Multiple authors (35) | 1 | All listed |
| Long title (227 chars) | 1 | Truncated in meta, full in JSON-LD |
| Collision suffix (book-2) | 1 | Canonical correct |
| 50 random books JSON-LD | 50 | All valid JSON, all @type=Book |

## Проверки

| Проверка | Результат |
|---|---|
| HTTP 200 canonical page | OK |
| Legacy /book/1 → 301 | OK |
| git diff --check | Clean |
| Python compile | OK |
| Unit tests (18) | OK |
| JSON-LD validity (50 books) | OK |
| Production VPS2 | Not touched |
| Push | Not done |

## Файлы

Изменения не требуются — все metadata уже реализованы в:

| Файл | Что делает |
|---|---|
| `cps/seo.py:104-137` | `detail_context()` — генерация всех SEO данных |
| `cps/seo.py:43-56` | `_plain_text()`, `_description()` — очистка HTML, truncation |
| `cps/themes/aubooks/templates/layout.html:6` | `<title>` с seo_title override |
| `cps/themes/aubooks/templates/detail.html:1-12` | canonical, meta, OG, JSON-LD |
| `cps/web.py:1677-1685` | `render_book_detail()` — передача detail_context в шаблон |
