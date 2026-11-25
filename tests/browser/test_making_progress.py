"""The audiobook card while chapter 1 is saved and chapter 2 is spoken (#1054), in the
browser: the whole job and the current chapter's own progress (its bar fills, a line names
it), and "Start listening" and the Listen tab opening without a reload once chapter 1 is
playable, on the job page and on the document's Prepare page (#1059), in English and German,
light and dark, with axe-core; and after a restart, the chapters on disk open the Listen tab
and play (#1059).

Colin's case: the last sentence of chapter 1 was spoken and its MP3 was being written, which
takes minutes for a long chapter; the card already said chapter 2 was being spoken, with
nothing to listen to. Here writing chapter 1's files waits at a gate and the fake voice holds
chapter 2's sentence (`Hold`), so each state stays until the test moves on.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import Page, Route, expect
from test_web_listen_growing import three_chapters

from conftest import Hold, Live, SlowFetch, at_rest, check_axe, inside, serve, settled
from sci2audio.app import JobError, audio
from sci2audio.web.i18n import COOKIE

PDF = {"name": "paper.pdf", "mimeType": "application/pdf", "buffer": three_chapters()}
NBSP = "\u00a0"
WORDS = {
    "en": {
        "saving": "Saving chapter 1 of 3",
        "saved": f"Chapter 1 of 3: 100{NBSP}%",
        "speaking": "Speaking chapter 2 of 3",
        "half": f"Chapter 2 of 3: 50{NBSP}%",
        "none": "Listen · No audio yet",
        "listen": "Listen",
        "start": "Start listening",
    },
    "de": {
        "saving": "Kapitel 1 von 3 wird gespeichert",
        "saved": f"Kapitel 1 von 3: 100{NBSP}%",
        "speaking": "Kapitel 2 von 3 wird gesprochen",
        "half": f"Kapitel 2 von 3: 50{NBSP}%",
        "none": "Anhören · Noch kein Audio",
        "listen": "Anhören",
        "start": "Schon jetzt anhören",
    },
}
# chunks: each chapter's title, then its sentence. Chapter 1's two are spoken, then its files
# wait; after them the voice speaks chapter 2's title and holds its sentence: half of it
SPOKEN_BEFORE_HOLD = 3


@pytest.fixture
def first_chapter_saving(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Any, Any]]:
    """Writing the first chapter's files waits for the gate; yields (reached, gate)."""
    write = audio._Chapters.done
    reached = threading.Event()
    gate = threading.Event()

    def writing(chapters: Any, *args: Any, **kwargs: Any) -> Any:
        if not chapters.added:
            reached.set()
            gate.wait(120)
        return write(chapters, *args, **kwargs)

    monkeypatch.setattr(audio._Chapters, "done", writing)
    try:
        yield reached, gate
    finally:
        gate.set()


def segments(page: Page) -> list[tuple[int, str]]:
    found = page.locator("#job-segments .job-seg").evaluate_all(
        "(bars) => bars.map((bar) => [bar.value, bar.className])"
    )
    return [(value, kind) for value, kind in found]


def described(page: Page) -> str:
    """What a screen reader hears as the job bar's description."""
    return page.locator("#job-bar").evaluate(
        """(bar) => bar.getAttribute("aria-describedby").split(" ")
            .map((id) => document.getElementById(id).textContent).join(" | ")"""
    )


@pytest.mark.parametrize("place", ["job", "document"])
@pytest.mark.parametrize("language", ["en", "de"])
def test_the_card_shows_the_chapter_and_opens_listening_without_a_reload(
    signed_in: Page,
    live: Live,
    first_chapter_saving: tuple[Any, Any],
    language: str,
    place: str,
) -> None:
    page = signed_in
    words = WORDS[language]
    reached, gate = first_chapter_saving
    live.install_voice()
    hold = Hold(after=SPOKEN_BEFORE_HOLD)
    live.voice.fail_on = hold
    try:
        page.set_input_files("#file", files=[PDF])
        page.locator("#open-file button[type=submit]").click()
        page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
        expect(page.locator("#summary")).to_be_visible()
        settled(page)
        page.context.add_cookies([{"name": COOKIE, "value": language, "url": live.url}])
        page.reload()
        settled(page)
        at_rest(page)
        opened = re.search(r"/documents/([0-9a-f]{16})", page.url)
        assert opened is not None
        document = opened.group(1)
        page.locator("#make").click()
        page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
        if place == "document":  # the same card on the document's own address (#1059)
            page.goto(f"{live.url}/documents/{document}")
            expect(page.locator("#making[data-events]")).to_have_count(1)
        expect(page.locator("html")).to_have_attribute("lang", language)
        at_rest(page)
        page.evaluate("() => { window.sameLoad = true; }")
        assert reached.wait(60)

        # chapter 1 is spoken and its files are written: nothing to listen to yet
        expect(page.locator("#job-chapter")).to_have_text(words["saving"])
        expect(page.locator("#job-chapter-progress")).to_have_text(words["saved"])
        assert segments(page) == [(100, "job-seg now"), (0, "job-seg"), (0, "job-seg")]
        expect(page.locator("#start-listening-box")).to_be_hidden()
        expect(page.locator("#tab-listen")).to_have_text(words["none"])
        expect(page.locator("#tab-listen")).not_to_have_attribute("href", re.compile("."))
        assert words["saved"] in described(page)
        check_axe(page, f"{language}, {place} page: chapter 1 being saved")

        # chapter 1 is playable and chapter 2 half spoken: the card and the tab follow
        gate.set()
        assert hold.reached.wait(60)
        expect(page.locator("#job-chapter")).to_have_text(words["speaking"])
        expect(page.locator("#job-chapter-progress")).to_have_text(words["half"])
        assert segments(page) == [(100, "job-seg done"), (50, "job-seg now"), (0, "job-seg")]
        expect(page.locator("#start-listening")).to_be_visible()
        expect(page.locator("#start-listening")).to_have_text(words["start"])
        tab = page.locator("#tab-listen")
        expect(tab).to_have_attribute("href", re.compile(r"^/documents/[0-9a-f]{16}/listen$"))
        expect(tab).to_have_text(words["listen"])
        expect(tab.locator("svg use")).to_have_attribute("href", "#i-speaker")
        assert words["half"] in described(page)
        assert page.evaluate("() => window.sameLoad === true")
        check_axe(page, f"{language}, {place} page: chapter 2 being spoken, chapter 1 playable")
        tab.click()
        page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}/listen$"))
        at_rest(page)
        expect(page.locator("#play")).to_be_enabled()
    finally:
        gate.set()
        hold.gate.set()


@pytest.fixture
def second_chapter_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The job fails as chapter 2's files would be written: chapter 1 stays playable, and
    the audiobook's record (`audio.json`), which only the job's end writes, never comes."""
    write = audio._Chapters.done

    def writing(chapters: Any, *args: Any, **kwargs: Any) -> Any:
        if chapters.added:
            raise JobError("the disk is full")
        return write(chapters, *args, **kwargs)

    monkeypatch.setattr(audio._Chapters, "done", writing)


def test_after_a_restart_the_chapters_on_disk_open_the_listen_tab_and_play(
    signed_in: Page, live: Live, tmp_path: Any, second_chapter_fails: None
) -> None:
    page = signed_in
    live.install_voice()
    page.set_input_files("#file", files=[PDF])
    page.locator("#open-file button[type=submit]").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    # the id alone: WebKit may already show the `#step-check` the page adds after opening
    opened = re.search(r"/documents/([0-9a-f]{16})", page.url)
    assert opened is not None
    document = opened.group(1)
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    at_rest(page)
    page.locator("#make").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#making")).to_contain_text("Making the audiobook stopped")
    assert not (live.config.work_root / document / "audio.json").exists()

    # the next run of sci2audio: no job on its board, only the folder says chapter 1 plays
    with serve(tmp_path, live.voice, SlowFetch()) as second:
        # Leave the old page while the old fence still stands: a font or event stream it
        # was still asking its server for would otherwise reach the new fence, which counts
        # the old port as outside (#1088).
        page.goto("about:blank")
        page.unroute("**/*")

        def fence(route: Route) -> None:
            if inside(route.request.url, second.url):
                route.continue_()
            else:
                live.outside.append(route.request.url)
                route.abort()

        page.route("**/*", fence)
        page.goto(second.start_url)
        page.goto(f"{second.url}/documents/{document}")
        at_rest(page)
        expect(page.locator("#making")).to_have_count(0)  # the job ended with the last run
        tab = page.locator("#tab-listen")
        expect(tab).to_have_attribute("href", f"/documents/{document}/listen")
        expect(tab).to_have_text("Listen")
        check_axe(page, "Prepare after a restart, chapter 1 playable")
        tab.click()
        page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}/listen$"))
        at_rest(page)
        expect(page.locator("#play")).to_be_enabled()
        chapters = page.evaluate(
            "() => JSON.parse(document.getElementById('player-data').textContent)"
            ".chapters.map((c) => c.title)"
        )
        assert chapters == ["Introduction"]
        page.locator("#play").click()
        page.wait_for_function("() => !document.getElementById('audio').paused")
