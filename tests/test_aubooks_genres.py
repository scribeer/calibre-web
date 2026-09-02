import unittest
from types import SimpleNamespace

from cps.aubooks_genres import (
    CATEGORIES,
    GENRES,
    UNKNOWN_CATEGORY,
    build_genre_tree,
    build_sidebar_genre_tree,
    genre_for_tag,
    group_tags,
)


def tag(tag_id, name):
    return SimpleNamespace(id=tag_id, name=name)


class AubooksGenresTest(unittest.TestCase):
    def test_source_size_and_categories(self):
        self.assertEqual(len(GENRES), 272)
        self.assertEqual(len(CATEGORIES), 21)

    def test_flbusta_labels_and_categories(self):
        expected = {
            "economics_ref": ("Деловая литература", "Деловая литература"),
            "det_classic": ("Классический детектив", "Детективы и триллеры"),
            "child_sf_space": ("Детская фантастика: космические приключения, пришельцы", "Детская литература"),
            "nonf_biography": ("Биографии и мемуары: прочее", "Документальная литература"),
            "love_history": ("Исторические любовные романы", "Любовные романы"),
            "sci_math": ("Математика", "Наука и образование"),
            "adv_maritime": ("Морские приключения", "Приключения"),
            "prose_magic": ("Магический реализм", "Проза"),
            "sf_action": ("Боевая фантастика и фэнтези", "Фантастика"),
            "sf_space": ("Космическая фантастика", "Фантастика"),
            "sf_social": ("Социально-психологическая фантастика", "Фантастика"),
            "humor_prose": ("Юмористическая проза", "Юмор"),
        }
        for code, (label, category) in expected.items():
            with self.subTest(code=code):
                self.assertEqual(GENRES[code]["label"], label)
                self.assertEqual(GENRES[code]["category"], category)

    def test_mapped_tag_keeps_original_id(self):
        genre = genre_for_tag(tag(42, "sf_action"))
        self.assertEqual(genre["tag_id"], 42)
        self.assertEqual(genre["label"], "Боевая фантастика и фэнтези")
        self.assertTrue(genre["mapped"])

    def test_unknown_technical_tag_has_explicit_fallback(self):
        genre = genre_for_tag(tag(7, "future_genre"))
        self.assertEqual(genre["category"], UNKNOWN_CATEGORY)
        self.assertEqual(genre["label"], "Неизвестный жанр (future_genre)")
        self.assertFalse(genre["mapped"])

    def test_unknown_russian_tag_keeps_readable_label(self):
        genre = genre_for_tag(tag(8, "Современная проза"))
        self.assertEqual(genre["category"], UNKNOWN_CATEGORY)
        self.assertEqual(genre["label"], "Современная проза")

    def test_exact_unique_russian_label_uses_dictionary_category(self):
        genre = genre_for_tag(tag(9, "Фэнтези"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertEqual(genre["label"], "Фэнтези")
        self.assertTrue(genre["mapped"])

    def test_duplicate_russian_label_remains_unknown(self):
        genre = genre_for_tag(tag(10, "Экономика"))
        self.assertEqual(genre["category"], UNKNOWN_CATEGORY)
        self.assertFalse(genre["mapped"])

    def test_book_tags_are_grouped_without_duplicate_category(self):
        groups = group_tags([
            tag(1, "sf_action"),
            tag(2, "sf_space"),
            tag(3, "det_classic"),
            tag(2, "sf_space"),
        ])
        self.assertEqual([group["category"] for group in groups], [
            "Детективы и триллеры",
            "Фантастика",
        ])
        self.assertEqual(len(groups[1]["genres"]), 2)

    def test_tree_retains_ids_counts_and_unknowns(self):
        tree = build_genre_tree([
            (tag(11, "sf_space"), 25),
            (tag(12, "sf_action"), 40),
            (tag(13, "custom_code"), 3),
        ])
        self.assertEqual([group["category"] for group in tree], ["Фантастика", UNKNOWN_CATEGORY])
        self.assertEqual(tree[0]["genres"][0]["tag_id"], 12)
        self.assertEqual(tree[0]["genres"][0]["count"], 40)
        self.assertEqual(tree[1]["genres"][0]["label"], "Неизвестный жанр (custom_code)")

    def test_sidebar_tree_has_all_categories_and_only_real_mapped_tags(self):
        tree = build_sidebar_genre_tree([
            tag(11, "sf_space"),
            tag(12, "sf_action"),
            tag(13, "custom_code"),
        ])
        self.assertEqual(len(tree), 21)
        fantasy = next(group for group in tree if group["category"] == "Фантастика")
        self.assertEqual([genre["tag_id"] for genre in fantasy["genres"]], [12, 11])
        self.assertFalse(any(genre["tag_id"] == 13 for group in tree for genre in group["genres"]))


if __name__ == "__main__":
    unittest.main()
