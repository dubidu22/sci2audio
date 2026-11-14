"""The read-along player's data (#78, OU-02, D-294 to D-303): what the listen page shows.

Three files tell the player everything (D-165, D-102): the audio job's `document.json`
(the laid-out document whose block text the read-along points at) and `audio.json` in the
document's working folder, and the read-along file in the output folder next to the
audio. The app's records keep no folders (they are machine-specific), so the web's audio
task writes its own small record, `audiobook.json`, with the output folder (D-295).

Nothing in these files is trusted as a path (D-295, D-192 to D-209): the record must name
this document and an absolute folder; the folder is only ever one of three (the recorded
one, the saved output folder, the server's default); file names must be bare names listed
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
import json
import math
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Any

from sci2audio.app import find_chapters
from sci2audio.app.chapters import Chapter
from sci2audio.app.files import write_texts
from sci2audio.app.report import Pages
from sci2audio.core import BlockKind, Document, Section, SpanError
from sci2audio.core.export import from_data
from sci2audio.output import ReadAlong, ReadAlongError, read_readalong
from sci2audio.textprep import (
    Category,
    CodeNoticeStep,
    FormulaNoticeStep,
    LineEndHyphenStep,
    StepContext,
    TableFigureNoticeStep,
)

RECORD = "audiobook.json"  # the web's own record of where the audiobook went (D-295)
RECORD_FORMAT = "sci2audio-web-audiobook"
RECORD_VERSION = 1
AUDIO_RECORD = "audio.json"  # the audio job's records (D-165)
DOCUMENT_RECORD = "document.json"
TIME_TOLERANCE = 0.0015  # seconds: both files round to 1 ms


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
    except (OSError, ValueError):
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
        )
    except PlayerError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError):
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
def _readalong(path: str, stamp: tuple[int, int]) -> ReadAlong:
    return read_readalong(Path(path))


def load_readalong(path: Path) -> ReadAlong:
    """The read-along file, read once per version of it on disk (the audio route asks on
    every range request). Raises ReadAlongError or OSError."""
    stat = path.stat()
    return _readalong(str(path), (stat.st_mtime_ns, stat.st_size))


@dataclass(frozen=True)
class Located:
    folder: Path
    readalong: ReadAlong


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
        return Located(folder, data)
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
    """Where the audiobook may be, in order (D-295): recorded, saved, default."""
    return [recorded_folder(work, document_id), saved, default]


# ---- the page's view -------------------------------------------------------------------


@dataclass(frozen=True)
class Piece:
    """A stretch of a block's text as shown: `element` is the id of the sentence element
    it is (a chunk's text), or None for text the voice does not read."""

    text: str
    element: str | None = None
    chunk: int | None = None  # the first chunk the element stands for (a click plays it)


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


@dataclass
class PlayerView:
    language: str
    voice: str
    chapters: list[ChapterView]
    left_out: list[str]  # chapters not in the audiobook
    chunks: list[tuple[float, float, int, str]]  # start, end, chapter, element id
    mode: str  # "mp3" or "m4b"

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
        }


def load_document(work: Path) -> Document:
    """The document the audio job read (D-165). PlayerError("listen.broken") if it can't
    be read."""
    try:
        data = json.loads((work / DOCUMENT_RECORD).read_text(encoding="utf-8"))
        return from_data(Document, data)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise PlayerError("listen.broken") from None


def build_view(document: Document, record: AudioRecord, readalong: ReadAlong) -> PlayerView:
    """The page for this audiobook (D-297, D-299). PlayerError("listen.mismatch") if a span
    points outside its block (the read-along file belongs to another document)."""
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
    joined = joined_hyphens(document, record.switched_off)
    levels = _heading_levels(document)
    pages = _page_starts(document)

    element_of: list[str] = [""] * len(readalong.chunks)
    views: list[ChapterView] = []
    used: set[int] = set()
    for index, times in enumerate(readalong.chapters):
        if not 0 <= times.first_chunk < len(readalong.chunks):
            raise PlayerError("listen.mismatch")
        chapter = _chapter_of(chapters, readalong.chunks[times.first_chunk].span.block)
        used.add(chapter.index)
        blocks: list[BlockView] = []
        for number in range(chapter.start, chapter.end):
            block = document.blocks[number]
            if block.kind is BlockKind.FURNITURE:
                continue
            view = _block_view(
                document,
                number,
                by_block.get(number, []),
                readalong,
                notices,
                element_of,
                joined.get(number, frozenset()),
            )
            view.heading = levels.get(number, 0)
            view.page = pages.get(number, "")
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
    left_out = [c.title for c in chapters if c.index not in used]
    chunks = [(c.start, c.end, c.chapter, element_of[n]) for n, c in enumerate(readalong.chunks)]
    return PlayerView(
        language=document.language,
        voice=record.voice,
        chapters=views,
        left_out=left_out,
        chunks=chunks,
        mode="mp3" if record.mp3s else "m4b",
    )


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


def _page_starts(document: Document) -> dict[int, str]:
    """The block where each printed page starts (the first block with an item on it)."""
    pages = Pages(document)
    starts: dict[int, str] = {}
    last: int | None = None
    for number, block in enumerate(document.blocks):
        if block.kind is BlockKind.FURNITURE or not block.parts:
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


def joined_hyphens(document: Document, switched_off: frozenset[str]) -> dict[int, frozenset[int]]:
    """By block, the offsets of the line-end hyphens whose words the line-end-hyphens step
    joined, as the voice read them; none where characters and hyphenation were off (#286)."""
    step = LineEndHyphenStep()
    if str(step.category) in switched_off or not step.handles(document.language):
        return {}
    found: dict[int, set[int]] = {}
    for edit in step.find(document, StepContext(document.language)):
        if edit.span.end - edit.span.start == 2:  # the hyphen and its line break: joined
            found.setdefault(edit.span.block, set()).add(edit.span.start)
    return {block: frozenset(offsets) for block, offsets in found.items()}


def _block_view(
    document: Document,
    number: int,
    chunk_numbers: list[int],
    readalong: ReadAlong,
    notices: dict[int, str],
    element_of: list[str],
    joined: frozenset[int] = frozenset(),
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
        if span.start > position:
            view.pieces.append(Piece(shown(text, position, span.start, joined)))
        last_element = f"s{n}"
        element_of[n] = last_element
        for early in waiting:
            element_of[early] = last_element
        waiting = []
        view.pieces.append(Piece(shown(text, span.start, span.end, joined), last_element, n))
        position = span.end
    if position < len(text):
        view.pieces.append(Piece(shown(text, position, None, joined)))
    for early in waiting:  # the block has no sentence: the block is what they read
        element_of[early] = f"b{number}"
    if not view.read and any(element_of[n] == f"b{number}" for n in chunk_numbers):
        # only empty spans point here: the block itself is what they read
        view.element = f"b{number}"
        view.chunk = chunk_numbers[0]
    return view


def player_for(
    work: Path, document_id: str, saved: Path | None, default: Path
) -> tuple[PlayerView, Located]:
    """Everything the listen page shows, or PlayerError saying why it can't."""
    record = read_audio_record(work, document_id)
    located = locate(record, candidate_folders(work, document_id, saved, default))
    document = load_document(work)
    return build_view(document, record, located.readalong), located


def audiobook_file(
    work: Path, document_id: str, name: str, saved: Path | None, default: Path
) -> Path | None:
    """The file `name` of the document's audiobook, if it is one of its files and passes
    every check; else None."""
    with contextlib.suppress(PlayerError):
        record = read_audio_record(work, document_id)
        if name not in record.names:
            return None
        located = locate(record, candidate_folders(work, document_id, saved, default))
        return in_folder(located.folder, name)
    return None
