# Доступный глобальный layout AU-Books
## Цель
Создать первый accessibility-фундамент темы `aubooks` для слепых, слабовидящих и клавиатурных пользователей без изменения backend, бизнес-логики и production.
## Изучено
- Проверены ветка `aubooks`, baseline `753ffb8936ca472836a1d66e4cbf226d6428192e` и чистота рабочего дерева перед началом.
- Изучены standard layout, AU layout и modal macro proxy, CSS Bootstrap/standard, responsive sidebar через Intention.js, navbar/upload JS-контракты, flash-селекторы, pagination/infinite-scroll и page templates главной, login, search и detail.
- Установлено, что дочерний AU layout мог переопределять только CSS: landmarks, navbar, sidebar, flash и pagination не выделены в Jinja-блоки standard. Поэтому AU layout основан на копии текущего standard layout; upstream layout не изменён.
## Изменённые файлы
- `cps/themes/aubooks/templates/layout.html` — доступная глобальная семантика и ARIA только для темы AU-Books.
- `cps/static/css/aubooks.css` — функциональные accessibility-стили темы.
- `docs/works/2026-08-31-aubooks-accessible-layout.md` — этот отчёт.
## Что изменено
- Первой полезной ссылкой страницы добавлен skip-link «Перейти к основному содержимому», ведущий на стабильный `main-content`; язык русской подписи указан через `lang="ru"`.
- Добавлены семантические `header`, именованный основной `nav`, `main`, `aside` с отдельно именованной навигацией и `footer`.
- Сохранены Bootstrap-классы, navbar/sidebar структура, responsive Intention.js attributes, JS ID, upload form, blocks и порядок scripts.
- Navbar toggle связан с collapse через `aria-controls`, имеет начальное `aria-expanded="false"`; декоративные иконки скрыты от accessibility tree, icon-only состояния navbar получили accessible names, file upload получил label.
- Активные ссылки sidebar получают `aria-current="page"` по существующему условию active state.
- Серверные ошибки flash получают `role="alert"`, информационные, warning и success сообщения — `role="status"`; общий `aria-live` намеренно не добавлялся, чтобы избежать повторных объявлений.
- Pagination стала именованным `nav` с корректным списком, понятными именами previous/next/page и `aria-current="page"`; сохранены `.pagination` и `.next` для infinite scroll.
- Book details modal получил `aria-modal="true"`, локализованное имя close и связанный `h2` title; focus trap и return focus не переписывались.
- Добавлены постоянно видимый keyboard focus, видимый focus upload control через `:focus-within`, скрытие/появление skip-link, подчёркивание обычных content links и отмена раздельных viewport scroll-контейнеров.
- Явно низкоконтрастные teal/secondary цвета затемнены. Расчётные контрасты: `#176b60` к `#f2f2f2` — 5.67:1, к белому — 6.35:1; `#595959` к `#f2f2f2` — 6.26:1.
## Исправленные барьеры
- Клавиатурный пользователь может сразу перейти к основному содержимому и видеть текущий focus.
- Screen reader получает основные landmarks, отдельные названия основной и библиотечной навигации, текущую sidebar/pagination страницу и имена controls без видимого текста.
- Ошибки login/flash объявляются как срочные сообщения, а обычные статусы не используют assertive announcement.
- Pagination больше не содержит `li` непосредственно внутри `div`; текущая страница не является лишней ссылкой на себя.
- Основной документ снова прокручивается как единое целое, что уменьшает барьеры при keyboard navigation и zoom.
## Заголовки и оставшиеся проблемы
- Layout намеренно не добавляет общий `h1`, чтобы не создавать дубликаты на страницах, где page template уже выводит собственный `h1`.
- Runtime подтвердил отсутствие `h1` на пустой главной, login и search: соответствующие standard templates начинают с `h2`. Detail использует `h2` для названия книги и `h3` для описания. Это требует AU page overrides на следующем этапе.
- Shared modal macros по-прежнему проксируются из standard. В них остаются отсутствующие `aria-labelledby` targets, непоследовательный `role="Dialog"`, а также не проверенные полностью focus trap, Escape и return focus. Bootstrap focus management целиком не переписывался.
- AJAX-generated flash markup в shared JavaScript не получил live-region semantics; исправление потребует согласованного изменения JS emitters. При нескольких серверных flash одного типа остаётся риск duplicate ID из upstream-совместимой схемы ID.
- Navbar collapse интерактивно не проверен в браузере: статически подтверждены `aria-controls` и `aria-expanded`, дальнейшее значение должен обновлять Bootstrap.
- Новые gettext labels пока отсутствуют в translation catalogs и используют fallback text; отдельная локализация ARIA-строк нужна вместе со следующим переводческим этапом.
- Страницы `/basic` и standalone `http_error.html` не используют этот AU layout и остаются вне данного этапа.
## Upstream
- Upstream-файлы `standard`, backend, routes, database и JavaScript не изменялись.
- Полная AU-копия layout необходима из-за отсутствия структурных extension blocks в standard. При будущей синхронизации upstream её нужно сравнивать с `cps/themes/standard/templates/layout.html`.
## Проверки
- `git diff --check` — успешно.
- Jinja parse `cps/themes/aubooks/templates/layout.html` — успешно.
- `.venv/bin/python -m pip check` — успешно, broken requirements нет.
- DEV service `calibre-web-dev.service` перезапущен и активен только на `127.0.0.1:8084`.
- HTTP smoke: `/`, `/login`, search с redirect и `/static/css/aubooks.css` — HTTP 200; template errors отсутствуют.
- Anonymous DOM: skip-link является первой ссылкой; присутствуют по одному `header`, `main#main-content`, `aside`, `footer`; navbar/sidebar имеют доступные имена; toggle и modal ARIA связаны корректно.
- Authenticated DOM: navbar controls имеют accessible names; sidebar имеет отдельное имя; `/hot/stored` помечает `Hot Books` через `aria-current="page"`.
- Flash: ошибочный login вернул HTTP 401 и server flash `alert-danger` с `role="alert"` без template error.
- Автоматические axe/pa11y/Playwright и браузер в окружении не установлены; тяжёлые зависимости не добавлялись. Выполнен структурный DOM-анализ через имеющийся `lxml`.
- DEV-библиотека пуста, поэтому detail и фактическая pagination runtime недоступны; pagination проверена статически, detail-проблемы зафиксированы по template analysis.
- В журнале DEV после перезапуска warning/error записей нет.
## Ограничения
- Полноценный фирменный дизайн, page-level heading/card redesign, доступность shelf/sort actions, cover alternatives и общих modal macros отложены на следующие этапы.
- Production VPS2 не затрагивался, production services не перезапускались, push не выполнялся.
## Commit
Изменения и отчёт фиксируются одним commit `Improve AU-Books layout accessibility`; итоговый hash указан в результате задачи, поскольку commit не может содержать собственный hash.
