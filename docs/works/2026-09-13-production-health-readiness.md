# Ожидание готовности Calibre-Web после restart
## Цель
Устранить race condition между успешным `systemctl restart` для `Type=simple` и фактической готовностью CPS принимать HTTP-запросы.
## Что изучено
- Текущий однократный `health_check` в production deploy helper.
- Общий вызов `health_check` после основного deploy и во время rollback.
- Герметичные non-dry deploy tests и test doubles для systemd, порта и HTTP.
## Изменённые файлы
- `deploy/vps2/deploy-calibre-web-release.sh`.
- `tests/test_calibre_web_deploy_helper.py`.
- `docs/works/2026-09-13-production-health-readiness.md`.
## Что изменено
- Добавлен bounded readiness loop: timeout 30 секунд, interval 1 секунда.
- На каждой итерации проверяется service state, затем LISTEN на `127.0.0.1:8083`, затем local HTTP.
- Local HTTP повторяется после появления порта до успеха или общего timeout.
- Состояния `failed`, `inactive` и `deactivating` завершают проверку досрочно.
- Timeout выводит service state, port state, последний HTTP result и последние 100 строк journal.
- После public/login и journal checks состояние service повторно проверяется.
- Основной deploy и rollback используют одну и ту же функцию без отдельных обходов.
## Проверки
- `bash -n` для deploy scripts.
- `git diff --check`.
- `python3 -m pytest tests/test_calibre_web_deploy_helper.py -q`: 70 passed.
- Regression tests delayed port, delayed HTTP, early service failure, port timeout, delayed rollback startup и multi-second startup.
- Clean venv install smoke, `pip check`, `cps --help`.
## Известные ограничения
- Production и VPS2 не изменялись; deploy не запускался.
- Локальный smoke выполнен на доступном Python 3.10; Python 3.12 проверяется CI build job.
## Commit
Commit задачи: `fix: wait for Calibre-Web startup readiness`.
