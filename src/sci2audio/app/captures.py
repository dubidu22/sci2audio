"""A document's captures on disk: `captures.json` in its working folder (ADR-008 2.1 item
4, 2.3, #396).

Reading never changes anything. Writing puts the whole file in place atomically
(`files.write_texts`) and touches no other file. A file this version can't read (a link,
not a plain file, too large, not UTF-8 or JSON, another format, version or document) is
never written, renamed or removed: `write_captures` refuses it, and capturing stays off
for that document until the person fixes or removes the file. Once written, the file
stays, also when it holds no capture any more.

Only the interface's server writes the file, with one read, one change and one write per
change under its own lock (#397), and it reads through `load_captures`, which carries the
v1.3 markers over first (#475). The job runner, the audio job and the command line never
read or write it.

The carry-over (ADR-008 2.1 item 5): when a document has `markers.json` and no
`captures.json`, its markers become captures one to one (a marker without a note a mark,
one with a note a note; id, times and anchor as they are), and `captures.json` is written
from them with `migrated_from: markers.json`. `markers.json` is the person's own file from
v1.3: it is only read, never written, renamed or removed, and not read at all while
`captures.json` is there, so removing `captures.json` by hand brings the markers back. A
`markers.json` that v1.3 can't read, or whose markers the capture model refuses (a lone
surrogate, more than fits the size limit), is left as it is and reported
(`MarkersNotCarried`), and nothing is written: writing `captures.json` would hide its
markers for good, so capturing stays off for that document until the person fixes or
removes the file. For the same reason `write_captures` never creates `captures.json` beside
a `markers.json` unless what it writes is their carry-over (`migrated_from: markers.json`,
#875): a writer that skips `load_captures` is refused, nothing is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sci2audio.app.files import write_texts
from sci2audio.core import (
    Anchor,
    Capture,
    CaptureFile,
    CaptureFormatError,
    CaptureType,
    captures_from_data,
    captures_to_data,
)

CAPTURES = "captures.json"
FILE_LIMIT = 6_000_000  # bytes: room for every readable v1.3 markers file (2 MB) carried over
MARKERS = "markers.json"  # the v1.3 markers (#474), read for the carry-over only


class CapturesBroken(Exception):
    """The file is there but this version can't read it; it is left as it is."""


class MarkersNotCarried(CapturesBroken):
    """There is no `captures.json` and the v1.3 `markers.json` can't be carried over:
    v1.3 can't read it, or the capture model refuses its markers; or a write that is not
    their carry-over would create `captures.json` beside them (#875). Nothing is written and
    `markers.json` is left as it is; capturing stays off, as for a broken captures file."""


def captures_path(work: Path) -> Path:
    return work / CAPTURES


def read_captures(work: Path, document_id: str) -> CaptureFile | None:
    """The document's captures, or None if it has no `captures.json` yet. Raises
    CapturesBroken, saying why, if the file is there and this version can't read it (it
    is not touched), OSError if it can't be read at all."""
    path = captures_path(work)
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise CapturesBroken(f"{path} is not a plain file")
    if path.stat().st_size > FILE_LIMIT:
        raise CapturesBroken(f"{path} is larger than {FILE_LIMIT} bytes")
    try:
        captures = _parse(path.read_bytes().decode("utf-8"))
    except ValueError as error:  # UnicodeDecodeError and CaptureFormatError are ValueErrors
        raise CapturesBroken(f"{path} can't be read: {error}") from None
    if captures.document != document_id:
        raise CapturesBroken(f"{path} holds the captures of another document")
    return captures


def write_captures(work: Path, captures: CaptureFile) -> None:
    """Put `captures` in the document's `captures.json`, all of it or nothing. Raises
    CapturesBroken (nothing is written) if the file there now can't be read or belongs to
    another document, MarkersNotCarried (a CapturesBroken; nothing is written) if there is
    no `captures.json` yet but a `markers.json` and `captures` is not its carry-over,
    ValueError if the file would be larger than its limit, OSError if writing fails (the
    old file stays)."""
    # never write over a file this version can't read
    if read_captures(work, captures.document) is None and captures.migrated_from != MARKERS:
        markers = work / MARKERS
        if markers.exists() or markers.is_symlink():  # a new captures.json would hide them
            raise MarkersNotCarried(
                f"{markers} is not carried over yet: read the captures through load_captures"
            )
    write_texts({captures_path(work): _sized_text(captures)}, overwrite=True)


def load_captures(work: Path, document_id: str) -> CaptureFile | None:
    """The document's captures as the server reads them before a change: those in
    `captures.json`; while there is none, the v1.3 markers carried over (written to
    `captures.json` first, all of it or nothing); None if there is neither file.

    Raises CapturesBroken if `captures.json` can't be read, MarkersNotCarried (a
    CapturesBroken) if `markers.json` can't be carried over, OSError if a file can't be
    read or the new one can't be written; then nothing is written. `markers.json` is never
    changed. A `captures.json` another writer puts in place during the run is kept, never
    replaced, and returned."""
    captures = read_captures(work, document_id)
    if captures is not None:  # markers.json is not read while captures.json is there
        return captures
    carried = _carried_markers(work, document_id)
    if carried is None:
        return None
    try:
        text = _sized_text(carried)
    except ValueError as error:  # CaptureFormatError is a ValueError
        raise MarkersNotCarried(f"{work / MARKERS} can't be carried over: {error}") from None
    try:
        write_texts({captures_path(work): text}, overwrite=False)
    except FileExistsError:  # another writer was first: theirs stays
        return read_captures(work, document_id)
    return carried


def _sized_text(captures: CaptureFile) -> str:
    text = captures_text(captures)
    if len(text.encode("utf-8")) > FILE_LIMIT:
        raise ValueError(f"the captures file would be larger than {FILE_LIMIT} bytes")
    return text


def captures_text(captures: CaptureFile) -> str:
    """The file's text: UTF-8 JSON, one space of indent, a line end at the end."""
    text = json.dumps(captures_to_data(captures), ensure_ascii=False, indent=1) + "\n"
    if _parse(text) != captures:  # never write a file this version could not read back
        raise CaptureFormatError("the captures would not read back as they are")
    return text


def _parse(text: str) -> CaptureFile:
    try:
        return captures_from_data(json.loads(text, parse_constant=_no_constant))
    except RecursionError:
        raise CaptureFormatError("nested too deeply") from None


def _no_constant(name: str) -> None:
    raise CaptureFormatError(f"{name} is not a number")


# ---- the v1.3 markers file, read only (#474, #475) ------------------------------------------
# The checks of the v1.3 reader in the web layer (`web.markers.read_markers`), which the app
# may not import (D-46): this reads exactly the files v1.3 reads, and a test holds both to it.

MARKERS_FORMAT = "sci2audio-web-markers"
MARKERS_VERSION = 1
MARKERS_LIMIT = 2_000_000  # bytes
MAX_MARKERS = 2000
NOTE_LIMIT = 4000  # characters
_HEX = frozenset("0123456789abcdef")
_MARKERS_KEYS = frozenset({"format", "version", "document", "markers"})
_MARKER_KEYS = frozenset({"id", "created", "changed", "anchor", "note"})
_ANCHOR_KEYS = frozenset({"block", "start", "end", "text"})


def _carried_markers(work: Path, document_id: str) -> CaptureFile | None:
    """The document's v1.3 markers as captures, or None if it has no `markers.json`; the
    whole file is built before anything is written. Raises MarkersNotCarried, OSError."""
    path = work / MARKERS
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise MarkersNotCarried(f"{path} is not a plain file")
    if path.stat().st_size > MARKERS_LIMIT:
        raise MarkersNotCarried(f"{path} is larger than {MARKERS_LIMIT} bytes")
    try:
        entries = _markers(path.read_bytes().decode("utf-8"), document_id)
    except ValueError as error:  # UnicodeDecodeError is a ValueError
        raise MarkersNotCarried(f"{path} can't be read: {error}") from None
    try:
        captures = tuple(_as_capture(entry) for entry in entries)
        return CaptureFile(document_id, captures, migrated_from=MARKERS)
    except CaptureFormatError as error:
        raise MarkersNotCarried(f"{path} can't be carried over: {error}") from None


def _as_capture(marker: dict[str, Any]) -> Capture:
    """A marker without a note as a mark, one with a note as a note (ADR-008 2.1 item 5)."""
    a = marker["anchor"]
    kind = CaptureType.NOTE if marker["note"] else CaptureType.MARK
    anchor = Anchor(a["block"], a["start"], a["end"], a["text"])
    return Capture(marker["id"], kind, marker["created"], marker["changed"], anchor, marker["note"])


def _markers(text: str, document_id: str) -> list[dict[str, Any]]:
    """The markers of a v1 file's text, checked as v1.3 checks them. Raises ValueError."""
    try:
        data = json.loads(text, parse_constant=_no_marker_constant)
        if not isinstance(data, dict) or set(data) != _MARKERS_KEYS:
            raise ValueError("not a markers file")
        if data["format"] != MARKERS_FORMAT or data["version"] != MARKERS_VERSION:
            raise ValueError("another format or version")
        if data["document"] != document_id:
            raise ValueError("the markers of another document")
        entries = data["markers"]
        if not isinstance(entries, list) or len(entries) > MAX_MARKERS:
            raise ValueError(f"the markers are not a list of at most {MAX_MARKERS}")
        for entry in entries:
            _check_marker(entry)
    except RecursionError:
        raise ValueError("nested too deeply") from None
    if len({entry["id"] for entry in entries}) != len(entries):
        raise ValueError("one marker is named twice")
    return entries


def _no_marker_constant(name: str) -> None:
    raise ValueError(f"{name} is not a number")


def _check_marker(data: object) -> None:
    if not isinstance(data, dict) or set(data) != _MARKER_KEYS:
        raise ValueError("a marker has id, created, changed, anchor and note")
    marker_id, created, changed, note = data["id"], data["created"], data["changed"], data["note"]
    if not (isinstance(marker_id, str) and len(marker_id) == 16 and set(marker_id) <= _HEX):
        raise ValueError("a marker's id is 16 hex digits")
    if not (isinstance(created, str) and isinstance(changed, str) and isinstance(note, str)):
        raise ValueError("a marker's times and note are texts")
    if len(created) > 40 or len(changed) > 40 or len(note) > NOTE_LIMIT or "\x00" in note:
        raise ValueError("a marker's times or note are too long")
    anchor = data["anchor"]
    if not isinstance(anchor, dict) or set(anchor) != _ANCHOR_KEYS:
        raise ValueError("an anchor has block, start, end and text")
    block, start, end, sentence = anchor["block"], anchor["start"], anchor["end"], anchor["text"]
    if not all(type(value) is int for value in (block, start, end)):
        raise ValueError("an anchor's block and offsets are whole numbers, its text a text")
    if not isinstance(sentence, str):
        raise ValueError("an anchor's block and offsets are whole numbers, its text a text")
    if block < 0 or start < 0 or end < start or not sentence:
        raise ValueError("an anchor's offsets don't fit")
