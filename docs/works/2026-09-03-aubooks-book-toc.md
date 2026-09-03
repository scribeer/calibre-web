# 2026-09-03: AU-Books Book TOC Requirements

## Блокер

**DEV не имеет доступа к физическим файлам книг.** Реализация реального TOC невозможна без изменения storage architecture.

## Доказательства

| Проверка | Результат |
|---|---|
| `find /home/feninf -name "*.epub"` | 0 файлов |
| `find /home/feninf -name "*.fb2"` | 0 файлов |
| `/home/feninf/calibre-web-dev-data/library/` | Только `metadata.db` (417MB) |
| `/home/feninf/aubooks/library/` | `metadata.db` + ~1040 `cover.jpg` (нет epub/fb2) |
| Book paths в metadata.db | Указывают на несуществующие директории |

Каталог содержит 122,463 книги (3,254 EPUB, 119,105 FB2, 108 MOBI в `data` таблице), но физические файлы не синхронизированы.

## Существующая архитектура Calibre-Web

### TOC сейчас — 100% client-side

- epub.js (JavaScript) парсит EPUB в браузере
- NCX/nav документ обрабатывается на клиенте
- Серверная сторона НЕ извлекает TOC
- TOC не хранится в БД

### Доступные серверные парсеры

| Файл | Что делает | Можно переиспользовать |
|---|---|---|
| `cps/epub_helper.py:get_content_opf()` | Открывает EPUB zip, читает container.xml, находит OPF | Да — база для навигации |
| `cps/epub.py:get_epub_info()` | Извлекает метаданные из OPF | Частично |
| `cps/fb2.py:get_fb2_info()` | Парсит FB2 XML метаданные | Частично |
| `lxml.etree` | XML/HTML парсинг | Да — для NCX/nav/OPF |
| `zipfile` (stdlib) | ZIP extraction | Да — для EPUB |

### Формат файлов

```
config.get_book_path() / book.path / data.name + "." + book_format.lower()
```

- `book.path` — относительный путь в библиотеке (e.g. `Author/Title`)
- `data.name` — имя файла без расширения
- `data.format` — `EPUB`, `FB2`, `PDF` и т.д.

## План реализации (когда файлы будут доступны)

### Форматы

1. **EPUB**: NCX (`toc.ncx`) или nav document (`nav.xhtml`)
2. **FB2**: `<section>/<title>` в XML

### Подход: Lazy

- На detail page: `<details><summary>Содержание</summary><div id="toc-content"></div></details>`
- При первом раскрытии: fetch к `/book/<id>/toc`
- Endpoint возвращает HTML с nested `<ol>`/`<ul>`
- In-process cache по book_id + file_mtime

### UI порядок

```
Описание → Содержание → Жанры
```

### Безопасность

- Извлекать только text заголовков + hierarchy + безопасный href
- Экранировать все titles (lxml автоматически)
- Не выводить raw HTML из книги
- Проверить `<script>alert(1)</script>` → отображается текстом

### Accessibility

- `<summary>Содержание</summary>` — native keyboard
- `<details>` без自动 open
- Focus ring не ломать

### CSS

- Использовать существующие AU CSS переменные
- Длинные названия глав — word-break
- Нет horizontal overflow

## Тестовые book ids (когда файлы будут доступны)

Нужно будет найти:
- EPUB с многоуровневым TOC
- EPUB без TOC
- FB2 с разделами
- Большой TOC
- Необычные символы в названиях глав

## Ограничения

- 119,105 FB2 vs 3,254 EPUB — FB2 основной формат библиотеки
- fb2.py уже парсит XML — расширение для TOC относительно просто
- EPUB TOC может быть в NCX или nav — оба варианта нужно поддерживать

## Следующий шаг

Синхронизировать физические файлы книг в DEV library (или подключить общий storage), затем реализовать:
1. `cps/toc.py` — extraction EPUB NCX/nav + FB2 sections
2. `/book/<id>/toc` — lazy endpoint
3. `detail.html` — `<details>` block
4. Tests
