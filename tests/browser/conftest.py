"""Browser tests of the interface (#77, #8; D-257, D-259): a real sci2audio server on
127.0.0.1 in this process, driven by Playwright through pytest-playwright.

- Every test here carries the `browser` marker: CI runs them in their own job (Chromium on
  every PR; Chromium, Firefox and WebKit nightly), not in the three-system matrix.
- The server gets the fake voice, a fake voice download and a small download plan, so no
  test needs the 355 MB of voice files or the network; ffmpeg is real (a few seconds).
- The page may only talk to this server: every other request is aborted and fails the
  test, and the Python side runs under `no_network`.
- `SCI2AUDIO_CHROMIUM` names a Chromium to launch instead of Playwright's own (a machine
  with a browser installed some other way).
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "unit"))

import uvicorn
from audio_fakes import FakeVoice
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, Route, expect
from web_helpers import make_config, offline  # noqa: F401 - fixture

from sci2audio.voices import download as download_module
from sci2audio.voices.download import DownloadPlan, RemoteFile
from sci2audio.web import api, create_app, pages
from sci2audio.web.launch import bind, uvicorn_config

HERE = Path(__file__).parent

# the voice download the tests agree to: two small files from a host that doesn't exist
SERVED = {
    "https://example.test/kokoro.bin": b"k" * 4000,
    "https://example.test/voice.bin": b"v" * 1500,
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if Path(str(item.fspath)).is_relative_to(HERE):
            item.add_marker(pytest.mark.browser)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    chromium = os.environ.get("SCI2AUDIO_CHROMIUM")
    if chromium:
        return {**browser_type_launch_args, "executable_path": chromium}
    return browser_type_launch_args


class SlowFetch:
    """The voice download's fetch: serves `SERVED` in blocks, `delay` seconds apart."""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.fetched: list[str] = []

    def __call__(self, url: str, out: Any, on_bytes: Any) -> None:
        self.fetched.append(url)
        data = SERVED[url]
        for start in range(0, len(data), 500):
            time.sleep(self.delay)
            out.write(data[start : start + 500])
            on_bytes(len(data[start : start + 500]))


def small_plan() -> DownloadPlan:
    files = tuple(
        RemoteFile(
            url,
            f"voice/{url.rsplit('/', 1)[1]}",
            len(data),
            hashlib.sha256(data).hexdigest(),
            "Apache-2.0 (test files)",
        )
        for url, data in SERVED.items()
    )
    return DownloadPlan(files, sum(f.size for f in files), ("Test voice: Apache-2.0.",))


@dataclass
class Live:
    """A running server and what the tests may want to look at."""

    url: str
    start_url: str
    config: Any
    state: Any
    voice: FakeVoice
    fetch: SlowFetch
    outside: list[str] = field(default_factory=list)  # requests the page tried elsewhere

    def install_voice(self) -> None:
        for file in small_plan().files:
            target = self.config.models_dir / file.target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(SERVED[file.url])


@pytest.fixture
def live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offline: list[str],  # noqa: F811
) -> Iterator[Live]:
    plan = small_plan()
    for module in (download_module, api, pages):
        monkeypatch.setattr(module, "download_plan", lambda: plan)
    sock = bind()
    port = sock.getsockname()[1]
    config = make_config(tmp_path, port=port)
    voice = FakeVoice()
    fetch = SlowFetch()
    app = create_app(config, fetch=fetch, voice=lambda models_dir: voice.source())
    server = uvicorn.Server(uvicorn_config(app))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.01)
    state = app.state.sci2audio
    try:
        yield Live(config.origin, config.start_url, config, state, voice, fetch)
    finally:
        state.stopping.set()
        state.board.shutdown(5)
        state.kept.dispose()
        server.should_exit = True
        thread.join(10)
        sock.close()


def inside(url: str, origin: str) -> bool:
    """True for a request to the test server, or for a `blob:` URL of its origin: an object
    in the page's memory, never a network request. WebKit routes those too, as images, once
    a file is chosen in a file input (#205)."""
    return url.startswith((origin + "/", "blob:" + origin + "/"))


@pytest.fixture
def signed_in(page: Page, live: Live) -> Iterator[Page]:
    """The page, signed in through the start link like a person, and fenced in."""

    def fence(route: Route) -> None:
        if inside(route.request.url, live.url):
            route.continue_()
        else:
            live.outside.append(route.request.url)
            route.abort()

    page.route("**/*", fence)
    page.set_default_timeout(15_000)
    page.goto(live.start_url)
    assert page.url == live.url + "/"
    yield page
    assert live.outside == [], "the page tried to reach something outside the server"


# --- accessibility (D-257) ----------------------------------------------------------------

AXE = Axe()
WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


def axe_problems(page: Page, where: str) -> list[str]:
    """Every WCAG A/AA violation, whatever its impact, and serious or critical
    best-practice findings (D-257), as readable lines. Waits for the page's load event
    first: a click doesn't, and without app.css axe finds problems that aren't there."""
    page.wait_for_load_state("load")
    position = page.evaluate("() => getComputedStyle(document.querySelector('.skip')).position")
    assert position == "absolute", f"{where}: the page's stylesheet is not applied"
    found: list[str] = []
    wcag = AXE.run(page, options={"runOnly": {"type": "tag", "values": WCAG}})
    best = AXE.run(page, options={"runOnly": {"type": "tag", "values": ["best-practice"]}})
    for result, serious_only in ((wcag, False), (best, True)):
        for violation in result.response["violations"]:
            if serious_only and violation.get("impact") not in ("serious", "critical"):
                continue
            targets = [node.get("target") for node in violation.get("nodes", [])][:3]
            found.append(f"{where}: {violation['id']} ({violation.get('impact')}) {targets}")
    return found


def settled(page: Page) -> None:
    """Wait until the document page no longer follows the analysis and is fully loaded.
    The report can be on disk while the job is still the running one; a page drawn in that
    moment shows the summary and still reloads itself when the job ends, under a test's key
    presses (#138). The reloaded page has no `data-events` as soon as its first bytes are
    parsed, before app.css applies: a Tab then gets the browser's own 1 px focus ring, so
    wait for the load event and the page's stylesheet too (#166)."""
    expect(page.locator("#document[data-events]")).to_have_count(0)
    page.wait_for_load_state("load")
    expect(page.locator(".skip")).to_have_css("position", "absolute")  # app.css applies


def check_axe(page: Page, where: str) -> None:
    """axe in the page's colour scheme and in the other one."""
    problems = axe_problems(page, f"{where} (light)")
    page.emulate_media(color_scheme="dark")
    problems += axe_problems(page, f"{where} (dark)")
    page.emulate_media(color_scheme="light")
    assert problems == []
