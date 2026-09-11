# Видимые состояния загрузки заданий озвучивания
## Цель
Сделать AU-Books `/tasks` устойчивой к ошибкам AJAX и JavaScript: пользователь должен видеть начальную загрузку или понятную ошибку вместо необъяснимо пустой таблицы.
## Что было изучено
- `cps/themes/aubooks/templates/tasks.html`: polling `GET /ajax/tts-jobs`, преобразование ответа и `bootstrapTable('load', rows)`.
- `cps/tasks_status.py` и `cps/aubooks_audio.py`: read-only JSON backend и выборка активных/завершённых заданий.
- `tests/test_aubooks_audio.py`: проверки шаблона, JSON endpoint, безопасных полей и отсутствия пользовательской отмены.
## Изменённые файлы
- `cps/themes/aubooks/templates/tasks.html`.
- `tests/test_aubooks_audio.py`.
- `docs/works/2026-09-11-audiobook-task-loading-errors.md`.
## Изменения
- Перед таблицей добавлен доступный live-status с начальным текстом «Загрузка...»; таблица получает `aria-busy="true"`.
- У `$.ajax` добавлен `error` callback с сообщением «Не удалось загрузить задания».
- Проверка типа JSON, преобразование строк и `bootstrapTable('load', rows)` защищены `try/catch`; ошибка отображается пользователю и пишется в browser console.
- Инициализация Bootstrap Table также защищена `try/catch`.
- Успешный непустой ответ скрывает статус, успешный пустой ответ показывает «Заданий нет».
- Polling каждые 5 секунд сохранён и повторяет загрузку после предыдущей ошибки.
- Backend API, dispatcher, `audio.db`, TTS jobs и cancel UI не изменялись.
## Тесты
- `.venv/bin/python -m pytest tests/test_aubooks_audio.py` — 71 passed.
- `git diff --check` — без ошибок.
- Проверки шаблона подтверждают loading/error markup, AJAX error callback, обработку render exception, продолжение polling и отсутствие cancel-кнопки.
- Существующие JSON endpoint tests прошли без изменений backend-контракта.
## Известные ограничения
- Автоматический тест проверяет обязательную разметку и JavaScript-контракт статически; headless browser runtime в окружении отсутствует.
- Журнал создан в том же коммите, что и изменения; hash см. `git log` (commit message `fix: show audiobook task loading errors`).
## Git
Изменения подготовлены в ветке `aubooks`. Push, рестарты сервисов и deploy не выполнялись.
