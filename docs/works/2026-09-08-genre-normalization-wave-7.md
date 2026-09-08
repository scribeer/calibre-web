# Genre Normalization Wave 7 (Final) — 2026-09-08

## Цель

Нормализация крупных unmapped genre tags (>=20 книг) на существующие codes. Финальная волна нормализации крупных тегов.

## Исходное состояние

- Unmapped tags: 737
- Fallback DISTINCT books: 2,832
- EXTRA_ALIASES: 219

## Добавленные aliases

### OBVIOUS_ALIAS (6 тегов)

| Tag | Code | Категория |
|-----|------|-----------|
| Зарубежная публицистика | `nonf_publicism` | Документальная литература |
| adv_western | `adv_indian` | Приключения |
| fantasy_heroic | `sf_heroic` | Фантастика |
| закордонна класика | `foreign_prose` | Проза |
| fantasy_epic | `sf_epic` | Фантастика |
| Личные финансы | `banking` | Деловая литература |

### Editorial decisions (5 тегов)

| Tag | Code | Категория | Комментарий |
|-----|------|-----------|-------------|
| Детские книги | `children` | Детская литература | Решение пользователя |
| Зарубежные любовные романы | `love` | Романтика | Решение пользователя |
| comp_soft | `computers` | Компьютеры и интернет | Не `comp_db` (software ≠ программирование) |
| foreign_adventure | `adventure` | Приключения | Не `adv_geo` (зарубежные ≠ путешествия) |
| Прочая образовательная литература | `sci_popular` | Наука и образование | Не `child_education`, не `foreign_prose` |

**Итого:** 11 aliases добавлены.

## Сознательно оставленные unmapped

### GARBAGE/ALREADY_DECIDED (не трогать)

| Tag | Книг | Статус |
|-----|------|--------|
| Нечто | 87 | ALREADY_DECIDED |
| спонсор | 63 | ALREADY_DECIDED |
| unrecognised | 56 | ALREADY_DECIDED |
| Экшн (action) | 51 | ALREADY_DECIDED |
| Другое | 43 | ALREADY_DECIDED |
| НЕОЗВУЧИВАЛ | 42 | ALREADY_DECIDED |
| Зарубежная образовательная литература | 39 | ALREADY_DECIDED |
| compilation | 26 | ALREADY_DECIDED |
| Дружба | 25 | ALREADY_DECIDED |
| Неокончено | 24 | ALREADY_DECIDED |
| stock | 20 | GARBAGE |

### NO_MATCH (нет существующих codes)

| Tag | Книг | Почему нет code |
|-----|------|----------------|
| vampire_book | 45 | Flibusta code, нет `sf_vampire` |
| cinema_theatre | 33 | Flibusta code, нет `art_cinema` |
| Учебные заведения | 23 | Тема, а не жанр |
| Копирайтинг | 22 | Профессиональная тема |
| Стёб | 20 | Тон/стиль, а не жанр |

## Метрики

| Метрика | Before | After |
|---------|--------|-------|
| EXTRA_ALIASES | 219 | 230 |
| Unmapped tags | 737 | 726 |
| Fallback DISTINCT books | 2,832 | 2,605 |
| Tags removed | — | 11 |
| Books removed | — | 227 |

## Tests

- Всего тестов: 135
- Wave 7 regression tests: 11
- Все тесты проходят

## Commit

- `7b921ff5` — feat: wave 7 (final) genre normalization — 11 aliases

## Вывод

Нормализация крупных unmapped тегов завершена. Все реальные genre-теги с >=20 книг обработаны. Оставшиеся unmapped теги — это мусорные/ editorial/ orphan теги без подходящих существующих codes.