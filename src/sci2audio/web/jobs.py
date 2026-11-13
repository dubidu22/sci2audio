"""The server's jobs: one at a time, each in its own thread, with progress for the events.

`JobBoard` keeps the jobs of one server run (D-200): a second start while one runs is
refused with `BoardBusyError`, whatever its kind (script, audio, voice download, voice
preview). Each job has an id `<document id>-<kind>-<n>` (`voices-<n>` for the voice
download, `preview-<n>` for a preview), a state, its latest progress and, when it ends,
its error or the files it wrote. What lasts beyond the server run is on disk (the job
records, the report, the audiobook).

The thread that runs a job reports through `JobRecord.report`; the event stream reads
`JobRecord.version` and the snapshot (D-201). Intermediate progress the stream had no
time to send is not queued: the next event carries the latest state.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JobKind(StrEnum):
    SCRIPT = "script"
    AUDIO = "audio"
    VOICES = "voices"
    PREVIEW = "preview"  # a voice preview (D-249)


class JobState(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BoardBusyError(Exception):
    """A job is running; the server runs one at a time."""


class JobCancelled(Exception):
    """Raised inside a job's work to end it as cancelled."""


@dataclass(frozen=True)
class JobFailure:
    """Why a job ended without its result: an error kind for programs, words for people."""

    kind: str
    message: str


@dataclass(frozen=True)
class JobFile:
    name: str
    path: Path
    size: int


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class JobRecord:
    """One job of this server run."""

    def __init__(
        self,
        job_id: str,
        kind: JobKind,
        document: str | None,
        settings: dict[str, Any] | None,
        cancellable: bool,
    ) -> None:
        self.id = job_id
        self.kind = kind
        self.document = document
        self.settings = settings
        self.cancellable = cancellable
        self.started = _now()
        self.cancel = threading.Event()
        self._lock = threading.Lock()
        self._version = 0
        self._state = JobState.RUNNING
        self._finished: str | None = None
        self._progress: dict[str, Any] | None = None
        self._failure: JobFailure | None = None
        self._files: tuple[JobFile, ...] = ()
        self._thread: threading.Thread | None = None

    @property
    def version(self) -> int:
        """Grows with every change; the event stream sends when it changed."""
        with self._lock:
            return self._version

    @property
    def state(self) -> JobState:
        with self._lock:
            return self._state

    @property
    def files(self) -> tuple[JobFile, ...]:
        with self._lock:
            return self._files

    def report(self, progress: dict[str, Any]) -> None:
        """Called by the job's thread with its latest progress."""
        with self._lock:
            self._progress = progress
            self._version += 1

    def file(self, name: str) -> JobFile | None:
        """A file the job wrote, by its name as written; None for any other name."""
        return next((file for file in self.files if file.name == name), None)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "kind": str(self.kind),
                "document": self.document,
                "state": str(self._state),
                "started": self.started,
                "finished": self._finished,
                "cancellable": self.cancellable and self._state is JobState.RUNNING,
                "settings": self.settings,
                "progress": self._progress,
                "error": None
                if self._failure is None
                else {"error": self._failure.kind, "message": self._failure.message},
                "files": [
                    {"name": file.name, "size": file.size, "folder": str(file.path.parent)}
                    for file in self._files
                ],
            }

    def _end(self, state: JobState, failure: JobFailure | None, files: Sequence[Path] = ()) -> None:
        kept = []
        for path in files:
            try:
                kept.append(JobFile(path.name, path, path.stat().st_size))
            except OSError:
                continue  # removed since it was written: not offered
        with self._lock:
            self._state = state
            self._failure = failure
            self._files = tuple(kept)
            self._finished = _now()
            self._version += 1

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)


Work = Callable[[JobRecord], Sequence[Path]]
# maps an exception from the work to how the job ends; None = an unexpected error
Classify = Callable[[BaseException], tuple[JobState, JobFailure] | None]


class JobBoard:
    """The jobs of one server run; at most one runs at a time."""

    def __init__(self, classify: Classify) -> None:
        self._classify = classify
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}
        self._counter = 0
        self._current: JobRecord | None = None

    @property
    def current(self) -> JobRecord | None:
        """The running job, if any."""
        with self._lock:
            job = self._current
        return job if job is not None and job.state is JobState.RUNNING else None

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[JobRecord]:
        """Every job of this run, newest first."""
        with self._lock:
            return list(reversed(self._jobs.values()))

    def start(
        self,
        kind: JobKind,
        document: str | None,
        settings: dict[str, Any] | None,
        work: Work,
        *,
        cancellable: bool,
    ) -> JobRecord:
        """Start `work` in a new thread as a job; BoardBusyError if one is running."""
        with self._lock:
            if self._current is not None and self._current.state is JobState.RUNNING:
                raise BoardBusyError(
                    f"job {self._current.id} is running; wait until it has finished"
                )
            self._counter += 1
            n = self._counter
            job_id = f"{kind}-{n}" if document is None else f"{document}-{kind}-{n}"
            job = JobRecord(job_id, kind, document, settings, cancellable)
            self._jobs[job_id] = job
            self._current = job
            thread = threading.Thread(
                target=self._run, args=(job, work), name=f"sci2audio-{job_id}", daemon=True
            )
            job._thread = thread
            thread.start()
        return job

    def _run(self, job: JobRecord, work: Work) -> None:
        try:
            files = work(job)
        except BaseException as error:
            outcome = self._classify(error)
            if outcome is None:
                logger.exception("job %s failed unexpectedly", job.id)
                outcome = (
                    JobState.FAILED,
                    JobFailure("internal", f"sci2audio met an unexpected error: {error}"),
                )
            job._end(*outcome)
            if not isinstance(error, Exception):  # KeyboardInterrupt, SystemExit
                raise
        else:
            job._end(JobState.DONE, None, files)

    def cancel(self, job_id: str) -> JobRecord | None:
        job = self.get(job_id)
        if job is not None:
            job.cancel.set()
        return job

    def shutdown(self, timeout: float) -> None:
        """Cancel the running job and wait up to `timeout` seconds for it to end."""
        job = self.current
        if job is not None:
            job.cancel.set()
            job.join(timeout)
