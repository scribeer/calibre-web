# Улучшение транслитерации SEO slug для AU-Books

## Цель

Устранить fallback slug "book" для армянских/грузинских названий и сделать slug generation устойчивее для нелатинских алфавитов.

## Проблема

Армянский алфавит (U+0530-U+058F) не имел таблицы транслитерации. Символы не раскладывались в ASCII через NFKD,-result пустой → fallback "book". 8 книг Egretta Garzetta с армянскими названиями все получали slug "book".

## Изменения

### cps/seo_urls.py

Добавлены:
- `_ARMENIAN` — таблица транслитерации 36 символов (ա→a, բ→b, գ→g, ... ֆ→f)
- `_GEORGIAN` — таблица транслитерации 38 символов (ა→a, ბ→b, გ→g, ... ჰ→h)
- `_ARMENIAN_RANGE`, `_GEORGIAN_RANGE` — regex для авто-определения скрипта
- `_is_script()` — универсальная функция авто-определения по language code и символам
- Обновлён `_transliterate()`: приоритет Armenian > Georgian > Ukrainian > Russian

Авто-определение работает даже если `lang_code="rus"` (как в данных Egretta Garzetta) — по presence символов в Unicode block.

### tests/test_seo_urls.py

Добавлены 7 новых тестов:
- `test_armenian_transliteration` — 4 проверки армянской транслитерации
- `test_armenian_auto_detected_from_chars` — авто-определение армянского по символам
- `test_georgian_transliteration` — 2 проверки грузинской транслитерации
- `test_georgian_auto_detected_from_chars` — авто-определение грузинского по символам
- `test_mixed_cyrillic_latin` — смешанный кириллица/латиница
- `test_digits_preserved` — цифры сохраняются
- `test_apostrophes_normalized` — апострофы нормализуются
- `test_hyphens_in_title` — дефисы в названиях

### scripts/aubooks-seo-migrate-fallback.py

DEV-only миграционный скрипт для обновления fallback routes. Сохраняет старые slugs как alias (301 redirect).

## Результаты анализа 122463 книг

### До исправления
| Метрика | Значение |
|---|---|
| Fallback "book" | 8 (Egretta Garzetta group) |
| Collision groups | 524 |
| Books in collisions | 1061 |
| Max collision group | 8 |

### После исправления
| Метрика | Значение |
|---|---|
| Fallback "book" | **4** (2 corrupted data, 1 block-drawing, 1 Greek) |
| Collision groups | **523** (-1) |
| Books in collisions | **1053** (-8) |
| Max collision group | **3** (-5) |

### Egretta Garzetta collision group

**До:** все 8 книг → `/egretta-garzetta/book` (plus -2 through -8)

**После:** каждая книга получила уникальный slug:

| ID | Название | Slug |
|---|---|---|
| 25916 | Լիլի | `/garzetta-egretta/lili` |
| 26361 | Վաղուց մdelays | `/garzetta-egretta/vaghouts-meratsy` |
| 26694 | Նerker, ancyalyal, aparni | `/garzetta-egretta/nerka-antsyal-aparni` |
| 26826 | ՄՄ | `/garzetta-egretta/mm` |
| 26898 | Նamak nran | `/garzetta-egretta/namak-nran` |
| 28499 | Փapуk bardzeri vra | `/garzetta-egretta/papouk-bardzeri-vra` |
| 50416 | Նa | `/garzetta-egretta/na` |
| 50417 | Khosk anougheghnerin | `/garzetta-egretta/khosk-anougheghnerin` |

### Оставшиеся fallback "book" (не исправляемые)

| ID | Причина |
|---|---|
| 76748 | Block-drawing chars (▟▄▙ ▄ ▙) — не текст |
| 90167 | Corrupted data (U+FFFD replacement chars) |
| 98393 | Corrupted data (U+FFFD replacement chars) |
| 111443 | Greek (ΣΚΟΤΟΣ) — вне scope Armenian/Georgian |

## Миграция

Выполнена для DEV: ID 25916 (единственный реальный fallback "book"):
- Старый slug `/egretta-garzetta/book` → alias (is_canonical=0)
- Новый slug `/garzetta-egretta/lili` → canonical (is_canonical=1)
- Legacy `/book/25916` → 301 → `/books/garzetta-egretta/lili`
- Old alias `/books/egretta-garzetta/book` → 301 → `/books/garzetta-egretta/lili`
- Total routes: 122464 (+1 new canonical)

## Проверки

| Проверка | Результат |
|---|---|
| Unit tests (13 slug tests) | OK |
| SEO DB tests (5 tests) | OK |
| Python compile | OK |
| git diff --check | Clean |
| HTTP smoke DEV | 200 |
| Legacy redirect (/book/25916) | 301 → /books/garzetta-egretta/lili |
| Old alias (/books/egretta-garzetta/book) | 301 → /books/garzetta-egretta/lili |
| Production VPS2 | Not touched |
| Push | Not done |

## Регрессии

RU/UK/EN транслитерация не затронута. Все существующие тесты проходят. Коллизии не увеличились.
