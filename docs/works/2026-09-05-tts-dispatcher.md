# TTS Dispatcher: HTTP endpoint для запуска вне mount namespace

## Цель
Сделать цепочку Calibre-Web DEV → HTTP POST → dispatcher → aubook-remote.sh, работая вне mount namespace Calibre-Web.

## Что было изучено
1. Calibre-Web DEV работает в isolated mount namespace с замаскированной TTS-библиотекой
2. Прямой subprocess из Calibre-Web не может вызвать aubook-remote.sh (библиотека недоступна внутри namespace)
3. HTTP-сервер на localhost работает через namespace boundaries
4. Python stdlib http.server + urllib.request — достаточно для минимального dispatcher

## Какие файлы добавлены
- `/home/feninf/bin/tts-dispatcher.py` — HTTP dispatcher (Python stdlib)
- `/home/feninf/.config/systemd/user/tts-dispatcher.service` — systemd user service
- `tests/test_tts_dispatcher.py` — 21 unit test для dispatcher
- `tests/test_aubooks_tts_transport.py` — 8 unit tests для transport

## Какие файлы изменены
- `cps/aubooks_tts.py` — HTTP вместо прямого subprocess
- `.config/systemd/user/calibre-web-dev.service` — добавлен TTS_DISPATCH_URL env

## Что именно изменено

### tts-dispatcher.py
- Слушает 127.0.0.1:18900
- POST /queue с {"book_id": N}
- Валидация: integer > 0, не bool
- Проверка audio.db: queued/processing/ready → 409 Conflict
- Вызов aubook-remote.sh start-book-id <id> 1 publish (shell=False)
- JSON ответ: {"ok": true, "book_id": N, "job_id": "..."} или {"ok": false, "code": N, "error": "..."}

### cps/aubooks_tts.py
- queue_book() теперь HTTP POST к TTS_DISPATCH_URL/queue
- TTS_DISPATCH_URL из env, default http://127.0.0.1:18900
- urllib.request (stdlib), не requests
- QueueResult API сохранён

### calibre-web-dev.service
- Добавлено Environment=TTS_DISPATCH_URL=http://127.0.0.1:18900

## Тесты
- 29/29 unit tests pass (dispatcher: 21, transport: 8)
- Smoke test: curl POST /queue → все validation/corner cases работают
- Smoke test: book_id=999999 → {"ok":false, "code":4, "error":"Book not found in the TTS library."}
- Запрос обработан ВНЕ mount namespace (pipeline вызван из tts-dispatcher.py)

## Статус сервиса
- tts-dispatcher.service: active (running)
- Bind: 127.0.0.1:18900
- opencode-calibre-web.service: active (running, не тронут)
- calibre-web-dev.service: active (running, daemon-reload без restart)

## Commit hashes
- calibre-web (aubooks): ba4e40df
- bin: 4649e7b

## Известные ограничения
- В production (VPS2→VPS1) потребуется добавить аутентификацию (Bearer token)
- Calibre-Web DEV service не перезапускался; env применится при следующем restart
- Timeout test (60s) не запускается в unit tests из-за длительности
