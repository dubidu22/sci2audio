"""What each kind of job does, built on the app's jobs and the one voice download.

- script: the pre-analysis. `JobRunner.run_script` writes the script and report into the
  document's own `script/` folder, always replacing them: they are sci2audio's files,
  rewritten whenever the person changes a switch or the chapter choice (D-199).
- voices: `voices.download_voice_files`, the one download function (D-104, D-122),
  started only after consent (D-203). Cancelled by raising from its progress callback;
  the download removes the `.part` file of the file it was fetching (D-202).

`classify` turns what a job raised into how it ends: an error kind for programs and the
app's own message for people.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO

from sci2audio.app import JobBusyError, JobError, JobRunner, JobSettings, OutputExistsError, Phase
from sci2audio.app import UnsupportedFileError as AppUnsupportedFileError
from sci2audio.voices import DownloadError, DownloadPlan, NetworkError, download_voice_files
from sci2audio.web.documents import StoredDocument
from sci2audio.web.jobs import JobCancelled, JobFailure, JobRecord, JobState

Fetch = Callable[[str, BinaryIO, Callable[[int], None]], None]


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
    if isinstance(error, JobCancelled | KeyboardInterrupt):
        return JobState.CANCELLED, JobFailure("cancelled", "the job was cancelled")
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
    ("job-failed", JobError),
)
