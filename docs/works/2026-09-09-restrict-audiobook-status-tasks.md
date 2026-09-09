# Ограничение доступа к статусам озвучивания
## Цель
Закрыть раскрытие скрытых книг и внутренних ошибок через TTS status endpoints, а также согласовать действия detail page с правами пользователя.
## Что изучено
- Проверка доступности книги на detail page через `CalibreDB.get_filtered_book()` и `common_filters()`.
- Права запуска TTS через `current_user.role_tts()` и обязательную аутентификацию.
- Права скачивания через `current_user.role_download()`.
- Формирование TTS controls в AU-Books detail template.
## Изменённые файлы
- `cps/web.py`.
- `cps/tasks_status.py`.
- `cps/themes/aubooks/templates/detail.html`.
- `cps/themes/aubooks/templates/tasks.html`.
- `tests/test_aubooks_audio.py`.
- `docs/works/2026-09-09-restrict-audiobook-status-tasks.md`.
## Что изменено
- `/ajax/audio-status/<book_id>` возвращает 404 для недоступной книги.
- `generate_url` выдаётся только аутентифицированному пользователю с TTS permission.
- `download_url` выдаётся только пользователю с download permission.
- `/ajax/tts-jobs` применяет canonical catalogue filters одним batch query и исключает отсутствующие книги.
- Raw `audio.db.error` заменён безопасным сообщением «Ошибка генерации аудиокниги».
- Detail polling создаёт generate/retry controls только при наличии `generate_url` от сервера.
- Первоначальные server-rendered controls используют те же проверки прав.
## Тесты
- `python3 -m unittest tests.test_aubooks_audio -v` — 62 tests passed.
- `python3 -m unittest tests.test_aubooks_opendrive_download -v` — 16 tests passed.
- `python3 -m py_compile cps/aubooks_audio.py cps/tasks_status.py cps/web.py`.
- DEV-проверка `/ajax/tts-jobs`, `/ajax/audio-status/10`, anonymous status и 404 для отсутствующей книги.
## Известные ограничения
- Audio download route не изменялся по условиям задачи; endpoint скрывает ссылку согласно download permission.
- Числовой прогресс отсутствует в TTS pipeline и не добавлялся.
## Commit
- Отдельный commit: `fix: restrict audiobook status and task visibility`.
