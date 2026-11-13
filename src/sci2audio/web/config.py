"""The server's configuration: everything a server run needs, passed in (no global state).

The command line builds one with `server_config()` from the app's default folders and a
fresh start-up token; tests build their own with folders in a temporary directory.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

import platformdirs

from sci2audio.app import default_config_file

HOST = "127.0.0.1"  # the only address the server ever binds to (D-192)
UPLOAD_LIMIT = 200 * 1024 * 1024  # bytes per opened file (D-198)
TEXT_LIMIT = 5 * 1024 * 1024  # bytes of pasted text, UTF-8 (D-198)
TOKEN_BYTES = 32  # 256 bits (D-193)


def new_token() -> str:
    """A fresh start-up token for one server run."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def default_work_root() -> Path:
    """The folder that holds one working folder per document (`<sha256[:16]>`), the same
    folders the audio job uses by default (D-164)."""
    return platformdirs.user_cache_path("sci2audio", appauthor=False) / "jobs"


def default_models_dir() -> Path:
    """Where the voice download puts the voice files (D-164)."""
    return platformdirs.user_data_path("sci2audio", appauthor=False) / "models"


def default_output_folder() -> Path:
    """Where audiobooks go when the person chose no folder: `~/Documents/sci2audio` (D-199)."""
    return platformdirs.user_documents_path() / "sci2audio"


@dataclass(frozen=True)
class ServerConfig:
    """One server run.

    `port` is the port the launcher bound (the Host and Origin checks need it); `token` is
    the start-up token the browser trades for its cookie at `/start`.
    """

    token: str
    port: int
    work_root: Path
    models_dir: Path
    config_file: Path
    output_folder: Path  # default for audiobooks when the settings name none
    upload_limit: int = UPLOAD_LIMIT
    text_limit: int = TEXT_LIMIT

    def __post_init__(self) -> None:
        if len(self.token) < 32:
            raise ValueError("the start-up token must be at least 32 characters")
        if not 0 < self.port < 65536:
            raise ValueError(f"port must be between 1 and 65535, got {self.port}")

    @property
    def origin(self) -> str:
        """The server's own origin, as the browser is sent to it."""
        return f"http://{HOST}:{self.port}"

    @property
    def hosts(self) -> frozenset[str]:
        """The Host header values the server answers (D-194)."""
        return frozenset({f"{HOST}:{self.port}", f"localhost:{self.port}"})

    @property
    def origins(self) -> frozenset[str]:
        """The Origin header values the server accepts (D-194)."""
        return frozenset(f"http://{host}" for host in self.hosts)

    @property
    def cookie_name(self) -> str:
        """Named after the port: cookies are shared between ports of one host."""
        return f"sci2audio-{self.port}"

    @property
    def start_url(self) -> str:
        """The link the terminal prints and the browser opens."""
        return f"{self.origin}/start?token={self.token}"


def server_config(port: int, *, token: str | None = None) -> ServerConfig:
    """The configuration of a server run with the default folders."""
    return ServerConfig(
        token=token or new_token(),
        port=port,
        work_root=default_work_root(),
        models_dir=default_models_dir(),
        config_file=default_config_file(),
        output_folder=default_output_folder(),
    )
