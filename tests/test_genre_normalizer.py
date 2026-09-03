#!/usr/bin/env python3
"""
Тесты genre_normalizer.py — нормализация жанров AU-Books.

Запуск: python3 tests/test_genre_normalizer.py
"""

import sys
import os
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "aubooks"))

from genre_normalizer import GenreNormalizer, GenreNormalizerError


class TestGenreNormalizerInit(unittest.TestCase):
    """Тест загрузки mapping."""

    def test_load_default_mapping(self):
        norm = GenreNormalizer()
        self.assertGreater(len(norm._raw_to_canonical), 400)

    def test_load_custom_mapping(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv",
                                         delete=False, encoding="utf-8") as f:
            f.write("raw_tag\tcanonical_tag\tparent_category\tclassification\tconfidence\tbook_count\tnotes\n")
            f.write("test_code\tТест\tЮмор\tgenre_code\thigh\t1\ttest\n")
            f.flush()
            try:
                norm = GenreNormalizer(f.name)
                self.assertEqual(len(norm._raw_to_canonical), 1)
                self.assertEqual(norm._raw_to_canonical["test_code"], "Тест")
            finally:
                os.unlink(f.name)

    def test_missing_mapping_raises(self):
        with self.assertRaises(GenreNormalizerError):
            GenreNormalizer("/nonexistent/mapping.tsv")

    def test_malformed_mapping_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv",
                                         delete=False, encoding="utf-8") as f:
            f.write("bad\tcolumns\there\n")
            f.flush()
            try:
                with self.assertRaises(GenreNormalizerError):
                    GenreNormalizer(f.name)
            finally:
                os.unlink(f.name)

    def test_duplicate_raw_tag_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv",
                                         delete=False, encoding="utf-8") as f:
            f.write("raw_tag\tcanonical_tag\tparent_category\tclassification\tconfidence\tbook_count\tnotes\n")
            f.write("dup\tTest1\tЮмор\tgenre_code\thigh\t1\ttest\n")
            f.write("dup\tTest2\tЮмор\tgenre_code\thigh\t1\ttest\n")
            f.flush()
            try:
                with self.assertRaises(GenreNormalizerError):
                    GenreNormalizer(f.name)
            finally:
                os.unlink(f.name)

    def test_invalid_confidence_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv",
                                         delete=False, encoding="utf-8") as f:
            f.write("raw_tag\tcanonical_tag\tparent_category\tclassification\tconfidence\tbook_count\tnotes\n")
            f.write("bad\tTest\tЮмор\tgenre_code\tinvalid\t1\ttest\n")
            f.flush()
            try:
                with self.assertRaises(GenreNormalizerError):
                    GenreNormalizer(f.name)
            finally:
                os.unlink(f.name)


class TestNormalize(unittest.TestCase):
    """Тест нормализации тегов."""

    def setUp(self):
        self.norm = GenreNormalizer()

    def test_high_confidence_genre_code_mapped(self):
        result = self.norm.normalize(["det_action"])
        self.assertEqual(result, ["Боевик"])

    def test_high_confidence_canonical_unchanged(self):
        result = self.norm.normalize(["Боевик"])
        self.assertEqual(result, ["Боевик"])

    def test_unknown_tag_unchanged(self):
        result = self.norm.normalize(["unknown_tag_xyz"])
        self.assertEqual(result, ["unknown_tag_xyz"])

    def test_multiple_tags_normalized(self):
        result = self.norm.normalize(["det_action", "sf_fantasy", "read"])
        self.assertEqual(result, ["Боевик", "Фэнтези", "read"])

    def test_case_insensitive_mapping(self):
        result = self.norm.normalize(["ДЕТЕКТИВ"])
        self.assertEqual(result, ["Детектив"])

    def test_case_insensitive_dedup(self):
        result = self.norm.normalize(["детектив", "ДЕТЕКТИВ", "Детектив"])
        self.assertEqual(result, ["Детектив"])

    def test_case_insensitive_dedup_with_mapping(self):
        result = self.norm.normalize(["det_action", "Det_Action"])
        self.assertEqual(result, ["Боевик"])

    def test_unknown_tags_not_collapsed(self):
        result = self.norm.normalize(["Test", "test", "TEST"])
        self.assertEqual(result, ["Test", "test", "TEST"])

    def test_empty_list(self):
        result = self.norm.normalize([])
        self.assertEqual(result, [])

    def test_whitespace_stripped(self):
        result = self.norm.normalize(["  det_action  ", " sf_fantasy "])
        self.assertEqual(result, ["Боевик", "Фэнтези"])

    def test_empty_strings_skipped(self):
        result = self.norm.normalize(["", "  ", "det_action"])
        self.assertEqual(result, ["Боевик"])

    def test_real_world_example(self):
        result = self.norm.normalize([
            "det_action", "sf_fantasy", "LitRPG",
            "popadancy", "love_contemporary", "nonf_biography"
        ])
        expected = [
            "Боевик", "Фэнтези", "ЛитРПГ",
            "Попаданцы", "Современные любовные романы", "Биографии и мемуары: прочее"
        ]
        self.assertEqual(result, expected)

    def test_medium_confidence_unchanged(self):
        # Medium confidence tags should NOT be mapped
        medium_tag = None
        for tag, conf in self.norm._raw_confidence.items():
            if conf == "medium":
                medium_tag = tag
                break
        if medium_tag:
            result = self.norm.normalize([medium_tag])
            self.assertEqual(result, [medium_tag])

    def test_low_confidence_unchanged(self):
        # Low confidence tags should NOT be mapped
        low_tag = None
        for tag, conf in self.norm._raw_confidence.items():
            if conf == "low":
                low_tag = tag
                break
        if low_tag:
            result = self.norm.normalize([low_tag])
            self.assertEqual(result, [low_tag])

    def test_canonical_spelling_preserved(self):
        """Canonical spelling from mapping is always used."""
        result = self.norm.normalize(["детектив"])
        self.assertEqual(result, ["Детектив"])

    def test_uppercase_to_canonical(self):
        """Uppercase input maps to canonical spelling."""
        result = self.norm.normalize(["ДЕТЕКТИВ"])
        self.assertEqual(result, ["Детектив"])

    def test_mixed_case_dedup(self):
        """Mixed case duplicates collapse to one canonical."""
        result = self.norm.normalize(["детектив", "ДЕТЕКТИВ", "Детектив"])
        self.assertEqual(result, ["Детектив"])

    def test_code_plus_russian_dedup(self):
        """Code and Russian variants collapse to one canonical."""
        result = self.norm.normalize(["det_action", "Боевик"])
        self.assertEqual(result, ["Боевик"])

    def test_unknown_case_not_changed(self):
        """Unknown tags are not auto-cased."""
        result = self.norm.normalize(["Foo", "foo", "FOO"])
        self.assertEqual(result, ["Foo", "foo", "FOO"])

    def test_unicode_casefold(self):
        """Unicode casefold works for Cyrillic."""
        result = self.norm.normalize(["ДЕТЕКТИВ"])
        self.assertEqual(result, ["Детектив"])

    def test_trim_known_genre(self):
        """Whitespace around known genre is trimmed."""
        result = self.norm.normalize(["  ДЕТЕКТИВ  "])
        self.assertEqual(result, ["Детектив"])

    def test_psyhology_typo_mapped(self):
        """Typo in mapping is correctly mapped."""
        result = self.norm.normalize(["Психлогия"])
        self.assertEqual(result, ["Психология"])

    def test_horror_mapped_to_uzhasy(self):
        """Хоррор maps to Ужасы."""
        result = self.norm.normalize(["Хоррор"])
        self.assertEqual(result, ["Ужасы"])


class TestNormalizeDry(unittest.TestCase):
    """Тест dry-run нормализации."""

    def setUp(self):
        self.norm = GenreNormalizer()

    def test_dry_run_returns_all_fields(self):
        result = self.norm.normalize_dry(["det_action", "read"])
        self.assertIn("before", result)
        self.assertIn("after", result)
        self.assertIn("changes", result)
        self.assertIn("duplicates_collapsed", result)

    def test_dry_run_mapped_change(self):
        result = self.norm.normalize_dry(["det_action"])
        self.assertEqual(result["before"], ["det_action"])
        self.assertEqual(result["after"], ["Боевик"])
        mapped = [c for c in result["changes"] if c["type"] == "mapped"]
        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0]["raw"], "det_action")
        self.assertEqual(mapped[0]["canonical"], "Боевик")

    def test_dry_run_unchanged(self):
        result = self.norm.normalize_dry(["read"])
        self.assertEqual(result["after"], ["read"])
        unchanged = [c for c in result["changes"] if c["type"] == "unchanged"]
        self.assertEqual(len(unchanged), 1)

    def test_dry_run_duplicates_detected(self):
        result = self.norm.normalize_dry(["детектив", "Детектив"])
        self.assertEqual(len(result["duplicates_collapsed"]), 1)
        self.assertEqual(result["duplicates_collapsed"][0], "Детектив")


class TestMappingStats(unittest.TestCase):
    """Тест статистики mapping."""

    def test_stats_structure(self):
        norm = GenreNormalizer()
        stats = norm.mapping_stats
        self.assertIn("total_entries", stats)
        self.assertIn("high_mapped", stats)
        self.assertIn("by_confidence", stats)
        self.assertGreater(stats["total_entries"], 1000)
        self.assertGreater(stats["high_mapped"], 400)

    def test_stats_confidence_counts(self):
        norm = GenreNormalizer()
        stats = norm.mapping_stats
        by_conf = stats["by_confidence"]
        self.assertEqual(by_conf["high"] + by_conf["medium"] + by_conf["low"],
                         stats["total_entries"])


class TestMultiTagCanonical(unittest.TestCase):
    """Тест разделения comma-separated canonical values на отдельные теги."""

    def setUp(self):
        self.norm = GenreNormalizer()

    def test_two_tag_split(self):
        """network_literature → Самиздат, сетевая литература."""
        result = self.norm.normalize(["network_literature"])
        self.assertEqual(result, ["Самиздат", "сетевая литература"])

    def test_three_tag_split(self):
        """sci_popular → 3 tags."""
        result = self.norm.normalize(["sci_popular"])
        self.assertEqual(len(result), 3)
        self.assertIn("Образовательная", result)
        self.assertIn("прикладная", result)
        self.assertIn("научно-популярная литература", result)

    def test_dedup_with_split_canonical(self):
        """Unknown tag matching canonical from split is deduped."""
        result = self.norm.normalize(["network_literature", "Самиздат"])
        self.assertEqual(result, ["Самиздат", "сетевая литература"])

    def test_dedup_case_insensitive_with_split(self):
        """Case-insensitive dedup works across split canonical values."""
        result = self.norm.normalize(["network_literature", "самиздат"])
        self.assertEqual(result, ["Самиздат", "сетевая литература"])

    def test_unknown_tags_not_deduped_among_themselves(self):
        """Unknown tags are not deduped among themselves."""
        result = self.norm.normalize(["foo", "Foo", "FOO"])
        self.assertEqual(result, ["foo", "Foo", "FOO"])

    def test_split_canonical_preserves_order(self):
        """Split canonical tags appear in mapping order."""
        result = self.norm.normalize(["love_sf"])
        self.assertEqual(result, ["Любовное фэнтези", "любовно-фантастические романы"])

    def test_split_across_multiple_raw_tags(self):
        """Two raw tags each producing split canonical values."""
        result = self.norm.normalize(["network_literature", "love_sf"])
        self.assertEqual(len(result), 4)
        self.assertEqual(result, [
            "Самиздат", "сетевая литература",
            "Любовное фэнтези", "любовно-фантастические романы"
        ])

    def test_split_no_duplicates_across_tags(self):
        """No duplicates when split canonical values overlap with other raw tags."""
        # network_literature produces "Самиздат"
        # If "Самиздат" also appears as raw tag, it should be deduped
        result = self.norm.normalize(["network_literature", "Самиздат", "сетевая литература"])
        self.assertEqual(result, ["Самиздат", "сетевая литература"])

    def test_dry_run_shows_canonical_tags(self):
        """dry_run includes canonical_tags list for multi-tag mappings."""
        d = self.norm.normalize_dry(["network_literature"])
        change = d["changes"][0]
        self.assertEqual(change["canonical_tags"], ["Самиздат", "сетевая литература"])
        self.assertEqual(change["type"], "mapped")
        self.assertEqual(d["after"], ["Самиздат", "сетевая литература"])

    def test_single_comma_canonical_still_works(self):
        """Single canonical value (no comma) still works correctly."""
        result = self.norm.normalize(["det_action"])
        self.assertEqual(result, ["Боевик"])

    def test_split_trim_parts(self):
        """Whitespace around split parts is trimmed."""
        result = self.norm.normalize(["network_literature"])
        for tag in result:
            self.assertEqual(tag, tag.strip())
            self.assertGreater(len(tag), 0)


if __name__ == "__main__":
    unittest.main()
