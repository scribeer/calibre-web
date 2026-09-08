import unittest
from types import SimpleNamespace

from cps.aubooks_genres import (
    CATEGORY_SLUGS,
    CATEGORIES,
    EXTRA_ALIASES,
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
        self.assertEqual(len(CATEGORIES), 22)

    def test_flbusta_labels_and_categories(self):
        expected = {
            "economics_ref": ("Деловая литература", "Деловая литература"),
            "det_classic": ("Классический детектив", "Детективы и триллеры"),
            "child_sf_space": ("Детская фантастика: космические приключения, пришельцы", "Детская литература"),
            "nonf_biography": ("Биографии и мемуары: прочее", "Документальная литература"),
            "love_history": ("Исторические любовные романы", "Романтика"),
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
        genre = genre_for_tag(tag(8, "Современная зарубежная литература"))
        self.assertEqual(genre["category"], UNKNOWN_CATEGORY)
        self.assertEqual(genre["label"], "Современная зарубежная литература")

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
        self.assertEqual(len(tree), 22)
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

    def test_all_22_slugs_are_unique(self):
        self.assertEqual(len(CATEGORY_SLUGS), 22)
        self.assertEqual(len(set(CATEGORY_SLUGS)), 22)

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


class AubooksCaseInsensitiveLookupTest(unittest.TestCase):

    def test_detektiv_lowercase_is_mapped(self):
        genre = genre_for_tag(tag(50, "детектив"))
        self.assertEqual(genre["category"], "Детективы и триллеры")
        self.assertTrue(genre["mapped"])

    def test_detektivy_exact_still_works(self):
        genre = genre_for_tag(tag(51, "Детективы"))
        self.assertEqual(genre["category"], "Детективы и триллеры")
        self.assertTrue(genre["mapped"])

    def test_mixed_case_russian_label_resolves(self):
        for name in ("ФЭНТЕЗИ", "фэнтези", "Фэнтези"):
            with self.subTest(name=name):
                genre = genre_for_tag(tag(60, name))
                self.assertEqual(genre["category"], "Фантастика")
                self.assertTrue(genre["mapped"])

    def test_boevaya_fantastika_alias(self):
        genre = genre_for_tag(tag(70, "Боевая фантастика"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertEqual(genre["label"], "Боевая фантастика и фэнтези")
        self.assertTrue(genre["mapped"])

    def test_geroicheskoe_fentezi_alias(self):
        genre = genre_for_tag(tag(71, "Героическое фэнтези"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertTrue(genre["mapped"])

    def test_lybovnoe_fentezi_alias(self):
        genre = genre_for_tag(tag(72, "Любовное фэнтези"))
        self.assertEqual(genre["category"], "Романтика")
        self.assertTrue(genre["mapped"])

    def test_litrrpg_alias(self):
        genre = genre_for_tag(tag(73, "LitRPG"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertTrue(genre["mapped"])

    def test_publicistika_lowercase_alias(self):
        genre = genre_for_tag(tag(74, "публицистика"))
        self.assertEqual(genre["category"], "Документальная литература")
        self.assertTrue(genre["mapped"])

    def test_proza_lowercase_alias(self):
        genre = genre_for_tag(tag(75, "проза"))
        self.assertEqual(genre["category"], "Проза")
        self.assertTrue(genre["mapped"])

    def test_unknown_random_tag_still_fallback(self):
        genre = genre_for_tag(tag(99, "totally_unknown_xyz"))
        self.assertEqual(genre["category"], UNKNOWN_CATEGORY)
        self.assertFalse(genre["mapped"])

    def test_extra_aliases_all_resolve_to_valid_genres(self):
        for alias, code in EXTRA_ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIn(code, GENRES, f"Code {code!r} not in GENRES")

    def test_duplicate_label_economics_still_unknown(self):
        genre = genre_for_tag(tag(10, "Экономика"))
        self.assertEqual(genre["category"], UNKNOWN_CATEGORY)
        self.assertFalse(genre["mapped"])

    # Wave 2 — editorial aliases

    def test_sovremennaya_proza_alias(self):
        genre = genre_for_tag(tag(200, "Современная проза"))
        self.assertEqual(genre["category"], "Проза")
        self.assertTrue(genre["mapped"])

    def test_psihologiya_alias(self):
        genre = genre_for_tag(tag(201, "психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_voennaya_proza_alias(self):
        genre = genre_for_tag(tag(202, "Военная проза"))
        self.assertEqual(genre["category"], "Проза")
        self.assertTrue(genre["mapped"])

    def test_biografiya_alias(self):
        genre = genre_for_tag(tag(203, "Биография"))
        self.assertEqual(genre["category"], "Документальная литература")
        self.assertTrue(genre["mapped"])

    def test_nauka_alias(self):
        genre = genre_for_tag(tag(204, "Наука"))
        self.assertEqual(genre["category"], "Наука и образование")
        self.assertTrue(genre["mapped"])

    def test_nauchno_populyarnoe_alias(self):
        genre = genre_for_tag(tag(205, "Научно-популярное"))
        self.assertEqual(genre["category"], "Наука и образование")
        self.assertTrue(genre["mapped"])

    # Wave 2 — high-confidence aliases

    def test_misticheskoe_fentezi_alias(self):
        genre = genre_for_tag(tag(206, "Мистическое фэнтези"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertTrue(genre["mapped"])

    def test_foreign_detective_alias(self):
        genre = genre_for_tag(tag(207, "foreign_detective"))
        self.assertEqual(genre["category"], "Детективы и триллеры")
        self.assertTrue(genre["mapped"])

    def test_detskaya_literatura_alias(self):
        genre = genre_for_tag(tag(208, "Детская литература"))
        self.assertEqual(genre["category"], "Детская литература")
        self.assertTrue(genre["mapped"])

    def test_fantasy_alias(self):
        genre = genre_for_tag(tag(209, "fantasy"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertTrue(genre["mapped"])

    # Wave 3 — category restructure: Романтика

    def test_lyubovnyj_roman_alias_to_romance(self):
        genre = genre_for_tag(tag(300, "Любовный роман"))
        self.assertEqual(genre["category"], "Романтика")
        self.assertTrue(genre["mapped"])

    def test_love_fantasy_alias_to_romance(self):
        genre = genre_for_tag(tag(301, "love_fantasy"))
        self.assertEqual(genre["category"], "Романтика")
        self.assertTrue(genre["mapped"])

    def test_light_erotica_alias_to_romance(self):
        genre = genre_for_tag(tag(302, "Легкая эротика"))
        self.assertEqual(genre["category"], "Романтика")
        self.assertTrue(genre["mapped"])

    def test_love_code_maps_to_romance(self):
        genre = genre_for_tag(tag(303, "love"))
        self.assertEqual(genre["category"], "Романтика")
        self.assertTrue(genre["mapped"])

    # Wave 3 — category restructure: Психология и здоровье

    def test_psihologiya_alias_to_psychology_health(self):
        genre = genre_for_tag(tag(310, "психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_psy_theraphy_alias_to_psychology_health(self):
        genre = genre_for_tag(tag(311, "psy_theraphy"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_foreign_psychology_alias_to_psychology_health(self):
        genre = genre_for_tag(tag(312, "foreign_psychology"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_detskaya_psihologiya_alias_to_psychology_health(self):
        genre = genre_for_tag(tag(313, "Детская психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_medicina_alias_to_psychology_health(self):
        genre = genre_for_tag(tag(314, "Медицина"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_zdorove_alias_to_psychology_health(self):
        genre = genre_for_tag(tag(315, "Здоровье"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_sci_psychology_code_to_psychology_health(self):
        genre = genre_for_tag(tag(316, "sci_psychology"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_sci_medicine_code_to_psychology_health(self):
        genre = genre_for_tag(tag(317, "sci_medicine"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    # Wave 4 — psychology/health cleanup: moved codes

    def test_religion_self_to_psychology_health(self):
        genre = genre_for_tag(tag(400, "religion_self"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_family_to_psychology_health(self):
        genre = genre_for_tag(tag(401, "family"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_home_sex_to_psychology_health(self):
        genre = genre_for_tag(tag(402, "home_sex"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_sf_social_stays_in_fantasy(self):
        genre = genre_for_tag(tag(403, "sf_social"))
        self.assertEqual(genre["category"], "Фантастика")
        self.assertTrue(genre["mapped"])

    # Wave 4 — psychology/health cleanup: new aliases → sci_psychology

    def test_psyhoterapiya_konsultirovanie_alias(self):
        genre = genre_for_tag(tag(410, "Психотерапия и консультирование"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_obshchaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(411, "Общая психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_zarubezhnaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(412, "Зарубежная психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_sotsialnaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(413, "Социальная психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_psihologiya_i_zdorove_self_alias(self):
        genre = genre_for_tag(tag(414, "Психология и здоровье"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_klassiki_psihologii_alias(self):
        genre = genre_for_tag(tag(415, "Классики психологии"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_vozrastnaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(416, "Возрастная психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_seks_i_semejnaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(417, "Секс и семейная психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    # Wave 4 — psychology/health cleanup: new aliases → sci_psychology_popular

    def test_biznes_i_psihologiya_alias(self):
        genre = genre_for_tag(tag(420, "Бизнес и психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_psihologiya_biznesa_alias(self):
        genre = genre_for_tag(tag(421, "Психология бизнеса"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_prakticheskaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(422, "Практическая психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_domashnyaya_psihologiya_alias(self):
        genre = genre_for_tag(tag(423, "Домашняя психология"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    # Wave 4 — psychology/health cleanup: new aliases → sci_medicine

    def test_medicinskaya_literatura_alias(self):
        genre = genre_for_tag(tag(430, "Медицинская литература"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_zdorove_i_medicina_alias(self):
        genre = genre_for_tag(tag(431, "Здоровье и медицина"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    # Wave 4 — psychology/health cleanup: new aliases → home_health

    def test_zdorove_i_lichnostnyj_rost_alias(self):
        genre = genre_for_tag(tag(432, "Здоровье и личностный рост"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_zdorove_i_kulinariya_alias(self):
        genre = genre_for_tag(tag(433, "Здоровье и кулинария"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])

    def test_zdorove_i_sport_alias(self):
        genre = genre_for_tag(tag(434, "Здоровье и спорт"))
        self.assertEqual(genre["category"], "Психология и здоровье")
        self.assertTrue(genre["mapped"])


class AubooksGenreTreeDedupTest(unittest.TestCase):
    """Tests for build_genre_tree deduplication by genre code."""

    def test_sf_action_five_tags_merge_to_one(self):
        """sf_action / Боевая фантастика и фэнтези — 5 tags → 1 entry."""
        entries = [
            (tag(2469, "sf_action"), 3798),
            (tag(228, "Боевая фантастика"), 5049),
            (tag(2858, "fantasy_action"), 267),
            (tag(2522, "fantasy_fight"), 233),
            (tag(217, "Боевое фэнтези"), 204),
        ]
        tree = build_genre_tree(entries)
        fantasy = next(g for g in tree if g["category"] == "Фантастика")
        sf_action = [g for g in fantasy["genres"] if g["code"] == "sf_action"]
        self.assertEqual(len(sf_action), 1)
        genre = sf_action[0]
        self.assertEqual(genre["label"], "Боевая фантастика и фэнтези")
        self.assertEqual(sorted(genre["tag_ids"]), [217, 228, 2469, 2522, 2858])
        self.assertEqual(genre["count"], 9551)

    def test_single_tag_genre_unchanged(self):
        """Genre with one tag produces one entry with tag_ids=[id]."""
        entries = [(tag(100, "det_classic"), 500)]
        tree = build_genre_tree(entries)
        det = next(g for g in tree if g["category"] == "Детективы и триллеры")
        self.assertEqual(len(det["genres"]), 1)
        self.assertEqual(det["genres"][0]["tag_ids"], [100])
        self.assertEqual(det["genres"][0]["count"], 500)

    def test_count_is_sum_not_unique(self):
        """Count for merged genre is sum of individual tag counts."""
        entries = [
            (tag(1, "sf_action"), 100),
            (tag(2, "Боевая фантастика"), 200),
        ]
        tree = build_genre_tree(entries)
        fantasy = next(g for g in tree if g["category"] == "Фантастика")
        self.assertEqual(fantasy["genres"][0]["count"], 300)

    def test_no_duplicate_labels_in_tree(self):
        """No genre code appears twice in the tree."""
        entries = [
            (tag(1, "sf_action"), 100),
            (tag(2, "Боевая фантастика"), 200),
            (tag(3, "det_classic"), 50),
            (tag(4, "Классический детектив"), 30),
        ]
        tree = build_genre_tree(entries)
        all_codes = []
        for group in tree:
            for genre in group["genres"]:
                all_codes.append(genre["code"])
        self.assertEqual(len(all_codes), len(set(all_codes)),
                         f"Duplicate codes: {[c for c in all_codes if all_codes.count(c) > 1]}")

    def test_unknown_tags_still_appear(self):
        """Unknown tags still get their own entry in Другие жанры."""
        entries = [
            (tag(1, "sf_action"), 100),
            (tag(99, "totally_unknown"), 5),
        ]
        tree = build_genre_tree(entries)
        unknown = next(g for g in tree if g["category"] == "Другие жанры")
        self.assertEqual(len(unknown["genres"]), 1)
        self.assertEqual(unknown["genres"][0]["tag_ids"], [99])

    def test_sidebar_tree_still_works(self):
        """Sidebar tree deduplication still works after refactor."""
        tags = [
            tag(100, "det_action"),
            tag(200, "Боевик"),
            tag(101, "det_irony"),
            tag(201, "Иронический детектив"),
        ]
        tree = build_sidebar_genre_tree(tags)
        det = next(g for g in tree if g["category"] == "Детективы и триллеры")
        self.assertEqual(len(det["genres"]), 2)
        boevik = next(g for g in det["genres"] if g["label"] == "Боевик")
        self.assertEqual(sorted(boevik["tag_ids"]), [100, 200])

    def test_genre_tree_has_tag_ids_for_template(self):
        """Every genre in tree has tag_ids list (required by template)."""
        entries = [
            (tag(1, "sf_action"), 100),
            (tag(2, "det_classic"), 50),
        ]
        tree = build_genre_tree(entries)
        for group in tree:
            for genre in group["genres"]:
                self.assertIn("tag_ids", genre)
                self.assertIsInstance(genre["tag_ids"], list)
                self.assertGreater(len(genre["tag_ids"]), 0)


if __name__ == "__main__":
    unittest.main()
