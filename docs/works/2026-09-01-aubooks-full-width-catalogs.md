# Полная ширина текстовых каталогов AU-Books
## Цель
Убрать искусственное ограничение ширины text-list на home, pagination, search, author и series pages.
## Что изучено
- Стили `.aubooks-book-list`, `.aubooks-catalog-book` и `.aubooks-book-annotation`.
- Итоговый DOM целевых страниц DEV.
- Штатные отступы основного Bootstrap content area.
## Изменённые файлы
- `cps/static/css/aubooks.css`
## Изменение
Из `.aubooks-book-list` удалён `max-width: 52rem`. Сохранены:
- `width: 100%` у списка;
- `width: 100%` у каждой книги;
- отсутствие отдельного ограничения ширины аннотации;
- одноколоночный block flow;
- `overflow-wrap: anywhere` для защиты от horizontal overflow;
- штатные боковые padding основного page container на mobile.
Backend, templates, annotations, covers, detail page, OpenDrive и SEO не изменялись.
## Проверки
- Live CSS: список `width: 100%`, `max-width` отсутствует.
- Book item: `width: 100%`, `max-width` отсутствует.
- Annotation: отсутствуют `width` и `max-width`, поэтому она растягивается вместе с item.
- DOM: нет Bootstrap column classes у book items, остаётся одна колонка.
- 320, 390, 768, 1366 и 1920px: ширина определяется только доступной шириной content area; фиксированных или максимальных ограничений нет.
- Horizontal overflow предотвращается переносом длинных строк и штатными page padding.
- HTTP 200: `/`, `/page/2`, search с результатами, author `9463`, series `1600`.
- `git diff --check`: успешно.
## Известные ограничения
Headless browser в окружении отсутствует; viewport-проверка выполнена по live DOM и итоговым CSS-инвариантам без screenshots.
## Commit
`fb067a46 Use full width for AU-Books catalogs`
