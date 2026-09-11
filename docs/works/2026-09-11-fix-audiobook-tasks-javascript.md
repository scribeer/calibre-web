# Исправление JavaScript на странице заданий озвучивания
## Цель
Исправить пустую AU-Books `/tasks`, сохранив состояния загрузки и ошибок, polling и текущий backend API.
## Что было изучено
- `cps/themes/aubooks/templates/tasks.html`: inline polling script и вызовы Bootstrap Table.
- `cps/themes/aubooks/templates/layout.html` и `cps/themes/standard/templates/layout.html`: наследование `block js` и порядок подключения jQuery/scripts.
- Фактически отданный authenticated HTML `/tasks` и извлечённый из него inline JavaScript.
- `tests/test_aubooks_audio.py`: UI, JSON endpoint и no-cancel проверки.
## Симптом и причина
Backend `/ajax/tts-jobs` исправно возвращал задания, но `/tasks` оставалась пустой. В конце inline script внутренний `$(function() { ... })` и внешний IIFE закрывались одной конструкцией `})();`; браузер отклонял весь script с `SyntaxError: Unexpected end of input`, поэтому polling не запускался.
## Browser diagnostics
Временный diagnostic block подтвердил в реальном браузере: AJAX success 200, 11 строк, Bootstrap Table доступен и инициализирован, `load` успешен, tbody содержит 11 строк, исключений нет; job 722 отображается как `ready` с кнопкой «Скачать аудиокнигу». После подтверждения весь diagnostic markup и instrumentation удалены.
## Изменения
- Финал inline script теперь отдельно закрывает ready-handler через `});` и внешний IIFE через `})();`.
- Сохранены «Загрузка...», «Не удалось загрузить задания», «Заданий нет», AJAX error callback, обработка render exception и polling каждые 5 секунд.
- Добавлен regression test на правильное закрытие script и отсутствие временной диагностики.
- Backend/API, `audio.db`, TTS jobs и dispatcher не изменялись.
## Проверки
- `.venv/bin/python -m pytest tests/test_aubooks_audio.py` — 72 passed.
- `git diff --check` — без ошибок.
- Exact inline JavaScript из live authenticated `/tasks` после перезапуска DEV service проверен через `node --check` — OK.
- Live `/tasks` и `/ajax/tts-jobs` вернули HTTP 200; job 722 присутствует в JSON как `ready`; diagnostic block в live HTML отсутствует.
## Известные ограничения
- Headless browser automation в окружении отсутствует; итоговая browser-проверка выполнена пользователем, а live HTML/JS проверен отдельными authenticated GET и Node parser.
- Журнал создаётся в том же коммите; hash см. `git log` по сообщению `fix: run audiobook tasks polling script`.
## Git
Изменения подготовлены в ветке `aubooks`. Push и deploy не выполнялись. Перезапускается только `calibre-web-dev.service`, чтобы сбросить template cache.
