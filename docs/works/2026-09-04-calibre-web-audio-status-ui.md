# Интеграция статуса аудиокниг в Calibre-Web

## Цель
Добавить read-only отображение статуса аудиокниг из `audio.db` на странице деталей книги в Calibre-Web (AU-Books тема).

## Что было изучено

- Структура Calibre-Web: `render_book_detail()` в `cps/web.py:1730`, шаблоны AU-Books, наследование тем.
- Детальная страница: `cps/themes/aubooks/templates/detail.html` расширяет `_themes/standard/detail.html`, переопределяет блоки `body`, `header`, `js`, `book_tags`.
- Кнопки действий (скачать, отправить, читать) размещены внутри `<div class="btn-toolbar">` → `<div class="btn-group">` на строках 178-324 шаблона.
- Структура аудио-кнопок: существующая кнопка "Listen in Browser" показывает форматы из `entry.audio_entries` (EPUB/MOBI и т.д.), но это файловые форматы, не статус из audio.db.

## Изменённые файлы

### Новые файлы
- `cps/aubooks_audio.py` — read-only адаптер для `audio.db`
- `tests/test_aubooks_audio.py` — 17 тестов

### Изменённые файлы
- `cps/web.py` — добавлена интеграция аудио-статуса в `render_book_detail()` (строки 1768-1790)
- `cps/themes/aubooks/templates/detail.html` — добавлен блок с кнопками статуса (строки 282-322)

## Что именно изменено

### cps/aubooks_audio.py (новый файл)
- `get_audio_status(book_id)` → `'not_available' | 'queued' | 'processing' | 'ready' | 'failed'`
- `get_audio_record(book_id)` → `dict | None`
- Читает `audio.db` в read-only режиме (`file:path?mode=ro`)
- Путь к БД: env `AUBOOKS_AUDIO_DB` или `/home/feninf/aubooks/audio.db`
- Безопасный fallback на `'not_available'` при любой ошибке

### cps/web.py (render_book_detail)
- Определяет `aubooks_audio_status` и `aubooks_audio_record` только для темы `aubooks`
- Передаёт переменные в шаблон через `render_title_template()`

### cps/themes/aubooks/templates/detail.html
Добавлен блок кнопок аудио-статуса после существующих кнопок скачивания/чтения:

| Статус | CSS класс | Текст кнопки | Disabled |
|--------|-----------|--------------|----------|
| `not_available` | `btn-default` | "Generate audio" | нет |
| `queued` | `btn-default` | "In queue" | да |
| `processing` | `btn-default` | "Generating audio…" | да |
| `ready` | `btn-success` | "Listen" | нет |
| `failed` | `btn-warning` | "Retry audio" | нет |

Каждая кнопка содержит:
- `data-book-id` — для будущей JS-интеграции
- `data-audio-status` — текущий статус
- `aria-disabled` — корректное состояние для screen readers
- `aria-label` на контейнере `btn-group`

## Тесты

17 тестов в `tests/test_aubooks_audio.py`:

**TestAudioAdapter (10):**
- `test_missing_record_returns_not_available` — нет записи → not_available
- `test_queued_status` — queued статус
- `test_processing_status` — processing статус
- `test_ready_status` — ready статус
- `test_failed_status` — failed статус
- `test_missing_db_returns_not_available` — нет файла БД → not_available
- `test_db_read_error_returns_not_available` — БД без таблицы audio → not_available
- `test_get_audio_record_returns_dict` — возвращает dict с правильными полями
- `test_other_book_id_not_affected` — другие book_id не затронуты
- `test_opendrive_path_not_in_html` — opendrive_path не утекает в HTML

**TestAudioStatusTemplate (4):**
- `test_template_has_audio_button` — шаблон содержит `aubooks_audio_status`
- `test_template_has_all_states` — все 5 состояний присутствуют
- `test_template_no_href_hash` — нет `<a href="#">`
- `test_template_uses_buttons` — используются `<button>`, не `<a>`

**TestAudioAdapterAccessibility (3):**
- `test_buttons_have_aria_disabled` — disabled кнопки имеют `aria-disabled`
- `test_buttons_have_aria_labels` — btn-group имеет `aria-label`
- `test_buttons_have_data_book_id` — кнопки имеют `data-book-id`

Все 46 тестов (17 audio + 29 genres) пройдены.

## DEV верификация

- Сервер перезапущен на `127.0.0.1:8084`
- Книга `/book/1` ("Дело о Медвежьем посохе"): кнопка "Generate audio" с `data-audio-status="not_available"` — корректно
- `audio.db` пуста (0 записей) → все книги показывают `not_available`

## Известные ограничения

- Кнопки пока статичные (без JS-обработчика). Будущая задача: добавить JS для отправки запросов на TTS-пайплайн.
- opendrive_path доступен в `aubooks_audio_record`, но пока не отображается в шаблоне (намеренно).
- Если `audio.db` не существует или недоступна, все книги показывают `not_available` без ошибок.
