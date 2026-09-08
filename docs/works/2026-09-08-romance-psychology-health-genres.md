# 2026-09-08 — Category Restructure: Романтика + Психология и здоровье

## Цель
1. Переименовать верхнеуровневую категорию `Любовные романы` → `Романтика`
2. Отнести `Легкая эротика` в `Романтика`
3. Объединить всю психологию со здоровьем под `Психология и здоровье`

## Что изменено

### `cps/aubooks_genres.py`

**Category remap** (добавлен после `GENRES = _load_genres()`):
- `_CATEGORY_REMAP` переименовывает `Любовные романы` → `Романтика`
- `_PSYCHOLOGY_HEALTH_CODES` — набор кодов, переносимых в новую категорию:
  - `home_health` (Здоровье, из `Дом и семья`)
  - `sci_psychology_popular` (Популярная психология, из `Дом и семья`)
  - `sci_psychology` (Психология и психотерапия, из `Наука и образование`)
  - `sci_medicine` (Медицина, из `Наука и образование`)
  - `sci_medicine_alternative` (Альтернативная медицина, из `Наука и образование`)
- `CATEGORIES` перестроен из фактических категорий в GENRES (22 вместо 21)

**Aliases** (добавлены в `EXTRA_ALIASES`):
- `Легкая эротика` → `love_erotica` (Романтика)
- `Детская психология` → `sci_psychology` (Психология и здоровье)
- `Медицина` → `sci_medicine` (Психология и здоровье)
- `Здоровье` → `home_health` (Психология и здоровье)

### `tests/test_aubooks_genres.py`

Обновлены 7 существующих тестов:
- `test_source_size_and_categories`: 21 → 22
- `test_flbusta_labels_and_categories`: love_history category → "Романтика"
- `test_sidebar_tree_has_all_categories_and_only_real_mapped_tags`: 21 → 22
- `test_all_22_slugs_are_unique`: 21 → 22
- `test_lybovnoe_fentezi_alias`: category → "Романтика"
- `test_psihologiya_alias`: category → "Психология и здоровье"
- `test_unknown_russian_tag_keeps_readable_label`: заменён тег (Легкая эротика теперь маппится)

Добавлены 12 новых тестов (Wave 3):
- `test_lyubovnyj_roman_alias_to_romance`
- `test_love_fantasy_alias_to_romance`
- `test_light_erotica_alias_to_romance`
- `test_love_code_maps_to_romance`
- `test_psihologiya_alias_to_psychology_health`
- `test_psy_theraphy_alias_to_psychology_health`
- `test_foreign_psychology_alias_to_psychology_health`
- `test_detskaya_psihologiya_alias_to_psychology_health`
- `test_medicina_alias_to_psychology_health`
- `test_zdorove_alias_to_psychology_health`
- `test_sci_psychology_code_to_psychology_health`
- `test_sci_medicine_code_to_psychology_health`

## Результаты

### Before/After
| | Before (wave 2) | After (wave 3) | Delta |
|---|---|---|---|
| Unmapped tags | 910 | 908 | -2 |
| Books in fallback | 12,350 | 11,407 | -943 |

### Категории
| Категория | Книг |
|---|---|
| Романтика | 24,728 |
| Психология и здоровье | 5,158 |
| Другие жанры (unmapped) | 11,407 |

### Browser verification
- Книга с love-жанром → `Романтика` ✓
- Книга с `Легкая эротика` → `Романтика` ✓
- Книга с психологией → `Психология и здоровье` ✓
- Старые верхние labels (`Любовные романы` как верхний уровень) не отображаются ✓
- Поджанры (например, `Любовные романы` как дочерний жанр `Романтика`) сохранены ✓

## Commit
Local only, push не выполнялся.
