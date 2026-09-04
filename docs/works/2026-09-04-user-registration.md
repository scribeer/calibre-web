# Регистрация пользователей AU-Books

## Цель

Включить публичную регистрацию в DEV Calibre-Web, чтобы анонимные посетители могли создать аккаунт и войти.

## Что было изучено

- Штатная регистрация Calibre-Web: `/register` route, `register.html` template
- Стандартный flow: генерация случайного пароля → отправка по email
- AU-Books theme не имеет `register.html` — используется fallback на standard template
- `config_public_reg` включает/выключает регистрацию
- `valid_password()` в `helper.py` проверяет политику паролей

## Что изменено

### Runtime (без commit)

- `config_public_reg = 0` → `1` в `/home/feninf/calibre-web/8084`

### Файлы (commit)

1. **`cps/themes/aubooks/templates/register.html`** — новый template
   - Поля: username, email, password, confirm password
   - Кнопки show/hide password (как в login.html)
   - Accessibility: labels, aria-required, autocomplete
   - Ссылка «Already have an account? Log in»

2. **`cps/web.py`** — модификация `register_post()`
   - Если `password` и `confirm_password` переданы в форме: используется user-chosen flow
   - Валидация: непустой пароль + совпадение паролей (глобальная `valid_password()` НЕ вызывается)
   - Если пароль не передан: fallback на стандартный flow (random password + email)
   - После успешной регистрации: redirect на `/login` с сообщением
   - Парольная политика (min length, uppercase, digits, specials) НЕ применяется к публичной регистрации

3. **`cps/themes/aubooks/templates/login.html`** — добавлена ссылка на регистрацию
   - Показывается только когда `config_public_reg = 1`

## Проверки

| Тест | Результат |
|---|---|
| GET `/register` → HTTP 200 | ✓ |
| AU-Books theme используется | ✓ (`css/aubooks` в HTML) |
| Anonymous `/` → HTTP 200 | ✓ |
| Регистрация testuser → HTTP 302 (redirect на /login) | ✓ |
| Пользователь создан (role=0, не admin) | ✓ |
| Login под новым пользователем → HTTP 302 | ✓ |
| Duplicate username → «already taken» error | ✓ |
| Password mismatch → «do not match» error | ✓ |
| Ссылка Register на странице login | ✓ |
| admin и Guest не изменены | ✓ |
| Сервис active через 15 сек | ✓ |

## Не сделано

- Email verification
- Роли для слепых/зрячих
- TTS permissions
- Approval администратором
