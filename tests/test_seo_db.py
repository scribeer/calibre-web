import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cps import seo_db


def book(book_id, author, title):
    author_object = SimpleNamespace(id=book_id, name=author, sort=author)
    return SimpleNamespace(
        id=book_id,
        title=title,
        author_sort=author,
        authors=[author_object],
        languages=[SimpleNamespace(lang_code="rus")],
    )


class SeoDatabaseTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        self.session = sessionmaker(bind=engine)()
        seo_db.init_db(self.session)
        self.library_uuid = "test-library"

    def tearDown(self):
        self.session.close()
        seo_db.clear_route_cache()

    def test_collision_suffix_and_round_trip(self):
        first = seo_db.ensure_canonical(
            self.library_uuid, book(1, "Иван Иванов", "Книга"), self.session
        )
        second = seo_db.ensure_canonical(
            self.library_uuid, book(2, "Иван Иванов", "Книга"), self.session
        )
        self.assertEqual((first.author_slug, first.book_slug), ("ivan-ivanov", "kniga"))
        self.assertEqual((second.author_slug, second.book_slug), ("ivan-ivanov", "kniga-2"))
        resolved = seo_db.resolve_route(
            self.library_uuid, second.author_slug, second.book_slug, self.session
        )
        self.assertEqual(resolved.book_id, 2)

    def test_mapping_is_persistent_after_metadata_change(self):
        original = book(1, "Михаил Булгаков", "Мастер и Маргарита")
        route = seo_db.ensure_canonical(self.library_uuid, original, self.session)
        changed = book(1, "Михаил Булгаков", "Исправленное название")
        same_route = seo_db.ensure_canonical(self.library_uuid, changed, self.session)
        self.assertEqual(route.book_slug, same_route.book_slug)

    def test_replacement_keeps_old_route_as_alias(self):
        original = book(1, "Михаил Булгаков", "Старое название")
        old_route = seo_db.ensure_canonical(self.library_uuid, original, self.session)
        changed = book(1, "Михаил Булгаков", "Новое название")
        new_route = seo_db.replace_canonical(self.library_uuid, changed, self.session)
        alias = seo_db.resolve_route(
            self.library_uuid, old_route.author_slug, old_route.book_slug, self.session
        )
        self.assertFalse(alias.is_canonical)
        self.assertEqual(new_route.book_slug, "novoe-nazvanie")

    def test_replacement_can_reuse_an_existing_alias(self):
        original = book(1, "Михаил Булгаков", "Первое название")
        first_route = seo_db.ensure_canonical(self.library_uuid, original, self.session)
        second_route = seo_db.replace_canonical(
            self.library_uuid, book(1, "Михаил Булгаков", "Второе название"), self.session
        )
        restored = seo_db.replace_canonical(self.library_uuid, original, self.session)
        self.assertEqual(restored.id, first_route.id)
        self.assertFalse(second_route.is_canonical)

    def test_migration_is_idempotent(self):
        seo_db.init_db(self.session)
        seo_db.init_db(self.session)


if __name__ == "__main__":
    unittest.main()
