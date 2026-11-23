"""What each kind of job does, built on the app's jobs and the one voice download.

- script: the pre-analysis. `JobRunner.run_script` writes the script and report into the
  document's own `script/` folder, always replacing them: they are sci2audio's files,
  rewritten whenever the person changes a switch or the chapter choice (D-199).
- audio: `JobRunner.run_audio` (#71) into the person's output folder, never replacing
  an audiobook without `overwrite` (D-163, D-199); cancelled through its event (D-160).
- voices: `voices.download_voice_files`, the one download function (D-104, D-122),
  started only after consent (D-203). Cancelled by raising from its progress callback;
  the download removes the `.part` file of the file it was fetching (D-202).
- book: `JobRunner.run_book` (#725) builds the whole audiobook as one M4B or MP3 from the
  chapters made, into the folder they are in, or reuses the file built before; cancelled
  through its event, leaving no half file. The file joins the project's record (D-750).
- preview: one sentence with one voice at one speed into `<work_root>/preview/` (D-249),
  through `voices.speak_to_wav`, the call the audio job speaks with.

`KeptVoice` keeps one engine loaded after it was first needed, for previews and audio
jobs alike, until the server stops (D-250, as D-166 allows a server to do).

`classify` turns what a job raised into how it ends: an error kind for programs and the
app's own message for people.
"""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import json
import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, BinaryIO

from sci2audio import __version__
from sci2audio.app import (
    AudioProgress,
    BookProgress,
    JobBusyError,
    JobCancelledError,
    JobError,
    JobRunner,
    JobSettings,
    MissingChaptersError,
    OutputExistsError,
    Phase,
    UnreadableTextError,
    VoiceSource,
    find_chapters,
)
from sci2audio.app import UnsupportedFileError as AppUnsupportedFileError
from sci2audio.output import BookKind, Ffmpeg
from sci2audio.voices import (
    DownloadError,
    DownloadPlan,
    Engine,
    EngineError,
    NetworkError,
    download_voice_files,
    speak_to_wav,
)
from sci2audio.web.documents import StoredDocument
from sci2audio.web.jobs import JobCancelled, JobFailure, JobRecord, JobState
from sci2audio.web.library import about_of, write_about
from sci2audio.web.player import (
    Made,
    PlayerError,
    current_audiobook,
    load_document,
    recorded_position,
    remove_position,
    write_record,
)
from sci2audio.web.project import ProjectError, audiobook_folder, record_files

logger = logging.getLogger(__name__)

Fetch = Callable[[str, BinaryIO, Callable[[int], None]], None]
PREVIEW_FOLDER = "preview"  # in the work root; holds the latest preview only
PREVIEW_FILE = "preview.wav"


class KeptVoice:
    """One engine, made the first time a preview or an audio job needs it and kept until
    `dispose` (D-250). The sources it hands out make the kept engine and leave it loaded;
    the jobs run one at a time (D-200), so one engine is never used by two at once."""

    def __init__(self, source: Callable[[], VoiceSource]) -> None:
        self._source = source
        self._lock = threading.Lock()
        self._engine: Engine | None = None
        self._release: Callable[[Engine], None] | None = None

    def source(self) -> VoiceSource:
        base = self._source()

        def make() -> Engine:
            with self._lock:
                if self._engine is None:
                    self._engine = base.make()
                    self._release = base.release
                return self._engine

        return dataclasses.replace(base, make=make, release=lambda engine: None)

    @property
    def loaded(self) -> bool:
        with self._lock:
            return self._engine is not None

    def dispose(self) -> None:
        """Hand the engine back as its source says (default: dispose it); the next use
        makes a new one. Called when the server stops and after a job failed, so a broken
        engine is never kept."""
        with self._lock:
            engine, release = self._engine, self._release
            self._engine = self._release = None
        if engine is not None and release is not None:
            release(engine)


def script_work(
    runner: JobRunner, document: StoredDocument, settings: JobSettings
) -> Callable[[JobRecord], Sequence[Path]]:
    def work(job: JobRecord) -> Sequence[Path]:
        def progress(phase: Phase) -> None:
            job.report({"phase": str(phase)})

        def pages(page: int, total: int) -> None:  # a PDF's pages as they are read (#343)
            job.report({"phase": str(Phase.READING), "page": page, "pages": total})

        own = replace(settings, output_folder=document.script_folder)
        result = runner.run_script(
            document.source, own, document.folder, overwrite=True, progress=progress, pages=pages
        )
        # what the library lists (#389); writing it never fails the job
        write_about(document.folder, about_of(result.result.run.document))
        return result.files.outputs

    return work


def audio_progress(event: AudioProgress) -> dict[str, Any]:
    """An audio job's progress as the API and the events show it."""
    data = dataclasses.asdict(event)
    data["phase"] = str(event.phase)
    return data


def audio_work(
    runner: JobRunner,
    document: StoredDocument,
    settings: JobSettings,
    voice: VoiceSource,
    *,
    overwrite: bool,
    on_failure: Callable[[], None] = lambda: None,
) -> Callable[[JobRecord], Sequence[Path]]:
    """`settings.output_folder` must be set (the server fills in its default): the
    audiobook goes into the project's own folder in it (D-749). `on_failure` runs when the
    job fails (the server drops its kept engine)."""
    output = settings.output_folder
    if output is None:
        raise ValueError("the audio job needs an output folder")

    def work(job: JobRecord) -> Sequence[Path]:
        try:
            folder = audiobook_folder(document.folder, document.id, document.name, output)
        except ProjectError as error:
            raise JobError(str(error)) from error
        noted = False

        def progress(event: AudioProgress) -> None:
            nonlocal noted
            if event.playable and not noted:
                # the Listen page plays the chapters as they come (#724): it needs to know
                # what they are made with before the job's own record is written at the end
                noted = True
                _note_made(document, folder, settings, voice, runner)
            job.report(audio_progress(event))

        try:
            result = runner.run_audio(
                document.source,
                replace(settings, output_folder=folder),
                document.folder,
                voice=voice,
                overwrite=overwrite,
                progress=progress,
                cancel=job.cancel,
            )
        except (JobCancelledError, OutputExistsError, JobBusyError):
            raise  # the engine is fine
        except BaseException:
            # the app wraps a voice failure in a JobError like any other (app/audio.py), so
            # any failure drops the engine; a rare failure costs one reload (D-250)
            on_failure()
            raise
        job.report(
            {
                "phase": "done",
                "spoken": result.spoken,
                "reused": result.reused,
                "seconds": result.duration,
                "characters_per_second": result.characters_per_second,
                "skipped": [  # sentences the voice failed on, left out (D-162)
                    {
                        "chapter": skipped.chapter,
                        "page": skipped.page,
                        "printed_page": skipped.printed_page,
                        "text": skipped.text,
                        "error": skipped.error,
                    }
                    for skipped in result.skipped
                ],
            }
        )
        written = result.written
        try:
            # where the player finds the audiobook (D-295); the audiobook is complete
            # either way, and without the record the player looks in the saved and the
            # default output folder
            write_record(document.folder, document.id, written.readalong.parent)
        except OSError as error:
            logger.warning("could not note where the audiobook is: %s", error)
        try:
            # a new audiobook starts at the start (#153); a position kept while this one
            # was growing is in it, and stays (#724)
            _forget_other_position(document, written.readalong.parent)
        except OSError as error:  # its stamp no longer fits: the page ignores it anyway
            logger.warning("could not forget the listening position: %s", error)
        files = [
            *([written.m4b] if written.m4b else []),
            *written.mp3s,
            *written.subtitles,
            written.readalong,
        ]
        try:
            # every file this run wrote, with its hash, for removing the project (D-750);
            # without it the files are never deleted by sci2audio, only kept
            record_files(document.folder, document.id, written.readalong.parent, files)
        except OSError as error:
            logger.warning("could not record the audiobook's files: %s", error)
        return files

    return work


BOOK_STEP = 0.01  # the share of the build between two progress reports


def book_work(
    runner: JobRunner,
    document: StoredDocument,
    folder: Path,
    kind: BookKind,
    *,
    partial_ok: bool,
    ffmpeg: Ffmpeg | None = None,
) -> Callable[[JobRecord], Sequence[Path]]:
    """Build the whole audiobook of `kind` into `folder`, the one its chapters are in."""

    def work(job: JobRecord) -> Sequence[Path]:
        told = -1.0

        def progress(event: BookProgress) -> None:
            nonlocal told
            if event.fraction >= 1.0 or event.fraction - told >= BOOK_STEP:
                told = event.fraction
                job.report({"phase": "building", "fraction": event.fraction})

        job.report({"phase": "building", "fraction": 0.0})
        built = runner.run_book(
            document.folder,
            folder,
            kind,
            partial_ok=partial_ok,
            progress=progress,
            cancel=job.cancel,
            ffmpeg=ffmpeg,
        )
        titles = _titles(document)
        job.report(
            {
                "phase": "done",
                "name": built.path.name,
                "kind": str(built.kind),
                "partial": built.partial,
                "reused": built.reused,
                "missing": [_title(titles, i) for i in built.missing],
                "unavailable": [_title(titles, i) for i in built.unavailable],
            }
        )
        try:
            # removing the project removes the built file too (D-750)
            record_files(document.folder, document.id, folder, [built.path])
        except OSError as error:
            logger.warning("could not record the audiobook's files: %s", error)
        return [built.path]

    return work


def _titles(document: StoredDocument) -> dict[int, str]:
    """The chapters' titles by their index, for the person, who never sees an index."""
    try:
        return {c.index: c.title for c in find_chapters(load_document(document.folder))}
    except PlayerError:
        return {}


def _title(titles: dict[int, str], index: int) -> str:
    return titles.get(index) or str(index + 1)


def _note_made(
    document: StoredDocument,
    folder: Path,
    settings: JobSettings,
    voice: VoiceSource,
    runner: JobRunner,
) -> None:
    """Write the web's record with what the job makes the audiobook with (`Made`), once its
    laid-out document is there (the voice follows its language, D-469). A failure only
    means the page shows the book once it is done."""
    try:
        language = load_document(document.folder).language
        steps = runner.steps_for(settings)
        made = Made(
            voice=voice.voice_for(settings.voice, language),
            switched_off=frozenset(str(c) for c in settings.switched_off),
            plugins=frozenset(s.id for s in steps if getattr(s, "plugin", None) is not None),
            version=__version__,
        )
        write_record(document.folder, document.id, folder, made)
    except (OSError, PlayerError) as error:
        logger.warning("could not note what the audiobook is made with: %s", error)


def _forget_other_position(document: StoredDocument, folder: Path) -> None:
    """Remove the listening position unless it is in the audiobook now in `folder`.
    Raises OSError."""
    try:
        stamp = current_audiobook(document.folder, document.id, [folder]).located.stamp
    except PlayerError:
        stamp = ""
    if not stamp or recorded_position(document.folder, document.id, stamp) is None:
        remove_position(document.folder)


def voices_work(models_dir: Path, fetch: Fetch | None) -> Callable[[JobRecord], Sequence[Path]]:
    def work(job: JobRecord) -> Sequence[Path]:
        if job.cancel.is_set():
            raise JobCancelled
        job.report({"phase": "downloading", "bytes_done": 0, "bytes_total": None, "file": ""})

        def progress(done: int, total: int, target: str) -> None:
            if job.cancel.is_set():
                raise JobCancelled
            job.report(
                {"phase": "downloading", "bytes_done": done, "bytes_total": total, "file": target}
            )

        download_voice_files(models_dir, progress=progress, fetch=fetch)
        job.report({"phase": "done"})
        return []

    return work


def preview_work(
    voice: VoiceSource,
    folder: Path,
    *,
    text: str,
    voice_id: str,
    speed: float,
    letter_speed: float = 1.0,
    on_failure: Callable[[], None] = lambda: None,
) -> Callable[[JobRecord], Sequence[Path]]:
    """Speak `text` into `folder/preview.wav` (replacing the last preview, D-249);
    `voice_id` "" is the source's default voice. Every preview writes the same file, so
    the file link of an earlier preview job plays the newest preview; the page only ever
    plays the preview it just made."""
    chosen = voice_id or voice.default_voice

    def work(job: JobRecord) -> Sequence[Path]:
        target = folder / PREVIEW_FILE
        try:
            job.report({"phase": "loading-voice"})
            engine = voice.make()
            try:
                session = engine.createSession()
                try:
                    job.report({"phase": "speaking"})
                    folder.mkdir(parents=True, exist_ok=True)
                    seconds = speak_to_wav(
                        session, text, chosen, target, speed=speed, letter_speed=letter_speed
                    )
                finally:
                    session.dispose()
            finally:
                voice.release(engine)
        except BaseException:
            on_failure()
            raise
        job.report({"phase": "done", "seconds": seconds})
        return [target]

    return work


def plan_digest(plan: DownloadPlan) -> str:
    """The digest a consent names: it changes whenever any file of the plan changes."""
    files = [
        [file.url, file.target, file.size, file.sha256, file.licence, file.unpack]
        for file in plan.files
    ]
    data = json.dumps(files, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def classify(error: BaseException) -> tuple[JobState, JobFailure] | None:
    """How a job ends after `error`; None for an error sci2audio did not expect."""
    if isinstance(error, JobCancelled | JobCancelledError | KeyboardInterrupt):
        return JobState.CANCELLED, JobFailure("cancelled", "the job was cancelled")
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return JobState.FAILED, JobFailure("disk-full", "not enough disk space; free some space")
    for kind, types in _KINDS:
        if isinstance(error, types):
            return JobState.FAILED, JobFailure(kind, str(error))
    return None


# earlier entries win: the subclasses come before JobError
_KINDS: tuple[tuple[str, type[BaseException] | tuple[type[BaseException], ...]], ...] = (
    ("busy", JobBusyError),
    ("missing-chapters", MissingChaptersError),  # #725: chapters gone from the cache
    ("output-exists", OutputExistsError),
    ("unsupported-file", AppUnsupportedFileError),
    ("unreadable-text", UnreadableTextError),  # #442
    ("network", NetworkError),
    ("download-failed", DownloadError),
    ("voice-failed", EngineError),  # a preview the voice could not speak
    ("job-failed", JobError),
)
