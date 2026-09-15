# Производительность поиска в AU-Books

## Статус
IMPLEMENTED IN DEV
PRODUCTION: PENDING

## Приоритет
Высокий — performance bug.

## Проблема
Поиск на AU-Books выполняется очень долго.

## Цель
Определить root cause медленного поиска и реализовать минимальное исправление, сохраняющее совместимость с upstream Calibre-Web.

## Этапы диагностики

### 1. Маршруты и обработчики
- Найти все route/handler поиска (`/search`, `/advsearch`, ajax search).
- Проследить путь от формы поиска до SQL и рендера результата.

### 2. Реальные запросы
- Выполнить на DEV запросы разных типов: точное название, часть названия, автор, редкое слово, пустой результат.
- Замерить время и размер ответа.

### 3. SQL-анализ
- Найти основной SQL, который выполняется при поиске.
- Проверить LIKE/ILIKE, `%term%`, JOIN, DISTINCT, GROUP BY, ORDER BY, COUNT, подзапросы.
- Проверить отсутствие LIMIT/OFFSET, `.all()` на больших выборках, Python-фильтрацию после SQL.
- Проверить N+1 queries и eager/lazy loading связанных author/series/tags.

### 4. Pagination
- Проверить, использует ли поиск server-side pagination.
- Определить, не загружает ли backend все совпадения перед показом первой страницы.

### 5. Indexes
- Показать существующие SQLite indexes для таблиц, участвующих в поиске.
- Получить `EXPLAIN QUERY PLAN` для медленных запросов.
- Выявить FULL TABLE SCAN и TEMP B-TREE.

### 6. Разделение времени
- Определить вклад SQL, Python processing и template rendering.

### 7. Сравнение с upstream
- Сравнить search code с upstream Calibre-Web.
- Определить, является ли медленность upstream-проблемой, AU-Books-изменением или комбинацией.

## Связанные файлы
- `cps/search.py` — основная логика поиска.
- `cps/web.py` — маршруты поиска.
- `cps/db.py` — модели Book, Authors, Tags, Series, Languages, Publishers.
- `cps/themes/aubooks/templates/` — шаблоны результатов поиска.
- `metadata.db` — таблицы и indexes Calibre.

## Риски
- AU-Books FTS не добавляется в canonical Calibre `metadata.db`: индекс строится только в приватном export artifact.
- Изменения в upstream search code усложняют будущие обновления.
- FTS token/phrase semantics не поддерживает произвольный substring по середине слова как legacy `%term%`.
- VPS2 продолжает использовать legacy search до отдельного production deployment consumer-кода и FTS metadata artifact.
