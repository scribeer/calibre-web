# Аудит AU-Books перед внедрением light/dark mode
## Цель
Подготовить точную карту цветов, конфликтов Bootstrap, accessibility-рисков и минимальной архитектуры полноценной светлой/тёмной темы без white flash. В рамках задачи код, CSS, templates, JavaScript, backend, SEO, OpenDrive и production не изменялись.
## Область аудита
Проверены:
- `cps/static/css/aubooks.css`;
- `cps/static/css/style.css`, Bootstrap 3.4.1 и подключаемые plugins;
- AU-Books templates и standard templates, наследуемые через fallback;
- normal site JavaScript и отдельные reader theme implementations;
- live DEV страницы home, pagination, search, author, series, detail, login и advanced search;
- source markup недоступных гостю dropdown/modal/table/admin states.
Live inspection выполнялся через HTTP/DOM и исходный CSS. Графического browser executable в окружении нет, поэтому computed styles, screenshots, forced-colors и реальная отрисовка JS-generated открытых widgets не проверялись.
## Загрузка CSS
Обычные AU-Books страницы загружают стили в порядке:
1. `cps/static/css/libs/bootstrap.min.css`;
2. page-specific plugin CSS из `{% block header %}`;
3. `cps/static/css/style.css`;
4. `cps/static/css/upload.css`;
5. `cps/static/css/aubooks.css`.
Порядок задаёт `cps/themes/aubooks/templates/layout.html:17-23`. Это позволяет держать dark overrides в `aubooks.css`, но более специфичные Bootstrap/plugin selectors и их `!important` потребуют достаточной специфичности.
## Количество hardcoded цветов
Методика: считались CSS declarations в color-bearing properties (`color`, `background*`, borders, shadows, outline, `fill`, `stroke`) со значениями hex/rgb/rgba/hsl, named `white`/`black`, `transparent` или `currentColor`. Комментарии и selector text не учитывались.
### Normal AU application shell
| Файл/группа | Hardcoded declarations | Color literal occurrences |
|---|---:|---:|
| `bootstrap.min.css` | 634 | 744 |
| `style.css` | 58 | 58 |
| `upload.css` | 0 | 0 |
| `aubooks.css` | 24 | 24 |
| Typeahead | 28 | 34 |
| Bootstrap Datepicker | 170 | 170 |
| Bootstrap Select | 19 | 19 |
| Bootstrap Table | 15 | 15 |
| Bootstrap Editable | 88 | 138 |
| WYSIHTML5 | 16 | 19 |
| **Итого normal shell/plugins** | **1 052** | **1 221** |
Дополнительно найдено 14 legacy filter literals вне выбранного набора properties.
### Standalone/basic/readers
В `basic.css`, reader `main.css`, `viewer.css`, `Djvu_html5.css`, `kthoom.css`, `popup.css`, `reader.css`, `epub_themes.css`, audio/player CSS и связанных файлах найдено ещё **409 hardcoded declarations**.
**Общий исследованный CSS total: 1 461 hardcoded color declaration.** Первая реализация site theme должна покрывать 1 052 declarations normal shell через semantic overrides; reader themes следует оставить отдельной задачей.
### Не-CSS источники
- `cps/static/js/main.js:103-125` динамически задаёт drag-and-drop background `#e6e6e6` inline и затем очищает его.
- `cps/themes/aubooks/templates/login.html:27` содержит Google SVG `fill="#FFC107"`.
- GitHub SVG в `login.html:26` не задаёт fill и использует default black, что опасно на dark surface.
- Inherited `register.html` содержит GitHub/Google SVG с inline brand fills.
- EPUB/comic/DjVu readers динамически задают собственные theme/canvas colors; это отдельная подсистема.
## Полная карта `aubooks.css`
В `cps/static/css/aubooks.css` найдено 24 hardcoded declarations:
- skip link: `#111`, `#fff`;
- focus/focus-visible: `#111`, `#ffd600`, часть правил с `!important`;
- links/brand/create shelf: `#176b60`, `#fff`;
- author/navigation muted text: `#595959`;
- footer: border `#aaa`, text `#444`;
- dropdown action: transparent, `#333`, hover `#f5f5f5`, `#176b60`;
- cover button: transparent;
- catalog separator: `#b8b8b8`;
- book metadata: `#555`.
Самые опасные AU rules: white/black skip link, black/yellow focus ring, light dropdown hover, muted/footer text и catalog borders. Ни один из них сейчас не связан с semantic variable.
## Карта компонентов
| Компонент | Текущий источник цвета | Риск для dark mode |
|---|---|---|
| Body/page | Bootstrap `body #333/#fff`, затем `style.css` background `#f2f2f2` | Dark background без явного text override или наоборот создаст нечитаемый initial state |
| Header/navbar | Bootstrap `.navbar-default` `#f8f8f8`, border `#e7e7e7`, links `#777/#333`; toggle black в `style.css` | Белая полоса, слабые borders, неверные active/open/disabled states |
| Sidebar | `.navigation li a #444`, `.nav-head #999/#595959`, border `#ccc`, rgba hover | Muted text и hover недостаточны на dark surface |
| Main content | В основном inheritance от body/Bootstrap | Нужны явные background/text roles для fallback templates |
| Catalog list | AU separator `#b8b8b8`, metadata `#555` | Separator и muted metadata требуют dark equivalents |
| Book title links | AU `#176b60`, underline | Цвет хорош в light, но слишком тёмный на dark; underline нужно сохранить |
| Author/series/metadata | `#595959`, `#555`, upstream `#444/#999` | Часть upstream selectors специфичнее AU и может сохранить серый light palette |
| Annotations | Наследуют body text | Должны наследовать `--aubooks-text`, не отдельный fixed color |
| Pagination/pager | Bootstrap white items, `#ddd` borders, `#eee` hover, disabled white | Один из главных источников белых плиток |
| Buttons | Bootstrap variants; `.btn-default` white; AU меняет только hover text | Нужны normal/hover/focus/active/open/disabled для каждого используемого variant |
| Forms | `.form-control` white, `#ccc`, placeholder `#999`, disabled `#eee`; addons и validation pastels | Белые inputs, слабые borders/placeholders, native autofill conflict |
| Dropdowns | `.dropdown-menu` white, `#333`, `#f5f5f5`; AU меняет только child button | Parent menu останется белым; active/disabled/divider/caret тоже требуют overrides |
| Modals | `.modal-content` white, `#e5e5e5` borders, black close/shadows | Глобальный modal присутствует на всех страницах и даст крупную белую surface |
| Flash messages | Bootstrap pastel `.alert-*` | Нужны semantic text/background/border pairs, роли live region менять нельзя |
| Breadcrumbs | Bootstrap `#f5f5f5`, separator `#ccc`, current `#777` | Белая detail stripe и слабый current text |
| Search controls | `.btn-primary`, shelf dropdowns, Bootstrap plugin widgets | Active/current/pressed states и generated menus должны быть различимы |
| Sorting/filter controls | Bootstrap primary states + AU focus | Нельзя потерять `aria-current`/`aria-pressed` визуальное отличие |
| Login | `.well #f5f5f5`, forms, input group, `.btn-default`, `.alert-danger` | Белая card/input surfaces; GitHub SVG default black может исчезнуть |
| Detail | Breadcrumb, labels, `.btn-info`, toolbar/dropdowns, comments, more-stuff border | `.btn-info` уже имеет слабый light contrast; labels/dropdowns могут остаться светлыми |
| Cover area | Transparent button, image; no theme surface contract | Не добавлять декоративную белую подложку; failed cover оставляет upstream grid column |
| Tables | Bootstrap white nested table, `#ddd`, striped/hover `#f9f9f9/#f5f5f5` | Auth/admin pages станут белыми; meaningful grid lines требуют >=3:1, если это единственная граница |
| Tooltips | `style.css` white background и `#ddd` text | Текущий contrast около 1.36:1; selector специфичнее Bootstrap `.tooltip-inner` |
| Popovers | Bootstrap white surface, `#f7f7f7` title, white arrow | Требуют surface/title/border/arrow overrides |
| Footer | AU border `#aaa`, text `#444` | Нужны border/muted variables |
## Bootstrap и plugin conflicts
### Критические Bootstrap selectors
Наиболее опасны:
```css
body
.navbar-default
.navbar-default .navbar-nav > li > a
.navbar-default .navbar-nav > .active > a
.navbar-default .navbar-nav > .open > a
.navbar-default .navbar-toggle
.form-control
.form-control[disabled]
.form-control[readonly]
.form-control::placeholder
.input-group-addon
.btn-default
.open > .dropdown-toggle.btn-default
.dropdown-menu
.dropdown-menu > li > a
.dropdown-menu > .active > a
.dropdown-menu > .disabled > a
.modal-content
.modal-header
.modal-footer
.pagination > li > a
.pagination > li > span
.pagination > .disabled > span
.alert-success
.alert-info
.alert-warning
.alert-danger
.breadcrumb
.table
.table-striped > tbody > tr:nth-of-type(odd)
.table-hover > tbody > tr:hover
.panel
.panel-body
.well
.list-group-item
.tooltip-inner
.tooltip.bottom .tooltip-inner
.popover
.popover-title
```
Особо важно переопределять полные state groups: normal, hover, focus, active/current, open, selected и disabled. Изменение только базового selector оставит белые Bootstrap states.
### Plugins
- Typeahead: `.tt-menu`, `.tt-suggestion`, `.tt-cursor`, `.tt-hint`, disabled input.
- Datepicker: popup/arrow, day/month/year, old/new/today/range/active/disabled/hover.
- Bootstrap Select: toggle, menu, search input, header/divider, selected/disabled/no-results/actions.
- Bootstrap Table: loading overlay, toolbar, rows, pagination, selected/disabled.
- Bootstrap Editable: editable links/errors и собственная legacy datepicker copy.
- WYSIHTML5: toolbar/menu chrome. Content color swatches должны сохранить смысл и не заменяться theme variables.
Plugin CSS загружается раньше `aubooks.css`, но часто имеет высокую specificity.
## Standard fallback и отдельные документы
AU template fallback реализован в `cps/render_template.py`; большинство inherited account/admin/shelf/table/edit templates всё равно extends AU `layout.html` и могут быть покрыты central CSS.
Отдельные документы обходят normal AU layout:
- `standard/http_error.html` не загружает `aubooks.css`;
- `standard/shelfdown.html` загружает theme CSS, но не имеет early resolver и switcher;
- `basic_layout.html` использует отдельный `basic.css`;
- EPUB/PDF/TXT/DjVu/comic/audio readers имеют самостоятельные heads, CSS и theme preferences.
Для первого site-theme этапа readers лучше явно исключить. Для consistent error/shelf download нужны AU overrides или общий минимальный resolver.
## Accessibility и contrast
### Текущие проходящие сочетания
- AU link `#176b60` на `#f2f2f2`: около 5.67:1.
- White на AU green `#176b60`: около 6.35:1.
- Metadata `#555` на `#f2f2f2`: около 6.66:1.
- Body `#333` на `#f2f2f2`: около 11.29:1.
- Bootstrap primary white на `#337ab7`: около 4.56:1, минимальный запас.
### Потенциальные проблемы уже в light mode
- Tooltip `#ddd` на white: около 1.36:1, критический fail.
- `.btn-info` white на `#5bc0de`: около 2.09:1; detail tags используют small text.
- Placeholder/typeahead `#999` на white: около 2.85:1.
- Navbar `#777` на `#f8f8f8`: около 4.22:1.
- Breadcrumb current `#777` на `#f5f5f5`: около 4.11:1.
- `.label-default` white на `#777`: около 4.48:1.
- Form border `#ccc` на white: около 1.61:1.
- Catalog separator `#b8b8b8` на `#f2f2f2`: около 1.77:1.
- Footer border `#aaa` на `#f2f2f2`: около 2.08:1.
Disabled text формально имеет исключение WCAG, но должен оставаться различимым и не выглядеть активным. Meaningful borders для controls/regions должны стремиться к 3:1, если другой visual cue отсутствует.
### Focus
Текущий dual ring: black `#111` outline + yellow `#ffd600` halo. Он хорошо заметен в light mode, но black inner ring исчезнет на тёмном фоне. Следует сохранить толщину, offset, двухцветность, selector coverage и `!important`, заменив inner color на theme-aware `--aubooks-focus-contrast`. Не изменять skip-link behavior, modal focus trap, `aria-current`, `aria-pressed`, live regions и heading hierarchy.
## Рекомендуемые CSS variables
Минимальный semantic набор:
```css
:root {
  --aubooks-bg: ...;
  --aubooks-surface: ...;
  --aubooks-surface-raised: ...;
  --aubooks-surface-hover: ...;
  --aubooks-text: ...;
  --aubooks-text-muted: ...;
  --aubooks-link: ...;
  --aubooks-link-hover: ...;
  --aubooks-border: ...;
  --aubooks-border-strong: ...;
  --aubooks-focus: ...;
  --aubooks-focus-contrast: ...;
  --aubooks-accent: ...;
  --aubooks-on-accent: ...;
  --aubooks-control-bg: ...;
  --aubooks-placeholder: ...;
  --aubooks-backdrop: ...;
  --aubooks-danger: ...;
  --aubooks-danger-surface: ...;
  --aubooks-success: ...;
  --aubooks-success-surface: ...;
  --aubooks-warning: ...;
  --aubooks-warning-surface: ...;
  --aubooks-info: ...;
  --aubooks-info-surface: ...;
}
```
Control text использует `--aubooks-text`, control border — `--aubooks-border-strong`; отдельные variables для каждого Bootstrap component не нужны. Semantic alert borders можно получать из strong border или semantic foreground после contrast validation.
Light values сначала должны воспроизвести текущий AU visual contract, одновременно исправив tooltip/placeholder/info contrast. Dark values задаются одним root override, а selectors компонентов используют только variables.
## Выбор режима
Рекомендуются **три режима: system, light, dark**.
- Default: `system`.
- Storage key: `aubooks.colorTheme`.
- Допустимые значения: только `system`, `light`, `dark`; invalid value трактуется как `system`.
- В storage хранится preference, а не resolved color, иначе выбор system потеряется.
- `localStorage`, `matchMedia` и storage listener оборачиваются безопасно.
- При `system` слушать `matchMedia('(prefers-color-scheme: dark)').change`.
- Синхронизировать открытые вкладки через `storage` event.
Два режима проще только визуально, но лишают пользователя ожидаемого default-follow-system поведения и возможности вернуть системный режим после ручного выбора.
## Предотвращение white flash
Лучшее место resolver — `cps/themes/aubooks/templates/layout.html` сразу после `<meta charset>` (`layout.html:7`) и до первого stylesheet (`layout.html:17`).
Последовательность:
1. Маленький inline script синхронно читает `aubooks.colorTheme` в `try/catch`.
2. Для system/invalid preference синхронно проверяет `matchMedia`.
3. До загрузки Bootstrap выставляет на `<html>` resolved `data-theme="light|dark"` и optional `data-theme-preference="system|light|dark"`.
4. Минимальный inline root style задаёт initial `background` и `color-scheme`, чтобы browser canvas не был белым при задержке внешнего CSS.
5. Основной CSS загружается уже с правильным root state.
Не следует скрывать body до JS: ошибка script оставит пустую страницу. Не следует ждать bottom script или DOMContentLoaded: это слишком поздно. Не добавлять theme transitions на initial load.
### Без JavaScript
- Не выставлять static `data-theme="light"`.
- Base variables — light.
- `@media (prefers-color-scheme: dark) { :root:not([data-theme]) { ...dark variables... } }` обеспечивает system dark.
- Switcher скрыт без `html.js`, так как изменить preference он не сможет.
- Страница остаётся полностью доступной.
## Accessible theme switcher
Рекомендуемое место: первым постоянным `<li>` внутри `ul#main-nav` сразу после `layout.html:58`.
Преимущества:
- доступен anonymous/login/authenticated users;
- находится внутри существующего mobile collapse;
- на mobile остаётся до перемещаемого `#scnd-nav`;
- не перегружает brand/toggle area;
- не исчезает вместе с sidebar.
Рекомендуемый control — native `<select>`, не binary switch:
```html
<li class="aubooks-theme-control">
  <label for="aubooks-color-theme">Theme</label>
  <select id="aubooks-color-theme" name="aubooks-color-theme">
    <option value="system">Use device setting</option>
    <option value="light">Light</option>
    <option value="dark">Dark</option>
  </select>
</li>
```
- Видимый короткий label предпочтительнее icon-only UI.
- Native select уже имеет keyboard и screen-reader semantics; `role="switch"` и `aria-pressed` не нужны.
- Не объявлять смену темы через live region: выбранная option уже сообщает состояние.
- Labels/options должны проходить gettext.
- Альтернатива — fieldset из трёх radios, семантически хорошая, но менее компактная для navbar.
## Reduced motion и browser integration
- В AU CSS нет theme transitions; skip link меняется transform без transition.
- Bootstrap содержит fade/collapse/modal/carousel/progress transitions.
- `main.js:792` вызывает smooth `window.scrollTo`.
- Добавить `@media (prefers-reduced-motion: reduce)` для normal UI transitions/animations; JS smooth scroll должен выбирать `auto` при reduce.
- На первом этапе вообще не добавлять color transitions. Если они появятся позже, включать только после initial resolution и при `no-preference`.
- Добавить root `color-scheme: light`/`dark`, чтобы native inputs, selects, scrollbars и browser UI соответствовали mode.
- Сейчас `<meta name="theme-color">` отсутствует. Для no-JS system можно добавить две media-aware meta entries; early/runtime script должен обновлять browser chrome при explicit saved choice.
## DEV inspection
Проверены HTTP 200:
- `/`, `/page/2`;
- `/search/stored?query=test` и empty search;
- `/author/9463`;
- `/series/1600`;
- `/books/georgiy-persikov/delo-o-medvezhem-posohe`;
- `/login`;
- `/advsearch`.
Подтверждены реальные компоненты: navbar/search/sidebar/footer, full-width text catalog, pagination, search live status и sorting, author/series headings, detail breadcrumb/labels/comments/toolbar/deferred cover, login well/forms/password toggle, advanced-search selectpicker/typeahead/datepicker source controls и глобальный book modal.
Guest session не показал shelf dropdowns, authenticated tables/admin dialogs и открытые plugin widgets; они проверены по templates/CSS/JS. Bare directory routes скрыты текущими visibility settings.
## Файлы следующего этапа
### Обязательные
1. `cps/themes/aubooks/templates/layout.html`
   - early resolver, root state, theme-color meta, navbar select.
2. `cps/static/css/aubooks.css`
   - variables, light/dark/system roots, Bootstrap/plugin overrides, focus, reduced motion, switcher styling.
3. `cps/static/js/aubooks-pages.js`
   - select synchronization, change handler, media-query и cross-tab listeners, safe storage.
4. `cps/static/js/main.js`
   - заменить inline drag background `#e6e6e6` на state class; учитывать reduced-motion smooth scroll.
### Вероятные AU overrides
5. `cps/themes/aubooks/templates/login.html` — GitHub `currentColor`, контраст icon container.
6. Новый `cps/themes/aubooks/templates/register.html` — inherited OAuth SVG handling.
7. Новый `cps/themes/aubooks/templates/shelfdown.html` — root resolver на standalone page.
8. Новый `cps/themes/aubooks/templates/http_error.html` — AU CSS/resolver для error page.
Vendored Bootstrap/plugin CSS менять не следует. Readers (`read*.html`, PDF/EPUB/comic/audio JS/CSS) не включать в первый site-theme этап.
## Рекомендуемый порядок реализации
1. Зафиксировать проверенную light/dark palette и contrast matrix для core variables.
2. Ввести variables в `aubooks.css`, не меняя визуально light mode.
3. Покрыть foundation: html/body/text/links/focus/navbar/sidebar/main/footer.
4. Покрыть Bootstrap surfaces: controls/buttons/dropdowns/modals/pagination/alerts/breadcrumbs/panels/wells/tables/tooltips/popovers.
5. Покрыть Typeahead/Datepicker/Select/Table/Editable/WYSIHTML5 generated states.
6. Добавить no-JS `prefers-color-scheme` fallback и `color-scheme`.
7. Добавить early resolver и minimal initial root style; проверить saved light/dark/system, blocked/invalid storage и отсутствие FOUC.
8. Добавить accessible navbar select и runtime synchronization.
9. Убрать JS hardcoded drag color, проверить dynamic alerts/modals/dropdowns.
10. Добавить login/register/error/shelfdown exception handling.
11. Добавить reduced-motion behavior и dynamic theme-color.
12. Выполнить browser matrix: desktop/mobile, no-JS, keyboard, screen reader, zoom, forced colors, autofill/disabled/forms, authenticated/admin/plugin pages.
## Известные ограничения аудита
- Нет graphical/computed-style browser inspection.
- JS-generated открытые dropdown/date/select widgets проверены по source, не визуально.
- Нет authenticated/admin session для live tables, upload, tasks и destructive dialogs.
- Readers сознательно отделены от normal AU site theme.
## Commit
Отчёт предназначен для commit `Document AU-Books dark theme audit`; итоговый hash указывается в финальном ответе.
