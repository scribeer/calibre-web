# Глобальная permission-политика OpenCode на VPS1
## Цель
Настроить OpenCode 1.18.25 так, чтобы чтение доступных пользователю `feninf` данных и обычная диагностика не требовали подтверждения, изменения были автоматически разрешены только в трёх рабочих областях, а внешние и системные изменения требовали `ask`.
## Изучено
- Установлена OpenCode 1.18.25: `/home/feninf/.opencode/bin/opencode --version`.
- Схема `https://opencode.ai/config.json` и `opencode debug config` подтвердили keys `read`, `glob`, `grep`, `list`, `edit`, `bash`, `external_directory` и pattern-based правила.
- В объектах permission последнее совпавшее правило имеет приоритет, поэтому broad default расположен раньше специальных rules.
- Все три Web service используют один глобальный config `/home/feninf/.config/opencode/opencode.jsonc`; project-level OpenCode configs в `/home/feninf/bin`, `/home/feninf/office-docs` и `/home/feninf/calibre-web` отсутствуют.
## Backup
- До изменения создан `/home/feninf/.config/opencode/opencode.jsonc.backup-20260830-1700`.
## Итоговая политика
- `read`, `glob`, `grep`, `list`: global `allow` для всех путей, доступных Unix-пользователю `feninf`.
- `external_directory`: global `allow`; нахождение вне workspace не создаёт отдельный `ask` для чтения.
- `edit`: default `ask`; `allow` только для `/home/feninf/bin/**`, `/home/feninf/office-docs/**`, `/home/feninf/calibre-web/**`.
- `bash`: default `ask`; диагностические команды (`ls`, `cat`, `grep`, `find`, `stat`, `git status/diff/log/show`, `journalctl`, read-only `systemctl` и другие перечисленные commands) имеют `allow`.
- `sudo`, destructive file commands, управляющие `systemctl` commands и log-maintenance flags `journalctl --vacuum/--rotate` явно оставлены `ask`.
## Применение
- Перезапущены `opencode-web.service`, `opencode-office-web.service`, `opencode-calibre-web.service`.
- Текущая задача не инициировала повторный restart после восстановления соединения.
- Все три сервиса active; health checks `http://127.0.0.1:4096/health`, `:4097/health`, `:4098/health` вернули HTTP 200.
## API-проверки
Проверки выполнены после restart через реальный API `POST /api/session/{sessionID}/permission` сервиса на `127.0.0.1:4098`; это только оценка permission и не выполняет команды или изменения файлов. Проверки рабочих областей дополнительно созданы на их собственных Web service: `/home/feninf/bin` на 4096 и `/home/feninf/office-docs` на 4097.
| Операция | Ожидается | Фактически |
| --- | --- | --- |
| чтение `/etc/passwd` | allow | allow |
| чтение `/home/feninf/translate/` | allow | allow |
| чтение `/home/feninf/calibre-web/` | allow | allow |
| чтение `/home/feninf/bin/` | allow | allow |
| чтение `/home/feninf/office-docs/` | allow | allow |
| `git status --short` | allow | allow |
| `journalctl --user -u opencode-calibre-web.service --no-pager` | allow | allow |
| `systemctl --user status opencode-calibre-web.service --no-pager` | allow | allow |
| изменение `/home/feninf/calibre-web/.opencode-permission-test` | allow | allow |
| изменение `/home/feninf/calibre-web/cps/themes/aubooks/.opencode-permission-test` | allow | allow |
| изменение `/home/feninf/bin/.opencode-permission-test` | allow | allow |
| изменение `/home/feninf/office-docs/.opencode-permission-test` | allow | allow |
| изменение `/etc/opencode-permission-test` | ask | ask |
| изменение `/var/opencode-permission-test` | ask | ask |
| изменение `/tmp/opencode-permission-test` | ask | ask |
| `sudo id` | ask | ask |
| `rm /etc/opencode-permission-test` | ask | ask |
## Очистка тестов
`ask`-запросы были отклонены через permission API. Проверка pending requests вернула пустой массив. Никакие реальные системные, project или test-файлы не создавались и не менялись.
## Изменённые файлы
- `/home/feninf/.config/opencode/opencode.jsonc` - глобальная policy OpenCode.
- `docs/works/2026-08-30-opencode-permission-policy.md` - этот отчёт.
## Ограничения
- `bash` pattern matching не анализирует смысл произвольной команды. Поэтому default `ask` сохранён, а allow выдан только диагностическим command patterns; новые mutating commands не становятся разрешёнными автоматически.
- Резервная копия конфигурации хранится рядом с активной конфигурацией и не должна редактироваться.
## Commit
Коммит не создавался.
