# Сохранение metadata app.db при deploy и rollback
## Цель
Исключить смену владельца, группы и режима `/opt/calibre-web/config/app.db` при изменении темы и восстановлении базы после неуспешного deploy.
## Что изучено
- Транзакционное изменение `config_theme` в `deploy/vps2/deploy-calibre-web-release.sh`.
- Создание SQLite backup и замена production DB через временный файл при rollback.
- Существующие герметичные deploy/security tests.
## Изменённые файлы
- `deploy/vps2/deploy-calibre-web-release.sh`.
- `tests/test_calibre_web_deploy_helper.py`.
- `docs/works/2026-09-13-preserve-deploy-database-metadata.md`.
## Что изменено
- До backup сохраняются числовые UID/GID и mode исходного `app.db`.
- SQLite mutation выполняется от service user, чтобы не создавать root-owned DB/journal files.
- После успешной SQLite mutation исходные owner/group/mode дополнительно восстанавливаются явно.
- База помечается как потенциально изменённая до mutation, поэтому ошибка SQL также запускает восстановление backup.
- После атомарной замены `app.db` при rollback исходные owner/group/mode восстанавливаются до restart сервиса.
- Добавлены non-dry regression tests успешной смены темы и rollback после отказа restart.
## Проверки
- `bash -n` для deploy scripts.
- `python3 -m pytest tests/test_calibre_web_deploy_helper.py -v`.
- Герметичный rollback с реальными SQLite backup, mutation и restore.
- `git diff --check`.
## Известные ограничения
- Production и VPS2 не изменялись; реальный deploy не запускался.
- В тестах systemd, сеть, смена пользователя и privileged `chown` заменены герметичными test doubles; SQLite операции выполняются реально.
## Commit
Commit задачи: `fix: preserve app database metadata during deploy`.
