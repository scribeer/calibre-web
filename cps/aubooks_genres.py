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
CATEGORIES = tuple(category for category, __, ___ in _CATEGORY_RANGES)
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
MAPPED_TAG_NAMES = tuple(GENRES) + tuple(_LABEL_GENRES)


def _public_unknown_label(name):
    name = (name or "").strip()
    if any(character.isalpha() and ord(character) > 127 for character in name):
        return name
    return "Неизвестный жанр ({})".format(name or "без кода")


def genre_for_tag(tag):
    """Return an AU presentation dict while preserving the original tag ID."""
    name = (tag.name or "").strip()
    genre = GENRES.get(name) or _LABEL_GENRES.get(name)
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
                        "category_tag_ids": category_tag_ids})
    result.sort(key=lambda item: category_order.get(item["category"], len(category_order)))
    return result


def build_genre_tree(entries):
    """Build a hierarchy from the existing aggregate tag/count query results."""
    grouped = OrderedDict((category, []) for category in CATEGORIES)
    grouped[UNKNOWN_CATEGORY] = []
    for tag, count in entries:
        genre = genre_for_tag(tag)
        genre["count"] = count
        grouped[genre["category"]].append(genre)

    tree = []
    for category, genres in grouped.items():
        if not genres:
            continue
        genres.sort(key=lambda item: item["label"].casefold())
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
    seen_codes = set()
    for tag in tags:
        genre = genre_for_tag(tag)
        if not genre["mapped"]:
            continue
        code = genre["code"]
        if code in seen_codes:
            for existing_genre in grouped[genre["category"]]:
                if existing_genre["code"] == code:
                    existing_genre["tag_ids"].append(genre["tag_id"])
                    break
            continue
        seen_codes.add(code)
        genre["tag_ids"] = [genre["tag_id"]]
        grouped[genre["category"]].append(genre)

    tree = []
    for category, genres in grouped.items():
        genres.sort(key=lambda item: item["label"].casefold())
        category_tag_ids = []
        seen_codes = set()
        for genre in genres:
            code = genre["code"]
            if code not in seen_codes:
                seen_codes.add(code)
                category_tag_ids.extend(genre["tag_ids"])
        tree.append({"category": category, "genres": genres,
                      "category_tag_ids": category_tag_ids})
    return tree
