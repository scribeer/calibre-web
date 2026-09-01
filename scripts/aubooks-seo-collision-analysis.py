#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze SEO URL collisions across all books in a Calibre-Web metadata.db.

Usage:
    python3 scripts/aubooks-seo-collision-analysis.py [--library PATH] [--app-db PATH]

Defaults:
    --library  /home/feninf/calibre-web-dev-data/library/metadata.db
    --app-db   /home/feninf/calibre-web-dev-data/app.db
"""

import argparse
import re
import sqlite3
import unicodedata
from collections import defaultdict

# ── Slug algorithm (identical to cps/seo_urls.py) ───────────────────────────

_RUSSIAN = {
    "\u0430": "a", "\u0431": "b", "\u0432": "v", "\u0433": "g", "\u0434": "d",
    "\u0435": "e", "\u0451": "yo", "\u0436": "zh", "\u0437": "z", "\u0438": "i",
    "\u0439": "y", "\u043a": "k", "\u043b": "l", "\u043c": "m", "\u043d": "n",
    "\u043e": "o", "\u043f": "p", "\u0440": "r", "\u0441": "s", "\u0442": "t",
    "\u0443": "u", "\u0444": "f", "\u0445": "h", "\u0446": "ts", "\u0447": "ch",
    "\u0448": "sh", "\u0449": "shch", "\u044a": "", "\u044b": "y", "\u044c": "",
    "\u044d": "e", "\u044e": "yu", "\u044f": "ya",
}

_UKRAINIAN = {
    "\u0430": "a", "\u0431": "b", "\u0432": "v", "\u0433": "h", "\u0491": "g",
    "\u0434": "d", "\u0435": "e", "\u0436": "zh", "\u0437": "z", "\u0438": "y",
    "\u0456": "i", "\u043a": "k", "\u043b": "l", "\u043c": "m", "\u043d": "n",
    "\u043e": "o", "\u043f": "p", "\u0440": "r", "\u0441": "s", "\u0442": "t",
    "\u0443": "u", "\u0444": "f", "\u0445": "kh", "\u0446": "ts", "\u0447": "ch",
    "\u0448": "sh", "\u0449": "shch", "\u044c": "", "'": "", "\u2019": "",
}

_UKRAINIAN_CONTEXT = {
    "\u0454": ("ye", "ie"), "\u0457": ("yi", "i"),
    "\u0439": ("y", "i"), "\u044e": ("yu", "iu"), "\u044f": ("ya", "ia"),
}

_SEPARATORS = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"-+")


def _is_ukrainian(language, value):
    language = (language or "").lower()
    return language in ("uk", "ukr", "ukrainian") or any(
        char in value.lower() for char in "\u0456\u0457\u0454\u0491"
    )


def _transliterate(value, language=None):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    ukrainian = _is_ukrainian(language, value)
    table = _UKRAINIAN if ukrainian else _RUSSIAN
    result = []
    at_word_start = True
    for char in value:
        if ukrainian and char in _UKRAINIAN_CONTEXT:
            start, middle = _UKRAINIAN_CONTEXT[char]
            result.append(start if at_word_start else middle)
            at_word_start = False
        elif char in table:
            replacement = table[char]
            result.append(replacement)
            if replacement:
                at_word_start = False
        elif char.isascii() and char.isalnum():
            result.append(char)
            at_word_start = False
        elif char.isalpha():
            ascii_char = unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode("ascii")
            result.append(ascii_char)
            at_word_start = not bool(ascii_char)
        else:
            result.append("-")
            at_word_start = True
    return "".join(result)


def slugify(value, language=None, max_length=96, fallback="item"):
    slug = _SEPARATORS.sub("-", _transliterate(value, language))
    slug = _DASHES.sub("-", slug).strip("-")
    if max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or fallback


def book_slug_parts(author, title, language=None):
    return (
        slugify(author, language=language, fallback="unknown-author"),
        slugify(title, language=language, fallback="book"),
    )


def detect_language(lang_code, title):
    if lang_code in ("ukr", "uk"):
        return "ukr"
    if lang_code in ("rus", "ru"):
        return "rus"
    if any(c in title for c in "\u0456\u0457\u0454\u0491"):
        return "ukr"
    if any(c in title for c in "\u0430\u0431\u0432\u0433\u0434\u0435\u0436\u0437\u0438\u0439\u043a\u043b\u043c\u043d\u043e\u043f\u0440\u0441\u0442\u0443\u0444\u0445\u0446\u0447\u0448\u0449\u044a\u044b\u044c\u044d\u044e\u044f\u0451"):
        return "rus"
    return None


def primary_author_from_row(author_sort, author_names):
    if author_sort:
        first = author_sort.split("&")[0].strip()
        if first:
            return first
    if author_names:
        return author_names.split("&")[0].strip()
    return None


def analyze(library_db, app_db):
    conn = sqlite3.connect(library_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT
            b.id as book_id, b.title, b.author_sort,
            GROUP_CONCAT(a.name, ' & ') as author_names,
            l.lang_code
        FROM books b
        LEFT JOIN books_authors_link bal ON bal.book = b.id
        LEFT JOIN authors a ON a.id = bal.author
        LEFT JOIN books_languages_link bll ON bll.book = b.id
        LEFT JOIN languages l ON l.id = bll.lang_code
        GROUP BY b.id
    """)
    rows = cur.fetchall()
    conn.close()

    total = len(rows)
    slug_map = defaultdict(list)
    book_data = {}

    for row in rows:
        book_id = row["book_id"]
        title = row["title"] or ""
        primary = primary_author_from_row(row["author_sort"], row["author_names"])
        if not primary:
            primary = "Unknown author"
        lang = detect_language(row["lang_code"], title)
        author_slug, book_slug = book_slug_parts(primary, title, lang)
        slug_map[(author_slug, book_slug)].append(book_id)
        book_data[book_id] = {
            "author": (row["author_names"] or "Unknown").split("&")[0].strip(),
            "title": title,
            "author_slug": author_slug,
            "book_slug": book_slug,
        }

    collisions = {k: v for k, v in slug_map.items() if len(v) > 1}
    sorted_collisions = sorted(collisions.items(), key=lambda x: -len(x[1]))

    print(f"Total books:                {total}")
    print(f"Unique slug pairs:          {len(slug_map)}")
    print(f"Collision groups:           {len(collisions)}")
    print(f"Books in collisions:        {sum(len(v) for v in collisions.values())}")
    print(f"Max collision group:        {max((len(v) for v in collisions.values()), default=0)}")
    print()

    if sorted_collisions:
        print("Top collision groups:")
        for (aslug, bslug), ids in sorted_collisions[:10]:
            print(f"  /{aslug}/{bslug} ({len(ids)} books)")
            for bid in ids[:3]:
                d = book_data[bid]
                print(f"    ID {bid}: {d['author'][:35]} — {d['title'][:45]}")
        print()

    return {
        "total": total,
        "unique_pairs": len(slug_map),
        "collision_groups": len(collisions),
        "books_in_collisions": sum(len(v) for v in collisions.values()),
        "max_collision": max((len(v) for v in collisions.values()), default=0),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEO URL collision analysis")
    parser.add_argument("--library", default="/home/feninf/calibre-web-dev-data/library/metadata.db")
    parser.add_argument("--app-db", default="/home/feninf/calibre-web-dev-data/app.db")
    args = parser.parse_args()
    analyze(args.library, args.app_db)
