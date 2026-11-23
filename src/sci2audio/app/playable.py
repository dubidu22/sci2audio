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
  `pending` the files vouched for before they are put in place: those of the chapter being
  written, and a new read-along file, M4B or subtitle file until the step that writes it
  is done. An entry of the same name elsewhere in the record, or earlier in `pending`, stays
  until then, as it still vouches for the file in place should the job stop before the
  rename.
- Names are bare, as in the job's other records (folders are machine-specific).
- Read strictly: missing, too large, a link, another format or version, or broken reads as
  no record.

Version 2 (#725, #726) adds, and version 1 records still read without them:

    "order": "book", "made": {<what `settings` hashes>},
    "chapters": [{…, "spoken": "<sha256 of spoken/<index>.json>"}],
    "built": [{"name": "…", "bytes": 123, "sha256": "…", "kind": "m4b",
               "chapters": ["<fingerprint>", …]}]

- `order` is "book" when chapters are numbered by their place among the book's chapters
  (D-903) and "chosen" when the person chose another order than printed (#119): such a
  book is never added to.
- `made` holds what `settings` is the hash of, so a job adding chapters can make them
  with the settings the others were made with (`keep_settings`).
- A chapter's `spoken` is the SHA-256 of its chunks' list in the working folder
  (`spoken/<index>.json`), from which the whole book is built without a new text run.
- `built` are the whole-book files built on request, with the fingerprints of the
  chapters they hold: a file whose chapters are still these is reused.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePath
from typing import Any

from sci2audio.app.chunks import CHUNKS
from sci2audio.app.files import write_texts
from sci2audio.core import AudioChunk, Span
from sci2audio.output import Pause, Spoken

RECORD = "chapters.json"
RECORD_FORMAT = "sci2audio-chapters"
RECORD_VERSION = 2
READ_VERSIONS = (1, 2)
RECORD_LIMIT = 4 * 1024 * 1024  # bytes: thousands of chapters
SPOKEN = "spoken"  # a chapter's chunks, `spoken/<index>.json` in the working folder
SPOKEN_FORMAT = "sci2audio-spoken"
SPOKEN_VERSION = 1
_CHUNK_FILE = re.compile(rf"{re.escape(CHUNKS)}/[0-9a-f]{{2}}/[0-9a-f]{{64}}\.wav")
_BLOCK = 1 << 20
_HEX = "0123456789abcdef"


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
    """A chapter whose files are complete: its job chapter index, title, number (counted
    from 1, as in its file name), fingerprint, files and the SHA-256 of its chunks' list
    (`spoken/<index>.json`, version 2)."""

    index: int
    title: str
    number: int
    fingerprint: str
    files: tuple[RecordedFile, ...] = ()
    spoken: str = ""


@dataclass(frozen=True)
class BuiltFile:
    """A whole-book file built on request (#725): the file, its kind and the fingerprints
    of the chapters it holds, in order."""

    file: RecordedFile
    kind: str
    chapters: tuple[str, ...]


@dataclass(frozen=True)
class ChapterRecord:
    complete: bool
    settings: str
    planned: tuple[int, ...]
    chapters: tuple[PlayableChapter, ...] = ()
    book: tuple[RecordedFile, ...] = ()
    # files vouched for before they are put in place, newest last (module docstring)
    pending: tuple[RecordedFile, ...] = ()
    order: str = "book"
    made: dict[str, Any] | None = None  # None in a version 1 record
    built: tuple[BuiltFile, ...] = ()
    version: int = RECORD_VERSION

    def with_built(self, built: BuiltFile) -> ChapterRecord:
        """The record once `built` is in place: it replaces an entry of the same name and
        leaves `pending`."""
        name = built.file.name
        rest = tuple(b for b in self.built if b.file.name != name)
        pending = tuple(f for f in self.pending if f.name != name)
        return replace(self, built=(*rest, built), pending=pending)

    def owned(self, folder: Path) -> set[str]:
        """The names of the recorded files still in `folder` as the job wrote them."""
        files = [
            *self.book,
            *self.pending,
            *(f for c in self.chapters for f in c.files),
            *(b.file for b in self.built),
        ]
        return {f.name for f in files if f.matches(folder)}

    def with_pending(self, file: RecordedFile) -> ChapterRecord:
        """The record vouching for `file` too; an entry of the same name stays, as the file
        in place may still be the one it names."""
        return replace(self, pending=(*(f for f in self.pending if f != file), file))

    def newest_pending(self) -> dict[str, RecordedFile]:
        """The newest `pending` entry of each name."""
        return {f.name: f for f in self.pending}

    def with_book_files(self, names: Collection[str]) -> ChapterRecord:
        """The record once the files `names` are in place: the newest `pending` entry of each
        becomes the book's entry of that name, and the older entries go."""
        newest = self.newest_pending()
        placed = [f for name, f in newest.items() if name in names]
        done = {f.name for f in placed}
        book = (*(f for f in self.book if f.name not in done), *placed)
        pending = tuple(f for f in self.pending if f.name not in done)
        return replace(self, book=book, pending=pending)

    def with_chapter(self, chapter: PlayableChapter) -> ChapterRecord:
        """The record with `chapter` complete (replacing an entry of the same index), in
        planned order; its files leave `pending`."""
        rest = [c for c in self.chapters if c.index != chapter.index]
        order = {index: n for n, index in enumerate(self.planned)}
        chapters = sorted([*rest, chapter], key=lambda c: order.get(c.index, len(order)))
        names = {f.name for f in chapter.files}
        pending = tuple(f for f in self.pending if f.name not in names)
        return replace(self, chapters=tuple(chapters), pending=pending)


@dataclass(frozen=True)
class ChapterState:
    """A chapter of the book that has something to say, and whether its files are made
    (#726; "being made" is the running job's to tell)."""

    index: int
    title: str
    generated: bool


def chapter_states(
    work: Path, out_folder: Path, chapters: Sequence[tuple[int, str]]
) -> tuple[ChapterState, ...]:
    """The state of each of `chapters` (index and title, in the book's order): generated
    when its recorded files are all still in `out_folder` (`playable_chapters`)."""
    made = {c.index for c in playable_chapters(work, out_folder)}
    return tuple(ChapterState(index, title, index in made) for index, title in chapters)


def spoken_path(work: Path, index: int) -> Path:
    return work / SPOKEN / f"{index}.json"


def spoken_text(spoken: Sequence[Spoken]) -> str:
    """The list of a chapter's chunks as `spoken/<index>.json` holds it."""
    data = {
        "format": SPOKEN_FORMAT,
        "version": SPOKEN_VERSION,
        "chunks": [
            [
                s.chunk.file,
                s.chunk.duration,
                [s.chunk.span.block, s.chunk.span.start, s.chunk.span.end],
                str(s.pause),
                s.text,
                s.continues,
            ]
            for s in spoken
        ],
    }
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def write_spoken(work: Path, index: int, spoken: Sequence[Spoken]) -> str:
    """Write chapter `index`'s chunk list atomically and return its SHA-256 (raises
    OSError)."""
    text = spoken_text(spoken)
    path = spoken_path(work, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_texts({path: text}, overwrite=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_spoken(work: Path, index: int, sha256: str) -> tuple[Spoken, ...] | None:
    """Chapter `index`'s chunks if its list is there with this SHA-256 and reads strictly,
    else None. A chunk file is always a name in the working folder's chunk cache."""
    path = spoken_path(work, index)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > RECORD_LIMIT:
            return None
        raw = path.read_bytes()
        if not sha256 or hashlib.sha256(raw).hexdigest() != sha256:
            return None
        data = json.loads(raw.decode("utf-8"))
        if data["format"] != SPOKEN_FORMAT or data["version"] != SPOKEN_VERSION:
            return None
        return tuple(_spoken(entry) for entry in data["chunks"]) or None
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return None


def _spoken(entry: Any) -> Spoken:
    file, duration, (block, start, end), pause, text, continues = entry
    if not (isinstance(file, str) and _CHUNK_FILE.fullmatch(file)):
        raise ValueError(f"not a chunk file: {file!r}")
    if type(duration) not in (int, float) or not duration >= 0:
        raise ValueError(f"bad duration {duration!r}")
    if not isinstance(text, str) or not isinstance(continues, bool):
        raise ValueError("bad chunk")
    span = Span(_int(block), _int(start), _int(end))
    return Spoken(AudioChunk(span, file, float(duration)), Pause(pause), text, continues)


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
                "spoken": c.spoken,
            }
            for c in record.chapters
        ],
        "book": [_file_data(f) for f in record.book],
        "pending": [_file_data(f) for f in record.pending],
        "order": record.order,
        "made": record.made,
        "built": [
            {**_file_data(b.file), "kind": b.kind, "chapters": list(b.chapters)}
            for b in record.built
        ],
    }


def _file(data: dict[str, Any]) -> RecordedFile:
    name, size, sha = data["name"], data["bytes"], data["sha256"]
    if not (isinstance(name, str) and _bare(name)):
        raise ValueError(f"not a bare file name: {name!r}")
    if type(size) is not int or size < 0:
        raise ValueError(f"bad size {size!r}")
    return RecordedFile(name, size, _sha(sha))


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


def _sha(value: Any) -> str:
    if not (isinstance(value, str) and len(value) == 64 and set(value) <= set(_HEX)):
        raise ValueError(f"bad SHA-256 {value!r}")
    return value


def _from_data(data: Any) -> ChapterRecord:
    version = data.get("version")
    if data.get("format") != RECORD_FORMAT or version not in READ_VERSIONS:
        raise ValueError("not a chapter record this version reads")
    complete, settings = data["complete"], data["settings"]
    if not isinstance(complete, bool) or not isinstance(settings, str):
        raise ValueError("bad record")
    chapters: list[PlayableChapter] = []
    for c in data["chapters"]:
        title, fingerprint = c["title"], c["fingerprint"]
        if not isinstance(title, str) or not isinstance(fingerprint, str):
            raise ValueError("bad chapter")
        spoken = c["spoken"] if version >= 2 and c["spoken"] else ""
        chapters.append(
            PlayableChapter(
                _int(c["index"]),
                title,
                _int(c["number"]),
                fingerprint,
                tuple(_file(f) for f in c["files"]),
                _sha(spoken) if spoken else "",
            )
        )
    record = ChapterRecord(
        complete,
        settings,
        tuple(_int(i) for i in data["planned"]),
        tuple(chapters),
        tuple(_file(f) for f in data["book"]),
        tuple(_file(f) for f in data["pending"]),
        version=version,
    )
    if version == 1:
        return record
    order, made = data["order"], data["made"]
    if order not in ("book", "chosen") or not (made is None or isinstance(made, dict)):
        raise ValueError("bad record")
    built = []
    for b in data["built"]:
        kind, held = b["kind"], b["chapters"]
        if not isinstance(kind, str) or not isinstance(held, list):
            raise ValueError("bad built file")
        built.append(BuiltFile(_file(b), kind, tuple(_sha(f) for f in held)))
    return replace(record, order=order, made=made, built=tuple(built))
