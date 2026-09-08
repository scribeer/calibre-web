# Guest Sidebar Navigation — 2026-09-08

## Проблема 1: Ссылка отсутствует в сайдбаре

Гость (неавторизованный пользователь) не видел пункт "Все категории" в сайдбаре.

### Причина

В `cps/themes/aubooks/templates/layout.html` строка 146:

```html
{% if current_user.check_visibility(element['visibility']) %}
<li id="nav_cat">...Все категории...</li>
{% endif %}
```

Условие `check_visibility` возвращало `false` для anonymous users, скрывая ссылку.

### Исправление

Удалено условие `check_visibility` для ссылки "Все категории". Ссылка теперь показывается всем пользователям, включая гостей.

## Проблема 2: HTTP 404 при переходе

После возвращения ссылки в сайдбар, клик по "Все категории" давал HTTP 404.

### Причина

В `cps/web.py:1200-1231`:

```python
def category_list():
    if current_user.check_visibility(constants.SIDEBAR_CATEGORY):
        # ... render page
    else:
        abort(404)
```

Для anonymous users `check_visibility(SIDEBAR_CATEGORY)` возвращал `false`, вызывая `abort(404)`.

### Исправление

Изменено условие на:

```python
if current_user.is_anonymous or current_user.check_visibility(constants.SIDEBAR_CATEGORY):
```

Anonymous users теперь могут открывать страницу категорий.

## Что отсутствовало у Guest

- **Все категории** — единственная отсутствующая публичная ссылка

## Что намеренно скрыто у Guest

- Личные списки (Полки)
- Прочитанное
- Архив
- Профиль
- Настройки
- Другие действия, требующие аккаунта

## Изменённые файлы

- `cps/themes/aubooks/templates/layout.html` — удалено условие `check_visibility` для "Все категории"
- `cps/web.py` — добавлен `current_user.is_anonymous` в условие `category_list()`

## Browser verification

- Guest: "Все категории" присутствует, страница открывается без 404
- Guest: категории отображаются, можно переходить к книгам
- Logged-in: сайдбар не сломан, прежние пункты остались

## Tests

- 136 tests pass (включая новый regression test для anonymous access)

## Commits

- d399418e — ui: restore public sidebar navigation for guests
- 660f8145 — docs: document guest sidebar navigation fix
- TBD — fix: allow guests to browse all categories