"""What one server run holds: its configuration, runner, documents and jobs (no global state).

`create_app` makes one `ServerState` and keeps it on the app; routes get it through the
`state_of` dependency.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from fastapi import Depends, Request

from sci2audio.app import JobRunner, JobSettings, VoiceSource, kokoro_voice
from sci2audio.web.config import ServerConfig
from sci2audio.web.documents import DocumentStore, StoredDocument
from sci2audio.web.jobs import JobBoard, JobRecord
from sci2audio.web.tasks import PREVIEW_FOLDER, Fetch, KeptVoice, audio_work, classify, preview_work

Work = Callable[[JobRecord], Sequence[Path]]


class ApiError(Exception):
    """An error answer: status, kind for programs, message for people."""

    def __init__(self, status: int, kind: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.message = message


@dataclass
class ServerState:
    config: ServerConfig
    runner: JobRunner
    fetch: Fetch | None = None  # the voice download's fetch; tests pass a fake
    # the voice of audio jobs from the models folder; tests pass a fake (D-166)
    voice: Callable[[Path], VoiceSource] = kokoro_voice
    store: DocumentStore = field(init=False)
    board: JobBoard = field(init=False)
    kept: KeptVoice = field(init=False)  # one engine for previews and audio jobs (D-250)
    stopping: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self) -> None:
        self.store = DocumentStore(
            self.config.work_root,
            upload_limit=self.config.upload_limit,
            text_limit=self.config.text_limit,
        )
        self.store.clear_stale_uploads()  # left behind by a server that was killed
        self.board = JobBoard(classify)
        self.kept = KeptVoice(lambda: self.voice(self.config.models_dir))

    def audio_work(self, document: StoredDocument, settings: JobSettings, overwrite: bool) -> Work:
        """An audio job into the person's output folder (D-199): the one in the settings,
        else the server's default."""
        if settings.output_folder is None:
            settings = replace(settings, output_folder=self.config.output_folder)
        return audio_work(
            self.runner,
            document,
            settings,
            self.kept.source(),
            overwrite=overwrite,
            on_failure=self.kept.dispose,
        )

    def preview_work(self, text: str, voice_id: str, speed: float) -> Work:
        """A voice preview into `<work_root>/preview/` (D-249)."""
        return preview_work(
            self.kept.source(),
            self.config.work_root / PREVIEW_FOLDER,
            text=text,
            voice_id=voice_id,
            speed=speed,
            on_failure=self.kept.dispose,
        )


def _state(request: Request) -> ServerState:
    state: ServerState = request.app.state.sci2audio
    return state


state_of = Depends(_state)
