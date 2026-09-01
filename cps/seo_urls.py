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

_ARMENIAN = {
    "\u0561": "a", "\u0562": "b", "\u0563": "g", "\u0564": "d", "\u0565": "e",
    "\u0566": "z", "\u0567": "e", "\u0568": "y", "\u0569": "t", "\u056a": "zh",
    "\u056b": "i", "\u056c": "l", "\u056d": "kh", "\u056e": "ts", "\u056f": "k",
    "\u0570": "h", "\u0571": "dz", "\u0572": "gh", "\u0573": "ch", "\u0574": "m",
    "\u0575": "y", "\u0576": "n", "\u0577": "sh", "\u0578": "o", "\u0579": "ch",
    "\u057a": "p", "\u057b": "j", "\u057c": "r", "\u057d": "s", "\u057e": "v",
    "\u057f": "t", "\u0580": "r", "\u0581": "ts", "\u0582": "u", "\u0583": "p",
    "\u0584": "k", "\u0585": "o", "\u0586": "f",
}

_GEORGIAN = {
    "\u10d0": "a", "\u10d1": "b", "\u10d2": "g", "\u10d3": "d", "\u10d4": "e",
    "\u10d5": "v", "\u10d6": "z", "\u10d7": "t", "\u10d8": "i", "\u10d9": "k",
    "\u10da": "l", "\u10db": "m", "\u10dc": "n", "\u10dd": "o", "\u10de": "p",
    "\u10df": "zh", "\u10e0": "r", "\u10e1": "s", "\u10e2": "t", "\u10e3": "u",
    "\u10e4": "p", "\u10e5": "k", "\u10e6": "sh", "\u10e7": "ch", "\u10e8": "sh",
    "\u10e9": "ch", "\u10ea": "ts", "\u10eb": "dz", "\u10ec": "ts", "\u10ed": "ch",
    "\u10ee": "kh", "\u10ef": "j", "\u10f0": "h",
}

_SEPARATORS = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"-+")
_ARMENIAN_RANGE = re.compile(r"[\u0530-\u058f]")
_GEORGIAN_RANGE = re.compile(r"[\u10a0-\u10ff]")


def _is_ukrainian(language, value):
    language = (language or "").lower()
    return language in ("uk", "ukr", "ukrainian") or any(char in value.lower() for char in "іїєґ")


def _is_script(language, value, lang_codes, char_pattern):
    language = (language or "").lower()
    if language in lang_codes:
        return True
    return bool(char_pattern.search(value))


def _transliterate(value, language=None):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    ukrainian = _is_ukrainian(language, value)
    armenian = _is_script(language, value, ("hy", "arm", "armenian"), _ARMENIAN_RANGE)
    georgian = _is_script(language, value, ("ka", "geo", "georgian"), _GEORGIAN_RANGE)
    if armenian:
        table = _ARMENIAN
    elif georgian:
        table = _GEORGIAN
    elif ukrainian:
        table = _UKRAINIAN
    else:
        table = _RUSSIAN
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
