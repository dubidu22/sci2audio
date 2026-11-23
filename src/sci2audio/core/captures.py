"""Captures of the study layer (ADR-008, D-850, D-854): a mark, a note or a quote set at
a sentence while listening, and the JSON form of a document's `captures.json`.

A capture is tied to the text, never to one audiobook: its anchor is the sentence's
block, its character offsets in that block's text and the sentence as printed, never its
spoken form (D-57). No time is stored; whoever shows a capture finds its sentence again
in the audiobook at hand. The stored anchor is never rewritten.

This module holds the data objects and their JSON form as pure functions to and from a
dict, with the format checks. Reading and writing the file is the app's (`app.captures`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

CAPTURES_FORMAT = "sci2audio-captures"
CAPTURES_VERSION = 1
MIGRATED_FROM = ("markers.json",)  # the files a captures file may say it was made from (#475)
MAX_CAPTURES = 6000  # room for the 2000 markers of v1.3 and three types
TEXT_LIMIT = 4000  # characters in a note, as the v1.3 marker's note
TIME_LIMIT = 40  # characters in `created` and `changed`, as the v1.3 marker
ID_LENGTH = 16  # hex digits, as the v1.3 marker

_HEX = frozenset("0123456789abcdef")
_FILE_KEYS = frozenset({"format", "version", "document", "captures"})
_OPTIONAL_FILE_KEYS = frozenset({"migrated_from"})
_CAPTURE_KEYS = frozenset({"id", "type", "created", "changed", "anchor", "text"})
_ANCHOR_KEYS = frozenset({"block", "start", "end", "text"})


class CaptureFormatError(ValueError):
    """Data that is not a captures file this version can read, with the reason."""


class CaptureType(StrEnum):
    """What a capture is; the keys are M, N and Q (ADR-008 2.1 item 1, 2.2 B)."""

    MARK = "mark"
    NOTE = "note"
    QUOTE = "quote"


@dataclass(frozen=True)
class Anchor:
    """A sentence in the document's text: block, character offsets in that block's text,
    and the sentence as printed (D-57)."""

    block: int
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        if self.block < 0 or self.start < 0 or self.end < self.start:
            raise CaptureFormatError(
                f"an anchor needs block >= 0 and 0 <= start <= end, got {self.block}, "
                f"{self.start}, {self.end}"
            )
        if not self.text:
            raise CaptureFormatError("an anchor holds the sentence's text")


@dataclass(frozen=True)
class Capture:
    """One capture. `text` is the note's text, empty for a mark and a quote; `created`
    and `changed` are UTC times as `2026-11-20T19:04:00Z`."""

    id: str
    type: CaptureType
    created: str
    changed: str
    anchor: Anchor
    text: str = ""

    def __post_init__(self) -> None:
        if len(self.id) != ID_LENGTH or not set(self.id) <= _HEX:
            raise CaptureFormatError(f"a capture's id is {ID_LENGTH} hex digits, not {self.id!r}")
        if not isinstance(self.type, CaptureType):
            raise CaptureFormatError(f"a capture's type is mark, note or quote, not {self.type!r}")
        if len(self.created) > TIME_LIMIT or len(self.changed) > TIME_LIMIT:
            raise CaptureFormatError(f"a capture's times are at most {TIME_LIMIT} characters")
        problem = text_problem(self.text)
        if problem:
            raise CaptureFormatError(problem)
        if self.text and self.type is not CaptureType.NOTE:
            raise CaptureFormatError(f"a {self.type} holds no text; only a note does")


@dataclass(frozen=True)
class CaptureFile:
    """The captures of one document, in the file's order: the content of its
    `captures.json`. `migrated_from` names the file they were carried over from (#475)."""

    document: str
    captures: tuple[Capture, ...] = field(default=())
    migrated_from: str | None = None

    def __post_init__(self) -> None:
        if not self.document:
            raise CaptureFormatError("a captures file names its document")
        if len(self.captures) > MAX_CAPTURES:
            raise CaptureFormatError(f"a document holds at most {MAX_CAPTURES} captures")
        if len({capture.id for capture in self.captures}) != len(self.captures):
            raise CaptureFormatError("one capture id is used twice")
        if self.migrated_from is not None and self.migrated_from not in MIGRATED_FROM:
            raise CaptureFormatError(f"captures are not carried over from {self.migrated_from!r}")

    def count(self) -> dict[CaptureType, int]:
        """How many captures of each type, every type named."""
        counts = dict.fromkeys(CaptureType, 0)
        for capture in self.captures:
            counts[capture.type] += 1
        return counts


def text_problem(text: str) -> str | None:
    """Why a note's text can't be kept, or None."""
    if len(text) > TEXT_LIMIT:
        return f"a note holds at most {TEXT_LIMIT} characters"
    if "\x00" in text:
        return "a note can't hold a NUL character"
    return None


# ---- the JSON form ---------------------------------------------------------------------------


def captures_to_data(captures: CaptureFile) -> dict[str, Any]:
    """The plain data of a captures file, keys in a fixed order (`json.dumps` it as is)."""
    data: dict[str, Any] = {
        "format": CAPTURES_FORMAT,
        "version": CAPTURES_VERSION,
        "document": captures.document,
    }
    if captures.migrated_from is not None:
        data["migrated_from"] = captures.migrated_from
    data["captures"] = [_capture_data(capture) for capture in captures.captures]
    return data


def _capture_data(capture: Capture) -> dict[str, Any]:
    a = capture.anchor
    return {
        "id": capture.id,
        "type": capture.type.value,
        "created": capture.created,
        "changed": capture.changed,
        "anchor": {"block": a.block, "start": a.start, "end": a.end, "text": a.text},
        "text": capture.text,
    }


def captures_from_data(data: object) -> CaptureFile:
    """The captures file `data` holds (as `json.loads` gives it). Raises CaptureFormatError,
    saying why, for anything this version can't read: another format or version, a key too
    many or too few, a value of the wrong kind or out of range."""
    if not isinstance(data, dict):
        raise CaptureFormatError("a captures file is a JSON object")
    keys = set(data)
    if _FILE_KEYS - keys or keys - _FILE_KEYS - _OPTIONAL_FILE_KEYS:
        raise CaptureFormatError(
            "a captures file has format, version, document, captures and maybe migrated_from"
        )
    if data["format"] != CAPTURES_FORMAT:
        raise CaptureFormatError(f"not a {CAPTURES_FORMAT} file")
    if type(data["version"]) is not int or data["version"] != CAPTURES_VERSION:
        raise CaptureFormatError(f"version {data['version']!r}; this version reads 1")
    document, entries = data["document"], data["captures"]
    migrated = data.get("migrated_from")
    if not isinstance(document, str):
        raise CaptureFormatError("the document is named by a text")
    if "migrated_from" in data and not isinstance(migrated, str):
        raise CaptureFormatError("migrated_from is a file name")
    if not isinstance(entries, list):
        raise CaptureFormatError("the captures are a list")
    if len(entries) > MAX_CAPTURES:
        raise CaptureFormatError(f"a document holds at most {MAX_CAPTURES} captures")
    return CaptureFile(document, tuple(_capture(entry) for entry in entries), migrated)


def _capture(data: object) -> Capture:
    if not isinstance(data, dict) or set(data) != _CAPTURE_KEYS:
        raise CaptureFormatError("a capture has id, type, created, changed, anchor and text")
    texts = (data["id"], data["type"], data["created"], data["changed"], data["text"])
    if not all(isinstance(value, str) for value in texts):
        raise CaptureFormatError("a capture's id, type, times and text are texts")
    try:
        kind = CaptureType(data["type"])
    except ValueError:
        raise CaptureFormatError(
            f"a capture's type is mark, note or quote, not {data['type']!r}"
        ) from None
    return Capture(
        data["id"], kind, data["created"], data["changed"], _anchor(data["anchor"]), data["text"]
    )


def _anchor(data: object) -> Anchor:
    if not isinstance(data, dict) or set(data) != _ANCHOR_KEYS:
        raise CaptureFormatError("an anchor has block, start, end and text")
    numbers = (data["block"], data["start"], data["end"])
    if not all(type(value) is int for value in numbers) or not isinstance(data["text"], str):
        raise CaptureFormatError("an anchor's block and offsets are whole numbers, its text a text")
    return Anchor(data["block"], data["start"], data["end"], data["text"])
