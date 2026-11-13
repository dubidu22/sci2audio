"""Record what a plain-text file holds as `Content` (D-344), and decode text files (D-345).

A plain-text file becomes one page without positions. Each printed line that is not blank is
a text line; a run of such lines between blank lines is a paragraph. The first line of a
paragraph is tagged ``p``, each following one ``p``, ``br``: the shape an EPUB ``<p>`` with
``<br>`` elements gives, so layout joins them the same way. White space is folded as a browser
shows it (D-306); every other character is kept as stored.

`decode_text` is shared with the Markdown reader: a byte order mark decides the encoding; a
file without one is read as UTF-8 if it is valid UTF-8, else as Windows-1252 as the WHATWG
Encoding Standard decodes it, which never fails and loses no byte, and the source then says the
encoding was guessed (D-346). Empty, binary and too large files raise `ExtractionError` with a
message a person can act on (D-347).
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
    lines: list[TextLine] = []
    in_paragraph = False
    for printed in _LINE_END.split(decoded.text):
        text = fold(printed)
        if not text:  # a blank line ends the paragraph
            in_paragraph = False
            continue
        tags = ("p", "br") if in_paragraph else ("p",)
        lines.append(TextLine(f"p1-l{len(lines) + 1}", (TextRun(text, tags=tags),)))
        in_paragraph = True
    if not lines:
        raise ExtractionError(f"{name}: the file holds no text")
    page = Page(1, lines=tuple(lines), order=tuple(line.id for line in lines))
    return Content(source=source_of(data, name, SourceFormat.TEXT, decoded), pages=(page,))
