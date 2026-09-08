# 2026-09-06 — Genre Normalization Wave 2

## Цель
Уменьшить `Другие жанры` за счёт 30 новых aliases (24 high-confidence + 6 editorial).

## Что было сделано

### `cps/aubooks_genres.py`
Добавлено 30 aliases в `EXTRA_ALIASES` (волна 2):

**High-confidence (24 aliases):**
- Мистическое фэнтези → sf_mystic
- Социальная фантастика → sf_social
- Юмористическая фантастика → sf_humor
- love_fantasy → love_sf
- fantasy_fight → sf_action
- Боевое фэнтези → sf_action
- Биографии и Мемуары → nonf_biography
- psy_theraphy → sci_psychology
- foreign_love → love
- foreign_detective → det_classic
- Детская литература → children
- Советская проза → prose_su_classics
- visual_arts → design
- foreign_psychology → sci_psychology
- Любовные истории → love
- Детская фантастика → child_sf
- Сказки → child_tale
- Детская проза → child_prose
- Попаданец в фэнтези → popadancy
- humor_fantasy → sf_humor
- Биология → sci_biology
- fantasy → sf_etc
- Путешествия и приключения → adv_geo
- Мистический триллер → thriller

**Editorial decisions (6 aliases):**
- Современная проза → prose_contemporary
- психология → sci_psychology
- Военная проза → prose_military
- Биография → nonf_biography
- Наука → sci_popular
- Научно-популярное → sci_popular

### `tests/test_aubooks_genres.py`
Добавлены 10 regression tests для wave 2 aliases + исправлен 1 существующий тест:
- test_unknown_russian_tag_keeps_readable_label: заменён с "Современная проза" на "Легкая эротика"
- test_sovremennaya_proza_alias
- test_psihologiya_alias
- test_voennaya_proza_alias
- test_biografiya_alias
- test_nauka_alias
- test_nauchno_populyarnoe_alias
- test_misticheskoe_fentezi_alias
- test_foreign_detective_alias
- test_detskaya_literatura_alias
- test_fantasy_alias

Все 51 tests + 61 subtests pass.

## Результаты

### Fallback
| | Tags | Books |
|---|---|---|
| Before | 940 | 25,629 |
| After | 910 | 12,350 |
| Delta | -30 | -13,279 |

51.8% books removed from fallback.

### Browser verification
- Современная проза → Проза ✓
- Военная проза → Проза ✓
- Биография → Документальная литература ✓
- психология → Наука и образование ✓
- Легкая эротика → Другие жанры (оставлена в fallback) ✓

### Новый top-30 unmapped
| # | Tag | Books |
|---|---|---|
| 1 | Легкая эротика | 674 |
| 2 | Любовные рассказы | 359 |
| 3 | Детская психология | 269 |
| 4 | Популярно о бизнесе | 249 |
| 5 | Бизнес | 228 |
| 6 | Личностный рост | 201 |
| 7 | Эротика и любовь | 187 |
| 8 | psy_generic | 184 |
| 9 | magician_book | 179 |
| 10 | novel | 165 |
| 11 | Любовь и эротика | 152 |
| 12 | Психотерапия и консультирование | 141 |
| 13 | Экономика | 133 |
| 14 | О бизнесе популярно | 118 |
| 15 | Современная зарубежная литература | 111 |
| 16 | Приключения с детьми | 98 |
| 17 | Обучение детей | 96 |
| 18 | Современная русская литература | 96 |
| 19 | Любовно-историческая проза | 95 |
| 20 | Роман | 91 |
| 21 | Русское фэнтези | 91 |
| 22 | сучасна проза | 91 |
| 23 | Сетевая литература | 89 |
| 24 | foreign_publicism | 88 |
| 25 | Нечто | 87 |
| 26 | management | 84 |
| 27 | Детский детектив | 84 |
| 28 | psy_sex_and_family | 81 |
| 29 | urban_fantasy | 81 |
| 30 | ya | 81 |

## Пропущенные/отложенные
- Легкая эротика (674 books) — оставлена в fallback, требует editorial decision

## Commit
Local only, push не выполнялся.
