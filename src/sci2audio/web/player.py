"""The read-along player's data (#78, OU-02, D-294 to D-303): what the listen page shows.

Three files tell the player everything (D-165, D-102): the audio job's `document.json`
(the laid-out document whose block text the read-along points at) and `audio.json` in the
document's working folder, and the read-along file in the output folder next to the
audio. The app's records keep no folders (they are machine-specific), so the web's audio
task writes its own small record, `audiobook.json`, with the output folder (D-295).

Nothing in these files is trusted as a path (D-295, D-192 to D-209): the record must name
this document and an absolute folder; the folder is only ever the recorded one, one of the
project's own audiobook folders (`project.json`, D-749), the saved output folder or the
server's default (earlier audiobooks sit flat there); file names must be bare names listed
in `audio.json`; a file is opened only as `<folder>/<name>` and must be a regular file in
that very folder; and the read-along file must agree with `audio.json` (duration and
chunk count) before any of its files is served or shown. The page also checks that every
span lies inside its block: a wrong highlight is worse than none.

The page itself (D-297): the blocks of the chapters in the audiobook, in reading order,
without furniture, with a marker where a new printed page starts; every chunk with a
non-empty span is one element around exactly its characters; a placeholder whose notice
was read is a notice box (D-299). A chunk whose span holds nothing to speak (a lone "-" of
an audiobook made before #652) is drawn as an empty span is: it gets no element of its own.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import statistics
import threading
import time
import unicodedata
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Any

from sci2audio import __version__
from sci2audio.app import find_chapters
from sci2audio.app.chapters import Chapter
from sci2audio.app.files import write_texts
from sci2audio.app.playable import RECORD as CHAPTER_RECORD
from sci2audio.app.playable import ChapterRecord, read_record
from sci2audio.app.report import Pages
from sci2audio.core import Block, BlockKind, Document, Edit, EditKind, Section, SpanError, TextLine
from sci2audio.core.export import from_data
from sci2audio.output import ReadAlong, ReadAlongError, read_readalong
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    CodeNoticeStep,
    FormulaNoticeStep,
    LineEndHyphenStep,
    Status,
    StepContext,
    StepRun,
    TableFigureNoticeStep,
    TextStep,
    run_steps,
    unspoken,
)
from sci2audio.web.figures import Catalog, Shown
from sci2audio.web.project import read_project

RECORD = "audiobook.json"  # the web's own record of where the audiobook went (D-295)
RECORD_FORMAT = "sci2audio-web-audiobook"
RECORD_VERSION = 1
AUDIO_RECORD = "audio.json"  # the audio job's records (D-165)
DOCUMENT_RECORD = "document.json"
TIME_TOLERANCE = 0.0015  # seconds: both files round to 1 ms
# seconds a browser can play past a chapter's end: one that keeps the padding of the file's
# last frame (Chromium on our MP3s, #779) plays up to a frame longer than the read-along
# says. An MP3 frame is at most 1152 samples, an AAC frame 1024: 48 ms at 24 kHz.
OVERRUN = 0.1
POSITION = "position.json"  # where the person stopped listening (#153)
POSITION_FORMAT = "sci2audio-web-position"
POSITION_VERSION = 1
POSITION_LIMIT = 4096  # bytes: a record is about 150; a larger file is not ours


class PlayerError(Exception):
    """Why the player can't show this audiobook: `key` names the text in the strings
    table, `values` fill it in."""

    def __init__(self, key: str, **values: Any) -> None:
        super().__init__(key)
        self.key = key
        self.values = values


# ---- the web's record (D-295) -----------------------------------------------------------


@dataclass(frozen=True)
class Made:
    """What the web's audio job makes the audiobook with, as `audio.json` will say once it
    is done (#724): the voice, the categories switched off, the plugin steps it runs and
    the sci2audio version. The Listen page draws a book that is still growing with them."""

    voice: str
    switched_off: frozenset[str]
    plugins: frozenset[str]
    version: str


def write_record(work: Path, document_id: str, folder: Path, made: Made | None = None) -> None:
    """Note where the audio job of `document_id` writes its audiobook and, while it runs,
    what it makes it with (`made`, an optional key older versions ignore). Raises OSError."""
    data: dict[str, Any] = {
        "format": RECORD_FORMAT,
        "version": RECORD_VERSION,
        "document": document_id,
        "folder": str(folder.absolute()),
    }
    if made is not None:
        data["made"] = {
            "voice": made.voice,
            "switched_off": sorted(made.switched_off),
            "plugins": sorted(made.plugins),
            "sci2audio": made.version,
        }
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    write_texts({work / RECORD: text}, overwrite=True)


def recorded_made(work: Path, document_id: str) -> Made | None:
    """What the record says the audio job makes the audiobook with, or None: no record, not
    ours, or no readable `made` (`recorded_folder` checks the rest)."""
    if recorded_folder(work, document_id) is None:
        return None
    try:
        made = json.loads((work / RECORD).read_text(encoding="utf-8"))["made"]
        voice, version = made["voice"], made["sci2audio"]
        switched_off, plugins = made["switched_off"], made["plugins"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None
    if not (
        isinstance(voice, str)
        and isinstance(version, str)
        and isinstance(switched_off, list)
        and isinstance(plugins, list)
        and all(isinstance(c, str) for c in (*switched_off, *plugins))
    ):
        return None
    return Made(voice, frozenset(switched_off), frozenset(plugins), version)


def recorded_folder(work: Path, document_id: str) -> Path | None:
    """The folder the record names, if the record is ours, for this document, and the
    folder an absolute path; else None."""
    try:
        data = json.loads((work / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # deep nesting: every page reads it (#389)
        return None
    if not isinstance(data, dict):
        return None
    folder = data.get("folder")
    if (
        data.get("format") != RECORD_FORMAT
        or data.get("version") != RECORD_VERSION
        or data.get("document") != document_id
        or not isinstance(folder, str)
        or "\x00" in folder
    ):
        return None
    path = Path(folder)
    return path if path.is_absolute() else None


# ---- the listening position (#153) -----------------------------------------------------
#
# The server picks a new port on every run, so the browser's storage, kept per origin,
# forgets where a person stopped. The position is kept in the document's working folder
# instead, next to `audiobook.json`, stamped with the hash of the read-along file it is a
# time in: a new audiobook (a rerun, from the web or the command line) has a new file, so
# an old position no longer fits and is dropped. A record that does not fit is ignored,
# never an error.


@dataclass(frozen=True)
class Position:
    """Chapter `chapter` of the audiobook (as the read-along file counts them) and `time`
    in seconds on the book's timeline. A book that grows by chapters added later (#726)
    also keeps the chapter's index in the document and the time inside it (`within`): a
    chapter added before it moves its place and its book time, not these (D-909)."""

    chapter: int
    time: float
    index: int | None = None
    within: float | None = None


def audiobook_stamp(readalong: Path) -> str:
    """The first 16 hex digits of the read-along file's SHA-256. Raises OSError. Kept
    while the file's identity, time and size stay: the audio job replaces the file whole
    (`write_texts`), which gives it a new identity even where two writes get the same
    time (Windows' clock ticks in milliseconds); a file changed in the last two seconds
    is read each time (`file_version`)."""
    version = file_version(readalong)
    if version is None:  # too fresh to tell apart: read it
        return _hash16(readalong)
    return _stamp(str(readalong), version)


@lru_cache(maxsize=256)  # the shelf asks for every audiobook's stamp on every page
def _stamp(path: str, version: tuple[int, int, int]) -> str:
    return _hash16(Path(path))


def _hash16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@dataclass(frozen=True)
class Bounds:
    """Where a listening position can be in an audiobook: its chapters' starts, its length,
    and when its first and last sentences end (None: it has none). The few numbers of the
    read-along file that the Listen page and the rail's shelf (#389) both check against."""

    starts: tuple[float, ...]
    duration: float
    spoken: tuple[float, float] | None

    @classmethod
    def of(cls, readalong: ReadAlong) -> Bounds:
        chunks = readalong.chunks
        return cls(
            tuple(c.start for c in readalong.chapters),
            readalong.duration,
            (chunks[0].end, chunks[-1].end) if chunks else None,
        )

    def fits(self, position: Position) -> bool:
        """True if the position is a time of this audiobook inside the chapter it names."""
        starts = self.starts
        if not 0 <= position.chapter < len(starts) or not math.isfinite(position.time):
            return False
        start = starts[position.chapter]
        if position.chapter + 1 < len(starts):
            return start <= position.time < starts[position.chapter + 1]
        return start <= position.time <= self.duration + TIME_TOLERANCE

    def settled(self, position: Position) -> Position:
        """The position a player keeps at the end of a chapter's file, moved onto the
        book (#779): a time up to OVERRUN past the last chapter's end is the book's end,
        one past any other chapter's end the start of the next chapter. Any other position
        is returned as it is."""
        starts = self.starts
        chapter, time = position.chapter, position.time
        if not 0 <= chapter < len(starts) or not math.isfinite(time):
            return position
        if chapter + 1 == len(starts):
            if self.duration < time <= self.duration + OVERRUN:
                return Position(chapter, self.duration)
        elif starts[chapter + 1] <= time <= starts[chapter + 1] + OVERRUN:
            return Position(chapter + 1, starts[chapter + 1])
        return position

    def continues(self, position: Position) -> bool:
        """True if the position fits and something is left to continue: it is after the
        first sentence ended and before the last one ended."""
        if self.spoken is None or not self.fits(position):
            return False
        first, last = self.spoken
        return first <= position.time < last


def audiobook_bounds(readalong: Path) -> Bounds:
    """The bounds of the read-along file at this path, read once per version of the file
    (kept as `audiobook_stamp` keeps its stamp) and kept small, so the shelf on every page
    costs no parse. Raises OSError or ReadAlongError."""
    version = file_version(readalong)
    if version is None:  # too fresh to tell apart: read it
        return Bounds.of(read_readalong(readalong))
    return _bounds(str(readalong), version)


# A file changed less than this long ago is read again on every call: a rewrite in place
# within the file system's clock tick (about 16 ms on Windows) keeps its time and size, so
# they cannot tell the two versions apart yet (as git treats "racy" files; #403).
RACY_NS = 2_000_000_000


def file_version(path: Path) -> tuple[int, int, int] | None:
    """What the caches of this module key a file's contents on: its identity, time and
    size. The audio job replaces a file whole (`write_texts`), so a new file gets a new
    identity even where two writes get the same time and size (#407). None for a file
    changed in the last RACY_NS, which the caller reads afresh. Raises OSError."""
    stat = path.stat()
    if time.time_ns() - stat.st_mtime_ns < RACY_NS:
        return None
    return (stat.st_ino, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=256)
def _bounds(path: str, version: tuple[int, int, int]) -> Bounds:
    return Bounds.of(read_readalong(Path(path)))


def write_position(work: Path, document_id: str, stamp: str, position: Position) -> None:
    """Keep where the person stopped (atomically: a failed write leaves the old record).
    Every write has its own temporary name (#778), so saves at once both succeed and the
    later rename wins; the server saves through `PositionSaves`. Raises OSError."""
    data: dict[str, Any] = {
        "format": POSITION_FORMAT,
        "version": POSITION_VERSION,
        "document": document_id,
        "audiobook": stamp,
        "chapter": position.chapter,
        "time": position.time,
    }
    if position.index is not None and position.within is not None:
        data.update(index=position.index, within=position.within)
    write_texts({work / POSITION: json.dumps(data) + "\n"}, overwrite=True)


@dataclass
class PositionSaves:
    """The turns of one server run's writes of a listening position (#790): the player's
    saves and the audio job's read-then-write of the kept position (`change`) hold one
    lock, so a save that lands while the job rewrites the record is not overwritten by the
    older place the job read. Each write has its own temporary name (#778), so the lock
    guards only the read-then-write, not a rename. A save is about 150 bytes: the wait is
    short."""

    lock: threading.Lock = field(default_factory=threading.Lock)

    def save(self, work: Path, document_id: str, stamp: str, position: Position) -> None:
        """`write_position` in turn. Raises OSError."""
        with self.lock:
            write_position(work, document_id, stamp, position)

    def change(
        self,
        work: Path,
        document_id: str,
        stamp: str,
        change: Callable[[Position], Position | None],
    ) -> None:
        """Read the position recorded for this audiobook and write what `change` makes of
        it, in one turn; nothing is written for no record or a `change` that gives None.
        Raises OSError."""
        with self.lock:
            position = recorded_position(work, document_id, stamp)
            if position is None:
                return
            changed = change(position)
            if changed is not None:
                write_position(work, document_id, stamp, changed)

    def forget_unless(self, work: Path, document_id: str, stamp: str) -> None:
        """Remove the position unless it is recorded for the audiobook `stamp` (none for
        "") - the read and the removal in one turn (#839), so a save that lands between
        them is written after the removal, not removed with it. Raises OSError."""
        with self.lock:
            if not stamp or recorded_position(work, document_id, stamp) is None:
                remove_position(work)


def remove_position(work: Path) -> None:
    """Forget the position (a new audiobook was made). Raises OSError."""
    (work / POSITION).unlink(missing_ok=True)


def read_position(
    work: Path, document_id: str, stamp: str, readalong: ReadAlong
) -> Position | None:
    """Where the person stopped in this audiobook, worth offering to continue from; None
    if there is no such record, it does not fit, or nothing is left to continue: before the
    first sentence ended or after the last one ended."""
    bounds = Bounds.of(readalong)
    position = placed_position(work, document_id, stamp, bounds)
    if position is None or not bounds.continues(position):
        return None
    return position


def placed_position(work: Path, document_id: str, stamp: str, bounds: Bounds) -> Position | None:
    """The kept position (`recorded_position`) where its chapter is in the book now: a
    chapter added before it since it was kept moved that chapter (#726, D-909)."""
    position = recorded_position(work, document_id, stamp)
    if position is None or position.index is None or position.within is None:
        return position
    place = chapter_place(work, position.index)
    if place is None or place >= len(bounds.starts):
        return position
    return replace(position, chapter=place, time=bounds.starts[place] + position.within)


def recorded_position(work: Path, document_id: str, stamp: str) -> Position | None:
    """The position the record keeps for this audiobook (`stamp`) of this document, read
    without the read-along file: None for no record, a record of something else, or one
    that is not ours. A record kept before #726 with the book's stamp of then
    (`legacy_book_key`) is this book's too (D-909). `read_position` checks it against the
    audiobook as well; the library and the rail's shelf (#389) take it with only the
    audiobook's length."""
    path = work / POSITION
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > POSITION_LIMIT:
            return None
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=_no_constant)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    chapter, time = data.get("chapter"), data.get("time")
    if (
        data.get("format") != POSITION_FORMAT
        or data.get("version") != POSITION_VERSION
        or data.get("document") != document_id
        or data.get("audiobook") not in _stamps(work, stamp)
        or not isinstance(chapter, int)
        or isinstance(chapter, bool)
        or not isinstance(time, int | float)
        or isinstance(time, bool)
        or not math.isfinite(time)
    ):
        return None
    index, within = data.get("index"), data.get("within")
    if (
        isinstance(index, int)
        and not isinstance(index, bool)
        and index >= 0
        and isinstance(within, int | float)
        and not isinstance(within, bool)
        and math.isfinite(within)
        and within >= 0
    ):
        return Position(chapter, float(time), index, float(within))
    return Position(chapter, float(time))


def _stamps(work: Path, stamp: str) -> tuple[str, ...]:
    """`stamp`, and the book's stamp before #726 when `stamp` is its book's key."""
    record = _chapter_record(work)
    if record is not None and stamp and book_key(record) == stamp:
        return (stamp, legacy_book_key(record))
    return (stamp,)


def _no_constant(name: str) -> None:
    raise ValueError(f"{name} is not a time")


# ---- the audio job's record --------------------------------------------------------------


@dataclass(frozen=True)
class AudioRecord:
    """What the player needs from `audio.json`."""

    voice: str
    switched_off: frozenset[str]
    duration: float
    chunks: int  # chunks in the read-along file: the total less the skipped ones
    m4b: str | None
    mp3s: tuple[str, ...]
    readalong: str
    made_with: str = ""  # the sci2audio version that made it ("" if the record has none)
    # the ids of the text-step plugins that made it (#669); a record without the list was
    # made with none, as every released one (D-852)
    plugins: frozenset[str] = frozenset()

    @property
    def names(self) -> frozenset[str]:
        return frozenset(n for n in (self.m4b, *self.mp3s, self.readalong) if n is not None)


def bare_name(name: object) -> bool:
    """True for a plain file name: no folder part, not `.` or `..`, no NUL or drive."""
    if not isinstance(name, str) or not name or name in (".", ".."):
        return False
    if any(c in name for c in "/\\\x00:"):
        return False
    return PurePath(name).name == name


def read_audio_record(work: Path, document_id: str) -> AudioRecord:
    """The audio job's record, checked; PlayerError("listen.no_audiobook") if there is none."""
    try:
        text = (work / AUDIO_RECORD).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PlayerError("listen.no_audiobook") from None
    except OSError:
        raise PlayerError("listen.broken") from None
    try:
        data = json.loads(text)
        if data["format"] != "sci2audio-audio" or data["version"] != 1:
            raise PlayerError("listen.broken")
        # the document id is the first 16 hex digits of its SHA-256 (D-198)
        if str(data["source"]["sha256"])[:16] != document_id:
            raise PlayerError("listen.broken")
        files = data["files"]
        record = AudioRecord(
            voice=str(data["voice"]),
            switched_off=frozenset(str(c) for c in data["settings"]["switched_off"]),
            duration=float(data["duration"]),
            chunks=int(data["chunks"]["total"]) - int(data["chunks"]["skipped"]),
            m4b=files["m4b"],
            mp3s=tuple(files["mp3"]),
            readalong=files["readalong"],
            made_with=str(data.get("sci2audio", "")),
            plugins=frozenset(str(plugin["step"]) for plugin in data.get("plugins", ())),
        )
    except PlayerError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise PlayerError("listen.broken") from None
    if not all(bare_name(n) for n in (*record.mp3s, record.readalong)) or not (
        record.m4b is None or bare_name(record.m4b)
    ):
        raise PlayerError("listen.broken")
    if not math.isfinite(record.duration):
        raise PlayerError("listen.broken")
    return record


# ---- finding the files -------------------------------------------------------------------


def in_folder(folder: Path, name: str) -> Path | None:
    """`<folder>/<name>` if `name` is a bare name and that is a regular file whose real
    location is in the folder itself (no link out of it); else None."""
    if not bare_name(name):
        return None
    path = folder / name
    try:
        real = path.resolve(strict=True)
        if real.parent != folder.resolve(strict=True) or not real.is_file():
            return None
    except (OSError, RuntimeError):
        return None
    return path


@lru_cache(maxsize=8)
def _readalong(path: str, version: tuple[int, int, int]) -> ReadAlong:
    return read_readalong(Path(path))


def load_readalong(path: Path) -> ReadAlong:
    """The read-along file, read once per version of it on disk (`file_version`; the audio
    route asks on every range request). Raises ReadAlongError or OSError."""
    version = file_version(path)
    if version is None:  # too fresh to tell apart: read it
        return read_readalong(path)
    return _readalong(str(path), version)


@dataclass(frozen=True)
class Located:
    folder: Path
    readalong: ReadAlong
    name: str = ""  # the read-along file's name in the folder
    key: str = ""  # the book's stamp from its chapter record (`book_key`), if it has one

    @property
    def stamp(self) -> str:
        """The audiobook's stamp for the listening position (#153): the book's key when its
        chapter record names this read-along file (#724), else the file's hash. Raises
        OSError."""
        return self.key or audiobook_stamp(self.folder / self.name)


def locate(record: AudioRecord, folders: Iterable[Path | None]) -> Located:
    """The first of `folders` holding this audiobook: its read-along file agrees with
    `audio.json` and every audio file it names is there. PlayerError otherwise: the files
    are missing, or a folder holds another audiobook's files under these names."""
    first: Path | None = None
    changed = False
    for folder in dict.fromkeys(f for f in folders if f is not None and f.is_absolute()):
        first = first or folder
        path = in_folder(folder, record.readalong)
        if path is None:
            continue
        try:
            data = load_readalong(path)
        except (OSError, ReadAlongError):
            changed = True
            continue
        if not _agrees(record, data):
            changed = True
            continue
        if any(in_folder(folder, name) is None for name in record.names):
            continue
        return Located(folder, data, record.readalong)
    if changed:
        raise PlayerError("listen.changed", folder=str(first or ""))
    raise PlayerError("listen.missing", folder=str(first or ""))


def _agrees(record: AudioRecord, data: ReadAlong) -> bool:
    mp3s = tuple(c.mp3 for c in data.chapters if c.mp3 is not None)
    return (
        abs(data.duration - record.duration) <= TIME_TOLERANCE
        and len(data.chunks) == record.chunks
        and data.m4b == record.m4b
        and mp3s == record.mp3s
        and bool(data.chunks)
    )


def candidate_folders(
    work: Path, document_id: str, saved: Path | None, default: Path
) -> list[Path | None]:
    """Where the audiobook may be, in order (D-295, D-749): the recorded one, the project's
    own audiobook folders (newest first), then the saved and the default output folder,
    which hold the audiobooks made before #469."""
    project = read_project(work, document_id)
    own = [] if project is None else list(reversed(project.folders()))
    return [recorded_folder(work, document_id), *own, saved, default]


# ---- a book that grows (#724, LW-02) --------------------------------------------------
#
# The audio job makes each chapter playable as soon as it is spoken (#723): its MP3 is in
# the output folder, the read-along file is written whole with it, and `chapters.json` in the
# working folder names every file with its size and SHA-256. `audio.json` comes only at the
# end. Until then the page draws the chapters the chapter record names, trusting nothing
# the record does not vouch for: the read-along file must be the one it names (size and
# SHA-256), list exactly its chapters' MP3s, and every MP3 must be there at its recorded
# size. The voice and the switched-off categories come from the web's own record (`Made`).
#
# Its timeline only grows: a chapter is added at the end, the ones before keep their
# times. So the stamp a listening position is kept with is the book's own key, the same
# while it grows and once it is done, not the read-along file's hash.


READALONG_SUFFIX = ".readalong.json"


def book_key(record: ChapterRecord) -> str:
    """The stamp of the book the chapter record describes: its settings. The same while the
    book grows, once it is done and when chapters are added later (#726, the settings key
    holds no chapter choice); another for any other settings."""
    data = json.dumps([record.settings], separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def legacy_book_key(record: ChapterRecord) -> str:
    """The book's stamp before #726, of its settings and its planned chapters: a position
    kept with it is still the book's (D-909)."""
    data = json.dumps([record.settings, list(record.planned)], separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Planned:
    """A chapter the audio job was asked to speak: its index in the document, its title,
    and its place in the read-along file once it is playable (else None)."""

    index: int
    title: str
    chapter: int | None


@dataclass(frozen=True)
class Current:
    """The document's audiobook as the player finds it: its record (`audio.json`, or for a
    book that is still growing one made from the chapter record and `Made`), where it is,
    and for a growing book its chapter record."""

    record: AudioRecord
    located: Located
    growing: ChapterRecord | None = None


def current_audiobook(work: Path, document_id: str, folders: Iterable[Path | None]) -> Current:
    """The finished audiobook if there is one; else the book the audio job is making, once a
    chapter of it is playable. PlayerError as `read_audio_record` and `locate` say."""
    try:
        record = read_audio_record(work, document_id)
    except PlayerError as error:
        if error.key != "listen.no_audiobook":
            raise
        growing = _growing(work, document_id, folders)
        if growing is None:
            raise
        return growing
    located = locate(record, folders)
    return Current(record, replace(located, key=_key_for(work, located.folder, located.name)))


def readalong_stamp(work: Path, readalong: Path) -> str:
    """The stamp of the audiobook whose read-along file this is (`Located.stamp`) without
    checking the rest of it, for the library and the shelf. Raises OSError."""
    return _key_for(work, readalong.parent, readalong.name) or audiobook_stamp(readalong)


def _key_for(work: Path, folder: Path, readalong: str) -> str:
    """The book's key if the working folder's chapter record names this very read-along
    file (its size and SHA-256): a file changed since is another audiobook, as before."""
    record = _chapter_record(work)
    if record is None:
        return ""
    for entry in record.book:
        if entry.name == readalong and _vouched(folder, entry.name, entry.bytes, entry.sha256):
            return book_key(record)
    return ""


def _chapter_record(work: Path) -> ChapterRecord | None:
    """The chapter record, read once per version of the file (every page asks, #389)."""
    try:
        version = file_version(work / CHAPTER_RECORD)
    except OSError:
        return None
    if version is None:
        return read_record(work)
    return _cached_record(str(work), version)


@lru_cache(maxsize=64)
def _cached_record(work: str, version: tuple[int, int, int]) -> ChapterRecord | None:
    return read_record(Path(work))


@lru_cache(maxsize=64)
def _sha256(path: str, version: tuple[int, int, int]) -> str:
    return _full_hash(Path(path))


def _full_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vouched(folder: Path, name: str, size: int, sha256: str) -> Path | None:
    """`<folder>/<name>` if it is in the folder (`in_folder`) with this size and SHA-256."""
    path = in_folder(folder, name)
    if path is None:
        return None
    try:
        if path.stat().st_size != size:
            return None
        version = file_version(path)
        found = _full_hash(path) if version is None else _sha256(str(path), version)
    except OSError:
        return None
    return path if found == sha256 else None


def _growing(work: Path, document_id: str, folders: Iterable[Path | None]) -> Current | None:
    record = _chapter_record(work)
    made = recorded_made(work, document_id)
    if record is None or record.complete or not record.chapters or made is None:
        return None
    entries = [f for f in record.book if f.name.endswith(READALONG_SUFFIX)]
    if len(entries) != 1:
        return None
    entry = entries[0]
    sizes = {f.name: f.bytes for c in record.chapters for f in c.files}
    mp3s = tuple(f.name for c in record.chapters for f in c.files if f.name.endswith(".mp3"))
    if len(mp3s) != len(record.chapters):
        return None
    for folder in dict.fromkeys(f for f in folders if f is not None and f.is_absolute()):
        path = _vouched(folder, entry.name, entry.bytes, entry.sha256)
        if path is None:
            continue
        try:
            data = load_readalong(path)
        except (OSError, ReadAlongError):
            continue
        if tuple(c.mp3 for c in data.chapters) != mp3s or data.m4b is not None or not data.chunks:
            continue
        if not all(_has_size(folder, name, size) for name, size in sizes.items()):
            continue
        audio = AudioRecord(
            voice=made.voice,
            switched_off=made.switched_off,
            duration=data.duration,
            chunks=len(data.chunks),
            m4b=None,
            mp3s=mp3s,
            readalong=entry.name,
            made_with=made.version,
            plugins=made.plugins,
        )
        return Current(audio, Located(folder, data, entry.name, book_key(record)), record)
    return None


def _has_size(folder: Path, name: str, size: int) -> bool:
    path = in_folder(folder, name)
    try:
        return path is not None and path.stat().st_size == size
    except OSError:
        return False


@dataclass(frozen=True)
class ChapterStates:
    """Which of the document's chapters are made (#726): `made` those whose files the
    chapter record names and vouches for where the audiobook is, `coming` those the running
    audio job is still to speak, `folder` where the audiobook is (a chapter added later
    goes there too)."""

    made: frozenset[int]
    coming: frozenset[int]
    folder: Path

    def of(self, index: int) -> str:
        """ "generated", "generating" or "not-generated"."""
        if index in self.made:
            return "generated"
        return "generating" if index in self.coming else "not-generated"


def chapter_states(
    work: Path, document_id: str, folders: Iterable[Path | None], running: bool
) -> ChapterStates | None:
    """The state of the document's chapters (#726), with `running` true while an audio job
    of it runs; None while the project has no chapter made: there is nothing to add to."""
    record = _chapter_record(work)
    if record is None or not record.chapters:
        return None
    try:
        folder = current_audiobook(work, document_id, folders).located.folder
    except PlayerError:
        return None
    made = frozenset(
        chapter.index
        for chapter in record.chapters
        if chapter.files
        and all(_vouched(folder, f.name, f.bytes, f.sha256) is not None for f in chapter.files)
    )
    if not made:
        return None
    coming = frozenset(record.planned) - made if running else frozenset()
    return ChapterStates(made, coming, folder)


def chapter_place(work: Path, index: int) -> int | None:
    """The place in the read-along file of the document's chapter `index`, as the chapter
    record says (None without one, or while it is not playable)."""
    record = _chapter_record(work)
    if record is None:
        return None
    return next((n for n, c in enumerate(record.chapters) if c.index == index), None)


def chapter_index(work: Path, n: int) -> int | None:
    """The document's index of the chapter at place `n` in the read-along file, as the
    chapter record says (None without one)."""
    record = _chapter_record(work)
    if record is None or not 0 <= n < len(record.chapters):
        return None
    return record.chapters[n].index


def planned_chapters(record: ChapterRecord, document: Document) -> list[Planned]:
    """Every chapter the job was asked to speak, in the job's order, with its place in the
    read-along file once it is playable. A chapter the voice failed on entirely gets no
    file (D-162) and so never a place."""
    titles = {chapter.index: chapter.title for chapter in find_chapters(document)}
    places = {chapter.index: n for n, chapter in enumerate(record.chapters)}
    for chapter in record.chapters:
        titles[chapter.index] = chapter.title
    return [
        Planned(index, titles.get(index, ""), places.get(index))
        for index in record.planned
        if index in titles
    ]


# ---- the page's view -------------------------------------------------------------------


@dataclass(frozen=True)
class Part:
    """A stretch of a piece as the voice treated it (#392, D-665 conflict 2): `mark` is ""
    for text read as printed, "cut" for text the voice left out and "said" for text it read
    differently, `said` being what it read."""

    text: str
    mark: str = ""
    said: str = ""


@dataclass(frozen=True)
class Piece:
    """A stretch of a block's text as shown: `element` is the id of the sentence element
    it is (a chunk's text), or None for text the voice does not read. `parts` split it
    where the audiobook's own edits cut or replaced text; empty when it holds none."""

    text: str
    element: str | None = None
    chunk: int | None = None  # the first chunk the element stands for (a click plays it)
    parts: tuple[Part, ...] = ()


@dataclass
class BlockView:
    index: int
    kind: str
    pieces: list[Piece] = field(default_factory=list)
    heading: int = 0  # 2 to 6 for a heading, else 0
    page: str = ""  # the page that starts here, as printed, else ""
    notice: str = ""  # a placeholder read as its notice: the notice
    printed: str = ""  # a notice box: the text the file holds for it
    code: str = ""  # a code block's notice box: its code, line breaks kept, shown open (D-546)
    element: str | None = None  # a notice box: its element id
    chunk: int | None = None  # a notice box: its first chunk
    figures: tuple[Shown, ...] = ()  # a notice box: the figure, table or formula itself (#293)

    @property
    def read(self) -> bool:
        return self.element is not None or any(p.element for p in self.pieces)


@dataclass
class ChapterView:
    index: int  # in the read-along file
    title: str
    blocks: list[BlockView]
    title_block: BlockView | None  # the heading that opens it, shown as its <h2>
    first_chunk: int
    source: str  # the audio file's name
    offset: float  # where that file's time 0 lies on the book's timeline, in seconds
    start: float  # where the chapter starts on the book's timeline, in seconds


@dataclass(frozen=True)
class ChangeView:
    """One category of changes in the Listen panel (#393, D-665 conflict 3): whether it was
    on when the audiobook was made, and how many of its edits the audiobook holds (None
    when the marks are not drawn, D-704b)."""

    category: str
    on: bool
    count: int | None


@dataclass
class PlayerView:
    language: str
    voice: str
    chapters: list[ChapterView]
    chunks: list[tuple[float, float, int, str]]  # start, end, chapter, element id
    mode: str  # "mp3" or "m4b"
    sentences: list[int] = field(default_factory=list)  # each chunk's sentence (#480)
    duration: float = 0.0  # the whole book, in seconds
    marked: bool = False  # the audiobook's edits are drawn on the text (D-704b)
    made_with: str = ""  # the sci2audio version that made the audiobook
    changes: list[ChangeView] = field(default_factory=list)
    # a book still growing (#724): every chapter the job was asked for; empty once done
    planned: list[Planned] = field(default_factory=list)

    @property
    def growing(self) -> bool:
        return bool(self.planned)

    def data(self, document_id: str) -> dict[str, Any]:
        """What the script needs. It builds each file's address itself from the document
        id and the bare file name, so no address from the page is used as it stands."""
        return {
            "document": document_id,
            "mode": self.mode,
            "chapters": [
                {
                    "title": c.title,
                    "file": c.source,
                    "offset": c.offset,
                    "start": c.start,
                    "first": c.first_chunk,
                }
                for c in self.chapters
            ],
            "chunks": [list(chunk) for chunk in self.chunks],
            # each chunk's sentence, by its first piece: next, previous and M step by it (#480)
            "sentences": self.sentences or list(range(len(self.chunks))),
        }


def load_document(work: Path) -> Document:
    """The document the audio job read (D-165). PlayerError("listen.broken") if it can't
    be read."""
    try:
        data = json.loads((work / DOCUMENT_RECORD).read_text(encoding="utf-8"))
        return from_data(Document, data)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise PlayerError("listen.broken") from None


def build_view(
    document: Document,
    record: AudioRecord,
    readalong: ReadAlong,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    *,
    figures: bool = True,
) -> PlayerView:
    """The page for this audiobook (D-297, D-299). PlayerError("listen.mismatch") if a span
    points outside its block (the read-along file belongs to another document).

    A block the text steps read elsewhere (a footnote read at its mark, #213) is shown right
    after the block it is read in, so the page follows the voice, but only where the
    read-along shows the voice read it there (`_heard_moves`): an audiobook made before #213
    read its notes where printed, and shows them there. `steps` are the steps the audiobook
    was made with: the server's runner's, plugins included (#666; tests pass others). With
    `figures`, a figure, table or formula read as its notice shows itself in its notice box
    (#293)."""
    for chunk in readalong.chunks:
        try:
            document.check_span(chunk.span)
        except SpanError:
            raise PlayerError("listen.mismatch") from None
    chapters = find_chapters(document)
    by_block: dict[int, list[int]] = {}
    for number, chunk in enumerate(readalong.chunks):
        by_block.setdefault(chunk.span.block, []).append(number)
    notices = _notices(document, record.switched_off)
    run = _settled(document, record.switched_off, steps)
    joined = _joins(run)
    # the steps that rebuild the run are the ones that made the audio only when the same
    # version of sci2audio made it: otherwise no mark is drawn (D-704b)
    marked = bool(record.made_with) and record.made_with == __version__
    marks = _marks(document, run) if marked else {}
    moved = _heard_moves(run, readalong)
    moved_into: dict[int, list[int]] = {}  # block -> the blocks read inside it, in order
    for block, target in sorted(moved.items()):
        moved_into.setdefault(target, []).append(block)
    levels = _heading_levels(document)
    pages = _page_starts(document, moved.keys())
    catalog = Catalog(document) if figures else None
    code_lines = _code_lines(document)
    code_pages = _code_pages(document, code_lines)

    element_of: list[str] = [""] * len(readalong.chunks)
    firsts = sentence_starts(readalong, document)
    silent = _silent(document, readalong)
    leaders = _leaders(readalong, silent)
    views: list[ChapterView] = []
    used: set[int] = set()
    for index, times in enumerate(readalong.chapters):
        if not 0 <= times.first_chunk < len(readalong.chunks):
            raise PlayerError("listen.mismatch")
        first = readalong.chunks[times.first_chunk].span.block
        chapter = _chapter_of(chapters, moved.get(first, first))  # where it is read
        used.add(chapter.index)
        blocks: list[BlockView] = []
        for number in range(chapter.start, chapter.end):
            if number in moved:
                continue  # shown after the block it is read in
            for shown_here in (number, *moved_into.get(number, ())):
                block = document.blocks[shown_here]
                if block.kind is BlockKind.FURNITURE:
                    continue
                view = _block_view(
                    document,
                    shown_here,
                    by_block.get(shown_here, []),
                    readalong,
                    notices,
                    element_of,
                    joined.get(shown_here, frozenset()),
                    marks.get(shown_here, ()),
                    firsts,
                    leaders,
                )
                view.heading = levels.get(shown_here, 0) if shown_here == number else 0
                view.page = pages.get(shown_here, "")
                if view.code:
                    view.code = indented(document.blocks[shown_here], code_lines, code_pages)
                if catalog is not None and view.notice and not view.code:
                    view.figures = tuple(catalog.images(shown_here, view.notice))
                blocks.append(view)
        title_block = None
        if blocks and blocks[0].heading and blocks[0].index == chapter.start:
            title_block = blocks.pop(0)
            title_block.heading = 2
        if record.mp3s:
            source, offset = times.mp3 or "", times.start
        else:
            source, offset = record.m4b or "", 0.0
        views.append(
            ChapterView(
                index,
                times.title,
                blocks,
                title_block,
                times.first_chunk,
                source,
                offset,
                times.start,
            )
        )
    _place_silent(readalong, element_of, silent)
    chunks = [(c.start, c.end, c.chapter, element_of[n]) for n, c in enumerate(readalong.chunks)]
    heard_blocks = {n for c in chapters if c.index in used for n in range(c.start, c.end)}
    return PlayerView(
        language=document.language,
        voice=record.voice,
        chapters=views,
        chunks=chunks,
        mode="mp3" if record.mp3s else "m4b",
        sentences=firsts,
        duration=readalong.duration,
        marked=marked,
        made_with=record.made_with,
        changes=_changes(document, run, record.switched_off, heard_blocks, marked, notices, moved),
    )


def _changes(
    document: Document,
    run: StepRun,
    switched_off: frozenset[str],
    heard: Collection[int],
    marked: bool,
    notices: Collection[int],
    moved: Collection[int],
) -> list[ChangeView]:
    """Per category: on or off when the audiobook was made, and how many of its accepted
    edits the page shows in the chapters the audiobook reads (an edit counts where its block
    is read, #213), so the count never names changes the text does not show (#462). Page
    furniture counts too, though the sheet never shows it: the sheet is the text without
    it, as it is heard (see `_shown`)."""
    counts: dict[str, int] = {}
    for outcome in run.outcomes:
        if (
            outcome.status is Status.ACCEPTED
            and run.read_at(outcome.edit.span.block) in heard
            and _shown(document, outcome.edit, notices, moved)
        ):
            key = str(outcome.category)
            counts[key] = counts.get(key, 0) + 1
    return [
        ChangeView(str(c), str(c) not in switched_off, counts.get(str(c), 0) if marked else None)
        for c in Category
    ]


_UNMARKED_STEPS = frozenset({LineEndHyphenStep.id})  # joins show as joined words (#286)
_NOTICE_STEPS = frozenset({FormulaNoticeStep.id, TableFigureNoticeStep.id, CodeNoticeStep.id})


def _shown(
    document: Document, edit: Edit, notices: Collection[int], moved: Collection[int]
) -> bool:
    """True if the page shows this accepted edit: the removal of page furniture (the sheet
    is the text without it, as heard), a notice box for a placeholder read as its notice
    (the edits inside its text are not drawn), "Not read" for a block cut whole, a note read
    at its mark shown where it is read, and every stretch `_marks` draws."""
    block = edit.span.block
    if document.blocks[block].kind is BlockKind.FURNITURE:
        # never shown: the sheet is the text without it, as heard
        return edit.kind is EditKind.REMOVE
    if block in notices:
        return edit.step in _NOTICE_STEPS
    if edit.kind is EditKind.MOVE:
        return block in moved
    if edit.kind is EditKind.REMOVE and _whole(document, edit):
        return True
    return _mark(document, edit) is not None


def _whole(document: Document, edit: Edit) -> bool:
    """True if a REMOVE cuts its whole block (the page says "Not read" instead)."""
    span = edit.span
    return span.start == 0 and span.end >= len(document.blocks[span.block].text.rstrip())


def _mark(document: Document, edit: Edit) -> tuple[int, int, str, str] | None:
    """The stretch an accepted edit draws on the text, or None (see `_marks`)."""
    span = edit.span
    if span.start == span.end or edit.step in _UNMARKED_STEPS:
        return None
    original = document.blocks[span.block].text[span.start : span.end]
    if edit.kind is EditKind.REMOVE:
        return None if _whole(document, edit) else (span.start, span.end, "cut", "")
    if edit.kind is EditKind.REPLACE and _looks(edit.replacement) != _looks(original):
        return (span.start, span.end, "said", " ".join(edit.replacement.split()))
    return None


def _marks(document: Document, run: StepRun) -> dict[int, list[tuple[int, int, str, str]]]:
    """By block, the stretches the audiobook's edits cut ("cut") or read differently
    ("said", with what was read), in order: the accepted REMOVE and REPLACE edits of the
    run the page is built from (#392). Left unmarked: a block cut whole (it says "Not read"),
    a word the hyphen step joined (it shows joined), and a replacement that reads like the
    printed text. A placeholder read as its notice draws its notice box, not its text, so
    its marks are never drawn; one read as printed shows its edits like any text."""
    found: dict[int, list[tuple[int, int, str, str]]] = {}
    for edit in run.accepted:
        mark = _mark(document, edit)
        if mark is not None:
            found.setdefault(edit.span.block, []).append(mark)
    for stretches in found.values():
        stretches.sort()
    return found


def _looks(text: str) -> str:
    """How a text looks to a reader: compatibility forms and spacing aside."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _parts(
    text: str,
    start: int,
    end: int,
    joined: frozenset[int],
    marks: Sequence[tuple[int, int, str, str]],
) -> tuple[Part, ...]:
    """Characters `start` to `end` of a block's text split at the marks they overlap; ()
    when they overlap none. The parts' texts join up to `shown(text, start, end, joined)`."""
    parts: list[Part] = []
    position = start
    for low, high, mark, said in marks:
        low, high = max(low, start), min(high, end)
        if low >= high:
            continue
        if low > position:
            parts.append(Part(shown(text, position, low, joined)))
        parts.append(Part(shown(text, low, high, joined), mark, said))
        position = high
    if not parts:
        return ()
    if position < end:
        parts.append(Part(shown(text, position, end, joined)))
    return tuple(p for p in parts if p.text)


def _heard_moves(run: StepRun, readalong: ReadAlong) -> dict[int, int]:
    """The moves of `run` (block -> the block it is read in) that the audiobook was read
    with. The read-along is taken as a row of runs, one per stretch of
    chunks of one block. A moved block counts when it stands in a stretch of blocks moved to
    the same target (notes read at one position, in block order) and that stretch comes
    right after a run of the target, or right before the target's first run (a move to the
    target's start). The page is built by today's steps, but the audio may be older: an
    audiobook made before #213 read each note where it is printed, so its read-along shows
    no such neighbour and the note is shown where printed, in its printed chapter."""
    row: list[int] = []  # the block of each run of chunks, in reading order
    first: dict[int, int] = {}  # block -> the index in `row` of its first run
    for chunk in readalong.chunks:
        if not row or row[-1] != chunk.span.block:
            first.setdefault(chunk.span.block, len(row))
            row.append(chunk.span.block)
    heard: dict[int, int] = {}
    for block, target in run.moved.items():
        if block not in first:
            continue  # nothing of it is read: shown where printed
        before = after = first[block]
        while before >= 0 and run.moved.get(row[before]) == target:
            before -= 1
        while after < len(row) and run.moved.get(row[after]) == target:
            after += 1
        if (before >= 0 and row[before] == target) or first.get(target, -1) == after:
            heard[block] = target
    return heard


def _chapter_of(chapters: Sequence[Chapter], block: int) -> Chapter:
    for chapter in chapters:
        if chapter.holds(block):
            return chapter
    raise PlayerError("listen.mismatch")


def _notices(document: Document, switched_off: frozenset[str]) -> dict[int, str]:
    """The notice each placeholder was read as, where its category was on (D-299)."""
    steps = []
    if str(Category.FORMULAS) not in switched_off:
        steps.append(FormulaNoticeStep())
    if str(Category.TABLES_AND_FIGURES) not in switched_off:
        steps.append(TableFigureNoticeStep())
    if str(Category.CODE) not in switched_off:
        steps.append(CodeNoticeStep())
    context = StepContext(document.language)
    found: dict[int, str] = {}
    for step in steps:
        for edit in step.find(document, context):
            found[edit.span.block] = edit.replacement
    return found


def _heading_levels(document: Document) -> dict[int, int]:
    """The HTML level of each heading block: a heading that opens a section of level n is
    <h(n+1)> (a chapter's own heading is <h2>); any other heading is one level below the
    deepest section it stands in (<h3> outside every section); at most <h6>."""
    levels: dict[int, int] = {}
    inside: dict[int, int] = {}

    def walk(sections: Iterable[Section]) -> None:
        for section in sections:
            for number in range(section.start, section.end):
                inside[number] = section.level
            if (
                section.start < section.end
                and document.blocks[section.start].kind is BlockKind.HEADING
            ):
                levels[section.start] = min(section.level + 1, 6)
            walk(section.children)

    walk(document.sections)
    for number, block in enumerate(document.blocks):
        if block.kind is BlockKind.HEADING and number not in levels:
            levels[number] = min(inside.get(number, 1) + 2, 6)
    return levels


def _page_starts(document: Document, moved: Collection[int] = ()) -> dict[int, str]:
    """The block where each printed page starts (the first block with an item on it). A
    block shown elsewhere (`moved`, #213) starts no page: the next block on it does."""
    pages = Pages(document)
    starts: dict[int, str] = {}
    last: int | None = None
    for number, block in enumerate(document.blocks):
        if block.kind is BlockKind.FURNITURE or not block.parts or number in moved:
            continue
        page = pages.items[block.parts[0].item]
        if page != last:
            label = document.page_label(page) or str(page)
            starts[number] = label
            last = page
    return starts


def shown(
    text: str, start: int = 0, end: int | None = None, joined: Collection[int] = frozenset()
) -> str:
    """Characters `start` to `end` of a block's text as the page shows them: layout's
    line breaks are spaces, except after a hyphen, where the word is joined. A hyphen at
    one of the `joined` offsets (a word the line-end-hyphens step joined) is left out with
    its line break, as the voice reads the word (#286); any other is kept as printed. Pieces
    of one text shown one by one join up to the whole."""
    stop = len(text) if end is None else end
    out = []
    for index in range(start, stop):
        char = text[index]
        if index in joined or (char == "\n" and index - 1 in joined):
            char = ""
        elif char == "\n":
            char = "" if index > 0 and text[index - 1] == "-" else " "
        out.append(char)
    return "".join(out)


def joined_hyphens(
    document: Document,
    switched_off: frozenset[str],
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
) -> dict[int, frozenset[int]]:
    """By block, the offsets of the line-end hyphens whose words the voice read joined: the
    line-end-hyphens step's joins that the settled run of `steps` accepted, with the job's
    categories (#286, #666). A join set aside because an earlier step won (a link, a
    citation, the reference list) is not one: that text shows as printed."""
    return _joins(_settled(document, switched_off, steps))


def _settled(
    document: Document, switched_off: frozenset[str], steps: Sequence[TextStep]
) -> StepRun:
    """The settled run of the steps with the job's categories."""
    off = {Category(value) for value in switched_off if value in _CATEGORIES}
    return run_steps(document, StepContext(document.language), steps, off)


def _joins(run: StepRun) -> dict[int, frozenset[int]]:
    found: dict[int, set[int]] = {}
    for edit in run.accepted:
        if edit.step == LineEndHyphenStep.id and edit.span.end - edit.span.start == 2:
            found.setdefault(edit.span.block, set()).add(edit.span.start)  # hyphen + break
    return {block: frozenset(offsets) for block, offsets in found.items()}


_CATEGORIES = frozenset(str(category) for category in Category)


MAX_INDENT = 40  # characters: a code line is never drawn further in than this (#282)


def _code_lines(document: Document) -> dict[str, tuple[int, TextLine]]:
    """The text lines of the document's CODE blocks that have a box, with their pages."""
    wanted = {p.item for b in document.blocks if b.kind is BlockKind.CODE for p in b.parts}
    if not wanted:
        return {}
    return {
        line.id: (page.number, line)
        for page in document.content.pages
        for line in page.lines
        if line.id in wanted and line.box is not None
    }


def _code_pages(
    document: Document, lines: dict[str, tuple[int, TextLine]]
) -> dict[int, Sequence[TextLine]]:
    """The text lines of each page that holds a line of a CODE block (#612)."""
    wanted = {page for page, _ in lines.values()}
    return {page.number: page.lines for page in document.content.pages if page.number in wanted}


def indented(
    block: Block,
    lines: dict[str, tuple[int, TextLine]],
    pages: dict[int, Sequence[TextLine]] | None = None,
) -> str:
    """A code block's text as the player shows it, each printed line indented as on its
    page (#282): a PDF line holds no leading white space, so a line starting further right
    than the block's left edge gets one space for each character width it stands in, the
    width measured on the block's own lines (a typewriter font's letters are all one
    width), at most `MAX_INDENT`. The block's text stays as printed; only the view gains
    the spaces. A block without line boxes (EPUB, Markdown, text) keeps its text.

    The left edge is the block's leftmost line on its first page. On a later page (a
    listing over a page break, #283) it is that line shifted by how much further right the
    later page's text column starts (odd and even pages have other margins), so a part made
    only of indented lines keeps its indent (#612); never right of the part's own leftmost
    line. Where `pages` (each page's lines) gives no column edge, the part's leftmost line
    on its page is the edge."""
    found = [(p.start, *lines[p.item]) for p in block.parts if p.item in lines]
    widths = [_box_width(line) / len(line.text) for _, _, line in found if line.text]
    width = statistics.median(widths) if widths else 0.0
    if width <= 0:
        return block.text.strip("\n")
    left: dict[int, float] = {}
    for _, page, line in found:
        x0 = line.box.x0 if line.box else 0.0
        left[page] = min(left.get(page, x0), x0)
    if pages and len(left) > 1:
        own = {p.item for p in block.parts}
        first = found[0][1]
        start = _column_edge(pages.get(first, ()), left[first], own)
        for page in left:
            edge = _column_edge(pages.get(page, ()), left[page], own)
            if page != first and start is not None and edge is not None:
                left[page] = min(left[page], left[first] + edge - start)
    starts = [0, *(k + 1 for k, char in enumerate(block.text) if char == "\n")]
    indent: dict[int, int] = {}
    for start, page, line in found:
        if line.box is not None:
            indent[start] = min(MAX_INDENT, round((line.box.x0 - left[page]) / width))
    rows = block.text.split("\n")
    shown = [" " * indent.get(start, 0) + row for start, row in zip(starts, rows, strict=True)]
    return "\n".join(shown).strip("\n")


def _column_edge(lines: Iterable[TextLine], left: float, own: Collection[str]) -> float | None:
    """The left edge of the text column a code part stands in, its leftmost line `left`
    points from the page's edge (#612): where most of the page's other lines that reach
    across `left` start (a column's lines start at its edge; indented first lines are
    fewer), the leftmost of equally many. None where no other line reaches across it."""
    starts: dict[int, int] = {}
    for line in lines:
        box = line.box
        if box is not None and line.id not in own and box.x0 <= left + 0.5 and box.x1 > left:
            starts[round(box.x0)] = starts.get(round(box.x0), 0) + 1
    if not starts:
        return None
    most = max(starts.values())
    return float(min(x for x, count in starts.items() if count == most))


def _box_width(line: TextLine) -> float:
    return line.box.x1 - line.box.x0 if line.box else 0.0


def _block_view(
    document: Document,
    number: int,
    chunk_numbers: list[int],
    readalong: ReadAlong,
    notices: dict[int, str],
    element_of: list[str],
    joined: frozenset[int] = frozenset(),
    marks: Sequence[tuple[int, int, str, str]] = (),
    firsts: Sequence[int] = (),
    leaders: frozenset[int] = frozenset(),
) -> BlockView:
    block = document.blocks[number]
    view = BlockView(number, str(block.kind))
    if block.is_placeholder and number in notices and chunk_numbers:
        view.notice = notices[number]
        if block.kind is BlockKind.CODE:  # the code itself, as printed (D-546)
            view.code = block.text.strip("\n")
        else:
            view.printed = shown(block.text).strip()
        view.element = f"b{number}"
        view.chunk = chunk_numbers[0]
        for n in chunk_numbers:
            element_of[n] = view.element
        return view
    text = block.text
    position = 0
    last_element: str | None = None
    sentence = (0, 0, 0)  # the last sentence: its first chunk, its start, its piece's index
    waiting: list[int] = []  # empty spans before the block's first sentence
    # spans with nothing to say before it (#652): with no sentence in the block, they never
    # make the block the read element; `_place_silent` gives them a neighbour's
    quiet: list[int] = []
    leading: list[int] = []  # markers that open the next sentence (`_leaders`, #869)
    for n in sorted(chunk_numbers, key=lambda n: (readalong.chunks[n].span.start, n)):
        span = readalong.chunks[n].span
        silent = not block.is_placeholder and unspoken(text[span.start : span.end])
        if span.start == span.end or span.start < position or silent:
            # an empty span (or one that would overlap, or say nothing, #652) belongs to the
            # sentence before it, or, before the first one, to the first one; a marker
            # belongs to the sentence it opens (#869)
            if n in leaders:
                leading.append(n)
            elif last_element is None:
                (quiet if silent and span.start < span.end else waiting).append(n)
            else:
                element_of[n] = last_element
            continue
        if n < len(firsts) and firsts[n] != n and n - 1 not in leaders and last_element is not None:
            # a piece of a cut sentence (#480), not a sentence a marker leads (#869): the
            # sentence's element runs on to its end, with the text between the pieces
            first, start, index = sentence
            del view.pieces[index:]
            element_of[n] = last_element
            view.pieces.append(_piece(text, start, span.end, joined, marks, last_element, first))
            position = span.end
            continue
        if span.start > position:
            view.pieces.append(_piece(text, position, span.start, joined, marks))
        last_element = f"s{n}"
        element_of[n] = last_element
        for early in (*waiting, *quiet, *leading):
            element_of[early] = last_element
        waiting, quiet, leading = [], [], []
        sentence = (n, span.start, len(view.pieces))
        view.pieces.append(_piece(text, span.start, span.end, joined, marks, last_element, n))
        position = span.end
    if position < len(text):
        view.pieces.append(_piece(text, position, len(text), joined, marks))
    for early in waiting:  # the block has no sentence: the block is what they read
        element_of[early] = f"b{number}"
    if not view.read and any(element_of[n] == f"b{number}" for n in chunk_numbers):
        # only empty spans point here: the block itself is what they read
        view.element = f"b{number}"
        view.chunk = chunk_numbers[0]
    return view


def sentence_starts(readalong: ReadAlong, document: Document) -> list[int]:
    """For each chunk, the first chunk of the sentence it is a piece of (#480): itself, unless
    the read-along says it `joins` the chunk before it and the page can show the two as one,
    which is when both read text of the same block, the chunk before is the one the page
    draws just before it there, and neither is skipped as empty or overlapping (as
    `_block_view` skips them). Any other `joins` is ignored, so a hand-made or broken file
    can't make the page, the captures and the player group the chunks differently.

    A chunk whose span says nothing (`_silent`: a lone "-" of an audiobook made before #652)
    leads the sentence after it in its block when it opens it (`_leaders`, #869), as the
    page draws it; any other is a piece of the sentence before it in its chapter; a run of
    them that opens a chapter leads the sentence after it. So Previous and Next never stop
    inside a sentence the page shows as one."""
    chunks = readalong.chunks
    silent = _silent(document, readalong)
    leaders = _leaders(readalong, silent)
    kept_before: dict[int, int | None] = {}  # a drawn chunk -> the drawn chunk before it
    by_block: dict[int, list[int]] = {}
    for n, chunk in enumerate(chunks):
        by_block.setdefault(chunk.span.block, []).append(n)
    for numbers in by_block.values():
        position = 0
        last: int | None = None
        for n in sorted(numbers, key=lambda n: (chunks[n].span.start, n)):
            span = chunks[n].span
            if span.start == span.end or span.start < position or n in silent:
                continue
            kept_before[n] = last
            last, position = n, span.end
    starts: list[int] = []
    leading = False  # every chunk of the chapter so far says nothing (#652)
    for n, chunk in enumerate(chunks):
        follows = chunk.joins and n > 0 and n in kept_before and kept_before[n] == n - 1
        same_chapter = n > 0 and chunks[n - 1].chapter == chunk.chapter
        if same_chapter and (leading or n - 1 in leaders or (n in silent and n not in leaders)):
            # ends the silent run that opens the chapter, is led by the marker before it,
            # or says nothing and leads nothing
            follows = True
        leading = n in silent and (leading or not same_chapter)
        starts.append(starts[n - 1] if follows else n)
    return starts


def _silent(document: Document, readalong: ReadAlong) -> frozenset[int]:
    """The chunks whose span holds text with nothing to speak (#652): a lone "-", a bullet
    or a bracket an audiobook made before the cutter left them out. A placeholder's chunk
    never is: it may read a notice for printed text of only brackets ("{ }"). Spans are
    checked by the caller (`document.check_span`); one outside its block is not silent."""
    out = set()
    for n, chunk in enumerate(readalong.chunks):
        span = chunk.span
        if span.start < span.end and 0 <= span.block < len(document.blocks):
            block = document.blocks[span.block]
            if (
                not block.is_placeholder
                and span.end <= len(block.text)
                and unspoken(block.text[span.start : span.end])
            ):
                out.add(n)
    return frozenset(out)


def _leaders(readalong: ReadAlong, silent: frozenset[int]) -> frozenset[int]:
    """The silent chunks that lead the sentence after them (#869), as the cutter has put a
    list marker with the item it opens since #855: the next chunk is in the same block and
    chapter, the page draws it right after this one there (empty and overlapping spans
    are not drawn), and it has something to say or leads in turn. `_block_view` and
    `sentence_starts` both follow this one rule, so the highlight and Previous, Next and
    the captures never put such a chunk in different sentences."""
    chunks = readalong.chunks
    by_block: dict[int, list[int]] = {}
    for n, chunk in enumerate(chunks):
        by_block.setdefault(chunk.span.block, []).append(n)
    after: dict[int, int] = {}  # a chunk drawn or silent -> the next such in its block
    for numbers in by_block.values():
        position = 0
        last: int | None = None
        for n in sorted(numbers, key=lambda n: (chunks[n].span.start, n)):
            span = chunks[n].span
            if span.start == span.end or span.start < position:
                continue
            if last is not None:
                after[last] = n
            last = n
            if n not in silent:
                position = span.end
    out: set[int] = set()
    for n in sorted(silent, reverse=True):
        follower = n + 1
        if (
            after.get(n) == follower
            and chunks[follower].chapter == chunks[n].chapter
            and (follower not in silent or follower in out)
        ):
            out.add(n)
    return frozenset(out)


def _place_silent(readalong: ReadAlong, element_of: list[str], silent: frozenset[int]) -> None:
    """Give a silent chunk that got no element in its block (#652: a block of only "-")
    the element of the nearest chunk before it in its chapter that has one, else of the
    nearest after it: the highlight stays on that sentence while it plays, never on the
    silent block. A run of silent chunks takes it through each other."""
    chunks = readalong.chunks

    def take(n: int, k: int) -> None:
        if not element_of[n] and 0 <= k < len(chunks) and chunks[k].chapter == chunks[n].chapter:
            element_of[n] = element_of[k]

    for n in sorted(silent):
        take(n, n - 1)
    for n in sorted(silent, reverse=True):
        take(n, n + 1)


def _piece(
    text: str,
    start: int,
    end: int,
    joined: frozenset[int],
    marks: Sequence[tuple[int, int, str, str]],
    element: str | None = None,
    chunk: int | None = None,
) -> Piece:
    parts = _parts(text, start, end, joined, marks) if marks else ()
    return Piece(shown(text, start, end, joined), element, chunk, parts)


def chapter_data(view: PlayerView, n: int) -> dict[str, Any]:
    """Chapter `n` of the view as the page's script holds it (`PlayerView.data`): the
    chapter, its chunks with their numbers in the book, and their sentences."""
    chapter = view.chapters[n]
    first = chapter.first_chunk
    end = view.chapters[n + 1].first_chunk if n + 1 < len(view.chapters) else len(view.chunks)
    sentences = view.sentences or list(range(len(view.chunks)))
    return {
        "chapter": {
            "title": chapter.title,
            "file": chapter.source,
            "offset": chapter.offset,
            "start": chapter.start,
            "first": first,
        },
        "first": first,
        "chunks": [list(chunk) for chunk in view.chunks[first:end]],
        "sentences": sentences[first:end],
    }


def player_for(
    work: Path,
    document_id: str,
    folders: Sequence[Path | None],
    *,
    figures: bool = True,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
) -> tuple[PlayerView, Located, Document]:
    """Everything the listen page shows, or PlayerError saying why it can't, with the
    document it was made from (for the captures, #397). `folders` are the only folders the
    audiobook may be in (`candidate_folders`, or the one folder a command-line job names,
    #154). Without `figures` no notice box shows its figure (a command-line job, #293).
    `steps` are the server's (its runner's, plugins included, #666); of their plugin steps
    only those the record names made the audiobook and are used (D-852), so a plugin
    installed, upgraded or added since shows no edit the voice never said."""
    current = current_audiobook(work, document_id, folders)
    record, located = current.record, current.located
    document = load_document(work)
    steps = tuple(
        step for step in steps if getattr(step, "plugin", None) is None or step.id in record.plugins
    )
    view = build_view(document, record, located.readalong, steps, figures=figures)
    if current.growing is not None:
        view.planned = planned_chapters(current.growing, document)
    return view, located, document


def audiobook_file(
    work: Path, document_id: str, name: str, folders: Sequence[Path | None]
) -> Path | None:
    """The file `name` of the document's audiobook, if it is one of its files and passes
    every check; else None."""
    with contextlib.suppress(PlayerError):
        current = current_audiobook(work, document_id, folders)
        if name in current.record.names:
            return in_folder(current.located.folder, name)
        return _built(work, current.located.folder, name)
    return None


# ---- the whole book, built on request (#725, LW-03) ---------------------------------------


@dataclass(frozen=True)
class WholeBook:
    """What the download dialog needs to know of the document's whole-book file of one kind.

    `missing` are the titles of the chosen chapters not made yet. `name` is a file to serve
    now: one built from exactly the chapters made, as the chapter record vouches for it
    (size and SHA-256), or the M4B an audio job of before #725 wrote. `buildable` is false
    for an audiobook without a chapter record (made before #723): only its own M4B is there."""

    missing: tuple[str, ...]
    name: str | None
    buildable: bool = True


def whole_book(work: Path, current: Current, kind: str) -> WholeBook:
    """The document's whole-book file of `kind` ("m4b" or "mp3") in the folder its
    audiobook is in."""
    record = _chapter_record(work)
    if record is None:
        old = current.record.m4b if kind == "m4b" else None
        return WholeBook((), old, buildable=False)
    try:
        planned = planned_chapters(record, load_document(work))
    except PlayerError:
        planned = [Planned(index, "", None) for index in record.planned]
    made = {chapter.index for chapter in record.chapters}
    missing = tuple(p.title or str(p.index + 1) for p in planned if p.index not in made)
    held = tuple(chapter.fingerprint for chapter in record.chapters)
    folder = current.located.folder
    for entry in record.built:
        if entry.kind != kind or entry.chapters != held:
            continue
        file = entry.file
        if _vouched(folder, file.name, file.bytes, file.sha256) is not None:
            return WholeBook(missing, file.name)
    return WholeBook(missing, None)


def _built(work: Path, folder: Path, name: str) -> Path | None:
    """`<folder>/<name>` if the chapter record names it as a whole-book file and vouches
    for it there."""
    record = _chapter_record(work)
    if record is None:
        return None
    for entry in record.built:
        file = entry.file
        if file.name == name:
            return _vouched(folder, file.name, file.bytes, file.sha256)
    return None


def check_outside(work: Path, document_id: str, folder: Path) -> Located:
    """The checks `sci2audio listen` runs before it starts the server (#154): the same as
    the page's, on the working folder and the output folder the person named, and the
    document record must be readable. PlayerError saying why not."""
    try:
        record = read_audio_record(work, document_id)
    except PlayerError as error:
        if error.key == "listen.broken" and _recorded_source(work) not in (None, document_id):
            raise PlayerError("listen.other_version") from None
        raise
    located = locate(record, [folder])
    load_document(work)
    return located


def _recorded_source(work: Path) -> str | None:
    """The document id the audio record names, if it names one."""
    try:
        data = json.loads((work / AUDIO_RECORD).read_text(encoding="utf-8"))
        found = data["source"]["sha256"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None
    return found[:16] if isinstance(found, str) else None
