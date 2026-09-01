# Текстовые каталоги AU-Books
## Цель
Перевести основные списки книг AU-Books из многоколоночных карточек в единую одноколоночную текстовую ленту с безопасными превью аннотаций без обложек.
## Что изучено
- Маршруты и query-пути главной, pagination, обычного и расширенного поиска, страниц автора и серии.
- Общий partial `cps/themes/aubooks/templates/_book_card.html` и использующие его шаблоны.
- Модель Calibre: аннотация хранится в `comments.text` и доступна через lazy relationship `Books.comments`.
- Штатная очистка описаний фильтром `clean_string` из `cps/clean_html.py`.
- `list.html` и `grid.html`: это каталоги авторов/серий/категорий, а не списки отдельных книг; ведущие из них author/series book routes переведены на новый формат.
## Изменённые файлы
- `cps/themes/aubooks/templates/_book_card.html`
- `cps/themes/aubooks/templates/index.html`
- `cps/themes/aubooks/templates/search.html`
- `cps/themes/aubooks/templates/author.html`
- `cps/static/css/aubooks.css`
- `cps/db.py`
- `cps/search.py`
- `cps/web.py`
## Страницы
Общий text-list item используется на:
- `/` и `/page/<n>`;
- обычных и расширенных search results;
- страницах книг автора;
- страницах книг серии;
- остальных AU-Books book collections, использующих `index.html`, как одноколоночная структура без Bootstrap `col-*`.
Внешний раздел Goodreads на author page также сделан одноколоночным. Directory views `list.html` и `grid.html` не отображают отдельные книги и не менялись.
## Структура книги
```html
<article class="aubooks-catalog-book">
  <h2 class="title"><a href="/books/author-slug/book-slug">Название</a></h2>
  <p class="author">Автор: ...</p>
  <p class="series">Серия: ... (номер)</p>
  <div class="aubooks-book-metadata">Форматы, рейтинг, статус чтения</div>
  <div class="aubooks-book-annotation">Текст аннотации...</div>
</article>
```
На author page после `h1` и `h2` названия книг используют `h3`; на home/search/series после `h1` используются `h2`. Ссылкой является только название, а не весь блок.
## Аннотация
- Источник: `comments.text` из Calibre `metadata.db` через `Books.comments`.
- Пустая или отсутствующая аннотация не создаёт DOM-блок и не оставляет место.
- Исходный HTML сначала очищается штатным `clean_string`, затем превращается в неинтерактивный текст через `striptags` и `trim`.
- Текстовый preview исключает скрытые focusable links и изображения внутри визуально обрезанной области.
- CSS ограничивает preview высотой `9.3em`, примерно шестью строками при `line-height: 1.55`; сервер не обрезает строку и не ломает HTML-теги.
## Backend и N+1
Добавлен opt-in параметр `load_comments` в `fill_indexpage()` и `get_search_results()`. Home, author, series и search включают `selectinload(Books.comments)`; advanced search применяет тот же loader к своему result query. Другие вызывающие коды сохраняют прежнее поведение по умолчанию.
Проверка SQLAlchemy на выборках по 60 книг для home, search, author и series:
- `comments_queries`: 1 на выборку;
- дополнительных запросов при чтении `book.comments`: 0;
- отдельных запросов на каждую книгу нет.
## Layout и responsive
- `.aubooks-book-list`: обычный block flow, `width: 100%`, `max-width: 52rem`.
- `.aubooks-catalog-book`: `width: 100%`, вертикальные отступы и нижний разделитель.
- Нет grid/flex layout и Bootstrap `col-xs/sm/md/lg-*` у book items.
- `overflow-wrap: anywhere` защищает 320/360/390/768px от переполнения длинными названиями и metadata.
- На mobile размер названия 20px, аннотации 16px; на desktop название 22px, список остаётся одной колонкой и не растягивается шире 52rem.
Проверка выполнена структурно по итоговому DOM/CSS для 320, 360, 390, 768px и desktop. Headless browser в окружении отсутствует, поэтому отдельные viewport screenshots не создавались.
## Проверки DEV
- `/`, `/page/2`, `/page/500`: HTTP 200, 60 основных книг на странице и 4 random books при включённом Discover.
- Search с результатами: HTTP 200, 60 text-list items, result live region и sorting semantics сохранены.
- Search без результатов: HTTP 200, heading и hint сохранены, book items отсутствуют.
- Author `9463`: HTTP 200, 60 книг на странице; author `3`: HTTP 200, 1 книга.
- Series `1600`: HTTP 200, 60 книг, у всех сохранена позиция серии.
- Проверены длинная, короткая и отсутствующая аннотация; книги с серией и без; title длиной 70 символов; RU/UK/EN metadata records.
- Во всех book items: 0 `<img>`, 0 `/cover/` URL, 0 Bootstrap column classes.
- Sanitization sample: 0 пустых annotation blocks, 0 вложенных HTML tags после text conversion.
- Один `h1` на каждой целевой странице; heading levels и DOM order корректны.
- Detail page и `/cover/1/og`: HTTP 200; deferred OpenDrive cover сохранён.
- `git diff --check`: успешно.
- Python compile (`cps/db.py`, `cps/web.py`, `cps/search.py`): успешно.
- Jinja parse четырёх изменённых templates: успешно.
- JavaScript syntax: успешно.
- Existing tests: 18/18 успешно.
- HTTP smoke всех целевых routes: успешно.
## Известные ограничения
- Directory routes `/author` и `/series` возвращают 404 при текущих DEV visibility settings; их реальные destination routes author/series проверены напрямую.
- CSS preview намеренно показывает очищенный plain text, а не исходное форматирование HTML-аннотации.
## Commit
`bb667df3 Make AU-Books catalogs text lists`
