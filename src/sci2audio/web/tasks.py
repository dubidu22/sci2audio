"""What each kind of job does, built on the app's jobs and the one voice download.

- script: the pre-analysis. `JobRunner.run_script` writes the script and report into the
  document's own `script/` folder, always replacing them: they are sci2audio's files,
  rewritten whenever the person changes a switch or the chapter choice (D-199).
- audio: `JobRunner.run_audio` (#71) into the person's output folder, never replacing
  an audiobook without `overwrite` (D-163, D-199); cancelled through its event (D-160).
- voices: `voices.download_voice_files`, the one download function (D-104, D-122),
  started only after consent (D-203). Cancelled by raising from its progress callback;
  the download removes the `.part` file of the file it was fetching (D-202).
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
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, BinaryIO

from sci2audio.app import (
    AudioProgress,
    JobBusyError,
    JobCancelledError,
    JobError,
    JobRunner,
    JobSettings,
    OutputExistsError,
    Phase,
    VoiceSource,
)
from sci2audio.app import UnsupportedFileError as AppUnsupportedFileError
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

        own = replace(settings, output_folder=document.script_folder)
        result = runner.run_script(
            document.source, own, document.folder, overwrite=True, progress=progress
        )
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
    """`settings.output_folder` must be set (the server fills in its default).
    `on_failure` runs when the job fails (the server drops its kept engine)."""

    def work(job: JobRecord) -> Sequence[Path]:
        try:
            result = runner.run_audio(
                document.source,
                settings,
                document.folder,
                voice=voice,
                overwrite=overwrite,
                progress=lambda event: job.report(audio_progress(event)),
                cancel=job.cancel,
            )
        except (JobCancelledError, OutputExistsError, JobBusyError):
            raise  # the engine is fine
        except BaseException:
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
        return [*([written.m4b] if written.m4b else []), *written.mp3s, written.readalong]

    return work


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
    on_failure: Callable[[], None] = lambda: None,
) -> Callable[[JobRecord], Sequence[Path]]:
    """Speak `text` into `folder/preview.wav` (replacing the last preview, D-249);
    `voice_id` "" is the source's default voice."""
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
                    seconds = speak_to_wav(session, text, chosen, target, speed=speed)
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
    ("output-exists", OutputExistsError),
    ("unsupported-file", AppUnsupportedFileError),
    ("network", NetworkError),
    ("download-failed", DownloadError),
    ("voice-failed", EngineError),  # a preview the voice could not speak
    ("job-failed", JobError),
)
