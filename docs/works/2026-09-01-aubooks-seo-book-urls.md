# SEO-friendly URL книг AU-Books
## Цель
Добавить стабильные публичные страницы книг без числового Calibre ID в canonical URL, сохранить совместимость со старыми ссылками и подготовить индексируемые metadata, sitemap и robots.
## Исследованная маршрутизация
- Исходная detail page использовала endpoint `web.show_book` и route `/book/<int:book_id>` в `cps/web.py`.
- Книга находилась по `Books.id` через `calibre_db.get_book_read_archived`; numeric ID также остаётся во внутренних download/read/shelf/AJAX endpoints.
- Detail links формировались через `url_for('web.show_book', book_id=...)` в standard/caliblur/AU templates, task/email helpers и edit redirects.
- AU-Books card links централизованы в `_book_card.html`; modal JavaScript берёт URL непосредственно из `href` и выполняет XHR с progressive-enhancement fallback.
- Старые `/book/<id>` могли находиться в bookmarks, письмах, task history и внешнем поисковом индексе.
- До изменения sitemap отсутствовал, а `/robots.txt` пытался отдать отсутствующий static-файл.
## Выбранная архитектура
- Canonical формат: `/books/<author-slug>/<book-slug>`.
- Числовой Calibre ID не входит в публичный canonical URL, но сохраняется в application mapping и используется backend для загрузки `Books`.
- Mapping хранится только в Calibre-Web `app.db`, таблица `aubooks_seo_book_route`; schema Calibre `metadata.db` не изменяется.
- Каждая строка содержит `library_uuid`, `book_id`, `author_slug`, `book_slug`, `is_canonical`, timestamp.
- Уникальный индекс `(library_uuid, author_slug, book_slug)` одновременно защищает canonical и alias namespace.
- Partial unique index `(library_uuid, book_id) WHERE is_canonical=1` гарантирует один canonical route на книгу.
- Индексы `(library_uuid, book_id)` и `(library_uuid, is_canonical, book_id)` обеспечивают lookup и sitemap pagination.
- Schema создаётся идемпотентно при startup. Полный backfill выполняется offline-скриптом `scripts/aubooks-seo-migrate.py`; повторный запуск добавляет только отсутствующие книги.
- Генерация ссылок в Jinja read-only. Для новой книги без mapping временно строится legacy URL; его первый запрос выделяет mapping через отдельную короткую app DB session и возвращает 301.
## Основной автор
- Для URL используется первый автор по текущему `books.author_sort`, то есть тот же порядок, который Calibre-Web применяет на detail page.
- Если `author_sort` не позволяет сопоставить автора, используется автор с минимальным author ID как детерминированный fallback.
- Полный список авторов остаётся в initial HTML, Open Graph и JSON-LD.
- Выбранный author slug сохраняется в mapping. Последующее изменение порядка авторов или metadata само по себе не меняет canonical URL.
## Slug и транслитерация
- Вход нормализуется через Unicode NFKC и `casefold`, независимо от system locale.
- Результат содержит только lowercase ASCII `a-z`, цифры и `-`; punctuation/whitespace становятся `-`, повторные и крайние дефисы удаляются.
- Максимальная длина базового author/title slug — 96 символов; fallback — `unknown-author` и `book`.
- Русская таблица детерминированно даёт `Михаил Булгаков` → `mihail-bulgakov`, `Мастер и Маргарита` → `master-i-margarita`.
- Украинская таблица различает `г→h`, `ґ→g`, `и→y`, `і→i` и контекстные `є/ї/й/ю/я`; `Іван Багряний` → `ivan-bahrianyi`.
- Latin сохраняется, диакритика снимается через Unicode decomposition.
## Статистика DEV library
- Книг: 122463; authors: 63224; book-author links: 146373.
- Книг с несколькими авторами: 8732; без автора: 0.
- Уникальных normalized full-author-set/title combinations: 122354.
- Точных duplicate combination groups: 109; в них 218 книг; максимум 2 книги.
- Для фактического URL algorithm с первым автором, транслитерацией и лимитом длины: 531 collision group, 1075 книг, максимальная группа 8.
- После allocation `book`, `book-2`, `book-3` создано 122463 уникальных canonical pair; duplicate routes — 0.
## Collision handling и стабильность
- Initial backfill идёт в стабильном порядке Calibre book ID, но ID используется только для allocation и не публикуется.
- Первый route получает base slug; следующие конфликты получают минимальный свободный suffix `-2`, `-3` и далее.
- Allocation сохраняется в `app.db`, поэтому добавление, удаление или переименование других книг не перенумеровывает существующие URL.
- Metadata edits не регенерируют canonical автоматически: это предотвращает неожиданные 404 и churn поискового индекса.
- При явной регенерации `replace_canonical` атомарно делает старый canonical alias. Alias lookup возвращает 301 на текущий canonical после visibility-check.
## Routes и redirects
- `GET /books/<author-slug>/<book-slug>` разрешает mapping, проверяет существование/видимость книги и отдаёт detail page.
- `GET /book/<id>` сохранён как legacy endpoint, проверяет видимость и возвращает `301 Moved Permanently` на canonical.
- Alias возвращает 301; неизвестная pair возвращает 404; redirect loops в DEV не обнаружены.
- Internal Jinja links централизованно перехватывают `url_for('web.show_book', book_id=...)`, поэтому home, search, author, series, standard, caliblur и AU templates получают canonical URL без механического копирования шаблонов.
- Numeric download/read/shelf/AJAX endpoints не менялись: они не являются canonical detail pages.
## SEO metadata и indexability
- AU detail получает title `Книга — Автор | AU-Books`, plain-text meta description до 160 символов и fallback `title — authors`.
- Добавлены absolute canonical, Open Graph `type/title/description/url/site_name` и image только при `has_cover`.
- JSON-LD schema.org `Book` содержит name, все authors, description, inLanguage, url, реальную cover image при наличии и ISBN только если он есть.
- Detail title, authors и description находятся в initial HTML; JavaScript не нужен для основного контента.
- Добавлены семантические breadcrumbs; существующий accessible `h1` и modal XHR flow сохранены.
- DEV имеет anonymous browsing, поэтому canonical detail доступен без login и не содержит `noindex`. Для закрытой библиотеки бизнес-логика не меняется: detail потребует login, sitemap будет 404, robots отдаст `Disallow: /`.
## Sitemap и robots
- `/sitemap.xml` отдаёт sitemap index.
- `/sitemaps/books-1.xml` ... `/sitemaps/books-7.xml` содержат не более 20000 canonical URL каждый.
- На DEV размеры частей: 20000, 20000, 20000, 20000, 20000, 20000 и 2463 URL; total и unique — 122463.
- Sitemap всегда применяет filters пользователя Guest независимо от cookie текущего пользователя, работает bounded batches по 500 mapping rows и имеет `Cache-Control: public, max-age=3600`.
- Legacy, aliases, login, admin, search/filter URLs в sitemap не включаются.
- Dynamic robots разрешает `/books/`, запрещает admin/ajax/legacy book/login/search/tasks, учитывает URL prefix и указывает sitemap. CSS/JS не блокируются.
## DEV migration
- Перед миграцией service остановлен, создан `/home/feninf/calibre-web-dev-data/app-before-seo-20260901.db`.
- Offline migration создала 122463 mappings за 9,165 с; `PRAGMA integrity_check` — `ok`.
- Dry-run на копии: 122463 mappings за 9,322 с; повторный запуск создал 0 строк за 5,299 с.
- После миграции перезапущен только `calibre-web-dev.service`; isolation pre-check подтвердил read-only snapshot из 122463 книг.
- `metadata.db` не изменялась; production VPS2, production nginx и production DB не затрагивались.
## Производительность
- Indexed lookup по 2000 случайным book IDs: в среднем 0,0412 мс на lookup.
- Warm canonical detail: 0,037 с; cold/parallel representative detail: 0,38–0,59 с, первый запрос после restart 1,31 с.
- Legacy redirect + final canonical: 0,054 с; alias redirect: 0,016 с.
- Sitemap index: около 0,47 с; одна часть 20000 URL: 3,15–3,69 с; все 7 частей: 19,57 с.
- Home/author/series формировали canonical links; наблюдавшиеся timings 2,2–2,5 с в текущем DEV. Search с большим результатом занял около 10,3 с; это существующая стоимость search/query/render и не полный пересчёт slug.
## Реальные DEV примеры
- Русская: `/books/georgiy-persikov/delo-o-medvezhem-posohe`.
- Украинская: `/books/hans-kristian-andersen/snihova-koroleva`.
- English language record: `/books/quick-online-converter/sword-art-online-18-zavershenie-alisizatsii`.
- Пунктуация: `/books/aleks-hatchinson/kardio-ili-silovaya-kakie-nagruzki-podhodyat-imenno-vam`.
- Несколько авторов: `/books/gardner-dozua/luchshaya-zarubezhnaya-nauchnaya-fantastika-sumerki-bogov`.
- Collision suffix: `/books/sergey-sergeevich-tarmashev/illyuziya-2`.
## Проверки
- Unit tests: 10 slug/storage tests — успешно.
- Проверены RU/UK/EN, punctuation, multiple authors, duplicate titles, collision suffix, no description, no cover, ISBN и image conditional output.
- 2000 случайных mappings прошли safe-character, uniqueness, book existence и indexed round-trip checks.
- Canonical 200; legacy 301; temporary stale alias 301; unknown slug 404; legacy follow имеет ровно один redirect.
- Home/search/author/series HTML содержит canonical `/books/` links; shelf fixture в DEV отсутствует, поэтому отдельный shelf HTTP case не выполнен.
- XHR canonical detail вернул 200 и сохранил detail scripts/modal fragment.
- Все 7 sitemap parts отдали 122463 уникальных URL.
- Python compile, Jinja parse, `pip check`, `git diff --check`, app DB integrity и metadata quick check выполнены успешно.
- В log после SEO startup/runtime проверок новых template/runtime errors не обнаружено.
## Изменённые файлы
- `cps/seo_urls.py` — детерминированные slug и primary-author selection.
- `cps/seo_db.py` — mapping model, indexes, persistence, collision и aliases.
- `cps/seo.py` — canonical route, URL helper, SEO context и sitemap.
- `cps/__init__.py`, `cps/main.py` — идемпотентная schema initialization и blueprint registration.
- `cps/db.py` — optional explicit user для безопасных Guest filters sitemap.
- `cps/web.py` — legacy 301, shared detail renderer и dynamic robots.
- `cps/themes/aubooks/templates/detail.html` — canonical/meta/OG/JSON-LD/breadcrumbs.
- `cps/themes/aubooks/templates/layout.html` — SEO title override; остальные незакоммиченные accessibility changes не относятся к этой задаче.
- `scripts/aubooks-seo-migrate.py` — offline idempotent backfill.
- `tests/test_seo_urls.py`, `tests/test_seo_db.py` — unit tests.
- `docs/works/2026-09-01-aubooks-seo-book-urls.md` — этот отчёт.
## Ограничения и production rollout
- Перед production нужен backup production `app.db`, остановка production Calibre-Web, offline backfill с `--offline`, integrity/row-count verification и только затем deploy/restart отдельной задачей.
- Для доверенного absolute origin в production следует задать `AUBOOKS_PUBLIC_URL=https://public.example`; без него canonical использует корректные proxy request headers, что требует trusted reverse-proxy configuration.
- Static/CDN/nginx caching sitemap и detail не настраивался; это отдельная задача.
- Automatic metadata-edit slug regeneration намеренно отсутствует. Если editorial policy потребует новый canonical после переименования, нужно вызвать контролируемый `replace_canonical`; старый route станет alias.
- External Python task/email/edit links, которые не проходят Jinja helper, могут сначала использовать legacy `/book/<id>`, но получают постоянный 301. Их прямой перевод можно сделать отдельно без нарушения compatibility.
- Отдельный shelf HTTP test невозможен без shelf fixture; общий helper уже применяется к shelf templates.
## Commit
Изменения предназначены для отдельного commit `Add SEO-friendly canonical book URLs`. Итоговый hash указан в финальном ответе, поскольку hash не может быть записан внутрь собственного commit без изменения этого hash.
