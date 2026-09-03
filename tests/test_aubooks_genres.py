import unittest
from types import SimpleNamespace

from cps.aubooks_genres import (
    CATEGORY_SLUGS,
    CATEGORIES,
    GENRES,
    UNKNOWN_CATEGORY,
    build_category_slug_map,
    build_genre_tree,
    build_sidebar_genre_tree,
    category_by_slug,
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

    def test_sidebar_tree_deduplicates_same_label_from_code_and_russian_tag(self):
        tree = build_sidebar_genre_tree([
            tag(100, "det_action"),
            tag(200, "Боевик"),
            tag(101, "det_irony"),
            tag(201, "Иронический детектив"),
        ])
        det = next(group for group in tree if group["category"] == "Детективы и триллеры")
        self.assertEqual(len(det["genres"]), 2)
        labels = [g["label"] for g in det["genres"]]
        self.assertEqual(len(labels), len(set(labels)), "Duplicate labels in sidebar tree")
        boevik = next(g for g in det["genres"] if g["label"] == "Боевик")
        self.assertEqual(sorted(boevik["tag_ids"]), [100, 200])
        self.assertIn(100, boevik["tag_ids"])
        self.assertIn(200, boevik["tag_ids"])

    def test_sidebar_tree_no_duplicate_labels_across_all_categories(self):
        all_labels = []
        for group in build_sidebar_genre_tree([
            tag(1, "det_action"),
            tag(2, "Боевик"),
            tag(3, "det_irony"),
            tag(4, "Иронический детектив"),
            tag(5, "sf_space"),
            tag(6, "Космическая фантастика"),
            tag(7, "love"),
            tag(8, "Любовные романы"),
        ]):
            for genre in group["genres"]:
                all_labels.append(genre["label"])
        self.assertEqual(len(all_labels), len(set(all_labels)),
                         "Duplicate labels found: {}".format(
                             [l for l in all_labels if all_labels.count(l) > 1]))

    def test_sidebar_tree_preserves_tag_id_for_url_generation(self):
        tree = build_sidebar_genre_tree([
            tag(100, "det_action"),
            tag(200, "Боевик"),
        ])
        det = next(group for group in tree if group["category"] == "Детективы и триллеры")
        boevik = next(g for g in det["genres"] if g["label"] == "Боевик")
        self.assertEqual(boevik["tag_id"], 100)
        self.assertIsInstance(boevik["tag_ids"], list)
        self.assertEqual(len(boevik["tag_ids"]), 2)

    def test_group_tags_produces_category_tag_ids(self):
        groups = group_tags([
            tag(10, "sf_action"),
            tag(20, "sf_space"),
            tag(30, "det_classic"),
        ])
        fantasy = next(g for g in groups if g["category"] == "Фантастика")
        self.assertIn("category_tag_ids", fantasy)
        self.assertEqual(sorted(fantasy["category_tag_ids"]), [10, 20])

    def test_group_tags_merges_duplicate_codes_into_category_tag_ids(self):
        groups = group_tags([
            tag(100, "det_action"),
            tag(200, "Боевик"),
        ])
        det = next(g for g in groups if g["category"] == "Детективы и триллеры")
        self.assertEqual(sorted(det["category_tag_ids"]), [100, 200])


class AubooksDetailTemplateTest(unittest.TestCase):

    def test_detail_template_has_cover_deferred_loading(self):
        from pathlib import Path
        tpl = Path("cps/themes/aubooks/templates/detail.html").read_text()
        self.assertIn('id="detailcover"', tpl)
        self.assertIn("data-src", tpl)
        self.assertIn("get_cover", tpl)
        self.assertIn("onerror", tpl)

    def test_detail_template_has_layout_wrapper(self):
        from pathlib import Path
        tpl = Path("cps/themes/aubooks/templates/detail.html").read_text()
        self.assertIn("aubooks-detail-layout", tpl)
        self.assertIn("aubooks-detail-cover-column", tpl)
        self.assertIn("aubooks-detail-content", tpl)

    def test_detail_template_no_bootstrap_grid_row(self):
        from pathlib import Path
        tpl = Path("cps/themes/aubooks/templates/detail.html").read_text()
        self.assertNotRegex(tpl, r'class="row"')

    def test_css_has_detail_layout_grid(self):
        from pathlib import Path
        css = Path("cps/static/css/aubooks.css").read_text()
        self.assertIn(".aubooks-detail-layout", css)
        self.assertIn("grid-template-columns", css)
        self.assertIn(".aubooks-detail-content", css)


class AubooksCategorySlugTest(unittest.TestCase):

    def test_all_21_slugs_are_unique(self):
        self.assertEqual(len(CATEGORY_SLUGS), 21)
        self.assertEqual(len(set(CATEGORY_SLUGS)), 21)

    def test_category_by_slug_returns_label(self):
        self.assertEqual(category_by_slug("fantastika"), "Фантастика")
        self.assertEqual(category_by_slug("detektivy-i-trillery"), "Детективы и триллеры")
        self.assertEqual(category_by_slug("spravochnaya-literatura"), "Справочная литература")

    def test_unknown_slug_returns_none(self):
        self.assertIsNone(category_by_slug("unknown-slug"))
        self.assertIsNone(category_by_slug(""))
        self.assertIsNone(category_by_slug("fantastika-extra"))

    def test_sidebar_tree_has_category_slug(self):
        tree = build_sidebar_genre_tree([
            tag(11, "sf_space"),
            tag(12, "sf_action"),
        ])
        fantasy = next(group for group in tree if group["category"] == "Фантастика")
        self.assertEqual(fantasy["category_slug"], "fantastika")
        self.assertIn("category_slug", fantasy)

    def test_all_sidebar_groups_have_slug(self):
        tree = build_sidebar_genre_tree([tag(i, c) for i, c in enumerate(GENRES)])
        for group in tree:
            self.assertIn("category_slug", group)
            self.assertTrue(category_by_slug(group["category_slug"]),
                            f"Slug {group['category_slug']!r} not resolvable")

    def test_group_tags_includes_category_slug(self):
        groups = group_tags([tag(10, "sf_action"), tag(20, "det_classic")])
        for group in groups:
            self.assertIn("category_slug", group)
            self.assertTrue(category_by_slug(group["category_slug"]))

    def test_sidebar_tree_category_tag_ids_nonempty(self):
        tree = build_sidebar_genre_tree([tag(i, c) for i, c in enumerate(GENRES)])
        for group in tree:
            self.assertIsInstance(group["category_tag_ids"], list)
            self.assertGreater(len(group["category_tag_ids"]), 0,
                               f"Empty tag_ids for {group['category']}")


class AubooksParentCategoryTemplateTest(unittest.TestCase):

    def test_sidebar_uses_category_by_slug_for_parent(self):
        from pathlib import Path
        tpl = Path("cps/themes/aubooks/templates/layout.html").read_text()
        self.assertIn("web.category_by_slug", tpl)
        self.assertIn("group.category_slug", tpl)

    def test_detail_uses_category_by_slug_for_parent(self):
        from pathlib import Path
        tpl = Path("cps/themes/aubooks/templates/detail.html").read_text()
        self.assertIn("web.category_by_slug", tpl)
        self.assertIn("group.category_slug", tpl)

    def test_index_breadcrumb_uses_category_by_slug(self):
        from pathlib import Path
        tpl = Path("cps/themes/aubooks/templates/index.html").read_text()
        self.assertIn("web.category_by_slug", tpl)
        self.assertIn("aubooks_genre.category_slug", tpl)


if __name__ == "__main__":
    unittest.main()
