# Иерархия жанров AU-Books
## Цель
Показывать технические genre codes Calibre как русские жанры Flibusta и организовать доступную навигацию `Категория → Подкатегория`, не изменяя metadata.db и существующие category routes.
## Найденные источники
Основной словарь найден в `/home/feninf/aubooks/files/flibusta_genres.txt`. Идентичная копия есть в `/home/feninf/bin/files/flibusta_genres.txt`; SHA-256 обеих копий: `7187cd900ae908fb3a25a697c1b32cbf65b15322cc834c96c57c16582c9abb12`.
В sibling project также найден `/home/feninf/aubooks/files/dict_genre` с частичными explicit sections. Он использован только для проверки тематических границ; русские leaf labels берутся исключительно из `flibusta_genres.txt`.
Exact основной словарь добавлен в репозиторий как `cps/data/flibusta_genres.txt`, поэтому HTTP requests не читают внешние `/home/feninf/...` paths.
## Формат словаря
- UTF-8 text, 273 непустые строки.
- 272 строки формата `g/<technical_code>=<русское название>`.
- Последняя служебная строка `g=Жанры` задаёт root label.
- Явных category/section markers в самом `flibusta_genres.txt` нет.
- Порядок записей образует 21 непрерывный тематический блок. Границы проверены по companion `dict_genre` и зафиксированы централизованно в Python module.
- Duplicate technical codes отсутствуют.
- Русский label `Экономика` встречается у двух codes (`economics`, `sci_economy`); reverse-label matching для него намеренно не применяется как неоднозначное.
- Единственный ASCII-only source label: `antique=antique`; он сохранён без выдуманного перевода, так как основной словарь является источником истины.
- Невалидных/пустых mappings нет.
## Категории
Создана 21 верхнеуровневая категория: Деловая литература; Детективы и триллеры; Детская литература; Документальная литература; Дом и семья; Драматургия; Искусство; Компьютеры и интернет; Любовные романы; Наука и образование; Поэзия; Приключения; Проза; Прочее; Религия и духовность; Справочная литература; Старинная литература; Техника и учебные пособия; Фантастика; Фольклор; Юмор.
Дополнительная runtime группа `Другие жанры` содержит DEV tags, которых нет в словаре.
## Архитектура
- `cps/aubooks_genres.py` один раз при import загружает и строго валидирует bundled dictionary.
- `GENRES` является единым resolved mapping `code → label/category`.
- Category boundaries централизованы в том же module; большой словарь не продублирован в Jinja.
- Exact unique Russian labels из словаря также распознаются как безопасные aliases. Неоднозначные labels не распознаются.
- `genre_for_tag()` сохраняет исходный tag ID для существующего `/category/stored/<id>` routing.
- `group_tags()` группирует detail tags в памяти и не повторяет category heading.
- `build_genre_tree()` преобразует результат существующего aggregate query без дополнительных SQL queries.
- Mapping активируется только при server theme identifier `aubooks`; standard/caliblur/simple presentation не меняется.
- ORM `Tags.name`, `Books.tags`, search, restrictions, OPDS, metadata editing и metadata.db не изменены.
## UI
### Detail
Стандартный detail получил узкий overridable Jinja block `book_tags`; исходная разметка других themes внутри блока сохранена. AU override выводит semantic section с `h2 Жанры`, внешним списком категорий и вложенными списками жанров. Leaf names кликабельны и ведут на прежние tag-ID routes.
Если книга имеет жанры нескольких категорий, каждая категория выводится один раз. Если несколько жанров относятся к одной категории, они находятся в одном вложенном списке.
### Directory
AU `/category` использует semantic `section`, `h2`, `ul/li`. Parent categories не являются fake routes; leaf links используют существующий `web.books_list` endpoint. Counts получены тем же aggregate query. Flat `filter_list.js` на hierarchy page не загружается.
### Results
Category result page показывает русский leaf heading и breadcrumb `Жанры → Категория → Подкатегория`. Sorting, pagination, filtering и tag ID сохраняются.
### Sidebar
AU label существующего category navigation item изменён с `Категории` на `Жанры`; visibility permission не обходится.
## Unknown fallback
- Неизвестный tag с кириллическим/украинским пользовательским label сохраняет исходное читаемое имя и помещается в `Другие жанры`.
- Неизвестный ASCII technical tag отображается как `Неизвестный жанр (<code>)`, остаётся кликабельным и не ломает страницу.
- Unknown coverage учитывается в этом отчёте; массовое runtime logging 1055 values не добавлялось, чтобы не засорять logs на каждом directory request.
## DEV coverage
Read-only анализ `/home/feninf/calibre-web-dev-data/library/metadata.db`:
- 1316 уникальных используемых tags.
- 207612 tag assignments.
- 261 из 272 technical codes словаря присутствуют в DEV library.
- Direct code match: 261/1316 unique tags (19.83%), 133269/207612 assignments (64.19%).
- С учётом exact unique Russian source labels presentation mapping покрывает 357/1316 unique tags (27.13%), 151508/207612 assignments (72.98%).
- Unknown: 959 presentation tags после exact-label resolution; в исходном direct-code анализе 1055 tags, из них 814 с читаемым non-ASCII label и 241 technical/ASCII.
- 121097 книг имеют tags; 58143 книги имеют больше одного tag; максимум 22 tags у книги.
- Распределение количества tags: 62954 книг с одним, 35079 с двумя, 18841 с тремя, остальные с 4–22.
- Languages library: rus 115392, ukr 6079, eng 597; также присутствуют 24 других language codes.
- 11 dictionary codes отсутствуют в DEV: `child_dramaturgy`, `child_sf_space`, `det_artifact`, `palindromes`, `poetry_for_modern`, `religion_protestantism`, `sci_build`, `sci_metal`, `sf_industrial_magic`, `tale_chivalry`, `utopia`.
Самые частые direct-code unknown tags: `Современная проза` (5357), `Боевая фантастика` (5049), `Любовное фэнтези` (4930), `детектив` (3793), `Любовный роман` (3681), `Фэнтези` (3138), `Альтернативная история` (2643), `Героическое фэнтези` (2119), `публицистика` (2034), `история` (2031), `Триллер` (1785), `LitRPG` (1647), `Космическая фантастика` (1633), `Эзотерика` (1401), `popadanec` (1198). Exact source labels из этого списка теперь resolve автоматически; остальные остаются explicit fallback.
## Примеры mappings
| Code | Категория | Русское название |
|---|---|---|
| `economics_ref` | Деловая литература | Деловая литература |
| `det_classic` | Детективы и триллеры | Классический детектив |
| `child_sf_space` | Детская литература | Детская фантастика: космические приключения, пришельцы |
| `nonf_biography` | Документальная литература | Биографии и мемуары: прочее |
| `love_history` | Любовные романы | Исторические любовные романы |
| `sci_math` | Наука и образование | Математика |
| `adv_maritime` | Приключения | Морские приключения |
| `prose_magic` | Проза | Магический реализм |
| `sf_action` | Фантастика | Боевая фантастика и фэнтези |
| `sf_space` | Фантастика | Космическая фантастика |
| `sf_social` | Фантастика | Социально-психологическая фантастика |
| `humor_prose` | Юмор | Юмористическая проза |
## Проверки реальной library
- Проверено более 50 разных dictionary codes через full 272-entry loader и 261 real code matches.
- Single genre: book 35354, `rus`, tag `sf`.
- Multiple genres: book 31, `rus`, три tags и две presentation categories без duplicate category heading.
- Ukrainian: book 35433, `ukr`, tag `prose_contemporary`.
- English: book 36149, `eng`, tag `antique`.
- Unknown technical: book 35395, `popadanec` + mapped `sf_fantasy`; fallback и mapped category отображаются вместе.
- HTTP 200: mapped code result `/category/stored/2469`, exact-label result `/category/stored/79`, unknown result `/category/stored/2487`, пять representative detail pages.
- Technical `sf_action` не присутствует в rendered mapped result; отображается `Фантастика → Боевая фантастика и фэнтези`.
- Existing category routing, tag IDs, sorting query и book filtering не изменены.
- N+1 не добавлен: directory использует прежний aggregate tags/count query и прежний no-tag count query; hierarchy builder не обращается к DB. Detail преобразует уже загруженную collection одной книги.
## Автоматические проверки
- 27/27 unit tests: 18 existing SEO tests и 9 новых genre tests.
- Python compile: `cps/aubooks_genres.py`, `cps/web.py`, `tests/test_aubooks_genres.py`.
- Jinja parse: 11 AU/standard templates.
- HTTP smoke выполнен для genre results и representative detail pages; общий smoke home/page 2/search/author/series/detail/login также выполнен перед commit.
- `git diff --check` выполнен.
- DEV service active, production не затрагивался.
## Ограничения
- `/category` для anonymous DEV Guest возвращает 404, потому что `SIDEBAR_CATEGORY` отключён в текущей visibility configuration. Permission не обходился и DB не изменялась. Tree проверен unit tests/Jinja; пользователи с включённой category visibility получают hierarchy page.
- 959 real presentation tags отсутствуют в основном словаре после exact-label matching и остаются в `Другие жанры`. Их нормализация требует отдельного подтверждённого словаря, а не предположений.
- `antique=antique` сохранён как в source dictionary.
## Commit
Изменения предназначены для commit `Add AU-Books genre hierarchy`. Итоговый hash указывается в финальном ответе.
