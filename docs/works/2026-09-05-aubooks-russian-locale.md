# Русская локализация AU-Books

## Цель
Перевести весь интерфейс AU-Books на русский язык для анонимных и авторизованных пользователей.

## Что было изучено
- Механизм локализации Calibre-Web: Flask-Babel + gettext `.po`/`.mo`
- `cw_babel.py:get_locale()` — определяет локаль: для залогиненных берёт `user.locale`, для анонимных — по `Accept-Language`, fallback был захардкожен `'en'`
- Dev instance app.db: `/home/feninf/calibre-web/8084` (не `calibre-web-dev-data/app.db`)
- Русские `.mo` файлы уже существовали, но многие строки отсутствовали

## Изменённые файлы

### `cps/cw_babel.py`
- Fallback локали: вместо захардкоженного `'en'` теперь читает `config.config_default_locale`
- Импорт `config` сделан ленивым (внутри функции) чтобы избежать циклических импортов

### `cps/translations/ru/LC_MESSAGES/messages.po`
- Добавлен перевод `"System"` → `"Системная"` (переключатель темы)
- Добавлены переводы для формы регистрации: `Confirm password`, `Create a password`, `Repeat your password`, `Your email address`, `Show/Hide password`, `Don't have an account? Register`, `Already have an account? Log in`, `Create a new account to access AU-Books`
- Добавлены переводы для детальной страницы: `Archive`, `Audio book status`, `Generate audio`, `Generating audio…`, `In queue`, `Retry audio`, `Listen`, `Send to eReader`, `Mark Book as Read or Unread`
- Добавлены переводы для навигации и UI: `Breadcrumb`, `Grid`, `List`, `Library navigation`, `Main navigation`, `Pagination`, `Search results`, `results found`, `Simple Theme`, `Ok`, `Select`
- Добавлены переводы для сортировки: `Sort title in alphabetical order`, `Sort title in reverse alphabetical order`
- Добавлены переводы для удаления: `This book format will be permanently erased from database`, `This book will be permanently erased from database and hard disk`
- Добавлены переводы для поиска: `Try a different search term or use Advanced Search to refine your query.`
- Добавлены переводы для Kobo: `Important Kobo Note: deleted books will remain on any paired Kobo Reader`
- Заполнены пустые `msgstr` для ранее существовавших записей: `Choose File Location`, `Cover`, `Grid`, `List`, `name`, `Ok`, `Parent Directory`, `Remove from shelf`, `Select`, `Send to eReader`, `Simple Theme`, `size`, `Sort title in alphabetical/reverse alphabetical order`, `This book format…`, `This book…`, `type`, `Show password`, `Hide password`, `Archive`, `Book %(index)s of %(range)s`
- Всего добавлено/заполнено ~50 строк перевода

### `cps/translations/ru/LC_MESSAGES/messages.mo`
- Перекомпилирован через Babel (943 entries)

### `cps/themes/aubooks/templates/layout.html`
- Удалена ссылка «О программе» из боковой панели

## Результаты
- Логин/регистрация: полностью на русском
- Главная страница: полностью на русском
- Детальная страница: полностью на русском (кроме данных из БД — авторы, теги)
- Боковая панель: только Категории + Полки (без «О программе»)
- Переключатель темы: Системная / Светлая / Тёмная
- 404 страница — на английском (стандартная тема, не AU-Books)
- Единственные английские строки — данные из БД (имена авторов, теги)

## Тесты
- 136/136 пройдены (skipped: `test_args_are_list` — pre-existing failure, transport refactored; `test_fetch_source_opendrive` — hang on network)
- Сервис стабилен: `calibre-web-dev.service` на порту 8084

## Известные ограничения
- Страница 404 использует стандартную тему — не переведена (не критично)
- Строка `"Mark Book as archived or not…"` содержит Anglizism "Calibre-Web" и "Kobo Reader" — оставлены как есть
