# -*- coding: utf-8 -*-

import re
import unicodedata


_RUSSIAN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_UKRAINIAN = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ь": "", "'": "", "’": "",
}

_UKRAINIAN_CONTEXT = {
    "є": ("ye", "ie"),
    "ї": ("yi", "i"),
    "й": ("y", "i"),
    "ю": ("yu", "iu"),
    "я": ("ya", "ia"),
}

_SEPARATORS = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"-+")


def _is_ukrainian(language, value):
    language = (language or "").lower()
    return language in ("uk", "ukr", "ukrainian") or any(char in value.lower() for char in "іїєґ")


def _transliterate(value, language=None):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    ukrainian = _is_ukrainian(language, value)
    table = _UKRAINIAN if ukrainian else _RUSSIAN
    result = []
    at_word_start = True

    for char in value:
        if ukrainian and char in _UKRAINIAN_CONTEXT:
            start, middle = _UKRAINIAN_CONTEXT[char]
            result.append(start if at_word_start else middle)
            at_word_start = False
        elif char in table:
            replacement = table[char]
            result.append(replacement)
            if replacement:
                at_word_start = False
        elif char.isascii() and char.isalnum():
            result.append(char)
            at_word_start = False
        elif char.isalpha():
            ascii_char = unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode("ascii")
            result.append(ascii_char)
            at_word_start = not bool(ascii_char)
        else:
            result.append("-")
            at_word_start = True

    return "".join(result)


def slugify(value, language=None, max_length=96, fallback="item"):
    slug = _SEPARATORS.sub("-", _transliterate(value, language))
    slug = _DASHES.sub("-", slug).strip("-")
    if max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or fallback


def book_slug_parts(author, title, language=None):
    return (
        slugify(author, language=language, fallback="unknown-author"),
        slugify(title, language=language, fallback="book"),
    )


def primary_author(authors, author_sort=""):
    authors = list(authors or [])
    if not authors:
        return None

    by_sort = {getattr(author, "sort", ""): author for author in authors}
    for sort_name in (author_sort or "").split("&"):
        author = by_sort.get(sort_name.strip())
        if author is not None:
            return author
    return min(authors, key=lambda author: getattr(author, "id", 0))
