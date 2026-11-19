"""The app: sci2audio in a window of its own (#215, D-45, D-47, D-797).

`sci2audio-app` starts the same local server as `sci2audio ui` (127.0.0.1, a port the
system picks, a fresh start-up token) and shows the interface in a pywebview window:
WKWebView on macOS, WebView2 on Windows. The server runs in a thread of its own, because
the window must have the main thread (macOS requires it). Closing the window stops the
server as Ctrl-C does; while an audiobook is being made it asks first.

Where there is no window engine (Linux, pywebview not installed, or WebView2 missing on
Windows) the app opens the interface in the default browser instead, launched as
"browser": the rail gets a Quit item and the server stops by itself when idle (`Watch`).

The app keeps a short start-up log (`config.app_log_file()`): when it started and stopped,
its version, how it shows the interface and why it could not start. Nothing else is
written to it: no requests, no start-up token, no file names (the privacy page says so).

`--selftest REPORT` is for the installers' smoke tests (#13): the app starts as usual,
checks the page the window loaded, writes what it found to REPORT as JSON and quits; with
no window to open it writes that and fails. Without a window the smoke tests drive the
browser path themselves (a stand-in browser receives the start link).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import locale
import logging
import logging.handlers
import multiprocessing
import os
import sys
import threading
from collections.abc import Callable, MutableMapping, Sequence
from pathlib import Path
from typing import Any

import platformdirs

from sci2audio import __version__
from sci2audio.web.config import ServerConfig, app_log_file, server_config
from sci2audio.web.i18n import DEFAULT_LANGUAGE, LANGUAGES, Strings, strings
from sci2audio.web.launch import Background, bind, run

WINDOW_SYSTEMS = frozenset({"darwin", "win32"})  # where pywebview has a bundled engine
TITLE = "sci2audio"
SIZE = (1280, 860)
MIN_SIZE = (480, 560)
LOG_BYTES = 1_000_000

# WebView2 reads extra engine switches from this variable (Microsoft's documented way); the
# app adds one that switches off SmartScreen, which would otherwise send addresses the
# window opens to Microsoft for a reputation check (#215 AC-3, offline rule).
WEBVIEW2_ARGUMENTS = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
NO_SMARTSCREEN = "--disable-features=msSmartScreenProtection"

# What the self test reads in the window: the page's title and language, whether the rail
# is drawn and where the page is. JSON, so the window hands back one string.
SELF_CHECK = (
    "JSON.stringify({title: document.title, lang: document.documentElement.lang,"
    " rail: document.querySelector('nav.rail') !== null, host: location.host,"
    " path: location.pathname})"
)

log = logging.getLogger("sci2audio.app")


# ---- the log, the language and the engine settings --------------------------------------


def open_log(path: Path) -> None:
    """Send the app's own log lines, and nothing else, to `path` (rotating, 1 MB)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=LOG_BYTES, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False  # never into uvicorn's or anyone else's handlers


def system_language(
    getlocale: Callable[[], tuple[str | None, str | None]] = locale.getlocale,
) -> str:
    """The language of the app's own dialogs: the system's, if sci2audio speaks it. The
    pages choose theirs from the request, as in a browser (D-288)."""
    with contextlib.suppress(ValueError):
        name = (getlocale()[0] or "").lower()
        for language in LANGUAGES:
            if name.startswith(language):
                return language
    return DEFAULT_LANGUAGE


def engine_settings(environ: MutableMapping[str, str], platform: str = sys.platform) -> None:
    """Switch off the web engine's own network checks before the window starts: SmartScreen
    in WebView2 (Windows). Switches already set (a test's debugging port) are kept."""
    if platform != "win32":
        return
    present = environ.get(WEBVIEW2_ARGUMENTS, "").split()
    if NO_SMARTSCREEN not in present:
        environ[WEBVIEW2_ARGUMENTS] = " ".join([*present, NO_SMARTSCREEN])


def webview_storage() -> Path:
    """Where the window keeps its cookies (the interface's settings cookies, as a browser
    keeps them for a year) and its cache; the start-up cookie still ends with each run."""
    return platformdirs.user_data_path("sci2audio", appauthor=False) / "window"


def load_webview(platform: str = sys.platform) -> Any | None:
    """pywebview, where it can open a window; None elsewhere (Linux, or not installed)."""
    if platform not in WINDOW_SYSTEMS:
        return None
    try:
        import webview  # the optional extra "window"; loaded only here
    except ImportError:
        return None
    return webview


# ---- the window --------------------------------------------------------------------------


class AppWindow:
    """One window on one running server. `webview` is the pywebview module (tests pass a
    fake); `server` the `Background` server whose start link the window opens."""

    def __init__(
        self,
        webview: Any,
        server: Background,
        config: ServerConfig,
        s: Strings,
        *,
        selftest: Path | None = None,
    ) -> None:
        self.webview = webview
        self.server = server
        self.config = config
        self.s = s
        self.selftest = selftest
        self._checked = threading.Event()
        self.window: Any = None

    def open(self) -> None:
        """Create the window and run it until it is closed (blocks on the main thread)."""
        settings = self.webview.settings
        settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # other sites never in the window
        settings["ALLOW_DOWNLOADS"] = True  # the audiobook's own files
        settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        self.window = self.webview.create_window(
            TITLE,
            self.config.start_url,
            width=SIZE[0],
            height=SIZE[1],
            min_size=MIN_SIZE,
            text_select=True,  # reading, markers and copying need it
            zoomable=True,  # larger text for those who need it
        )
        self.window.events.closing += self.closing
        if self.selftest is not None:
            self.window.events.loaded += self.loaded
        storage = webview_storage()
        storage.mkdir(parents=True, exist_ok=True)
        self.webview.start(private_mode=False, storage_path=str(storage))

    def closing(self) -> bool:
        """False keeps the window open: asked while an audiobook is being made."""
        if not self.server.running or self._checked.is_set():
            return True
        return bool(
            self.window.create_confirmation_dialog(
                self.s("app.close_title"), self.s("app.close_making")
            )
        )

    def loaded(self) -> None:
        """The self test: once the interface (not the start link) has loaded, read it,
        write the report and close."""
        if self._checked.is_set():
            return
        found = json.loads(self.window.evaluate_js(SELF_CHECK) or "{}")
        if found.get("path") == "/start":  # the start link, on its way to the library
            return
        self._checked.set()
        write_report(self.selftest, self.config, "window", found)  # type: ignore[arg-type]
        self.window.destroy()


def write_report(path: Path, config: ServerConfig, launched_as: str, page: dict[str, Any]) -> None:
    """The self test's findings: the version, how it was launched, the server's origin and what the
    page showed. Never the start-up token."""
    report = {
        "version": __version__,
        "launched_as": launched_as,
        "origin": config.origin,
        "page": page,
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def run_window(webview: Any, *, selftest: Path | None = None) -> int:
    """The app with its window. Returns the exit code; raises what the window engine
    raises when it can't start, so `main` can fall back to the browser."""
    sock = bind()
    config = server_config(sock.getsockname()[1], launched_as="window")
    server = Background(sock, config)
    if not server.start():
        log.error("the server did not start: %r", server.error)
        server.stop()
        return 1
    log.info("running in a window on %s", config.origin)
    try:
        AppWindow(webview, server, config, strings(system_language()), selftest=selftest).open()
    finally:
        server.stop()
    log.info("stopped")
    return 0 if selftest is None or selftest.exists() else 1


# ---- without a window --------------------------------------------------------------------


def run_browser() -> int:
    """The app without a window: the browser, a Quit item, and a stop when idle."""
    log.info("running in the browser")
    code = run(launched_as="browser", say=lambda text: None)  # nobody reads a terminal here
    log.info("stopped")
    return code


# ---- the program --------------------------------------------------------------------------


def _quiet_streams() -> None:
    """A windowed build has no terminal: Python then has no stdout or stderr, and a library
    writing to one would fail. Both go nowhere instead."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115


def main(argv: Sequence[str] | None = None) -> int:
    # A packaged build starts itself again for each PDF reader process (D-581).
    multiprocessing.freeze_support()
    _quiet_streams()
    parser = argparse.ArgumentParser(prog="sci2audio-app", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"sci2audio {__version__}")
    parser.add_argument("--selftest", type=Path, metavar="REPORT", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    open_log(app_log_file())
    log.info("sci2audio %s starting on %s", __version__, sys.platform)
    engine_settings(os.environ)
    webview = load_webview()
    if webview is None:
        log.info("no window engine on this system")
    else:
        try:
            return run_window(webview, selftest=args.selftest)
        except Exception as error:  # the engine could not start (WebView2 missing, ...)
            reason = f"{type(error).__name__}: {error}"
            log.error("the window could not open (%s); using the browser", reason)
    if args.selftest is not None:  # the smoke tests asked for a window and got none
        args.selftest.write_text(json.dumps({"launched_as": "browser"}), encoding="utf-8")
        return 1
    return run_browser()


if __name__ == "__main__":
    raise SystemExit(main())
