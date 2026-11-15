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

from sci2audio.app import JobRunner, JobSettings, VoiceSource, kokoro_voice, load_settings
from sci2audio.web.config import OUTSIDE_PREFIX, ServerConfig
from sci2audio.web.documents import DocumentStore, StoredDocument
from sci2audio.web.jobs import JobBoard, JobRecord
from sci2audio.web.player import candidate_folders
from sci2audio.web.tasks import PREVIEW_FOLDER, Fetch, KeptVoice, audio_work, classify, preview_work

Work = Callable[[JobRecord], Sequence[Path]]


class ApiError(Exception):
    """An error answer: status, kind for programs, message for people."""

    def __init__(self, status: int, kind: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class Listening:
    """A document the player can open (#154): one the web holds, or one `sci2audio listen`
    named. `id` is its key in the addresses, `document` the file's id its records name
    (the same for the web's own documents); `folders` are the only folders its audiobook
    may be in (D-295); an outside document is read-only and has no document page."""

    id: str
    document: str
    name: str
    work: Path
    folders: tuple[Path | None, ...]
    outside: bool


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

    def preview_work(
        self, text: str, voice_id: str, speed: float, letter_speed: float = 1.0
    ) -> Work:
        """A voice preview into `<work_root>/preview/` (D-249)."""
        return preview_work(
            self.kept.source(),
            self.config.work_root / PREVIEW_FOLDER,
            text=text,
            voice_id=voice_id,
            speed=speed,
            letter_speed=letter_speed,
            on_failure=self.kept.dispose,
        )

    def listening(self, document_id: str) -> Listening | None:
        """The document `document_id` as the player sees it, or None. A command-line job
        has its own key (`cli-…`), so it and a web document of the same file never stand
        for each other; it is looked for only in its one output folder, never in the
        recorded, the saved or the default one."""
        if document_id.startswith(OUTSIDE_PREFIX):
            job = next((j for j in self.config.outside if j.id == document_id), None)
            if job is None:
                return None
            return Listening(job.id, job.document, job.name, job.work, (job.folder,), outside=True)
        found = self.store.get(document_id)
        if found is None:
            return None
        saved, _ = load_settings(self.config.config_file)
        folders = candidate_folders(
            found.folder, found.id, saved.output_folder, self.config.output_folder
        )
        return Listening(
            found.id, found.id, found.name, found.folder, tuple(folders), outside=False
        )


def _state(request: Request) -> ServerState:
    state: ServerState = request.app.state.sci2audio
    return state


state_of = Depends(_state)
