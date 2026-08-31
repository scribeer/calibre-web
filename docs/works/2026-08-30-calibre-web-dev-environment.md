# Изолированное DEV-окружение Calibre-Web на VPS1
## Цель
Поднять отдельный Calibre-Web DEV для форка AU-Books, безопасно проверять тему и шаблоны без доступа к production VPS2.
## Структура
- Репозиторий и рабочая ветка: `/home/feninf/calibre-web`, `aubooks`.
- Virtualenv: `/home/feninf/calibre-web/.venv`.
- DEV data root: `/home/feninf/calibre-web-dev-data`.
- DEV application database: `/home/feninf/calibre-web-dev-data/app.db`.
- DEV Google Drive database: `/home/feninf/calibre-web-dev-data/gdrive.db`.
- DEV cache: `/home/feninf/calibre-web-dev-data/cache`.
- DEV log: `/home/feninf/calibre-web-dev-data/calibre-web-dev.log`.
- DEV Calibre library: `/home/feninf/calibre-web-dev-data/library/metadata.db`.
- Initial admin password: `/home/feninf/calibre-web-dev-data/admin-password`, права `0600`; значение не включено в документацию.
## Библиотека и изоляция
- В DEV скопирован локальный `library/metadata.db` из репозитория. В нём 0 книг, `PRAGMA integrity_check` вернул `ok`.
- Service использует только копию metadata.db в DEV data root, не production library.
- `app.db`, `gdrive.db`, cache и log отдельные; service передаёт их явными аргументами и environment variables.
- Service запускается от user `feninf` через user systemd. Он не использует venv, БД, файлы или сервисы VPS2.
- Port привязан только к `127.0.0.1:8084`; nginx, firewall и внешний bind не настраивались.
## Установка зависимостей
Создан venv через `python3 -m venv .venv`. Внутри него выполнено `.venv/bin/pip install --requirement requirements.txt`; используются только зависимости из репозитория. `.venv/bin/pip check` вернул `No broken requirements found`.
## Systemd service
Unit: `/home/feninf/.config/systemd/user/calibre-web-dev.service`.
```ini
[Service]
WorkingDirectory=/home/feninf/calibre-web
Environment=CALIBRE_PORT=8084
Environment=CACHE_DIRECTORY=/home/feninf/calibre-web-dev-data/cache
ExecStart=/home/feninf/calibre-web/.venv/bin/python /home/feninf/calibre-web/cps.py -p /home/feninf/calibre-web-dev-data/app.db -g /home/feninf/calibre-web-dev-data/gdrive.db -o /home/feninf/calibre-web-dev-data/calibre-web-dev.log -i 127.0.0.1 -m
Restart=on-failure
```
Unit enabled and active. Управление без sudo:
```bash
systemctl --user start calibre-web-dev.service
systemctl --user stop calibre-web-dev.service
systemctl --user restart calibre-web-dev.service
systemctl --user status calibre-web-dev.service
```
Точная команда остановки: `systemctl --user stop calibre-web-dev.service`.
## Первоначальная DEV-конфигурация
В отдельной DEV app.db до запуска установлены `config_calibre_dir=/home/feninf/calibre-web-dev-data/library`, `config_port=8084`, `config_external_port=8084`, `config_theme=3`, `config_anonbrowse=1`, `config_calibre_web_title=AU-Books DEV`.

Тему выбрали безопасно прямой записью только в DEV app.db, когда production-БД не использовались. В обычном DEV UI её можно сменить через `Admin` -> `UI Configuration` -> `Theme` -> `AU-Books`. Пароль user `admin` заменён случайным и хранится только в DEV-файле с правами `0600`.
## Проверки
- `systemctl --user is-active calibre-web-dev.service` - `active`.
- Unit enabled.
- `ss -ltnp 'sport = :8084'` - слушает только `127.0.0.1:8084`.
- `curl http://127.0.0.1:8084/` - HTTP 200.
- `curl http://127.0.0.1:8084/login` - HTTP 200.
- `curl http://127.0.0.1:8084/static/css/aubooks.css` - HTTP 200.
- DEV app.db содержит theme id `3`, title `AU-Books DEV`, путь к DEV library и UUID, совпадающий с копией metadata.db.
- `PRAGMA integrity_check` для DEV app.db и DEV metadata.db - `ok`.
- `.venv/bin/python -m py_compile cps/themes.py` - успешно.
## Проверка темы aubooks
- Главная страница отдала standard `index.html` через существующий fallback: тема `aubooks` не содержит `index.html`.
- `/login` также отдал standard `login.html` через fallback.
- Оба HTML содержат `<link href="/static/css/aubooks.css">` и title `AU-Books DEV`.
- Layout не падает. Runtime обнаружил, что standard layout импортирует `theme('modal_dialogs.html')`, поэтому добавлен минимальный `cps/themes/aubooks/templates/modal_dialogs.html`: он экспортирует пять proxy macros из standard template. Page templates и visual CSS не копировались и дизайн не менялся.
## Доступ с ноутбука
На ноутбуке с существующим SSH key для `feninf@server.domain.com`:
```bash
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 8084:127.0.0.1:8084 feninf@server.domain.com
```
После установления туннеля открыть `http://127.0.0.1:8084` в браузере. Проверка: `curl -I http://127.0.0.1:8084/`. Остановка foreground tunnel: `Ctrl-C`.
## Доступ с Android и Termux
На телефоне с уже рабочим SSH public key пользователя `feninf` использовать:
```bash
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 8084:127.0.0.1:8084 feninf@server.domain.com
```
Затем браузер телефона открывает `http://127.0.0.1:8084`. Туннель привязан к loopback телефона по умолчанию и не публикует порт в сети.

Удобный постоянный вариант: сохранить в Termux alias `aubooks-dev` с этой же командой в shell profile; он запускается короткой командой `aubooks-dev`. Для более устойчивого foreground tunnel добавить `-o ServerAliveCountMax=3`. Проверка: `curl -I http://127.0.0.1:8084/` в Termux или открыть URL в браузере. Остановка: `Ctrl-C`; для background запуска следует завершить только процесс этого SSH tunnel по его PID.

Проверка на VPS1: основной `/etc/ssh/sshd_config` содержит `PubkeyAuthentication yes`, не переопределяет default `AllowTcpForwarding yes` и имеет `GatewayPorts no`. Никакая server SSH-конфигурация не менялась. Полный loopback SSH-тест с VPS1 не выполнился, потому что у текущего окружения нет private key для аутентификации `feninf@localhost`; это не означает запрет forwarding. Фактическое подтверждение для телефона выполняется его уже настроенным ключом командой выше.
## Изменённые файлы
- `cps/themes/aubooks/templates/modal_dialogs.html` - минимальный macro shim, необходимый для runtime fallback layout.
- `docs/works/2026-08-30-calibre-web-dev-environment.md` - этот отчёт.
- Внешние от репозитория DEV artifacts: `.venv`, `/home/feninf/calibre-web-dev-data/`, `/home/feninf/.config/systemd/user/calibre-web-dev.service`.
## Ограничения
- Тестовая библиотека пуста; для проверки карточек, обложек, скачивания и readers нужно позже добавить отдельную малую тестовую книгу в DEV library.
- Проверка Android tunnel требует запуск команды на самом телефоне с его существующим private key. Порт 8084 остаётся недоступным извне независимо от этой проверки.
## Commit
Коммит не создавался.
