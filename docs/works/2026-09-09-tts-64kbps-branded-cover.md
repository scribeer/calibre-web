# TTS 64 kbps и брендированная обложка
## Цель
Повысить качество новых TTS-аудиокниг до AAC 64 kbps и добавлять логотип AU-Books снизу обложки перед встраиванием в M4B, не изменяя готовые аудиокниги и production.
## Что было изучено
Проверена цепочка `tts-dispatcher.py` → `aubook-remote.sh` → `1au-prepare_book.py` → `tts_processor.py` → `aubook-publish-opendrive.py`. Фактические скрипты находятся в `/home/feninf/bin`. До изменения код использовал default 48 kbps, runtime-конфигурация задавала 32 kbps, а итоговый M4B кодировался как AAC 24 kHz mono. Для оформления использован существующий логотип `/home/feninf/bin/files/logo_au-books-1500.png` размером 1685x193.
## Изменённые файлы
- `/home/feninf/bin/tts_processor.py`: default bitrate повышен до 64 kbps.
- `/home/feninf/bin/1au-prepare_book.py`: логотип масштабируется до ширины обложки и добавляется снизу через ffmpeg `vstack`; при отсутствии исходной обложки сначала создаётся fallback; ошибки logo/cover/ffmpeg завершают prepare ненулевым exit code.
- `/home/feninf/bin/files/logo_au-books-1500.png`: logo asset добавлен в Git.
- `/home/feninf/bin/tests/test_tts_audio_output.py`: восемь focused regression tests.
- Локальная runtime-конфигурация `/home/feninf/aubooks`: effective bitrate для новых jobs изменён на 64 kbps; конфигурационный файл с приватными параметрами не коммитился.
## Проверки
- Focused unit tests: 8/8 passed.
- `/home/feninf/aubooks`: 78/78 tests passed.
- `py_compile` и `git diff --check`: успешно.
- Safe local ffmpeg smoke на 12-секундном fixture: AAC, 64172 bps, 24000 Hz, mono; embedded MJPEG cover 800x892, `attached_pic=1`.
- Извлечённая smoke-обложка визуально проверена: исходная cover сверху, logo снизу на полную ширину, без перекрытия, обрезки и искажения.
- Временные smoke-файлы и `*.branded.tmp.jpg` удалены.
- Релевантные calibre-web orchestration suites: 64 tests passed. Дополнительный aggregate discovery показал 13 ранее существующих failures в stale assertions про старый subprocess transport и разметку шаблонов. Отдельный известный transport timeout test был прекращён после 120 секунд из-за mock sleep 9999 секунд.
## Ограничения
Полная реальная генерация через edge-tts и upload не запускалась. Во время финальной проверки появился активный job `20260910_034055_1074210`; процесс не останавливался и состояние job не изменялось. Готовые M4B и схема `audio.db` не изменялись. Production-сервисы не перезапускались, deploy и push не выполнялись.
## Git
- `/home/feninf/bin`, branch `main`: `677d349 feat: improve audiobook quality and brand covers`.
- `/home/feninf/calibre-web`, branch `aubooks`: этот отчёт будет зафиксирован отдельным docs commit.
## Итог
Новые TTS-генерации настроены на AAC 64 kbps и получают валидированную брендированную обложку. Изменение покрыто unit tests и реальным локальным ffmpeg smoke; существующие аудиокниги и production не затронуты.
