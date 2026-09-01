# Исправление DOM order detail page

## Цель
Заголовок книги `h1` должен идти в DOM раньше toolbar с действиями Download/Send/Read/Shelf, чтобы screen reader читал страницу в логическом порядке.

## Решение
Перемещение блока h1 + author/metadata в `cps/themes/standard/templates/detail.html` так, чтобы он стоял перед toolbar.

### Способ
Прямой рефакторинг `standard/detail.html`: блоки переставлены местами в шаблоне. Без JS, без копирования шаблона, без дополнительных абстракций.

### Почему этот способ
- Минимальное изменение: 1 файл, перестановка существующих блоков
- Не дублирует шаблон
- Не меняет бизнес-логику
- Не затрагивает SEO URL, canonical, JSON-LD, sitemap, robots
- Все темы (standard, AU) получают исправление автоматически

## Изменённые файлы
- `cps/themes/standard/templates/detail.html` — блок h1 + author/metadata перемещён перед toolbar

## DOM порядок (до / после)

### До
```
breadcrumb → toolbar (Download/Send/Read) → h1 → author → rating → ... → more-stuff
```

### После
```
breadcrumb → h1 → author → rating → series → ... → toolbar (Download/Send/Read) → more-stuff
```

## Подтверждённый порядок на DEV
```
breadcrumb(5972) → h1(6513) → author(6559) → toolbar(8019) → more-stuff(8275)
```

## Проверки

### DOM order assertion
| Book | h1 < toolbar | h1 count | toolbar buttons |
|------|-------------|----------|-----------------|
| Гипнотизер (Lars Kepler) | OK | 1 | Download, Send, Read |
| Окно для Деда Мороза | OK | 1 | Download |
| Академия Горгулий | OK | 1 | Download |

### HTTP smoke
| Page | Status |
|------|--------|
| Home (/) | 200 |
| Page 2 (/page/2) | 200 |
| Login (/login) | 200 |
| Detail (/books/lars-kepler/gipnotizer-2) | 200 |
| Detail (/books/artemiy-dergunov/okno-dlya-deda-moroza) | 200 |
| Robots.txt | 200 |
| Sitemap | 200 |
| Legacy /book/1 → 301 | OK |

### Other checks
- git diff --check: OK
- Python compile: OK
- Unit tests: 18/18 OK
- Canonical link: present
- Sitemap: 9 entries
- Heading hierarchy: h1 (title) → h2 (Description/Book Details)

## Что НЕ изменилось
- SEO URL architecture (canonical, sitemap, robots, slugs)
- JSON-LD structured data
- Business logic (download, send, read, shelf operations)
- Modal behavior (focus trap, Escape, aria-modal)
- Breadcrumb (aria-current="page")
- Toolbar accessible name (aria-label)

## Commit
`e8f772e3 Improve book detail reading order`
