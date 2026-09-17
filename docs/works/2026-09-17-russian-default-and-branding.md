# 2026-09-17: Русская локаль + удаление брендинга Calibre

## Цель
Установить русский язык по умолчанию для новых пользователей и удалить весь пользовательский брендинг Calibre-Web из интерфейса AU-Books.

## Что было изучено
- Поток регистрации в AU-Books: публичная регистрация заблокирована `is_aubooks_active()`, пользователи регистрируются через invite-ссылки (`/register/<token>` → `_register_user(..., invite=invite)`).
- Locale пользователя задаётся в `_register_user()` через `content.locale`. Invitation-based registration — единственный путь для AU-Books.
- `config_calibre_web_title` хранится в БД (`settings` таблица в `app.db`), Column default влияет только на новые установки.
- Брендинг Calibre-Web присутствовал в: email-ах, заголовках страниц, модальных окнах админки, osd.xml, feed.xml, index.xml, http_error, logviewer, config_edit, detail, stats.

## Изменённые файлы

### Python
- `cps/web.py` — `content.locale = "ru"` для всех новых регистраций
- `cps/config_sql.py` — default `config_calibre_web_title` изменён с `'Calibre-Web'` на `'AU-Books'`
- `cps/about.py` — `'Calibre Web'` → `'AU-Books'` в versions dict
- `cps/helper.py` — "Calibre-Web" → "AU-Books" в test email, registration email body/signature/subject
- `cps/search.py` — "restart Calibre-Web" → "restart the application"
- `cps/error_handler.py` — realm `"calibre-web"` → `"au-books"`
- `cps/admin.py` — flash messages "Calibre-Web configuration updated" → "Configuration updated", modal confirmation texts

### Шаблоны (standard theme — наследуется aubooks для admin/stats)
- `cps/themes/standard/templates/stats.html` — убрана "powered by Calibre-Web" ссылка
- `cps/themes/standard/templates/admin.html` — Restart/Stop/Update modal titles → AU-Books
- `cps/themes/standard/templates/http_error.html` — "Calibre-Web Instance is unconfigured" → "Instance is unconfigured"
- `cps/themes/standard/templates/logviewer.html` — "Calibre-Web Log" → "System Log"
- `cps/themes/standard/templates/config_edit.html` — reverse proxy warning без "Calibre-Web"
- `cps/themes/standard/templates/detail.html` — archive tooltip без "Calibre-Web"

### Шаблоны (caliblur theme)
- `cps/themes/caliblur/templates/stats.html` — убрана "powered by Calibre-Web"
- `cps/themes/caliblur/templates/http_error.html` — убрана "Calibre-Web Instance"

### XML
- `cps/templates/osd.xml` — Description и Contact → `{{instance}}`
- `cps/templates/feed.xml` — author uri → `{{instance}}`
- `cps/templates/index.xml` — author uri → `{{instance}}`

### Тесты
- `tests/test_branding_and_locale.py` — 20 новых тестов на локаль и брендинг

### Production
- Обновлена БД: `UPDATE settings SET config_calibre_web_title='AU-Books'`
- Перезапущен `calibre-web.service`

## Тесты
- `tests/test_branding_and_locale.py`: 20/20 passed
- `python3 -m compileall cps/`: чисто
- Полный прогон: 666 passed, 42 pre-existing failures (deploy helper, cmd_start, invite_admin endpoint, TTS dispatcher — не связаны с изменениями)

## Известные ограничения
- `config_calibre_web_title` в БД обновлён вручную через sqlite3. Новая default-коля `config_sql.py` влияет только на новые инсталляции.
- Оставлены технические ссылки на "Calibre" в: комментариях, header-ах файлов, admin-шаблонах (Calibre Database, Calibre Binaries — относятся к ПО Calibre), cli.py (server-side), constants.py (home dir).
- `config_edit.html:77`: "calibre-web.log" — имя файла, не брендинг.
- `web.py:1119`: комментарий "Calibre-Web filters" — developer-facing.

## Commit
- `d279547a` — Remove Calibre branding and default Russian locale for new users
