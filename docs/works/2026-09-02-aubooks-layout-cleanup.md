# Cleanup layout AU-Books
## Цель
Унифицировать breadcrumbs, сделать normal AU shell dark-first с чёрным фоном, убрать дублирующий text brand, расширить navbar search и визуально центрировать title detail без изменений backend/SEO.
## Что изучено
- AU templates `layout.html`, `detail.html`, `author.html`, `index.html`, `search.html`, `list.html`.
- Общий detail template и сохранённый DOM order.
- Route contexts author, series, category, search и detail.
- Light/dark/system variables и Bootstrap overrides в `aubooks.css`.
- Existing genre hierarchy и category tag-ID routes.
## Breadcrumbs
Breadcrumbs добавлены или унифицированы только в page templates; общий layout не создаёт автоматическую цепочку, поэтому дублирования нет.
- Detail: `Home → Жанры → Категория → основной жанр → Название книги`. Если tags отсутствуют, остаётся `Home → Название книги`.
- Author result: `Home → Authors → текущий author title`.
- Series result: `Home → Series → текущий series title`.
- Category result: `Home → Жанры → Категория → Жанр`.
- Category directory: `Home → Жанры`.
- Search: `Home → Search`; query остаётся только в `h1`, чтобы длинный запрос не дублировался в breadcrumb.
Каждая цепочка использует `<nav aria-label="Breadcrumb"><ol class="breadcrumb">`; последний `li` имеет `class="active" aria-current="page"`. Existing canonical и SEO URLs не изменялись.
## Чёрный фон и темы
Dark palette selector `[data-theme="dark"]` теперь задаёт `#000000` для:
- `--aubooks-bg`;
- `--aubooks-surface`;
- `--aubooks-surface-raised`;
- `--aubooks-control-bg`.
Те же значения заданы в `:root:not([data-theme])` внутри `prefers-color-scheme: dark` для no-JS/system-dark fallback. Hover/interactive state оставлен `#161616`, чтобы controls сохраняли различимые состояния. Text, links, borders и focus ring используют существующие contrast-aware semantic variables.
Дополнительный selector `html[data-theme="dark"], [data-theme="dark"] body, ...` явно закрепляет `background-color: #000000` на canvas, header, outer container, main, sidebar, footer, catalog, search results и detail.
Forms, dropdowns, modals, pagination, breadcrumbs, panels, wells, list groups и genre sections получают чёрный фон через общие dark surface variables и существующие Bootstrap overrides. Alert semantic surfaces оставлены цветными, поскольку передают статус.
### Интерпретация light mode
Требование интерпретировано как dark-first: explicit `dark` и `system` при системной dark preference используют полностью чёрный shell и surfaces. Explicit `light` не удалён и сохраняет светлую palette, иначе selector `Light` перестал бы соответствовать названию. Anti-FOUC/localStorage/runtime theme architecture не менялась.
## Brand area
Из AU `layout.html` удалён только `<a class="navbar-brand">{{instance}}</a>`. Верхний image logo, mobile navbar toggle, `<title>`, SEO `og:site_name` и instance footer не изменены. Пустого desktop brand offset нет: `.navbar-header` сохраняется только как контейнер необходимого mobile toggle и на desktop имеет нулевой flex footprint.
## Search layout
Search form получила класс `.aubooks-navbar-search`.
- Input group имеет `width: 100%`.
- На desktop navbar container использует flex с wrap; search задан `flex: 1 1 24rem`, без `max-width`, и забирает всё свободное место.
- Navigation/theme/account controls остаются auto-width и могут переноситься при недостатке места.
- На mobile search имеет `clear: both`, `width: 100%`, нулевые horizontal margins; input и submit button остаются одной Bootstrap input group и не перекрываются.
- Search backend/action/field names не менялись.
## Detail title
DOM и heading hierarchy не изменялись: единственный normal-page `h1#title` остаётся внутри `.book-meta` и раньше toolbar. CSS задаёт `text-align: center`.
На desktop title visual box расширяется до `133.333333%` с `margin-left: -33.333333%`, что компенсирует соседнюю 25% cover column и центрирует текст относительно всей detail row без JS или DOM reordering. Расширение остаётся внутри row geometry. На mobile дополнительная ширина не применяется, title остаётся centered в доступной области. Cover column и её существующий `20px` top alignment не изменены.
## Изменённые файлы
- `cps/themes/aubooks/templates/layout.html` — удалён text brand, добавлен search class.
- `cps/themes/aubooks/templates/detail.html` — unified breadcrumb с genre context.
- `cps/themes/aubooks/templates/author.html` — author breadcrumb.
- `cps/themes/aubooks/templates/index.html` — series и category breadcrumbs.
- `cps/themes/aubooks/templates/search.html` — search breadcrumb.
- `cps/themes/aubooks/templates/list.html` — category directory breadcrumb.
- `cps/static/css/aubooks.css` — black dark palette, shell surfaces, responsive navbar search и centered detail title.
## Проверки
- 27/27 unit tests успешно: SEO DB/URLs и AU genre mapping.
- Jinja parse: 11 templates успешно.
- JS syntax: `aubooks-pages.js`, `main.js`, `details.js` успешно; JS не изменялся.
- HTTP 200: home, search, author, series, category result, canonical detail после legacy redirect и login.
- DOM: на целевых result/detail pages ровно один breadcrumb; current item имеет `aria-current="page"`; first item ведёт на `/`.
- DOM: `.navbar-brand` отсутствует на всех проверенных страницах, `.aubooks-logo` и `.aubooks-navbar-search` присутствуют.
- Detail: один `h1`; `h1` остаётся раньше `.btn-toolbar`.
- Dark CSS: `#000000` tokens и explicit shell selector подтверждены; крупных white background declarations в dark overrides нет. `#ffffff` background остаётся только в light palette, остальные упоминания white используются как text color.
- Viewports 320, 390, 768, 1366, 1920 проверены по responsive DOM/CSS branches: mobile full-width search; desktop flex-grow/wrap; title width не применяется ниже 768px.
- Keyboard/focus: native search controls, theme selector, links и existing dual focus ring не изменены.
- `git diff --check`: успешно.
- DEV `calibre-web-dev.service` active; journal после restart без template/runtime errors.
## Ограничения
- На VPS1 отсутствуют Chromium/Firefox и Playwright, поэтому screenshot/computed-style browser check и инструментальное измерение horizontal overflow не выполнены. Responsive layout проверен статически по DOM/CSS для заданных widths.
- `/category` для DEV Guest по-прежнему возвращает 404 из-за существующей `SIDEBAR_CATEGORY` visibility. Template breadcrumb/tree проверены Jinja и unit tests; permissions/DB намеренно не изменялись. Category result route проверен HTTP 200.
- Guest locale DEV сейчас English, поэтому gettext labels отображаются как `Home`, `Authors`, `Series`, `Search`; при Russian locale используются существующие переводы `Главная`, `Авторы`, `Серии`, `Поиск`.
## Commit
Изменения предназначены для commit `Refine AU-Books site layout`. Итоговый hash указывается в финальном ответе.
