# Создание регистрационных приглашений администратором
## Цель
Добавить для темы AU-Books административный интерфейс создания одноразовых ссылок регистрации, не реализуя их погашение и не меняя публичную регистрацию.
## Что изучено
- административный blueprint, декораторы `user_login_required` и `admin_required`;
- глобальная CSRF-защита Flask-WTF;
- shared-шаблон `admin.html` и механизм определения активной темы;
- модель и хелперы приглашений из Stage 1.
## Route
Добавлен `POST /admin/registration-link` в `cps/admin.py`.
Route:
- требует авторизации и роли администратора;
- защищён глобальным `CSRFProtect`;
- работает только при `aubooks_permissions.is_aubooks_active()`;
- передаёт в `ub.create_invite()` только `current_user.id`;
- не принимает из формы срок, владельца, email, роль или число использований;
- для GET возвращает 405.
## Работа с raw token
`ub.create_invite()` возвращает сырой токен только обработчику POST. Обработчик формирует относительный URL `/register/<token>` и сразу рендерит admin-страницу.
Redirect не используется, потому что для него пришлось бы сохранять bearer token в flash или cookie-сессии. Токен не сохраняется в БД и не записывается в лог. В БД остаётся только SHA-256 hash из Stage 1.
## Admin UI
В `cps/themes/standard/templates/admin.html` рядом с `Add New User` добавлена AU-only секция:
- кнопка `Создать ссылку регистрации` в POST-форме с CSRF token;
- readonly-поле `Ссылка регистрации` в единственном ответе после создания;
- пояснение `Действительна 7 дней и позволяет создать один аккаунт.`;
- список последних 20 приглашений без токенов.
Для standard и других тем секция не рендерится, а прямой POST запрещён.
## Список приглашений
`ub.get_invite_list(session, limit=20)` возвращает даты, имя создателя и статус. Поддерживаются статусы `Active`, `Used`, `Expired`, `Revoked`. Сырой токен в результат не входит.
## Изменённые файлы
- `cps/admin.py`;
- `cps/ub.py`;
- `cps/themes/standard/templates/admin.html`;
- `tests/test_invite_admin.py`;
- `docs/works/2026-09-12-registration-invite-admin.md`.
## Тесты
`tests/test_invite_admin.py` использует отдельное Flask-приложение, production admin blueprint, глобальный CSRFProtect и in-memory SQLite.
Проверены anonymous/non-admin/admin, обязательность CSRF, POST-only route, AU-only ограничение, ровно одна созданная запись, серверные creator и expiry, игнорирование подменённых полей, raw URL в ответе, отсутствие raw token в БД и логах, SHA-256 hash, лимит и статусы списка, отсутствие UI в standard theme и работоспособность существующей admin-страницы.
Дополнительно запускаются Stage 1 и связанные regression tests, а также `py_compile` изменённых Python-файлов.
## Stage 3
Stage 3 должен добавить `GET/POST /register/<token>` и атомарно объединить создание пользователя с `ub.consume_invite()` в одной транзакции. Stage 2 не изменяет registration/login flow.
## Ограничения
- ссылка пока ведёт на route, который появится только в Stage 3;
- revoke UI не реализован;
- даты списка выводятся в формате, который предоставляет текущий Jinja context.
## Commit
Корректирующий commit Stage 2: см. commit, содержащий этот отчёт.
