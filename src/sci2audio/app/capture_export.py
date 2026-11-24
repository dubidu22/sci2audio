"""Captures written as files (ADR-008 2.1 item 7, 2.2 A and C, #399): Markdown for
Obsidian, RIS for Zotero and a CSV, each to a folder the person chooses.

The caller hands over what to write: each document's reference (its title as the Library
shows it) and its captures in reading order, each with the PDF page on which its sentence
starts. Nothing here reads a work folder or a setting, and nothing makes a network call.

Sentences and notes are written as they are (D-57); only what a format cannot hold as it
is changes, and in a way a reader can undo:

- CSV: a cell that begins with `=`, `+`, `-`, `@`, a tab or a carriage return gets one
  apostrophe in front (the OWASP rule against CSV injection), so a spreadsheet shows it as
  text and never runs it; the text after the apostrophe is the text as it is. The file is
  UTF-8 with a byte-order mark, since Excel reads UTF-8 without one as a legacy code page.
- RIS: a line break inside a value ends the line, and the next line is written with one
  leading space, so no line of a note or a sentence can begin with a tag. Zotero shows a
  note as HTML, where that space does not show.
- Markdown: the sentence is a block quote, line by line. Markdown characters in it are not
  escaped, since escaping would change the quote; only a heading, which holds one line,
  has its line breaks written as spaces.

An existing file is never replaced unless the caller says so (`overwrite`): the interface
asks the person first. The file is written whole or not at all (`files`).
"""

from __future__ import annotations

import csv
import errno
import io
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sci2audio.app.files import write_bytes_atomically
from sci2audio.app.report import Pages
from sci2audio.core import Capture, CaptureType, Content, Document, SourceFormat


class ExportFormat(StrEnum):
    """The three files; the value is the file's extension."""

    MARKDOWN = "md"
    RIS = "ris"
    CSV = "csv"


@dataclass(frozen=True)
class ExportLabels:
    """The words a heading of a capture is made of, in the interface's language. `page`
    holds `{page}` where the page number goes. The CSV's `type` column is data and always
    `mark`, `note` or `quote`."""

    mark: str = "Mark"
    note: str = "Note"
    quote: str = "Quote"
    page: str = "p. {page}"


ENGLISH = ExportLabels()


@dataclass(frozen=True)
class Reference:
    """What the document states about itself (ADR-008 2.2 A): `title` as the Library shows
    it; authors, year and DOI only where extraction found them, else empty."""

    title: str
    authors: tuple[str, ...] = ()
    year: str = ""
    doi: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("a reference needs the document's title")
        if not all(self.authors):
            raise ValueError("an author is named by a text, never an empty one")


@dataclass(frozen=True)
class ExportedCapture:
    """A capture and the PDF page on which its sentence starts; None for EPUB, Markdown
    and text, and where the sentence is not found in the document."""

    capture: Capture
    page: int | None = None

    def __post_init__(self) -> None:
        if self.page is not None and self.page < 1:
            raise ValueError(f"a page is counted from 1, not {self.page}")


@dataclass(frozen=True)
class ExportedDocument:
    reference: Reference
    captures: tuple[ExportedCapture, ...] = ()


# ---- what the document states --------------------------------------------------------------

_DOI = re.compile(r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)", re.IGNORECASE)
_YEAR = re.compile(r"(\d{4})(?:\D|$)")


def reference_of(title: str, content: Content) -> Reference:
    """The reference of a document whose Library title is `title`. The DOI is the
    identifier when that is a DOI (not an ISBN or arXiv id). A PDF gets no year: extraction
    takes its date from the file's CreationDate, the day the file was made, which is not a
    year the document states (a paper from 1987 scanned in 2015 would read 2015)."""
    metadata = content.metadata
    doi = found.group(1) if (found := _DOI.fullmatch(metadata.identifier.strip())) else ""
    year = ""
    if content.source.format is not SourceFormat.PDF and (found := _YEAR.match(metadata.date)):
        year = found.group(1)
    authors = tuple(author for author in metadata.authors if author)
    return Reference(title, authors, year, doi)


class PageFinder:
    """The PDF page on which a sentence starts, for one document."""

    def __init__(self, document: Document) -> None:
        self._document = document
        pdf = document.content.source.format is SourceFormat.PDF
        self._pages = Pages(document) if pdf else None

    def page(self, block: int, start: int) -> int | None:
        """The page of the character at `start` in block `block` (where the interface
        found the capture's sentence); None for a document without pages or a place the
        document does not have."""
        if self._pages is None or not 0 <= block < len(self._document.blocks):
            return None
        part = self._document.blocks[block].part_at(start)
        return self._pages.items.get(part.item) if part else None


# ---- the three texts ------------------------------------------------------------------------

_BREAK = re.compile(r"\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]")
"""Every line break `str.splitlines` knows: a reader may take any of them as one."""

CSV_COLUMNS = ("document", "type", "page", "sentence", "text")
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _lines(text: str) -> list[str]:
    return _BREAK.split(text)


def _heading(capture: ExportedCapture, labels: ExportLabels) -> str:
    word = {
        CaptureType.MARK: labels.mark,
        CaptureType.NOTE: labels.note,
        CaptureType.QUOTE: labels.quote,
    }[capture.capture.type]
    if capture.page is None:
        return word
    return f"{word} · {labels.page.format(page=capture.page)}"


def markdown_text(documents: Sequence[ExportedDocument], labels: ExportLabels = ENGLISH) -> str:
    """One Markdown text: a `#` heading per document, a `##` heading per capture, its
    sentence as a block quote and a note's text below it."""
    out: list[str] = []
    for document in documents:
        if out:
            out.append("")
        out += [f"# {_one_line(document.reference.title)}"]
        for item in document.captures:
            out += ["", f"## {_one_line(_heading(item, labels))}", ""]
            out += [f"> {line}" if line else ">" for line in _lines(item.capture.anchor.text)]
            if item.capture.text:
                out += ["", *_lines(item.capture.text)]
    return "".join(f"{line}\n" for line in out)


def _one_line(text: str) -> str:
    return " ".join(_lines(text))


def ris_text(documents: Sequence[ExportedDocument], labels: ExportLabels = ENGLISH) -> str:
    """One RIS record per document, a new item for Zotero: its reference and one `N1`
    note per capture (its heading, its sentence, a note's text)."""
    records = []
    for document in documents:
        ref = document.reference
        references = [("TY", "GEN"), ("TI", ref.title)]  # extraction records no item type
        references += [("AU", author) for author in ref.authors]
        references += [(tag, value) for tag, value in (("PY", ref.year), ("DO", ref.doi)) if value]
        fields: list[tuple[str, list[str]]] = []
        fields += [(tag, _lines(value)) for tag, value in references]
        for item in document.captures:
            # each part is split on its own: a sentence ending in "\r" and the line end
            # after it must not merge into one "\r\n"
            note = [_heading(item, labels), *_lines(item.capture.anchor.text)]
            if item.capture.text:
                note += ["", *_lines(item.capture.text)]
            fields.append(("N1", note))
        fields.append(("ER", [""]))
        records.append("".join(_ris_field(tag, lines) for tag, lines in fields))
    return "\r\n".join(records)


def _ris_field(tag: str, lines: list[str]) -> str:
    first, *more = lines
    return f"{tag}  - {first}\r\n" + "".join(f" {line}\r\n" for line in more)


def csv_text(documents: Sequence[ExportedDocument]) -> str:
    """The table of all captures (RFC 4180), a header row first; without the file's
    byte-order mark."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for document in documents:
        for item in document.captures:
            capture = item.capture
            page = "" if item.page is None else str(item.page)
            writer.writerow(
                [
                    _cell(document.reference.title),
                    capture.type.value,
                    page,
                    _cell(capture.anchor.text),
                    _cell(capture.text),
                ]
            )
    return buffer.getvalue()


def _cell(text: str) -> str:
    return "'" + text if text.startswith(_FORMULA_STARTS) else text


# ---- the file -------------------------------------------------------------------------------

STEM_BYTES = 120
"""A file name's stem holds at most this many bytes of UTF-8: with its extension and the
partial file's name around it (`files.partial_path`), it stays under the 255 bytes every
file system allows."""

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{port}{n}" for port in ("COM", "LPT") for n in "0123456789\u00b9\u00b2\u00b3"}
)
"""Names Windows keeps for devices, with any extension; the ports also with a superscript
number (COM\u00b9)."""


def file_stem(title: str) -> str:
    """A file name for `title` without its extension, safe on Windows, macOS and Linux:
    the characters a file system refuses become spaces, runs of white space one space, no
    dot or space at either end, at most `STEM_BYTES` bytes; a Windows device name gets a
    `_` in front; "captures" if nothing is left. `file_stem(file_stem(x)) == file_stem(x)`."""
    stem = _trimmed(" ".join(_UNSAFE.sub(" ", title).split()))
    while len(stem.encode("utf-8")) > STEM_BYTES:
        stem = _trimmed(stem[:-1])
    if stem.split(".")[0].rstrip(" ").upper() in _RESERVED:
        stem = "_" + stem
    return stem or "captures"


def _trimmed(text: str) -> str:
    return text.strip(". ")


def export_text(
    form: ExportFormat, documents: Sequence[ExportedDocument], labels: ExportLabels = ENGLISH
) -> bytes:
    """The file's bytes: UTF-8, the CSV with a byte-order mark."""
    if form is ExportFormat.CSV:
        return csv_text(documents).encode("utf-8-sig")
    if form is ExportFormat.RIS:
        return ris_text(documents, labels).encode("utf-8")
    return markdown_text(documents, labels).encode("utf-8")


def export_captures(
    folder: Path,
    stem: str,
    form: ExportFormat,
    documents: Iterable[ExportedDocument],
    *,
    overwrite: bool = False,
    labels: ExportLabels = ENGLISH,
) -> Path:
    """Write `documents` as `<folder>/<stem>.<extension>` and return its path, the whole
    file or nothing.

    Raises ValueError if `stem` is not a safe file name (`file_stem`), NotADirectoryError
    if `folder` is not a folder, FileExistsError (nothing written) if the file is there and
    `overwrite` is false, also when it appears during the write, OSError if writing fails
    (no partial file is left, and a file being replaced stays as it was)."""
    if not stem or file_stem(stem) != stem:
        raise ValueError(f"{stem!r} is not a safe file name; file_stem gives one")
    if not folder.is_dir():
        raise NotADirectoryError(errno.ENOTDIR, "not a folder", str(folder))
    target = folder / f"{stem}.{form.value}"
    if not overwrite and (target.exists() or target.is_symlink()):
        raise FileExistsError(errno.EEXIST, "the file is there already", str(target))
    write_bytes_atomically(target, export_text(form, list(documents), labels), overwrite=overwrite)
    return target
