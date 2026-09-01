# Реализация light/dark тем AU-Books: первый этап

## Цель

Реализовать три режима темы (system, light, dark) для normal AU shell с anti-FOUC, accessible switcher, CSS custom properties и полным покрытием Bootstrap компонентов.

## CSS Variables

31 уникальная CSS custom property, организованная в группы:

**Поверхности:** `--aubooks-bg`, `--aubooks-surface`, `--aubooks-surface-raised`, `--aubooks-surface-hover`
**Текст:** `--aubooks-text`, `--aubooks-text-muted`, `--aubooks-text-subtle`
**Ссылки:** `--aubooks-link`, `--aubooks-link-hover`, `--aubooks-link-muted`
**Границы:** `--aubooks-border`, `--aubooks-border-strong`
**Фокус:** `--aubooks-focus`, `--aubooks-focus-ring`
**Акцент:** `--aubooks-accent`, `--aubooks-on-accent`
**Контролы:** `--aubooks-control-bg`, `--aubooks-placeholder`
**Семантические:** success/warning/danger/info (text + surface + base)

## Palette

### Light

Сохраняет текущий визуальный контракт AU-Books:
- `--aubooks-bg: #f2f2f2` (текущий background body)
- `--aubooks-surface: #ffffff`
- `--aubooks-text: #333333`
- `--aubooks-link: #176b60` (текущий AU green)
- `--aubooks-border: #dddddd`

### Dark

Спокойная тёмная палитра для чтения:
- `--aubooks-bg: #121212`
- `--aubooks-surface: #1e1e1e`
- `--aubooks-surface-raised: #252525`
- `--aubooks-text: #e0e0e0` (не чистый белый)
- `--aubooks-link: #4db8a4` (lightened AU green для контраста)
- `--aubooks-focus-ring: #ffd600` (сохранён жёлтый фокус)

## Anti-FOUC

Inline script в `<head>` сразу после `<meta charset>`:

1. Читает `localStorage.getItem("aubooks-theme")`
2. При `system` или invalid значении проверяет `matchMedia("(prefers-color-scheme: dark)")`
3. Синхронно устанавливает `document.documentElement.setAttribute("data-theme", "light|dark")`
4. Не зависит от jQuery, не бросает exceptions при недоступном localStorage
5. Не скрывает body — minimal canvas paint предотвращён через root background в CSS

## Storage

- **Ключ:** `aubooks-theme`
- **Значения:** `system`, `light`, `dark`
- **Default:** `system`
- **Invalid:** fallback на `system`
- **Mechanism:** `localStorage`, без cookies/backend/DB

## Theme Resolution

```
system → matchMedia.dark ? "dark" : "light"
light  → "light"
dark   → "dark"
invalid/missing → "system" (как выше)
```

## Selector Behavior

Native `<select>` в первом `<li>` `#main-nav`:

```html
<li class="aubooks-theme-control">
  <label for="aubooks-color-theme">Theme</label>
  <select id="aubooks-color-theme">
    <option value="system">System</option>
    <option value="light">Light</option>
    <option value="dark">Dark</option>
  </select>
</li>
```

- Has accessible name через `<label>` + `aria-label`
- Keyboard accessible (native select)
- Visible на desktop и mobile (внутри collapse)
- При смене: сохраняет в localStorage, применяет без reload
- При `system`: слушает `matchMedia` change event
- Cross-tab sync через `storage` event

## Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## color-scheme

- Root `color-scheme: light` по умолчанию
- `[data-theme="dark"]` → `color-scheme: dark`
- Нативные формы, scrollbar, autofill следуют системе

## Покрытые Bootstrap компоненты (dark overrides)

| Компонент | Overrides |
|---|---|
| Body/page | background, color |
| Navbar | background, border, nav links, toggle, collapse, form |
| Forms | form-control, placeholder, disabled, input-group-addon, select, textarea |
| Buttons | btn-default (all states), btn-primary, btn-success/warning/danger/info |
| Dropdowns | menu, items, active, disabled, divider, caret |
| Modals | content, header, footer, backdrop, close |
| Pagination | items, active, disabled, hover/focus |
| Alerts | success, info, warning, danger |
| Breadcrumbs | background, separator, active |
| Tables | borders, striped, hover, bordered |
| Panels | heading, body, footer |
| Wells | background, border |
| List groups | items, hover, active |
| Tooltips | inner, arrow positions |
| Popovers | content, title, arrows |
| Labels | all variants |
| Badges | background, color |
| Close button | color |
| Dividers | hr border |

## Покрытые Plugin компоненты

| Plugin | Overrides |
|---|---|
| Typeahead | menu, suggestion, cursor, hint |
| Datepicker | table, cells, active/today/disabled/old/new, nav, dropdown |
| Bootstrap Select | toggle, menu, items, selected, disabled, search input |
| Bootstrap Table | container, header, rows, toolbar, search, pagination, loading |
| Bootstrap Editable | editable links, form control |
| WYSIHTML5 | toolbar, buttons, sandbox |

## Покрытые AU компоненты

| Компонент | Override |
|---|---|
| Sidebar | background, links, hover, active, badges |
| Flash messages | all 4 types (danger/success/info/warning) |
| Login well | background, border |
| Detail breadcrumb | background, text |
| Book card titles | link color |
| Catalog separators | border |
| Dropdown actions | text, hover |
| Footer | border, text |
| Drag-and-drop | CSS class `.drag-over` с theme variable |

## Изменённые файлы

1. `cps/static/css/aubooks.css` — variables, palettes, all dark overrides
2. `cps/themes/aubooks/templates/layout.html` — anti-FOUC script, theme selector
3. `cps/static/js/aubooks-pages.js` — runtime theme switching, media listener, cross-tab sync
4. `cps/static/js/main.js` — replaced inline `#e6e6e6` drag color with `.drag-over` CSS class

## Оставшиеся белые surfaces

В normal shell не перекрыты:
- Plugin-generated dropdowns при открытии через Bootstrap JS (datepicker popup, typeahead menu) — перекрыты через CSS, но не проверены визуально
- Admin-specific tables и forms — не были доступны для проверки
- Tooltip из `style.css` с `background-color: #fff` — перекрыт через `[data-theme="dark"] .tooltip.bottom .tooltip-inner`
- `.btn-info` text contrast в light mode — существующий проблема, не решалась в этом этапе

## Что не охвачено

- Standalone readers (EPUB/PDF/comic/audio/DjVu)
- `basic_layout.html` и `basic.css`
- `standard/http_error.html` (не загружает aubooks.css)
- `shelfdown.html` (standalone page)
- `register.html` (Google/GitHub SVG fills)
- Forced colors / high contrast mode
- Computed-style browser inspection
- Authenticated admin tables, upload, tasks dialogs

## Технические проверки

- `git diff --check`: clean
- Jinja parse: 10 templates OK
- JS syntax (`node --check`): both files OK
- HTTP smoke: 200 on `/`, `/page/2`, `/search`, `/login`
- DOM checks: theme selector present on all 8 tested pages
- Anti-FOUC script position: after `<meta charset>`, before stylesheets
- No hardcoded `#e6e6e6` in main.js

## localStorage Key

`aubooks-theme`

## Как работает system mode

1. При загрузке: `matchMedia("(prefers-color-scheme: dark)")` определяет resolved theme
2. При выборе `system` в select: привязывается `mediaQuery.addEventListener("change")`
3. При смене системной темы: автоматически обновляет `data-theme`
4. При выборе `light`/`dark`: listener не активен, system changes игнорируются

## Как предотвращён white flash

Inline script в `<head>` синхронно устанавливает `data-theme` до загрузки CSS. CSS переменные определены в `:root` как light, dark override через `[data-theme="dark"]`. Canvas paint происходит уже с правильным background через CSS custom properties.

## Результат проверок

Все static/runtime проверки пройдены. Service активен на DEV.
