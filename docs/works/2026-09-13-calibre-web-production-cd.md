# Production CD contract для AU-Books Calibre-Web
## Цель
Подготовить Phase 2A ручного production deploy без выполнения deploy: оператор указывает полный commit SHA из `aubooks`, workflow принимает только успешный CI artifact этого SHA, повторно проверяет его и формирует однозначный bundle для ограниченного production-side helper.
## Что изучено
- Действующий `.github/workflows/ci-aubooks.yml`, имя artifact и поля `artifact-manifest.json`.
- Wheel packaging metadata и console entry point в `pyproject.toml`.
- Production-настройка темы: таблица `settings`, колонка `config_theme`, AU-Books theme `3:aubooks`.
- Существующие shell/test conventions репозитория; конфликтующего deploy workflow или helper не было.
## Exact artifact selection
Workflow запускается только через `workflow_dispatch` с обязательным полным 40-символьным SHA. GitHub API подтверждает существование commit, его принадлежность истории `aubooks` и exact CI run с `head_sha`, branch `aubooks`, event `push`, workflow path `.github/workflows/ci-aubooks.yml` и conclusion `success`.
Artifact выбирается по имени `calibreweb-aubooks-${commit_sha}` только внутри найденного run, после чего скачивается по immutable artifact ID. Отсутствующий, пустой, expired или связанный с другим run/SHA artifact отклоняется; последний успешный artifact никогда не используется как fallback. Локальная сборка в deploy workflow отсутствует.
## Bundle contract
До remote-вызова workflow проверяет manifest repository/SHA/ref/run/attempt/version, SHA-256 wheel, `SHA256SUMS`, ZIP-целостность и минимальный runtime layout AU-Books/invite без `library/`. Временный `deploy-bundle/` содержит wheel, `SHA256SUMS`, `artifact-manifest.json` и `deploy-request.json` с requested SHA, wheel metadata, CI run metadata, repository, actor и UTC-временем запроса.
## Security model
- Job использует GitHub environment `production`, `contents: read` и `actions: read`; `GITHUB_TOKEN` применяется только к GitHub API и artifact download.
- Workflow не запускается по push и имеет non-cancelling concurrency group `calibre-web-production`.
- SSH требует заранее доверенный `VPS2_KNOWN_HOSTS`; динамическое получение host key и отключение проверки запрещены.
- Host, port, user и public URL проходят format validation до transport.
- Remote command фиксирован: versioned helper `/usr/local/sbin/aubooks-deploy-calibre-web` получает только фиксированный staging path и уже проверенный hex SHA. Пользовательский input не интерпретируется как shell program.
- Helper требует non-root `User` в systemd unit; установка binary-only dependencies, `cps --help` и candidate imports выполняются от этого service user, а проверенный wheel копируется в root-controlled release path с повторной проверкой SHA-256.
- Отсутствующая production configuration приводит к явному fail до SSH.
## Release layout
Helper проектируется для `/opt/calibre-web/{current,releases,backups,config,library}`. `current` обязан быть symlink на существующий каталог внутри `releases/`; databases остаются вне release. Если release layout ещё не создан, обычный режим останавливается с `INITIAL_MIGRATION_REQUIRED`, а dry-run сообщает необходимость отдельной initial migration. Silent migration отсутствует.
## Deploy and theme contract
Normal path предусматривает lock, SQLite integrity check/backup, backup `gdrive.db`, сохранение previous target, clean release venv, wheel install, `pip check`, `cps --help`, AU theme/invite imports, atomic symlink switch, controlled service restart, health checks и deployed manifest.
Текущее `config_theme` читается из единственной строки `settings`. Значение `3` не изменяется. Иное значение меняется транзакционно только после backup `app.db` и проверки candidate theme `3:aubooks`; dry-run только показывает план.
## Health and rollback
Health contract проверяет active systemd unit, LISTEN на `127.0.0.1:8083`, local HTTP, public HTTPS, login и отсутствие startup traceback. Медленный local HTTP допускается только при одновременно успешных service, port, public HTTPS и login checks.
При ошибке rollback возвращает previous `current`, восстанавливает backup `app.db`, если theme DB менялась, перезапускает previous release и повторяет health check. Failed release и его данные сохраняются; deploy завершается ошибкой даже после успешного rollback.
## Required production configuration
- Secret: `VPS2_DEPLOY_SSH_KEY`.
- Variables: `VPS2_HOST`, `VPS2_SSH_PORT`, `VPS2_DEPLOY_USER`, `VPS2_KNOWN_HOSTS`, `AUBOOKS_PUBLIC_URL`.
- Phase 2A не создаёт и не изменяет GitHub environment, secret или variable.
## Изменённые файлы
- `.github/workflows/deploy-production.yml`
- `.github/workflows/ci-aubooks.yml`
- `deploy/vps2/deploy-calibre-web-release.sh`
- `tests/test_calibre_web_deploy_helper.py`
- `docs/works/2026-09-13-calibre-web-production-cd.md`
## Проверки
- YAML syntax и shell run blocks проверены локально.
- Helper прошёл `bash -n`; `shellcheck` в локальном окружении отсутствует.
- Hermetic helper tests проверяют invalid SHA, missing bundle, checksum mismatch, manifest SHA mismatch, legacy layout, отсутствие изменений в dry-run, неизменность theme 3 и previous release rollback plan.
- Расширенный CI suite: `109 passed`.
- На опубликованном artifact Phase 1 локально воспроизведены GitHub API ancestry/exact-run gate, exact artifact metadata gate, manifest/runtime/archive verification и `SHA256SUMS`.
- `git diff --check` и security grep выполнены перед commit.
## Известные ограничения
- Initial migration legacy production layout намеренно не реализована.
- Helper не устанавливается на server автоматически; размещение fixed privileged wrapper и least-privilege sudo policy является отдельной будущей операционной задачей.
- Remote workflow не запускался; production, VPS2, databases и services не затрагивались.
## Commit
Изменения подготовлены одним commit `ci: prepare safe Calibre-Web production deploy`; push не выполняется.
