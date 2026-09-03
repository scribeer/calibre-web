# 2026-09-03: Calibre Tag Normalization Architecture

## Текущий pipeline добавления книги

```
Исходный файл (FB2/EPUB)
    ↓
1au-prepare_book.py → cleaned TXT + OPF + JPG
    ↓
tts_processor.py → M4B (для аудио)
    ↓
calibredb add --with-library ~/aubooks/library
    ↓
metadata.db (Calibre)
    ↓
export-metadata-sync.sh → rclone → VPS2
    ↓
Calibre-Web (aubooks_genres.py группирует по 21 категории)
```

**Ключевые точки:**
- `calibredb add` — основной способ добавления книг
- Flibusta daily ingest (`02_flibusta_daily_ingest.sh`) — **DISABLED** (не адаптирован к текущей схеме)
- Ручной `calibredb add` — активен
- Телефонный синхронизирующий скрипт (`aubook-sync.sh`) — активен

## Где сейчас формируются tags

**При добавлении через `calibredb add`:**
- Книга может иметь теги из OPF-файла (если он есть)
- Или теги берутся из метаданных формата (FB2 `<genre>`, EPUB DC subject)
- Формат FB2: `<genre>det_action</genre>` — технический код Flibusta
- Формат EPUB: `<dc:subject>sf_fantasy</dc:subject>` — технический код

**Проблема:** raw tags из Flibusta попадают в metadata.db как есть:
- `det_action` вместо `Боевик`
- `sf_space` вместо `Космическая фантастика`
- Всего 273 технических кода из 1,316 уникальных тегов

## Текущее состояние metadata.db

| Метрика | Значение |
|---|---|
| Книг | 122,463 |
| Уникальных тегов | 1,316 |
| Tag assignments | 207,612 |
| Среднее тегов на книгу | 1.71 |
| Книг без тегов | 1,366 (1.1%) |
| Flibusta кодов как тегов | 273 |
| Русских тегов | ~850+ |
| Смешанных (лат+кирил) | 8 |
| Тегов с underscore (lowercase) | 273 |

**Важно:** Книги имеют ИЛИ код ИЛИ русский label, но **никогда оба одновременно**. Например, 495 книг с `det_action` и 545 с `Боевик`, но **0 книг с обоими**.

## Топ-10 тегов по количеству книг

| Тег | Кол-во |
|---|---|
| `network_literature` | 7,822 |
| `sf_fantasy` | 7,360 |
| `popadancy` | 6,741 |
| `Современная проза` | 5,357 |
| `Боевая фантастика` | 5,049 |
| `Любовное фэнтези` | 4,930 |
| `prose_contemporary` | 4,889 |
| `nonf_biography` | 4,513 |
| `love_contemporary` | 4,511 |
| `love_sf` | 4,422 |

## calibredb возможности

| Возможность | Доступна |
|---|---|
| `calibredb set_metadata <id> --field tags:tag1,tag2` | Да |
| `calibredb set_metadata --search="..." --field tags:...` | Да (массово) |
| `calibredb add -T "tag1,tag2"` | Да (при импорте) |
| `calibredb list --for-machine` | Да (JSON) |
| `--library-path` | Да |
| Dry-run | Нет (но можно preview через list) |
| OPF как промежуточный формат | Да (set_metadata --from-opf) |

**Версия:** calibre 9.13

## Рекомендация: точка нормализации

### Варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| A. До `calibredb add` | Чистые данные с первого дня | Нужно менять pipeline |
| B. После через `set_metadata` | Не меняет pipeline | Двойная работа, legacy |
| C. Calibre Python API | Гибкость | Не установлен в venv |
| D. Прямое SQL | Быстро | Рискованно, ломает Calibre |

### Рекомендация: **Вариант A + B**

**A ( primary):** Нормализация до `calibredb add` — через предобработку тегов в pipeline.
**B (fallback):** Массовая миграция существующих 122k книг через `calibredb set_metadata`.

**Порядок:**
1. Создать единый mapping file
2. Написать нормализующую функцию
3. Встроить в pipeline перед `calibredb add`
4. Запустить массовую миграцию существующих книг
5. Упростить `aubooks_genres.py` (убрать双头 lookup)

## Схема mapping файла

**Формат:** TSV (Tab-Separated Values) — один источник истины.

```
# raw_tag	canonical_russian_label	parent_category
det_action	Боевик	Детективы и триллеры
det_classic	Классический детектив	Детективы и триллеры
sf_space	Космическая фантастика	Фантастика
love_contemporary	Современные любовные романы	Любовные романы
network_literature	Сетевая литература	Прочее
popadancy	Попаданцы	Фантастика
```

**Преимущества TSV:**
- Парсится одной строкой Python
- Комментарии через `#`
- Легко читать/редактировать вручную
- Единый файл для migration + runtime + import

**Хранение:** `/home/feninf/aubooks/files/genre_mapping.tsv`

Этот же файл заменяет:
- `flibusta_genres.txt` (273 строки raw→label)
- `_CATEGORY_RANGES` в `aubooks_genres.py` (21 категория)
- Дублированный `flibusta_genres.txt` в `cps/data/`

**Структура TSV:**
```
# raw_tag	canonical_label	parent_category
# Группировка по категориям определяется parent_category
# Неизвестные теги проходят как есть (не в mapping)
```

## Правила для множественных тегов

### Нормализация (при импорте)

1. Каждый raw tag проверяется по mapping
2. Если найден → заменяется на canonical Russian label
3. Если не найден → оставляется как есть (non-genre tag)
4. Дубликаты после нормализации удаляются
5. Теги, не являющиеся жанрами (серия, язык, формат), не трогаются

### Примеры

| Raw tags книги | После нормализации |
|---|---|
| `det_action` | `Боевик` |
| `det_action, sf_space` | `Боевик`, `Космическая фантастика` |
| `Боевик` (уже русский) | `Боевик` (без изменений) |
| `det_action, Боевик` | `Боевик` (дубль удалён) |
| `det_action,read,2024` | `Боевик`, `read`, `2024` (non-genre сохранены) |
| `unknown_new_genre` | `unknown_new_genre` (без изменений) |

### Что НЕ удалять

- Тематические теги (`read`, `favorite`, `to-read`)
- Годы (`2024`)
- Языковые теги
- Серийные теги
- Пользовательские теги
- Всё, чего нет в mapping → оставить как есть

## План миграции существующих 122k книг

### Phase 0: Подготовка

```bash
# 1. Бэкап metadata.db
cp ~/aubooks/library/metadata.db ~/aubooks/library/metadata.db.bak.$(date +%Y%m%d)

# 2. Проверка целостности
calibredb check_library --with-library ~/aubooks/library

# 3. Экспорт текущих тегов для анализа
calibredb list --with-library ~/aubooks/library --fields=tags --for-machine > /tmp/tags_before.json
```

### Phase 1: Dry-run (по тегам)

```python
# Скрипт: analyze_changes.py
# Для каждого raw_tag в mapping:
#   - сколько книг имеет этот тег
#   - какой canonical label будет назначен
#   - есть ли уже canonical label в библиотеке
# Вывод: статистика planned changes
```

### Phase 2: Миграция (по тегам, batch)

```python
# Скрипт: migrate_tags.py
# Алгоритм:
# 1. Для каждого (raw_tag, canonical_label) в mapping:
#    a. calibredb list --search="tags:raw_tag" --fields=id,tags
#    b. Для каждой книги: новый tags = (tags - raw_tag) + canonical_label
#    c. calibredb set_metadata <id> --field tags:new_tags
#    d. Логирование изменений
#    e. Пауза между batches (100 книг)
# 2. Проверка после каждого batch
```

### Phase 3: Проверка

```bash
# Сравнение до/после
calibredb list --with-library ~/aubooks/library --fields=tags --for-machine > /tmp/tags_after.json

# Проверка:
# - количество книг не изменилось
# - количество уникальных тегов уменьшилось (codes → labels)
# - все canonical labels присутствуют
# - не-genre теги сохранены
```

### Rollback Strategy

```bash
# Если что-то пошло не так:
cp ~/aubooks/library/metadata.db.bak.YYYYMMDD ~/aubooks/library/metadata.db
# Calibre перечитает при следующем обращении
```

## Влияние на Calibre-Web

### Что изменится при смене tag IDs

| Компонент | Зависимость | Влияние |
|---|---|---|
| `cps/aubooks_genres.py` | `genre_for_tag()` ищет по name, не по id | **Не сломается** — lookup по name |
| `flibusta_genres.txt` | Mapping code→label | **Упростится** — заменится на TSV |
| Sidebar genre tree | `tag_ids` из БД | **ID изменятся** — это нормально |
| Parent category routes | `/category/<slug>` | **Не сломаются** — slug определяется из name |
| Child genre routes | `/category/stored/<tag_id>` | **ID изменятся** — URL изменятся |
| SEO URLs категорий | `/category/<slug>` | **Не сломаются** |
| Detail genre links | `category_by_slug` + `tag_id` | **tag_id изменится** — но slug stable |
| `MAPPED_TAG_NAMES` | Все code + label | **Уменьшится** — только labels |

### Ключевой момент

**Calibre-Web ищет теги по NAME, не по ID.** Поэтому:
- Смена tag IDs **не ломает** логику группировки
- Изменятся только URL вида `/category/stored/<tag_id>` (нужно обновить)
- Sidebar будет работать корректно

### Что нужно будет обновить после миграции

1. `flibusta_genres.txt` → заменить на `genre_mapping.tsv`
2. `aubooks_genres.py` → упростить (убрать双头 lookup)
3. Все existing `/category/stored/<tag_id>` URL в sidebar/detail → пересчитать
4. SEO sitemap (если есть) → обновить

## Риски

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| Потеря тегов при миграции | Низкая | Высокое | Бэкап + dry-run |
| Некорректный mapping | Средняя | Среднее | Валидация + проверка |
| Сломанные URL | Высокое | Низкое | URL содержат tag_id, пересчитаются |
| Потеря не-genre тегов | Низкая | Среднее | Фильтрация по mapping |
| Дубли после нормализации | Средняя | Низкое | Deduplication logic |

## Порядок следующих задач

1. **Создать `genre_mapping.tsv`** — единый source of truth
2. **Написать `normalize_tags.py`** — функция нормализации
3. **Встроить в pipeline** — перед `calibredb add` в `1au-prepare_book.py`
4. **Написать `migrate_tags.py`** — массовая миграция существующих книг
5. **Запустить dry-run** — проверить статистику
6. **Запустить миграцию** — batch по 100 книг
7. **Обновить Calibre-Web** — упростить `aubooks_genres.py`
8. **Обновить URL** — пересчитать child genre URLs
9. **Проверить** — все 21 parent category, sidebar, detail
10. **Deploy** — синхронизировать на VPS2
