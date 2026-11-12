"""File names from the book and chapter titles (OU-03), safe on Windows, macOS and Linux.

File systems limit one name to 255 bytes (ext4, APFS: UTF-8) or 255 UTF-16 units (NTFS).
A character never takes more UTF-16 units than UTF-8 bytes, so a cap in UTF-8 bytes holds
for all of them. Names are capped in characters (to stay readable) and in bytes (for
titles in Greek, Chinese or maths symbols), leaving room for the longest suffix output
adds: `.<book>.readalong.json.partial` and `.<chapter file>.partial`.
"""

from __future__ import annotations

import re
import unicodedata

MAX_LENGTH = 120  # characters of one name part
MAX_BYTES = 200  # UTF-8 bytes of one name part: 200 + the 24-byte suffix stays under 255
NAME_LIMIT = 255  # bytes of a whole file name, the smallest limit of the usual file systems
_BOOK_IN_CHAPTER = (80, 100)  # characters, bytes of the book's name inside a chapter's name
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


def cut(text: str, chars: int, max_bytes: int) -> str:
    """`text` cut to at most `chars` characters and `max_bytes` UTF-8 bytes, on a character
    boundary, without trailing dots or spaces."""
    text = text[:chars]
    data = text.encode("utf-8")
    if len(data) > max_bytes:
        text = data[:max_bytes].decode("utf-8", "ignore")
    return text.rstrip(" .")


def clean(title: str, fallback: str) -> str:
    """A name part from a title: forbidden characters become spaces, runs of white space
    one space, no leading or trailing dots or spaces, at most MAX_LENGTH characters and
    MAX_BYTES bytes, never a name Windows reserves; `fallback` when nothing is left."""
    text = unicodedata.normalize("NFC", title)
    text = "".join(" " if unicodedata.category(c) in _UNPRINTABLE else c for c in text)
    text = _SPACES.sub(" ", _FORBIDDEN.sub(" ", text)).strip(" .")
    text = cut(text, MAX_LENGTH, MAX_BYTES)
    if not text:
        return fallback
    if text.split(".")[0].strip().upper() in _RESERVED:
        text = cut(f"_{text}", MAX_LENGTH, MAX_BYTES)
    return text


def book_name(title: str) -> str:
    return clean(title, "audiobook")


def chapter_file(book: str, number: int, count: int, title: str) -> str:
    """`<book> - 01 <chapter>.mp3`, numbered with at least two digits, padded to `count`.

    The book part is cut to 80 characters (100 bytes) and the whole name to MAX_LENGTH
    characters (MAX_BYTES bytes), so the number always survives and the path stays short.
    """
    width = max(2, len(str(count)))
    short = cut(book, *_BOOK_IN_CHAPTER) or "audiobook"
    base = f"{short} - {number:0{width}d} {clean(title, 'chapter')}"
    return f"{cut(base, MAX_LENGTH, MAX_BYTES)}.mp3"
