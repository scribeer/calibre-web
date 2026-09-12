# Admin Registration Invite Creation — Stage 2

Цель: добавить admin-only UI и route для создания одноразовых инвайт-ссылок регистрации.

## Route

`POST /admin/registration-link`

- `@user_login_required` + `@admin_required` — только авторизованные администраторы
- CSRF защищён глобально через `CSRFProtect` (автоматически)
- GET не разрешён

## Raw token handling

Сырой токен существует только во времени выполнения POST-запроса:

1. `ub.create_invite()` генерирует токен и возвращает его
2. Токен вставляется в URL: `/register/<raw_token>`
3. URL рендерится на странице `admin.html` в `readonly` поле
4. Страница возвращается администратору **один раз**
5. Сырой токен **не сохраняется** в БД, сессии, flash, логах

Почему не redirect: redirect потребовал бы сохранить токен в session/flash, что противоречит требованию не хранить сырой токен. Рендер напрямую после POST — единственный безопасный способ показать токен ровно один раз.

## Admin UI

Расположение: `cps/themes/standard/templates/admin.html`, после кнопки "Add New User".

Секция видна только при `is_aubooks` (theme ID == 3).

Элементы:
- Кнопка "Создать ссылку регистрации" — POST-форма с CSRF-токеном
- Readonly поле с URL — после успешного POST
- Таблица "Recent Invitations" — список последних 20 инвайтов

## Invite list

Добавлен хелпер `ub.get_invite_list(session, limit=20)` в Stage 1 модель для переиспользования.

`admin._get_invite_list()` оборачивает его с локализацией статусов.

Статусы: Active, Used, Expired, Revoked.

Сырой токен никогда не отображается в списке.

## Тесты

37 тестов в `tests/test_invite_admin.py`:

- Структура route (POST-only, decorators, create_invite, current_user.id, no custom expiry/role/flash)
- Template (форма, CSRF, кнопка, readonly URL, invite list, AU-only)
- Invite list helper (все статусы, created_by, no raw token)
- Token security (no raw in DB, only SHA-256)
- Regression (Stage 1 model cycle, py_compile)

## Stage 3 integration points

- `GET /register/<token>` — вызывает `ub.get_invite_by_token()`
- `POST /register/<token>` — вызывает `ub.consume_invite()` + создание пользователя
- Навигация и login-страница — скрытие/показ ссылки на регистрацию

## Изменённые файлы

- `cps/admin.py` — route `create_registration_link()`, хелпер `_get_invite_list()`, обновлён `admin()` для передачи invites
- `cps/ub.py` — добавлен `get_invite_list()`
- `cps/themes/standard/templates/admin.html` — секция инвайтов (AU-only)
- `tests/test_invite_admin.py` — новый тестовый файл
