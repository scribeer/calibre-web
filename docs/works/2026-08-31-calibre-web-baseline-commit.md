# Baseline commit AU-Books
## Цель
Зафиксировать проверенный bootstrap темы AU-Books и документацию как чистую исходную точку перед дальнейшим дизайном.
## Изучено
- Проверены рабочая ветка `aubooks`, tracked и untracked изменения.
- Повторно проверены регистрация темы, metadata, наследование standard layout, macro proxy, CSS и `theme_css` extension point.
- Проверены правила исключения virtualenv, DEV databases, logs, cache, ключей и локальных runtime-конфигов.
## Изменённые файлы
- `.gitignore` — добавлено правило `.venv/`.
- `cps/themes.py`, `cps/themes/aubooks/`, `cps/static/css/aubooks.css` и `cps/themes/standard/templates/layout.html` — зафиксирован ранее проверенный bootstrap темы.
- `docs/works/` — зафиксированы отчёты выполненных работ; в отчёте bootstrap устранено устаревшее ограничение о невыполненной runtime-проверке.
## Проверки
- `git diff --check` и проверка staged diff — успешно.
- `python3 -m py_compile cps/themes.py` — успешно.
- JSON validation `info.json` — успешно.
- Jinja parse AU и standard templates — успешно.
- `.venv/bin/python -m pip check` — успешно.
- DEV HTTP smoke `/`, `/login`, `/static/css/aubooks.css` — HTTP 200; AU CSS подключён в HTML.
- В baseline commit не включены `.venv`, DEV DB, logs, secrets, runtime cache и production-файлы.
## Ограничения
- Собственный дизайн AU-Books ещё не реализован; CSS остаётся пустой точкой расширения.
- Production VPS2 не затрагивался, push не выполнялся.
## Commit
Baseline commit: `753ffb8936ca472836a1d66e4cbf226d6428192e` (`Add AU-Books theme bootstrap and development baseline`).
Этот отчёт фиксируется отдельным документационным commit, поскольку commit не может содержать собственный итоговый hash.
