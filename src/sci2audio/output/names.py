"""File names from the book and chapter titles (OU-03), safe on Windows, macOS and Linux.

File systems limit one name to 255 bytes (ext4, APFS: UTF-8) or 255 UTF-16 units (NTFS).
A character never takes more UTF-16 units than UTF-8 bytes, so a cap in UTF-8 bytes holds
for all of them. Names are capped in characters (to stay readable) and in bytes (for
titles in Greek, Chinese or maths symbols), leaving room for the longest suffix output
adds: `.<book>.readalong.json.partial` and `.<chapter file>.partial`.

A Mac's file system can still refuse a cleaned name (#493): APFS refuses a code point its own
Unicode table does not know yet (EILSEQ), and that table can be older than Python's, which
`clean` follows. So a name holding a character newer than Unicode 3.2 is tried on the folder
first (`refused`), and a refused one is made again from the characters every Mac knows
(`retried`). Every other name is never tried: nothing is created for it.
"""

from __future__ import annotations

import contextlib
import errno
import os
import re
import unicodedata
from pathlib import Path

MAX_LENGTH = 120  # characters of one name part
MAX_BYTES = 200  # UTF-8 bytes of one name part: 200 + the 24-byte suffix stays under 255
NAME_LIMIT = 255  # bytes of a whole file name, the smallest limit of the usual file systems
_BOOK_IN_CHAPTER = (80, 100)  # characters, bytes of the book's name inside a chapter's name
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
# controls, format, surrogates, line and paragraph separators, and code points Unicode has
# not assigned yet, which APFS refuses in a name (#491)
_UNPRINTABLE = frozenset({"Cc", "Cf", "Cs", "Cn", "Zl", "Zp"})
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


def older(text: str) -> str:
    """`text` with every code point Unicode 3.2 had not assigned yet turned into a space.
    Unicode 3.2 (2002, in Python's `unicodedata.ucd_3_2_0`) is older than the oldest table
    of APFS (Unicode 9.0), so every Mac accepts what is left (#493)."""
    old = unicodedata.ucd_3_2_0
    return "".join(" " if old.category(c) == "Cn" else c for c in text)


def retried(title: str, fallback: str) -> str:
    """The name part `clean` makes from `title`, from its old characters only (`older`);
    `fallback` when nothing is left."""
    return clean(older(title), fallback)


def refused(folder: Path, name: str) -> bool:
    """True if the file system refuses `name` in `folder` as an illegal byte sequence
    (EILSEQ, #493). Only a name holding a code point newer than Unicode 3.2 is tried, by
    making the hidden file `.<name>.partial` (the name output and the app write under first)
    with O_EXCL and removing it again; a file of that name that is already there is never
    touched and counts as accepted. Any other error, a missing folder included, is not a
    refusal: writing the file then fails as it always did."""
    if older(name) == name:
        return False
    probe = folder / f".{name}.partial"
    try:
        handle = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        return error.errno == errno.EILSEQ
    os.close(handle)
    with contextlib.suppress(OSError):
        os.unlink(probe)
    return False


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


SUBTITLE_SUFFIXES = (".srt", ".vtt")


def subtitle_files(book: str, mp3s: list[str], m4b: bool) -> list[str]:
    """The subtitle files (#214): an `.srt` and a `.vtt` named like each chapter's MP3, then
    `<book>.srt` and `<book>.vtt` for the M4B when there is one."""
    names = [f"{mp3.removesuffix('.mp3')}{suffix}" for mp3 in mp3s for suffix in SUBTITLE_SUFFIXES]
    if m4b:
        names += [f"{book}{suffix}" for suffix in SUBTITLE_SUFFIXES]
    return names
