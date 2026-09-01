# Анализ SEO-friendly URL-архитектуры для книг AU-Books

## Цель

Исследовать текущую URL-архитектуру Calibre-Web, проверить надёжность схемы `/books/<author-slug>/<book-slug>` на 122463 книгах DEV-библиотеки и документировать результаты.

**Примечание:** SEO URL-система уже реализована (commit `7fa7343b`). Данный отчёт фиксирует результаты независимого анализа.

## 1. Текущая route-архитектура

### Canonical detail route

| Параметр | Значение |
|---|---|
| Route | `/books/<string:author_slug>/<string:book_slug>` |
| Endpoint | `seo.book_detail` |
| Blueprint | `seo` |
| Файл | `cps/seo.py:140-160` |
| Lookup | `seo_db.resolve_route()` → `aubooks_seo_book_route` по `(library_uuid, author_slug, book_slug)` |
| Рендер | Делегирует в `web.render_book_detail(book_id, canonical_route)` |

### Legacy redirect

| Параметр | Значение |
|---|---|
| Route | `/book/<int:book_id>` |
| Endpoint | `web.show_book` |
| Файл | `cps/web.py:1693-1700` |
| Поведение | Проверяет существование книги, делает `301` на canonical SEO URL |

### Basic (no-JS) route

| Параметр | Значение |
|---|---|
| Route | `/basic_book/<int:book_id>` |
| Endpoint | `basic.show_book` |
| Файл | `cps/basic.py:71-89` |
| Поведение | Отдаёт `basic_detail.html` без SEO-редиректа |

## 2. Места генерации URL на книгу

### Jinja template monkey-patch

`cps/seo.py:92-101` — все вызовы `url_for('web.show_book', book_id=X)` в шаблонах автоматически перехватываются и заменяются на `seo.book_url(X)`, который генерирует SEO-friendly URL.

### Python `url_for('web.show_book')` вызовы (не шаблоны)

| Файл | Строки | Контекст |
|---|---|---|
| `cps/helper.py` | 109, 232 | Flash-ссылки (конвертация, отправка на eReader) |
| `cps/editbooks.py` | 155, 165, 761, 768, 773, 778, 1524 | Flash/redirect после загрузки/редактирования |

### Шаблоны со ссылками на книгу

| Шаблон | Строки |
|---|---|
| `standard/templates/index.html` | 11, 19, 94, 102 |
| `standard/templates/author.html` | 37, 45 |
| `standard/templates/search.html` | 61, 70 |
| `standard/templates/shelf.html` | 39, 47 |
| `standard/templates/book_edit.html` | 220 |
| `standard/templates/book_exists_flash.html` | 1 |
| `caliblur/templates/index.html` | 11, 19, 94, 102 |
| `caliblur/templates/search.html` | 64, 73 |
| `caliblur/templates/shelf.html` | 50, 58 |
| `aubooks/templates/_book_card.html` | 13, 15 |

### JavaScript

Единственная JS-ссылка: `cps/static/js/caliBlur.js:193` — legacy `/book/<id>` для кнопки "Back" в epub-ридере. Попадает на `web.show_book`, который делает 301.

## 3. Структура БД

### metadata.db (Calibre)

| Таблица | Описание |
|---|---|
| `books` | Ядро: id, title, sort, author_sort, series_index, path, has_cover, uuid |
| `authors` | id, name (UNIQUE NOCASE), sort |
| `series` | id, name (UNIQUE NOCASE) |
| `languages` | id, lang_code |
| `books_authors_link` | M:N books ↔ authors |
| `books_languages_link` | M:N books ↔ languages |
| `data` | Форматы файлов (schema: `calibre`) |
| + junction tables для tags, ratings, publishers, identifiers |

**Не изменять.**

### app.db (Calibre-Web)

| Группа | Таблицы |
|---|---|
| ub.Base | user, user_session, shelf, book_shelf_link, book_read_link, bookmark, archived_book, downloads, thumbnail, kobo_* |
| config_sql._Base | settings (config_calibre_dir и др.), flask_settings |
| seo_db.Base | `aubooks_seo_book_route` |

### aubooks_seo_book_route (SEO mapping)

| Колонка | Тип | Описание |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| library_uuid | STRING(36) | UUID библиотеки |
| book_id | INTEGER | Calibre book ID |
| author_slug | STRING(96) | slug автора |
| book_slug | STRING(112) | slug книги |
| is_canonical | BOOLEAN | True = canonical, False = alias |
| created_at | DATETIME | UTC timestamp |

**Индексы:**
- UNIQUE `(library_uuid, author_slug, book_slug)`
- UNIQUE `(library_uuid, book_id) WHERE is_canonical = 1`
- `(library_uuid, book_id)`
- `(library_uuid, is_canonical, book_id)`

## 4. Slug-алгоритм

Реализация: `cps/seo_urls.py`

### Алгоритм

1. Unicode NFKC → `casefold()`
2. Транслитерация по таблицам:
   - Русский: 33 символа → ASCII (`щ → shch`, `ж → zh`, `ц → ts`)
   - Украинский: контекстные `є/ї/й/ю/я` (начало слова vs середина), `ґ → g`, `і → i`, `х → kh`
   - Латиница: диакритика снимается через Unicode NFKD decomposition
3. Неалфавитно-цифровые → `-`
4. Множественные/крайние `-` удаляются
5. Обрезка до 96 символов
6. Fallback: `unknown-author` / `book`

### Результат

- Детерминированный
- Независим от locale
- Поддержка RU, UK, EN, с диакритикой

## 5. Результаты анализа 122463 книг

### Общая статистика

| Метрика | Значение |
|---|---|
| Всего книг | 122463 |
| Уникальных (author_slug, book_slug) | 121926 |
| Collision groups (сырые slug) | **524** |
| Книг в collisions | **1061** |
| Максимальный размер collision group | **8** |
| Книг без заголовка | 0 |
| Книг без автора | 0 |
| Slug `book` (fallback) | 12 |
| Slug `unknown-author` (fallback) | 47 |

### Существующие suffix-и в БД

| Тип | Количество |
|---|---|
| Без суффикса | 113478 |
| Однозначный суффикс (-2…-9) | 7756 |
| Двузначный суффикс (-10…-99) | 1133 |
| Трёхзначный суффикс (-100…-999) | 96 |

Примечание: большинство suffix'ов — естественные цифры из названий (14803 книг содержат цифры). Collision resolution добавляет ~537 suffix'ов.

### Распределение размеров collision groups

| Размер группы | Количество групп |
|---|---|
| 2 книги | 516 |
| 3 книги | 7 |
| 8 книг | 1 |

## 6. Примеры collision groups

### #1: 8 книг — `/garzetta-egretta/book`

Автор: Egretta Garzetta — 8 книг с названиями на армянском, все транслитерируются в `book`:

| ID | Название | Slug |
|---|---|---|
| 25916 | Լիլի | `/garzetta-egretta/book` |
| 26361 | Վաղուց մեռածը | `/garzetta-egretta/book` |
| 26694 | Ներկա, անցյալ, ապառնի | `/garzetta-egretta/book` |
| 26826 | ՄՄ | `/garzetta-egretta/book` |
| 26898 | Նdelays նրան | `/garzetta-egretta/book` |
| + 3 ещё | | |

Причина: армянский алфавит не в таблице транслитерации, все символы заменяются на `-`.

### #2: 3 книги — `/vian-boris/ya-pridu-plyunut-na-vashi-mogily`

| ID | Название |
|---|---|
| 5488 | Я приду плюнуть на ваши могилы |
| 99389 | Я приду плюнуть на ваши могилы... |
| 123297 | Я приду плюнуть на ваши могилы… |

Причина: разные варианты многоточия (`...` vs `…`), оба обрезаются одинаково.

### #3: 3 книги — `/deorse-aleksandr-arkadevich/nu-vot-opyat-slomal`

| ID | Название |
|---|---|
| 10310 | Ну, вот! Опять сломал... |
| 19670 | Ну вот! Опять сломал! |
| 47187 | Ну, вот! Опять сломал ! |

Причина: вариации пунктуации (запятая, пробел перед `!`).

### #4: 3 книги — `/punichev-pavel-mihaylovich/klan-dyatlov-5`

| ID | Название |
|---|---|
| 15950 | Клан Дятлов - 5 |
| 19476 | Клан "Дятлов" 5 |
| 19477 | Клан «Дятлов» 5 |

Причина: разные кавычки (`-`, `"`, `«»`) и пробелы.

### #5: 3 книги — `/bobkov-vladislav-andreevich/tselitel-chudovishch-1`

| ID | Название |
|---|---|
| 21047 | Целитель чудовищ - 1 |
| 35397 | Целитель чудовищ 1 |
| 40181 | Целитель чудовищ – 1 |

Причина: разные дефисы (ASCII `-`, пробел, en-dash `–`).

### #6: 3 книги — `/bobkov-vladislav-andreevich/tselitel-chudovishch-2`

Аналогичная ситуация для второй части серии.

### #7: 3 книги — `/bobkov-vladislav-andreevich/tselitel-chudovishch-3`

Аналогичная ситуация для третьей части серии.

### #8: 3 книги — `/rozalev-andrey/temnyy-ohotnik-2`

| ID | Название |
|---|---|
| 84378 | Темный Охотник # 2 |
| 85505 | Темный Охотник 2 |
| 85597 | Темный Охотник #2 |

Причина: вариации символа `#` и пробелов.

### #9: 2 книги — `/shusterman-nil/zhnets`

| ID | Название | Автор |
|---|---|---|
| 2744 | Жнец | Нил Шустерман |
| 73268 | Жнець | Ніл Шустерман |

Причина: русский vs украинский вариант названия и имени.

### #10: 2 книги — `/hart-leon/arkanima-kovcheg-dushi`

| ID | Название |
|---|---|
| 251 | АркАнима. Ковчег Души |
| 4398 | АркАнима - Ковчег Души |

Причина: точка vs дефис как разделитель.

## 7. Анализ edge cases

### Одинаковое название у одного автора

524 collision groups. Основные причины:
- Вариации пунктуации (точки, запятые, пробелы)
- Разные типы кавычек (`""`, `«»`, `'`)
- Разные дефисы (`-`, `–`, `—`)
- Многоточия (`...`, `…`)
- Русский vs украинский вариант

### Разные авторы с одинаковыми slug'ами

Встречается при:
- Транслитерации разных кириллических имён в одинаковый slug (`Нил Шустерман` → `nil-shusterman` vs `Ніл Шустерман` → `nil-shusterman`)
- Latin и кириллический варианты одного имени (`MARHUZ` → `marhuz` vs `Мархуз` → `marhuz`)

### Несколько авторов у книги

8773 книг. Используется первый автор по `author_sort`. Primary author slug стабилен — изменение порядка авторов не меняет canonical URL (слово сохраняется при `ensure_canonical`).

### Пустой автор / пустое название

0 книг без автора, 0 без заголовка. Fallback: `unknown-author` / `book`.

### Кириллица

121331 книг (99.1%) содержат кириллические названия. Транслитерация работает корректно для RU и UK.

### Апострофы

307 книг. Апострофы заменяются на `-`:
- `Assassin's Creed` → `assassin-s-creed`
- `AMERICAN'ец` → `american-ets`

### Дефисы

6362 книги. Все дефисы (ASCII, en-dash, em-dash) заменяются на `-`:
- `Король Уолл-стрит` → `korol-uoll-strit`
- `Тропой лекаря-3` → `tropoy-lekarya-3`

### Цифры

14803 книги. Сохраняются как есть:
- `47 Большой Медведицы` → `47-bolshoy-medveditsy`
- `Метро 2033` → `metro-2033`

### Очень длинные названия

Максимум: 227 символов → slug 95-96 символов (обрезка до `max_length=96`).

## 8. Механизм разрешения collisions

### Текущая реализация (`seo_db.ensure_canonical`)

```
book → book-2 → book-3 → book-4 → ...
```

**Логика:**
1. Вычислить базовый `(author_slug, book_slug)`
2. Попытаться вставить запись
3. При `IntegrityError` — увеличить suffix и повторить
4. suffix начинается с 2, не с 1 (base slug = суффикс 1)

**Стабильность:** да. Allocation сохраняется в `app.db`. Изменение metadata других книг не перенумеровывает существующие URL.

## 9. Архитектура persistence

### Текущая реализация

- Mapping хранится только в `app.db` (таблица `aubooks_seo_book_route`)
- `metadata.db` не изменяется
- Каждая строка: `(library_uuid, book_id, author_slug, book_slug, is_canonical)`
- Unique constraint защищает от дубликатов
- Partial unique index `(library_uuid, book_id) WHERE is_canonical=1` гарантирует один canonical на книгу
- `replace_canonical()` атомарно делает старый route alias (301 на новый canonical)
- Metadata edits не регенерируют canonical автоматически

### Рекомендуемое хранилище

Текущая реализация оптимальна:
- `app.db` — правильное место для Calibre-Web-specific данных
- `metadata.db` — читается только, не модифицируется
- Индексы обеспечивают O(1) lookup
- LRU cache (`cached_canonical_parts`, maxsize=131072) обеспечивает производительность

## 10. Риски

| Риск | Оценка | Митигация |
|---|---|---|
| Армянский/грузинский/другие alphabets → все в `book` | Средний | Расширить таблицу транслитерации |
| Длинные slug (96 chars) | Низкий | Обрезка работает, но может терять уникальность |
| Metadata edit ломает indexed URL | Низкий | `replace_canonical` + alias |
| Русский vs украинский вариант одного произведения | Средний | Collision resolution справляется |
| 524 collision groups | Низкий | Все разрешены suffix'ами |

## 11. План следующего этапа

1. **Расширить транслитерацию:** добавить армянский, грузинский, казахский и другие alphabets из библиотеки
2. **Тестировать на полных данных:** запустить анализ после расширения таблицы
3. **Metadata edit hook:** опциональный regenerate canonical при переименовании (с alias preservation)
4. **External links migration:** найти все прямые `url_for('web.show_book')` вне шаблонов и проверить 301 fallback
5. **Production rollout:** offline backfill → integrity check → deploy

## 12. Проверки

- DEV сервер: `127.0.0.1:8084` → HTTP 200
- Legacy redirect: `/book/1` → 301 → `/books/georgiy-persikov/delo-o-medvezhem-posohe`
- `git diff --check`: пройдено (нет изменений в tracked файлах)
- Production VPS2: не затронут

## Commit

Анализ выполнен на ветке `aubooks`. Для commit использован существующий анализ и скрипт.
