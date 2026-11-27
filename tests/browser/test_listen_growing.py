"""Listening while the audiobook is still being made (#724, LW-02), in the browser: "Start
listening" on the job card once the first chapter is playable, each new chapter added to the
open Listen page without a reload, the player waiting at the end of the last chapter and going
on by itself, the announcements, the keys, the listening position and axe-core.

The fake voice holds a sentence at a gate (`Hold`), so a chapter is playable while the job
still runs; every test opens the gate before it ends, so the server can stop.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from playwright.sync_api import Page, expect
from test_web_listen_growing import three_chapters

from conftest import Hold, Live, at_rest, check_axe, settled, tab_key

PDF = {"name": "paper.pdf", "mimeType": "application/pdf", "buffer": three_chapters()}
PER_CHARACTER = 600  # samples at 24 kHz: 25 ms a character, a sentence lasts about half a second
# chunks: each chapter's title, then its sentence. After 2 the second chapter's title waits
# (the first chapter is playable); after 4 the third chapter's title (two are)
FIRST_READY = 2
TWO_READY = 4


@contextmanager
def making(page: Page, live: Live, after: int) -> Iterator[Hold]:
    """Open the three-chapter paper and start its audiobook; the voice holds after `after`
    chunks until the block ends (or the test opens the gate)."""
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    hold = Hold(after=after)
    live.voice.fail_on = hold
    try:
        page.set_input_files("#file", files=[PDF])
        page.get_by_role("button", name="Open and analyse").click()
        page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
        expect(page.locator("#summary")).to_be_visible()
        settled(page)
        at_rest(page)
        page.get_by_role("button", name="Make the audiobook").click()
        page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
        assert hold.reached.wait(60)
        yield hold
    finally:
        hold.gate.set()


def open_listen(page: Page) -> None:
    expect(page.locator("#start-listening")).to_be_visible()
    page.get_by_role("link", name="Start listening").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}/listen$"))
    at_rest(page)
    expect(page.locator("#play")).to_be_enabled()


def chapter_buttons(page: Page) -> list[str]:
    return [text.strip() for text in page.locator(".chapter-button .ot").all_inner_texts()]


def test_start_listening_appears_and_opens_the_first_chapter(signed_in: Page, live: Live) -> None:
    page = signed_in
    with making(page, live, FIRST_READY):
        expect(page.locator("#start-listening")).to_have_text("Start listening")
        open_listen(page)
        assert chapter_buttons(page) == ["Introduction"]
        later = page.locator("li.chapter-later")
        expect(later).to_have_count(2)
        expect(later.nth(0)).to_contain_text("Methods")
        expect(later.nth(0)).to_contain_text("being generated")
        expect(page.locator("#now")).to_contain_text("Introduction")
        page.locator("#play").click()
        expect(page.locator("#text .s.now")).to_have_count(1)
        assert page.evaluate("() => !document.getElementById('audio').paused")


def test_a_chapter_that_becomes_ready_appears_without_a_reload(signed_in: Page, live: Live) -> None:
    page = signed_in
    with making(page, live, FIRST_READY) as hold:
        open_listen(page)
        page.evaluate("() => { window.sameLoad = true; }")
        hold.gate.set()
        expect(page.locator(".chapter-button")).to_have_count(3, timeout=60_000)
        assert chapter_buttons(page) == ["Introduction", "Methods", "Results"]
        expect(page.locator("li.chapter-later")).to_have_count(0)
        expect(page.locator("#chapter-2")).to_contain_text("It worked well.")
        expect(page.locator("#growing-status")).to_have_text(
            re.compile(r"^Chapter 3 is ready\. Results$")
        )
        assert page.evaluate("() => window.sameLoad === true")
        # the timeline holds the whole book now
        data = page.evaluate("() => Number(document.getElementById('timeline').max)")
        assert data > 0
        page.locator('.chapter-button[data-chapter="2"]').click()
        expect(page.locator("#now")).to_contain_text("Results")
        expect(page.locator("#chapter-2 .s.now")).to_have_count(1)


@pytest.mark.quarantined(
    issue=1145, reason="no sentence of the next chapter is marked", browser="webkit"
)
def test_the_player_waits_for_the_next_chapter_and_goes_on_by_itself(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    with making(page, live, FIRST_READY) as hold:
        open_listen(page)
        # the last sentence of the only chapter: it ends, and the next is not there yet
        page.locator("#chapter-0 .s", has_text="Things happen").click()
        waiting = page.locator("#waiting")
        expect(waiting).to_be_visible(timeout=20_000)
        expect(waiting).to_have_text(re.compile(r"^The next chapter is still being generated\."))
        assert page.evaluate("() => document.getElementById('audio').ended")
        hold.gate.set()
        expect(waiting).to_be_hidden(timeout=60_000)
        expect(page.locator("#now")).to_contain_text("Methods")
        expect(page.locator("#chapter-1 .s.now")).to_have_count(1, timeout=20_000)


def test_chapter_ready_is_announced_and_reachable_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    # the first chapter's sentence waits, so the card is drawn before any chapter is ready;
    # then each chunk takes a while, so the card stays while the keys reach its link
    with making(page, live, 1) as hold:
        expect(page.locator("#start-listening-box")).to_be_hidden()
        live.voice.on_speak = lambda text: time.sleep(1.5)
        hold.gate.set()
        expect(page.locator("#job-status")).to_have_text("Chapter 1 is ready.", timeout=30_000)
        link = page.locator("#start-listening")
        expect(link).to_be_visible()
        tab = tab_key(page)
        for _ in range(40):
            if page.evaluate("() => document.activeElement?.id") == "start-listening":
                break
            page.keyboard.press(tab)
        expect(link).to_be_focused()
        page.keyboard.press("Enter")
        page.wait_for_url(re.compile(r"/listen$"))
        at_rest(page)
        expect(page.locator("#play")).to_be_enabled()
        expect(page.locator("#growing-status")).to_have_text(
            re.compile(r"^Chapter 2 is ready\. Methods$"), timeout=60_000
        )
        # the new chapter's button takes the focus by the keys and plays it by Enter
        for _ in range(80):
            if page.evaluate("() => document.activeElement?.dataset?.chapter") == "1":
                break
            page.keyboard.press(tab)
        expect(page.locator('.chapter-button[data-chapter="1"]')).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#now")).to_contain_text("Methods")


def test_the_position_and_read_along_work_while_the_book_grows(signed_in: Page, live: Live) -> None:
    page = signed_in
    with making(page, live, TWO_READY):
        open_listen(page)
        assert chapter_buttons(page) == ["Introduction", "Methods"]
        sentence = page.locator("#chapter-1 .s", has_text="We measured it twice.")
        with page.expect_response(re.compile(r"/api/v1/documents/[^/]+/position$")):
            sentence.click()
        expect(sentence).to_have_class(re.compile(r"\bnow\b"))
        page.locator("#play").click()  # pause
        page.reload()
        at_rest(page)
        expect(page.locator("#resume")).to_be_visible()
        expect(page.locator("#resume-text")).to_contain_text("chapter 2")
        page.locator("#resume-continue").click()
        expect(page.locator("#now")).to_contain_text("Methods")


def test_the_growing_listen_page_has_no_axe_problems(signed_in: Page, live: Live) -> None:
    page = signed_in
    with making(page, live, FIRST_READY):
        expect(page.locator("#start-listening")).to_be_visible()
        check_axe(page, "job card with Start listening")
        open_listen(page)
        check_axe(page, "Listen page of a growing book")
        page.locator("#chapter-0 .s", has_text="Things happen").click()
        expect(page.locator("#waiting")).to_be_visible(timeout=20_000)
        check_axe(page, "Listen page waiting for the next chapter")
