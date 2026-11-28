"""Starting the server: a socket on 127.0.0.1, uvicorn, and the browser (D-192, D-193).

The launcher binds the socket itself, on 127.0.0.1 and port 0 (the operating system picks
a free port), and hands it to uvicorn, so the port is known before the browser opens and
nothing else can take it in between. There is no option for another address.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
import webbrowser
from collections.abc import Callable

import uvicorn
from starlette.types import ASGIApp

from sci2audio.web.config import HOST, OutsideJob, ServerConfig, server_config
from sci2audio.web.jobs import JobKind
from sci2audio.web.server import create_app
from sci2audio.web.state import ServerState

SHUTDOWN_WAIT = 5  # seconds for a running job and open event streams to end
IDLE_STOP = 15 * 60  # seconds without a request after which the app without a window stops
WATCH_EVERY = 1.0  # seconds between the watch's looks at Quit and the idle time


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


class Watch:
    """The lifetime of the app without a window (launched as "browser", #215, D-797): no terminal
    and no window to close, so it stops when the rail's Quit item is pressed, or when no
    request has come for `idle` seconds while no job runs (the Listen page saves the
    position every few seconds while it plays, and a page in sight asks for the job list
    once a minute, so reading and listening keep it alive, #631)."""

    def __init__(
        self,
        state: ServerState,
        stop: Callable[[], None],
        *,
        idle: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = state
        self.stop = stop
        self.idle = IDLE_STOP if idle is None else idle
        self.clock = clock
        self.reason: str | None = None  # "quit" or "idle" once it stopped the server

    def check(self) -> bool:
        """One look: True, and the server told to stop, when it should end now."""
        if self.state.quit.is_set():
            self.reason = "quit"
        elif self.state.board.current is None and self.clock() - self.state.seen >= self.idle:
            self.reason = "idle"
        else:
            return False
        self.stop()
        return True

    def run(self, ended: threading.Event, every: float | None = None) -> None:
        """Looks every `every` seconds until it stopped the server or `ended` is set."""
        every = WATCH_EVERY if every is None else every
        while not ended.wait(every):
            if self.check():
                return


def _wind_down(state: ServerState) -> None:
    """What every way of stopping does once uvicorn has ended: end the event streams,
    cancel the running job, let the voice go."""
    state.stopping.set()
    state.start_page.remove()  # if the browser never traded the token
    state.board.shutdown(SHUTDOWN_WAIT)
    # a preview can't be cancelled: while one still speaks, its engine stays with it
    # and goes when the process ends
    if state.board.current is None:
        state.kept.dispose()


def serve(
    sock: socket.socket,
    config: ServerConfig,
    *,
    open_browser: bool = True,
    say: Callable[[str], None] = print,
) -> None:
    """Run the server on `sock` until Ctrl-C; the running job is cancelled on the way out.
    The link is printed, and the browser opened, once the server has started (#161): at the
    start page, so no command line holds the token (#117). Launched as "browser", a `Watch`
    also ends it on Quit or when idle (#215)."""
    app = create_app(config)
    state = app.state.sci2audio

    def started() -> None:
        say(f"sci2audio is running at {config.start_url}")
        if config.launched_as == "terminal":
            say("Keep this window open while you use sci2audio; press Ctrl-C to stop it.")
        if open_browser:
            try:
                page = state.start_page.write(config.start_url)
            except OSError as error:  # the link above still works
                say(f"Open the link above in your browser (no start page: {error.strerror}).")
            else:
                webbrowser.open(page)

    server = _Server(uvicorn_config(app), started)
    ended = threading.Event()
    if config.launched_as == "browser":
        watch = Watch(state, lambda: setattr(server, "should_exit", True))
        threading.Thread(target=watch.run, args=(ended,), name="watch", daemon=True).start()
    try:
        server.run(sockets=[sock])
    except KeyboardInterrupt:  # uvicorn raises Ctrl-C again once it has shut down
        pass
    finally:
        ended.set()
        _wind_down(state)
    say("sci2audio has stopped.")


class Background:
    """The server in a thread of its own, for the app's window, which must have the main
    thread (macOS requires it, #215). `start()` returns once uvicorn has started or failed;
    `stop()` ends it as Ctrl-C would and waits for it."""

    def __init__(self, sock: socket.socket, config: ServerConfig) -> None:
        self.app = create_app(config)
        self.state: ServerState = self.app.state.sci2audio
        self._ready = threading.Event()
        self._server = _Server(uvicorn_config(self.app), self._ready.set)
        self._sock = sock
        self._thread = threading.Thread(target=self._run, name="server", daemon=True)
        self.error: BaseException | None = None

    def _run(self) -> None:
        try:
            self._server.run(sockets=[self._sock])
        except BaseException as error:  # reported by start() or the window's log
            self.error = error
        finally:
            self._ready.set()

    def start(self, timeout: float = 60) -> bool:
        """True once the server answers; False if it ended or did not start in time."""
        self._thread.start()
        self._ready.wait(timeout)
        return self._server.started and self._thread.is_alive()

    @property
    def running(self) -> bool:
        """Is a job running that closing would stop (a voice preview is not asked about)?"""
        current = self.state.board.current
        return current is not None and current.kind is not JobKind.PREVIEW

    def stop(self, timeout: float = SHUTDOWN_WAIT + 10) -> None:
        self._server.should_exit = True
        if self._thread.ident is not None:  # it was started
            self._thread.join(timeout)
        self._sock.close()
        _wind_down(self.state)


def run(
    *,
    open_browser: bool = True,
    say: Callable[[str], None] = print,
    outside: tuple[OutsideJob, ...] = (),
    launched_as: str = "terminal",
) -> int:
    """`sci2audio ui`: bind, configure with the default folders, serve. `sci2audio listen`
    passes the command-line job it opens in the player (#154); the app without a window
    passes "browser" (#215)."""
    sock = bind()
    port = sock.getsockname()[1]
    config = server_config(port, outside=outside, launched_as=launched_as)
    serve(sock, config, open_browser=open_browser, say=say)
    return 0
