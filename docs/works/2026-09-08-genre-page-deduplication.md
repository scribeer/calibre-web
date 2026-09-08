# Дедупликация строк на странице Жанры

## Цель
Убрать дублирующиеся строки на странице `/category` (Жанры), где один и тот же жанр отображался несколько раз из-за наличия нескольких тегов с одним и тем же кодом (например, `sf_action` + `Боевая фантастика`).

## Что было изучено
- Корневая причина: `build_genre_tree()` не дедуплицировал записи по коду жанра; `build_sidebar_genre_tree()` — дедуплицировал вручную через `seen_codes`
- 124 кода жанров имели дублирующиеся теги (166 лишних строк)

## Какие файлы изменены
- `cps/aubooks_genres.py` — новый хелпер `_merge_genres_by_code()`, рефакторинг `build_genre_tree()` и `build_sidebar_genre_tree()`
- `cps/themes/aubooks/templates/list.html` — `genre.tag_id` → `genre.tag_ids|join('+')`
- `tests/test_aubooks_genres.py` — 7 новых тестов (84 → 91)

## Что именно изменено
1. Добавлен `_merge_genres_by_code(grouped)` — объединяет записи с одним `code` в списке `tag_ids`, суммирует `count`
2. `build_genre_tree()` теперь вызывает `_merge_genres_by_code()` и устанавливает `tag_ids` для каждого тега
3. `build_sidebar_genre_tree()` рефакторинг: вместо ручной дедупликации через `seen_codes` использует тот же `_merge_genres_by_code()`
4. Шаблон `list.html`: URL использует `tag_ids|join('+')` вместо `tag_id` для корректного отображения объединённых тегов

## Результаты
- До: 1316 строк на странице Жанры
- После: 1150 строк (удалено 166 дублирующих строк)
- Пример: `sf_action` (5 тегов: sf_action, Боевая фантастика, fantasy_action, fantasy_fight, Боевое фэнтези) → 1 строка с `tag_ids=[217, 228, 2469, 2522, 2858]`
- 91 тест проходит (было 84)

## Тесты
- `test_sf_action_five_tags_merge_to_one` — 5 тегов → 1 запись
- `test_single_tag_genre_unchanged` — одиночный тег без изменений
- `test_count_is_sum_not_unique` — count = сумма тегов
- `test_no_duplicate_labels_in_tree` — нет дублей кодов
- `test_unknown_tags_still_appear` — неизвестные теги на месте
- `test_sidebar_tree_still_works` — боковая панель без регрессий
- `test_genre_tree_has_tag_ids_for_template` — tag_ids у всех записей

## Ограничения
- `count` для объединённых жанров — приближённый (сумма тегов); книга с двумя тегами одного кода будет посчитана дважды
- Браузерная верификация недоступна (сервис на 8084 возвращает 404 для `/category`)

## Commit
- Hash: `3c017b24`
- Branch: aubooks
