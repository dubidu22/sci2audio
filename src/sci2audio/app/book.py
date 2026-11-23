"""The whole audiobook as one file, built on request from the chapters made (#725, LW-03).

A job writes each chapter's MP3 as soon as it is spoken (#723); the whole book, one M4B
with chapter marks or one MP3 with ID3 chapter marks, is built only when the person asks
for it. It is built from the chunk cache, with each chapter's chunk list the job kept
(`spoken/<index>.json`, `playable.py`), on the timeline the job uses: nothing is spoken
and no text step runs, and the M4B is the one the job would have written for the same
chapters (output's `write_book_file`).

- Only the chapters made go in, in the book's order. Chosen chapters not made yet, and
  made chapters whose chunks were cleaned out of the cache, are named; the file is then
  built only when a partial book is asked for, and named partial.
- The file goes into the project's output folder and into the chapter record (`built`,
  with the fingerprints of the chapters it holds) after `vouch` named it there before the
  rename, as every file of the job (#723). A file of that name the record does not vouch
  for is never replaced (D-163). A recorded file whose chapters are still these is reused.
- One job per working folder (D-161); progress as the share of the book's audio fed to
  ffmpeg; cancel by a `threading.Event`, which leaves no half file (D-119).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from sci2audio.app.chunks import is_finished
from sci2audio.app.job import JobCancelledError, JobError, OutputExistsError
from sci2audio.app.lock import work_folder_lock
from sci2audio.app.playable import (
    BuiltFile,
    ChapterRecord,
    PlayableChapter,
    RecordedFile,
    file_sha256,
    read_record,
    read_spoken,
    write_record,
)
from sci2audio.output import (
    BookChapter,
    BookInfo,
    BookKind,
    ChunkAudioError,
    Ffmpeg,
    FfmpegError,
    FfmpegNotFoundError,
    OutputSettings,
    Spoken,
    book_file_name,
    book_subtitles,
    find_ffmpeg,
    write_book_file,
)

COVER_NAMES = ("cover.jpg", "cover.png")  # the cover the job wrote (D-313)


@dataclass(frozen=True)
class BookProgress:
    """How far the build is: the share of the book's audio given to ffmpeg, 0 to 1."""

    fraction: float


@dataclass(frozen=True)
class BuiltBook:
    """The whole-book file and what it holds (job chapter indices, in the book's order).

    `missing` are the chosen chapters not made yet, `unavailable` the made chapters whose
    chunks are no longer in the cache; with either, the file is `partial`. `reused` is
    true when the recorded file was still current and nothing was written."""

    path: Path
    kind: BookKind
    chapters: tuple[int, ...]
    missing: tuple[int, ...]
    unavailable: tuple[int, ...]
    partial: bool
    reused: bool


class MissingChaptersError(JobError):
    """Chosen chapters are not made, or no longer in the cache, and no partial book was
    asked for; `missing` and `unavailable` as in `BuiltBook`."""

    def __init__(self, missing: Sequence[int], unavailable: Sequence[int]) -> None:
        self.missing, self.unavailable = tuple(missing), tuple(unavailable)
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} of the chosen chapters are not made yet")
        if self.unavailable:
            parts.append(
                f"the audio of {len(self.unavailable)} chapters is no longer in the working "
                "folder; generate them again"
            )
        super().__init__("; ".join(parts) + "; choose a partial audiobook to build the rest")


def build_book(
    work: Path,
    out_folder: Path,
    kind: BookKind = BookKind.M4B,
    *,
    partial_ok: bool = False,
    progress: Callable[[BookProgress], None] | None = None,
    cancel: threading.Event | None = None,
    ffmpeg: Ffmpeg | None = None,
) -> BuiltBook:
    """Build the whole book of the chapters made in `work` as one `kind` file in
    `out_folder`, or reuse the one built before; see the module docstring.

    Raises MissingChaptersError when chapters are missing and not `partial_ok`,
    OutputExistsError for a file of that name not from this project, JobCancelledError
    when `cancel` is set, JobError (or a subclass) when the book cannot be built. Nothing
    half-written is left."""
    tell: Callable[[BookProgress], None] = progress or (lambda event: None)
    out_folder = out_folder.absolute()
    with work_folder_lock(work):
        record = read_record(work)
        if record is None or not record.chapters:
            raise JobError("no chapter of this audiobook is made yet; make its chapters first")
        if record.made is None:
            raise JobError(
                "the chapters were made by an earlier version of sci2audio, which did not "
                "keep what the whole audiobook is built from; make the chapters again"
            )
        book, settings = _book(work, record)
        chapters, unavailable = _chapters(work, record)
        made = {c.index for c in record.chapters}
        missing = tuple(i for i in record.planned if i not in made)
        if not chapters:
            raise MissingChaptersError(missing, unavailable)
        partial = bool(missing or unavailable)
        if partial and not partial_ok:
            raise MissingChaptersError(missing, unavailable)
        target = book_file_name(out_folder, book.title, kind, partial=partial)
        held = tuple(c.fingerprint for c, _ in chapters)
        indices = tuple(c.index for c, _ in chapters)
        built = BuiltBook(target, kind, indices, missing, unavailable, partial, reused=False)
        for entry in record.built:
            if (
                entry.file.name == target.name
                and entry.kind == kind.value
                and entry.chapters == held
                and entry.file.matches(out_folder)
                and _pair_current(record, target, kind, settings)
            ):
                tell(BookProgress(1.0))
                return replace(built, reused=True)
        _check_cancel(cancel)
        _write(
            work,
            out_folder,
            record,
            target,
            chapters,
            book,
            settings,
            kind,
            held,
            tell,
            cancel,
            ffmpeg,
        )
        tell(BookProgress(1.0))
        return built


def _book(work: Path, record: ChapterRecord) -> tuple[BookInfo, OutputSettings]:
    """The book's details and output settings the chapters were made with."""
    assert record.made is not None  # noqa: S101 (checked by the caller)
    try:
        title, authors, language = record.made["book"]
        settings = OutputSettings(**record.made["output"])
        book = BookInfo(
            title=str(title), authors=tuple(str(a) for a in authors), language=str(language)
        )
    except (KeyError, TypeError, ValueError) as error:
        raise JobError(
            "the chapter record of this audiobook cannot be read; make the chapters again"
        ) from error
    cover = next((work / name for name in COVER_NAMES if (work / name).is_file()), None)
    return replace(book, cover=cover), settings


def _chapters(
    work: Path, record: ChapterRecord
) -> tuple[list[tuple[PlayableChapter, tuple[Spoken, ...]]], tuple[int, ...]]:
    """The made chapters whose chunk list and chunks are all in the working folder, in
    the book's order, and the indices of those whose are not."""
    out, unavailable = [], []
    for chapter in record.chapters:
        spoken = read_spoken(work, chapter.index, chapter.spoken)
        if spoken is None or not all(is_finished(work / s.chunk.file) for s in spoken):
            unavailable.append(chapter.index)
        else:
            out.append((chapter, spoken))
    return out, tuple(unavailable)


def _pair_current(
    record: ChapterRecord, target: Path, kind: BookKind, settings: OutputSettings
) -> bool:
    """The subtitles beside a book M4B are there as recorded (the MP3 has none)."""
    if kind is not BookKind.M4B or not settings.subtitles:
        return True
    names = {p.name for p in book_subtitles(target)}
    files = {f.name: f for f in record.book}
    return all(name in files and files[name].matches(target.parent) for name in names)


def _write(
    work: Path,
    out_folder: Path,
    record: ChapterRecord,
    target: Path,
    chapters: Sequence[tuple[PlayableChapter, tuple[Spoken, ...]]],
    book: BookInfo,
    settings: OutputSettings,
    kind: BookKind,
    held: tuple[str, ...],
    tell: Callable[[BookProgress], None],
    cancel: threading.Event | None,
    ffmpeg: Ffmpeg | None,
) -> None:
    owned = record.owned(out_folder)
    pair = book_subtitles(target) if kind is BookKind.M4B and settings.subtitles else ()
    present = [p.name for p in (target, *pair) if p.exists() or p.is_symlink()]
    if foreign := [name for name in present if name not in owned]:
        raise OutputExistsError(
            f"these files exist already and were not made from this project: "
            f"{', '.join(foreign)}; move them away to build the audiobook here"
        )
    try:
        run = _Watched(
            (ffmpeg or Ffmpeg(find_ffmpeg())).exe,
            inner=ffmpeg,
            cancel=cancel,
            tell=tell,
            total=_audio_bytes(work, chapters),
        )
    except FfmpegNotFoundError as error:
        raise JobError(str(error)) from error
    state = {"record": record}

    def save(new: ChapterRecord) -> None:
        try:
            write_record(work, new)
        except OSError as error:
            raise JobError(
                f"could not write the job's chapter record: {error.strerror or error}"
            ) from error
        state["record"] = new

    def vouch(path: Path, size: int, sha256: str) -> None:
        save(state["record"].with_pending(RecordedFile(path.name, size, sha256)))

    parts = [
        # any increasing numbers fix the order; a book in the order chosen (#119) is
        # numbered by that order, so its place is its number here
        BookChapter(n, chapter.title, spoken)
        for n, (chapter, spoken) in enumerate(chapters, start=1)
    ]
    try:
        write_book_file(
            work,
            target,
            parts,
            book,
            settings,
            kind,
            ffmpeg=run,
            vouch=vouch,
            replace=bool(present),
        )
    except JobError:
        raise
    except FileExistsError as error:
        raise OutputExistsError(f"{error}; move them away to build the audiobook here") from error
    except ChunkAudioError as error:
        raise JobError(f"{error}; generate the chapter again") from error
    except FfmpegError as error:
        raise JobError(f"could not build the audiobook: {error}") from error
    except OSError as error:
        where = Path(str(error.filename)).name if error.filename else target.name
        raise JobError(f"could not write {where}: {error.strerror or error}") from error
    try:
        file = RecordedFile(target.name, target.stat().st_size, file_sha256(target))
    except OSError as error:
        raise JobError(f"could not read {target.name}: {error.strerror or error}") from error
    done = state["record"].with_book_files({p.name for p in pair})
    save(done.with_built(BuiltFile(file, kind.value, held)))


def _audio_bytes(work: Path, chapters: Sequence[tuple[PlayableChapter, tuple[Spoken, ...]]]) -> int:
    """About how many bytes of audio ffmpeg is fed: the chunks' (pauses are left out, so
    the share is capped at 1)."""
    total = 0
    for _, spoken in chapters:
        for s in spoken:
            try:
                total += max((work / s.chunk.file).stat().st_size - 44, 0)
            except OSError:
                continue
    return max(total, 1)


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise JobCancelledError("the build was cancelled; nothing was written")


@dataclass(frozen=True)
class _Watched(Ffmpeg):
    """Runs the given ffmpeg, telling how much of the audio it was fed and stopping the
    feed when the build is cancelled; output then removes its partial file (D-119)."""

    inner: Ffmpeg | None = None
    cancel: threading.Event | None = None
    tell: Callable[[BookProgress], None] = lambda event: None
    total: int = 1

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        runner = self.inner or Ffmpeg(self.exe)
        return runner.run(args, self._watched(feed))

    def _watched(self, feed: Iterable[bytes]) -> Iterator[bytes]:
        fed = 0
        for piece in feed:
            _check_cancel(self.cancel)
            fed += len(piece)
            self.tell(BookProgress(min(fed / self.total, 1.0)))
            yield piece
