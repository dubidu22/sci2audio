"""The installed app's interface, driven by Playwright (#13 AC-2, D-797): "Playwright tests
run against the app window's content where possible".

Linux: the installed AppImage opens its start link in the browser; the installers workflow
catches that link with a stand-in browser and names it in `SCI2AUDIO_APP_START`, and these
tests open it in Playwright's Chromium, as a person's browser would, and end with Quit.

Windows (`SCI2AUDIO_APP_CDP`): WebView2 is Chromium, so a window started with a debugging
port (set through `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`, never by the app) can be attached
to. The hosted runners can't use it: their processes are elevated, and an elevated WebView2
ignores that variable, so there the window is checked by the app's own self test only.
macOS's WKWebView has no such port. Everywhere else these tests are skipped.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, Playwright, expect

from conftest import axe_problems

CDP = os.environ.get("SCI2AUDIO_APP_CDP", "")
START = os.environ.get("SCI2AUDIO_APP_START", "")
LIBRARY = re.compile(r"^http://127\.0\.0\.1:\d+/$")

pytestmark = pytest.mark.skipif(
    not (CDP or START), reason="needs the installed app (installers workflow)"
)


@pytest.fixture(scope="module")
def window(playwright: Playwright) -> Iterator[Page]:
    if START:  # the browser path: a browser of our own opens the app's start link
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(START)
    else:  # the window: attach to it as it is
        browser = playwright.chromium.connect_over_cdp(CDP, timeout=60_000)
        pages = [page for context in browser.contexts for page in context.pages]
        assert len(pages) == 1, [page.url for page in pages]  # one window, one page
        page = pages[0]
    try:
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
    window.wait_for_url(LIBRARY)
    expect(window.locator("nav.rail")).to_be_visible()
    # a window closes; Quit is for the browser
    expect(window.locator("#quit")).to_have_count(1 if START else 0)
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


@pytest.mark.skipif(not START, reason="Quit is for the app in the browser")
def test_quit_in_the_browser_stops_the_installed_app(window: Page) -> None:
    """Last: the workflow then waits for the app's process to end by itself."""
    origin = origin_of(window)
    window.goto(f"{origin}/")
    window.locator("#quit").click()
    window.wait_for_url(f"{origin}/quit")
    window.locator("#quit-now").click()
    expect(window.locator("#quit-done")).to_be_visible()
