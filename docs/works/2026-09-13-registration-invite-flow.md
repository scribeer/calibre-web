# Регистрация по одноразовому приглашению
## Цель
Реализовать для темы AU-Books регистрацию по одноразовой ссылке `/register/<token>` с семидневным сроком действия, не меняя публичную регистрацию стандартной темы Calibre-Web.
## Что изучено
- существующие GET/POST routes `/register` и AU-шаблон формы;
- проверки username, email и разрешённых доменов;
- создание `ub.User`, password hashing и default role/config fields;
- Stage 1 helpers проверки и атомарного потребления приглашения;
- AU login/navbar templates и связанные permission tests.
## Routes
Добавлены:
- `GET /register/<token>`;
- `POST /register/<token>` с лимитами `40/day` и `3/minute` по IP.
Routes работают только при активной теме AU-Books. Авторизованный пользователь перенаправляется на главную страницу. GET проверяет приглашение, но не потребляет его.
Неизвестное, malformed, истёкшее, отозванное или использованное приглашение даёт одинаковое сообщение `Ссылка регистрации недействительна или срок её действия истёк.` и redirect на login.
## Plain register
Для AU-Books GET и POST `/register` больше не предоставляют публичную регистрацию. Они показывают сообщение `Регистрация доступна только по приглашению.` и перенаправляют на login. POST не создаёт пользователя.
Для standard/CaliBlur сохранены прежние `config_public_reg`, SMTP, OAuth и form semantics.
## Validation flow
Общий внутренний helper `_register_user()` используется public и invite flows без дублирования основных проверок.
Invite flow:
1. повторно проверяет валидность токена на POST;
2. требует username, email, password и confirmation;
3. применяет `check_username()`, `check_email()` и `check_valid_domain()`;
4. создаёт `ub.User` с хешем выбранного пароля;
5. копирует `config_default_role`, locale, sidebar и allowed/denied restrictions;
6. потребляет приглашение и коммитит транзакцию;
7. перенаправляет на login без автоматического входа.
Invite не принимает email, role, creator или другие security fields из формы.
## Транзакция и атомарность
Для invite registration выполняются `session.add(user)`, `session.flush()`, conditional `consume_invite()` и один `session.commit()`.
При validation error запись пользователя ещё не добавлена, а приглашение остаётся unused. При flush/update/commit error выполняется rollback обеих операций.
Conditional UPDATE теперь включает `used_at IS NULL`, `revoked_at IS NULL` и `expires_at > now`. Поэтому повторные и конкурентные попытки могут успешно создать не более одного пользователя, включая границу истечения срока.
## Role и permissions
Новый пользователь получает ровно `config_default_role`. Поля POST не могут выдать admin, upload, edit, delete или AU TTS upload. Администратор по-прежнему отвечает за безопасное значение глобального default role в существующей конфигурации Calibre-Web. Существующие AU-правила download/TTS для обычного авторизованного пользователя не изменялись.
## SMTP
GET invite form и регистрация с выбранным паролем не требуют настроенного SMTP и не отправляют registration email. Legacy standard registration с generated password сохраняет прежнюю SMTP-зависимость.
## Token security
- raw token находится только в исходной invite URL и request path;
- форма без `action` отправляет POST на тот же `/register/<token>`;
- raw token не сохраняется в БД, session или flash;
- встроенный Tornado access log заменяет token segment на `<redacted>`;
- в БД хранится только SHA-256 hash;
- registration template не содержит внешних HTTP(S) ресурсов, assets загружаются same-origin через layout;
- ссылки формы на login не содержат токен.
Внешний reverse proxy может логировать исходный URI до передачи приложению; его access-log policy нужно проверить отдельно перед production rollout.
## UI
В AU login template публичная ссылка регистрации заменена текстом `Регистрация доступна по приглашению.`. В AU navbar удалена ссылка на plain `/register`; доступ к login сохранён при включённом и выключенном anonymous browsing. Standard/CaliBlur templates не изменялись.
## Изменённые файлы
- `cps/web.py`;
- `cps/ub.py`;
- `cps/tornado_wsgi.py`;
- `cps/themes/aubooks/templates/login.html`;
- `cps/themes/aubooks/templates/layout.html`;
- `tests/test_invite_registration.py`;
- `tests/test_aubooks_registration.py`;
- `tests/test_aubooks_user_permissions.py`;
- `docs/works/2026-09-13-registration-invite-flow.md`.
## Тесты
Hermetic HTTP tests используют production web blueprint, глобальный CSRFProtect и in-memory SQLite. Проверены valid GET/POST, password hash, default role, used fields, redirect/login, invalid invite states, generic errors, validation rollback, forced DB rollback, повторное использование, plain AU routes, generated-password flow standard registration, CSRF, ignored role/creator fields, token storage/session/logging, маскирование встроенного access log, rate limits и отсутствие публичных UI-ссылок.
Отдельно запускаются Stage 1 model tests, Stage 2 admin tests, AU download/TTS/upload permission regressions и связанные registration/SEO tests.
## Ограничения и следующий шаг
Реальный DEV runtime smoke test не выполнялся: `/home/feninf/calibre-web/8084` не изменялся, сервисы не перезапускались, реальные приглашения и пользователи не создавались. Следующий шаг после review commit: отдельная разрешённая задача на DEV smoke test с резервной копией DEV DB.
## Commit
Commit hash: см. commit, содержащий этот отчёт.
