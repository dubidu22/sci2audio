"""The v1.3 markers (#474, D-722, D-728), read only, and finding a sentence again.

v1.3 kept markers with an optional note in the web layer's own file `markers.json` in the
document's working folder. The captures (#397) replace them: the server no longer writes
that file, and the carry-over (`app.captures`, #475) turns its markers into captures. This
module keeps v1.3's reader, which the library's counts use until a document's markers are
carried over (`count_captures`), and the file's text as v1.3 wrote it (`markers_text`).

An anchor is tied to the text, never to one audiobook: its sentence's block, its character
offsets in that block's text and the text itself as printed. On every page it is looked for
again in the document the audiobook was made from (`locate`), so a capture outlives a new
audiobook and a changed layout; one that can't be found is listed as not found, never
dropped. The stored anchor is never rewritten.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from sci2audio.app.captures import CapturesBroken, read_captures
from sci2audio.core import CaptureType, Document, Span

MARKERS = "markers.json"
MARKERS_FORMAT = "sci2audio-web-markers"
MARKERS_VERSION = 1
MAX_MARKERS = 2000
FILE_LIMIT = 2_000_000  # bytes
NOTE_LIMIT = 4000  # characters
NEAR_BLOCKS = 20  # how far from its block a sentence cut differently is looked for

State = Literal["found", "not-read", "not-found"]
_ID_DIGITS = frozenset("0123456789abcdef")
_ANCHOR_KEYS = frozenset({"block", "start", "end", "text"})
_MARKER_KEYS = frozenset({"id", "created", "changed", "anchor", "note"})
_FILE_KEYS = frozenset({"format", "version", "document", "markers"})


class MarkerError(Exception):
    """A markers file this version would not write: it could not read it back."""


class MarkersBroken(MarkerError):
    """The file is there but this version can't read it; it is left as it is."""


class MarkerLimit(MarkerError):
    """Too many markers, or the file would grow past its limit."""


class MarkersTooLarge(MarkerLimit):
    """The file would grow past its limit."""


@dataclass(frozen=True)
class Anchor:
    """A sentence in the document's text: block, character offsets, the text as printed."""

    block: int
    start: int
    end: int
    text: str


class Anchored(Protocol):
    """What finding a sentence again needs: a marker's anchor or a capture's (#397)."""

    @property
    def block(self) -> int: ...
    @property
    def start(self) -> int: ...
    @property
    def end(self) -> int: ...
    @property
    def text(self) -> str: ...


@dataclass(frozen=True)
class Marker:
    id: str
    created: str
    changed: str
    anchor: Anchor
    note: str = ""


def anchor_of(document: Document, span: Span) -> Anchor:
    """The anchor of the sentence `span` reads. The span must be valid for the document."""
    text = document.blocks[span.block].text
    return Anchor(span.block, span.start, span.end, text[span.start : span.end])


def note_problem(note: str) -> str | None:
    """Why a note can't be kept, or None."""
    if len(note) > NOTE_LIMIT:
        return f"a note holds at most {NOTE_LIMIT} characters"
    if "\x00" in note:
        return "a note can't hold a NUL character"
    return None


# ---- the file, as v1.3 wrote and read it ------------------------------------------------


def _no_constant(name: str) -> None:
    raise ValueError(f"{name} is not a number")


def _is_int(value: object) -> bool:
    return type(value) is int


def _anchor(data: object) -> Anchor:
    if not isinstance(data, dict) or set(data) != _ANCHOR_KEYS:
        raise ValueError("an anchor has block, start, end and text")
    block, start, end, text = data["block"], data["start"], data["end"], data["text"]
    if not (_is_int(block) and _is_int(start) and _is_int(end) and isinstance(text, str)):
        raise ValueError("an anchor's block and offsets are whole numbers, its text a text")
    if block < 0 or start < 0 or end < start or not text:
        raise ValueError("an anchor's offsets don't fit")
    return Anchor(block, start, end, text)


def _marker(data: object) -> Marker:
    if not isinstance(data, dict) or set(data) != _MARKER_KEYS:
        raise ValueError("a marker has id, created, changed, anchor and note")
    marker_id, created, changed, note = data["id"], data["created"], data["changed"], data["note"]
    if not (isinstance(marker_id, str) and len(marker_id) == 16 and set(marker_id) <= _ID_DIGITS):
        raise ValueError("a marker's id is 16 hex digits")
    if not (isinstance(created, str) and isinstance(changed, str) and isinstance(note, str)):
        raise ValueError("a marker's times and note are texts")
    if len(created) > 40 or len(changed) > 40 or note_problem(note):
        raise ValueError("a marker's times or note are too long")
    return Marker(marker_id, created, changed, _anchor(data["anchor"]), note)


def read_markers(work: Path, document_id: str) -> list[Marker]:
    """The markers of the document, in the file's order; [] if there is no file. Raises
    MarkersBroken if the file is there and this version can't read it (it is not touched),
    OSError if it can't be read at all."""
    path = work / MARKERS
    if not path.exists() and not path.is_symlink():
        return []
    if path.is_symlink() or not path.is_file():
        raise MarkersBroken(f"{path} is not a plain file")
    if path.stat().st_size > FILE_LIMIT:
        raise MarkersBroken(f"{path} is larger than {FILE_LIMIT} bytes")
    try:
        return _parse(path.read_bytes().decode("utf-8"), document_id)
    except ValueError as error:  # UnicodeDecodeError is a ValueError
        raise MarkersBroken(f"{path} can't be read: {error}") from None


def _parse(text: str, document_id: str) -> list[Marker]:
    """The markers of a file's text. Raises ValueError if this version can't read it."""
    try:
        data = json.loads(text, parse_constant=_no_constant)
        if not isinstance(data, dict) or set(data) != _FILE_KEYS:
            raise ValueError("not a markers file")
        if data["format"] != MARKERS_FORMAT or data["version"] != MARKERS_VERSION:
            raise ValueError("another format or version")
        if data["document"] != document_id:
            raise ValueError("the markers of another document")
        entries = data["markers"]
        if not isinstance(entries, list) or len(entries) > MAX_MARKERS:
            raise ValueError(f"the markers are not a list of at most {MAX_MARKERS}")
        markers = [_marker(entry) for entry in entries]
    except RecursionError:
        raise ValueError("nested too deeply") from None
    if len({marker.id for marker in markers}) != len(markers):
        raise ValueError("one marker is named twice")
    return markers


def _data(marker: Marker) -> dict[str, Any]:
    a = marker.anchor
    return {
        "id": marker.id,
        "created": marker.created,
        "changed": marker.changed,
        "anchor": {"block": a.block, "start": a.start, "end": a.end, "text": a.text},
        "note": marker.note,
    }


def markers_text(document_id: str, markers: Sequence[Marker]) -> str:
    """The file's text for these markers. Raises MarkerLimit past the limits."""
    if len(markers) > MAX_MARKERS:
        raise MarkerLimit(f"a document holds at most {MAX_MARKERS} markers")
    data = {
        "format": MARKERS_FORMAT,
        "version": MARKERS_VERSION,
        "document": document_id,
        "markers": [_data(marker) for marker in markers],
    }
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if len(text.encode("utf-8")) > FILE_LIMIT:
        raise MarkersTooLarge(f"the markers file would be larger than {FILE_LIMIT} bytes")
    try:  # never write a file this version could not read back
        _parse(text, document_id)
    except ValueError as error:
        raise MarkerError(f"the markers would not be readable: {error}") from None
    return text


def count_captures(work: Path, document_id: str) -> dict[str, Any]:
    """The document's captures by type (`note`, `quote`, `mark`), for the removal box
    (ADR-008 2.1 item 4, #396), counted as the box is drawn: from `captures.json`, or,
    while there is none, from `markers.json` as the carry-over (#475) will map them: a
    marker with a note as a note, one without as a mark. `unread` names the file that
    is there but can't be read (`captures` or `markers`), else None."""
    counts: dict[str, Any] = {**dict.fromkeys(CaptureType, 0), "unread": None}
    try:
        captures = read_captures(work, document_id)
    except (CapturesBroken, OSError):
        return counts | {"unread": "captures"}
    if captures is not None:  # markers.json is not read while captures.json is there
        return counts | captures.count()
    try:
        markers = read_markers(work, document_id)
    except (MarkersBroken, OSError):
        return counts | {"unread": "markers"}
    noted = sum(1 for marker in markers if marker.note)
    return counts | {CaptureType.NOTE: noted, CaptureType.MARK: len(markers) - noted}


# ---- finding a marker again (plan section 3) ----------------------------------------------


def _normal(text: str) -> tuple[str, list[int]]:
    """The text as it reads, with where each of its characters stands in `text`: soft
    hyphens and a hyphen that joins a word across a line end left out, every run of white
    space one space, none at either end."""
    out: list[str] = []
    where: list[int] = []
    at, size = 0, len(text)
    while at < size:
        char = text[at]
        if char == "­":
            at += 1
            continue
        if char == "-" and text[at + 1 : at + 2] == "\n" and text[at + 2 : at + 3].islower():
            at += 2
            continue
        if char.isspace():
            if out and out[-1] != " ":
                out.append(" ")
                where.append(at)
            at += 1
            continue
        out.append(char)
        where.append(at)
        at += 1
    if out and out[-1] == " ":
        out.pop()
        where.pop()
    return "".join(out), where


def _occurrences(hay: str, needle: str) -> list[int]:
    found: list[int] = []
    at = hay.find(needle)
    while at >= 0:
        found.append(at)
        at = hay.find(needle, at + 1)
    return found


class _Finder:
    """Looks for anchors in one document; each block is made readable once."""

    def __init__(self, document: Document) -> None:
        self.texts = [block.text for block in document.blocks]
        self._normal: dict[int, tuple[str, list[int]]] = {}

    def normal(self, block: int) -> tuple[str, list[int]]:
        if block not in self._normal:
            self._normal[block] = _normal(self.texts[block])
        return self._normal[block]

    def find(self, anchor: Anchored) -> tuple[int, int, int] | None:
        """(block, start, end) of the anchor's sentence in this document, or None."""
        found = self.place(anchor)
        return None if found is None else found[0]

    def place(self, anchor: Anchored) -> tuple[tuple[int, int, int], tuple[int, int]] | None:
        """As `find`, and (block, start) of the sentence's first character: a sentence the
        layout now splits is placed in the block holding most of it, but it starts in an
        earlier one, and an export names the page where it starts (#399)."""
        needle = _normal(anchor.text)[0]
        if not needle:
            return None
        count = len(self.texts)
        # 1. the same place, with the same text
        if 0 <= anchor.block < count and anchor.end <= len(self.texts[anchor.block]):
            here = self.texts[anchor.block][anchor.start : anchor.end]
            if _normal(here)[0] == needle:
                return (anchor.block, anchor.start, anchor.end), (anchor.block, anchor.start)
        # 2. the same text in one block, nearest the old block (and its old offset)
        for block in sorted(range(count), key=lambda b: (abs(b - anchor.block), b)):
            hay, where = self.normal(block)
            starts = _occurrences(hay, needle)
            if starts:
                best = min(starts, key=lambda s: abs(where[s] - anchor.start))
                first = where[best]
                return (block, first, where[best + len(needle) - 1] + 1), (block, first)
        # 3. the same text across neighbouring blocks (a sentence the layout now splits)
        return self._across(anchor, needle)

    def _across(
        self, anchor: Anchored, needle: str
    ) -> tuple[tuple[int, int, int], tuple[int, int]] | None:
        low = max(0, min(anchor.block, len(self.texts)) - NEAR_BLOCKS)
        high = min(len(self.texts), anchor.block + NEAR_BLOCKS + 1)
        hay: list[str] = []
        owner: list[tuple[int, int]] = []  # per character of the joined text: (block, raw)
        for block in range(low, high):
            text, where = self.normal(block)
            if not text:
                continue
            if hay:
                hay.append(" ")
                owner.append((-1, -1))
            hay.extend(text)
            owner.extend((block, raw) for raw in where)
        starts = _occurrences("".join(hay), needle)
        if not starts:
            return None
        start = starts[0]
        stretch = [o for o in owner[start : start + len(needle)] if o[0] >= 0]
        shares: dict[int, list[int]] = {}
        for block, raw in stretch:
            shares.setdefault(block, []).append(raw)
        block = max(shares, key=lambda b: (len(shares[b]), -b))
        raws = shares[block]
        return (block, raws[0], raws[-1] + 1), stretch[0]


def finder(document: Document) -> Callable[[Anchored], tuple[int, int] | None]:
    """Where an anchor's sentence starts in `document` now, as (block, offset), or None:
    found as `locate` finds it, so an export (#399) orders captures as the pages place them
    and names the page where each sentence starts."""
    places = _Finder(document)

    def start(anchor: Anchored) -> tuple[int, int] | None:
        found = places.place(anchor)
        return None if found is None else found[1]

    return start


def locate[T](
    items: Sequence[T], anchor: Callable[[T], Anchored], document: Document, spans: Sequence[Span]
) -> list[tuple[T, int | None, State]]:
    """Each item, by its anchor, where this audiobook reads it (`spans`: the read-along's
    chunks, in order), in reading order: found ones by their chunk, then those whose text
    this audiobook does not read, then those not found, each group in the given order. The
    sentence shown is the chunk that overlaps the found place most (the first on a tie).
    No item is ever left out."""
    finder = _Finder(document)
    by_block: dict[int, list[tuple[int, Span]]] = {}
    for number, span in enumerate(spans):
        if span.start < span.end:
            by_block.setdefault(span.block, []).append((number, span))
    found: list[tuple[int, int, tuple[T, int | None, State]]] = []
    unread: list[tuple[T, int | None, State]] = []
    lost: list[tuple[T, int | None, State]] = []
    for order, item in enumerate(items):
        where = finder.find(anchor(item))
        if where is None:
            lost.append((item, None, "not-found"))
            continue
        block, start, end = where
        best, most = None, 0
        for number, span in by_block.get(block, ()):
            overlap = min(end, span.end) - max(start, span.start)
            if overlap > most:
                best, most = number, overlap
        if best is None:
            unread.append((item, None, "not-read"))
        else:
            found.append((best, order, (item, best, "found")))
    found.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in found] + unread + lost


def same_sentence(anchor: Anchored, others: Sequence[Anchored], document: Document | None) -> bool:
    """Whether one of `others` stands on the sentence `anchor` stands on, with no audiobook
    to place them in (#934): sentences never overlap, so two anchors that overlap in one
    block are one sentence, whatever their offsets. Each is found in `document` first, as
    its text may have moved; one not found there is no sentence of it. Without a document,
    their own places count."""
    finder = None if document is None else _Finder(document)

    def where(item: Anchored) -> tuple[int, int, int] | None:
        return (item.block, item.start, item.end) if finder is None else finder.find(item)

    here = where(anchor)
    if here is None:
        return False
    block, start, end = here
    for other in others:
        there = where(other)
        if there is not None and there[0] == block and min(end, there[2]) > max(start, there[1]):
            return True
    return False
