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
was read is a notice box (D-299).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import statistics
import time
import unicodedata
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Any

from sci2audio import __version__
from sci2audio.app import find_chapters
from sci2audio.app.chapters import Chapter
from sci2audio.app.files import write_texts
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
)
from sci2audio.web.figures import Catalog, Shown
from sci2audio.web.project import read_project

RECORD = "audiobook.json"  # the web's own record of where the audiobook went (D-295)
RECORD_FORMAT = "sci2audio-web-audiobook"
RECORD_VERSION = 1
AUDIO_RECORD = "audio.json"  # the audio job's records (D-165)
DOCUMENT_RECORD = "document.json"
TIME_TOLERANCE = 0.0015  # seconds: both files round to 1 ms
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


def write_record(work: Path, document_id: str, folder: Path) -> None:
    """Note where the audio job of `document_id` wrote its audiobook. Raises OSError."""
    data = {
        "format": RECORD_FORMAT,
        "version": RECORD_VERSION,
        "document": document_id,
        "folder": str(folder.absolute()),
    }
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    write_texts({work / RECORD: text}, overwrite=True)


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
    in seconds on the book's timeline."""

    chapter: int
    time: float


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

    def continues(self, position: Position) -> bool:
        """True if the position fits and something is left to continue: it is after the
        first sentence ended and before the last one ended."""
        if self.spoken is None or not self.fits(position):
            return False
        first, last = self.spoken
        return first <= position.time < last


def fits(readalong: ReadAlong, position: Position) -> bool:
    """True if the position is a time of this audiobook inside the chapter it names."""
    return Bounds.of(readalong).fits(position)


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
# they cannot tell the two versions apart yet (as git treats "racy" files; #403 B1).
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
    Raises OSError."""
    data = {
        "format": POSITION_FORMAT,
        "version": POSITION_VERSION,
        "document": document_id,
        "audiobook": stamp,
        "chapter": position.chapter,
        "time": position.time,
    }
    write_texts({work / POSITION: json.dumps(data) + "\n"}, overwrite=True)


def remove_position(work: Path) -> None:
    """Forget the position (a new audiobook was made). Raises OSError."""
    (work / POSITION).unlink(missing_ok=True)


def read_position(
    work: Path, document_id: str, stamp: str, readalong: ReadAlong
) -> Position | None:
    """Where the person stopped in this audiobook, worth offering to continue from; None
    if there is no such record, it does not fit, or nothing is left to continue: before the
    first sentence ended or after the last one ended."""
    position = recorded_position(work, document_id, stamp)
    if position is None or not Bounds.of(readalong).continues(position):
        return None
    return position


def recorded_position(work: Path, document_id: str, stamp: str) -> Position | None:
    """The position the record keeps for this audiobook (`stamp`) of this document, read
    without the read-along file: None for no record, a record of something else, or one
    that is not ours. `read_position` checks it against the audiobook as well; the library
    and the rail's shelf (#389) take it with only the audiobook's length."""
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
        or data.get("audiobook") != stamp
        or not isinstance(chapter, int)
        or isinstance(chapter, bool)
        or not isinstance(time, int | float)
        or isinstance(time, bool)
        or not math.isfinite(time)
    ):
        return None
    return Position(chapter, float(time))


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

    @property
    def stamp(self) -> str:
        """The audiobook's stamp for the listening position (#153). Raises OSError."""
        return audiobook_stamp(self.folder / self.name)


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

    element_of: list[str] = [""] * len(readalong.chunks)
    firsts = sentence_starts(readalong)
    views: list[ChapterView] = []
    used: set[int] = set()
    for index, times in enumerate(readalong.chapters):
        if not 0 <= times.first_chunk < len(readalong.chunks):
            raise PlayerError("listen.mismatch")
        first = readalong.chunks[times.first_chunk].span.block
        chapter = _chapter_of(chapters, moved.get(first, first))  # where it is read (R1-1)
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
                )
                view.heading = levels.get(shown_here, 0) if shown_here == number else 0
                view.page = pages.get(shown_here, "")
                if view.code:
                    view.code = indented(document.blocks[shown_here], code_lines)
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


def indented(block: Block, lines: dict[str, tuple[int, TextLine]]) -> str:
    """A code block's text as the player shows it, each printed line indented as on its
    page (#282): a PDF line holds no leading white space, so a line starting further right
    than the block's leftmost line on that page gets one space for each character width it
    stands in, the width measured on the block's own lines (a typewriter font's letters are
    all one width), at most `MAX_INDENT`. The block's text stays as printed; only the view
    gains the spaces. A block without line boxes (EPUB, Markdown, text) keeps its text."""
    found = [(p.start, *lines[p.item]) for p in block.parts if p.item in lines]
    widths = [_box_width(line) / len(line.text) for _, _, line in found if line.text]
    width = statistics.median(widths) if widths else 0.0
    if width <= 0:
        return block.text.strip("\n")
    left: dict[int, float] = {}
    for _, page, line in found:
        x0 = line.box.x0 if line.box else 0.0
        left[page] = min(left.get(page, x0), x0)
    starts = [0, *(k + 1 for k, char in enumerate(block.text) if char == "\n")]
    indent: dict[int, int] = {}
    for start, page, line in found:
        if line.box is not None:
            indent[start] = min(MAX_INDENT, round((line.box.x0 - left[page]) / width))
    rows = block.text.split("\n")
    shown = [" " * indent.get(start, 0) + row for start, row in zip(starts, rows, strict=True)]
    return "\n".join(shown).strip("\n")


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
    for n in sorted(chunk_numbers, key=lambda n: (readalong.chunks[n].span.start, n)):
        span = readalong.chunks[n].span
        if span.start == span.end or span.start < position:
            # an empty span (or one that would overlap) belongs to the sentence before it,
            # or, before the first one, to the first one
            if last_element is None:
                waiting.append(n)
            else:
                element_of[n] = last_element
            continue
        if n < len(firsts) and firsts[n] != n and last_element is not None:
            # a piece of a cut sentence (#480): the sentence's element runs on to its end,
            # with the text between the pieces
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
        for early in waiting:
            element_of[early] = last_element
        waiting = []
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


def sentence_starts(readalong: ReadAlong) -> list[int]:
    """For each chunk, the first chunk of the sentence it is a piece of (#480): itself, unless
    the read-along says it `joins` the chunk before it and the page can show the two as one,
    which is when both read text of the same block, the chunk before is the one the page
    draws just before it there, and neither is skipped as empty or overlapping (as
    `_block_view` skips them). Any other `joins` is ignored, so a hand-made or broken file
    can't make the page, the markers and the player group the chunks differently."""
    chunks = readalong.chunks
    kept_before: dict[int, int | None] = {}  # a drawn chunk -> the drawn chunk before it
    by_block: dict[int, list[int]] = {}
    for n, chunk in enumerate(chunks):
        by_block.setdefault(chunk.span.block, []).append(n)
    for numbers in by_block.values():
        position = 0
        last: int | None = None
        for n in sorted(numbers, key=lambda n: (chunks[n].span.start, n)):
            span = chunks[n].span
            if span.start == span.end or span.start < position:
                continue
            kept_before[n] = last
            last, position = n, span.end
    starts: list[int] = []
    for n, chunk in enumerate(chunks):
        follows = chunk.joins and n > 0 and n in kept_before and kept_before[n] == n - 1
        starts.append(starts[n - 1] if follows else n)
    return starts


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


def player_for(
    work: Path,
    document_id: str,
    folders: Sequence[Path | None],
    *,
    figures: bool = True,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
) -> tuple[PlayerView, Located, Document]:
    """Everything the listen page shows, or PlayerError saying why it can't, with the
    document it was made from (for the markers, #474). `folders` are the only folders the
    audiobook may be in (`candidate_folders`, or the one folder a command-line job names,
    #154). Without `figures` no notice box shows its figure (a command-line job, #293).
    `steps` are the server's (its runner's, plugins included, #666); of their plugin steps
    only those the record names made the audiobook and are used (D-852), so a plugin
    installed, upgraded or added since shows no edit the voice never said."""
    record = read_audio_record(work, document_id)
    located = locate(record, folders)
    document = load_document(work)
    steps = tuple(
        step for step in steps if getattr(step, "plugin", None) is None or step.id in record.plugins
    )
    view = build_view(document, record, located.readalong, steps, figures=figures)
    return view, located, document


def audiobook_file(
    work: Path, document_id: str, name: str, folders: Sequence[Path | None]
) -> Path | None:
    """The file `name` of the document's audiobook, if it is one of its files and passes
    every check; else None."""
    with contextlib.suppress(PlayerError):
        record = read_audio_record(work, document_id)
        if name not in record.names:
            return None
        located = locate(record, folders)
        return in_folder(located.folder, name)
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
