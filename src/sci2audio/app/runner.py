"""The job runner: one job at a time per runner (D-138), no global state.

The command line and the server each make one `JobRunner`. The audio job also holds an
operating-system lock on its working folder, so two processes never work on one folder
(D-161).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from sci2audio.app.audio import AudioJob, AudioProgress, run_audio_job
from sci2audio.app.job import JobBusyError, Phase, ScriptJob, run_script_job
from sci2audio.app.settings import JobSettings
from sci2audio.app.voice import VoiceSource
from sci2audio.output import OutputSettings
from sci2audio.textprep import BUILT_IN_STEPS, DEFAULT_MAX_CHARS, TextStep


class JobRunner:
    """Runs one job at a time. The cli and the server each make one; no global state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    @contextmanager
    def _one_job(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            raise JobBusyError("another job is running; wait until it has finished")
        try:
            yield
        finally:
            self._lock.release()

    def run_script(
        self,
        source: Path,
        settings: JobSettings,
        work: Path,
        *,
        overwrite: bool = False,
        progress: Callable[[Phase], None] | None = None,
        steps: Sequence[TextStep] = BUILT_IN_STEPS,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> ScriptJob:
        """`run_script_job` on this runner; JobBusyError if a job is running on it."""
        with self._one_job():
            return run_script_job(
                source,
                settings,
                work,
                overwrite=overwrite,
                progress=progress,
                steps=steps,
                max_chars=max_chars,
            )

    def run_audio(
        self,
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
    ) -> AudioJob:
        """`run_audio_job` on this runner; JobBusyError if a job is running on it."""
        with self._one_job():
            return run_audio_job(
                source,
                settings,
                work,
                voice=voice,
                output_settings=output_settings,
                overwrite=overwrite,
                progress=progress,
                cancel=cancel,
                steps=steps,
                max_chars=max_chars,
            )
