# Техническое исследование архитектуры UI Calibre-Web для AU-Books
## Цель
Определить устройство интерфейса Calibre-Web, источники данных для Jinja-шаблонов, риски изменений и безопасную стратегию доступной переделки под AU-Books с минимальным расхождением с upstream.
## Границы исследования
- Изучена локальная ветка `aubooks` в `/home/feninf/calibre-web`.
- Production на VPS2 не открывался, не изменялся и не перезапускался.
- Код приложения не изменялся.
- На момент исследования `aubooks` отличается от `master` только файлом `AGENTS.md`; AU-Books UI-изменений пока нет.
## Краткий вывод
Calibre-Web строит серверный интерфейс на Flask/Jinja. Основной UI сосредоточен в шаблонах темы `standard`, общем CSS `cps/static/css/style.css` и jQuery-скриптах. Тема выбирается централизованно и допускает fallback к `standard` для отсутствующих шаблонов. Это делает отдельную тему `aubooks` с одним CSS-файлом и небольшим набором переопределений наиболее безопасным способом работы.

Большая часть первого этапа реальна без изменения модели данных, маршрутов и бизнес-логики. Для доступной структуры потребуются небольшие изменения шаблонов: landmarks, один `h1`, skip-link, корректная пагинация, именование кнопок и замена интерактивных `div`/ссылок без `href`. Python потребуется только для регистрации темы и, при необходимости, для более устойчивых серверных альтернатив JS-only действиям.
## Архитектурная карта
| Элемент | Файл | Назначение и данные |
| --- | --- | --- |
| Создание приложения и blueprints | `cps/main.py:main` | Регистрирует `web`, `search`, `basic`, `shelf`, `admin` и другие blueprints без общего URL-prefix. |
| Рендеринг и тема | `cps/render_template.py:render_title_template`, `themed_render` | Добавляет в каждый рендер `instance`, `sidebar`, `simple`, `accept`; выбирает тему, а для отсутствующего шаблона применяет `standard`. |
| Реестр тем | `cps/themes.py` | Описывает `standard`, `caliblur`, `simple`; `/basic` принудительно использует `simple`. |
| Базовый layout | `cps/themes/standard/templates/layout.html` | Подключает Bootstrap, общий CSS/JS, верхнюю навигацию, боковую навигацию, flash, пагинацию и модаль деталей книги. Это главный общий шаблон сайта. |
| Navbar и пользовательское меню | `cps/themes/standard/templates/layout.html:24-85` | Бренд, простой поиск, расширенный поиск, upload, tasks, admin, профиль, logout, login/register. Права и настройки определяют видимость элементов. |
| Боковая навигация | `cps/themes/standard/templates/layout.html:109-134`, `cps/render_template.py:get_sidebar_config` | Ссылки на книги, авторов, серии, категории и другие разделы; публичные и личные полки. Формируется из настроек пользователя, ролей и конфигурации. |
| Footer | Отсутствует | В `standard`, `caliblur` и `simple` нет общего семантического `<footer>`. |
| Главная и каталог книг | `cps/themes/standard/templates/index.html`, `cps/web.py:index`, `render_books_list` | Карточки новых, популярных, прочитанных, серийных и прочих отфильтрованных книг. `entries` содержит связанные данные `Books`, archived/read state; `random`, `pagination`, `title`, `page`, `order` определяют вывод. |
| Карточка книги | Повторяется в `index.html`, `search.html`, `author.html` | Показывает `entry.Books.title`, authors, series, rating, formats/read marker и макрос обложки. Повторение разметки является кандидатом на будущий минимальный include/macro, но не для первого изменения. |
| Детальная страница книги | `cps/themes/standard/templates/detail.html`, `cps/web.py:show_book` | Метаданные, обложка, загрузка, чтение, отправка на eReader, read/archive, полки, описание и custom columns. Для XHR наследует `cps/templates/fragment.html`; обычно открывается в Bootstrap modal. |
| Автор | `cps/themes/standard/templates/author.html`, `cps/web.py:render_author_books` | Книги автора; при включенном Goodreads также биография и внешние книги. |
| Серия | `index.html`, `cps/web.py:render_series_books` | Страница конкретной серии использует общий каталог. Обзор серий использует `list.html` или `grid.html`. |
| Каталоги авторов, серий и метаданных | `cps/themes/standard/templates/list.html`, `grid.html`; `cps/web.py:author_list`, `series_list`, `publisher_list`, `category_list`, `language_overview`, `ratings_list`, `formats_list` | Списки сущностей с числом книг, сортировкой и буквенным фильтром. Вид серий хранится в настройках пользователя. |
| Поиск | `cps/themes/standard/templates/search.html`, `search_form.html`, `cps/search.py` | Простой поиск перенаправляет на каталог `search`; расширенная форма сохраняет критерии в Flask session и рендерит общую выдачу результатов. |
| Login/регистрация | `login.html`, `register.html`; `cps/web.py:login`, `login_post`, `register`, `register_post` | Local/LDAP/OAuth/magic-link в зависимости от конфигурации. Регистрация возможна только при `config_public_reg`. |
| Профиль | `user_edit.html`, `cps/web.py:profile`, `change_profile` | Данные `current_user`, языки, доступные переводы, настройки sidebar, роли и OAuth/Kobo. |
| Пагинация | `layout.html:138-157`, `cps/pagination.py:Pagination`, фильтр `url_for_other_page` в `cps/jinjia.py` | Общий вывод pagination во всех страницах, которые передают `pagination`; URL сохраняет параметры запроса. |
| Flash и alerts | `layout.html:86-108`; AJAX: `cps/static/js/details.js` | Серверные категории `error`, `info`, `warning`, `success` выводятся в layout. AJAX вставляет alerts после navbar или в модаль. |
| Ошибки | `cps/themes/standard/templates/http_error.html`, `cps/error_handler.py:error_http`, `internal_error` | Самостоятельная страница ошибки, не наследующая основной layout. |
| Обложки | `cps/templates/image.html`, `cps/web.py:get_cover`, `get_series_cover`, helper cover functions | Jinja macro строит `img` с `srcset`, lazy loading и URL `/cover/...`; backend берёт thumbnail/cache, Google Drive или `cover.jpg`, имеет generic fallback. |
| Скачивание и чтение | `detail.html`, `cps/web.py:download_link`, `serve_book`, `read_book` | Права `role_download` и `role_viewer`; reader templates для EPUB, PDF, TXT, DjVu, audio и comics имеют отдельные CSS/JS. |
| Основной CSS | `cps/static/css/style.css`, `upload.css` | Глобальные стили standard UI, карточек, sidebar, modal и upload. |
| Основной JS | `cps/static/js/main.js`, `details.js`, `filter_list.js`, `filter_grid.js`, `fullscreen.js` | jQuery-интеракции, POST с CSRF, modal details, infinite scroll, filters, полки, read/archive и fullscreen cover. Селекторы зависят от существующих ID/classes. |
## Общие и страничные части
### Общие для сайта
- Выбор темы и контекст рендера: `render_template.py`.
- Базовая HTML-оболочка, загрузка зависимостей, navbar, sidebar, flash, pagination и modal: `layout.html`.
- Настройки видимости sidebar и публичных полок: `get_sidebar_config`.
- Макросы изображений и Jinja-фильтры: `cps/templates/image.html`, `cps/jinjia.py`.
- Bootstrap 3, `style.css`, `upload.css`, `main.js`.
- HTTP error template как отдельная, но общая для всех кодов ошибок оболочка.
### Относящиеся к страницам
- Выдача карточек: `index.html`, `search.html`, `author.html`.
- Списки авторов/серий/категорий: `list.html`; series grid: `grid.html`.
- Детали книги и их AJAX-действия: `detail.html`, `details.js`, `fullscreen.js`.
- Поиск: `search.html`, `search_form.html`, `search.py`.
- Аутентификация и профиль: `login.html`, `register.html`, `user_edit.html`.
- Readers имеют независимые templates и стили (`read.html`, `readpdf.html`, `readtxt.html`, `readdjvu.html`, `readcbr.html`, `listenmp3.html`); их не следует включать в первый дизайн-этап без отдельной задачи.
## Поток данных в шаблоны
### Общий контекст и пользователь
- `render_title_template` передаёт название инстанса, sidebar, mobile/simple flag и форматы upload.
- `current_user` доступен в Jinja через систему авторизации. Его роли (`role_admin`, `role_download`, `role_viewer`, `role_upload`, `role_edit`) определяют и UI, и доступ к endpoint.
- Глобальные `g.allow_anonymous`, `g.allow_registration`, `g.allow_upload`, `g.config_authors_max` устанавливаются до запросов в `cps/admin.py:before_request`.
- `CalibreDB.common_filters` в `cps/db.py` применяет персональные ограничения: archived, язык, allowed/denied tags и custom columns. UI не должен получать данные обходя эти запросы.
### Книги, авторы и серии
- `/` и `/<data>/<sort_param>/...` вызывают `cps/web.py:index`, `books_list`, затем `render_books_list` и специализированные `render_*_books`.
- `calibre_db.fill_indexpage` формирует `entries`: связанные объекты `Books`, флаг archived и read status/custom read column. `Books` содержит `authors`, `series`, `ratings`, `data`, `languages`, `tags`, `publishers`, `comments` и другие связи ORM.
- `render_author_books` фильтрует `Books.authors`; `render_series_books` фильтрует `Books.series`; обзоры авторов и серий подготавливаются в `author_list`/`series_list`.
- Поиск использует `cps/search.py:render_search_results` и `render_adv_search_results`; выдача сохраняет такой же контракт карточки. Расширенный поиск формирует tags, series, shelves, formats, languages и custom columns в `render_prepare_search_form`.
### Детали, ссылки и медиа
- `show_book` получает книгу через `calibre_db.get_book_read_archived`, добавляет `read_status`, `is_archived`, локализованные languages, sorted tags, `ordered_authors`, доступные reader/email formats, audio formats, custom columns и IDs полок.
- Ссылки на скачивание: `web.download_link` (`/download/<book_id>/<format>`), с `download_required`; чтение в браузере: `web.read_book` (`/read/...`), с `viewer_required`; непосредственная выдача: `web.serve_book` (`/show/...`).
- Обложки: `/cover/<book_id>/<resolution>` и `/series_cover/<series_id>/<resolution>`; macro `book_cover` передаёт `title` как alt по умолчанию, `srcset` и `loading="lazy"`.
- Действия read/archive, shelves и send-to-eReader завязаны на CSRF и AJAX; при изменении разметки должны сохраняться их endpoint и нужные `data-*`/ID либо одновременно корректироваться JS.
## CSS, JavaScript и темы
### Глобальная загрузка
В standard layout порядок CSS: `bootstrap.min.css`, страничный `{% block header %}`, `style.css`, `upload.css`. Поэтому общий project CSS может перекрывать страничные плагины. Внизу страницы загружаются jQuery 3.6.3, Bootstrap JS 3.4.1, Underscore, Intention, Context, `plugins.js`, jquery.form, uploadprogress, `main.js`, затем страничный `{% block js %}`.

`plugins.js` содержит legacy-плагины, включая Isotope, Infinite Scroll и imagesLoaded. Обновление Bootstrap или замена jQuery не относится к редизайну: Bootstrap 3.4.1 зависит от jQuery и его `data-toggle`, grid, dropdown и modal используются во множестве шаблонов и плагинов.
### Собственные стили
- `style.css`: стандартная тема, layout, карточки, обложки, list/detail/sidebar и scroll containers.
- `upload.css`: загрузка книг.
- `basic.css`: упрощенный `/basic` интерфейс.
- `caliBlur.css` и `caliBlur_override.css`: отдельная dark-тема; первый файл очень крупный и содержит presentation logic assumptions.
- `main.css`, `reader.css`, `text.css`, `kthoom.css`, `popup.css` и viewer CSS: независимые reader pages.

`style.css` делает обложки центральным элементом каталога: карточка ограничена 180px, cover имеет фиксированную высоту 225px. Основной content и sidebar имеют отдельные scroll containers с `max-height: calc(100vh - 111px)`. Для AU-Books это стоит заменить или переопределить в новой теме: обычная document-прокрутка и текстовый список лучше для screen reader, keyboard и увеличения масштаба.
### Темы
- `standard` - default и основной источник fallback templates.
- `caliblur` - отдельная тема с 42 отличающимися шаблонами, отдельным layout и JS `caliBlur.js`; это не тонкая CSS-надстройка.
- `simple` - специальная невыбираемая тема blueprint `basic`.

Поля `css_files` и `js_files` в `themes.py` являются метаданными: автоматически они не подключаются. CaliBlur подключает свои ресурсы непосредственно в своем `layout.html`.
### Рекомендуемая изоляция
1. Создать новую configurable theme `aubooks` в `cps/themes/aubooks/` и добавить только её описание в `cps/themes.py`.
2. Сделать AU layout, сохраняющий поддерживаемые Jinja blocks `header`, `body`, `modal`, `js`, и подключающий `css/aubooks.css` последним.
3. Переопределять только необходимые страницы; остальные должны fallback к `standard`.
4. Не изменять `style.css`, `main.js`, Bootstrap и не копировать массово шаблоны caliBlur.
5. Не базировать AU-Books на `caliBlur`: он удаляет focus outlines, мутирует DOM в JS и увеличивает конфликтную поверхность.
## Оценка доступности
Аудит статический: приложение не запускалось в браузере, поэтому нужны последующие ручные keyboard и screen-reader проверки.
### Семантика и landmarks
- В `standard/layout.html` два `<nav>`, но отсутствуют `<header>`, `<main>`, `<aside>`, `<footer>` и skip-link. Основное содержимое находится в `div.col-sm-10`.
- `http_error.html` не наследует layout и также не имеет landmarks.
- Для AU layout нужны `<header>`, именованные `<nav aria-label>`, `<aside>` для browse, `<main id="main-content" tabindex="-1">`, `<footer>` и первая фокусируемая ссылка «Перейти к содержимому».
### Заголовки
- Главная, search results, author и detail начинаются с `h2`, без route-level `h1` (`index.html`, `search.html`, `author.html`, `detail.html`).
- `stats.html` начинается с `h3`; `http_error.html` содержит два `h1`.
- `search_form.html`, `list.html`, `grid.html`, `user_edit.html` уже имеют `h1`.
- Нужен один `h1` с назначением страницы, затем `h2` для sections и `h3` для вложенных частей. Название сайта в header не должно заменять заголовок документа.
### Формы, кнопки и клавиатура
- Положительно: login, register и расширенный поиск в основном используют связки `<label for>`; login password toggle имеет `aria-label`.
- В basic search отсутствует label. У date-clear кнопок `search_form.html` отсутствуют доступные имена.
- В `list.html`/`grid.html` сортировка и буквенные фильтры выполнены как кликабельные `div.btn`; в `user_edit.html`, `detail.html`, `shelf.html`, `book_table.html` есть аналогичные `div` или `<a>` без `href`. Они не получают нативный focus и не работают с клавиатуры.
- `filter_list.js`, `filter_grid.js`, `main.js`, `details.js` преимущественно слушают `click`; при замене на реальные `<button type="button">` необходимо сохранить selectors или скорректировать обработчики.
- Upload использует скрытый file input внутри `span`, а shelf reordering зависит от mouse drag-and-drop. Для первого этапа следует предоставить видимые именованные controls; клавиатурную альтернативу reorder планировать отдельно.
### Focus, ARIA, alerts и pagination
- В caliBlur глобально убирается `outline` у ссылок, buttons и controls. Это критическая причина не использовать его как базу AU-Books.
- В standard явного единого современного focus style нет. В AU CSS нужен контрастный `:focus-visible` с `outline` и `outline-offset`, без удаления fallback `:focus`.
- Server flash и dynamically created alerts не имеют `role="alert"`/`aria-live`; screen reader не гарантированно объявит изменение.
- Pagination содержит `<li>` напрямую в `<div>`, а не внутри `<ul>`; у Previous ошибочный `aria-label="next page"`; текущая страница остаётся ссылкой без `aria-current="page"`.
- В `modal_dialogs.html` часть `aria-labelledby` ссылается на отсутствующие id, а встречается некорректный `role="Dialog"`.
- Bootstrap modal частично обеспечивает focus management, но доступные имя, роль и связи должны быть валидными.
### Ссылки, изображения и зависимость от обложек
- Карточка создаёт два перехода к книге: для cover и title. Это увеличивает число tab stops и ставит обложку перед текстом.
- `image.book_cover` даёт alt, lazy loading и responsive `srcset`; это сильная часть текущей реализации.
- Detail cover, basic detail, shelf order и внешние Goodreads cards имеют отсутствующий/неподходящий alt. В author cards alt обложки передаётся как имя автора, а не название книги.
- Текстовый title/author/formats должен быть первичным способом выбрать книгу. Обложка должна быть декоративной (`alt=""`) или иметь точный текст «Обложка: {название}», но не быть единственным носителем информации.
- Рейтинг, состояние прочтения и формат не должны полагаться только на Glyphicons: нужен текст для screen reader или доступное имя.
## Реалистичность переделки с минимальными конфликтами
Реалистично сделать основную визуальную и структурную переделку преимущественно собственным CSS и ограниченным набором AU template overrides. Маршруты уже поставляют все необходимые для первого этапа данные: текстовое название, авторов, серию, описание, formats, user permissions, read/archive state и pagination.

Минимальный контракт, который нужно сохранять при template changes: endpoint names, CSRF inputs, значения `data-href`/`data-action`, ID `bookDetailsModal`, `have_read_form`, `have_read_cb`, `archived_form`, `archived_cb`, `add-to-shelves`, `remove-from-shelves`, и selectors, на которые опираются `main.js` и `details.js`.
## Риски конфликтов с upstream
### Высокий риск
- `cps/themes/standard/templates/layout.html`: navbar, sidebar, flash, pagination, modal и ресурсы.
- `index.html`, `detail.html`, `search.html`, `search_form.html`, `author.html`, `list.html`, `grid.html`: смешивают структуру UI, URL, permissions и ORM data.
- `modal_dialogs.html`, `style.css`, `main.js`, `details.js`: широко используются и связаны точными селекторами.
- `web.py`, `search.py`, `render_template.py`, `themes.py`: центральные backend точки UI.
### Средний риск
- Все шаблоны caliBlur: они являются копиями standard и upstream может менять их отдельно.
- `basic.py` и basic templates: simple theme принудительно выбирается для blueprint `basic`.
- `filter_list.js` и `filter_grid.js`: привязаны к non-semantic filter controls.
### Низкий риск
- Новые `cps/themes/aubooks/templates/...`.
- Новый `cps/static/css/aubooks.css` и только новые AU-specific JS-файлы при необходимости.
- Минимальное добавление темы в `cps/themes.py`.
## Стратегия переделки AU-Books
### A. Только CSS
- Контрастная типографика, крупные интервалы, responsive layout, print/high-zoom rules.
- Единый видимый `:focus-visible`, стили hover без замены focus, стили reduced motion.
- Сделать title/author метаданные приоритетнее cover, убрать фиксированную высоту cover, скрыть декоративные изображения по настройке/в узком виде.
- Переопределить fixed nested scrolling в пользу обычной прокрутки страницы.
- Визуально отделить primary actions «Читать», «Скачать», «Слушать» и сделать кнопки не зависящими от Glyphicons.
### B. Небольшие изменения шаблонов
- Отдельная тема `aubooks`, AU layout, `aubooks.css`, fallback к standard для остальных страниц.
- Добавить skip-link, `header/nav/main/aside/footer`, осмысленные `aria-label`, live region для flash.
- Привести route-level headings к одному `h1`; исправить HTML pagination на `nav > ul`, `aria-current` и labels.
- Переопределить `index.html`, `search.html`, `author.html`, `detail.html`, `list.html`, `login.html`, `register.html`, `http_error.html` с текстовой, keyboard-first структурой.
- Заменить управляющие `div` и `<a>` без `href` на buttons, добавив accessible names для icon-only controls. Одновременно адаптировать selectors JS в AU-specific обработчиках или минимально в existing handlers.
- Исправить alt на detail/external covers; для декоративных изображений установить пустой alt.
### C. Python/backend
- Регистрация `aubooks` в `cps/themes.py` - минимально необходимое изменение для выбираемой темы.
- Если AU-Books должен заменять forced `/basic`, потребуется отдельное решение в `get_theme_identifier`; это не нужно для первого этапа.
- Серверные POST forms или endpoint-адаптация для actions, которые сейчас работают только через JS, если нужен надёжный no-JS fallback.
- Клавиатурная альтернатива shelf reorder потребует доработки frontend и, вероятно, server-side маршрута перемещения.
- Не менять запросы Calibre ORM, фильтры доступа, скачивание/чтение и permission decorators без отдельной продуктовой причины.
## Первые 5 задач разработки
1. Создать тему `aubooks`: добавить минимальную запись в `themes.py`, AU layout и пустой `aubooks.css`; проверить выбор темы, fallback standard и сохранение login/catalog/detail маршрутов.
2. Сделать доступную глобальную оболочку: skip-link, `header`, именованные nav, `aside`, `main`, footer, один live region для flash, корректная pagination; проверить tab order и responsive navigation.
3. Переделать каталог в text-first view: AU overrides `index.html` и `search.html`, один понятный переход к книге, title как heading/link, author/series/formats/read status текстом, обложка вторична; проверить без обложек и при 200% zoom.
4. Переделать detail page: `h1`, корректные alt, логическая группа основных действий, доступные controls для read/archive/полок, исправление невалидных форм; проверить download/read/shelf actions и XHR modal.
5. Привести auth, поиск и справочники к keyboard-first UI: `login.html`, `register.html`, `search_form.html`, `list.html`, `grid.html`, `http_error.html`; заменить interactive `div` на buttons, добавить labels и проверить keyboard/screen reader сценарии.
## Проверка и ограничения
- Выполнена статическая проверка структуры репозитория, Jinja templates, CSS, JavaScript, routes и источников данных.
- Проверены текущая ветка `aubooks` и состояние Git до создания отчёта: исходное рабочее дерево было чистым.
- Автоматические тесты не запускались: изменена только документация, приложение и его runtime не менялись.
- Не выполнялись browser, keyboard, screen-reader, Lighthouse или production проверки. Их необходимо включить в каждую последующую UI-задачу.
## Изменённые файлы
- `docs/works/2026-08-30-calibre-web-ui-architecture.md` - этот отчёт.
## Commit
Коммит не создавался.
