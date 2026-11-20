"""The job runner: one job at a time per runner (D-138), no global state.

The command line and the server each make one `JobRunner`. The audio job also holds an
operating-system lock on its working folder, so two processes never work on one folder
(D-161). A runner loads the text-step plugins once, when it is made (#216, D-836), and runs
them with the built-in steps in every job unless a job is given other steps or its settings
switch the plugins off (#667).
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
from sci2audio.textprep import DEFAULT_MAX_CHARS, TextStep, installed_steps


class JobRunner:
    """Runs one job at a time. The cli and the server each make one; no global state."""

    def __init__(self, steps: Sequence[TextStep] | None = None) -> None:
        """`steps` defaults to the built-in steps with the installed plugins."""
        self._lock = threading.Lock()
        self.steps: Sequence[TextStep] = installed_steps() if steps is None else steps

    def steps_for(
        self, settings: JobSettings, steps: Sequence[TextStep] | None = None
    ) -> Sequence[TextStep]:
        """The steps a job with `settings` runs: `steps`, else the runner's, without the
        plugins' steps when its `plugins` is false (#667), so the report and the record
        never say "off" beside a plugin's edits. Other steps given are kept."""
        chosen = self.steps if steps is None else steps
        if settings.plugins:
            return chosen
        return tuple(step for step in chosen if getattr(step, "plugin", None) is None)

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
        pages: Callable[[int, int], None] | None = None,
        steps: Sequence[TextStep] | None = None,
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
                pages=pages,
                steps=self.steps_for(settings, steps),
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
        steps: Sequence[TextStep] | None = None,
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
                steps=self.steps_for(settings, steps),
                max_chars=max_chars,
            )
