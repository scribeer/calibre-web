# 2026-09-05 — Визуальная очистка темы AU-Books

## Цель
Привести тему AU-Books к единому визуальному стилю: тёмные кнопки, минимальный сайдбар (только Категории + Полка), фиксированный размер обложки на странице деталей.

## Что изучено
- Текущий CSS `aubooks.css`: секции 1–23, включая тёмную палитру, Bootstrap-override.
- Шаблон `layout.html`: сайдбар рендерится циклом `for element in sidebar` с ветвлением `cat` (дерево жанров) и `elif` (остальные элементы).
- Шаблон `detail.html`: обложка в `.aubooks-detail-cover-column .cover` без фиксированных размеров.

## Изменённые файлы
1. `cps/static/css/aubooks.css`
2. `cps/themes/aubooks/templates/layout.html`

## Что именно изменено

### 1. Тёмные кнопки
Добавлена секция 24 в `aubooks.css`:
```css
.btn-default {
  background-color: #222222;
  border-color: #333333;
  color: #e0e0e0;
}
```
Состояния `:hover`, `:focus`, `:active`, `[disabled]` — все тёмные. Работает в обеих темах (светлая/тёмная).

### 2. Сайдбар: только Категории + Полка
В `layout.html` удалена ветка `elif` (строки 177–178), которая рендерила `new`, `hot`, `serie`, `author`, `lang`, `rate`, `format`, `read`, `rand`. Теперь в сайдбаре только:
- Заголовок «Категории» + дерево жанров (ветка `cat`)
- Полки (секция shelves, отдельная от цикла `sidebar`)

### 3. Обложка на странице деталей
Добавлены стили:
```css
.aubooks-main .single .aubooks-detail-cover-column .cover {
  width: 160px;
  height: 240px;
}
.aubooks-main .single .aubooks-detail-cover-column .cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
```
Фиксированный контейнер 160×240px, изображение масштабируется с сохранением пропорций.

## Тесты
- `test_cmd_start_book_id.py`: 8/8 PASSED
- Визуальная проверка через curl: сайдбар показывает только Категории + Полка, кнопки `btn-default` получают тёмные стили, CSS подключается корректно.

## Commits
- `9216114a` — aubooks: visual cleanup — dark buttons, minimal sidebar, cover sizing
- `6117b436` — aubooks: dark styling for ALL Bootstrap button variants

---

# Исправление: все кнопки Bootstrap тёмные

## Проблема
Предыдущий commit (`9216114a`) стилизовал только `.btn-default`. Кнопки `.btn-primary` (Download, Edit Metadata), `.btn-success` (Listen), `.btn-info`, `.btn-warning` оставались синими/зелёными Bootstrap-цветами.

## Bootstrap классы, создававшие синие кнопки
- `.btn-primary` — Download, Edit Metadata, Create a Shelf (submit), Login submit, Register submit
- `.btn-success` — Listen (audio ready), Mark as read
- `.btn-info` — теги, идентификаторы
- `.btn-warning` — Retry audio
- `.btn-success.btn-xs` — идентификаторы в listenmp3

## CSS селекторы (добавлены/заменены)
```css
/* Специфичность 0-2-0: .btn.btn-X > Bootstrap .btn-X (0-1-0) */
.btn.btn-default, .btn.btn-primary, .btn.btn-info, .btn.btn-success, .btn.btn-warning {
  background-color: #222222; border-color: #444444; color: #e0e0e0;
}
/* + :hover/:focus, :active/.active, [disabled]/.disabled, .caret */
.btn.btn-danger { background-color: #5c1a1a; border-color: #7a2e2e; color: #e0e0e0; }
/* + :hover, :active, disabled */
/* Pagination: .pagination > li > a/span */
```

Тёмный режим (`[data-theme="dark"]`) аналогично обновлён — вместо `var(--aubooks-accent)` (синий) используется тот же палитра `#222222`.

## Computed styles (Playwright)
| Элемент | bg | color | border |
|---|---|---|---|
| Download (btn-primary) | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Edit Metadata (btn-sm btn-primary) | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Cancel (btn-default) | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Listen (btn-success) | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Retry audio (btn-warning) | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Delete (btn-danger) | rgb(92,26,26) | rgb(224,224,224) | rgb(122,46,46) |
| Login submit | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Register submit | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |
| Pagination link | rgb(34,34,34) | rgb(224,224,224) | rgb(68,68,68) |

Синих кнопок: **0** (все 11 протестированных вариантов — тёмные).

## Browser verification
- Login page: кнопка Submit — тёмная
- Register page: кнопка Submit — тёмная
- Detail page (внутри .single): Search, Close — тёмные
- Инъекция тестовых кнопок со всеми variant'ами — все тёмные
- Hover/focus/active состояния — тёмные
- Нет синего Bootstrap glow

---

# Исправление: Create a Shelf — тёмный

## Проблема
Кнопка `Create a Shelf` в sidebar оставалась синей. Причина: это **не** `.btn` элемент, а普通的 `<a>` внутри `<li id="nav_createshelf" class="create-shelf">`. Наши `.btn.btn-*` overrides её не затрагивали.

## DOM
```html
<li id="nav_createshelf" class="create-shelf">
  <a href="/shelf/create">Create a Shelf</a>
</li>
```

## Какой CSS делал синей
В `aubooks.css` (не Bootstrap!) было правило:
```css
.navigation .create-shelf a {
  background-color: var(--aubooks-link);  /* #1976d2 = СИНИЙ */
  color: var(--aubooks-on-accent);
}
```
Это переопределяло `style.css` (`background: #45b29d` — зелёный) на синий фон темы.

## Исправление
Заменено на:
```css
.navigation .create-shelf a {
  background-color: #222222;
  color: #e0e0e0;
}
.navigation .create-shelf a:hover, .navigation .create-shelf a:focus {
  background-color: #333333;
  color: #ffffff;
}
.navigation .create-shelf a:active {
  background-color: #1a1a1a;
  color: #ffffff;
}
```

## Computed styles (Playwright injection)
| State | bg | color |
|---|---|---|
| Default | rgb(34,34,34) | rgb(224,224,224) |
| Hover | rgb(34,34,34) | rgb(224,224,224) |

Синих/зелёных элементов: **0**.

## Commit
`4e6f8cf5` — aubooks: fix Create a Shelf button — dark styling for sidebar link
