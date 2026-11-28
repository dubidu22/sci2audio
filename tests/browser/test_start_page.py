"""The browser opened at the start page on disk is signed in like one opened at the link (#117)."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, Route, expect

from conftest import Live, inside


def test_the_start_page_on_disk_signs_the_browser_in(
    page: Page, live: Live, tmp_path: Path
) -> None:
    start = live.state.start_page  # as the launcher writes it, so the trade takes it away
    start.folder = tmp_path / "run"
    address = start.write(live.start_url)
    written = start.path
    outside: list[str] = []

    def fence(route: Route) -> None:
        # the start page itself is the one thing outside the server the browser may read
        if inside(route.request.url, live.url) or route.request.url == address:
            route.continue_()
        else:
            outside.append(route.request.url)
            route.abort()

    page.route("**/*", fence)
    page.set_default_timeout(15_000)
    page.goto(address)
    page.wait_for_url(live.url + "/")
    expect(page.locator("main h1")).to_be_visible()
    # signed in: the cookie came with the request to "/", and with the next one
    assert page.request.get(live.url + "/api/v1/settings").status == 200
    assert outside == []
    assert written is not None
    assert not written.exists()  # gone once the token was traded
