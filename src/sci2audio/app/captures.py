"""A document's captures on disk: `captures.json` in its working folder (ADR-008 2.1 item
4, 2.3, #396).

Reading never changes anything. Writing puts the whole file in place atomically
(`files.write_texts`) and touches no other file. A file this version can't read (a link,
not a plain file, too large, not UTF-8 or JSON, another format, version or document) is
never written, renamed or removed: `write_captures` refuses it, and capturing stays off
for that document until the person fixes or removes the file. Once written, the file
stays, also when it holds no capture any more.

Only the interface's server writes the file, with one read, one change and one write per
change under its own lock (#397). The job runner, the audio job and the command line
never read or write it. The carry-over of the v1.3 markers is #475.
"""

from __future__ import annotations

import json
from pathlib import Path

from sci2audio.app.files import write_texts
from sci2audio.core import CaptureFile, CaptureFormatError, captures_from_data, captures_to_data

CAPTURES = "captures.json"
FILE_LIMIT = 6_000_000  # bytes: room for every readable v1.3 markers file (2 MB) carried over


class CapturesBroken(Exception):
    """The file is there but this version can't read it; it is left as it is."""


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
    another document, ValueError if the file would be larger than its limit, OSError if
    writing fails (the old file stays)."""
    read_captures(work, captures.document)  # never write over a file this version can't read
    text = captures_text(captures)
    if len(text.encode("utf-8")) > FILE_LIMIT:
        raise ValueError(f"the captures file would be larger than {FILE_LIMIT} bytes")
    write_texts({captures_path(work): text}, overwrite=True)


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
