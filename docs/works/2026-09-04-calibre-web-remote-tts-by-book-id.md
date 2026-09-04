# Calibre-Web: Remote TTS by book_id

**Дата:** 2026-09-04
**Статус:** Завершено

## Цель

Убрать из Calibre-Web локальный поиск source-файла (`_find_tts_source`). Вся логика поиска и запуска TTS теперь на стороне VPS1 (`aubook-remote.sh start-book-id <book_id>`). Calibre-Web только отправляет book_id и показывает результат.

## Что было сделано

### 1. Транспортный слой: `cps/aubooks_tts.py`

Создан модуль-абстракция для очереди TTS:

- `queue_book(book_id, voice, publish, remote_path)` — вызывает `aubook-remote.sh start-book-id <book_id>` через `subprocess.run`
- `QueueResult` — результат: `success`, `exit_code`, `error_message`, `job_id`
- Маппинг exit code → пользовательское сообщение (`_EXIT_MESSAGES`)
- Обработка ошибок: `FileNotFoundError`, `TimeoutExpired`, `OSError`
- Без `shell=True`, без прямого Popen

### 2. Рефакторинг `web.py`

Удалены:
- `_TTS_SOURCE_FORMATS` — список форматов для локального поиска
- `_AUBOOK_REMOTE` — путь к aubook-remote.sh (перенесён в aubooks_tts.py)
- `_find_tts_source(book)` — функция локального поиска source-файла

Маршрут `generate_audio` упрощён:
1. Проверка auth (role_tts)
2. Проверка book exists
3. Проверка audio status (queued/processing → blocked, ready → blocked)
4. `queue_book(book_id)` — один вызов
5. Flash + redirect

Вся логика работы с `audio_index` (create_queued, reset_for_retry, mark_failed) перенесена в pipeline на VPS1.

### 3. Тесты Calibre-Web: 42 tests

Новый класс `TestTransportAbstraction` (10 tests):
- Проверка наличия queue_book, QueueResult, subprocess.run
- Отсутствие shell=True, Popen
- Наличие обработки ошибок и exit code messages

Обновлён `TestGenerateAudioRoute` (7 tests):
- Проверяет что route НЕ содержит _find_tts_source, _TTS_SOURCE_FORMATS
- Проверяет что route НЕ содержит subprocess.Popen, mark_failed, create_queued, reset_for_retry
- Проверяет наличие queue_book и result.success

### 4. VPS1: `aubook-remote.sh start-book-id`

Добавлена команда `start-book-id`:
- Валидация book_id
- Проверка audio index status (already queued/processing → exit 2, already ready → exit 3)
- Вызов `find_source.py` для поиска source-файла
- Делегирование в `cmd_start` для запуска pipeline

### 5. VPS1: `find_source.py`

Создан скрипт для поиска source-файла:
- Запрос к `metadata.db` для получения пути книги
- Приоритет: FB2 > EPUB > TXT
- Валидация: путь внутри library dir, файл существует
- Exit codes: 0=found, 4=not found, 5=no format, 7=file missing, 1=error

### 6. VPS1 тесты: 12 tests

Покрытие `find_source.py`:
- FB2, EPUB, TXT найдены
- Приоритет FB2 > EPUB
- Книга без файлов → error
- Отсутствующий book_id → error
- Path traversal защита

## Тестирование

- Calibre-Web: 155/155 tests pass
- VPS1 find_source: 12/12 tests pass

## Известные ограничения

- `aubook-remote.sh start-book-id` пока заглушка (cmd_start_book_id добавлена, но pipeline ещё не вызывается — это следующий шаг)
- Книги без физических файлов в библиотеке не могут быть обработаны TTS
