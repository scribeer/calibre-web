# OpenDrive source fetcher для TTS pipeline

## Цель
Обеспечить получение исходных файлов книг (FB2/EPUB) с OpenDrive по `book_id`, когда локальные файлы отсутствуют (metadata-only библиотека).

## Что было изучено
1. Структура OpenDrive: `calibre-books-v2/<bucket>/<book_id>.<ext>`
2. Формула бакета: `book_id < 100 ? book_id : (book_id // 100) * 100`
3. Форматы на remote: FB2 (119,105), EPUB (3,255), TXT нет
4. Максимальный book_id на OpenDrive: ~37444
5. Существующий `find_source.py` ищет только локально

## Какие файлы добавлены
- `/home/feninf/aubooks/fetch_source_from_opendrive.py` — standalone fetcher
- `tests/test_fetch_source_opendrive.py` — 25 unit tests

## Какие файлы изменены
- `/home/feninf/bin/aubook-remote.sh` — `cmd_start_book_id()` с OpenDrive fallback

## Что именно изменено

### fetch_source_from_opendrive.py
- `compute_opendrive_path(book_id, fmt)` — вычисление remote path
- `lookup_format(book_id, db_path)` — запрос metadata.db для FB2/EPUB
- `fetch_source(book_id, dest_dir, remote, db_path)` — скачивание через rclone copyto
- shell=False, timeout=120s, проверка size > 0
- Exit codes: 0=ok, 4=not found, 5=no format, 6=remote missing, 7=download failed

### aubook-remote.sh cmd_start_book_id()
- Сначала `find_source.py` (приоритет: локальный файл)
- Если exit 7 (file missing) → `fetch_source_from_opendrive.py`
- Временный файл в `mktemp` dir, удаляется после cmd_start
- Exit 6 для remote не загружен (non-fatal)

## Тесты
- 54/54 pass (21 dispatcher + 8 transport + 25 fetch_source)
- Smoke test: book 27408 → 9,793 bytes, valid FB2 XML

## Commit hashes
- aubooks: `bc0c510`
- bin: `8a39db5`
- calibre-web: `9ca0a5f4`

## Известные ограничения
- TXT формат не поддерживается на OpenDrive
- Книги с ID > 37444 пока отсутствуют на remote
- fetch_source_from_opendrive.py не добавляет поддержку TXT
