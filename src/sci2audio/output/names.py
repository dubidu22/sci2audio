"""File names from the book and chapter titles (OU-03), safe on Windows, macOS and Linux."""

from __future__ import annotations

import re
import unicodedata

MAX_LENGTH = 120  # characters of one name part, well inside every file system's limit
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_UNPRINTABLE = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})  # controls, format, surrogates
_SPACES = re.compile(r"\s+")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{n}" for n in range(10)),
    *(f"LPT{n}" for n in range(10)),
}


def clean(title: str, fallback: str) -> str:
    """A name part from a title: forbidden characters become spaces, runs of white space
    one space, no leading or trailing dots or spaces, at most MAX_LENGTH characters, never a
    name Windows reserves; `fallback` when nothing is left."""
    text = unicodedata.normalize("NFC", title)
    text = "".join(" " if unicodedata.category(c) in _UNPRINTABLE else c for c in text)
    text = _SPACES.sub(" ", _FORBIDDEN.sub(" ", text)).strip(" .")
    text = text[:MAX_LENGTH].rstrip(" .")
    if not text:
        return fallback
    if text.split(".")[0].strip().upper() in _RESERVED:
        text = f"_{text}"[:MAX_LENGTH].rstrip(" .")
    return text


def book_name(title: str) -> str:
    return clean(title, "audiobook")


def chapter_file(book: str, number: int, count: int, title: str) -> str:
    """`<book> - 01 <chapter>.mp3`, numbered with at least two digits, padded to `count`.

    The book part is cut to 80 characters and the whole name to MAX_LENGTH, so the number
    always survives and the path stays short on Windows.
    """
    width = max(2, len(str(count)))
    short = book[:80].rstrip(" .") or "audiobook"
    base = f"{short} - {number:0{width}d} {clean(title, 'chapter')}"
    return f"{base[:MAX_LENGTH].rstrip(' .')}.mp3"
