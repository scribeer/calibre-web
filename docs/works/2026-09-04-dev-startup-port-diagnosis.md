# Диагностика «зависания» DEV Calibre-Web

## Цель

Выяснить, почему DEV Calibre-Web «перестал запускаться» после изменений generate-audio / TTS integration.

## Что было изучено

- git diff, git status, git log — последние коммиты и незакоммиченные изменения
- `cps/web.py` — дифф показал рефакторинг `generate_audio` (замена inline вызовов на `aubooks_tts.queue_book`)
- `cps/aubooks_tts.py` — новый модуль, чистый, без side effects при import
- `cps/aubooks_audio.py` — read-only adapter для audio.db, не вызывается при startup
- `cps/cli.py` — разбор аргументов командной строки
- `cps/server.py` — `WebServer.start()`, `_start_gevent()`
- `cps/main.py` — цепочка import и `web_server.start()`
- PID текущего процесса и его file descriptors
- Содержимое settings database (`8084`, `app.db`)

## Что выяснено

**Зависания startup НЕТ.** Сервер запускается корректно.

### Корень проблемы

Флаг `-p` в `cps.py` — это **путь к файлу settings database**, а **не номер порта**.

Коменд `cps.py -i 127.0.0.1 -p 8084 -m` означает:
- `-i 127.0.0.1` — IP адрес для прослушивания
- `-p 8084` — файл settings database = `8084` (относительный путь)
- `-m` — memory backend для rate limiter

Файл `8084` — это SQLite база данных настроек, созданная при первом запуске. В ней:
```
config_port = 8083
```

Сервер слушает на **8083**, а не 8084. `curl http://127.0.0.1:8084/` получает connection refused, потому что на 8084 ничего не слушает.

### Проверка работоспособности

```
ss -tlnp → LISTEN 127.0.0.1:8083
curl http://127.0.0.1:8083/ → HTTP 302 (редирект на login)
```

Сервер полностью работоспособен.

## Файлы

- Состоящие в working tree: не требуют изменений
- `cps/aubooks_tts.py` — новый модуль, безопасный
- `cps/web.py` — рефакторинг `generate_audio`, не влияет на startup
- `8084` — settings database с портом 8083

## Исправление

Не требуется. Нужно либо:
1. Использовать `http://127.0.0.1:8083/` вместо 8084
2. Либо изменить порт в settings database: `UPDATE settings SET config_port = 8084 WHERE id = 1`
3. Либо убрать файл `8084` и использовать стандартный `app.db`
