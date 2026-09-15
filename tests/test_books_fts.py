"""Regression tests for the AU-Books FTS5 search consumer."""

import inspect
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from cps import db


def _subject(execute_side_effect):
    subject = MagicMock()
    subject._fts_available = None
    subject.session.execute.side_effect = execute_side_effect
    subject.common_filters.return_value = True
    subject.get_cc_columns.return_value = []
    query = MagicMock()
    query.filter.return_value = query
    query.options.return_value = query
    subject.generate_linked_query.return_value = query
    return subject, query


class BooksFtsConsumerTest(unittest.TestCase):
    def test_detects_versioned_fts_in_attached_calibre_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata = Path(temp_dir) / "metadata.db"
            library = sqlite3.connect(metadata)
            library.executescript(
                """
                CREATE VIRTUAL TABLE books_fts USING fts5(title);
                CREATE TABLE aubooks_fts_schema (
                    singleton INTEGER PRIMARY KEY,
                    schema_version INTEGER NOT NULL
                );
                INSERT INTO aubooks_fts_schema VALUES (1, 1);
                INSERT INTO books_fts(rowid, title) VALUES (7, 'Маракх');
                """
            )
            library.close()
            connection = sqlite3.connect(":memory:")
            connection.execute("ATTACH DATABASE ? AS calibre", (str(metadata),))
            detected = connection.execute(
                db.AUBOOKS_FTS_PROBE_SQL.replace(":schema_version", "?"),
                (db.AUBOOKS_FTS_SCHEMA_VERSION,),
            ).fetchone()
            matched = connection.execute(
                db.AUBOOKS_FTS_MATCH_PROBE_SQL.replace(":term", "?"),
                (db.normalize_fts_query("  МАРАКХ  "),),
            ).fetchone()
            connection.close()
            self.assertEqual(detected, (1,))
            self.assertEqual(matched, (1,))

    def test_valid_zero_result_is_authoritative(self):
        subject, query = _subject([MagicMock(fetchone=MagicMock(return_value=(1,))),
                                   MagicMock(fetchone=MagicMock(return_value=None))])
        result = db.CalibreDB.search_query(subject, "missing", SimpleNamespace(config_read_column=0))
        self.assertIs(result, query)
        self.assertFalse(subject.session.query.called)
        self.assertEqual(str(query.filter.call_args_list[-1].args[0]), "false")

    def test_missing_fts_uses_legacy_fallback(self):
        subject, query = _subject([MagicMock(fetchone=MagicMock(return_value=None))])
        result = db.CalibreDB.search_query(subject, "legacy", SimpleNamespace(config_read_column=0))
        self.assertIs(result, query)
        self.assertTrue(subject.session.query.called)

    def test_fts_query_error_uses_legacy_fallback(self):
        error = OperationalError("MATCH failed", {}, Exception("broken FTS"))
        subject, query = _subject([MagicMock(fetchone=MagicMock(return_value=(1,))), error])
        result = db.CalibreDB.search_query(subject, "legacy", SimpleNamespace(config_read_column=0))
        self.assertIs(result, query)
        self.assertTrue(subject.session.query.called)

    def test_positive_fts_filter_remains_in_sql(self):
        subject, query = _subject([MagicMock(fetchone=MagicMock(return_value=(1,))),
                                   MagicMock(fetchone=MagicMock(return_value=(1,)))])
        db.CalibreDB.search_query(subject, "Олег Куява", SimpleNamespace(config_read_column=0))
        condition = query.filter.call_args_list[-1].args[0]
        self.assertIn("calibre.books_fts", str(condition))
        self.assertIn("SELECT rowid", str(condition))
        self.assertEqual(condition.compile().params["fts_term"], '"олег куява"')
        source = inspect.getsource(db.CalibreDB.search_query)
        self.assertNotIn("fetchall()", source)

    def test_query_normalization(self):
        self.assertEqual(
            db.normalize_fts_query("  МАРАКХ.\t  Испытание  "),
            '"маракх. испытание"',
        )
        self.assertEqual(db.normalize_fts_query("A \"quote\""), '"a ""quote"""')

    def test_pagination_limits_the_sql_filtered_query(self):
        subject = MagicMock()
        query = MagicMock()
        subject.search_query.return_value = query
        query.options.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = list(range(61))
        subject.order_authors.side_effect = lambda result, **kwargs: result
        with patch("cps.db.ub.store_combo_ids"):
            entries, result_count, pagination = db.CalibreDB.get_search_results(
                subject,
                "popular",
                SimpleNamespace(),
                0,
                [[db.Books.sort], "abc"],
                60,
            )
        query.limit.assert_called_once_with(61)
        self.assertEqual(len(entries), 60)
        self.assertEqual(result_count, 61)
        self.assertTrue(pagination.has_next)

    def test_reconnect_resets_cached_availability(self):
        subject = db.CalibreDB()
        subject._fts_available = True
        config = SimpleNamespace(config_calibre_dir="/tmp/library")
        with patch.object(db.CalibreDB, "setup_db"), patch.object(db.CalibreDB, "update_config"):
            db.CalibreDB.reconnect_db(subject, config, "/tmp/app.db")
        self.assertIsNone(subject._fts_available)


if __name__ == "__main__":
    unittest.main()
