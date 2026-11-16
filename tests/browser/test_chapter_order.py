"""Choosing the order of the chapters (#119, UC-03): Move up and Move down buttons on the
document page, by keyboard alone, announced in the status line; the analysis, the
audiobook and the player follow the chosen order."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect
from test_flow import open_paper, update
from test_keyboard import tab_to
from test_player import PER_CHARACTER, chunk_id, highlighted

from conftest import Live, check_axe


def named(action: str, title: str) -> re.Pattern[str]:
    """The button's name: its action, then the chapter's title (marked with its language)."""
    return re.compile(rf"^{action}\W+{title}$")


def order(page: Page) -> list[str]:
    return page.locator("ol.choices li label").all_inner_texts()


def test_the_chapters_are_reordered_by_keyboard_and_read_in_that_order(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    document = open_paper(page, live)
    assert order(page) == ["Introduction", "Methods", "References"]
    up = page.get_by_role("button", name=named("Move up", "Introduction"))
    expect(up).to_be_disabled()  # the first can't go up, the last can't go down
    expect(page.get_by_role("button", name=named("Move down", "References"))).to_be_disabled()
    check_axe(page, "document, chapter order buttons")

    tab_to(page, "move-down-0")
    page.keyboard.press("Enter")
    assert order(page) == ["Methods", "Introduction", "References"]
    expect(page.locator("#move-down-0")).to_be_focused()  # the focus stays on its button
    expect(page.locator("#message")).to_have_text("Introduction is now chapter 2 of 3.")
    expect(page.locator("#changed")).to_be_visible()  # the analysis must be updated first
    page.keyboard.press("Enter")  # down again: now last, so its Move down is disabled
    assert order(page) == ["Methods", "References", "Introduction"]
    expect(page.locator("#move-down-0")).to_be_disabled()
    expect(page.locator("#move-up-0")).to_be_focused()  # the focus moved to its sibling
    page.keyboard.press("Enter")
    assert order(page) == ["Methods", "Introduction", "References"]
    page.emulate_media(color_scheme="dark")
    check_axe(page, "document, chapters reordered, dark")
    page.emulate_media(color_scheme="light")

    update(page)
    assert order(page) == ["Methods", "Introduction", "References"]  # kept by the analysis
    expect(page.locator("#changed")).to_be_hidden()
    report = page.evaluate(
        f"() => fetch('/api/v1/documents/{document}/report').then(r => r.json())"
    )
    assert report["settings"]["chapters"] == [1, 0]

    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(f"{live.url}/documents/{document}/listen")
    expect(page.locator(".chapter-button .ot")).to_have_text(["Methods", "Introduction"])
    page.get_by_role("button", name="Play").click()
    first = chunk_id(page, "Methods")
    page.wait_for_function(f"() => document.getElementById('{first}').classList.contains('now')")
    assert highlighted(page) == first
    src = page.evaluate("() => document.getElementById('audio').getAttribute('src')")
    assert src.endswith("01%20Methods.mp3"), src


def test_without_reordering_nothing_changes(signed_in: Page, live: Live) -> None:
    page = signed_in
    open_paper(page, live)
    page.get_by_role("button", name=named("Move down", "Introduction")).click()
    page.get_by_role("button", name=named("Move up", "Introduction")).click()
    assert order(page) == ["Introduction", "Methods", "References"]
    expect(page.locator("#changed")).to_be_hidden()  # back in printed order: nothing to update
