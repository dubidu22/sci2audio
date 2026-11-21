"""The update check and the two headers of #172 in a real browser (#217, D-837): turned on
in Settings, its result shown there and in the rail; the page itself never contacts the
release source (the fence in `signed_in` fails on any outside request); Permissions-Policy
and COEP on the pages and the audio, and no console complaint about either."""

from __future__ import annotations

import json
import threading
from typing import Any

from playwright.sync_api import ConsoleMessage, Page, expect

from conftest import Live, at_rest, check_axe
from sci2audio.app.updates import STATE_NAME, UpdateCheck
from sci2audio.web.security import PERMISSIONS_POLICY


class Release:
    def __init__(self) -> None:
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self) -> bytes:
        with self.lock:
            self.calls += 1
        return json.dumps({"tag_name": "v9.0.0", "html_url": "https://evil.example/"}).encode()


def fake_release(live: Live) -> Release:
    release = Release()
    live.state.updates = UpdateCheck(
        live.config.config_file.parent / STATE_NAME, fetch=release, current="1.4.0"
    )
    return release


def test_the_update_check_is_off_until_turned_on(signed_in: Page, live: Live) -> None:
    page = signed_in
    release = fake_release(live)
    page.goto(live.url + "/settings")
    switch = page.get_by_role("switch", name="Look for new versions")
    expect(switch).not_to_be_checked()
    expect(page.locator("#update-notice")).to_have_count(0)
    check_axe(page, "settings, update check off")
    assert release.calls == 0

    with page.expect_response(lambda r: r.url.endswith("/api/v1/updates")) as answer:
        switch.check()
    assert answer.value.status == 200
    live.state.updates.join(10)
    assert release.calls == 1
    page.reload()
    expect(page.locator("#updates-status")).to_contain_text("is out: sci2audio 9.0.0")
    notice = page.locator("#update-notice")
    expect(notice).to_have_attribute(
        "href", "https://github.com/dubidu22/sci2audio/releases/tag/v9.0.0"
    )
    expect(page.get_by_role("switch", name="Look for new versions")).to_be_checked()
    check_axe(page, "settings, update check on with a newer version")

    page.goto(live.url + "/")
    expect(page.locator("#update-notice")).to_be_visible()
    page.goto(live.url + "/settings")
    # a click while the page's fonts still arrived did not go through: WebKit found the
    # switch unchanged after it (#699)
    at_rest(page)
    with page.expect_response(lambda r: r.url.endswith("/api/v1/updates")):
        page.get_by_role("switch", name="Look for new versions").uncheck()
    page.reload()
    expect(page.locator("#update-notice")).to_have_count(0)
    assert release.calls == 1


def test_the_headers_break_nothing_and_raise_no_complaint(signed_in: Page, live: Live) -> None:
    page = signed_in
    complaints: list[str] = []

    def heard(message: ConsoleMessage) -> None:
        text = message.text
        if any(word in text for word in ("Permissions-Policy", "Permissions policy", "Embedder")):
            complaints.append(text)

    page.on("console", heard)
    seen: list[dict[str, Any]] = []
    page.on("response", lambda r: seen.append(r.all_headers()))
    for path in ("/", "/settings", "/voice", "/privacy"):
        page.goto(live.url + path)
        page.wait_for_load_state("load")
        assert page.evaluate("() => crossOriginIsolated") is True, path
    assert seen
    for headers in seen:
        assert headers["permissions-policy"] == PERMISSIONS_POLICY
        assert headers["cross-origin-embedder-policy"] == "require-corp"
    # the fonts and icons still load under COEP
    assert page.evaluate("() => document.fonts.check('16px Inter') || document.fonts.size > 0")
    assert complaints == []
