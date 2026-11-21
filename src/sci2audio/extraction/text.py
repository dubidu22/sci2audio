"""Record what a plain-text file holds as `Content` (D-344), and decode text files (D-345).

A plain-text file becomes one page without positions. Each printed line that is not blank is
a text line; a run of such lines between blank lines is a paragraph. The first line of a
paragraph is tagged ``p``, each following one ``p``, ``br``: the shape an EPUB ``<p>`` with
``<br>`` elements gives, so layout joins them the same way. White space is folded as a browser
shows it (D-306); every other character is kept as stored.

Inside a paragraph, two kinds of line start an element of their own (#466). A line that opens
a list item is tagged ``ul, li`` or ``ol, li``, as Markdown's are, its wrapped lines ``br``
after that, the marker kept in its text. It opens with a bullet ("- ", "* ", "• ") or is one
of a run of two or more numbered lines ("1. ", "1) ") that count up by one, and it stands
where the shape says list: first in the paragraph, after an item, or after a line ending in
a colon. So a spaced dash wrapped to a line's start stays in its sentence, and "1.
Introduction" alone or a German date opening a paragraph ("3. Oktober 1990") stays text.
Markdown would make a lone "1." line an item; plain text differs on purpose, for those
German dates and ordinals. And the line after a title line is tagged ``p``: a short line in
capitals, or a short line without closing punctuation before a line that starts with a
capital (`_title`). Hard-wrapped prose keeps its lines together: none of its lines but the
last is short, measured against its longest line that holds a space.

`decode_text` is shared with the Markdown reader: a byte order mark decides the encoding; a
file without one is read as UTF-8 if it is valid UTF-8, else as Windows-1252 as the WHATWG
Encoding Standard decodes it, which never fails and loses no byte, and the source then says the
encoding was guessed (D-346). Empty, binary and too large files raise `ExtractionError` with a
message a person can act on (D-347); a file of more printed lines than `MAX_LINES` is too large
too, counted before the text is split (D-579).
"""

from __future__ import annotations

import codecs
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sci2audio.core import Content, Page, Source, SourceFormat, TextLine, TextRun
from sci2audio.extraction.errors import ExtractionError
from sci2audio.extraction.markup import fold

MAX_TEXT = 64 * 1024 * 1024  # bytes of a text or Markdown file, as of one EPUB member (D-351)
# printed lines of a text file, blank ones included (#174, D-579): each costs about 425 bytes
# read and as much again in layout, so this bounds a file to about 210 MB, three times the
# hard-wrapped lines of the longest books (Shakespeare's works: about 170,000)
MAX_LINES = 500_000

# Byte order marks, longest first: a UTF-32 LE mark starts with the UTF-16 LE one. The names
# are the WHATWG ones where it has them (it has no UTF-32).
_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32-le", "utf-32le"),
    (codecs.BOM_UTF32_BE, "utf-32-be", "utf-32be"),
    (codecs.BOM_UTF8, "utf-8", "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le", "utf-16le"),
    (codecs.BOM_UTF16_BE, "utf-16-be", "utf-16be"),
)
# Windows-1252 as the WHATWG Encoding Standard decodes it: Python's cp1252 leaves five bytes
# unassigned; WHATWG maps them to the C1 controls of the same number, so no byte is lost.
_WINDOWS_1252 = "".join(
    bytes([byte]).decode("cp1252", errors="ignore") or chr(byte) for byte in range(256)
)
# Files that are not text, by their first bytes; a PDF gets a message of its own.
_PDF = b"%PDF-"
_BINARY = (
    b"PK\x03\x04",  # zip: EPUB, Word, OpenDocument
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
    b"\x1f\x8b",  # gzip
)
_LINE_END = re.compile(r"\r\n|\r|\n")
# Structure inside a paragraph (#466): list markers, and where a title line ends
_BULLET = re.compile(r"[-*\u2022]\s+\S")
_NUMBERED = re.compile(r"(\d{1,3})([.)])\s+\S")
TITLE_SHARE = 0.6  # a title line is at most this share of its paragraph's longest line
_ENDS = ".!?:;,\u2026-\u2010\u2011\u2013\u2014/"  # a line ending in one of these runs on
_CLOSERS = "\"'\u201c\u201d\u2019\u00ab\u00bb\u2039\u203a)]}"  # looked through at a line's end
# looked through at a line's start
_OPENERS = "\"'\u201c\u201e\u2018\u201a\u00ab\u00bb\u2039\u203a([{"


@dataclass(frozen=True)
class Decoded:
    """A text file's text and how it was read (see `Source.encoding`)."""

    text: str
    encoding: str  # the WHATWG name, e.g. "utf-8"
    guessed: bool  # no byte order mark and not UTF-8: read as Windows-1252


def decode_text(data: bytes, name: str) -> Decoded:
    """The text of a text or Markdown file (D-345); ExtractionError for an empty, binary or
    too large file (D-347). `name` is the file name the messages start with."""
    if not data:
        raise ExtractionError(f"{name}: the file is empty")
    if len(data) > MAX_TEXT:
        raise ExtractionError(
            f"{name}: the file is too large; sci2audio reads text files up to"
            f" {MAX_TEXT // (1024 * 1024)} MB"
        )
    if data.startswith(_PDF):
        raise ExtractionError(
            f"{name}: this is a PDF, not a text file; open it with the .pdf ending"
        )
    if data.startswith(_BINARY):
        raise ExtractionError(f"{name}: not a text file")
    decoded = _decode(data)
    if "\x00" in decoded.text:
        raise ExtractionError(f"{name}: not a text file")
    return decoded


def _decode(data: bytes) -> Decoded:
    for mark, codec, label in _MARKS:
        if data.startswith(mark):
            text = data[len(mark) :].decode(codec, errors="replace")
            return Decoded(text, label, guessed=False)
    try:
        return Decoded(data.decode("utf-8"), "utf-8", guessed=False)
    except UnicodeDecodeError:
        text, _ = codecs.charmap_decode(data, "strict", _WINDOWS_1252)
        return Decoded(text, "windows-1252", guessed=True)


def line_count(text: str) -> int:
    """The printed lines of `text`, blank ones included, counted without splitting it: each
    line end (CR LF, CR or LF) ends a line, and text after the last line end is one more."""
    ends = text.count("\n") + text.count("\r") - text.count("\r\n")
    return ends + (1 if text and not text.endswith(("\n", "\r")) else 0)


def check_lines(text: str, name: str, limit: int, kind: str) -> None:
    """ExtractionError if `text` holds more than `limit` printed lines; `kind` names the
    files in the message ("text", "Markdown")."""
    if line_count(text) > limit:
        raise ExtractionError(
            f"{name}: the file is too large; sci2audio reads {kind} files of up to {limit:,} lines"
        )


def source_of(data: bytes, name: str, kind: SourceFormat, decoded: Decoded) -> Source:
    """The `Source` of a text or Markdown file read as `decoded`."""
    return Source(
        name,
        kind,
        sha256=hashlib.sha256(data).hexdigest(),
        encoding=decoded.encoding,
        encoding_guessed=decoded.guessed,
    )


def extract_text(path: Path) -> Content:
    """Read the plain-text file at `path` into `Content`; ExtractionError if it can't be read."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ExtractionError(f"{path.name}: cannot be opened ({error.strerror})") from error
    return read_text(data, path.name)


def read_text(data: bytes, name: str) -> Content:
    """Read plain-text bytes into `Content`; `name` is the bare file name the source keeps."""
    decoded = decode_text(data, name)
    check_lines(decoded.text, name, MAX_LINES, "text")
    lines: list[TextLine] = []
    paragraph: list[str] = []
    for printed in [*_LINE_END.split(decoded.text), ""]:
        text = fold(printed)
        if text:
            paragraph.append(text)
            continue
        for text, tags in zip(paragraph, paragraph_tags(paragraph), strict=True):
            lines.append(TextLine(f"p1-l{len(lines) + 1}", (TextRun(text, tags=tags),)))
        paragraph = []
    if not lines:
        raise ExtractionError(f"{name}: the file holds no text")
    page = Page(1, lines=tuple(lines), order=tuple(line.id for line in lines))
    return Content(source=source_of(data, name, SourceFormat.TEXT, decoded), pages=(page,))


def paragraph_tags(paragraph: list[str]) -> list[tuple[str, ...]]:
    """The tags of each line of a plain-text paragraph (#466): ``p`` for its first line and
    for a line after a title line (`_title`), ``ul, li`` or ``ol, li`` for a line that opens a
    list item, and the tags of the line before plus ``br`` for any other line.

    A line with a list marker (`_items`) opens an item only where the shape says list: as
    the paragraph's first line, right after a line that opens or continues an item, or after
    a line ending in a colon. A spaced dash that a hard wrap put at a line's start ("Texte
    - meist unterwegs - und") stays inside its sentence (#561).

    Lines are short against the paragraph's longest line that holds a space: a lone long
    token (a URL, a DOI) on a line of its own does not make the filled lines short (M2)."""
    items = _items(paragraph)
    widths = [len(text) for text in paragraph if " " in text]
    longest = max(widths) if widths else max(map(len, paragraph), default=0)
    out: list[tuple[str, ...]] = []
    element: tuple[str, ...] = ("p",)  # the element the next wrapped line continues
    for k, text in enumerate(paragraph):
        anchored = k == 0 or element[0] != "p" or paragraph[k - 1].rstrip().endswith(":")
        if k in items and anchored:
            element = items[k]
            out.append(element)
        elif k and not _title(paragraph[k - 1], text, longest):
            out.append((*element, "br"))
        else:
            element = ("p",)
            out.append(element)
    return out


def _items(paragraph: list[str]) -> dict[int, tuple[str, ...]]:
    """The lines of the paragraph that may open a list item, by index, with their tags. Any
    line opening with a bullet ("- ", "* ", "• ") may; a numbered line ("1. ", "1) ") may in a
    run of two or more numbered lines of one style whose numbers go up by one, so a lone
    "1. Introduction" or a German date ("3. Oktober 1990 ...") stays text."""
    found: dict[int, tuple[str, ...]] = {}
    run: list[tuple[int, int, str]] = []  # (index, number, "." or ")")
    for k, text in enumerate(paragraph):
        if _BULLET.match(text):
            found[k] = ("ul", "li")
        elif numbered := _NUMBERED.match(text):
            number, style = int(numbered[1]), numbered[2]
            if not (run and number == run[-1][1] + 1 and style == run[-1][2]):
                found.update(_run(run))
                run = []
            run.append((k, number, style))
    found.update(_run(run))
    return found


def _run(run: list[tuple[int, int, str]]) -> dict[int, tuple[str, ...]]:
    return {k: ("ol", "li") for k, _, _ in run} if len(run) >= 2 else {}


def _title(line: str, after: str, longest: int) -> bool:
    """True if `line` is a title line, so `after` starts a paragraph of its own: it holds at
    least two letters, is no longer than `TITLE_SHARE` of the paragraph's longest line, and
    has no lower-case letter ("LISTENING TO PAPERS") or ends without punctuation, hyphen or
    dash before a line starting with a capital ("A pilot note" / "Written for ...")."""
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 2 or len(line) > TITLE_SHARE * longest:
        return False
    if not any(c.islower() for c in letters) and any(c.isupper() for c in letters):
        return True
    if line.rstrip(_CLOSERS)[-1:] in _ENDS:
        return False
    return after.lstrip(_OPENERS)[:1].isupper()
