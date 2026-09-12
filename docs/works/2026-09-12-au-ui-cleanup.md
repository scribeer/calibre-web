# Очистка интерфейса AU-Books
## Цель
Упростить detail page, полку и sidebar темы AU-Books, улучшить контраст вторичного текста и убрать пользовательские входы во встроенный reader без изменения Standard theme и backend.
## Что изучено
- AU-шаблоны detail, layout, index и list.
- Fallback полки на `themes/standard/templates/shelf.html`.
- Палитры и Bootstrap overrides в `aubooks.css`.
- Прямые reader routes `/read/...` и `/show/...`.
- Существующие AU-тесты permissions, TTS, sidebar и genres.
## Изменённые файлы
- `cps/themes/aubooks/templates/detail.html`.
- `cps/themes/aubooks/templates/layout.html`.
- `cps/static/css/aubooks.css`.
- `tests/test_aubooks_theme_templates.py`.
## Что изменено
- Download и audio/TTS actions объединены в один flex action-row с естественным переносом на узких экранах.
- Удалены только AU entry points `Read in Browser`; Standard template и прямые reader endpoints не изменены.
- На shelf явно включено отображение существующей cover-разметки, а названия книг используют общую AU link palette с заметными hover/focus states.
- Удалён sidebar header «Категории», ссылка «Все категории» переименована в «Все жанры»; genre tree сохранён.
- Вторичный текст dark theme осветлён, а disabled text оставлен отдельным более тусклым цветом.
- Добавлены scoped rules для Bootstrap `.text-muted`, `.help-block` и `.form-text`.
## Полка и обложки
AU не имеет отдельного `shelf.html` и использует Standard fallback, который уже содержит `image.book_cover` и fallback cover endpoint. В текущем DEV theme не найдено правила, удаляющего shelf cover markup. Добавлен узкий AU selector, явно показывающий cover. Единственная DEV shelf приватная и для guest перенаправляет на главную; её настройки и пользователи не менялись. Если на production обложки останутся скрыты, нужно отдельно проверить внешний nginx/injected CSS.
## Порядок sidebar
- Блок полок (`Shelves` header + shelf links + `Create a Shelf`) перемещён выше genre tree в `layout.html`.
- Старый порядок: жанры → полки. Новый порядок: полки → жанры.
- URL, permissions и логика полок не изменены.
## Тесты
- `pytest -q tests/test_aubooks_theme_templates.py`: 9 passed ( добавлены 2 regression tests для порядка sidebar).
- `pytest -q tests/test_aubooks_*.py`: 335 passed, 248 subtests passed.
- `pytest -q tests --ignore=tests/test_cmd_start_book_id.py`: 448 passed, 248 subtests passed.
- `py_compile tests/test_aubooks_theme_templates.py`: успешно.
- DEV HTTP: home, detail, login, search, tasks redirect и shelf access проверены без POST и записей в БД.
## Известные ограничения
- Прямые reader endpoints технически доступны; скрыты только AU UI entry points.
- Authenticated visual shelf check не выполнялся, потому что существующая shelf приватная; cover markup и active AU CSS проверены тестами и source inspection.
- TTS permission, polling и backend не менялись.
## Commit
- Commit hash: текущий commit с этим отчётом; точный hash указан в итоговом отчёте задачи.
