# Simplify Sidebar and Book Controls — 2026-09-08

## Цель

Убрать из интерфейса AU-Books три ненужных элемента: заголовок "Просмотр" в сайдбаре и чекбоксы "Прочесть"/"Архивировать" на странице книги.

## Что убрано

### Сайдбар

Удалён визуальный заголовок `<li class="nav-head hidden-xs">{{_('Browse')}}</li>` (переводится как "Просмотр"). Пункты навигации под ним (Категории, Полки) остались на месте.

### Страница книги

Удалены два элемента:

1. **Прочесть (Read)** — checkbox/form для отметки книги прочитанной (`have_read_form`)
2. **Архивировать (Archive)** — checkbox/form для архивирования книги (`archived_form`)

Обёртка `custom_columns` и условие `if not current_user.is_anonymous` также удалены.

## Изменённые файлы

- `cps/themes/aubooks/templates/layout.html` — удалена строка с `<li class="nav-head hidden-xs">{{_('Browse')}}</li>`
- `cps/themes/aubooks/templates/detail.html` — удалены формы `have_read_form` и `archived_form`

## Способ

Изменения только в AU-Books templates. Backend-функциональность Calibre-Web не затронута. Другие темы не изменены.

## Browser verification

- `Просмотр` больше нет в визуальном сайдбаре (остался только в `aria-label` для accessibility)
- `Прочесть` отсутствует на странице книги
- `Архивировать` отсутствует на странице книги
- Остальная информация и действия на странице книги не пострадали
- Mobile layout не нарушен

## Tests

- 135 tests pass (все существующие)
- Дополнительные regression tests не требуются (UI-only изменения, проверены визуально)

## Commit

- `e9126286` — ui: simplify sidebar and book detail controls