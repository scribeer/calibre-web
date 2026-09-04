# Кнопка «Озвучить» — POST route для запуска TTS

## Цель
Сделать кнопку «О דיגיטלי / Озвучить повторно» на странице книги рабочей: при нажатии безопасно создавать реальную TTS job через существующий pipeline.

## POST Route

`POST /books/<int:book_id>/generate-audio`

- Декораторы: `@web.route(..., methods=["POST"])`, `@user_login_required`
- Внутри: проверка `current_user.role_tts()`,否则 abort(403)
- CSRF: автоматическая через `CSRFProtect` (validate against session)
- Post/Redirect/Get: `redirect(url_for("web.show_book", book_id=book_id), code=303)`

## Кто может запускать TTS

Новая роль `ROLE_GENERATE_TTS = 1 << 9` (бит 9):

| Файл | Изменение |
|------|-----------|
| `cps/constants.py:71` | `ROLE_GENERATE_TTS = 1 << 9` |
| `cps/constants.py:81` | `"tts_role": ROLE_GENERATE_TTS` в `ALL_ROLES` |
| `cps/ub.py:175-176` | `role_tts()` метод в `UserBase` |

В шаблоне `detail.html` кнопка «Озвучить» показывается только при `current_user.role_tts()`.

## Выбор source file

`_find_tts_source(book)` — ищет лучший формат для TTS:

1. Проходит по `_TTS_SOURCE_FORMATS`: EPUB, FB2, PDF, TXT, MOBI, AZW3, AZW, KEPUB, DOCX, RTF, HTML
2. Для каждого формата вызывает `calibre_db.get_book_format(book_id, fmt)`
3. Строит полный путь: `config.get_book_path() + book.path + data.name + "." + fmt.lower()`
4. Проверяет `os.path.isfile()` — физическое наличие на диске
5. Возвращает `(file_path, format)` или `(None, None)`

Пользователь не передаёт путь — он определяется из Calibre metadata.

## Вызов pipeline

```python
subprocess.Popen(
    [_AUBOOK_REMOTE, "start", source_path, "1", "publish", str(book_id)],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
```

- `shell=True` НЕ используется
- Аргументы — список, не строка
- `_AUBOOK_REMOTE` = `~/bin/aubook-remote.sh` (фиксированный путь из home dir)
- `start_new_session=True` — задание изолировано от Flask process
- stdout/stderr → DEVNULL чтобы не блокировать
- `Popen` возвращает мгновенно — HTTP request не ждёт TTS

## Двойная защита от дублей

1. **Route-level**: проверяет `audio_status` перед `create_queued`:
   - `queued` / `processing` / `ready` → flash + redirect (не создаёт job)
   - `not_available` → `create_queued(book_id)`
   - `failed` → `reset_for_retry(book_id)` → потом pipeline создаёт job заново

2. **audio_index-level**: `create_queued()` проверяет `UNIQUE(book_id)` constraint:
   - `ValueError` если record уже существует
   - SQLite UNIQUE guarantee предотвращает race condition

## Retry после failed

```
failed → reset_for_retry(book_id) → queued
```

Если `reset_for_retry` не удался → flash error + redirect (без создания job).

Если `Popen` завершился ошибкой (FileNotFoundError / OSError):
- `mark_failed(book_id, "reason")` — статус возвращается в failed
- Пользователь видит flash error и может повторить

## Что происходит при каждом статусе

| Статус | Действие | UI |
|--------|----------|----|
| `not_available` | `create_queued()` → `Popen(start ...)` | Flash: «Книга добавлена в очередь на озвучивание.» |
| `failed` | `reset_for_retry()` → `Popen(start ...)` | Flash: «Книга добавлена в очередь на озвучивание.» |
| `queued` | Ничего (blocked) | Flash: «Эта книга уже обрабатывается.» |
| `processing` | Ничего (blocked) | Flash: «Эта книга уже обрабатывается.» |
| `ready` | Ничего (blocked) | Flash: «Аудио уже доступно.» |

## После успешного POST

1. HTTP 303 redirect → `/books/<id>/<slug>`
2. Flash message через `flask.flash()` с category="success"
3. После reload: `audio.db` содержит `status=queued`, UI показывает «В очереди»

## Обработка ошибок

| Ошибка | Действие | Пользователь видит |
|--------|----------|-------------------|
| Нет book_id | abort(404) | 404 page |
| Guest / нет role_tts | abort(403) | 403 page |
| Нет source format | flash error + redirect | «No supported source format available for TTS.» |
| audio.db недоступна | flash error + redirect | «Could not create audio job.» |
| Pipeline не найден | mark_failed + flash error | «Audio generation service is unavailable.» |
| OSError при запуске | mark_failed + flash error | «Could not start audio generation.» |

Полная диагностика только в server log. Traceback, пути, команды — не показываются.

## Тесты

36 тестов в `tests/test_aubooks_generate_audio.py`:

**TestFindTtsSource (4):** форматы определены, EPUB>PDF, функция существует, использует get_book_path
**TestGenerateAudioStatusChecks (5):** queued/processing/ready blocked, not_available allowed, failed retry
**TestDuplicateProtection (2):** create_queued предотвращает дубли, reset только из failed
**TestSubprocessCall (4):** список аргументов, без shell=True, фиксированный путь, DEVNULL
**TestTemplateFormStructure (9):** POST формы для not_available/failed, нет форм для queued/processing/ready, CSRF, submit, role_tts gate
**TestAuthAndPermissions (3):** POST only, role_tts check, user_login_required
**TestErrorHandling (5):** FileNotFoundError/OSError revert, нет traceback, user-friendly flash
**TestRaceProtection (2):** UNIQUE constraint, status check before create
**TestRouteSignature (3):** book_id param, PRG pattern, book exists check

Все 82 теста (36 + 46 существующих) пройдены.

## DEV верификация

1. Сервер перезапущен на `127.0.0.1:8084`
2. Admin пользователю добавлена роль `ROLE_GENERATE_TTS` (role: 479 → 991)
3. Login → /book/1 → кнопка «Generate audio» отображается
4. POST → 303 redirect → Flash: «No supported source format available for TTS.» (book 1 не имеет EPUB/FB2/TXT)
5. CSRF защита работает (400 при невалидном токене)
6. Лог чистый, ошибок нет

## Изменённые файлы

| Файл | Что изменено |
|------|-------------|
| `cps/constants.py` | `ROLE_GENERATE_TTS = 1 << 9`, добавлен в `ALL_ROLES` |
| `cps/ub.py` | `role_tts()` метод в `UserBase` |
| `cps/web.py` | Импорт `subprocess`, `_TTS_SOURCE_FORMATS`, `_AUBOOK_REMOTE`, `_find_tts_source()`, `generate_audio()` route |
| `cps/themes/aubooks/templates/detail.html` | not_available → POST form с CSRF, failed → POST form,其他状态 → read-only |
| `tests/test_aubooks_generate_audio.py` | 36 новых тестов |
| `docs/works/2026-09-04-calibre-web-generate-audio-action.md` | Этот отчёт |

## Commit

`git add cps/constants.py cps/ub.py cps/web.py cps/themes/aubooks/templates/detail.html tests/test_aubooks_generate_audio.py docs/works/2026-09-04-calibre-web-generate-audio-action.md`
