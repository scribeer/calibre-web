# Аудит Calibre-Web перед дальнейшей DEV-разработкой
## Цель
Подтвердить состояние форка AU-Books, темы, OpenCode Web и изолированного DEV Calibre-Web перед дальнейшей разработкой, не затрагивая production на VPS2.
## Границы аудита
- Проверен локальный каталог `/home/feninf/calibre-web` и пользовательские systemd units на текущем сервере.
- Production VPS2 не открывался, не изменялся и не перезапускался; deploy не выполнялся.
- OpenCode Web и DEV Calibre-Web не перезапускались этой задачей.
- Выполнялись только read-only диагностика, проверки синтаксиса с cache в `/tmp/opencode` и создание этого отчёта.
## Git и ветки
- Текущая ветка: `aubooks`, HEAD `c60bc33c` (`Add AU-Books development instructions`). Ветка отслеживает `origin/aubooks` и не расходится с ней.
- `master` находится на `a9782640`, отслеживает `origin/master` и не содержит AU-Books-разработку. `aubooks` опережает `master` на один коммит, добавляющий только `AGENTS.md`.
- Read-only `git ls-remote upstream master Develop` подтвердил, что текущий `master` точно совпадает с `upstream/master` (`a9782640`). Upstream `Develop` находится на `53afea26` и новее; локального remote-tracking ref `upstream/*` нет, поскольку fetch не выполнялся.
- `origin`: `https://github.com/scribeer/calibre-web.git` для fetch и push.
- `upstream`: `https://github.com/janeczku/calibre-web.git` для fetch и push.
- `git fsck --full` завершился без ошибок.
- Staged-изменений нет. Тема, DEV-отчёты и этот аудит существуют только в рабочем дереве и ещё не входят в `origin/aubooks`.
### Состояние рабочего дерева до создания этого отчёта
```text
 M cps/themes.py
 M cps/themes/standard/templates/layout.html
?? .venv/
?? cps/static/css/aubooks.css
?? cps/themes/aubooks/
?? docs/
```
- Tracked upstream-файлы изменены только в `cps/themes.py` и `cps/themes/standard/templates/layout.html`: всего 15 добавленных строк.
- `.venv/` не покрывается текущим `.gitignore`: игнорируются `env/` и `venv/`, но не `.venv/`. Поэтому `git status --untracked-files=all` включает всё окружение и не является удобно контролируемым.
## AGENTS.md и документация
- Действующая инструкция найдена в корне: `AGENTS.md`. Она правильно разделяет чистый `master` и рабочий `aubooks`, запрещает автоматические production-действия и требует русские отчёты в `docs/works/`.
- `docs/works/` используется. Оба обязательных отчёта присутствуют: `docs/works/2026-08-30-calibre-web-ui-architecture.md` и `docs/works/2026-08-30-aubooks-theme-bootstrap.md`.
- Также присутствуют отчёты о permission policy и DEV environment.
- Все файлы `docs/` пока untracked, поэтому отсутствуют в clone ветки и могут быть случайно потеряны.
- В `2026-08-30-aubooks-theme-bootstrap.md` строки об уже выполненной runtime-проверке и оставшейся необходимости такой проверки противоречат друг другу. Runtime-проверка фактически выполнена и повторно подтверждена этим аудитом.
- `AGENTS.md` требует отчёт, но не требует отдельный commit. Commit в рамках аудита не создавался.
## Тема AU-Books
- В `cps/themes.py` тема зарегистрирована с уникальным для текущего реестра integer ID `3`, identifier `aubooks`, label `AU-Books` и `configurable=True`.
- `get_available_themes()` включает тему в административный выбор; `is_valid_theme(3)` принимает её. DEV app.db фактически хранит `config_theme=3`.
- `cps/themes/aubooks/info.json` содержит совпадающие `identifier=aubooks` и `application=cps`; имя каталога также `aubooks`.
- `cps/themes/aubooks/templates/layout.html` наследует `_themes/standard/layout.html` и переопределяет только block `theme_css`.
- Standard fallback реализован существующим `themed_render`: отсутствующий top-level AU-шаблон рендерится из `standard`, при этом активная тема остаётся `aubooks`. Runtime запросы `/` и `/login` возвращают HTTP 200 и используют standard page templates с AU layout.
- `modal_dialogs.html` является минимальным proxy для пяти macros standard. Он необходим, потому что standard layout импортирует macros через активную тему.
- `cps/static/css/aubooks.css` подключается через `url_for('static', filename='css/aubooks.css')` только из AU layout. Runtime запрос CSS возвращает HTTP 200, а HTML главной содержит `/static/css/aubooks.css`.
- Массового копирования шаблонов нет: у темы только `layout.html` и необходимый macro proxy. Page templates не копировались.
- Лишних backend-изменений нет: единственная Python-правка регистрирует тему.
- CSS пока содержит только комментарий. Это корректно для bootstrap без визуальных изменений, но дизайн и accessibility AU-Books ещё не реализованы.
## Fallback и пути
- Jinja parse успешно выполнен для AU layout, AU modal proxy и standard layout.
- Жёсткие пути `_themes/standard/layout.html` и `_themes/standard/modal_dialogs.html` соответствуют текущей структуре Flask-Themes2.
- Application static path `cps/static/css/aubooks.css` соответствует URL `/static/css/aubooks.css`.
- Fallback подтверждён не только статически, но и работающим DEV runtime.
- Ограничение: обработчик `TemplateNotFound` охватывает весь render. Ошибка nested include/import также может быть воспринята как отсутствие top-level AU template. Это существующая архитектура, не новая ошибка темы.
- Ограничение: macro proxy потребуется синхронизировать, если upstream изменит набор импортируемых macros.
- Standalone templates, например HTTP error и readers, могут не наследовать AU layout. `/basic` намеренно принудительно использует тему `simple`.
## Upstream-совместимость
- `cps/themes.py`: минимальная правка, но центральный реестр может конфликтовать при добавлении upstream-темы с ID `3`. Тема хранится в БД как integer, поэтому коллизию нельзя игнорировать при update.
- `cps/themes/standard/templates/layout.html`: добавлена ровно одна нейтральная строка `{% block theme_css %}{% endblock %}` после общих CSS. Она не меняет standard/caliblur/simple и позволяет AU layout подключить CSS последним.
- Правка `standard/layout.html` оправдана и существенно безопаснее копирования всего layout в AU-тему. Уменьшить её без дублирования 191-строчного upstream layout или изменения общей загрузки ресурсов практически нельзя.
- Риск merge-конфликта мал по объёму, но файл центральный. Потеря block при update приведёт к тихому исчезновению AU CSS, поэтому это нужно покрывать smoke-проверкой после каждого upstream merge.
- Текущее сравнение точно относится к `upstream/master`. Совместимость с более новым `upstream/Develop` не проверялась и не требуется для текущего clean-master workflow.
## Проверки качества
- `git diff --check` — успешно.
- `.venv/bin/python -m py_compile cps/themes.py` с `PYTHONPYCACHEPREFIX=/tmp/opencode/calibre-web-audit-pycache` — успешно.
- JSON parse и проверки `identifier/application` для `info.json` — успешно.
- Jinja parse трёх затронутых templates — успешно.
- `.venv/bin/python -m pip check` — `No broken requirements found`.
- `git fsck --full` — успешно.
- HTTP smoke: OpenCode `4098` — 200; DEV `/`, `/login`, AU CSS — 200.
- Полный browser, keyboard, screen reader и тест с реальной книгой не выполнялись.
## OpenCode Web
- User unit: `/home/feninf/.config/systemd/user/opencode-calibre-web.service`.
- `WorkingDirectory=/home/feninf/calibre-web`.
- ExecStart использует `opencode web --hostname 127.0.0.1 --port 4098`.
- Service enabled и `active (running)`; версия OpenCode `1.18.25`.
- Listener подтверждён только на `127.0.0.1:4098`.
- `GET /health` возвращает HTTP 200, но body является HTML SPA, а не содержательным health payload. Это подтверждает доступность процесса, но не внутреннее состояние.
- Во время аудита журнал показал рестарты в `04:42:47` и `04:45:49 UTC`, инициированные не этой задачей. Текущий service стабилен после последнего запуска.
- `OPENCODE_SERVER_PASSWORD` не задан; журнал прямо отмечает server как unsecured. Loopback bind не публикует его напрямую, но локальные процессы и SSH port forwarding остаются моделью доступа.
## OpenCode permissions
- Эффективная конфигурация из `opencode debug config`: `read=allow`, `external_directory=allow`, глобальные `edit=allow` и `bash "*"=allow`; только отдельные опасные команды имеют `ask`.
- Обычному чтению и работе внутри `/home/feninf/calibre-web` политика не мешает.
- Политика существенно шире описанной в `docs/works/2026-08-30-opencode-permission-policy.md`, где edit должен быть ограничен рабочими областями, а bash по умолчанию должен быть `ask`.
- Сочетание отсутствия OpenCode password и глобальных edit/bash permissions является предупреждением безопасности, даже при loopback bind. Это не блокирует разработку, но должно быть осознанно исправлено отдельной задачей.
## DEV Calibre-Web
- `.venv` существует; Python 3.10.12, Calibre-Web `0.6.28 Beta`. Зависимости установлены и `pip check` проходит.
- User unit `/home/feninf/.config/systemd/user/calibre-web-dev.service` существует, enabled и active.
- Unit использует только `.venv/bin/python`, `WorkingDirectory=/home/feninf/calibre-web` и bind `127.0.0.1`.
- Listener подтверждён только на `127.0.0.1:8084`; наружу порт не открыт.
- Отдельные данные находятся в `/home/feninf/calibre-web-dev-data`: `app.db`, `gdrive.db`, cache, log и `library/metadata.db`.
- Unit явно передаёт DEV app.db/gdrive.db/log и DEV cache. В app.db подтверждены library path `/home/feninf/calibre-web-dev-data/library`, порты `8084`, theme `3`, title `AU-Books DEV`.
- `PRAGMA integrity_check` для DEV app.db и metadata.db вернул `ok`.
- Признаков подключения к production app.db/metadata.db, VPS2 endpoints или внешних TCP-соединений процесса не найдено.
- DEV этап уже выполнен; это не `NOT DONE`. Незавершён только функциональный тест с отдельной тестовой книгой.
## Безопасность и version control
- Эта задача не обращалась к production VPS2 и не меняла его.
- OpenCode `4098` и DEV `8084` слушают только IPv4 loopback. Внешние application listeners не обнаружены.
- В tracked Git-файлах сигнатуры private keys и типовых API tokens не найдены. Специализированные `gitleaks`/`detect-secrets` в окружении не установлены, поэтому использована эвристическая проверка; найденные password-совпадения относятся к полям и логике приложения, не к встроенным секретам.
- В `.venv` есть test private key из пакета Tornado. Это dependency fixture, не tracked secret, но из-за отсутствия `.venv/` в `.gitignore` весь venv потенциально можно случайно добавить.
- `.gitignore` покрывает `*.db`, `*.log`, `.key`, credential JSON. Реальные DEV runtime-файлы расположены вне repository root.
- `library/metadata.db` уже tracked как исходная пустая тестовая библиотека. Это не активная DEV/production БД; DEV использует отдельную копию.
## Таблица статусов
| Компонент | Статус | Комментарий |
| --- | --- | --- |
| Git | WARNING | Репозиторий цел, staged нет, но тема/docs untracked и `.venv/` создаёт неконтролируемый шум. |
| ветка aubooks | OK | Текущая ветка правильная, синхронизирована с `origin/aubooks`; AU-работа не ведётся в `master`. |
| upstream | OK | URL правильный; `master` совпадает с `upstream/master`. Локальных `upstream/*` refs нет. |
| AGENTS.md | OK | Инструкции найдены и соответствуют модели AU-Books. |
| docs/works | WARNING | Обязательные отчёты есть, но весь каталог пока untracked; один отчёт содержит устаревшее ограничение. |
| тема aubooks | WARNING | Регистрация и runtime работают, но реализация ещё не зафиксирована в Git и CSS пока пуст. |
| fallback | OK | Standard fallback и macro proxy подтверждены статически и HTTP runtime. |
| CSS | WARNING | Подключается только для AU layout и отдаётся с 200, но пока не содержит дизайна. |
| upstream compatibility | WARNING | Изменения минимальны; остаются риски ID `3`, macro proxy и одной строки в центральном layout. |
| OpenCode 4098 | WARNING | Active, HTTP 200, только localhost; password не задан, `/health` не является полноценным health API. |
| permissions | WARNING | Работе не мешают, но фактически глобальные edit/bash allow шире документированной политики. |
| Python DEV venv | WARNING | Существует, зависимости исправны, но `.venv/` не игнорируется Git. |
| Calibre-Web DEV service | OK | Enabled/active, HTTP 200, только `127.0.0.1:8084`. |
| DEV database/config | OK | Отдельные целые DB/config/cache/log вне репозитория, theme `3`, порт `8084`. |
| production isolation | OK | DEV paths и listeners изолированы; production VPS2 этой задачей не затрагивался. |
## Итоговая оценка
### Сделано правильно
- Ветки и remotes соответствуют принятой модели; чистый `master` совпадает с canonical `upstream/master`.
- Тема зарегистрирована минимально, выбирается, наследует standard и использует рабочий fallback без массового копирования templates.
- Единственная правка standard layout является малой и обоснованной extension point.
- DEV полностью поднят отдельно: собственные venv, service, app.db, metadata.db, cache/log и localhost port `8084`.
- Production isolation подтверждается unit paths, DB config и listeners.
### Требует исправления
- Добавить `.venv/` в ignore, чтобы исключить случайное добавление зависимостей и test key fixture.
- Привести effective OpenCode permissions в соответствие с задокументированной ограниченной политикой и отдельно решить вопрос локальной аутентификации Web UI.
- Удалить противоречие о runtime discovery из bootstrap-отчёта.
- Атомарно зафиксировать тему и отчёты в `aubooks`, иначе remote branch не содержит выполненной работы.
### Ещё не сделано
- Собственный AU-Books дизайн и accessibility improvements: CSS пуст, layout пока полностью наследует standard UI.
- Browser/keyboard/screen-reader проверки и функциональная проверка на отдельной тестовой книге.
### Блокеры
Кодовых или инфраструктурных блокеров дальнейшей разработки нет. DEV готов. До начала содержательных UI-изменений желательно сначала устранить риск неконтролируемого рабочего дерева и сохранить текущий bootstrap как атомарную исходную точку.
## Один следующий шаг
Подготовить один контролируемый baseline commit в `aubooks`: добавить `.venv/` в `.gitignore`, исправить устаревшую строку отчёта и атомарно зафиксировать bootstrap темы вместе с `docs/works`. Этот шаг данным аудитом не начинался.
## Изменённые файлы
- `docs/works/2026-08-31-calibre-web-pre-dev-audit.md` — создан этот отчёт.
## Известные ограничения
- Не выполнялись fetch/merge, сравнение с `upstream/Develop`, browser automation, screen reader и firewall/nftables-проверка с root-доступом.
- Проверка секретов эвристическая из-за отсутствия специализированного scanner.
- Утверждение о production означает отсутствие действий и ссылок в проверенной локальной конфигурации; независимое состояние VPS2 намеренно не проверялось.
## Commit
Коммит не создавался: `AGENTS.md` требует отчёт, но не требует commit после каждого аудита.
