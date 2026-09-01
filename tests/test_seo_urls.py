import unittest

from cps.seo_urls import book_slug_parts, slugify


class SeoSlugTest(unittest.TestCase):
    def test_russian_transliteration(self):
        self.assertEqual(slugify("Михаил Булгаков", "rus"), "mihail-bulgakov")
        self.assertEqual(slugify("Мастер и Маргарита", "rus"), "master-i-margarita")

    def test_ukrainian_transliteration(self):
        self.assertEqual(slugify("Іван Багряний", "ukr"), "ivan-bahrianyi")

    def test_english_punctuation_and_dashes(self):
        self.assertEqual(slugify("  Hello, world! -- Revised  ", "eng"), "hello-world-revised")

    def test_empty_values_have_safe_fallbacks(self):
        self.assertEqual(book_slug_parts("", "", "eng"), ("unknown-author", "book"))

    def test_slug_is_bounded(self):
        self.assertLessEqual(len(slugify("А" * 200, "rus")), 96)


if __name__ == "__main__":
    unittest.main()
