#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migrate fallback 'book' slug routes to proper Armenian transliteration.

DEV ONLY - does not touch production.
Preserves old slugs as aliases (301 redirects).
"""

import importlib.util
import sqlite3
import sys

spec = importlib.util.spec_from_file_location("seo_urls", "cps/seo_urls.py")
seo_urls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seo_urls)
book_slug_parts = seo_urls.book_slug_parts


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


def migrate():
    APP_DB = "/home/feninf/calibre-web-dev-data/app.db"
    LIBRARY_DB = "/home/feninf/calibre-web-dev-data/library/metadata.db"

    app_conn = sqlite3.connect(APP_DB)
    app_cur = app_conn.cursor()

    lib_conn = sqlite3.connect(LIBRARY_DB)
    lib_cur = lib_conn.cursor()

    # Find all books with slug "book" in mapping
    app_cur.execute(
        "SELECT book_id, author_slug, book_slug FROM aubooks_seo_book_route "
        "WHERE book_slug = 'book'"
    )
    fallback_routes = app_cur.fetchall()
    print(f"Found {len(fallback_routes)} routes with slug 'book'")

    migrated = 0
    skipped = 0

    for book_id, old_author_slug, old_book_slug in fallback_routes:
        lib_cur.execute(
            """
            SELECT b.title, b.author_sort,
                   GROUP_CONCAT(a.name, ' & ') as author_names, l.lang_code
            FROM books b
            LEFT JOIN books_authors_link bal ON bal.book = b.id
            LEFT JOIN authors a ON a.id = bal.author
            LEFT JOIN books_languages_link bll ON bll.book = b.id
            LEFT JOIN languages l ON l.id = bll.lang_code
            WHERE b.id = ?
            GROUP BY b.id
            """,
            (book_id,),
        )
        row = lib_cur.fetchone()
        if not row:
            print(f"  ID {book_id}: not found in library, skipping")
            skipped += 1
            continue

        title, author_sort, author_names, lang_code = row
        title = title or ""

        if author_sort:
            primary = author_sort.split("&")[0].strip()
        elif author_names:
            primary = author_names.split("&")[0].strip()
        else:
            primary = "Unknown author"

        lang = detect_language(lang_code, title)
        new_author_slug, new_book_slug = book_slug_parts(primary, title, lang)

        # Skip if slug didn't actually change
        if new_book_slug == old_book_slug:
            print(f"  ID {book_id}: slug unchanged ({old_book_slug}), skipping")
            skipped += 1
            continue

        print(f"  ID {book_id}: /{old_author_slug}/{old_book_slug} -> /{new_author_slug}/{new_book_slug}")

        # Check if new slug pair already exists
        app_cur.execute(
            "SELECT book_id FROM aubooks_seo_book_route WHERE author_slug = ? AND book_slug = ?",
            (new_author_slug, new_book_slug),
        )
        existing = app_cur.fetchone()
        if existing:
            print(f"    WARNING: new slug already taken by book_id={existing[0]}, skipping")
            skipped += 1
            continue

        # Mark old route as non-canonical (alias)
        app_cur.execute(
            "UPDATE aubooks_seo_book_route SET is_canonical = 0 "
            "WHERE book_id = ? AND is_canonical = 1",
            (book_id,),
        )

        # Insert new canonical route
        app_cur.execute(
            "INSERT INTO aubooks_seo_book_route "
            "(library_uuid, book_id, author_slug, book_slug, is_canonical) "
            "SELECT library_uuid, ?, ?, ?, 1 "
            "FROM aubooks_seo_book_route WHERE book_id = ? LIMIT 1",
            (book_id, new_author_slug, new_book_slug, book_id),
        )

        migrated += 1

    app_conn.commit()
    app_conn.close()
    lib_conn.close()

    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped")


if __name__ == "__main__":
    migrate()
