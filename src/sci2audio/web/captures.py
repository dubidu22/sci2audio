"""The server's store of captures (#397, ADR-008 2.1): marks, notes and quotes set at a
sentence while listening, kept in the document's `captures.json` through `app.captures`.

Every change is one read, one change and one atomic write under a lock per working folder
(`CaptureBook.change`); this is the only path in the server that writes the file, and the
web layer writes it only through `app.captures.write_captures`. A file this version can't
read is never written, renamed or removed: capturing is off for that document until the
person fixes or removes it. A removed capture leaves the file at once; the server keeps it
in memory only, for the toast's Undo (ADR-008 2.1 item 6).

A sentence holds at most one capture of each type (ADR-008 2.2 B). The anchor is the
sentence as printed, never its spoken form (D-57); where this audiobook reads it is worked
out on each load (`markers.locate`), never stored.

Every read goes through `app.captures.load_captures` (#475): with only the v1.3
`markers.json` there, it carries the markers over first. When it refuses to (a markers
file it can't read), capturing is off for that document and nothing is written, since
writing `captures.json` would hide those markers for good. Reads take the folder's lock
too, so a carry-over never meets a change half way.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sci2audio.app.captures import (
    CapturesBroken,
    MarkersNotCarried,
    load_captures,
    peek_carry_over,
    write_captures,
)
from sci2audio.core import Anchor, Capture, CaptureFile, CaptureFormatError, CaptureType
from sci2audio.core.captures import MAX_CAPTURES, text_problem

UNDO_SECONDS = 600.0  # a removed capture can be put back for 10 minutes
UNDO_KEPT = 20  # removed captures kept per document


class CaptureError(Exception):
    """A capture request the file or the store refuses: `kind` for programs."""

    kind = "captures-not-saved"


class CapturesUnreadable(CaptureError):
    """The file is there but this version can't read it; it is left as it is."""

    kind = "captures-unreadable"


class MarkersWaiting(CaptureError):
    """The document has the v1.3 `markers.json`, no `captures.json`, and the carry-over
    (#475) refused it: nothing is written."""

    kind = "markers-not-carried"


class CarryOverUnsaved(OSError):
    """The v1.3 `markers.json` was read, but the `captures.json` carried over from it could
    not be written (a full disk, say, #910): nothing was written and `markers.json` is as
    it was. An OSError, so that every reader that keeps going past one still does."""


class CaptureLimit(CaptureError):
    """Too many captures, or the file would grow past its limit."""

    kind = "too-many-captures"


class CapturesTooLarge(CaptureLimit):
    kind = "captures-too-large"


class TextRefused(CaptureError):
    """A note's text the file can't hold, or text on a mark or a quote."""

    kind = "invalid"


class CaptureMissing(CaptureError):
    kind = "not-found"


class UndoExpired(CaptureError):
    """The server no longer holds the removed capture (10 minutes, a restart, 20 later)."""

    kind = "undo-expired"


class NoteThere(CaptureError):
    """The sentence has a note already (written in another window, say): a new note's text
    is never dropped for it; the page keeps it and says so."""

    kind = "note-exists"


class CapturedAgain(CaptureError):
    """The sentence got a capture of this type again since this one was removed."""

    kind = "captured-again"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(work: Path, document_id: str) -> CaptureFile | None:
    """The document's captures (the v1.3 markers carried over first, #475), None while it
    has none. Raises CapturesUnreadable if the file can't be read, MarkersWaiting if the
    markers could not be carried over, CarryOverUnsaved if they were read but their
    `captures.json` could not be written, OSError if the folder can't be read at all."""
    try:
        return load_captures(work, document_id)
    except MarkersNotCarried as error:
        raise MarkersWaiting(str(error)) from None
    except CapturesBroken as error:
        raise CapturesUnreadable(str(error)) from None
    except OSError as error:
        if _carrying_over(work, document_id):
            raise CarryOverUnsaved(*error.args) from error
        raise


def _carrying_over(work: Path, document_id: str) -> bool:
    """After an OSError of `load_captures`: whether it was the carry-over's write. With
    still no `captures.json` and markers the carry-over still makes captures of, nothing
    else was left to fail (#910). Asked of `app.captures`, the one reader of
    `markers.json` (#887)."""
    try:
        return peek_carry_over(work, document_id) is not None
    except (CapturesBroken, OSError):
        return False


class CaptureBook:
    """The server's one way to change captures files, and its store of removed captures
    for Undo. `clock` gives seconds (tests pass their own)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._removed: dict[str, dict[str, tuple[Capture, float]]] = {}

    def _lock(self, work: Path) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(str(work), threading.Lock())

    def read(self, work: Path, document_id: str) -> CaptureFile | None:
        """`load` under the folder's lock: what the page shows."""
        with self._lock(work):
            return load(work, document_id)

    def change[T](
        self,
        work: Path,
        document_id: str,
        edit: Callable[[list[Capture]], tuple[list[Capture] | None, T]],
    ) -> T:
        """Read the file, let `edit` change its captures (None: no change), write them back
        atomically, all under the folder's lock. Raises CapturesUnreadable or MarkersWaiting
        (nothing is written), CaptureError from `edit`, CaptureLimit, OSError (the old file
        stays)."""
        with self._lock(work):
            file = load(work, document_id)
            changed, result = edit(list(file.captures) if file else [])
            if changed is None:
                return result
            if len(changed) > MAX_CAPTURES:
                raise CaptureLimit(f"a document holds at most {MAX_CAPTURES} captures")
            migrated = file.migrated_from if file else None
            try:
                write_captures(work, CaptureFile(document_id, tuple(changed), migrated))
            except CapturesBroken as error:  # changed on disk since the read
                raise CapturesUnreadable(str(error)) from None
            except CaptureFormatError as error:
                raise CaptureError(f"the captures would not be readable: {error}") from None
            except ValueError as error:  # past the file's size limit
                raise CapturesTooLarge(str(error)) from None
            return result

    def add(
        self,
        work: Path,
        document_id: str,
        kind: CaptureType,
        anchor: Anchor,
        text: str,
        existing: Callable[[list[Capture]], Capture | None],
    ) -> tuple[Capture, bool]:
        """A capture of `kind` on the sentence `anchor` names: the mark or quote `existing`
        finds already there (False, unchanged), or a new one (True). A note needs text; a
        mark and a quote hold none. Raises NoteThere for a note on a sentence that has one,
        so its text is never lost (ADR-008 2.2 B)."""
        _check_text(kind, text)

        def edit(captures: list[Capture]) -> tuple[list[Capture] | None, tuple[Capture, bool]]:
            there = existing(captures)
            if there is not None and kind is CaptureType.NOTE:
                raise NoteThere("the sentence has a note already")
            if there is not None:
                return None, (there, False)
            if len(captures) >= MAX_CAPTURES:
                raise CaptureLimit(f"a document holds at most {MAX_CAPTURES} captures")
            taken = {capture.id for capture in captures}
            capture_id = secrets.token_hex(8)
            while capture_id in taken:
                capture_id = secrets.token_hex(8)
            now = _now()
            capture = Capture(capture_id, kind, now, now, anchor, text)
            return [*captures, capture], (capture, True)

        return self.change(work, document_id, edit)

    def write_note(self, work: Path, document_id: str, capture_id: str, text: str) -> Capture:
        """The note with its text replaced. Raises TextRefused for empty text (a note is
        removed instead) or a capture that is not a note."""
        _check_text(CaptureType.NOTE, text)

        def edit(captures: list[Capture]) -> tuple[list[Capture] | None, Capture]:
            at = _index(captures, capture_id)
            if captures[at].type is not CaptureType.NOTE:
                raise TextRefused(f"a {captures[at].type} holds no text")
            if captures[at].text == text:
                return None, captures[at]
            captures[at] = replace(captures[at], text=text, changed=_now())
            return captures, captures[at]

        return self.change(work, document_id, edit)

    def remove(self, work: Path, document_id: str, capture_id: str) -> Capture:
        """Take the capture out of the file and keep it for Undo."""

        def edit(captures: list[Capture]) -> tuple[list[Capture] | None, Capture]:
            gone = captures.pop(_index(captures, capture_id))
            return captures, gone

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
        capture_id: str,
        clash: Callable[[Capture, list[Capture]], bool],
    ) -> Capture:
        """Put a removed capture back unchanged, through `change` like every write. Raises
        UndoExpired if it is no longer kept, CapturedAgain if `clash` says its sentence has a
        capture of its type again."""
        with self._guard:
            kept = self._removed.get(str(work), {})
            entry = kept.get(capture_id)
            if entry is not None and self._clock() - entry[1] > UNDO_SECONDS:
                del kept[capture_id]
                entry = None
        if entry is None:
            raise UndoExpired("the capture can no longer be put back")
        capture = entry[0]

        def edit(captures: list[Capture]) -> tuple[list[Capture] | None, Capture]:
            if any(other.id == capture.id for other in captures) or clash(capture, captures):
                raise CapturedAgain(f"the sentence has a {capture.type} again")
            if len(captures) >= MAX_CAPTURES:
                raise CaptureLimit(f"a document holds at most {MAX_CAPTURES} captures")
            return [*captures, capture], capture

        restored = self.change(work, document_id, edit)
        with self._guard:
            # only the entry this call put back: a removal of the same capture since (from
            # another window) keeps its own Undo
            kept = self._removed.get(str(work), {})
            if kept.get(capture_id) is entry:
                del kept[capture_id]
        return restored


def _check_text(kind: CaptureType, text: str) -> None:
    if kind is not CaptureType.NOTE:
        if text:
            raise TextRefused(f"a {kind} holds no text; only a note does")
        return
    if not text.strip():
        raise TextRefused("a note holds text; an empty note is removed instead")
    problem = text_problem(text)
    if problem:
        raise TextRefused(problem)


def _index(captures: list[Capture], capture_id: str) -> int:
    for at, capture in enumerate(captures):
        if capture.id == capture_id:
            return at
    raise CaptureMissing(f"no capture {capture_id}")
