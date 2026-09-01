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

    def test_armenian_transliteration(self):
        self.assertEqual(slugify("\u053c\u056b\u056c\u056b", "rus"), "lili")
        self.assertEqual(slugify("\u054e\u0561\u0572\u0578\u0582\u0581 \u0574\u0565\u057c\u0561\u056e\u0568", "rus"), "vaghouts-meratsy")
        self.assertEqual(slugify("\u0546\u0565\u0580\u056f\u0561, \u0561\u0576\u0581\u0575\u0561\u056c, \u0561\u057a\u0561\u057c\u0576\u056b", "rus"), "nerka-antsyal-aparni")
        self.assertEqual(slugify("\u0544\u0544", "rus"), "mm")

    def test_armenian_auto_detected_from_chars(self):
        self.assertEqual(slugify("\u053c\u056b\u056c\u056b"), "lili")
        self.assertEqual(slugify("\u0546\u0561\u0574\u0561\u056f"), "namak")

    def test_georgian_transliteration(self):
        self.assertEqual(slugify("\u10e1\u10d0\u10d9\u10d0\u10e0\u10d7\u10d5\u10d4\u10da\u10dd", "ka"), "sakartvelo")
        self.assertEqual(slugify("\u10d7\u10d1\u10d8\u10da\u10d8\u10e1\u10d8", "ka"), "tbilisi")

    def test_georgian_auto_detected_from_chars(self):
        self.assertEqual(slugify("\u10e1\u10d0\u10d9\u10d0\u10e0\u10d7\u10d5\u10d4\u10da\u10dd"), "sakartvelo")

    def test_mixed_cyrillic_latin(self):
        result = slugify("Тест Test", "rus")
        self.assertIn("test", result)

    def test_digits_preserved(self):
        self.assertEqual(slugify("42", "eng"), "42")
        self.assertEqual(slugify("Метро 2033", "rus"), "metro-2033")

    def test_apostrophes_normalized(self):
        self.assertEqual(slugify("I'm back", "eng"), "i-m-back")

    def test_hyphens_in_title(self):
        result = slugify("Король Уолл-стрит", "rus")
        self.assertIn("uoll-strit", result)
