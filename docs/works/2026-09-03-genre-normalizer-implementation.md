# 2026-09-03 Genre Normalizer Implementation

## Цель
Реализовать нормализацию жанров для новых книг перед импортом в Calibre:
- Flibusta codes → русские канонические названия
- Дедупликация с учётом регистра
- Интеграция в pipeline обработки книг

## Что сделано

### 1. Создан genre_normalizer.py (`/home/feninf/aubooks/genre_normalizer.py`)
- Загружает genre_mapping.tsv
- Применяет ТОЛЬКО high-confidence преобразования (428 маппингов)
- Case-insensitive lookup через `casefold()`
- Дедупликация: известные теги — по canonical case, неизвестные — без дедупликации
- CLI режим: `--dry`, `--validate`, `--stats`, `--file`, `--csv`

### 2. Интеграция в 1au-prepare_book.py (`/home/feninf/bin/1au-prepare_book.py`)
- Импорт GenreNormalizer с fallback если не загрузился
- Извлечение жанров из FB2 `<genre>` элементов
- Нормализация перед записью OPF
- Добавление `<dc:subject>` тегов в OPF (раньше было без тегов)
- Вывод маппингов и удалённых дублей в консоль

### 3. Тесты (`/home/feninf/calibre-web/tests/test_genre_normalizer.py`)
- 26 тестов, все проходят
- Покрытие: init, normalize, normalize_dry, stats, edge cases

## Изменённые файлы
- `/home/feninf/aubooks/genre_normalizer.py` — новый модуль
- `/home/feninf/bin/1au-prepare_book.py` — интеграция нормализации
- `/home/feninf/calibre-web/tests/test_genre_normalizer.py` — тесты

## Проверка
- Smoke test: `calibredb add` с нормализованными тегами → `Боевик, Фэнтези, детектив` в metadata.db
- Case-insensitive collisions: 0 в mapping
- Всё nochmal 26/26 тестов OK

## Известные ограничения
- Нормализация работает ТОЛЬКО для FB2 (извлекает `<genre>` элементы)
- Для EPUB/other форматов теги не извлекаются (нужна отдельная работа)
- Medium/low confidence теги проходят без изменений (по設計)

## Следующие шаги
- Добавить извлечение тегов из EPUB (`<dc:subject>`)
- Добавить поддержку plain text формата (без жанров)
- Тестирование на реальных книгах из pipeline
