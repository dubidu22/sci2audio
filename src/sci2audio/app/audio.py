"""The audio job: a file in, the audiobook out (#71, WI-02, WI-04, VA-04; closes #10).

file → script preparation (as the script job, in memory) → the voice speaks every
utterance of the chosen chapters into the working folder's chunk cache → output writes one
MP3 per chapter, the M4B and the read-along file → the job's records.

- Writes only the audiobook files into the output folder (D-154); the script and the
  report are the script job's.
- Resume (D-155, D-156): a chunk is cached under a key of its text, voice, speed and engine
  version; running the job again on the same working folder speaks only what is missing.
  All chapters are encoded again at the end (seconds, against minutes of speech).
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
import threading
import time
import wave
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from sci2audio import __version__
from sci2audio.app.chapters import document_title
from sci2audio.app.chunks import (
    cache_size,
    chunk_file,
    chunk_key,
    is_finished,
    remove_partials,
)
from sci2audio.app.estimate import Estimate
from sci2audio.app.files import write_bytes_atomically, write_texts
from sci2audio.app.job import (
    COVERS,
    JobCancelledError,
    JobError,
    OutputExistsError,
    Phase,
    check_folders,
    check_readable,
    json_text,
    read_document,
    settings_data,
)
from sci2audio.app.lock import work_folder_lock
from sci2audio.app.report import Pages
from sci2audio.app.script import ScriptResult, prepare_script
from sci2audio.app.settings import JobSettings
from sci2audio.app.voice import VoiceSource
from sci2audio.core import AudioChunk, BlockKind, Document, Span
from sci2audio.core.export import to_data
from sci2audio.output import (
    BookInfo,
    Chapter,
    ChunkAudioError,
    Ffmpeg,
    FfmpegError,
    FfmpegNotFoundError,
    OutputSettings,
    Pause,
    Spoken,
    Written,
    find_ffmpeg,
    names,
    read_readalong,
    write_audiobook,
)
from sci2audio.output.ffmpeg import LOCAL_ONLY
from sci2audio.textprep import BUILT_IN_STEPS, DEFAULT_MAX_CHARS, TextStep, Utterance
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
    chunks_done: int = 0
    chunks_total: int = 0
    reused: int = 0  # chunks found finished in the cache
    characters_done: int = 0
    characters_total: int = 0
    characters_per_second: float | None = None
    seconds_left: float | None = None


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
    result: ScriptResult, *, engine: str, engine_version: str, voice: str, speed: float
) -> AudioPlan:
    """The chunks of the chosen chapters with their pause kinds (D-116, D-157):
    PARAGRAPH for the first chunk of another block (HEADING after a heading), SENTENCE for
    the next sentence of one block, NONE where the length limit cut a sentence, and at
    least PAUSE_EDIT after a `pause` edit. A chapter's first chunk gets the chapter pause
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
                kind = Pause.NONE
            else:
                kind = Pause.SENTENCE
            if pause_edit:
                kind = Pause.strongest(Pause.PAUSE_EDIT, kind)
            key = chunk_key(utterance.text, voice, speed, engine, engine_version)
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
    paragraph start still gives the paragraph pause."""
    chapters: list[Chapter] = []
    spoken: list[Spoken] = []
    carried = Pause.NONE
    current: int | None = None
    for chunk in plan.chunks:
        if chunk.chapter != current:
            current, carried = None, Pause.NONE
        if chunk.key not in durations:
            carried = Pause.strongest(carried, chunk.pause)
            continue
        if current is None:
            current = chunk.chapter
            chapters.append(Chapter(titles[chunk.chapter], len(spoken)))
        audio = AudioChunk(chunk.utterance.span, chunk.file, durations[chunk.key])
        spoken.append(Spoken(audio, Pause.strongest(carried, chunk.pause)))
        carried = Pause.NONE
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
    """The files `write_audiobook` writes for these chapters (output's naming rules)."""
    base = names.book_name(book.title)
    files = []
    if settings.mp3:
        count = len(titles)
        files += [
            out_folder / names.chapter_file(base, n, count, title)
            for n, title in enumerate(titles, start=1)
        ]
    if settings.m4b:
        files.append(out_folder / f"{base}.m4b")
    files.append(out_folder / f"{base}.readalong.json")
    return files


# ---- running -------------------------------------------------------------------------


_Identity = tuple[int, int, int, int]  # device, inode, size, modification time (ns)


@dataclass(frozen=True)
class _CancellableFfmpeg(Ffmpeg):
    """Runs the given ffmpeg, stopping the feed when the job is cancelled; output then
    removes its partial file (D-119). Remembers the identity of every file ffmpeg finished
    (device, inode, size and modification time, which the rename into place keeps), so a
    failed run can tell its own files from anyone else's."""

    inner: Ffmpeg | None = None
    cancel: threading.Event | None = None
    finished: list[_Identity] = field(default_factory=list)

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        runner = self.inner or Ffmpeg(self.exe)
        printed = runner.run(args, self._watched(feed))
        with contextlib.suppress(OSError):  # the file it wrote is its last argument
            self.finished.append(_identity(Path(args[-1])))
        return printed

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

    def progress(self, chunk: PlannedChunk, title: str) -> AudioProgress:
        return AudioProgress(
            Phase.SPEAKING,
            chapter=chunk.chapter,
            chapter_title=title,
            chapters=self.chapters,
            chunks_done=self.chunks_done,
            chunks_total=self.chunks_total,
            reused=self.reused,
            characters_done=self.characters_done,
            characters_total=self.characters_total,
            characters_per_second=self.speed(),
            seconds_left=self.seconds_left(),
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
    progress: Callable[[AudioProgress], None] | None = None,
    cancel: threading.Event | None = None,
    steps: Sequence[TextStep] = BUILT_IN_STEPS,
    max_chars: int = DEFAULT_MAX_CHARS,
    ffmpeg: Ffmpeg | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> AudioJob:
    """Turn `source` into an audiobook in the output folder; see the module docstring.

    `work` is the job's own working folder (made if missing; it holds the chunk cache and
    the records). Existing audiobook files are replaced only with `overwrite`, checked
    before any speech. Raises JobError (or a subclass) when the job cannot go on;
    JobCancelledError when `cancel` is set. Nothing half-written is left.
    """
    tell: Callable[[AudioProgress], None] = progress or (lambda event: None)
    output_settings = output_settings or OutputSettings()
    voice_id = settings.voice or voice.default_voice
    if voice_id not in voice.voices:
        raise JobError(f"there is no {voice.engine} voice {voice_id!r}; choose another voice")
    check_readable(source)
    out_folder = (settings.output_folder or source.absolute().parent).absolute()
    check_folders((out_folder, work))
    _check_cancel(cancel)
    with work_folder_lock(work):
        document = read_document(source, settings, lambda phase: tell(AudioProgress(phase)))
        tell(AudioProgress(Phase.TEXT_STEPS))
        result = prepare_script(document, settings, steps, max_chars)
        plan = plan_audio(
            result,
            engine=voice.engine,
            engine_version=voice.version,
            voice=voice_id,
            speed=settings.speed,
        )
        if not plan.chunks:
            raise JobError("there is nothing to read in the chosen chapters")
        titles = {chapter.chapter.index: chapter.chapter.title for chapter in result.chapters}
        book = book_info(document)
        _check_targets(out_folder, book, plan, titles, output_settings, overwrite)
        try:
            run = _CancellableFfmpeg(
                (ffmpeg or Ffmpeg(find_ffmpeg())).exe, inner=ffmpeg, cancel=cancel
            )
        except FfmpegNotFoundError as error:
            raise JobError(str(error)) from error
        book = replace(book, cover=usable_cover(write_cover(source, work), run.exe))
        _check_cancel(cancel)

        speech = _speak(plan, work, voice, voice_id, settings.speed, titles, tell, cancel, clock)
        chapters, spoken = assemble(plan, speech.durations, titles)
        if not spoken:
            raise JobError("the voice could not speak any of the chosen chapters")

        tell(AudioProgress(Phase.ENCODING, chapters=len(chapters)))
        _remove_old_records(work)
        written = _encode(work, out_folder, chapters, spoken, book, output_settings, run, overwrite)
        skipped = _skipped(result, plan, speech)
        record = _record(result, settings, voice, voice_id, plan, speech, skipped, written, work)
        files = _write_records(work, result.document, record)
        tell(AudioProgress(Phase.DONE, chapters=len(chapters)))
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


def _check_targets(
    out_folder: Path,
    book: BookInfo,
    plan: AudioPlan,
    titles: dict[int, str],
    settings: OutputSettings,
    overwrite: bool,
) -> None:
    """Refuse, before any speech, to replace an existing audiobook without `overwrite`
    (D-163; output checks again when it writes, D-119)."""
    if overwrite:
        return
    chapters = list(dict.fromkeys(chunk.chapter for chunk in plan.chunks))
    targets = audiobook_files(out_folder, book, [titles[c] for c in chapters], settings)
    if existing := [path.name for path in targets if path.exists()]:
        raise OutputExistsError(
            f"these files exist already: {', '.join(existing)}; choose to replace them"
        )


def _speak(
    plan: AudioPlan,
    work: Path,
    voice: VoiceSource,
    voice_id: str,
    speed: float,
    titles: dict[int, str],
    tell: Callable[[AudioProgress], None],
    cancel: threading.Event | None,
    clock: Callable[[], float],
) -> _Speech:
    """Speak every chunk not yet in the cache; the engine is made only if one is missing."""
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
    )
    for characters in needed.values():
        speech.estimate.expect(characters)
    engine: Engine | None = None
    session: EngineSession | None = None
    try:
        if needed:
            tell(AudioProgress(Phase.LOADING_VOICE, chapters=speech.chapters))
            engine, session = _load(voice)
        tell(
            AudioProgress(
                Phase.SPEAKING,
                chapters=speech.chapters,
                chunks_total=speech.chunks_total,
                characters_total=speech.characters_total,
            )
        )
        for index, chunk in enumerate(plan.chunks):
            _check_cancel(cancel)
            _one(chunk, work, needed, session, voice_id, speed, speech)
            speech.chunks_done += 1
            if speech.first_chapter is not None and index == last_of_chapter[speech.first_chapter]:
                speech.first_chapter_done = True
            tell(speech.progress(chunk, titles[chunk.chapter]))
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
    speed: float,
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
        seconds = speak_to_wav(session, text, voice_id, path, speed=speed)
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


def _encode(
    work: Path,
    out_folder: Path,
    chapters: list[Chapter],
    spoken: list[Spoken],
    book: BookInfo,
    settings: OutputSettings,
    ffmpeg: _CancellableFfmpeg,
    overwrite: bool,
) -> Written:
    """`write_audiobook`, all or nothing for the files that are new: if it fails or is
    cancelled part-way (Ctrl-C included), every audiobook file this run put in place where
    none was before is removed again, so no half set is left and a rerun without
    `overwrite` is not refused. Only files ffmpeg wrote in this run are removed, never a
    file that appeared from elsewhere. With `overwrite`, files this run already replaced
    cannot be restored: the old versions are gone (output removes the old read-along file
    first, so it never vouches for a mixed set, D-119)."""
    _check_rates(work, spoken)
    targets = audiobook_files(out_folder, book, [c.title for c in chapters], settings)
    existed = {target for target in targets if target.exists()}
    try:
        return write_audiobook(
            work, out_folder, chapters, spoken, book, settings, ffmpeg=ffmpeg, overwrite=overwrite
        )
    except BaseException as error:
        _remove_new(targets, existed, ffmpeg.finished)
        if isinstance(error, Exception):
            raise _encode_error(error, out_folder) from error
        raise


def _remove_new(targets: list[Path], existed: set[Path], ours: list[_Identity]) -> None:
    for target in targets:
        if target in existed:
            continue
        with contextlib.suppress(OSError):
            if _identity(target) in ours:
                target.unlink()


def _identity(path: Path) -> _Identity:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


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


def _check_rates(work: Path, spoken: list[Spoken]) -> None:
    """All chunks at one sample rate (D-117). They are, unless the cache holds chunks of an
    engine that changed its rate without changing its version; then cleaning helps, and a
    plain rerun would only fail the same way."""
    rates = set()
    for file in dict.fromkeys(s.chunk.file for s in spoken):
        try:
            with wave.open(str(work / file), "rb") as audio:
                rates.add(audio.getframerate())
        except (OSError, EOFError, wave.Error):
            continue  # output names a missing or broken chunk itself
    if len(rates) > 1:
        raise JobError(
            f"the working folder holds audio at different sample rates ({sorted(rates)} Hz); "
            "remove its chunks (clean the working folder) and run the job again"
        )


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
        "engine_version": voice.version,
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
        },
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
