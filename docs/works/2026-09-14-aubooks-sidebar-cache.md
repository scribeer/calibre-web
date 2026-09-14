# Кеширование дерева жанров AU-Books
## Цель
Устранить повторное выполнение тяжёлого SQL построения genre sidebar на каждом HTTP-запросе и не строить дерево на странице входа.
## Что изучено
- Путь рендера через `render_title_template()` и `_get_aubooks_sidebar_genre_tree()`.
- Жизненный цикл прежнего кеша во `flask.g`, ограниченный одним запросом.
- Время ответов `/`, `/login`, `/category` и canonical страницы книги на DEV-каталоге из 122463 книг.
- Наличие genre sidebar в итоговом HTML проверенных страниц.
## Изменённые файлы
- `cps/render_template.py`.
- `tests/test_aubooks_sidebar_cache.py`.
- `docs/works/2026-09-14-aubooks-sidebar-cache.md`.
## Что изменено
- Готовое дерево кешируется в памяти процесса между HTTP-запросами.
- Ключ кеша содержит путь к `metadata.db` и `st_mtime_ns`; изменение mtime заставляет следующий запрос перестроить дерево.
- Lock не допускает параллельного выполнения одинакового тяжёлого SQL при заполнении кеша.
- Для `login.html` дерево не строится.
- SQL и структура дерева жанров не изменены.
## Проверки
- `.venv/bin/python -m pytest -q tests/test_aubooks_sidebar_cache.py tests/test_aubooks_guest_sidebar.py tests/test_aubooks_genres.py`: 139 passed, 245 subtests passed.
- `.venv/bin/python -m py_compile cps/render_template.py tests/test_aubooks_sidebar_cache.py`: успешно.
- DEV HTTP 200: `/`, `/login`, `/category`, `/books/georgiy-persikov/delo-o-medvezhem-posohe`.
- Genre sidebar присутствует на `/`, `/category` и странице книги; на `/login` отсутствует.
- Медианы до изменения: `/` 1.807 с, `/login` 0.755 с, `/category` 0.694 с, книга 0.683 с.
- Медианы после прогрева кеша: `/` 1.190 с, `/login` 0.016 с, `/category` 0.705 с, книга 0.070 с.
## Известные ограничения
- Кеш локален для процесса; каждый worker заполняет собственный кеш после запуска или изменения `metadata.db`.
- `/category` выполняет собственный aggregate запрос категорий и не ускоряется этим изменением.
- Остальные ранее найденные N+1, SEO, TTS, OpenDrive и UI проблемы не изменялись.
## Commit
Текущий commit, включающий этот отчёт.
