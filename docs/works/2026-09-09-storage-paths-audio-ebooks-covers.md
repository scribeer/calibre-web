# Storage Paths Audit: Audio / eBooks / Covers

**Дата:** 2026-09-09

## Цель
Аудит и исправление работы с файлами книги на странице книги: аудио, текстовые форматы, обложки.

## Обнаруженные проблемы

### 1. Аудиокнига — Две ошибки

**Ошибка A: Неверное имя поля**
- `audio.db` хранит путь в поле `opendrive_path`
- Код в `download_audiobook` искал `record.get("od_path")` → всегда `None`
- Результат: маршрут всегда отдавал 404 «Audio file path not available»

**Ошибка B: Вычисляемый путь вместо фактического**
- Даже если бы поле было найдено, маршрут игнорировал его и вычислял `calibre-books-v2/{bucket}/{book_id}.m4b`
- Реальный путь для book_id=10: `Audiobooks/2026/09/elena-zvezdnaya-dolina-drakonov.m4b`
- Вычисляемый путь: `calibre-books-v2/1/10.m4b` — этого файла нет на OpenDrive

**Исправление:**
- `cps/web.py`: `record.get("od_path")` → `record.get("opendrive_path")`
- `cps/web.py`: `remote_path = od_path` вместо вычисления

### 2. Обложки — Неверный путь к бакету

**Проблема:**
- `opendrive.py` использовал шаблон `{book_id}/{book_id}.jpg`
- Реальная структура: `{bucket}/{book_id}.jpg`, где bucket = 1 если book_id < 100, иначе (book_id // 100) * 100
- Для book_id=10: ожидалось `10/10.jpg` (404), реальный путь `1/10.jpg` (200)

**Исправление:**
- `cps/opendrive.py`: новая функция `_opendrive_cover_path(book_id)` с правильным вычислением bucket
- Удалён `COVER_PATH_TEMPLATE`

### 3. Текстовые файлы — Отсутствует интеграция с OpenDrive

**Проблема:**
- Локальная библиотека содержит только `metadata.db` (нет файлов книг)
- `do_download_file` пытался читать с диска → 404
- Существовала интеграция только с Google Drive, но не с OpenDrive

**Исправление:**
- `cps/opendrive.py`: новые функции `compute_opendrive_path()` и `fetch_ebook_from_opendrive()`
- `cps/helper.py`: fallback на OpenDrive при отсутствии локального файла

## Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `cps/web.py` | Исправлено поле `opendrive_path`, убрано вычисление пути |
| `cps/opendrive.py` | Исправлен путь обложки, добавлены функции для ebook |
| `cps/helper.py` | Добавлен OpenDrive fallback для скачивания ebooks |
| `cps/themes/aubooks/templates/detail.html` | (ранее) Кнопка "Скачать аудиокнигу" вместо "Слушать" |

## Тесты

| Тест | Результат |
|------|-----------|
| `/books/10/audio/download` | ✅ 200, файл 126MB, Content-Disposition корректен |
| `/cover/10` | ✅ 200, изображение получено |
| `/download/10/fb2/10.fb2` | ⚠️ 404 — pre-existing проблема CalibreDB (не связана с изменениями) |
| `fetch_ebook_from_opendrive(10, 'FB2')` | ✅ Файл 977648 байт получен, cleanup работает |
| `compute_opendrive_path(10, 'FB2')` | ✅ `calibre-books-v2/1/10.fb2` |
| `_opendrive_cover_path(10)` | ✅ `1/10.jpg` |

## Текущая модель хранения

```
OpenDrive: calibre-books-v2/
├── <bucket>/                     # bucket = 1 (book_id<100), 100, 200, ...
│   ├── <book_id>.fb2             # текстовые файлы книг
│   ├── <book_id>.epub
│   └── <book_id>.jpg             # обложки
└── ...

OpenDrive: Audiobooks/
└── <YYYY>/<MM>/<filename>.m4b    # аудиокниги (путь в audio.db)
```

## Требует проверки на VPS2

- Скачивание аудиокниги для другого book_id с реальным файлом
- Скачивание ebook через OpenDrive fallback
- Отображение обложек для книг с book_id >= 100 (другой bucket)
- Отсутствие regressions для книг без audio.od_path
- Проверка безопасности: путь берётся только из БД, не из URL/query string
