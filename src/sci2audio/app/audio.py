"""The audio job: a file in, the audiobook out (#71, WI-02, WI-04, VA-04; closes #10).

file → script preparation (as the script job, in memory) → the voice speaks every
utterance of the chosen chapters into the working folder's chunk cache → output writes each
chapter's MP3 as soon as the chapter is spoken (#723), then the M4B when asked for and the
final read-along file → the job's records.

- Writes only the audiobook files into the output folder (D-154); the script and the
  report are the script job's.
- Resume (D-155, D-156): a chunk is cached under a key of its text, voice, speed and engine
  version; running the job again on the same working folder speaks only what is missing.
- Each chapter is playable as soon as it is spoken (#723, LW-01, `playable.py`): its files
  are put in place before the next chapter is spoken, recorded in `chapters.json` (named
  there before each rename) and told to the listener (`AudioProgress.ready`). A rerun or
  resume under the same settings takes its own whole chapters as they are (same
  fingerprint, same size and SHA-256), and replaces its own unfinished files without
  `overwrite`; a finished audiobook, or one made under other settings, still needs it.
  The job's own default writes no M4B (`JOB_OUTPUT`); the CLI and the web pass theirs.
- Pauses (D-116, D-157): the app gives every chunk one `Pause` kind; output turns kinds
  into seconds and opens every chapter with the chapter pause.
- Progress and the time estimate (D-159, D-380 to D-382, D-384, `estimate.py`) are
  measured on this run's own speech; cancel (D-160) by a `threading.Event`; one job per
  working folder (D-161).
- It never stops to ask (D-61 (3)): an utterance the voice fails on is left out and
  listed, five failures in a row stop the job (D-162). It fails with a `JobError` a person
  can act on, and nothing half-written, when it cannot go on (D-140): the existing
  audiobook without `overwrite` (checked before any speech, D-163), missing voice files,
  a full disk, a removed output folder, ffmpeg failing.
- The cover (D-313): the file's own cover image, written to the working folder as
  `cover.jpg` or `cover.png` and decoded once by ffmpeg before any speech, goes into every
  MP3 and the M4B. A file without one, or a cover that cannot be read, decoded or
  written, gives an audiobook without a cover, never a failed job.
"""

from __future__ import annotations

import contextlib
import dataclasses
import threading
import time
import wave
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from sci2audio import __version__
from sci2audio.app.chapters import document_title, find_chapters, selected
from sci2audio.app.chunks import (
    cache_size,
    chunk_file,
    chunk_key,
    is_finished,
    remove_partials,
)
from sci2audio.app.estimate import Estimate
from sci2audio.app.files import write_bytes_atomically, write_text_atomically, write_texts
from sci2audio.app.job import (
    COVERS,
    JobCancelledError,
    JobError,
    OutputExistsError,
    Phase,
    SettingsChangedError,
    UnreadableTextError,
    check_folders,
    check_readable,
    json_text,
    read_document,
    settings_changes,
    settings_data,
)
from sci2audio.app.lock import work_folder_lock
from sci2audio.app.playable import (
    ChapterRecord,
    PlayableChapter,
    RecordedFile,
    read_record,
    settings_key,
    write_record,
    write_spoken,
)
from sci2audio.app.readability import stop_message, unreadable
from sci2audio.app.report import Pages
from sci2audio.app.script import ScriptResult, prepare_script, speakable
from sci2audio.app.settings import JobSettings
from sci2audio.app.voice import VoiceSource
from sci2audio.core import AudioChunk, BlockKind, Document, Span
from sci2audio.core.export import to_data
from sci2audio.output import (
    BookInfo,
    BookWriter,
    Chapter,
    ChunkAudioError,
    Ffmpeg,
    FfmpegError,
    FfmpegNotFoundError,
    OutputSettings,
    Pause,
    Spoken,
    Written,
    audiobook_targets,
    chapter_fingerprint,
    find_ffmpeg,
    read_readalong,
)
from sci2audio.output.ffmpeg import LOCAL_ONLY
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    DEFAULT_MAX_CHARS,
    Category,
    TextStep,
    Utterance,
)
from sci2audio.voices import (
    Engine,
    EngineError,
    EngineSession,
    ModelNotFoundError,
    speak_to_wav,
)

RECORD = "audio.json"
RECORD_FORMAT = "sci2audio-audio"
RECORD_VERSION = 1
DOCUMENT = "document.json"
COVER_NAMES = ("cover.jpg", "cover.png")  # the cover in the working folder (D-313)
ESTIMATE_MIN_CHARACTERS = 1000  # measured before the first estimate (D-159, D-382)
WARM_UP_CALLS = 4  # the voice's first calls are slower; they are not measured (D-381)
FAILURES_IN_A_ROW = 5  # the voice is taken as broken after this many (D-162)
# what the job writes unless told otherwise (#723): each chapter's MP3 as soon as it is
# spoken, and the read-along file; the whole book is built on request (#725)
JOB_OUTPUT = OutputSettings(m4b=False)


@dataclass(frozen=True)
class PlannedChunk:
    """One utterance the voice speaks: its chapter, cache key and the pause before it."""

    utterance: Utterance
    chapter: int  # index in the job's chapter list
    key: str
    pause: Pause

    @property
    def file(self) -> str:
        return chunk_file(self.key)


@dataclass(frozen=True)
class AudioPlan:
    """Every chunk of the chosen chapters in order, and the chosen chapters with nothing
    to say (they get no audio)."""

    chunks: tuple[PlannedChunk, ...]
    silent: tuple[int, ...]


@dataclass(frozen=True)
class SkippedUtterance:
    """An utterance the voice failed on: left out of the audiobook and listed (D-162)."""

    chapter: int
    span: Span
    page: int | None
    printed_page: str
    text: str
    error: str


@dataclass(frozen=True)
class AudioProgress:
    """What the audio job is doing; sent as each phase starts and after every chunk.

    `characters_*` count only what the voice speaks in this run (cached chunks are not
    spoken again). `seconds_left` is None while the speed is being measured (D-159).
    """

    phase: Phase
    chapter: int | None = None  # the chunk's chapter, index in the job's chapter list
    chapter_title: str = ""
    chapters: int = 0  # chapters with something to say
    # D-695: the chunk's chapter counted from 1 among those, in the order read, and
    # whether the chunk was that chapter's last (the next one starts the next chapter);
    # 0 and False outside the speaking phase's chunks
    chapter_number: int = 0
    chapter_done: bool = False
    # #1054: the chunk's chapter's own count, done (this chunk included) and in all, so a
    # page can show how far the chapter being spoken is; 0 outside the speaking phase's chunks
    chapter_chunks_done: int = 0
    chapter_chunks_total: int = 0
    chunks_done: int = 0
    chunks_total: int = 0
    reused: int = 0  # chunks found finished in the cache
    characters_done: int = 0
    characters_total: int = 0
    characters_per_second: float | None = None
    seconds_left: float | None = None
    page: int = 0  # reading a PDF: the page its reader started, counted from 1 (#343)
    pages: int = 0  # ... and the PDF's page count; 0 for other files and phases
    # #723: the chapter whose files just became playable, on the event sent right after
    # they are recorded (it repeats the chapter's last chunk event); and every playable
    # chapter so far, as indices in the job's chapter list, in the job's order
    ready: int | None = None
    playable: tuple[int, ...] = ()


@dataclass(frozen=True)
class AudioJob:
    """What a finished audio job worked out and wrote."""

    result: ScriptResult
    written: Written
    spoken: int  # chunks the voice spoke in this run
    reused: int  # chunks taken from the cache (or spoken earlier in this run)
    skipped: tuple[SkippedUtterance, ...]
    duration: float  # seconds of the M4B timeline
    characters_per_second: float | None
    record: Path
    document_file: Path


# ---- planning (pure) -----------------------------------------------------------------


def plan_audio(
    result: ScriptResult,
    *,
    engine: str,
    engine_version: str,
    voice: str,
    speed: float,
    letter_speed: float = 1.0,
) -> AudioPlan:
    """The chunks of the chosen chapters with their pause kinds (D-116, D-157):
    PARAGRAPH for the first chunk of another block (HEADING after a heading), SENTENCE for
    the next sentence of one block, CLAUSE where the length limit cut a sentence (#480), and
    at least PAUSE_EDIT after a `pause` edit. A chapter's first chunk gets the chapter pause
    from output, whatever its kind."""
    blocks = result.document.blocks
    chunks: list[PlannedChunk] = []
    silent: list[int] = []
    for chapter in result.chapters:
        if not chapter.selected:
            continue
        previous: int | None = None  # block of the previous spoken utterance
        pause_edit = False
        before = len(chunks)
        for utterance in chapter.utterances:
            if utterance.pause:
                pause_edit = True
                continue
            block = utterance.span.block
            if previous is None or block != previous:
                kind = (
                    Pause.HEADING
                    if previous is not None and blocks[previous].kind is BlockKind.HEADING
                    else Pause.PARAGRAPH
                )
            elif utterance.continues:
                kind = Pause.CLAUSE
            else:
                kind = Pause.SENTENCE
            if pause_edit:
                kind = Pause.strongest(Pause.PAUSE_EDIT, kind)
            key = chunk_key(
                utterance.text, voice, speed, engine, engine_version, letter_speed=letter_speed
            )
            chunks.append(PlannedChunk(utterance, chapter.chapter.index, key, kind))
            previous, pause_edit = block, False
        if len(chunks) == before:
            silent.append(chapter.chapter.index)
    return AudioPlan(tuple(chunks), tuple(silent))


def assemble(
    plan: AudioPlan,
    durations: dict[str, float],
    titles: dict[int, str],
) -> tuple[list[Chapter], list[Spoken]]:
    """Output's chapters and spoken chunks from the plan, leaving out every chunk without
    audio (a skipped utterance); its pause carries over to the next chunk, so a skipped
    paragraph start still gives the paragraph pause.

    A chunk `continues` the chunk before it when it and every skipped chunk between them go
    on with a cut sentence (#480): a skipped sentence start breaks the join. A chapter's
    first chunk continues nothing."""
    chapters: list[Chapter] = []
    spoken: list[Spoken] = []
    carried = Pause.NONE
    linked = False  # every chunk since the last one spoken went on with its sentence
    current: int | None = None
    for chunk in plan.chunks:
        if chunk.chapter != current:
            current, carried, linked = None, Pause.NONE, False
        linked = linked and chunk.utterance.continues
        if chunk.key not in durations:
            carried = Pause.strongest(carried, chunk.pause)
            continue
        if current is None:
            current = chunk.chapter
            chapters.append(Chapter(titles[chunk.chapter], len(spoken)))
        audio = AudioChunk(chunk.utterance.span, chunk.file, durations[chunk.key])
        pause = Pause.strongest(carried, chunk.pause)
        spoken.append(Spoken(audio, pause, chunk.utterance.text, linked))
        carried, linked = Pause.NONE, True
    return chapters, spoken


def book_info(document: Document) -> BookInfo:
    """The book's title, authors and language for the files' metadata (the cover is
    `write_cover`'s)."""
    return BookInfo(
        title=document_title(document),
        authors=tuple(a for a in document.content.metadata.authors if a.strip()),
        language=document.language or "en",
    )


def write_cover(source: Path, work: Path) -> Path | None:
    """The source's cover image written to the working folder, or None (D-313).

    None for a file type or file without a usable cover, and for a cover that cannot be
    read or written: a missing cover never stops a job. A cover left by an earlier run is
    removed first, so the audiobook never shows the cover of another file.
    """
    for name in COVER_NAMES:
        with contextlib.suppress(OSError):
            (work / name).unlink(missing_ok=True)
    find = COVERS.get(source.suffix.lower())
    if find is None:
        return None
    try:
        cover = find(source)
    except Exception:  # the cover functions give None on any damage; a bug must not stop the job
        return None
    if cover is None:
        return None
    target = work / f"cover{cover.suffix}"
    try:
        write_bytes_atomically(target, cover.data, overwrite=True)
    except OSError:
        return None
    return target


def usable_cover(cover: Path | None, exe: Path) -> Path | None:
    """`cover` if ffmpeg can decode it, else None and the file removed (D-313).

    `Cover` checks only the first bytes; a damaged image behind a good signature would make
    ffmpeg refuse the first MP3 after all the speech. Decoding its first frame now, before
    any speech, finds that out in a fraction of a second.
    """
    if cover is None:
        return None
    try:
        Ffmpeg(exe).run([*LOCAL_ONLY, "-i", str(cover), "-frames:v", "1", "-f", "null", "-"])
    except (FfmpegError, OSError):
        with contextlib.suppress(OSError):
            cover.unlink(missing_ok=True)
        return None
    return cover


def audiobook_files(
    out_folder: Path, book: BookInfo, titles: Sequence[str], settings: OutputSettings
) -> list[Path]:
    """The files `write_audiobook` writes for these chapters, named as it names them
    (`output.audiobook_targets`, a name the file system refuses retried, #493)."""
    named = audiobook_targets(out_folder, book.title, titles, settings)
    return [*named.mp3s, *([named.m4b] if named.m4b else []), *named.subtitles, named.readalong]


# ---- running -------------------------------------------------------------------------


@dataclass(frozen=True)
class _CancellableFfmpeg(Ffmpeg):
    """Runs the given ffmpeg, stopping the feed when the job is cancelled; output then
    removes its partial file (D-119)."""

    inner: Ffmpeg | None = None
    cancel: threading.Event | None = None

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        runner = self.inner or Ffmpeg(self.exe)
        return runner.run(args, self._watched(feed))

    def _watched(self, feed: Iterable[bytes]) -> Iterator[bytes]:
        for piece in feed:
            _check_cancel(self.cancel)
            yield piece


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise JobCancelledError("the job was cancelled; finished parts are kept for a rerun")


@dataclass
class _Speech:
    """The speaking phase's counters and the speed measurement (D-159)."""

    clock: Callable[[], float]
    chunks_total: int
    characters_total: int
    chapters: int
    last_of_chapter: dict[int, int]  # chapter -> index of its last chunk
    chapter_chunks: dict[int, int] = field(default_factory=dict)  # chapter -> its chunks
    chapter_chunks_done: dict[int, int] = field(default_factory=dict)  # ... of them done
    chunks_done: int = 0
    reused: int = 0
    spoken: int = 0
    characters_done: int = 0
    estimate: Estimate = field(default_factory=Estimate)
    calls: int = 0  # voice calls that spoke a chunk in this run
    first_chapter: int | None = None  # chapter of the first chunk spoken in this run
    first_chapter_done: bool = False
    durations: dict[str, float] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    failures_in_a_row: int = 0

    def speed(self) -> float | None:
        return self.estimate.speed()

    def seconds_left(self) -> float | None:
        """The cost model summed over the chunks still to speak (D-380, D-384); None
        while the first chapter is spoken and until enough characters are measured (D-159,
        D-382)."""
        if (
            not self.first_chapter_done
            or self.estimate.measured_characters < ESTIMATE_MIN_CHARACTERS
        ):
            return None
        return self.estimate.seconds_left()

    def progress(
        self, chunk: PlannedChunk, title: str, index: int, playable: tuple[int, ...]
    ) -> AudioProgress:
        """The progress after the chunk at `index` in the plan."""
        order = list(self.last_of_chapter)  # the chapters in the order their chunks come
        return AudioProgress(
            Phase.SPEAKING,
            chapter=chunk.chapter,
            chapter_title=title,
            chapters=self.chapters,
            chapter_number=order.index(chunk.chapter) + 1,
            chapter_done=self.last_of_chapter[chunk.chapter] == index,
            chapter_chunks_done=self.chapter_chunks_done.get(chunk.chapter, 0),
            chapter_chunks_total=self.chapter_chunks.get(chunk.chapter, 0),
            chunks_done=self.chunks_done,
            chunks_total=self.chunks_total,
            reused=self.reused,
            characters_done=self.characters_done,
            characters_total=self.characters_total,
            characters_per_second=self.speed(),
            seconds_left=self.seconds_left(),
            playable=playable,
        )


def _cached_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def run_audio_job(
    source: Path,
    settings: JobSettings,
    work: Path,
    *,
    voice: VoiceSource,
    output_settings: OutputSettings | None = None,
    overwrite: bool = False,
    keep_settings: bool = False,
    progress: Callable[[AudioProgress], None] | None = None,
    cancel: threading.Event | None = None,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    max_chars: int = DEFAULT_MAX_CHARS,
    ffmpeg: Ffmpeg | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> AudioJob:
    """Turn `source` into an audiobook in the output folder; see the module docstring.

    `work` is the job's own working folder (made if missing; it holds the chunk cache and
    the records). Without `output_settings` the job writes the chapters' MP3s and the
    read-along file, no M4B (`JOB_OUTPUT`). Existing audiobook files are replaced only with
    `overwrite`, checked before any speech; the job's own files of an unfinished run are
    reused or replaced without it (#723).

    Chapters chosen beyond those the project has made are added to them (#726): the made
    ones are reused, only the new ones spoken. Made under other settings, the job raises
    SettingsChangedError before any speech, unless `keep_settings` (the new chapters are
    made with the settings the others were made with: only the chapter choice and the
    output folder are taken from `settings`) or `overwrite` (every chapter made anew).

    Raises JobError (or a subclass) when the job cannot go on; JobCancelledError when
    `cancel` is set. Only whole chapters are left.
    """
    tell: Callable[[AudioProgress], None] = progress or (lambda event: None)
    keep_settings = keep_settings and not overwrite
    if not keep_settings:
        _check_voice_name(settings, voice)
    check_readable(source)
    out_folder = (settings.output_folder or source.absolute().parent).absolute()
    check_folders((out_folder, work))
    _check_cancel(cancel)
    with work_folder_lock(work):
        record = read_record(work)

        def read(settings: JobSettings) -> Document:
            document = read_document(
                source,
                settings,
                lambda phase: tell(AudioProgress(phase)),
                pages=lambda page, pages: tell(
                    AudioProgress(Phase.READING, page=page, pages=pages)
                ),
                cancel=cancel,
            )
            # a PDF that is mostly glyph numbers is not voiced: nothing is spoken or
            # written (#442)
            found = unreadable(document.content)
            if found is not None and found.stops:
                raise UnreadableTextError(stop_message(source.name, found))
            return document

        document = read(settings)
        # the working folder's record is this book's, or another book's whose files are
        # its own and whose settings are never this book's (#726)
        same = record is not None and _same_book(record, book_info(document), out_folder)
        if keep_settings and same:
            assert record is not None  # noqa: S101 (same implies a record)
            given = settings
            settings, output_settings, steps = _kept(record, settings, output_settings, steps)
            _check_voice_name(settings, voice)
            if settings.language != given.language:  # the layout follows the language
                document = read(settings)
        elif keep_settings:
            _check_voice_name(settings, voice)
        # the person's choice of subtitles is a job setting (D-606); output writes them
        output_settings = replace(output_settings or JOB_OUTPUT, subtitles=settings.subtitles)
        # the voice follows the job's language (D-469); its files must be there (D-468)
        voice_id = voice.voice_for(settings.voice, document.language)
        if not voice.installed(voice_id):
            raise JobError(
                f"the voice is not set up: the files of voice {voice_id!r} (language "
                f"{voice.languages.get(voice_id, document.language)}) are not installed; "
                "run the voice download for that language"
            )
        book = book_info(document)
        made = {
            "settings": {k: v for k, v in settings_data(settings).items() if k != "chapters"},
            "voice": [voice.engine, voice.version_of(voice_id), voice_id],
            "output": dataclasses.asdict(output_settings),
            "book": [book.title, list(book.authors), book.language],
        }
        # the chapter choice is not part of the key: adding chapters keeps the settings (#726)
        key = settings_key(made)
        chosen, ignored = selected(find_chapters(document), settings.chapters)
        order = "book" if list(chosen) == sorted(chosen) else "chosen"
        owned = record.owned(out_folder) if record is not None else set()
        union = _adding(
            record if same else None, owned, key, made, chosen, order, overwrite, keep_settings
        )
        if union is not None:
            settings = replace(settings, chapters=union)
        tell(AudioProgress(Phase.TEXT_STEPS))
        result = prepare_script(document, settings, steps, max_chars)
        # the union holds only chapters the document has: the numbers it does not have are
        # the person's choice, reported as in a fresh run (#810)
        result = replace(result, ignored_chapters=ignored)
        plan = plan_audio(
            result,
            engine=voice.engine,
            engine_version=voice.version_of(voice_id),
            voice=voice_id,
            speed=settings.speed,
            letter_speed=settings.letter_speed,
        )
        if not plan.chunks:
            raise JobError("there is nothing to read in the chosen chapters")
        titles = {chapter.chapter.index: chapter.chapter.title for chapter in result.chapters}
        # D-903: in printed order a chapter is numbered by its place among the book's
        # chapters with something to say, so its files stay the same when others are added;
        # in an order the person chose (#119) by its place among the chosen
        if order == "book":
            places = speakable(result, max_chars)
        else:
            places = tuple(dict.fromkeys(chunk.chapter for chunk in plan.chunks))
        numbers = {index: n for n, index in enumerate(places, start=1)}
        try:
            run = _CancellableFfmpeg(
                (ffmpeg or Ffmpeg(find_ffmpeg())).exe, inner=ffmpeg, cancel=cancel
            )
        except FfmpegNotFoundError as error:
            raise JobError(str(error)) from error
        book = replace(book, cover=usable_cover(write_cover(source, work), run.exe))
        book_plan = _BookPlan.of(plan, titles, book, output_settings, numbers, len(places))
        found_files = _check_targets(
            work, out_folder, book_plan, record, owned, key, overwrite, adding=union is not None
        )
        _check_cancel(cancel)

        chapters = _Chapters(
            work,
            out_folder,
            book_plan,
            ChapterRecord(False, key, book_plan.order, order=order, made=made),
            found_files,
            run,
            overwrite,
            tell,
            result.document,
        )
        speech = _speak(
            plan,
            work,
            voice,
            voice_id,
            (settings.speed, settings.letter_speed),
            titles,
            tell,
            cancel,
            clock,
            chapters,
        )
        if chapters.writer is None:
            raise JobError("the voice could not speak any of the chosen chapters")

        tell(
            AudioProgress(Phase.ENCODING, chapters=len(chapters.added), playable=chapters.playable)
        )
        written = chapters.finish()
        skipped = _skipped(result, plan, speech)
        record = _record(result, settings, voice, voice_id, plan, speech, skipped, written, work)
        files = _write_records(work, result.document, record)
        chapters.complete()
        tell(AudioProgress(Phase.DONE, chapters=len(chapters.added), playable=chapters.playable))
        return AudioJob(
            result=result,
            written=written,
            spoken=speech.spoken,
            reused=speech.reused,
            skipped=skipped,
            duration=record["duration"],
            characters_per_second=speech.speed(),
            record=files[0],
            document_file=files[1],
        )


@dataclass(frozen=True)
class _BookPlan:
    """The chapters the job is to speak, in the order read, with their numbers in the book
    (counted from 1: the number in a chapter's file name and track tag, D-903), the book's
    chapter count and their chunks."""

    order: tuple[int, ...]  # job chapter indices
    titles: dict[int, str]
    chunks: dict[int, tuple[PlannedChunk, ...]]
    book: BookInfo
    settings: OutputSettings
    numbers: dict[int, int]
    count: int

    @classmethod
    def of(
        cls,
        plan: AudioPlan,
        titles: dict[int, str],
        book: BookInfo,
        settings: OutputSettings,
        numbers: dict[int, int],
        count: int,
    ) -> _BookPlan:
        chunks: dict[int, list[PlannedChunk]] = {}
        for chunk in plan.chunks:
            chunks.setdefault(chunk.chapter, []).append(chunk)
        return cls(
            tuple(chunks),
            titles,
            {index: tuple(c) for index, c in chunks.items()},
            book,
            settings,
            numbers,
            count,
        )

    def number(self, index: int) -> int:
        """Chapter `index`'s number in the book."""
        return self.numbers[index]

    def place(self, index: int) -> int:
        """Chapter `index`'s place among the job's chapters, counted from 1."""
        return self.order.index(index) + 1

    def planned_titles(self) -> list[str]:
        return [self.titles[index] for index in self.order]

    def planned_numbers(self) -> list[int]:
        return [self.numbers[index] for index in self.order]

    def targets(self, out_folder: Path) -> Written:
        return audiobook_targets(
            out_folder,
            self.book.title,
            self.planned_titles(),
            self.settings,
            self.planned_numbers(),
            self.count,
        )

    def chapter_files(self, out_folder: Path, index: int) -> set[str]:
        """The names of chapter `index`'s files: its MP3 and its subtitle pair."""
        targets = self.targets(out_folder)
        place = self.place(index)
        if not targets.mp3s:
            return set()
        names = {targets.mp3s[place - 1].name}
        if self.settings.subtitles:
            names |= {p.name for p in targets.subtitles[2 * (place - 1) : 2 * place]}
        return names

    def spoken(self, work: Path, index: int, keys: Collection[str] | None) -> list[Spoken]:
        """Chapter `index`'s spoken chunks, timed from their cached files; `keys` the chunks
        with audio (None: every chunk, all of which must be cached)."""
        chunks = self.chunks[index]
        durations = {
            c.key: _cached_duration(work / c.file) for c in chunks if keys is None or c.key in keys
        }
        _, spoken = assemble(AudioPlan(chunks, ()), durations, self.titles)
        return spoken

    def fingerprint(self, index: int, spoken: Sequence[Spoken]) -> str:
        return chapter_fingerprint(
            self.book,
            self.titles[index],
            self.number(index),
            self.count,
            spoken,
            self.settings,
        )


@dataclass(frozen=True)
class _Found:
    """What the output folder holds of this job before it starts: the chapters whose files
    it can take as they are, and the files that are its own to replace (#723)."""

    reuse: dict[int, PlayableChapter]
    keep: frozenset[str]
    record: ChapterRecord | None


def _check_voice_name(settings: JobSettings, voice: VoiceSource) -> None:
    if settings.voice and settings.voice not in voice.voices:
        raise JobError(f"there is no {voice.engine} voice {settings.voice!r}; choose another voice")


def _same_book(record: ChapterRecord, book: BookInfo, out_folder: Path) -> bool:
    """True if the chapter record is of this book (its title and authors). A version 1
    record keeps no book details, but its files carry the book's name, as this job's
    would: `<book> - NN <title>.mp3`, `<book>.readalong.json`, `<book>.m4b`."""
    if record.made is not None:
        return list(record.made.get("book", [])[:2]) == [book.title, list(book.authors)]
    named = audiobook_targets(out_folder, book.title, [book.title], OutputSettings())
    base = named.readalong.name.removesuffix(".readalong.json")
    files = [*record.book, *record.pending, *(f for c in record.chapters for f in c.files)]
    return any(
        f.name.startswith(f"{base} - ") or f.name in (named.readalong.name, f"{base}.m4b")
        for f in files
    )


def kept_settings(work: Path, settings: JobSettings) -> JobSettings:
    """The settings the project's chapters were made with, read from the working folder's
    record (#783): only `settings`' chapter choice and output folder are kept from it. The
    settings as given if the project has no chapters; raises OutputExistsError if the
    record can't bring them back, as a job that keeps them does."""
    record = read_record(work)
    if record is None or not record.chapters:
        return settings
    kept, _, _ = _kept(record, settings, None, ())
    return kept


def _kept(
    record: ChapterRecord | None,
    settings: JobSettings,
    output_settings: OutputSettings | None,
    steps: Sequence[TextStep],
) -> tuple[JobSettings, OutputSettings | None, Sequence[TextStep]]:
    """The settings the project's chapters were made with, for a job that keeps them
    (#726): only the chapter choice and the output folder are this job's. A project with
    no chapters made keeps nothing: the job's own settings."""
    if record is None or not record.chapters:
        return settings, output_settings, steps
    if record.made is None:  # a version 1 record holds only their hash
        raise OutputExistsError(
            "the chapters made so far were made by an earlier version of sci2audio, which "
            "did not keep their settings; choose to replace them"
        )
    data, output = record.made["settings"], record.made["output"]
    try:
        kept = JobSettings(
            language=data["language"],
            switched_off=frozenset(Category(c) for c in data["switched_off"]),
            chapters=settings.chapters,
            voice=data["voice"],
            speed=data["speed"],
            letter_pace=data["letter_pace"],
            subtitles=output["subtitles"],
            plugins=data.get("plugins", True),
            output_folder=settings.output_folder,
        )
        kept_output = OutputSettings(**output)
    except (KeyError, TypeError, ValueError) as error:
        raise OutputExistsError(
            "the settings the chapters made so far were made with cannot be read; "
            "choose to replace them"
        ) from error
    if not kept.plugins:  # as the runner leaves them out (#667)
        steps = tuple(step for step in steps if getattr(step, "plugin", None) is None)
    return kept, kept_output, steps


def _adding(
    record: ChapterRecord | None,
    owned: Collection[str],
    key: str,
    made: dict[str, Any],
    chosen: Sequence[int],
    order: str,
    overwrite: bool,
    kept: bool = False,
) -> tuple[int, ...] | None:
    """The chapters the job makes when it adds to the chapters the project has made
    (#726): those and the chosen ones, in printed order. None when there is nothing to add
    to (no chapter made, `overwrite`) or nothing to add to a finished audiobook (D-163).
    Checked before any speech: made under other settings (SettingsChangedError), made by a
    version that kept no settings, or read in an order the person chose (#119), the
    project is not added to without `overwrite`. With the settings `kept`, what still
    differs is what keeping cannot bring back (the voice's version). `record` is this
    book's (`_same_book`): another book's adds nothing, and its files are checked as any
    other files."""
    if overwrite or record is None:
        return None
    generated = {
        c.index for c in record.chapters if c.files and {f.name for f in c.files} <= set(owned)
    }
    if not generated:
        return None
    if record.made is None:
        raise OutputExistsError(
            "the chapters made so far were made by an earlier version of sci2audio, which "
            "did not keep their settings; choose to replace them"
        )
    if record.settings != key:
        if kept:
            changes = "; ".join(settings_changes(record.made, made))
            raise OutputExistsError(
                f"the chapters made so far cannot be matched: {changes}; choose to replace them"
            )
        raise SettingsChangedError(record.made, made)
    if record.order == "chosen" or order == "chosen":
        if tuple(chosen) != record.planned:
            raise OutputExistsError(
                "chapters are added only to an audiobook read in printed order, and this one "
                "is read in the order chosen; choose to replace them"
            )
        return None
    if record.complete and set(chosen) <= generated:
        return None
    return tuple(sorted({*chosen, *generated}))


def _check_targets(
    work: Path,
    out_folder: Path,
    plan: _BookPlan,
    record: ChapterRecord | None,
    owned: Collection[str],
    key: str,
    overwrite: bool,
    *,
    adding: bool,
) -> _Found:
    """Refuse, before any speech, to replace an existing audiobook without `overwrite`
    (D-163; output checks again when it writes, D-119). A file the working folder's
    chapter record names, unchanged, from an unfinished run under the same settings, or
    from a finished one the job adds chapters to (#726), is the job's own (#723): a chapter
    whose files are all such and whose fingerprint is the same is reused, any other such
    file is replaced."""
    same = record is not None and record.settings == key
    owned = set(owned) if same else set()
    if not overwrite:
        if record is not None and record.complete and not adding:
            owned = set()  # a finished audiobook is replaced only with overwrite (D-163)
        targets = plan.targets(out_folder)
        names = [*targets.mp3s, *([targets.m4b] if targets.m4b else []), *targets.subtitles]
        names.append(targets.readalong)
        if existing := [p.name for p in names if p.exists() and p.name not in owned]:
            raise OutputExistsError(
                f"these files exist already: {', '.join(existing)}; choose to replace them"
            )
    reuse: dict[int, PlayableChapter] = {}
    if record is not None and same:
        for chapter in record.chapters:
            if chapter.index not in plan.order or chapter.number != plan.number(chapter.index):
                continue
            files = {f.name for f in chapter.files}
            if files != plan.chapter_files(out_folder, chapter.index) or not files <= owned:
                continue
            try:
                spoken = plan.spoken(work, chapter.index, None)
            except (OSError, EOFError, wave.Error):
                continue  # a chunk is missing from the cache: the chapter is spoken again
            if plan.fingerprint(chapter.index, spoken) == chapter.fingerprint:
                reuse[chapter.index] = chapter
    return _Found(reuse, frozenset(owned), record if same else None)


def _standing(work: Path, out_folder: Path, plan: _BookPlan, found: _Found) -> tuple[int, ...]:
    """The chapters playable before this run puts its first file in place (#1065): the
    ones it takes as they are, in its order, if the earlier run's book still stands whole.
    Until then the Listen page plays that book, and only as a whole: every file its record
    names, as recorded, with this book's read-along file among them (and its `audio.json`
    once it was finished). Otherwise none, so the job never reports a chapter the page
    cannot open."""
    old = found.record
    if old is None or not found.reuse:
        return ()
    files = [*old.book, *(f for c in old.chapters for f in c.files)]
    readalong = plan.targets(out_folder).readalong.name
    if (
        not all(c.files for c in old.chapters)
        or not all(f.name in found.keep for f in files)
        or readalong not in {f.name for f in old.book}
        or (old.complete and not (work / RECORD).is_file())
    ):
        return ()
    return tuple(index for index in plan.order if index in found.reuse)


class _Chapters:
    """Writes each chapter's files as soon as its last chunk is spoken, and keeps the
    chapter record (`playable.py`) one step ahead of the files (#723)."""

    def __init__(
        self,
        work: Path,
        out_folder: Path,
        plan: _BookPlan,
        record: ChapterRecord,
        found: _Found,
        ffmpeg: _CancellableFfmpeg,
        overwrite: bool,
        tell: Callable[[AudioProgress], None],
        document: Document,
    ) -> None:
        self.work = work
        self.document = document
        self.out_folder = out_folder
        self.plan = plan
        self.found = found
        self.ffmpeg = ffmpeg
        self.overwrite = overwrite
        self.tell = tell
        self.record = record
        self.writer: BookWriter | None = None
        self.added: list[int] = []
        self.rates: set[int] = set()
        self.in_book = False  # writing the book's files (the M4B and its subtitles)
        self.placing: set[str] = set()  # book files vouched for, maybe not yet in place
        self.standing = _standing(work, out_folder, plan, found)

    @property
    def playable(self) -> tuple[int, ...]:
        if self.writer is None:
            return self.standing
        return tuple(c.index for c in self.record.chapters)

    def done(self, index: int, keys: Collection[str], event: AudioProgress) -> None:
        """Chapter `index` is spoken (`keys`: its chunks with audio): write its files, record
        them and tell the listener."""
        try:
            spoken = self.plan.spoken(self.work, index, keys)
        except (OSError, EOFError, wave.Error) as error:
            raise JobError("a cached audio chunk became unreadable") from error
        if not spoken:
            return  # the voice failed on every sentence: the chapter gets no file (D-162)
        self._check_rates(spoken)
        number = self.plan.number(index)
        fingerprint = self.plan.fingerprint(index, spoken)
        reused = self.found.reuse.get(index)
        written = reused is not None and reused.fingerprint == fingerprint
        try:
            writer = self._writer()
            # the chunk list the whole book is built from later (#725), before the files
            spoken_sha = write_spoken(self.work, index, spoken)
            writer.add(self.plan.place(index), spoken, written=written)
        except Exception as error:
            raise _encode_error(error, self.out_folder) from error
        if written and reused is not None:
            files = reused.files
        else:
            files = tuple(self.record.newest_pending().values())
        names = self.plan.chapter_files(self.out_folder, index)
        chapter = PlayableChapter(
            index,
            self.plan.titles[index],
            number,
            fingerprint,
            tuple(f for f in files if f.name in names),
            spoken_sha,
        )
        self._save(self._placed(self.record.with_chapter(chapter)))
        self.added.append(index)
        self.tell(dataclasses.replace(event, ready=index, playable=self.playable))

    def finish(self) -> Written:
        """The M4B and the book's subtitles when asked for, and the final read-along file."""
        assert self.writer is not None  # noqa: S101 (finish follows a chapter)
        self.in_book = True
        try:
            return self.writer.finish()
        except Exception as error:
            raise _encode_error(error, self.out_folder) from error

    def complete(self) -> None:
        self._save(dataclasses.replace(self._placed(self.record), complete=True))

    def _placed(self, record: ChapterRecord) -> ChapterRecord:
        """`record` once the book's files vouched for since the last step are in place."""
        record = record.with_book_files(self.placing)
        self.placing = set()
        return record

    def _writer(self) -> BookWriter:
        if self.writer is None:
            # the old records vouch for a finished audiobook (D-119): they go before the
            # first file of this run is put in place. The new laid-out document comes now,
            # so a page can read along in the chapters as they become playable (#724)
            _remove_old_records(self.work)
            _write_document(self.work, self.document)
            base = self.record
            if self.found.record is not None:  # an earlier run's files stay ours
                old = self.found.record
                kept = [*old.book, *old.pending, *(f for c in old.chapters for f in c.files)]
                for file in kept:
                    if file.name in self.found.keep:
                        base = base.with_pending(file)
                # a whole-book file built from its chapters stays the project's (#725)
                base = replace(
                    base, built=tuple(b for b in old.built if b.file.name in self.found.keep)
                )
            self._save(base)
            try:
                self.out_folder.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise _encode_error(error, self.out_folder) from error
            self.writer = BookWriter(
                self.work,
                self.out_folder,
                self.plan.book,
                self.plan.planned_titles(),
                self.plan.settings,
                ffmpeg=self.ffmpeg,
                overwrite=self.overwrite,
                keep=[self.out_folder / name for name in self.found.keep],
                vouch=self._vouch,
                numbers=self.plan.planned_numbers(),
                count=self.plan.count,
            )
        return self.writer

    def _vouch(self, target: Path, size: int, sha256: str) -> None:
        file = RecordedFile(target.name, size, sha256)
        assert self.writer is not None  # noqa: S101 (output vouches while writing)
        # the record keeps the entry for the file now in place until the step is done:
        # a stop before the rename leaves that file, which a rerun must still take as its own
        if self.in_book or target.name == self.writer.targets.readalong.name:
            self.placing.add(target.name)
        self._save(self.record.with_pending(file))

    def _save(self, record: ChapterRecord) -> None:
        try:
            write_record(self.work, record)
        except OSError as error:
            raise JobError(
                f"could not write the job's chapter record: {error.strerror or error}"
            ) from error
        self.record = record

    def _check_rates(self, spoken: Sequence[Spoken]) -> None:
        """All chunks at one sample rate (D-117). They are, unless the cache holds chunks
        of an engine that changed its rate without changing its version; then cleaning
        helps, and a plain rerun would only fail the same way."""
        for file in dict.fromkeys(s.chunk.file for s in spoken):
            try:
                with wave.open(str(self.work / file), "rb") as audio:
                    self.rates.add(audio.getframerate())
            except (OSError, EOFError, wave.Error):
                continue  # output names a missing or broken chunk itself
        if len(self.rates) > 1:
            raise JobError(
                "the working folder holds audio at different sample rates "
                f"({sorted(self.rates)} Hz); remove its chunks (clean the working folder) "
                "and run the job again"
            )


def _speak(
    plan: AudioPlan,
    work: Path,
    voice: VoiceSource,
    voice_id: str,
    speeds: tuple[float, float],  # the speed and the letter speed (#295)
    titles: dict[int, str],
    tell: Callable[[AudioProgress], None],
    cancel: threading.Event | None,
    clock: Callable[[], float],
    chapters: _Chapters,
) -> _Speech:
    """Speak every chunk not yet in the cache, and have each chapter written as soon as its
    last chunk is done; the engine is made only if a chunk is missing."""
    try:
        remove_partials(work)
        needed: dict[str, int] = {}  # key -> characters, in order
        for chunk in plan.chunks:
            if chunk.key not in needed and not is_finished(work / chunk.file):
                needed[chunk.key] = len(chunk.utterance.text)
    except OSError as error:
        raise JobError(f"could not read the working folder: {error.strerror or error}") from error
    last_of_chapter = {chunk.chapter: index for index, chunk in enumerate(plan.chunks)}
    speech = _Speech(
        clock=clock,
        chunks_total=len(plan.chunks),
        characters_total=sum(needed.values()),
        chapters=len(last_of_chapter),
        last_of_chapter=last_of_chapter,
        chapter_chunks=dict(Counter(chunk.chapter for chunk in plan.chunks)),
    )
    for characters in needed.values():
        speech.estimate.expect(characters)
    engine: Engine | None = None
    session: EngineSession | None = None
    try:
        if needed:
            tell(
                AudioProgress(
                    Phase.LOADING_VOICE, chapters=speech.chapters, playable=chapters.playable
                )
            )
            engine, session = _load(voice)
        tell(
            AudioProgress(
                Phase.SPEAKING,
                chapters=speech.chapters,
                chunks_total=speech.chunks_total,
                characters_total=speech.characters_total,
                playable=chapters.playable,
            )
        )
        for index, chunk in enumerate(plan.chunks):
            _check_cancel(cancel)
            _one(chunk, work, needed, session, voice_id, speeds, speech)
            speech.chunks_done += 1
            done = speech.chapter_chunks_done
            done[chunk.chapter] = done.get(chunk.chapter, 0) + 1
            if speech.first_chapter is not None and index == last_of_chapter[speech.first_chapter]:
                speech.first_chapter_done = True
            event = speech.progress(chunk, titles[chunk.chapter], index, chapters.playable)
            tell(event)
            if event.chapter_done:
                chapters.done(chunk.chapter, speech.durations.keys(), event)
    finally:
        if session is not None:
            session.dispose()
        if engine is not None:
            voice.release(engine)
    return speech


def _load(voice: VoiceSource) -> tuple[Engine, EngineSession]:
    try:
        engine = voice.make()
    except ModelNotFoundError as error:
        raise JobError(f"the voice is not set up: {error}") from error
    except EngineError as error:
        raise JobError(f"the voice could not be loaded: {error}") from error
    try:
        return engine, engine.createSession()
    except EngineError as error:
        voice.release(engine)
        raise JobError(f"the voice could not be started: {error}") from error


def _one(
    chunk: PlannedChunk,
    work: Path,
    needed: dict[str, int],
    session: EngineSession | None,
    voice_id: str,
    speeds: tuple[float, float],
    speech: _Speech,
) -> None:
    """Speak one chunk, or take it from the cache or from earlier in this run."""
    key, path = chunk.key, work / chunk.file
    if key in speech.durations or key in speech.failed:
        speech.reused += key in speech.durations
        return
    if key not in needed:
        try:
            speech.durations[key] = _cached_duration(path)
        except (OSError, EOFError, wave.Error) as error:
            raise JobError(f"a cached audio chunk became unreadable: {path.name}") from error
        speech.reused += 1
        return
    assert session is not None  # noqa: S101 (made whenever a chunk is needed)
    text = chunk.utterance.text
    started = speech.clock()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        speed, letter_speed = speeds
        seconds = speak_to_wav(
            session, text, voice_id, path, speed=speed, letter_speed=letter_speed
        )
    except ModelNotFoundError as error:
        raise JobError(f"the voice is not set up: {error}") from error
    except EngineError as error:
        speech.failed[key] = str(error) or type(error).__name__
        speech.characters_done += len(text)
        speech.estimate.done(len(text))
        speech.failures_in_a_row += 1
        if speech.failures_in_a_row >= FAILURES_IN_A_ROW:
            raise JobError(
                f"the voice failed on {FAILURES_IN_A_ROW} sentences in a row, the last "
                f"with: {error}; the sentences spoken so far are kept for a rerun"
            ) from error
        return
    except OSError as error:
        raise JobError(
            f"could not write the voice's audio: {error.strerror or error}; "
            "the sentences spoken so far are kept for a rerun"
        ) from error
    elapsed = speech.clock() - started
    speech.durations[key] = seconds
    speech.spoken += 1
    speech.failures_in_a_row = 0
    speech.characters_done += len(text)
    speech.estimate.done(len(text))
    if speech.first_chapter is None:
        speech.first_chapter = chunk.chapter
    speech.calls += 1
    if speech.calls > WARM_UP_CALLS:  # the first calls warm the voice up (D-381)
        speech.estimate.measure(len(text), elapsed)


def _encode_error(error: Exception, out_folder: Path) -> Exception:
    """The JobError a person can act on for an error while writing the audiobook."""
    if isinstance(error, JobError):
        return error
    if isinstance(error, FileExistsError):
        return OutputExistsError(f"{error}; choose to replace them")
    if isinstance(error, ChunkAudioError):
        return JobError(f"{error}; run the job again to speak it anew")
    if isinstance(error, FfmpegError | OSError):
        if not out_folder.is_dir():
            return JobError(
                f"the output folder {out_folder.name} was removed during the run; "
                "the spoken audio is kept, run the job again"
            )
        if isinstance(error, FfmpegError):
            return JobError(f"could not write the audiobook: {error}")
        where = Path(str(error.filename)).name if error.filename else "the audiobook"
        return JobError(f"could not write {where}: {error.strerror or error}")
    return error


def _skipped(
    result: ScriptResult, plan: AudioPlan, speech: _Speech
) -> tuple[SkippedUtterance, ...]:
    pages = Pages(result.document)
    out = []
    for chunk in plan.chunks:
        if chunk.key in speech.failed:
            where = pages.where(chunk.utterance.span)
            out.append(
                SkippedUtterance(
                    chapter=chunk.chapter,
                    span=chunk.utterance.span,
                    page=where.page,
                    printed_page=where.printed_page,
                    text=chunk.utterance.text,
                    error=speech.failed[chunk.key],
                )
            )
    return tuple(out)


def _record(
    result: ScriptResult,
    settings: JobSettings,
    voice: VoiceSource,
    voice_id: str,
    plan: AudioPlan,
    speech: _Speech,
    skipped: tuple[SkippedUtterance, ...],
    written: Written,
    work: Path,
) -> dict[str, Any]:
    """`audio.json` (format "sci2audio-audio", version 1, D-165)."""
    source = result.document.content.source
    times = read_readalong(written.readalong)
    seconds = {}
    spoken = [chunk.chapter for chunk in plan.chunks if chunk.key in speech.durations]
    spoken_chapters = list(dict.fromkeys(spoken))
    for index, chapter in zip(spoken_chapters, times.chapters, strict=True):
        seconds[index] = round(chapter.end - chapter.start, 3)
    counts: dict[int, int] = {}
    for chunk in plan.chunks:
        if chunk.key in speech.durations:
            counts[chunk.chapter] = counts.get(chunk.chapter, 0) + 1
    speed = speech.speed()
    return {
        "format": RECORD_FORMAT,
        "version": RECORD_VERSION,
        "sci2audio": __version__,
        "source": {"name": source.name, "format": str(source.format), "sha256": source.sha256},
        "settings": settings_data(settings),
        "engine": voice.engine,
        "engine_version": voice.version_of(voice_id),
        "voice": voice_id,
        "speed": settings.speed,
        "duration": times.duration,
        "chapters": [
            {
                "index": chapter.chapter.index,
                "title": chapter.chapter.title,
                "selected": chapter.selected,
                "chunks": counts.get(chapter.chapter.index, 0),
                "seconds": seconds.get(chapter.chapter.index, 0.0),
            }
            for chapter in result.chapters
        ],
        "chunks": {
            "total": len(plan.chunks),
            "spoken": speech.spoken,
            "reused": speech.reused,
            "skipped": len(skipped),
        },
        "skipped": [
            {
                "chapter": item.chapter,
                "block": item.span.block,
                "start": item.span.start,
                "end": item.span.end,
                "page": item.page,
                "printed_page": item.printed_page,
                "text": item.text,
                "error": item.error,
            }
            for item in skipped
        ],
        "characters_per_second": None if speed is None else round(speed, 1),
        "cache_bytes": cache_size(work),
        "files": {
            "m4b": written.m4b.name if written.m4b else None,
            "mp3": [path.name for path in written.mp3s],
            "readalong": written.readalong.name,
            "subtitles": [path.name for path in written.subtitles],
        },
        # the plugins that made the script (#669); none: no key, so records read as before
        **(
            {
                "plugins": [
                    {"step": p.step, "distribution": p.distribution, "version": p.version}
                    for p in result.run.plugins
                ]
            }
            if result.run.plugins
            else {}
        ),
    }


def _remove_old_records(work: Path) -> None:
    """The records vouch for the audiobook: an old one must not outlive a rerun that fails
    while it replaces the files (as output does with its read-along file, D-119)."""
    try:
        (work / RECORD).unlink(missing_ok=True)
        (work / DOCUMENT).unlink(missing_ok=True)
    except OSError as error:
        raise JobError(
            f"could not replace the job's record in the working folder: {error.strerror or error}"
        ) from error


def _write_document(work: Path, document: Document) -> None:
    """`document.json` on its own, ahead of `audio.json` (#724)."""
    try:
        write_text_atomically(work / DOCUMENT, json_text(to_data(document)), overwrite=True)
    except OSError as error:
        raise JobError(
            f"could not write the job's record in the working folder: {error.strerror or error}"
        ) from error


def _write_records(work: Path, document: Document, record: dict[str, Any]) -> tuple[Path, Path]:
    """`audio.json` and `document.json` (the laid-out document, for the player, #78)."""
    files = (work / RECORD, work / DOCUMENT)
    try:
        write_texts(
            {files[1]: json_text(to_data(document)), files[0]: json_text(record)},
            overwrite=True,
        )
    except OSError as error:
        raise JobError(
            f"the audiobook is written, but its record could not be: {error.strerror or error}"
        ) from error
    return files
