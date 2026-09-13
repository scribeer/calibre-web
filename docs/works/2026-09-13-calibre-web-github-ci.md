# GitHub Actions CI для AU-Books Calibre-Web
## Цель
Заменить ручную сборку wheel воспроизводимой автоматической проверкой каждого изменения ветки `aubooks`. CI должен рано выявлять несовместимость поддерживаемых версий Python и не допускать создание артефакта из кода, который не прошёл тесты, проверку содержимого wheel и изолированную установку.
## Что изучено
- Состояние ветки `aubooks`, packaging commit `e657347f`, `pyproject.toml`, `requirements.txt` и `MANIFEST.in`.
- Существующий package layout `calibreweb/cps`, console entry point `cps` и состав wheel, подготовленный packaging commit.
- Hermetic-тесты invite-механизма, регистрации и AU-Books theme templates.
- Существующие GitHub Actions workflows: конфликтующих workflows в репозитории не было.
## Архитектура CI
- Workflow запускается для `push` и `pull_request`, направленных в `aubooks`, с разрешением только `contents: read`.
- Concurrency объединяет запуски по workflow и Git ref; новый запуск отменяет незавершённый старый запуск той же ref.
- Job `test` выполняет matrix на Python 3.10 и 3.12, устанавливает зависимости из `requirements.txt` и отдельный фиксированный pytest, компилирует `cps` и `calibreweb`, затем запускает выбранный hermetic suite.
- Job `build` зависит от успешного завершения всей test matrix, использует Python 3.12 и `build==1.6.1`.
- После сборки CI проверяет ZIP-целостность wheel, обязательные package-файлы, AU-Books templates, CSS и модули, invite implementation, отсутствие `library/` и console entry point.
- Wheel устанавливается с зависимостями в новый venv и проверяется из каталога вне checkout. Проверка подтверждает отсутствие checkout в `sys.path`, импорт package и AU-Books модулей, theme contract `3:aubooks` и доступность invite model/helpers.
## Контракт артефакта
Для `push` в `aubooks` публикуется artifact `calibreweb-aubooks-${commit_sha}` со сроком хранения 90 дней. Он содержит ровно deployable wheel `calibreweb-*.whl`, `SHA256SUMS` и `artifact-manifest.json`.
Manifest фиксирует repository, commit SHA, Git ref, run ID, run attempt, имя и SHA-256 wheel, package version, Python version сборки и UTC-время сборки. SHA-256 повторно вычисляется при подготовке artifact и сверяется с результатом archive verification.
Для `pull_request` выполняются те же тесты, сборка, archive verification и isolated install, но artifact намеренно не публикуется.
## Изменённые файлы
- `.github/workflows/ci-aubooks.yml`
- `docs/works/2026-09-13-calibre-web-github-ci.md`
## Проверки
- YAML syntax проверен локальным parser.
- `python -m compileall -q cps calibreweb`: успешно.
- Выбранный hermetic suite: `101 passed`.
- `build==1.6.1` собрал `calibreweb-0.6.28b0-py3-none-any.whl`.
- Archive verification, установка wheel в новый venv, `cps --help` и импорты вне checkout: успешно.
- Локальные `artifact-manifest.json` и `SHA256SUMS` созданы; checksum подтверждён через `sha256sum -c`.
- `git diff --check` выполнен без ошибок.
- Workflow проверен на отсутствие secrets, SSH, deploy-команд и обращений к production/VPS.
## Известные ограничения
- CI не включает VPS1-specific integration tests.
- На локальной машине доступен только Python 3.10; matrix и build на Python 3.12 будут выполнены GitHub-hosted runner.
- GitHub-hosted runner и фактическая загрузка artifact будут окончательно подтверждены первым GitHub Actions run.
- CD намеренно отсутствует: workflow не подключается к серверам, не использует secrets, не выполняет deploy и не меняет сервисы.
## Commit
Изменения подготовлены одним commit `ci: build verified AU-Books wheel`; push не выполняется.
