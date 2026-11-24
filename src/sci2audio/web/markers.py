"""Markers with an optional note (#474, D-722, D-723, D-728): the v1.3 slice of the study
layer, kept in the web layer's own file `markers.json` in the document's working folder.

A marker is tied to the text, never to one audiobook: its anchor is the sentence's block,
its character offsets in that block's text and the text itself as printed. On every page
the anchor is looked for again in the document the audiobook was made from (`place`), so
a marker outlives a new audiobook and a changed layout; one that can't be found is listed
as not found, never dropped. The stored anchor is never rewritten.

Only the server writes the file, and only through `MarkerBook.change`: one read, one
change and one atomic write under a lock per working folder. Two servers on one working
folder: the last write wins, as for the listening position. A file this version can't
read (bad JSON, another format, version or document, too large, a link) is never written,
renamed or removed: setting markers is off for that document until the person fixes or
removes it. A removed marker leaves the file at once; the server keeps it in memory only,
for the toast's Undo (D-723 ruling 1).

The job runner, the audio job and the command line never read or write this file. The
core capture model of the study layer replaces it later (#396, #475).
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from sci2audio.app.captures import CapturesBroken, read_captures
from sci2audio.app.files import write_texts
from sci2audio.core import CaptureType, Document, Span

MARKERS = "markers.json"
MARKERS_FORMAT = "sci2audio-web-markers"
MARKERS_VERSION = 1
MAX_MARKERS = 2000
FILE_LIMIT = 2_000_000  # bytes
NOTE_LIMIT = 4000  # characters
UNDO_SECONDS = 600.0  # a removed marker can be put back for 10 minutes
UNDO_KEPT = 20  # removed markers kept per document
NEAR_BLOCKS = 20  # how far from its block a sentence cut differently is looked for

State = Literal["found", "not-read", "not-found"]
_ID_DIGITS = frozenset("0123456789abcdef")
_ANCHOR_KEYS = frozenset({"block", "start", "end", "text"})
_MARKER_KEYS = frozenset({"id", "created", "changed", "anchor", "note"})
_FILE_KEYS = frozenset({"format", "version", "document", "markers"})


class MarkerError(Exception):
    """A marker request the file or the store refuses: `kind` for programs."""

    kind = "markers-not-saved"


class MarkersBroken(MarkerError):
    """The file is there but this version can't read it; it is left as it is."""

    kind = "markers-unreadable"


class MarkerLimit(MarkerError):
    """Too many markers, or the file would grow past its limit."""

    kind = "too-many-markers"


class MarkersTooLarge(MarkerLimit):
    """The file would grow past its limit."""

    kind = "markers-too-large"


class NoteRefused(MarkerError):
    """A note too long or with a NUL character."""

    kind = "invalid"


class MarkerMissing(MarkerError):
    """No marker with that id in the file."""

    kind = "not-found"


class UndoExpired(MarkerError):
    """The server no longer holds the removed marker (10 minutes, a restart, 20 later)."""

    kind = "undo-expired"


class MarkedAgain(MarkerError):
    """The sentence got a marker again since this one was removed."""

    kind = "marked-again"


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


@dataclass(frozen=True)
class Placed:
    """A marker where this audiobook reads it: the chunk it is shown on, or None."""

    marker: Marker
    chunk: int | None
    state: State


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


# ---- the file ----------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        needle = _normal(anchor.text)[0]
        if not needle:
            return None
        count = len(self.texts)
        # 1. the same place, with the same text
        if 0 <= anchor.block < count and anchor.end <= len(self.texts[anchor.block]):
            here = self.texts[anchor.block][anchor.start : anchor.end]
            if _normal(here)[0] == needle:
                return anchor.block, anchor.start, anchor.end
        # 2. the same text in one block, nearest the old block (and its old offset)
        for block in sorted(range(count), key=lambda b: (abs(b - anchor.block), b)):
            hay, where = self.normal(block)
            starts = _occurrences(hay, needle)
            if starts:
                best = min(starts, key=lambda s: abs(where[s] - anchor.start))
                return block, where[best], where[best + len(needle) - 1] + 1
        # 3. the same text across neighbouring blocks (a sentence the layout now splits)
        return self._across(anchor, needle)

    def _across(self, anchor: Anchored, needle: str) -> tuple[int, int, int] | None:
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
        return block, raws[0], raws[-1] + 1


def finder(document: Document) -> Callable[[Anchored], tuple[int, int, int] | None]:
    """Where an anchor's sentence is in `document` now, as (block, start, end), or None:
    found as `locate` finds it, so an export (#399) orders captures as the pages place them."""
    return _Finder(document).find


def locate[T](
    items: Sequence[T], anchor: Callable[[T], Anchored], document: Document, spans: Sequence[Span]
) -> list[tuple[T, int | None, State]]:
    """Each item, by its anchor, where this audiobook reads it (`spans`: the read-along's
    chunks, in order), in reading order: found ones by their chunk, then those whose text
    this audiobook does not read, then those not found, each group in the given order. The
    sentence shown is the chunk that overlaps the found place most (the first on a tie).
    No item is ever left out. Markers and captures (#397) are placed alike."""
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


def place(markers: Sequence[Marker], document: Document, spans: Sequence[Span]) -> list[Placed]:
    """Each marker where this audiobook reads it, in reading order (`locate`)."""
    return [
        Placed(marker, chunk, state)
        for marker, chunk, state in locate(markers, lambda m: m.anchor, document, spans)
    ]


# ---- changing the file -----------------------------------------------------------------------


class MarkerBook:
    """The server's one way to change markers files, and its store of removed markers for
    Undo. `clock` gives seconds (tests pass their own)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._removed: dict[str, dict[str, tuple[Marker, float]]] = {}

    def _lock(self, work: Path) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(str(work), threading.Lock())

    def change[T](
        self,
        work: Path,
        document_id: str,
        edit: Callable[[list[Marker]], tuple[list[Marker] | None, T]],
    ) -> T:
        """Read the file, let `edit` change its markers (None: no change), write them back
        atomically, all under the folder's lock. The only path that writes the file
        (D-728 ruling 2). Raises MarkersBroken (nothing is written), MarkerError from
        `edit`, MarkerLimit, OSError (the old file stays)."""
        with self._lock(work):
            markers = read_markers(work, document_id)
            changed, result = edit(list(markers))
            if changed is not None:
                write_texts({work / MARKERS: markers_text(document_id, changed)}, overwrite=True)
            return result

    def set(
        self,
        work: Path,
        document_id: str,
        anchor: Anchor,
        existing: Callable[[list[Marker]], Marker | None],
    ) -> tuple[Marker, bool]:
        """A marker on the sentence `anchor` names: the one `existing` finds already on it
        among the file's markers (False), or a new one (True)."""

        def edit(markers: list[Marker]) -> tuple[list[Marker] | None, tuple[Marker, bool]]:
            there = existing(markers)
            if there is not None:
                return None, (there, False)
            if len(markers) >= MAX_MARKERS:
                raise MarkerLimit(f"a document holds at most {MAX_MARKERS} markers")
            taken = {marker.id for marker in markers}
            marker_id = secrets.token_hex(8)
            while marker_id in taken:
                marker_id = secrets.token_hex(8)
            now = _now()
            marker = Marker(marker_id, now, now, anchor)
            return [*markers, marker], (marker, True)

        return self.change(work, document_id, edit)

    def note(self, work: Path, document_id: str, marker_id: str, note: str) -> Marker:
        """The marker with its note replaced ("" for none). Raises NoteRefused."""
        problem = note_problem(note)
        if problem:
            raise NoteRefused(problem)

        def edit(markers: list[Marker]) -> tuple[list[Marker] | None, Marker]:
            at = _index(markers, marker_id)
            if markers[at].note == note:
                return None, markers[at]
            markers[at] = replace(markers[at], note=note, changed=_now())
            return markers, markers[at]

        return self.change(work, document_id, edit)

    def remove(self, work: Path, document_id: str, marker_id: str) -> Marker:
        """Take the marker out of the file and keep it for Undo."""

        def edit(markers: list[Marker]) -> tuple[list[Marker] | None, Marker]:
            gone = markers.pop(_index(markers, marker_id))
            return markers, gone

        gone = self.change(work, document_id, edit)
        with self._guard:
            kept = self._removed.setdefault(str(work), {})
            kept.pop(gone.id, None)
            kept[gone.id] = (gone, self._clock())
            while len(kept) > UNDO_KEPT:
                del kept[next(iter(kept))]
        return gone

    def restore(
        self,
        work: Path,
        document_id: str,
        marker_id: str,
        clash: Callable[[Marker, list[Marker]], bool],
    ) -> Marker:
        """Put a removed marker back unchanged, through `change` like every write. Raises
        UndoExpired if it is no longer kept, MarkedAgain if `clash` says its sentence has a
        marker again."""
        with self._guard:
            kept = self._removed.get(str(work), {})
            entry = kept.get(marker_id)
            if entry is not None and self._clock() - entry[1] > UNDO_SECONDS:
                del kept[marker_id]
                entry = None
        if entry is None:
            raise UndoExpired("the marker can no longer be put back")
        marker = entry[0]

        def edit(markers: list[Marker]) -> tuple[list[Marker] | None, Marker]:
            if any(other.id == marker.id for other in markers) or clash(marker, markers):
                raise MarkedAgain("the sentence has a marker again")
            if len(markers) >= MAX_MARKERS:
                raise MarkerLimit(f"a document holds at most {MAX_MARKERS} markers")
            return [*markers, marker], marker

        restored = self.change(work, document_id, edit)
        with self._guard:
            self._removed.get(str(work), {}).pop(marker_id, None)
        return restored


def _index(markers: Sequence[Marker], marker_id: str) -> int:
    for at, marker in enumerate(markers):
        if marker.id == marker_id:
            return at
    raise MarkerMissing(f"no marker {marker_id}")
