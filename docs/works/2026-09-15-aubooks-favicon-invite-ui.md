# Favicon и улучшение invite UI

## Цель
Закрыть текущие мелкие задачи AU-Books: добавить favicon, улучшить UI генерации приглашения, задокументировать решение по обложкам и добавить TODO по человекочитаемым URL.

## Изменения
- `cps/static/img/favicon.png`: добавлен favicon AU-Books (источник `/home/feninf/aubooks/files/favicon.png`).
- `cps/themes/aubooks/templates/layout.html`: подключён AU favicon через `url_for('static', filename='img/favicon.png')`.
- `cps/admin.py`: ссылка приглашения теперь формируется как полный URL через `url_for('web.register_invite', token=raw_token, _external=True)`.
- `cps/themes/standard/templates/admin.html`: добавлена кнопка "Копировать" рядом со ссылкой приглашения и JS для копирования с feedback "Скопировано".
- `docs/works/2026-09-01-aubooks-cover-loading.md`: зафиксировано решение не использовать обложки, не переносить OpenDrive cover proxy, не показывать generic cover.
- `docs/works/2026-09-15-aubooks-friendly-urls-todo.md`: добавлена будущая задача по человекочитаемым URL с требованиями.

## Проверки
- `python3 -m py_compile cps/admin.py`: OK.
- Favicon: `GET /static/img/favicon.png` → 200, `Content-Type: image/png`, 6696 bytes.
- Favicon link присутствует в HTML главной страницы AU theme.
- Wheel packaging: `calibreweb/cps/static/img/favicon.png` найден в wheel.
- DEV smoke: `/` 200, `/login` 200, `/book/127813` 200.
- Copy button и JS присутствуют в `admin.html`.
- Полное end-to-end тестирование создания приглашения требует входа под admin (требуются credentials).

## Git
Commit: `8a94677a` в ветке `aubooks`, pushed to `origin/aubooks`.
Незакоммиченные изменения `deploy/vps2/deploy-calibre-web-release.sh`, `audit_ui_final.py`, `docs/works/2026-09-12-real-tts-smoke-test.md` оставлены без изменений.

## Production
VPS2 не затронут.
