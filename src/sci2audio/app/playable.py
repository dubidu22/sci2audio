"""The record of an audio job's playable chapters, `chapters.json` in the working folder
(#723, LW-01).

The audio job writes each chapter's files as soon as the chapter is spoken (output's
`BookWriter`). This record names every file the job put into the output folder, with its
size and SHA-256, before the file is put in place (output's `vouch`); so a killed job leaves
whole chapters the record names, and a rerun or resume can tell its own files from anyone
else's:

    {"format": "sci2audio-chapters", "version": 1, "complete": false,
     "settings": "<sha256>", "planned": [0, 2, 5],
     "chapters": [{"index": 0, "title": "…", "number": 1, "fingerprint": "<sha256>",
                   "files": [{"name": "<bare name>", "bytes": 123, "sha256": "…"}]}],
     "book": [{"name": "…", "bytes": 123, "sha256": "…"}],
     "pending": [{"name": "…", "bytes": 123, "sha256": "…"}]}

- `complete` is true once the job wrote its last file; a finished audiobook is replaced
  only with `overwrite`, as before (D-163).
- `settings` is a SHA-256 of what the person chose (voice, speeds, text and output
  settings, the book's details): a resume under other settings is refused without
  `overwrite`, so nothing is mixed silently.
- `planned` are the chapters the job is to speak (job chapter indices, in the job's order);
  `chapters` the chapters whose files are complete, each with output's
  `chapter_fingerprint`; `book` the read-along file, the M4B and the book's subtitles;
  `pending` the files of the chapter being written, put in place before it is complete.
- Names are bare, as in the job's other records (folders are machine-specific).
- Read strictly: missing, too large, a link, another format or version, or broken reads as
  no record.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path, PurePath
from typing import Any

from sci2audio.app.files import write_texts

RECORD = "chapters.json"
RECORD_FORMAT = "sci2audio-chapters"
RECORD_VERSION = 1
RECORD_LIMIT = 4 * 1024 * 1024  # bytes: thousands of chapters
_BLOCK = 1 << 20


@dataclass(frozen=True)
class RecordedFile:
    """A file the job put into the output folder: its bare name, size and SHA-256."""

    name: str
    bytes: int
    sha256: str

    def matches(self, folder: Path) -> bool:
        """True if `folder/name` is a regular file of this size and SHA-256."""
        path = folder / self.name
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size != self.bytes:
                return False
            return file_sha256(path) == self.sha256
        except OSError:
            return False


@dataclass(frozen=True)
class PlayableChapter:
    """A chapter whose files are complete: its job chapter index, title, number among the
    planned chapters (counted from 1, as in its file name), fingerprint and files."""

    index: int
    title: str
    number: int
    fingerprint: str
    files: tuple[RecordedFile, ...] = ()


@dataclass(frozen=True)
class ChapterRecord:
    complete: bool
    settings: str
    planned: tuple[int, ...]
    chapters: tuple[PlayableChapter, ...] = ()
    book: tuple[RecordedFile, ...] = ()
    # files of the chapter being written, put in place before the chapter is complete
    pending: tuple[RecordedFile, ...] = ()

    def owned(self, folder: Path) -> set[str]:
        """The names of the recorded files still in `folder` as the job wrote them."""
        files = [*self.book, *self.pending, *(f for c in self.chapters for f in c.files)]
        return {f.name for f in files if f.matches(folder)}

    def with_pending(self, file: RecordedFile) -> ChapterRecord:
        return replace(self, pending=_put(self.pending, file))

    def with_book_file(self, file: RecordedFile) -> ChapterRecord:
        """The record with `file` among the book's files, replacing one of the same name
        there or in `pending` (an unfinished run's file this run writes again)."""
        pending = tuple(f for f in self.pending if f.name != file.name)
        return replace(self, book=_put(self.book, file), pending=pending)

    def with_chapter(self, chapter: PlayableChapter) -> ChapterRecord:
        """The record with `chapter` complete (replacing an entry of the same index), in
        planned order; its files leave `pending`."""
        rest = [c for c in self.chapters if c.index != chapter.index]
        order = {index: n for n, index in enumerate(self.planned)}
        chapters = sorted([*rest, chapter], key=lambda c: order.get(c.index, len(order)))
        names = {f.name for f in chapter.files}
        pending = tuple(f for f in self.pending if f.name not in names)
        return replace(self, chapters=tuple(chapters), pending=pending)


def _put(files: tuple[RecordedFile, ...], file: RecordedFile) -> tuple[RecordedFile, ...]:
    return (*(f for f in files if f.name != file.name), file)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(_BLOCK):
            digest.update(block)
    return digest.hexdigest()


def settings_key(data: Any) -> str:
    """A SHA-256 of `data` (JSON), for the record's `settings`."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_record(work: Path) -> ChapterRecord | None:
    """The working folder's record, or None (see the module docstring)."""
    path = work / RECORD
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > RECORD_LIMIT:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return _from_data(data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return None


def write_record(work: Path, record: ChapterRecord) -> None:
    """Write the record atomically (raises OSError)."""
    text = json.dumps(_to_data(record), ensure_ascii=False, indent=2) + "\n"
    write_texts({work / RECORD: text}, overwrite=True)


def remove_record(work: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        (work / RECORD).unlink()


def playable_chapters(work: Path, out_folder: Path) -> tuple[PlayableChapter, ...]:
    """The recorded chapters whose files are all still in `out_folder` with their recorded
    size (cheap enough for a page to ask often; the job checks hashes before reusing)."""
    record = read_record(work)
    if record is None:
        return ()
    out = []
    for chapter in record.chapters:
        with contextlib.suppress(OSError):
            if chapter.files and all(
                (out_folder / f.name).is_file() and (out_folder / f.name).stat().st_size == f.bytes
                for f in chapter.files
            ):
                out.append(chapter)
    return tuple(out)


def _file_data(file: RecordedFile) -> dict[str, Any]:
    return {"name": file.name, "bytes": file.bytes, "sha256": file.sha256}


def _to_data(record: ChapterRecord) -> dict[str, Any]:
    return {
        "format": RECORD_FORMAT,
        "version": RECORD_VERSION,
        "complete": record.complete,
        "settings": record.settings,
        "planned": list(record.planned),
        "chapters": [
            {
                "index": c.index,
                "title": c.title,
                "number": c.number,
                "fingerprint": c.fingerprint,
                "files": [_file_data(f) for f in c.files],
            }
            for c in record.chapters
        ],
        "book": [_file_data(f) for f in record.book],
        "pending": [_file_data(f) for f in record.pending],
    }


def _file(data: dict[str, Any]) -> RecordedFile:
    name, size, sha = data["name"], data["bytes"], data["sha256"]
    if not (isinstance(name, str) and _bare(name)):
        raise ValueError(f"not a bare file name: {name!r}")
    if type(size) is not int or size < 0:
        raise ValueError(f"bad size {size!r}")
    if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
        raise ValueError(f"bad SHA-256 {sha!r}")
    return RecordedFile(name, size, sha)


def _bare(name: str) -> bool:
    return (
        bool(name)
        and name not in (".", "..")
        and PurePath(name).name == name
        and ("/" not in name and "\\" not in name)
    )


def _int(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"bad number {value!r}")
    return value


def _from_data(data: Any) -> ChapterRecord:
    if data.get("format") != RECORD_FORMAT or data.get("version") != RECORD_VERSION:
        raise ValueError("not a chapter record this version reads")
    complete, settings = data["complete"], data["settings"]
    if not isinstance(complete, bool) or not isinstance(settings, str):
        raise ValueError("bad record")
    chapters: list[PlayableChapter] = []
    for c in data["chapters"]:
        title, fingerprint = c["title"], c["fingerprint"]
        if not isinstance(title, str) or not isinstance(fingerprint, str):
            raise ValueError("bad chapter")
        chapters.append(
            PlayableChapter(
                _int(c["index"]),
                title,
                _int(c["number"]),
                fingerprint,
                tuple(_file(f) for f in c["files"]),
            )
        )
    return ChapterRecord(
        complete,
        settings,
        tuple(_int(i) for i in data["planned"]),
        tuple(chapters),
        tuple(_file(f) for f in data["book"]),
        tuple(_file(f) for f in data["pending"]),
    )
