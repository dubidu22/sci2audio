"""Starting the server: a socket on 127.0.0.1, uvicorn, and the browser (D-192, D-193).

The launcher binds the socket itself, on 127.0.0.1 and port 0 (the operating system picks
a free port), and hands it to uvicorn, so the port is known before the browser opens and
nothing else can take it in between. There is no option for another address.
"""

from __future__ import annotations

import logging
import socket
import webbrowser
from collections.abc import Callable

import uvicorn
from starlette.types import ASGIApp

from sci2audio.web.config import HOST, ServerConfig, server_config
from sci2audio.web.server import create_app

SHUTDOWN_WAIT = 5  # seconds for a running job and open event streams to end


def bind() -> socket.socket:
    """A listening socket on 127.0.0.1 at a port the operating system picks."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((HOST, 0))
        sock.listen(128)
    except OSError:
        sock.close()
        raise
    sock.set_inheritable(True)
    return sock


class _NoUpgradeHint(logging.Filter):
    """uvicorn answers any `Upgrade:` request it can't serve with a warning, and for a
    websocket one with a hint to install a websocket library: neither means anything to
    the person reading the terminal, and sci2audio has no websockets (D-196)."""

    HINTS = ("Unsupported upgrade request", "No supported WebSocket library")

    def filter(self, record: logging.LogRecord) -> bool:
        return not str(record.msg).startswith(self.HINTS)


def uvicorn_config(app: ASGIApp) -> uvicorn.Config:
    """How uvicorn runs the app (D-196). Making the config sets up uvicorn's loggers, so the
    filter goes on afterwards."""
    config = uvicorn.Config(
        app,
        access_log=False,  # it would print the start link's token and file names
        log_level="warning",
        server_header=False,
        timeout_graceful_shutdown=SHUTDOWN_WAIT,
        lifespan="off",
        ws="none",  # never websockets, even if a websocket library gets installed
    )
    errors = logging.getLogger("uvicorn.error")
    if not any(isinstance(f, _NoUpgradeHint) for f in errors.filters):
        errors.addFilter(_NoUpgradeHint())
    return config


class _Server(uvicorn.Server):
    """uvicorn's server, calling `on_started` once it has started (#161). uvicorn puts its
    Ctrl-C handler in place before it starts; until then Python's own handler raises
    KeyboardInterrupt wherever the program is, and if that is inside the import of the
    event loop's module, Python drops it ("Exception ignored") and the server runs on. So
    the "running" line comes from here: once it shows, Ctrl-C stops the server."""

    def __init__(self, config: uvicorn.Config, on_started: Callable[[], None]) -> None:
        super().__init__(config)
        self._on_started = on_started

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started:
            self._on_started()


def serve(
    sock: socket.socket,
    config: ServerConfig,
    *,
    open_browser: bool = True,
    say: Callable[[str], None] = print,
) -> None:
    """Run the server on `sock` until Ctrl-C; the running job is cancelled on the way out.
    The link is printed, and the browser opened, once the server has started (#161)."""
    app = create_app(config)
    state = app.state.sci2audio

    def started() -> None:
        say(f"sci2audio is running at {config.start_url}")
        say("Keep this window open while you use sci2audio; press Ctrl-C to stop it.")
        if open_browser:
            webbrowser.open(config.start_url)

    server = _Server(uvicorn_config(app), started)
    try:
        server.run(sockets=[sock])
    except KeyboardInterrupt:  # uvicorn raises Ctrl-C again once it has shut down
        pass
    finally:
        state.stopping.set()
        state.board.shutdown(SHUTDOWN_WAIT)
        # a preview can't be cancelled: while one still speaks, its engine stays with it
        # and goes when the process ends
        if state.board.current is None:
            state.kept.dispose()
    say("sci2audio has stopped.")


def run(*, open_browser: bool = True, say: Callable[[str], None] = print) -> int:
    """`sci2audio ui`: bind, configure with the default folders, serve."""
    sock = bind()
    port = sock.getsockname()[1]
    serve(sock, server_config(port), open_browser=open_browser, say=say)
    return 0
