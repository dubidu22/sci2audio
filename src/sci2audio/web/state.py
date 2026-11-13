"""What one server run holds: its configuration, runner, documents and jobs (no global state).

`create_app` makes one `ServerState` and keeps it on the app; routes get it through the
`state_of` dependency.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Depends, Request

from sci2audio.app import JobRunner, JobSettings
from sci2audio.web.config import ServerConfig
from sci2audio.web.documents import DocumentStore, StoredDocument
from sci2audio.web.jobs import JobBoard, JobRecord
from sci2audio.web.tasks import Fetch, classify

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
    store: DocumentStore = field(init=False)
    board: JobBoard = field(init=False)
    stopping: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self) -> None:
        self.store = DocumentStore(
            self.config.work_root,
            upload_limit=self.config.upload_limit,
            text_limit=self.config.text_limit,
        )
        self.board = JobBoard(classify)

    def audio_work(self, document: StoredDocument, settings: JobSettings, overwrite: bool) -> Work:
        """The audio job arrives with #71 (D-208)."""
        raise ApiError(
            501, "not-available", "making audiobooks arrives with the audio job (Issue #71)"
        )


def _state(request: Request) -> ServerState:
    state: ServerState = request.app.state.sci2audio
    return state


state_of = Depends(_state)
