#!/usr/bin/env python3

import argparse
import collections
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cps.seo_urls import book_slug_parts  # noqa: E402


SCHEMA = """
CREATE TABLE IF NOT EXISTS aubooks_seo_book_route (
    id INTEGER NOT NULL PRIMARY KEY,
    library_uuid VARCHAR(36) NOT NULL,
    book_id INTEGER NOT NULL,
    author_slug VARCHAR(96) NOT NULL,
    book_slug VARCHAR(112) NOT NULL,
    is_canonical BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_aubooks_seo_route UNIQUE (library_uuid, author_slug, book_slug)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_aubooks_seo_canonical_book
ON aubooks_seo_book_route (library_uuid, book_id) WHERE is_canonical = 1;
CREATE INDEX IF NOT EXISTS ix_aubooks_seo_book
ON aubooks_seo_book_route (library_uuid, book_id);
CREATE INDEX IF NOT EXISTS ix_aubooks_seo_sitemap
ON aubooks_seo_book_route (library_uuid, is_canonical, book_id);
"""


def _metadata_connection(path):
    uri = "file:{}?mode=ro".format(Path(path).resolve())
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _language_map(connection):
    return dict(connection.execute(
        "SELECT bal.book, CASE "
        "WHEN SUM(l.lang_code = 'ukr') > 0 THEN 'ukr' "
        "WHEN SUM(l.lang_code = 'rus') > 0 THEN 'rus' "
        "ELSE MIN(l.lang_code) END "
        "FROM books_languages_link bal JOIN languages l ON l.id = bal.lang_code GROUP BY bal.book"
    ))


def _books(connection):
    query = connection.execute(
        "SELECT b.id, b.title, b.author_sort, a.id, a.name, a.sort "
        "FROM books b "
        "JOIN books_authors_link bal ON bal.book = b.id "
        "JOIN authors a ON a.id = bal.author "
        "ORDER BY b.id, bal.id"
    )
    current_id = None
    row_data = None
    authors = []
    for book_id, title, author_sort, author_id, author_name, author_sort_name in query:
        if current_id is not None and book_id != current_id:
            yield row_data, authors
            authors = []
        current_id = book_id
        row_data = (book_id, title, author_sort or "")
        authors.append((author_id, author_name, author_sort_name or ""))
    if row_data is not None:
        yield row_data, authors


def _primary_author(authors, author_sort):
    by_sort = {sort_name: name for _, name, sort_name in authors}
    for sort_name in author_sort.split("&"):
        if sort_name.strip() in by_sort:
            return by_sort[sort_name.strip()]
    return min(authors, key=lambda author: author[0])[1]


def migrate(metadata_path, app_path):
    started = time.perf_counter()
    metadata = _metadata_connection(metadata_path)
    app = sqlite3.connect(str(Path(app_path).resolve()))
    app.executescript(SCHEMA)
    app.execute("BEGIN IMMEDIATE")

    library_uuid = metadata.execute("SELECT uuid FROM library_id LIMIT 1").fetchone()[0]
    languages = _language_map(metadata)
    existing_books = {
        row[0] for row in app.execute(
            "SELECT book_id FROM aubooks_seo_book_route "
            "WHERE library_uuid = ? AND is_canonical = 1", (library_uuid,)
        )
    }
    used = collections.defaultdict(set)
    for author_slug, book_slug in app.execute(
            "SELECT author_slug, book_slug FROM aubooks_seo_book_route WHERE library_uuid = ?", (library_uuid,)):
        used[author_slug].add(book_slug)

    pending = []
    base_counts = collections.Counter()
    created = 0
    for (book_id, title, author_sort), authors in _books(metadata):
        author_name = _primary_author(authors, author_sort)
        author_slug, base_book_slug = book_slug_parts(author_name, title, languages.get(book_id))
        base_counts[(author_slug, base_book_slug)] += 1
        if book_id in existing_books:
            continue

        suffix = 1
        book_slug = base_book_slug
        while book_slug in used[author_slug]:
            suffix += 1
            book_slug = "{}-{}".format(base_book_slug, suffix)
        used[author_slug].add(book_slug)
        pending.append((library_uuid, book_id, author_slug, book_slug, 1))
        created += 1
        if len(pending) >= 5000:
            app.executemany(
                "INSERT INTO aubooks_seo_book_route "
                "(library_uuid, book_id, author_slug, book_slug, is_canonical) VALUES (?, ?, ?, ?, ?)",
                pending,
            )
            pending = []

    if pending:
        app.executemany(
            "INSERT INTO aubooks_seo_book_route "
            "(library_uuid, book_id, author_slug, book_slug, is_canonical) VALUES (?, ?, ?, ?, ?)",
            pending,
        )
        app.commit()

    app.commit()
    total = app.execute(
        "SELECT COUNT(*) FROM aubooks_seo_book_route WHERE library_uuid = ? AND is_canonical = 1",
        (library_uuid,),
    ).fetchone()[0]
    integrity = app.execute("PRAGMA integrity_check").fetchone()[0]
    collision_groups = [count for count in base_counts.values() if count > 1]
    result = {
        "library_uuid": library_uuid,
        "canonical_routes": total,
        "created": created,
        "base_collision_groups": len(collision_groups),
        "books_in_collision_groups": sum(collision_groups),
        "max_collision_size": max(collision_groups or [1]),
        "app_db_integrity": integrity,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    metadata.close()
    app.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Create persistent AU-Books SEO routes in the Calibre-Web app DB")
    parser.add_argument("--metadata-db", required=True)
    parser.add_argument("--app-db", required=True)
    parser.add_argument("--offline", action="store_true", help="confirm that Calibre-Web is stopped")
    args = parser.parse_args()
    if not args.offline:
        parser.error("--offline is required; stop the DEV service before migration")
    print(json.dumps(migrate(args.metadata_db, args.app_db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
