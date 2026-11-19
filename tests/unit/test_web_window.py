"""The app (#215, D-797): its window on the local server, asking before closing while an
audiobook is being made, the self test, the engine's network checks, the start-up log, and
the app without a window (Quit, idle stop). pywebview is replaced by a fake: real windows
open only in the installers' smoke tests on macOS and Windows (#13)."""

from __future__ import annotations

import html
import http.cookiejar
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from web_helpers import ORIGIN, browser, make_config, program

from sci2audio import __version__
from sci2audio.web import bind, create_app, launch, window
from sci2audio.web.i18n import strings
from sci2audio.web.jobs import JobKind

# ---- a stand-in for pywebview -------------------------------------------------------------


class FakeEvent:
    def __init__(self) -> None:
        self.handlers: list[Callable[[], Any]] = []

    def __iadd__(self, handler: Callable[[], Any]) -> FakeEvent:
        self.handlers.append(handler)
        return self

    def fire(self) -> list[Any]:
        return [handler() for handler in self.handlers]


class FakeEvents:
    def __init__(self) -> None:
        self.closing = FakeEvent()
        self.loaded = FakeEvent()


class FakeWindow:
    def __init__(self, title: str, url: str, **options: Any) -> None:
        self.title, self.url, self.options = title, url, options
        self.events = FakeEvents()
        self.pages: list[Any] = []  # what run_js answers, one per call
        self.destroyed = False
        # pywebview's own close question: asked by the engine on its GUI thread (#631 F1)
        self.confirm_close = options.get("confirm_close", False)
        self.localization = dict(options.get("localization") or {})

    def run_js(self, script: str) -> str:
        assert script == window.SELF_CHECK
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return json.dumps(page)

    def evaluate_js(self, script: str) -> str:
        # wraps the script in eval(), which the pages' CSP refuses in a real window (#215)
        pytest.fail("evaluate_js fails under the pages' Content-Security-Policy")

    def create_confirmation_dialog(self, title: str, message: str) -> bool:
        # from a closing handler this hangs the window on macOS (#631 F1): never used
        pytest.fail("a dialog of the app's own: use confirm_close")

    def destroy(self) -> None:
        self.destroyed = True


class FakeWebview:
    """pywebview's module as the app uses it. `while_open` runs inside `start()`, where the
    real one runs the window until it is closed."""

    def __init__(self, while_open: Callable[[FakeWindow], None] = lambda w: None) -> None:
        self.settings = {
            "ALLOW_DOWNLOADS": False,
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": False,
            "OPEN_DEVTOOLS_IN_DEBUG": True,
        }
        self.windows: list[FakeWindow] = []
        self.started: list[dict[str, Any]] = []
        self.while_open = while_open

    def create_window(self, title: str, url: str, **options: Any) -> FakeWindow:
        self.windows.append(FakeWindow(title, url, **options))
        return self.windows[-1]

    def start(self, **options: Any) -> None:
        self.started.append(options)
        self.while_open(self.windows[-1])


@pytest.fixture
def folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The app's default folders and log under tmp_path; the log handler is put back."""
    monkeypatch.setattr(
        window,
        "server_config",
        lambda port, **kw: make_config(tmp_path, port=port, **kw),
    )
    monkeypatch.setattr(window, "webview_storage", lambda: tmp_path / "data" / "window")
    monkeypatch.setattr(window, "app_log_file", lambda: tmp_path / "logs" / "app.log")
    monkeypatch.setattr(launch, "SHUTDOWN_WAIT", 0.5)
    handlers = list(window.log.handlers)
    yield tmp_path
    for handler in window.log.handlers:
        handler.close()
    window.log.handlers[:] = handlers


def fetch(url: str, opener: urllib.request.OpenerDirector | None = None, **kw: Any) -> Any:
    request = urllib.request.Request(url, **kw)  # noqa: S310 (our own 127.0.0.1 server)
    return (opener or urllib.request.build_opener()).open(request, timeout=10)


def answers(url: str) -> bool:
    try:
        fetch(url).close()
    except urllib.error.HTTPError:
        return True  # it answered, if only with 401
    except OSError:
        return False
    return True


def a_job(state: Any, kind: JobKind = JobKind.AUDIO) -> tuple[Any, threading.Event]:
    gate = threading.Event()
    job = state.board.start(kind, None, None, lambda job: gate.wait(30) and [], cancellable=True)
    return job, gate


# ---- the window ----------------------------------------------------------------------------


def test_the_window_opens_the_start_link_and_closing_it_stops_the_server(
    folders: Path,
) -> None:
    seen: dict[str, Any] = {}

    def while_open(win: FakeWindow) -> None:
        seen["answers"] = answers(win.url)

    webview = FakeWebview(while_open)
    assert window.run_window(webview) == 0
    (win,) = webview.windows
    assert win.title == "sci2audio"
    assert win.url.startswith("http://127.0.0.1:")
    assert "/start?token=" in win.url
    assert seen["answers"] is True  # the server ran while the window was open
    assert not answers(win.url)  # and stopped when it closed
    assert win.options["text_select"] is True  # reading, markers and copying
    assert win.options["zoomable"] is True
    assert webview.settings == {
        "ALLOW_DOWNLOADS": True,
        "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,  # other sites go to the system browser
        "OPEN_DEVTOOLS_IN_DEBUG": False,
    }
    # cookies kept like a browser's (the Settings page's choices), in sci2audio's data folder
    assert webview.started == [
        {"private_mode": False, "storage_path": str(folders / "data" / "window")}
    ]
    assert len(win.events.closing.handlers) == 1
    assert len(win.events.loaded.handlers) == 1  # each page load: the question's language
    assert win.options["confirm_close"] is False  # asked only while an audiobook is made
    assert win.localization["global.quit"] == strings("en")("app.close_quit")


def make_window(folders: Path) -> tuple[window.AppWindow, FakeWindow]:
    sock = bind()
    config = make_config(folders, port=sock.getsockname()[1], launched_as="window")
    server = launch.Background(sock, config)
    app_window = window.AppWindow(FakeWebview(), server, config)
    win = FakeWindow("sci2audio", config.start_url, localization={"global.quit": "Quit"})
    app_window.window = win
    return app_window, win


def test_closing_asks_only_while_an_audiobook_is_being_made(folders: Path) -> None:
    app_window, win = make_window(folders)
    state = app_window.server.state
    assert app_window.closing() is True  # the window may always close ...
    assert win.confirm_close is False  # ... and nothing runs: at once
    preview, gate = a_job(state, JobKind.PREVIEW)
    try:
        assert app_window.closing() is True
        assert win.confirm_close is False  # a voice preview is not worth a question
    finally:
        gate.set()
        preview.join(10)
    job, gate = a_job(state)
    try:
        assert app_window.closing() is True
        assert win.confirm_close is True  # pywebview asks, and Cancel keeps it open
        app_window._checked.set()  # the self test closes without asking
        assert app_window.closing() is True
        assert win.confirm_close is False
    finally:
        gate.set()
        job.join(10)


def test_the_close_question_speaks_the_language_of_the_last_page(
    folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window, "system_language", lambda: "en")
    app_window, win = make_window(folders)
    question = win.localization  # the engine's own dictionary: changed in place
    app_window.closing()
    en = strings("en")
    assert question == {
        "global.quitConfirmation": en("app.close_making"),
        "global.quit": en("app.close_quit"),
        "global.cancel": en("app.close_cancel"),
    }
    config = app_window.config
    client = TestClient(
        app_window.server.app,
        base_url=config.origin,
        headers={"Authorization": f"Bearer {config.token}"},
    )
    assert client.get("/", headers={"Accept-Language": "de-DE"}).status_code == 200
    assert app_window.server.state.language == "de"
    app_window.loaded()  # macOS reads the strings before `closing` runs: each load sets them
    de = strings("de")
    assert win.localization is question
    assert question["global.quitConfirmation"] == de("app.close_making")
    assert question["global.quit"] == de("app.close_quit") == "sci2audio beenden"
    assert question["global.cancel"] == de("app.close_cancel")


def test_the_self_test_reads_the_interface_writes_its_report_and_closes(
    folders: Path,
) -> None:
    report = folders / "report.json"
    library = {"title": "Library · sci2audio", "lang": "en", "rail": True, "path": "/"}

    def while_open(win: FakeWindow) -> None:
        win.pages = [{"path": "/start"}, {**library, "host": win.url.split("/")[2]}]
        for _ in range(3):  # the start link, the library, and a later page load
            win.events.loaded.fire()

    webview = FakeWebview(while_open)
    assert window.run_window(webview, selftest=report) == 0
    (win,) = webview.windows
    assert win.destroyed
    found = json.loads(report.read_text(encoding="utf-8"))
    port = win.url.split(":")[2].split("/")[0]
    assert found == {
        "version": __version__,
        "launched_as": "window",
        "origin": f"http://127.0.0.1:{port}",
        "page": {**library, "host": f"127.0.0.1:{port}"},
    }
    assert win.url.split("token=")[1] not in report.read_text(encoding="utf-8")


def test_a_self_test_that_cannot_read_the_page_reports_why_and_closes(folders: Path) -> None:
    report = folders / "report.json"

    def while_open(win: FakeWindow) -> None:
        win.pages = [RuntimeError("EvalError: refused by the CSP")]
        win.events.loaded.fire()

    webview = FakeWebview(while_open)
    window.run_window(webview, selftest=report)
    assert webview.windows[0].destroyed  # it never waits for the smoke test's timeout
    found = json.loads(report.read_text(encoding="utf-8"))
    assert found["page"] == {"error": "RuntimeError: EvalError: refused by the CSP"}


def test_a_self_test_whose_page_never_loaded_fails(folders: Path) -> None:
    assert window.run_window(FakeWebview(), selftest=folders / "report.json") == 1


def test_a_server_that_cannot_start_ends_the_app_with_an_error(
    folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launch.Background, "start", lambda self, timeout=60: False)
    webview = FakeWebview()
    assert window.run_window(webview) == 1
    assert webview.windows == []


# ---- the engine, the language, the log ----------------------------------------------------


def test_webview2_gets_smartscreen_switched_off_and_keeps_other_switches() -> None:
    environ: dict[str, str] = {}
    window.engine_settings(environ, "win32")
    assert environ == {window.WEBVIEW2_ARGUMENTS: window.NO_SMARTSCREEN}
    environ = {window.WEBVIEW2_ARGUMENTS: "--remote-debugging-port=9222"}
    window.engine_settings(environ, "win32")
    window.engine_settings(environ, "win32")  # twice: once is enough
    assert environ[window.WEBVIEW2_ARGUMENTS] == (
        f"--remote-debugging-port=9222 {window.NO_SMARTSCREEN}"
    )
    for platform in ("darwin", "linux"):
        untouched: dict[str, str] = {}
        window.engine_settings(untouched, platform)
        assert untouched == {}


@pytest.mark.parametrize(
    ("name", "language"),
    [
        ("de_DE", "de"),
        ("de_AT", "de"),
        ("German_Germany", "de"),  # Windows names (#631 F2)
        ("English_United Kingdom", "en"),
        ("en_GB", "en"),
        ("fr_FR", "en"),
        ("French_France", "en"),
        (None, "en"),
        ("C", "en"),
    ],
)
def test_the_dialogs_speak_the_systems_language_if_sci2audio_does(
    name: str | None, language: str
) -> None:
    assert window.system_language(lambda: (name, "UTF-8")) == language


def test_pywebview_is_loaded_only_where_it_has_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = object()
    monkeypatch.setitem(sys.modules, "webview", fake)
    assert window.load_webview("linux") is None
    assert window.load_webview("darwin") is fake
    assert window.load_webview("win32") is fake
    monkeypatch.setitem(sys.modules, "webview", None)  # not installed: import fails
    assert window.load_webview("win32") is None


def test_the_app_falls_back_to_the_browser_when_the_window_cannot_open(
    folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(win: FakeWindow) -> None:
        raise RuntimeError("WebView2 runtime not found")

    ran: list[str] = []
    monkeypatch.setattr(window, "load_webview", lambda: FakeWebview(broken))
    monkeypatch.setattr(window, "run_browser", lambda: ran.append("browser") or 0)
    assert window.main([]) == 0
    assert ran == ["browser"]
    text = (folders / "logs" / "app.log").read_text(encoding="utf-8")
    assert f"sci2audio {__version__} starting on {sys.platform}" in text
    assert "running in a window on http://127.0.0.1:" in text
    assert "the window could not open (RuntimeError: WebView2 runtime not found)" in text


def test_a_self_test_without_a_window_says_so_and_fails(
    folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window, "load_webview", lambda: None)
    monkeypatch.setattr(window, "run_browser", lambda: pytest.fail("no browser in a self test"))
    report = folders / "report.json"
    assert window.main(["--selftest", str(report)]) == 1
    assert json.loads(report.read_text(encoding="utf-8")) == {"launched_as": "browser"}
    assert "no window engine on this system" in (folders / "logs" / "app.log").read_text()


def test_the_log_holds_the_apps_own_lines_only_never_the_token(folders: Path) -> None:
    window.open_log(folders / "logs" / "app.log")
    tokens: list[str] = []

    def while_open(win: FakeWindow) -> None:
        tokens.append(win.url.split("token=")[1])
        logging.getLogger("uvicorn.error").warning("a line of uvicorn's")
        logging.getLogger("sci2audio").warning("a line of another part")
        answers(win.url)

    window.run_window(FakeWebview(while_open))
    text = (folders / "logs" / "app.log").read_text(encoding="utf-8")
    assert "running in a window" in text
    assert "stopped" in text
    assert tokens[0] not in text
    assert "uvicorn" not in text
    assert "another part" not in text
    assert window.log.propagate is False


def test_a_windowed_build_without_terminal_streams_gets_quiet_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    window._quiet_streams()
    assert sys.stdout is not None
    assert sys.stderr is not None
    print("goes nowhere")
    sys.stdout.close()
    sys.stderr.close()


def test_the_app_is_an_entry_point_and_loading_it_does_not_load_pywebview() -> None:
    import subprocess

    text = (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    assert '[project.gui-scripts]\nsci2audio-app = "sci2audio.web.window:main"' in text
    assert 'window = [\n    "pywebview>=6.2.1,<7",\n]' in text
    code = "import sys, sci2audio.web.window; print('webview' in sys.modules)"
    found = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert found.stdout.strip() == "False"


# ---- the app without a window: Quit and idle stop ------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_watch_stops_on_quit_or_after_a_quiet_spell_without_a_job(tmp_path: Path) -> None:
    app = create_app(make_config(tmp_path, launched_as="browser"))
    state = app.state.sci2audio
    stops: list[int] = []
    clock = Clock()
    state.seen = clock.now
    watch = launch.Watch(state, lambda: stops.append(1), idle=900, clock=clock)
    clock.now += 899
    assert watch.check() is False
    job, gate = a_job(state)
    try:
        clock.now += 3600  # an hour of silence while an audiobook is made: it runs on
        assert watch.check() is False
    finally:
        gate.set()
        job.join(10)
    assert watch.check() is True
    assert (watch.reason, stops) == ("idle", [1])
    state.seen = clock.now  # a request came
    quitting = launch.Watch(state, lambda: stops.append(2), idle=900, clock=clock)
    assert quitting.check() is False
    state.quit.set()
    assert quitting.check() is True
    assert (quitting.reason, stops) == ("quit", [1, 2])


def test_the_watch_looks_until_the_server_ended(tmp_path: Path) -> None:
    state = create_app(make_config(tmp_path, launched_as="browser")).state.sci2audio
    watch = launch.Watch(state, lambda: None, idle=10**9)
    ended = threading.Event()
    looking = threading.Thread(target=watch.run, args=(ended, 0.01))
    looking.start()
    ended.set()
    looking.join(5)
    assert not looking.is_alive()
    assert watch.reason is None


def test_only_requests_that_passed_the_checks_keep_the_app_awake(tmp_path: Path) -> None:
    config = make_config(tmp_path, launched_as="browser")
    app = create_app(config)
    state = app.state.sci2audio
    state.seen = 0.0
    refused = program(app, config).get("/", headers={"Host": "evil.example:8123"})
    assert refused.status_code == 421
    assert state.seen == 0.0
    assert program(app, config).get("/").status_code == 200
    assert state.seen > 0.0


def test_the_rail_has_quit_and_the_privacy_page_the_log_only_where_they_apply(
    tmp_path: Path,
) -> None:
    for launched_as, has_quit, has_log in (
        ("terminal", False, False),
        ("window", False, True),
        ("browser", True, True),
    ):
        config = make_config(tmp_path / launched_as, launched_as=launched_as)
        client = program(create_app(config), config)
        library = client.get("/").text
        assert ('id="quit"' in library) is has_quit
        # only the browser needs a page in sight to keep the app awake (#631 F3)
        assert ('data-keep-alive="/api/v1/jobs"' in library) is has_quit
        for language in ("en", "de"):
            s = strings(language)
            privacy = client.get("/privacy", headers={"Accept-Language": language}).text
            assert ('id="app-log"' in privacy) is has_log
            if has_log:
                assert "app.log" in privacy
            # the app has no terminal that shows a link (#631 N1)
            key = "privacy.interface_key_app" if has_log else "privacy.interface_key"
            other = "privacy.interface_key" if has_log else "privacy.interface_key_app"
            assert html.escape(s(key), quote=False) in privacy
            assert html.escape(s(other), quote=False) not in privacy


@pytest.mark.parametrize("launched_as", ["terminal", "window"])
def test_there_is_no_quit_page_where_a_terminal_or_window_stops_it(
    tmp_path: Path, launched_as: str
) -> None:
    config = make_config(tmp_path, launched_as=launched_as)
    app = create_app(config)
    client = browser(app, config)
    assert client.get("/quit").status_code == 404
    assert client.post("/quit", headers={"Origin": ORIGIN}).status_code == 404
    assert not app.state.sci2audio.quit.is_set()


def test_the_quit_page_asks_warns_while_making_and_quits_on_post(tmp_path: Path) -> None:
    config = make_config(tmp_path, launched_as="browser")
    app = create_app(config)
    state = app.state.sci2audio
    client = browser(app, config)
    page = client.get("/quit")
    assert page.status_code == 200
    assert 'id="quit-now" data-api="/quit" disabled' in page.text  # until app.js wires it
    assert 'id="quit-done" hidden' in page.text
    assert 'id="quit-making"' not in page.text
    job, gate = a_job(state)
    try:
        assert 'id="quit-making"' in client.get("/quit").text
    finally:
        gate.set()
        job.join(10)
    # a cookie request that changes something needs the server's own Origin (D-194)
    assert client.post("/quit").status_code == 403
    assert not state.quit.is_set()
    done = client.post("/quit", headers={"Origin": ORIGIN})
    assert (done.status_code, done.json()) == (202, {"stopping": True})
    assert state.quit.is_set()


def test_the_app_without_a_window_opens_the_browser_and_quit_stops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    said: list[str] = []
    monkeypatch.setattr(launch.webbrowser, "open", opened.append)
    monkeypatch.setattr(launch, "WATCH_EVERY", 0.05)
    monkeypatch.setattr(launch, "SHUTDOWN_WAIT", 0.5)
    sock = bind()
    config = make_config(tmp_path, port=sock.getsockname()[1], launched_as="browser")
    serving = threading.Thread(
        target=launch.serve, args=(sock, config), kwargs={"say": said.append}
    )
    serving.start()
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        for _ in range(200):  # until the browser has been opened
            if opened:
                break
            serving.join(0.05)
        assert opened == [config.start_url]
        with fetch(config.start_url, opener) as library:
            assert 'id="quit"' in library.read().decode("utf-8")
        with fetch(
            f"{config.origin}/quit", opener, method="POST", headers={"Origin": config.origin}
        ):
            pass
        serving.join(15)
        assert not serving.is_alive()
    finally:
        sock.close()
    assert said[0] == f"sci2audio is running at {config.start_url}"
    assert not any("Ctrl-C" in line for line in said)  # there is no terminal to press it in
    assert said[-1] == "sci2audio has stopped."


def test_launched_as_takes_only_the_known_ways(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="launched_as"):
        make_config(tmp_path, launched_as="kiosk")


# ---- when the app cannot start: the log and a message (#631 F4) ----------------------------


@pytest.fixture
def messages(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(window, "show_message", lambda title, text: shown.append((title, text)))
    monkeypatch.setattr(window, "system_language", lambda: "en")
    return shown


def test_an_error_ends_the_app_with_its_reason_in_the_log_and_a_message_naming_it(
    folders: Path, monkeypatch: pytest.MonkeyPatch, messages: list[tuple[str, str]]
) -> None:
    def broken() -> int:
        raise OSError("no free port")

    monkeypatch.setattr(window, "load_webview", lambda: None)
    monkeypatch.setattr(window, "run_browser", broken)
    assert window.main([]) == 1
    log_file = folders / "logs" / "app.log"
    text = log_file.read_text(encoding="utf-8")
    assert "the app stopped with an error" in text
    assert "Traceback" in text
    assert "OSError: no free port" in text
    assert "sci2audio could not start: OSError: no free port" in text
    en = strings("en")
    assert messages == [(en("app.failed_title"), en("app.failed", path=str(log_file)))]
    assert str(log_file) in messages[0][1]


def test_a_normal_stop_shows_no_message(
    folders: Path, monkeypatch: pytest.MonkeyPatch, messages: list[tuple[str, str]]
) -> None:
    monkeypatch.setattr(window, "load_webview", lambda: None)
    monkeypatch.setattr(window, "run_browser", lambda: 0)
    assert window.main([]) == 0
    monkeypatch.setattr(window, "load_webview", FakeWebview)
    assert window.main([]) == 0  # the window opened and was closed
    assert messages == []
    assert "could not start" not in (folders / "logs" / "app.log").read_text(encoding="utf-8")


def test_a_server_that_cannot_start_in_the_app_shows_the_message(
    folders: Path, monkeypatch: pytest.MonkeyPatch, messages: list[tuple[str, str]]
) -> None:
    monkeypatch.setattr(launch.Background, "start", lambda self, timeout=60: False)
    monkeypatch.setattr(window, "load_webview", FakeWebview)
    assert window.main([]) == 1
    assert len(messages) == 1
    assert str(folders / "logs" / "app.log") in messages[0][1]
    text = (folders / "logs" / "app.log").read_text(encoding="utf-8")
    assert "sci2audio could not start: the server did not start" in text


def test_the_message_is_a_message_box_on_windows_an_alert_on_macos_and_nothing_on_linux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes

    boxes: list[tuple[Any, ...]] = []
    user32 = type("User32", (), {"MessageBoxW": staticmethod(lambda *a: boxes.append(a))})
    monkeypatch.setattr(ctypes, "windll", type("WinDLL", (), {"user32": user32}), raising=False)
    runs: list[list[str]] = []
    monkeypatch.setattr(window.subprocess, "run", lambda args, **kw: runs.append(args))
    window.show_message("A title", 'It said "no" in C:\\Logs', "win32")
    assert boxes == [(None, 'It said "no" in C:\\Logs', "A title", 0x10)]
    assert runs == []
    window.show_message("A title", 'It said "no" in C:\\Logs', "darwin")
    assert runs == [
        [
            "/usr/bin/osascript",
            "-e",
            'display alert "A title" message "It said \\"no\\" in C:\\\\Logs" as critical',
        ]
    ]
    window.show_message("A title", "text", "linux")
    assert len(boxes) == 1
    assert len(runs) == 1

    def broken(args: list[str], **kw: Any) -> None:
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(window.subprocess, "run", broken)
    window.show_message("A title", "text", "darwin")  # never hides the real failure


# ---- what the review's mutants showed untested (#631 T1) -----------------------------------


@pytest.mark.parametrize(("launched_as", "stops"), [("terminal", False), ("browser", True)])
def test_only_the_app_without_a_window_stops_when_idle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launched_as: str, stops: bool
) -> None:
    monkeypatch.setattr(launch, "IDLE_STOP", 0)
    monkeypatch.setattr(launch, "WATCH_EVERY", 0.01)
    monkeypatch.setattr(launch, "SHUTDOWN_WAIT", 0.1)
    told: list[bool] = []

    def run(server: Any, sockets: Any) -> None:  # uvicorn, while the watch would look
        deadline = time.monotonic() + 0.5
        while not server.should_exit and time.monotonic() < deadline:
            time.sleep(0.01)
        told.append(server.should_exit)

    monkeypatch.setattr(launch.uvicorn.Server, "run", run)
    sock = bind()
    try:
        config = make_config(tmp_path, port=sock.getsockname()[1], launched_as=launched_as)
        launch.serve(sock, config, open_browser=False, say=lambda text: None)
    finally:
        sock.close()
    assert told == [stops]


def test_the_app_window_never_stops_when_idle(
    folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launch, "IDLE_STOP", 0)
    monkeypatch.setattr(launch, "WATCH_EVERY", 0.01)
    sock = bind()
    config = make_config(folders, port=sock.getsockname()[1], launched_as="window")
    server = launch.Background(sock, config)
    assert server.start()
    try:
        time.sleep(0.3)
        assert server._thread.is_alive()
        assert answers(config.origin)
    finally:
        server.stop()


def test_the_idle_stop_comes_exactly_after_the_quiet_spell(tmp_path: Path) -> None:
    state = create_app(make_config(tmp_path, launched_as="browser")).state.sci2audio
    clock = Clock()
    state.seen = clock.now
    clock.now = state.seen + 900 - 0.001
    assert launch.Watch(state, lambda: None, idle=900, clock=clock).check() is False
    clock.now = state.seen + 900
    assert launch.Watch(state, lambda: None, idle=900, clock=clock).check() is True


def test_the_app_switches_smartscreen_off_before_the_window_engine_starts(
    folders: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(window.WEBVIEW2_ARGUMENTS, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    seen: list[str | None] = []
    monkeypatch.setattr(window, "load_webview", FakeWebview)

    def run_window(webview: Any, *, selftest: Path | None = None) -> int:
        seen.append(os.environ.get(window.WEBVIEW2_ARGUMENTS))
        return 0

    monkeypatch.setattr(window, "run_window", run_window)
    assert window.main([]) == 0
    assert seen == [window.NO_SMARTSCREEN]


def a_waiting_job(state: Any) -> Any:
    return state.board.start(
        JobKind.AUDIO, None, None, lambda job: job.cancel.wait(30) and [], cancellable=True
    )


def test_stopping_the_app_window_cancels_the_job_and_ends_the_event_streams(
    folders: Path,
) -> None:
    sock = bind()
    server = launch.Background(sock, make_config(folders, port=sock.getsockname()[1]))
    assert server.start()
    job = a_waiting_job(server.state)
    server.stop()
    job.join(10)
    assert job.cancel.is_set()
    assert server.state.stopping.is_set()
    assert server.state.board.current is None


def test_stopping_the_app_window_ends_the_server_at_once(folders: Path) -> None:
    sock = bind()
    server = launch.Background(sock, make_config(folders, port=sock.getsockname()[1]))
    assert server.start()
    began = time.monotonic()
    server.stop()
    assert time.monotonic() - began < launch.SHUTDOWN_WAIT + 2
    assert not server._thread.is_alive()


def test_the_quit_page_does_not_warn_about_a_voice_preview(tmp_path: Path) -> None:
    config = make_config(tmp_path, launched_as="browser")
    app = create_app(config)
    state = app.state.sci2audio
    client = browser(app, config)
    preview, gate = a_job(state, JobKind.PREVIEW)
    try:
        assert state.board.current is preview
        assert 'id="quit-making"' not in client.get("/quit").text
    finally:
        gate.set()
        preview.join(10)
