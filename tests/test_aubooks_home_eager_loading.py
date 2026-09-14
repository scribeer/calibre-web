import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cps import db


class TestAubooksHomeEagerLoading(unittest.TestCase):
    @patch("cps.db.current_user", SimpleNamespace(show_detail_random=lambda: False))
    def test_card_relationships_are_selectin_loaded(self):
        query = MagicMock()
        query.options.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.count.return_value = 0
        query.all.return_value = []

        calibre_db = MagicMock()
        calibre_db.config = SimpleNamespace(config_books_per_page=60)
        calibre_db.session.query.return_value = query
        calibre_db.common_filters.return_value = True
        calibre_db.order_authors.return_value = []

        db.CalibreDB.fill_indexpage_with_archived_books(
            calibre_db, 1, db.Books, 60, True, [], False, False, 0,
            load_card_relations=True,
        )

        paths = {str(option.path) for option in query.options.call_args.args}
        self.assertEqual(paths, {
            "ORM Path[Mapper[Books(books)] -> Books.authors -> Mapper[Authors(authors)]]",
            "ORM Path[Mapper[Books(books)] -> Books.series -> Mapper[Series(series)]]",
            "ORM Path[Mapper[Books(books)] -> Books.ratings -> Mapper[Ratings(ratings)]]",
            "ORM Path[Mapper[Books(books)] -> Books.data -> Mapper[Data(data)]]",
        })

    def test_text_catalog_enables_card_eager_loading(self):
        source = (Path(__file__).parent.parent / "cps" / "web.py").read_text(encoding="utf-8")
        self.assertIn("load_card_relations=text_catalog", source)


if __name__ == "__main__":
    unittest.main()
