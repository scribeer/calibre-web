# -*- coding: utf-8 -*-

"""AU-Books presentation mapping for Flibusta genre tags."""

from collections import OrderedDict
from pathlib import Path


GENRE_SOURCE = Path(__file__).with_name("data") / "flibusta_genres.txt"
UNKNOWN_CATEGORY = "Другие жанры"

# The source file has no section markers, but its entries are ordered in
# contiguous Flibusta topic blocks. Boundaries keep that source order explicit.
_CATEGORY_RANGES = (
    ("Деловая литература", "economics_ref", "economics"),
    ("Детективы и триллеры", "det_artifact", "det_espionage"),
    ("Детская литература", "children", "child_verse"),
    ("Документальная литература", "nonf_biography_celebrities", "nonf_publicism"),
    ("Дом и семья", "auto_regulations", "home_crafts"),
    ("Драматургия", "drama_antique", "tragedy"),
    ("Искусство", "painting", "theatre"),
    ("Компьютеры и интернет", "computers", "tbg_computers"),
    ("Любовные романы", "love_history", "love_erotica"),
    ("Наука и образование", "sci_medicine_alternative", "sci_linguistic"),
    ("Поэзия", "palindromes", "humor_verse"),
    ("Приключения", "adv_story", "tale_chivalry"),
    ("Проза", "aphorisms", "epistolary_fiction"),
    ("Прочее", "periodic", "fanfiction"),
    ("Религия и духовность", "astrology", "religion_paganism"),
    ("Справочная литература", "geo_guides", "ref_encyc"),
    ("Старинная литература", "antique", "antique_european"),
    ("Техника и учебные пособия", "auto_business", "tbg_school"),
    ("Фантастика", "asian_fantasy", "sf_humor"),
    ("Фольклор", "epic", "limerick"),
    ("Юмор", "humor_anecdote", "humor_prose"),
)


def _load_genres():
    entries = []
    root_label = None
    for line_number, raw_line in enumerate(GENRE_SOURCE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        key, separator, label = line.partition("=")
        if not separator or not label:
            raise ValueError("Invalid Flibusta genre at line {}".format(line_number))
        if key == "g":
            root_label = label
            continue
        if not key.startswith("g/") or not key[2:]:
            raise ValueError("Invalid Flibusta genre code at line {}".format(line_number))
        entries.append((key[2:], label))

    codes = [code for code, __ in entries]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate Flibusta genre codes")
    if root_label != "Жанры":
        raise ValueError("Missing Flibusta genre root")

    mapping = OrderedDict()
    offset = 0
    for category, first_code, last_code in _CATEGORY_RANGES:
        if offset >= len(entries) or entries[offset][0] != first_code:
            raise ValueError("Unexpected start of Flibusta category {}".format(category))
        while offset < len(entries):
            code, label = entries[offset]
            mapping[code] = {
                "code": code,
                "label": label,
                "category": category,
                "mapped": True,
            }
            offset += 1
            if code == last_code:
                break
        else:
            raise ValueError("Missing end of Flibusta category {}".format(category))
    if offset != len(entries):
        raise ValueError("Uncategorized Flibusta genre codes")
    return mapping


GENRES = _load_genres()

# ---------------------------------------------------------------------------
# Category presentation remap
# The raw _CATEGORY_RANGES must stay contiguous for file parsing, but we
# rename categories for the user-facing presentation.
# ---------------------------------------------------------------------------

_CATEGORY_REMAP = {
    "Любовные романы": "Романтика",
    "Наука и образование": "Наука и образование",  # placeholder, rebuilt below
    "Дом и семья": "Дом и семья",                   # placeholder, rebuilt below
}

# Codes that move from their original category to "Психология и здоровье".
_PSYCHOLOGY_HEALTH_CODES = {
    "home_health",        # Здоровье (was Дом и семья)
    "sci_psychology_popular",  # Популярная психология (was Дом и семья)
    "sci_psychology",     # Психология и психотерапия (was Наука и образование)
    "sci_medicine",       # Медицина (was Наука и образование)
    "sci_medicine_alternative",  # Альтернативная медицина (was Наука и образование)
    "religion_self",      # Самосовершенствование (was Религия и духовность)
    "family",             # Семейные отношения (was Дом и семья)
    "home_sex",           # Семейные отношения, секс (was Дом и семья)
}

_NEW_CATEGORY = "Психология и здоровье"

for _genre in GENRES.values():
    _old = _genre["category"]
    if _genre["code"] in _PSYCHOLOGY_HEALTH_CODES:
        _genre["category"] = _NEW_CATEGORY
    elif _old in _CATEGORY_REMAP:
        _genre["category"] = _CATEGORY_REMAP[_old]

# Rebuild CATEGORIES from the actual categories present in GENRES, preserving
# the original _CATEGORY_RANGES order and appending new categories at the end.
_original_order = [cat for cat, __, ___ in _CATEGORY_RANGES]
_seen = set()
_categories = []
for _cat in _original_order:
    # Use remapped name if it changed
    _mapped = _CATEGORY_REMAP.get(_cat, _cat)
    if _mapped not in _seen and any(g["category"] == _mapped for g in GENRES.values()):
        _categories.append(_mapped)
        _seen.add(_mapped)
# Append any new categories not in original order
for _cat in sorted(set(g["category"] for g in GENRES.values()) - _seen):
    _categories.append(_cat)
CATEGORIES = tuple(_categories)
_LABEL_GENRES = {}
_DUPLICATE_LABELS = set()
for _genre in GENRES.values():
    _label = _genre["label"]
    if _label in _LABEL_GENRES:
        _DUPLICATE_LABELS.add(_label)
    else:
        _LABEL_GENRES[_label] = _genre
for _label in _DUPLICATE_LABELS:
    del _LABEL_GENRES[_label]

# ---------------------------------------------------------------------------
# Case-insensitive label lookup
# ---------------------------------------------------------------------------

_LABEL_GENRES_NORMALIZED = {}
for _label, _genre in _LABEL_GENRES.items():
    _norm = _label.strip().casefold()
    if _norm not in _LABEL_GENRES_NORMALIZED:
        _LABEL_GENRES_NORMALIZED[_norm] = _genre

# ---------------------------------------------------------------------------
# Explicit aliases: raw tag name → GENRES entry
# Only unambiguous mappings where the alias clearly refers to an existing
# genre.  Entries that could not be resolved to a single GENRES entry are
# intentionally omitted and listed in the docs report.
# ---------------------------------------------------------------------------

EXTRA_ALIASES = {
    # Wave 1 — original aliases
    "детектив": "detective",
    "Любовный роман": "love",
    "Боевая фантастика": "sf_action",
    "Героическое фэнтези": "sf_heroic",
    "Любовное фэнтези": "love_sf",
    "LitRPG": "sf_litrpg",
    "Эзотерика": "religion_esoterics",
    "публицистика": "nonf_publicism",
    "проза": "prose",
    "foreign_fantasy": "foreign_sf",
    "city_fantasy": "sf_fantasy_city",
    "fantasy_action": "sf_action",
    "russian_contemporary": "prose_contemporary",
    "foreign_contemporary": "foreign_prose",
    "psy_personal": "sci_psychology_popular",
    "popadanec": "popadancy",
    # Wave 2 — high-confidence obvious wins (24 tags, 5170 books)
    "Мистическое фэнтези": "sf_mystic",
    "Социальная фантастика": "sf_social",
    "Юмористическая фантастика": "sf_humor",
    "love_fantasy": "love_sf",
    "fantasy_fight": "sf_action",
    "Боевое фэнтези": "sf_action",
    "Биографии и Мемуары": "nonf_biography",
    "psy_theraphy": "sci_psychology",
    "foreign_love": "love",
    "foreign_detective": "det_classic",
    "Детская литература": "children",
    "Советская проза": "prose_su_classics",
    "visual_arts": "design",
    "foreign_psychology": "sci_psychology",
    "Любовные истории": "love",
    "Детская фантастика": "child_sf",
    "Сказки": "child_tale",
    "Детская проза": "child_prose",
    "Попаданец в фэнтези": "popadancy",
    "humor_fantasy": "sf_humor",
    "Биология": "sci_biology",
    "fantasy": "sf_etc",
    "Путешествия и приключения": "adv_geo",
    "Мистический триллер": "thriller",
    # Wave 2 — editorial decisions (6 tags, 8783 books)
    "Современная проза": "prose_contemporary",
    "психология": "sci_psychology",
    "Военная проза": "prose_military",
    "Биография": "nonf_biography",
    "Наука": "sci_popular",
    "Научно-популярное": "sci_popular",
    # Wave 3 — category restructure aliases
    "Легкая эротика": "love_erotica",
    "Детская психология": "sci_psychology",
    "Медицина": "sci_medicine",
    "Здоровье": "home_health",
    # Wave 4 — psychology/health cleanup aliases
    "Психотерапия и консультирование": "sci_psychology",
    "Общая психология": "sci_psychology",
    "Зарубежная психология": "sci_psychology",
    "Социальная психология": "sci_psychology",
    "Психология и здоровье": "sci_psychology",
    "Классики психологии": "sci_psychology",
    "Возрастная психология": "sci_psychology",
    "Секс и семейная психология": "sci_psychology",
    "Бизнес и психология": "sci_psychology_popular",
    "Психология бизнеса": "sci_psychology_popular",
    "Практическая психология": "sci_psychology_popular",
    "Домашняя психология": "sci_psychology_popular",
    "Медицинская литература": "sci_medicine",
    "Здоровье и медицина": "sci_medicine",
    "Здоровье и личностный рост": "home_health",
    "Здоровье и кулинария": "home_health",
    "Здоровье и спорт": "home_health",
}

_ALIAS_GENRES = {}
for _alias, _code in EXTRA_ALIASES.items():
    if _code in GENRES:
        _ALIAS_GENRES[_alias] = GENRES[_code]

MAPPED_TAG_NAMES = tuple(GENRES) + tuple(_LABEL_GENRES) + tuple(_LABEL_GENRES_NORMALIZED) + tuple(_ALIAS_GENRES)


# ---------------------------------------------------------------------------
# Category slug helpers for /category/<slug> parent pages
# ---------------------------------------------------------------------------

_SLUG_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def _slugify(label):
    """Transliterate a Russian category label to a stable ASCII slug."""
    parts = []
    for ch in label.lower():
        if ch.isalnum():
            parts.append(_SLUG_MAP.get(ch, ch))
        elif parts and parts[-1] != '-':
            parts.append('-')
    return ''.join(parts).strip('-')


CATEGORY_SLUGS = {_slugify(cat): cat for cat in CATEGORIES}


def category_by_slug(slug):
    """Return category label for a slug, or None."""
    return CATEGORY_SLUGS.get(slug)


def build_category_slug_map(sidebar_tree):
    """Build slug→{label, tag_ids} mapping from the sidebar genre tree."""
    slug_map = {}
    for group in sidebar_tree:
        slug = _slugify(group["category"])
        slug_map[slug] = {
            "label": group["category"],
            "tag_ids": list(group.get("category_tag_ids", [])),
        }
    return slug_map


def _public_unknown_label(name):
    name = (name or "").strip()
    if any(character.isalpha() and ord(character) > 127 for character in name):
        return name
    return "Неизвестный жанр ({})".format(name or "без кода")


def genre_for_tag(tag):
    """Return an AU presentation dict while preserving the original tag ID."""
    name = (tag.name or "").strip()
    # 1. Exact match by Flibusta code
    genre = GENRES.get(name)
    # 2. Exact match by unique Russian label
    if not genre:
        genre = _LABEL_GENRES.get(name)
    # 3. Case-insensitive match by Russian label
    if not genre:
        norm = name.casefold()
        genre = _LABEL_GENRES_NORMALIZED.get(norm)
    # 4. Explicit alias lookup
    if not genre:
        genre = _ALIAS_GENRES.get(name)
    if genre:
        result = dict(genre)
    else:
        result = {
            "code": name,
            "label": _public_unknown_label(name),
            "category": UNKNOWN_CATEGORY,
            "mapped": False,
        }
    result["tag_id"] = tag.id
    return result


def group_tags(tags):
    """Group one book's tags by category without duplicating category labels.

    Each group gets a ``category_tag_ids`` list containing every tag ID that
    belongs to the category (deduplicated by genre code so that Flibusta
    code tags and their Russian label equivalents are merged).
    """
    grouped = OrderedDict()
    seen = set()
    for tag in tags:
        genre = genre_for_tag(tag)
        identity = (genre["tag_id"], genre["code"])
        if identity in seen:
            continue
        seen.add(identity)
        grouped.setdefault(genre["category"], []).append(genre)

    category_order = {name: index for index, name in enumerate(CATEGORIES)}
    category_order[UNKNOWN_CATEGORY] = len(category_order)
    result = []
    for category, genres in grouped.items():
        genres.sort(key=lambda item: item["label"].casefold())
        category_tag_ids = [genre["tag_id"] for genre in genres]
        result.append({"category": category, "genres": genres,
                        "category_tag_ids": category_tag_ids,
                        "category_slug": _slugify(category)})
    result.sort(key=lambda item: category_order.get(item["category"], len(category_order)))
    return result


def _merge_genres_by_code(grouped):
    """Deduplicate genre entries within each category by merging by genre code.

    For each category in *grouped*, entries sharing the same ``code`` are
    collapsed into a single entry.  ``tag_ids`` lists are merged, and
    ``count`` values (when present) are summed.  The resulting list is
    sorted by label.
    """
    for category in grouped:
        merged = OrderedDict()
        for genre in grouped[category]:
            code = genre["code"]
            if code in merged:
                existing = merged[code]
                existing["tag_ids"].extend(genre["tag_ids"])
                if "count" in genre:
                    existing["count"] = existing.get("count", 0) + genre["count"]
            else:
                merged[code] = genre
        grouped[category] = sorted(merged.values(),
                                   key=lambda item: item["label"].casefold())


def build_genre_tree(entries):
    """Build a hierarchy from the existing aggregate tag/count query results.

    Each raw Calibre tag is classified via ``genre_for_tag`` and grouped by
    category.  Tags that resolve to the same genre code are merged into a
    single entry with a ``tag_ids`` list and a ``count`` equal to the sum of
    individual tag counts (approximation — a book carrying two tags of the
    same code will be counted twice, which is acceptable for the directory
    listing where the precise count is less critical than correct merging).
    """
    grouped = OrderedDict((category, []) for category in CATEGORIES)
    grouped[UNKNOWN_CATEGORY] = []
    for tag, count in entries:
        genre = genre_for_tag(tag)
        genre["count"] = count
        genre["tag_ids"] = [genre["tag_id"]]
        grouped[genre["category"]].append(genre)

    _merge_genres_by_code(grouped)

    tree = []
    for category, genres in grouped.items():
        if not genres:
            continue
        tree.append({"category": category, "genres": genres})
    return tree


def build_sidebar_genre_tree(tags):
    """Build all mapped categories from real tags without counts or unknowns.

    Deduplicates by display label (genre code) so that Flibusta code tags
    (e.g. ``det_action``) and their Russian label equivalents (e.g.
    ``Боевик``) produce a single sidebar entry.  All tag IDs that resolve
    to the same label are merged into a ``tag_ids`` list so that the
    resulting compound URL shows books from *every* matching tag.
    """
    grouped = OrderedDict((category, []) for category in CATEGORIES)
    for tag in tags:
        genre = genre_for_tag(tag)
        if not genre["mapped"]:
            continue
        genre["tag_ids"] = [genre["tag_id"]]
        grouped[genre["category"]].append(genre)

    _merge_genres_by_code(grouped)

    tree = []
    for category, genres in grouped.items():
        category_tag_ids = []
        for genre in genres:
            category_tag_ids.extend(genre["tag_ids"])
        tree.append({"category": category, "genres": genres,
                      "category_tag_ids": category_tag_ids,
                      "category_slug": _slugify(category)})
    return tree
