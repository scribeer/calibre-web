# Registration Invite Model — Stage 1

Цель: добавить модель и хелперы для одноразовых инвайт-ссылок регистрации.

## Схема

Таблица `invite` в `app.db` через `ub.Base`:

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY, autoincrement |
| `token_hash` | VARCHAR(64) | NOT NULL, UNIQUE, INDEX |
| `created_by_user_id` | INTEGER | FK → user.id, NULLABLE |
| `created_at` | DATETIME | NOT NULL (UTC) |
| `expires_at` | DATETIME | NOT NULL, INDEX (UTC) |
| `used_at` | DATETIME | NULLABLE |
| `used_by_user_id` | INTEGER | FK → user.id, NULLABLE |
| `revoked_at` | DATETIME | NULLABLE |

Терминальные состояния: `used_at IS NOT NULL` или `revoked_at IS NOT NULL`.

## Токен

Генерация: `secrets.token_urlsafe(32)` — 256 бит энтропии, URL-safe base64, ~43 символа.

Хранение: только `sha256(raw_token).hexdigest()` — 64 hex-символа. Сырой токен возвращается однократно администратору и никогда не сохраняется в БД.

Почему SHA-256, а не werkzeug `generate_password_hash`: токены не являются паролями, имеют 256 бит энтропии, требуют детерминированного indexed lookup.

## Срок жизни

`expires_at = created_at + 7 дней (UTC)`.

Проверка: `expires_at > now`. При `expires_at == now` — токен уже недействителен.

## Атомарное потребление

`consume_invite()` использует conditional UPDATE:

```python
session.query(Invite).filter(
    Invite.id == invite.id,
    Invite.used_at.is_(None),
    Invite.revoked_at.is_(None),
).update({'used_at': now, 'used_by_user_id': user_id})
```

Возвращает `True` только если обновлена ровно одна строка. SQLite сериализует записи, поэтому параллельные POST не могут успешно потребить один токен дважды.

Дизайн не коммитит внутри хелпера — вызывающий код может обернуть создание пользователя и потребление инвайта в одну транзакцию.

## Хелперы

| Функция | Назначение |
|---|---|
| `create_invite(session, created_by_user_id=None)` | Генерирует токен, добавляет строку в сессию, возвращает сырой токен |
| `get_invite_by_token(session, raw_token)` | Ищет валидный инвайт (не использован, не отозван, не истёк) |
| `consume_invite(session, invite, user_id)` | Атомарно помечает инвайт как использованный |
| `revoke_invite(session, invite)` | Помечает инвайт как отозванный |
| `_hash_token(raw_token)` | Возвращает SHA-256 hex |

## Тесты

40 тестов в `tests/test_invite_model.py`:

- генерация токена (URL-safe, энтропия, уникальность)
- хранение хеша (не сырой токен, 64 hex, уникальность)
- валидация (валидный, невалидный, истёкший, ровно на границе, использованный, отозванный)
- потребление (успех, повторный отказ, запись used_by_user_id, запись created_by_user_id)
- срок жизни (created_at + 7 дней, до/после истечения)
- безопасность откатов (rollback не потребляет инвайт)
- параллельное потребление (только одно из пяти вызовов успешно)
- отзыв (успех, нельзя отозвать использованный)
- безопасность (сырой токен не в БД, хеш совпадает с SHA-256)
- регрессия (существующие тесты регистрации и SEO проходят)

## Точки интеграции со Stage 2

- `GET /register/<token>` — вызывает `get_invite_by_token()`, рендерит форму
- `POST /register/<token>` — вызывает `get_invite_by_token()`, создаёт пользователя, вызывает `consume_invite()`, коммитит в одной транзакции
- `POST /admin/registration-link` — вызывает `create_invite()`, отображает токен администратору
- Очистка истёкших инвайтов — опционально, не обязательна для MVP

## Изменённые файлы

- `cps/ub.py` — модель `Invite`, хелперы, импорты `hashlib` и `secrets`
- `tests/test_invite_model.py` — новый тестовый файл
