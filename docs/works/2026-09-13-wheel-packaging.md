# Подготовка AU-Books wheel
## Цель
Сделать ветку `aubooks` устанавливаемой через wheel с layout, совместимым с официальным `calibreweb` и production venv, без изменения runtime-функциональности.
## Что изучено
- `pyproject.toml`, `MANIFEST.in`, source layout и импорты `cps`.
- Официальный wheel `calibreweb==0.6.27`, загруженный в `/tmp`: package расположен в `calibreweb/cps`, wrapper `calibreweb/__main__.py` добавляет каталог `calibreweb` в `sys.path`, console entry point равен `cps = calibreweb.__main__:main`.
- В Git checkout отсутствует ожидаемый metadata каталог `src/calibreweb`; runtime-код находится в корневом `cps/`.
- `library/metadata.db` является локальной Calibre-библиотекой, а не Python package. Автоматический namespace-discovery ошибочно находил `cps` и `library` как два top-level package.
## Что изменено
- В `pyproject.toml` задан явный список packages и mapping `cps/` в `calibreweb.cps`; `library/` не входит в список.
- В `MANIFEST.in` ссылки приведены к реальным source-путям `calibreweb/` и `cps/`.
- Добавлены минимальные wrappers `calibreweb/__init__.py` и `calibreweb/__main__.py`, сохраняющие официальный launcher contract и существующие абсолютные импорты `cps.*`.
- Runtime-файлы `cps/` не переносились и не менялись.
## Изменённые файлы
- `pyproject.toml`
- `MANIFEST.in`
- `calibreweb/__init__.py`
- `calibreweb/__main__.py`
- `docs/works/2026-09-13-wheel-packaging.md`
## Проверки
- `/tmp/opencode/calibreweb-build-venv/bin/python -m build --wheel`: успешно создан `calibreweb-0.6.28b0-py3-none-any.whl`.
- Archive audit: все 972 tracked-файла из `cps/` присутствуют; AU-Books templates, CSS, Python modules и invite implementation присутствуют; `library/` отсутствует.
- Установка wheel со всеми dependencies в отдельный `/tmp/opencode/calibreweb-wheel-test-venv`: успешно.
- `cps --help` из `/tmp/opencode/calibreweb-wheel-run`: успешно.
- Импорты из каталога вне checkout: `calibreweb`, `cps`, AU-Books theme `3:aubooks`, invite model/helpers/routes/admin handler импортируются из `site-packages/calibreweb`; checkout отсутствует в `sys.path`.
- `pytest -q tests/test_invite_model.py tests/test_invite_registration.py tests/test_invite_admin.py tests/test_aubooks_registration.py tests/test_aubooks_theme_templates.py`: `101 passed`.
- `git diff --check`: успешно.
## Известные ограничения
- Системный `pip 22.0.2` некорректно обработал современную PEP 621 metadata и создал тестовый `UNKNOWN-0.0.0` wheel. Итоговая проверка выполнена через актуальный `build 1.6.1` в отдельном временном venv; ошибочный артефакт не используется и удалён из checkout.
- Реальный server process не запускался, production и DEV databases не подключались.
## Commit
Изменения подготовлены для одного отдельного commit без push.
