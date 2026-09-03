# 2026-09-03 Calibre Genre Mapping Review

## Итоговая статистика

| Метрика | До | После |
|---------|-----|-------|
| medium tags | 296 | 302 |
| low tags | 551 | 550 |
| high assignments % | 91.8% | 90.5% |
| medium assignments % | 7.5% | 8.8% |
| low assignments % | 0.7% | 0.7% |

### По classification

| Classification | Tags | Assignments | % |
|---------------|------|-------------|---|
| genre_code | 512 | 141,659 | 68.2% |
| canonical_genre | 202 | 48,214 | 23.2% |
| thematic | 73 | 11,044 | 5.3% |
| genre | 40 | 4,448 | 2.1% |
| service | 11 | 1,190 | 0.6% |
| unknown | 426 | 863 | 0.4% |
| noise | 1 | 87 | 0.0% |
| compound | 6 | 59 | 0.0% |
| mixed | 45 | 48 | 0.0% |

## A. Top 100 medium/low tags

### Medium tags (sorted by book_count)

| # | raw_tag | books | classification | proposed parent | confidence | reason |
|---|---------|-------|----------------|-----------------|------------|--------|
| 1 | публицистика | 2034 | thematic | | medium | Literary form/journalism, not genre |
| 2 | история | 2031 | thematic | | medium | Subject matter, not genre |
| 3 | Эзотерика | 1401 | thematic | | medium | Subject matter |
| 4 | психология | 822 | thematic | | medium | Subject matter |
| 5 | Здоровье | 779 | thematic | | medium | Subject matter |
| 6 | Легкая эротика | 674 | genre | Любовные романы | medium | Sub-genre of romance |
| 7 | проза | 467 | thematic | | medium | Literary form, not genre |
| 8 | Любовные рассказы | 359 | genre | Любовные романы | medium | Romance sub-genre |
| 9 | Философия | 327 | thematic | | medium | Subject matter |
| 10 | Детская психология | 269 | thematic | | medium | Subject matter |
| 11 | Наука | 257 | thematic | | medium | Subject matter |
| 12 | Научно-популярное | 250 | genre | Наука и образование | medium | Non-fiction form |
| 13 | Популярно о бизнесе | 249 | thematic | | medium | Subject matter |
| 14 | Личностный рост | 201 | thematic | | medium | Subject matter |
| 15 | Эротика и любовь | 187 | genre | Любовные романы | medium | Romance sub-genre |
| 16 | magician_book | 179 | genre | Фантастика | medium | Fantasy sub-genre |
| 17 | Советская проза | 168 | genre | Проза | medium | Historical literary category |
| 18 | novel | 165 | genre | Проза | medium | Literary form |
| 19 | Любовь и эротика | 152 | genre | Любовные романы | medium | Romance sub-genre |
| 20 | Любовные истории | 145 | genre | Любовные романы | medium | Romance sub-genre |
| 21 | Детская фантастика | 144 | genre | Детская литература | medium | Children's genre |
| 22 | Культурология | 143 | thematic | | medium | Subject matter |
| 23 | Психотерапия и консультирование | 141 | thematic | | medium | Subject matter |
| 24 | Сказки | 137 | genre | Детская литература | medium | Genre |
| 25 | Детская проза | 130 | genre | Детская литература | medium | Genre |
| 26 | Биология | 125 | thematic | | medium | Subject matter |
| 27 | fantasy | 121 | genre | Фантастика | medium | Genre code |
| 28 | О бизнесе популярно | 118 | thematic | | medium | Subject matter |
| 29 | Современная зарубежная литература | 111 | genre | Проза | medium | Literary category |
| 30 | Путешествия и приключения | 103 | genre | Приключения | medium | Genre |

### Low tags (top 20)

| # | raw_tag | books | classification | proposed parent | confidence | reason |
|---|---------|-------|----------------|-----------------|------------|--------|
| 1 | Нечто | 87 | noise | | low | Meaningless tag |
| 2 | Дружба | 25 | thematic | | low | Theme, not genre |
| 3 | Управление | 17 | thematic | | low | Subject matter |
| 4 | География | 16 | thematic | | low | Subject matter |
| 5 | Рукоделие | 16 | thematic | | low | Subject matter |
| 6 | Филология | 16 | thematic | | low | Subject matter |
| 7 | реклама | 16 | thematic | | low | Subject matter |
| 8 | Социология | 15 | thematic | | low | Subject matter |
| 9 | Языкознание | 15 | thematic | | low | Subject matter |
| 10 | подбор персонала | 15 | thematic | | low | Subject matter |
| 11 | Кинематограф | 14 | thematic | | low | Subject matter |
| 12 | Путеводитель | 14 | thematic | | low | Subject matter |
| 13 | collection | 13 | service | Прочее | low | Service tag |
| 14 | PR | 13 | thematic | | low | Subject matter |
| 15 | Культура | 13 | thematic | | low | Subject matter |
| 16 | Детское | 12 | thematic | | low | Vague tag |
| 17 | Записки путешественника | 12 | thematic | | low | Subject matter |
| 18 | Спорт | 12 | thematic | | low | Subject matter |
| 19 | Трилер | 12 | genre | Детективы и триллеры | low | Genre (misspelling of Триллер) |
| 20 | action | 11 | genre | Фантастика | low | Genre code |

## B. Genre vs Thematic Boundary

### Теги, признанные literary genres (не subject themes)

Эти теги являются жанрами/формами литературы и должны показываться в genre sidebar:

- Легкая эротика, Любовные рассказы, Эротика и любовь, Любовь и эротика, Любовные истории
- Детская фантастика, Сказки, Детская проза, Приключения с детьми, Детский детектив
- Советская проза, Современная зарубежная литература, Современная русская литература
- Научно-популярное, Мистическая фантастика, Роман
- Путешествия и приключения, Приключения с животными

### Теги, признанные thematic (subject matter)

Эти теги являются предметными темами и НЕ должны показываться в genre sidebar:

- публицистика, история, психология, проза, Наука
- Популярно о бизнесе, Личностный рост, Детская психология
- Биология, Философия, Культурология
- Управление, География, Рукоделие, Филология
- Кинематограф, Путеводитель, Спорт, PR
- подбор персонала, реклама, Социология

### Правило

Если тег описывает **что** (предмет/тема) — это thematic.
Если тег описывает **как** (форма/стиль/жанр) — это genre.

## C. Typo Candidates (54 resolved)

32 typo variants исправлены с confidence=high:

| raw → canonical | books | similarity |
|----------------|-------|------------|
| Исторические прключения → Исторические приключения | 6 | 0.98 |
| Мистиоческая фантастика → Мистическая фантастика | 1 | 0.98 |
| Компьютерная литертура → Компьютерная литература | 3 | 0.98 |
| Исторческая фантастика → Историческая фантастика | 4 | 0.98 |
| Фантастически детектив → Фантастический детектив | 2 | 0.98 |
| Социальная фантатстика → Социальная фантастика | 1 | 0.98 |
| Мистическа фантастика → Мистическая фантастика | 2 | 0.98 |
| Социальна фантастика → Социальная фантастика | 3 | 0.98 |
| Иронический \детектив → Иронический детектив | 1 | 0.98 |
| Попоулярно о бизнесе → Популярно о бизнесе | 2 | 0.97 |
| Ирониеский детектив → Иронический детектив | 2 | 0.97 |
| Античная литертура → Античная литература | 1 | 0.97 |
| Сетевая литертура → Сетевая литература | 5 | 0.97 |
| Научно-поулярное → Научно-популярное | 1 | 0.97 |
| Любовное фэнтез → Любовное фэнтези | 1 | 0.97 |
| Детскийдетектив → Детский детектив | 1 | 0.97 |
| Круто детектив → Крутой детектив | 3 | 0.97 |
| Военна история → Военная история | 3 | 0.97 |
| Обчение детей → Обучение детей | 1 | 0.96 |
| Приключения с животынми → Приключения с животными | 1 | 0.96 |
| Иностринная фантастика → Иностранная фантастика | 1 | 0.95 |
| Домводство → Домоводство | 2 | 0.95 |
| Поліцейский детектив → Полицейский детектив | 2 | 0.95 |
| Д5тская литература → Детская литература | 1 | 0.94 |
| Шпиноский детектив → Шпионский детектив | 2 | 0.94 |
| Городское фэнтззи → Городское фэнтези | 1 | 0.94 |
| Эписеское фэнтези → Эпическое фэнтези | 5 | 0.94 |
| Эпическое фентези → Эпическое фэнтези | 1 | 0.94 |
| Иновтранная проза → Иностранная проза | 1 | 0.94 |
| Психология\ → Психология | 2 | 0.95 |
| Социальнаф фантастика → Социальная фантастика | 3 | 0.95 |
| Исторический любовны роман → Исторический любовный роман | 1 | 0.98 |

Остальные 22 typo-кандидата признаны неочевидными и оставлены как есть.

## D. User Decisions

Файл: `docs/works/2026-09-03-calibre-genre-user-decisions.tsv`

Только реально спорные случаи, где необходимо решение пользователя.

## E. Tags для будущего удаления (service/noise)

Эти теги можно будет безопасно удалить когда-нибудь:

- Нечто (noise, 87 books)
- collection (service, 13 books)
- foreign_desc (service, 8 books)
- screenplay/screenplays (service)
- compilation (service)

## F. Case-insensitive collisions

0 case-insensitive collisions в mapping.

## G. metadata.db

**Не изменялась.** MD5: `9f52badfbb07ffe6f739e0f81e212eaa`

## H. Commits

Mapping обновлён в `/home/feninf/aubooks/files/genre_mapping.tsv`.
