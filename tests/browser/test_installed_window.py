"""The installed app's own window, driven by Playwright (#13 AC-2, D-797).

WebView2, the window engine on Windows, is Chromium: the installers workflow starts the
installed `sci2audio-app` with a debugging port (`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`,
set by the workflow only, never by the app) and names it in `SCI2AUDIO_APP_CDP`. These
tests then attach to the window as it is, without a browser of their own. Everywhere else
(the browser job, macOS's WKWebView, which has no such port) they are skipped.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright, expect

from conftest import axe_problems

CDP = os.environ.get("SCI2AUDIO_APP_CDP", "")
LIBRARY = re.compile(r"^http://127\.0\.0\.1:\d+/$")

pytestmark = pytest.mark.skipif(
    not CDP, reason="needs the installed app's window (installers workflow, Windows)"
)


@pytest.fixture
def window(playwright: Playwright) -> Iterator[Page]:
    browser = playwright.chromium.connect_over_cdp(CDP, timeout=60_000)
    try:
        pages = [page for context in browser.contexts for page in context.pages]
        assert len(pages) == 1, [page.url for page in pages]  # one window, one page
        page = pages[0]
        page.set_default_timeout(30_000)
        page.wait_for_url(LIBRARY, timeout=60_000)  # the start link leads to the library
        yield page
    finally:
        browser.close()  # attached over CDP: this disconnects, the app keeps running


def origin_of(page: Page) -> str:
    found = re.match(r"^http://127\.0\.0\.1:\d+", page.url)
    assert found, page.url
    return found.group(0)


def test_the_window_shows_the_library_served_on_this_computer(window: Page) -> None:
    expect(window).to_have_title(re.compile("sci2audio"))
    assert window.locator("html").get_attribute("lang") in ("en", "de")
    expect(window.locator("nav.rail")).to_be_visible()
    expect(window.locator("#quit")).to_have_count(0)  # a window closes; Quit is for the browser
    assert axe_problems(window, "the library in the app's window") == []


def test_the_rail_works_by_keyboard_in_the_window(window: Page) -> None:
    origin = origin_of(window)
    link = window.locator("nav.rail a[href='/settings']")
    link.focus()
    window.keyboard.press("Enter")
    window.wait_for_url(f"{origin}/settings")
    expect(window.locator("h1")).to_be_visible()
    assert axe_problems(window, "Settings in the app's window") == []
    home = window.locator("#nav-library")
    home.focus()
    window.keyboard.press("Enter")
    window.wait_for_url(LIBRARY)


def test_the_window_asks_nothing_outside_the_app(window: Page) -> None:
    origin = origin_of(window)
    asked: list[str] = []
    window.on("request", lambda request: asked.append(request.url))
    window.reload(wait_until="networkidle")
    window.goto(f"{origin}/privacy", wait_until="networkidle")
    outside = [url for url in asked if not url.startswith((f"{origin}/", "data:", "blob:"))]
    assert outside == []
    assert any(url.startswith(origin) for url in asked)
