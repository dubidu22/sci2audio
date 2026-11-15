"""An audiobook the command line made, in the player (#154): `sci2audio listen` starts a
server that knows the job only by its two folders. Here the first server makes the
audiobook; a second one, started as `listen` starts it, opens it from those folders. The
player plays, the highlight follows, the keyboard reaches the buttons, there is no link to
a document page the second server does not have, and axe finds nothing."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from playwright.sync_api import Browser, Page, Route, expect
from test_player import chunk_id, highlighted, make_audiobook
from web_helpers import make_config

from conftest import Live, check_axe, inside, tab_key
from sci2audio.web import OutsideJob, create_app
from sci2audio.web.launch import bind, uvicorn_config
from sci2audio.web.player import recorded_folder


@contextmanager
def listen_server(tmp_path: Path, job: OutsideJob, live: Live) -> Iterator[tuple[str, str]]:
    """A server as `sci2audio listen` starts it: its own folders, and the one job."""
    sock = bind()
    config = make_config(tmp_path, port=sock.getsockname()[1], outside=(job,))
    app = create_app(config, voice=lambda models_dir: live.voice.source())
    server = uvicorn.Server(uvicorn_config(app))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.01)
    try:
        yield config.origin, config.start_url
    finally:
        app.state.sci2audio.stopping.set()
        app.state.sci2audio.board.shutdown(5)
        server.should_exit = True
        thread.join(10)
        sock.close()


def test_an_audiobook_from_the_command_line_plays_with_its_text(
    signed_in: Page, live: Live, browser: Browser, tmp_path: Path
) -> None:
    document = make_audiobook(signed_in, live)
    stored = live.state.store.get(document)
    assert stored is not None
    folder = recorded_folder(stored.folder, document)
    assert folder is not None
    job = OutsideJob(document, "paper.pdf", stored.folder, folder)
    with listen_server(tmp_path / "listen", job, live) as (origin, start):
        context = browser.new_context()  # its own cookie, as a second server's page has
        page = context.new_page()
        elsewhere: list[str] = []

        def fence(route: Route) -> None:
            if inside(route.request.url, origin):
                route.continue_()
            else:
                elsewhere.append(route.request.url)
                route.abort()

        page.route("**/*", fence)
        page.set_default_timeout(15_000)
        page.goto(start)
        check_axe(page, "start page with a command-line job")
        page.get_by_role("link", name="Listen to paper.pdf with the text").click()
        page.wait_for_url(f"{origin}/documents/{document}/listen")
        expect(page.get_by_role("heading", level=1)).to_have_text("Listen: paper.pdf")
        expect(page.get_by_role("link", name="Back to the document")).to_have_count(0)
        expect(page.get_by_role("link", name="Back to the start page")).to_have_count(1)
        check_axe(page, "listen page of a command-line job")
        page.locator("#listen-title").focus()
        page.keyboard.press(tab_key(page))
        expect(page.locator("#play")).to_be_focused()
        page.locator("#next-chapter").focus()
        page.keyboard.press("Enter")
        assert highlighted(page) == chunk_id(page, "Methods")
        page.locator("#play").focus()
        page.keyboard.press("Space")
        page.wait_for_function("() => document.getElementById('audio').currentTime > 0.2")
        page.keyboard.press("Space")
        page.wait_for_function("() => document.getElementById('audio').paused")
        assert highlighted(page) != ""
        context.close()
        assert elsewhere == [], "the page tried to reach something outside its server"
