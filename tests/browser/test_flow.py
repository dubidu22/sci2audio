"""The main flow in a real browser (#77, #8): open a file, read the pre-analysis, switch a
category and chapters, set up the voice with consent, listen to a preview, choose the
speed, make the audiobook, replace it, free the speech cache; with axe-core on every page
on the way (D-257)."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Route, expect
from web_helpers import paper_bytes

from conftest import Hold, Live, at_rest, check_axe, inside, settled, small_plan
from sci2audio.app import JobSettings, save_settings
from sci2audio.voices import PREVIEW_TEXT, PREVIEW_TEXTS
from sci2audio.web import pages
from sci2audio.web.jobs import JobKind, JobRecord

PDF = {"name": "paper.pdf", "mimeType": "application/pdf", "buffer": paper_bytes()}
GERMAN_NOTE = (
    Path(__file__).resolve().parents[1] / "corpus" / "markdown" / "sci2audio-beispiel-notiz.md"
)


def until(check: Any, timeout: float = 10.0) -> None:
    """Wait for `check()` (the page's CSP forbids the string evaluation `wait_for_function`
    uses, which is as it should be)."""
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def open_paper(page: Page, live: Live) -> str:
    """Open the paper from the start page; returns the document id once its report shows
    and the page no longer reloads itself for the analysis (in WebKit on macOS that late
    reload cancels a test's own page.reload(), #205)."""
    page.set_input_files("#file", files=[PDF])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    return page.url.rsplit("/", 1)[1].split("#")[0]


def update(page: Page) -> None:
    page.get_by_role("button", name="Update the analysis").click()
    expect(page.locator("#changed")).to_be_hidden()  # the page came back with a new report
    expect(page.locator("#step-check")).to_be_focused()
    # a page drawn while the analysis was still the running job reloads once more when it
    # ends; its buttons are wired only after that (#411, as for open_paper)
    settled(page)


def test_the_main_flow(signed_in: Page, live: Live) -> None:
    page = signed_in
    expect(page.get_by_role("heading", level=1)).to_have_text("Library")
    check_axe(page, "start page, nothing opened")

    document = open_paper(page, live)
    expect(page.locator("#summary")).to_contain_text("3 chapters, 2 of them chosen")
    expect(page.locator("#counts-citations")).to_contain_text("1 heard")
    expect(page.get_by_role("checkbox", name=re.compile("^References"))).not_to_be_checked()
    expect(page.locator("#make")).to_have_attribute("aria-disabled", "true")
    expect(page.locator("#make-note")).to_have_text("Set up the voice first.")
    check_axe(page, "document with its report, voice missing")
    page.get_by_text(re.compile(r"^Citations: author-year .*: 1 change$")).click()
    expect(page.get_by_role("cell", name="(Smith, 2020)", exact=True)).to_be_visible()
    check_axe(page, "document with a list of changes open")

    # a switch off: its change is listed as switched off (UC-02)
    page.get_by_role("switch", name=re.compile("^Citations")).uncheck()
    expect(page.locator("#changed")).to_be_visible()
    update(page)
    expect(page.locator("#counts-citations")).to_contain_text("0 heard")
    expect(page.locator("#counts-citations")).to_contain_text("1 switched off")
    expect(page.get_by_role("switch", name=re.compile("^Citations"))).not_to_be_checked()

    # back on, and its chapter not chosen: listed as not spoken (UC-03, D-100)
    page.get_by_role("switch", name=re.compile("^Citations")).check()
    page.get_by_role("checkbox", name="Introduction").uncheck()
    update(page)
    expect(page.locator("#summary")).to_contain_text("3 chapters, 1 of them chosen")
    expect(page.locator("#counts-citations")).to_contain_text("1 in chapters not chosen")
    expect(page.get_by_role("checkbox", name="Introduction")).not_to_be_checked()
    page.get_by_role("button", name="Choose all").click()
    expect(page.locator("#changed")).to_be_visible()
    page.get_by_role("button", name="Choose none").click()
    page.get_by_role("checkbox", name="Methods").check()
    expect(page.locator("#changed")).to_be_hidden()  # the same choice as the report again

    # the analysis files can be saved
    with page.expect_download() as saved:
        page.get_by_role("link", name="report to read").click()
    assert saved.value.suggested_filename == "paper.report.md"

    # the voice: the whole download first, nothing without consent (VA-03, D-252)
    page.get_by_role("link", name="Set up the voice").first.click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Set up the voice")
    expect(page.get_by_role("cell", name="voice/kokoro.bin")).to_be_visible()
    expect(page.get_by_text("example.test")).to_be_visible()
    check_axe(page, "voice setup page")
    page.get_by_role("button", name="Download the voice").click()
    time.sleep(0.3)
    assert live.fetch.fetched == []
    assert page.url.endswith("/voice")
    page.get_by_role("checkbox", name=re.compile("I agree")).check()
    page.get_by_role("button", name="Download the voice").click()
    page.wait_for_url(re.compile(r"/jobs/voices-\d+"))
    expect(page.locator("#result")).to_have_text(
        "The voice is installed. Nothing needs to be downloaded."
    )
    assert sorted(live.fetch.fetched) == sorted(
        ["https://example.test/kokoro.bin", "https://example.test/voice.bin"]
    )
    check_axe(page, "voice download done")

    # preview and speed (VA-05, D-249, D-251)
    page.goto(f"{live.url}/documents/{document}")
    expect(page.locator("#make")).not_to_have_attribute("aria-disabled", "true")
    speed = page.get_by_role("slider", name="Speed")
    speed.focus()
    for _ in range(5):
        page.keyboard.press("ArrowRight")
    expect(page.locator("#speed-value")).to_have_text("1.25 times")
    expect(speed).to_have_attribute("aria-valuetext", "1.25 times")
    page.get_by_label("Voice", exact=True).select_option("bm_george")
    abbreviations = page.get_by_role("group", name="Spelled-out abbreviations")
    expect(abbreviations.get_by_role("radio", name="Normal")).to_be_checked()
    abbreviations.get_by_role("radio", name="Slower").check()  # #295
    page.get_by_role("button", name="Listen").click()
    player = page.locator("#preview-audio")
    expect(player).to_be_visible()
    expect(player).to_be_focused()
    until(lambda: player.evaluate("audio => audio.readyState") >= 1)  # the WAV loaded
    assert live.voice.spoken[-1] == (PREVIEW_TEXT, "bm_george", 1.25)
    assert live.voice.letter_speeds[-1] == 0.7
    check_axe(page, "document with the voice installed and a preview")

    # make the audiobook (WI-04) and save its files
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    expect(page.locator("#result")).to_be_focused()
    links = page.locator("ul.files a")
    names = [re.sub(r"^Save (.*) \(.*\)$", r"\1", text) for text in links.all_inner_texts()]
    assert names[0] == "paper.m4b"  # named after the file, as the PDF has no title
    assert any(name.endswith(".mp3") for name in names)
    assert names[-1].endswith(".readalong.json")
    for link in links.all():
        answer = page.request.get(live.url + link.get_attribute("href"))
        assert answer.status == 200
        assert answer.headers["content-disposition"].startswith("attachment")
    expect(page.locator("#making").get_by_text(str(live.config.output_folder))).to_be_visible()
    check_axe(page, "audiobook done")
    settings = page.request.get(f"{live.url}/api/v1/settings").json()["settings"]
    assert settings["voice"] == "bm_george"  # remembered for the next document (D-246)
    assert settings["speed"] == 1.25
    assert settings["letter_pace"] == "slower"
    assert settings["output_folder"] == str(live.config.output_folder)
    spoken = {text for text, _, _ in live.voice.spoken}
    assert "We measured it twice." in spoken
    assert not any("Smith" in text for text in spoken)  # chapter 1 was not chosen

    # the job is shown on Prepare (#391): the header's Listen tab now leads to the player
    expect(page.get_by_role("link", name="Prepare")).to_have_attribute("aria-current", "page")
    expect(page.locator("#tab-listen")).to_have_attribute("href", f"/documents/{document}/listen")

    # again: the files exist; replacing them is its own button (D-254)
    page.get_by_role("link", name="Prepare").click()
    at_rest(page)  # a click while the Prepare page's fonts still arrived did nothing (WebKit)
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("The audiobook files exist already.")
    # the app's own words follow as details, in English (D-291)
    expect(page.locator("#making span[lang=en]")).to_contain_text("these files exist already")
    check_axe(page, "audiobook files exist")
    page.get_by_role("button", name="Replace these files").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")

    # free the speech cache (D-158), after its confirm names what goes (D-733)
    expect(page.locator("#cache-text")).to_contain_text("sci2audio keeps the spoken sentences")
    page.locator("#cache-free-open").click()
    expect(page.locator("#free-goes")).to_contain_text("deletes every sentence spoken")
    check_axe(page, "the free confirm")
    page.get_by_role("button", name="Delete the speech cache").click()
    expect(page.locator("#message")).to_have_text("The speech cache is empty.")
    expect(page.locator("#message")).to_be_focused()
    folder = live.config.work_root / document / "chunks"
    assert not folder.exists() or not any(folder.rglob("*.wav"))


def test_progress_while_speaking_and_pause(signed_in: Page, live: Live) -> None:
    """The job inline on Prepare (#391): the chapter being spoken, how far and how long,
    the sentences; Pause is today's cancel and keeps what is spoken."""
    page = signed_in
    live.install_voice()
    hold = Hold(after=1)  # the second sentence waits, so Pause comes mid-job
    live.voice.fail_on = hold
    open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    try:
        assert hold.reached.wait(30)
        expect(page.locator("#job-chapter")).to_have_text(re.compile(r"^Speaking chapter \d of 2$"))
        expect(page.locator("#job-progress")).to_contain_text(re.compile(r"\d of \d sentences"))
        expect(page.locator("#job-left")).to_contain_text("measuring the speed")
        bar = page.get_by_role("progressbar", name="Making the audiobook")
        expect(bar).to_have_attribute("aria-valuetext", re.compile("^Speaking chapter"))
        expect(page.locator("#job-segments .seg")).to_have_count(2)
        expect(page.locator("#job-segments .seg.now")).to_have_count(1)
        # the rail's shelf names the running job and how far it is (#387)
        expect(page.locator("#shelf-job")).to_contain_text("Audiobook of paper.pdf")
        expect(page.locator("#shelf-job-state")).to_contain_text("speaking")
        check_axe(page, "audiobook running")
        with page.expect_response(
            re.compile(r"/api/v1/jobs/[^/]+/cancel$")
        ):  # the cancel is in before the gate opens
            page.get_by_role("button", name="Pause").click()
        expect(page.locator("#message")).to_have_text("Pausing…")
    finally:
        hold.gate.set()
    expect(page.locator("#result")).to_have_text(re.compile(r"^Paused in chapter [12]\.$"))
    expect(page.locator("#job-kept")).to_contain_text(re.compile(r"\d of 4 sentences"))
    expect(page.get_by_role("button", name="Resume")).to_be_visible()
    expect(page.locator("#cache-free-open")).to_have_text(re.compile(r"^Free the speech cache \("))
    check_axe(page, "audiobook paused")


def test_pause_then_resume_speaks_only_what_is_missing(signed_in: Page, live: Live) -> None:
    """Pause keeps every sentence spoken so far; Resume speaks only the rest (#391)."""
    page = signed_in
    live.install_voice()
    hold = Hold(after=2)
    live.voice.fail_on = hold
    open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    try:
        assert hold.reached.wait(30)
        with page.expect_response(
            re.compile(r"/api/v1/jobs/[^/]+/cancel$")
        ):  # the cancel is in before the gate opens
            page.get_by_role("button", name="Pause").click()
        expect(page.locator("#message")).to_have_text("Pausing…")
    finally:
        hold.gate.set()
    expect(page.locator("#result")).to_have_text(re.compile(r"^Paused in chapter [12]\.$"))
    expect(page.locator("#result")).to_be_focused()
    before = list(live.voice.texts)
    assert 2 <= len(before) < 4, before
    live.voice.fail_on = lambda text: False
    page.get_by_role("button", name="Resume").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    again = live.voice.texts[len(before) :]
    assert again, "Resume spoke nothing"
    assert not set(again) & set(before), "Resume spoke a kept sentence again"


def test_resume_of_a_paused_replace_never_asks_to_replace_again(
    signed_in: Page, live: Live
) -> None:
    """A run that replaces an earlier audiobook, paused and resumed, goes on with the
    sentences it spoke and never stops at the files it was already allowed to replace
    (D-733). Before, Resume sent no "replace" and showed the existing-files card."""
    page = signed_in
    live.install_voice()
    document = open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    # a new speech (as after an update of the voice): nothing is kept to reuse
    deleted = page.request.delete(
        f"{live.url}/api/v1/documents/{document}/chunks", headers={"Origin": live.url}
    )
    assert deleted.status == 204

    page.get_by_role("link", name="Prepare").click()
    at_rest(page)  # a click while the Prepare page's fonts still arrived did nothing (WebKit)
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("The audiobook files exist already.")
    # replacing never needs the cache freed; with nothing spoken, nothing is said kept
    expect(page.locator("#cache-free-open")).to_have_count(0)
    expect(page.locator("#job-kept")).to_have_count(0)

    hold = Hold(after=2)
    live.voice.fail_on = hold
    first = len(live.voice.texts)  # what the finished build spoke
    page.get_by_role("button", name="Replace these files").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    try:
        assert hold.reached.wait(30)
        with page.expect_response(re.compile(r"/api/v1/jobs/[^/]+/cancel$")):
            page.get_by_role("button", name="Pause").click()
    finally:
        hold.gate.set()
    expect(page.locator("#result")).to_have_text(re.compile(r"^Paused in chapter [12]\.$"))
    before = list(live.voice.texts[first:])
    assert 2 <= len(before) < 4, before
    live.voice.fail_on = lambda text: False
    with page.expect_request(re.compile(r"/api/v1/jobs$")) as started:
        page.get_by_role("button", name="Resume").click()
    assert started.value.post_data_json["overwrite"] is True
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    again = live.voice.texts[first + len(before) :]
    assert again, "Resume spoke nothing"
    assert not set(again) & set(before), "Resume spoke a kept sentence again"


def test_a_paused_first_build_resumes_without_replace(signed_in: Page, live: Live) -> None:
    """Resume of a run that replaced nothing still does not say "replace": a file that
    appeared meanwhile is refused as before (D-163, D-733)."""
    page = signed_in
    live.install_voice()
    hold = Hold(after=1)
    live.voice.fail_on = hold
    open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    try:
        assert hold.reached.wait(30)
        with page.expect_response(re.compile(r"/api/v1/jobs/[^/]+/cancel$")):
            page.get_by_role("button", name="Pause").click()
    finally:
        hold.gate.set()
    expect(page.locator("#result")).to_have_text(re.compile(r"^Paused in chapter [12]\.$"))
    live.voice.fail_on = lambda text: False
    with page.expect_request(re.compile(r"/api/v1/jobs$")) as started:
        page.get_by_role("button", name="Resume").click()
    assert started.value.post_data_json["overwrite"] is False
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")


def test_freeing_the_speech_cache_asks_first(signed_in: Page, live: Live) -> None:
    """The cache button opens a confirm that names what is lost; only its own button sends
    the DELETE (D-733). Without the confirm one click deleted every spoken sentence."""
    page = signed_in
    live.install_voice()
    document = open_paper(page, live)
    deletes: list[str] = []
    page.on(
        "request",
        lambda request: (
            deletes.append(request.url)
            if request.method == "DELETE" and request.url.endswith("/chunks")
            else None
        ),
    )
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    size = page.request.get(f"{live.url}/api/v1/documents/{document}").json()
    assert size["speech_cache_bytes"] > 0
    page.locator("#cache-free-open").click()
    expect(page.locator("#free-goes")).to_contain_text(
        "This deletes every sentence spoken for this document ("
    )
    expect(page.get_by_role("button", name="Delete the speech cache")).to_be_enabled()
    page.wait_for_timeout(500)
    assert deletes == [], "opening the confirm deleted the speech cache"
    found = page.request.get(f"{live.url}/api/v1/documents/{document}").json()
    assert found["speech_cache_bytes"] == size["speech_cache_bytes"]
    check_axe(page, "the free confirm open")
    page.get_by_role("button", name="Delete the speech cache").click()
    expect(page.locator("#message")).to_have_text("The speech cache is empty.")
    assert len(deletes) == 1
    expect(page.locator("#free-box")).to_have_count(0)


def test_cancel_deletes_the_speech_cache_only_once_the_voice_stopped(
    signed_in: Page, live: Live
) -> None:
    """Cancel = Pause, then the DELETE of the speech cache, and only after the job stopped
    (D-694): while the voice still holds a sentence, no DELETE goes out. Without the wait
    the DELETE would race a chunk still being written."""
    page = signed_in
    live.install_voice()
    hold = Hold(after=1)
    live.voice.fail_on = hold
    document = open_paper(page, live)
    deletes: list[str] = []
    page.on(
        "request",
        lambda request: (
            deletes.append(request.url)
            if request.method == "DELETE" and request.url.endswith("/chunks")
            else None
        ),
    )
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    job = page.url.rsplit("/", 1)[1].split("#")[0]
    try:
        assert hold.reached.wait(30)
        page.get_by_text("Cancel", exact=True).click()  # the confirm opens
        confirm = page.locator("#cancel-box")
        expect(confirm).to_contain_text("deletes the speech cache")
        # the confirm names the cache's size, read when it opens: one sentence is spoken
        expect(page.locator("#cancel-size")).to_have_text(
            re.compile(r"^Its size now: [1-9][0-9.,]*\s(bytes|KB|MB)\.$")
        )
        check_axe(page, "the cancel confirm")
        page.get_by_role("button", name="Cancel and delete the speech cache").click()
        expect(page.locator("#message")).to_have_text("Stopping the voice…")
        # the voice holds its sentence: the job runs on, and no DELETE may go out
        page.wait_for_timeout(1500)
        state = page.request.get(f"{live.url}/api/v1/jobs/{job}").json()["state"]
        assert state == "running"
        assert deletes == [], "the speech cache was deleted while the job still ran"
    finally:
        hold.gate.set()
    expect(page.locator("#result")).to_have_text("Cancelled. The speech cache is empty.")
    assert len(deletes) == 1
    found = page.request.get(f"{live.url}/api/v1/documents/{document}").json()
    assert found["speech_cache_bytes"] == 0
    expect(page.get_by_role("button", name="Make it again")).to_be_visible()
    check_axe(page, "audiobook cancelled")


def test_cancel_gives_up_on_a_voice_that_does_not_stop(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A voice stuck in native code may ignore the cancel. Cancel waits a while (two
    minutes; here 1.5 s), then says the voice did not stop, deletes nothing, and gives its
    button back (#433 N3)."""
    page = signed_in
    monkeypatch.setattr(pages, "STOP_WAIT_MS", 1500)
    live.install_voice()
    hold = Hold(after=1)
    live.voice.fail_on = hold
    open_paper(page, live)
    deletes: list[str] = []
    page.on(
        "request",
        lambda request: deletes.append(request.url) if request.method == "DELETE" else None,
    )
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    job = page.url.rsplit("/", 1)[1].split("#")[0]
    try:
        assert hold.reached.wait(30)
        page.locator("#job-cancel-open").click()
        cancel = page.get_by_role("button", name="Cancel and delete the speech cache")
        cancel.click()
        message = page.locator("#message")
        expect(message).to_have_text(
            "The voice did not stop within two minutes, so nothing was deleted. "
            "Try Cancel again, or wait for the job to end."
        )
        expect(message).to_be_focused()
        assert deletes == []
        expect(cancel).not_to_have_attribute("aria-disabled", "true")
        state = page.request.get(f"{live.url}/api/v1/jobs/{job}").json()["state"]
        assert state == "running"  # the job never left running
    finally:
        hold.gate.set()
    # once the voice lets go, the pause it was asked for lands: nothing was deleted
    expect(page.locator("#result")).to_have_text(re.compile(r"^Paused"))
    assert deletes == []


def gated(state: Any, kind: JobKind, document: str | None) -> tuple[JobRecord, threading.Event]:
    gate = threading.Event()
    job = state.board.start(
        kind, document, None, lambda job: gate.wait(30) and [], cancellable=False
    )
    return job, gate


def test_a_busy_server_says_so(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = open_paper(page, live)
    job, gate = gated(live.state, JobKind.VOICES, None)
    try:
        page.reload()
        expect(page.locator("#shelf-job")).to_contain_text("Voice download")
        page.get_by_role("checkbox", name="Methods").uncheck()
        page.get_by_role("button", name="Update the analysis").click()
        expect(page.locator("#message")).to_contain_text(f"job {job.id} is running")
        expect(page.locator("#message")).to_be_focused()
        check_axe(page, "document while another job runs")
    finally:
        gate.set()
        job.join(10)
    assert document


def test_pasted_text_opens_and_is_analysed(signed_in: Page, live: Live) -> None:
    """Pasted text is kept as `<name>.txt` and read as a plain-text file (#74, D-350)."""
    page = signed_in
    pasted = "Pasted words for the test.\n\nA second paragraph."
    page.get_by_text("Or paste text").click()  # the library's paste box (#389)
    page.get_by_label("Text to open").fill(pasted)
    page.get_by_label("Name for the pasted text").fill("My notes")
    check_axe(page, "start page with pasted text")
    page.get_by_role("button", name="Open the text").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)  # axe must not run while the page reloads after its analysis (#365)
    # the analysis names the text after its name; the file is `My notes.txt`
    expect(page.get_by_role("heading", level=1)).to_have_text("My notes")
    expect(page.locator(".side")).to_contain_text("My notes.txt")
    check_axe(page, "document from pasted text")


def test_a_damaged_file_shows_the_apps_message(signed_in: Page, live: Live) -> None:
    page = signed_in
    damaged = {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 nothing"}
    page.set_input_files("#file", files=[damaged])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#analysis-error")).to_contain_text("The analysis failed:")
    expect(page.get_by_role("button", name="Analyse the document")).to_be_visible()
    settled(page)  # #365
    check_axe(page, "document whose analysis failed")


def test_a_file_sci2audio_cant_read_is_refused(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.set_input_files(
        "#file",
        files=[{"name": "notes.docx", "mimeType": "application/octet-stream", "buffer": b"x"}],
    )
    page.get_by_role("button", name="Open and analyse").click()
    # the kind's sentence, then the app's own words as details in English (D-291)
    expect(page.locator("#message")).to_have_text(
        "sci2audio can't read this kind of file. "
        "Details from sci2audio: notes.docx: "
        "sci2audio can read .epub, .markdown, .md, .pdf, .txt files only"
    )
    expect(page.locator("#message span[lang=en]")).to_have_text(
        "notes.docx: sci2audio can read .epub, .markdown, .md, .pdf, .txt files only"
    )
    expect(page.locator("#message")).to_be_focused()
    check_axe(page, "start page with an error")


def test_a_lost_server_is_named(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.route(f"{live.url}/api/**", lambda route: route.abort("connectionrefused"))
    page.set_input_files("#file", files=[PDF])
    page.get_by_role("button", name="Open and analyse").click()
    expect(page.locator("#message")).to_have_text(
        "sci2audio can't be reached. Is it still running in its terminal window?"
    )


LOST = "sci2audio can't be reached. Is it still running in its terminal window?"


def lose_the_server(page: Page, live: Live) -> None:
    """The server goes away under an open page: its event streams end and every new request
    is refused, as when the terminal window was closed."""
    page.route(f"{live.url}/api/**", lambda route: route.abort("connectionrefused"))
    live.state.stopping.set()


def test_the_job_page_says_when_the_server_is_gone(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = open_paper(page, live)
    job, gate = gated(live.state, JobKind.AUDIO, document)
    try:
        page.goto(f"{live.url}/jobs/{job.id}")
        expect(page.get_by_role("progressbar", name="Making the audiobook")).to_be_visible()
        lose_the_server(page, live)
        expect(page.locator("#message")).to_have_text(LOST, timeout=15_000)  # LOST_AFTER is 5 s
        expect(page.locator("#message")).to_be_focused()
    finally:
        gate.set()
        job.join(10)


def test_the_document_page_says_when_the_server_is_gone_while_it_analyses(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    document = open_paper(page, live)
    job, gate = gated(live.state, JobKind.SCRIPT, document)
    try:
        page.reload()
        expect(page.locator("#message")).to_have_text("Analysing the document…")
        expect(page.get_by_role("button", name="Analyse the document")).to_have_count(0)
        check_axe(page, "document while it analyses")
        lose_the_server(page, live)
        expect(page.locator("#message")).to_have_text(LOST, timeout=15_000)  # LOST_AFTER is 5 s
        expect(page.locator("#message")).to_be_focused()
    finally:
        gate.set()
        job.join(10)


def test_make_starts_nothing_until_the_report_matches_and_has_a_chapter(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    make = page.get_by_role("button", name="Make the audiobook")
    expect(make).not_to_have_attribute("aria-disabled", "true")

    # a switch changed and not yet analysed: Make says so and starts nothing (D-245)
    page.get_by_role("switch", name=re.compile("^Citations")).uncheck()
    expect(make).to_have_attribute("aria-disabled", "true")
    expect(page.locator("#make-note")).to_have_text(
        "Update the analysis first to see what your changes do."
    )
    make.click(force=True)  # aria-disabled: Playwright would wait for it to be enabled
    expect(page.locator("#message")).to_have_text(
        "Update the analysis first to see what your changes do."
    )
    expect(page.locator("#message")).to_be_focused()
    page.get_by_role("switch", name=re.compile("^Citations")).check()

    # no chapter chosen: nothing to read, so nothing starts
    page.get_by_role("button", name="Choose none").click()
    update(page)
    expect(page.locator("#summary")).to_contain_text("3 chapters, 0 of them chosen")
    expect(make).to_have_attribute("aria-disabled", "true")
    note = "Choose at least one chapter and update the analysis."
    expect(page.locator("#make-note")).to_have_text(note)
    make.click(force=True)  # aria-disabled: Playwright would wait for it to be enabled
    expect(page.locator("#message")).to_have_text(note)
    expect(page.locator("#message")).to_be_focused()
    # choosing one shows the update is due; once updated, Make is free again
    page.get_by_role("checkbox", name="Methods").check()
    expect(page.locator("#make-note")).to_have_text(
        "Update the analysis first to see what your changes do."
    )
    update(page)
    expect(make).not_to_have_attribute("aria-disabled", "true")
    kinds = [job.kind for job in live.state.board.all()]
    assert JobKind.AUDIO not in kinds  # no press of Make started anything


def test_the_fence_lets_only_the_server_and_its_own_blobs_through() -> None:
    """#205: WebKit routes `blob:` URLs of the page's origin; they are no network requests."""
    origin = "http://127.0.0.1:5000"
    assert inside(origin + "/documents/1", origin)
    assert inside("blob:" + origin + "/7c1e2b3a-0d4e-4f5a-9b6c-1d2e3f4a5b6c", origin)
    for elsewhere in (
        "http://127.0.0.1:5001/x",  # another port is another server
        "http://127.0.0.1:50000/x",  # a port that starts the same
        "blob:http://127.0.0.1:5001/7c1e2b3a",
        "blob:https://example.org/7c1e2b3a",
        "https://example.org/" + origin,
        "data:text/plain,x",
    ):
        assert not inside(elsewhere, origin), elsewhere


def test_a_request_elsewhere_is_caught_and_refused(signed_in: Page, live: Live) -> None:
    elsewhere = "http://192.0.2.1/x"  # TEST-NET-1: the fence refuses it before any network
    with pytest.raises(PlaywrightError):
        signed_in.goto(elsewhere)
    assert live.outside == [elsewhere]
    live.outside.clear()  # seen; the fixture's own check would fail the test otherwise


def test_the_preview_sentence_follows_the_voice_language(signed_in: Page, live: Live) -> None:
    """#211: choosing the German voice puts the German sample sentence in the preview box
    (marked lang="de"), unless the person wrote their own text."""
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    box = page.get_by_label("Sentence to listen to")
    expect(box).to_have_value(PREVIEW_TEXT)
    voice = page.get_by_label("Voice", exact=True)
    expect(voice.locator("option[value=dm_thorsten]")).to_have_text(
        "Thorsten, German, male (default for German)"
    )
    voice.select_option("dm_thorsten")
    expect(box).to_have_value(PREVIEW_TEXTS["de"])
    expect(box).to_have_attribute("lang", "de")
    check_axe(page, "document with the German voice chosen")
    voice.select_option("bm_george")
    expect(box).to_have_value(PREVIEW_TEXT)
    expect(box).to_have_attribute("lang", "en")
    box.fill("Mein eigener Satz.")
    voice.select_option("dm_thorsten")
    expect(box).to_have_value("Mein eigener Satz.")


def test_a_german_book_keeps_the_remembered_english_voice(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#211 review: making a German book with the German voice must not replace the English
    voice the person chose before; a voice of the same language still replaces it."""
    page = signed_in
    plan = small_plan()  # its second file stands for the German pack here
    files = (plan.files[0], replace(plan.files[1], pack="de"))
    monkeypatch.setattr(pages, "download_plan", lambda: replace(plan, files=files))
    live.install_voice()
    fake = live.voice
    english = fake.source()
    live.voice.source = lambda: replace(  # type: ignore[method-assign]
        english,
        voices=(*english.voices, "af_bella", "dm_thorsten"),
        languages={"af_heart": "en-US", "af_bella": "en-US", "bm_george": "en-GB"}
        | {"dm_thorsten": "de-DE"},
        defaults={"en": "af_heart", "de": "dm_thorsten"},
    )
    folder = str(live.config.output_folder)
    save_settings(
        JobSettings(language="de", voice="bm_george", output_folder=folder),  # type: ignore[arg-type]
        live.config.config_file,
    )
    open_paper(page, live)
    expect(page.get_by_label("Voice", exact=True)).to_have_value("dm_thorsten")
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    assert {voice for _, voice, _ in fake.spoken} == {"dm_thorsten"}
    settings = page.request.get(f"{live.url}/api/v1/settings").json()["settings"]
    assert settings["voice"] == "bm_george"

    save_settings(
        JobSettings(language="en", voice="bm_george", output_folder=folder),  # type: ignore[arg-type]
        live.config.config_file,
    )
    page.goto(page.url.split("/jobs/")[0] + "/")
    open_paper(page, live)
    voice = page.get_by_label("Voice", exact=True)
    expect(voice).to_have_value("bm_george")
    voice.select_option("af_bella")
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    settings = page.request.get(f"{live.url}/api/v1/settings").json()["settings"]
    assert settings["voice"] == "af_bella"


def test_the_language_of_the_text_is_chosen_for_this_document_only(
    signed_in: Page, live: Live
) -> None:
    """#212 (D-521): the check form's language choice runs the analysis again, the notices
    follow it, the audiobook is made in it, and the next document starts automatic."""
    page = signed_in
    live.install_voice()  # English voices only: the German note needs English to be made
    note = {"name": "notiz.md", "mimeType": "text/markdown", "buffer": GERMAN_NOTE.read_bytes()}
    page.set_input_files("#file", files=[note])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    language = page.get_by_label("Language of the text", exact=True)
    expect(language).to_have_value("")
    expect(page.locator("#text-language")).to_have_text(
        "Language of the text: German (as the file states)."
    )
    expect(page.locator("td", has_text="Eine Tabelle wird übersprungen.")).to_have_count(1)
    make = page.get_by_role("button", name="Make the audiobook")
    expect(make).to_have_attribute("aria-disabled", "true")  # no German voice here

    language.select_option("en")
    expect(page.locator("#changed")).to_be_visible()
    expect(page.locator("#make-note")).to_have_text("Set up the voice first.")
    update(page)
    expect(language).to_have_value("en")
    expect(page.locator("#text-language")).to_have_text(
        "Language of the text: English (your setting)."
    )
    expect(page.locator("td", has_text="A table is skipped.")).to_have_count(1)
    expect(page.locator("td", has_text="Eine Tabelle wird übersprungen.")).to_have_count(0)
    check_axe(page, "document page, language chosen")

    expect(make).not_to_have_attribute("aria-disabled", "true")
    make.click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    (audio,) = [job for job in live.state.board.all() if job.kind is JobKind.AUDIO]
    assert audio.settings is not None
    assert audio.settings["language"] == "en"
    saved = page.request.get(f"{live.url}/api/v1/settings").json()["settings"]
    assert saved["language"] == ""  # not remembered for the next document

    page.goto(f"{live.url}/")
    open_paper(page, live)
    expect(page.get_by_label("Language of the text", exact=True)).to_have_value("")


def test_replace_waits_until_the_page_script_runs(signed_in: Page, live: Live) -> None:
    """ "Replace these files" is drawn by the server, and app.js (deferred) gives it its
    click. Until then the button is disabled, so a click that comes too early waits instead
    of doing nothing; that click was the ZAP walk's flaky step (#177)."""
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    page.get_by_role("link", name="Prepare").click()
    at_rest(page)  # a click while the Prepare page's fonts still arrived did nothing (WebKit)
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("The audiobook files exist already.")

    release = reload_holding_back_app_js(page, live)
    replace_button = page.get_by_role("button", name="Replace these files")
    expect(replace_button).to_be_disabled()
    release()
    expect(replace_button).to_be_enabled()
    replace_button.click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")

    # the finished job's other buttons wait the same way; the ZAP walk clicks "Free the
    # speech cache" right after this page loads (#177 review R1-1)
    release = reload_holding_back_app_js(page, live)
    page.locator("#cache-free-open").click()  # the confirm opens without the script
    free = page.get_by_role("button", name="Delete the speech cache")
    expect(free).to_be_disabled()
    release()
    expect(free).to_be_enabled()
    free.click()
    expect(page.locator("#message")).to_have_text("The speech cache is empty.")


WIRED = ["#make", "#choose-all", "#choose-none", "#update", "#preview-listen"]


def test_the_document_pages_buttons_wait_for_the_script(signed_in: Page, live: Live) -> None:
    """The document page's buttons that only app.js (deferred) wires are drawn disabled, so
    a click before the script ran waits instead of doing nothing; the German main flow's
    Make button was clicked in that moment (#427, as #350 for Replace)."""
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    release = reload_holding_back_app_js(page, live)
    moves = page.locator("ol.choices button.move-up, ol.choices button.move-down")
    expect(page.locator("#make")).to_be_attached()
    for selector in WIRED:
        expect(page.locator(selector)).to_be_disabled()
    assert moves.count() == 6
    for n in range(moves.count()):
        expect(moves.nth(n)).to_be_disabled()
    release()
    for selector in WIRED:
        expect(page.locator(selector)).to_be_enabled()
    # every move button but the first's Move up and the last's Move down
    expect(page.locator("ol.choices button.move-up:enabled")).to_have_count(2)
    expect(page.locator("ol.choices button.move-down:enabled")).to_have_count(2)
    expect(page.locator("ol.choices li").first.locator(".move-up")).to_be_disabled()
    expect(page.locator("ol.choices li").last.locator(".move-down")).to_be_disabled()


def test_a_report_downloaded_while_the_page_loads_leaves_it_wired(
    signed_in: Page, live: Live
) -> None:
    """#435: a download link clicked before app.js ran must not stop the page's load, or
    the script never runs and its buttons stay disabled. The `download` attribute saves
    the file without navigating the page."""
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    release = reload_holding_back_app_js(page, live)
    report = page.locator('a[href*="?download=true"]').first
    expect(report).to_be_attached()
    with page.expect_download() as download:
        report.click()
    assert download.value.suggested_filename.endswith(".md")
    release()
    for selector in ("#update", "#make"):
        expect(page.locator(selector)).to_be_enabled()


def test_the_cards_buttons_wait_for_the_script(signed_in: Page, live: Live) -> None:
    """The job card's Pause, Cancel (in its confirm) and Resume are drawn by the server and
    wired only by app.js: disabled until then, like the page's other buttons (#427)."""
    page = signed_in
    live.install_voice()
    hold = Hold(after=1)
    live.voice.fail_on = hold
    open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    try:
        assert hold.reached.wait(30)
        release = reload_holding_back_app_js(page, live)
        pause, cancel = page.locator("#job-pause"), page.locator("#job-cancel")
        expect(pause).to_be_disabled()
        page.locator("#job-cancel-open").click()  # the confirm opens without the script
        expect(cancel).to_be_visible()
        expect(cancel).to_be_disabled()
        release()
        expect(pause).to_be_enabled()
        expect(cancel).to_be_enabled()
        with page.expect_response(re.compile(r"/api/v1/jobs/[^/]+/cancel$")):
            pause.click()
    finally:
        hold.gate.set()
    expect(page.locator("#result")).to_have_text(re.compile(r"^Paused"))
    release = reload_holding_back_app_js(page, live)
    resume = page.get_by_role("button", name="Resume")
    expect(resume).to_be_disabled()
    release()
    expect(resume).to_be_enabled()


@pytest.mark.parametrize("where", ["document", "library"])
def test_the_removal_button_waits_for_the_script(signed_in: Page, live: Live, where: str) -> None:
    """ "Remove … now" is wired only by app.js, on the document page and in a library row
    (#421): disabled until then (#427)."""
    page = signed_in
    document = open_paper(page, live)
    page.goto(live.url + "/" if where == "library" else f"{live.url}/documents/{document}")
    release = reload_holding_back_app_js(page, live)
    page.locator("details.remove summary").first.click()
    remove = page.locator("button.remove-now").first
    expect(remove).to_be_visible()
    expect(remove).to_be_disabled()
    release()
    expect(remove).to_be_enabled()


def test_analyse_waits_for_the_script(signed_in: Page, live: Live) -> None:
    """A document whose analysis failed shows "Analyse the document", wired by app.js too
    (#427)."""
    page = signed_in
    damaged = {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 nothing"}
    page.set_input_files("#file", files=[damaged])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#analysis-error")).to_be_visible()
    settled(page)
    release = reload_holding_back_app_js(page, live)
    analyse = page.get_by_role("button", name="Analyse the document")
    expect(analyse).to_be_disabled()
    release()
    expect(analyse).to_be_enabled()


# an image the page asks for once its script has run: until it comes the page has not loaded
HOLD_LOAD = """document.addEventListener("DOMContentLoaded", () => {
  const img = document.createElement("img");
  img.alt = "";
  img.src = "/static/held-back.png";
  document.body.append(img);
});"""


def test_a_move_made_while_the_page_loads_stays_where_it_was_made(
    signed_in: Page, live: Live
) -> None:
    """A page opened at a fragment (the step after an analysis, the result after a job) is
    focused there by app.js. Once that is done the fragment leaves the address: left in it,
    WebKit focuses and scrolls to it again when the page has loaded, under a key press or a
    click made in the meantime (D-698)."""
    page = signed_in
    document = open_paper(page, live)
    page.goto(live.url + "/")
    held: list[Route] = []
    page.route(f"{live.url}/static/held-back.png", lambda route: held.append(route))
    page.add_init_script(HOLD_LOAD)
    page.goto(f"{live.url}/documents/{document}#step-check", wait_until="domcontentloaded")
    expect(page.locator("#step-check")).to_be_focused()
    until(lambda: held)
    assert page.evaluate("() => document.readyState") != "complete"
    page.locator("#update").focus()  # the person moves on before the page has loaded
    held[0].fulfill(status=404)
    page.wait_for_load_state("load")
    page.wait_for_timeout(500)  # whatever the browser does once the page has loaded
    expect(page.locator("#update")).to_be_focused()
    assert page.evaluate("() => location.hash") == ""


def reload_holding_back_app_js(page: Page, live: Live) -> Callable[[], None]:
    """Reload the page with app.js held back; the result lets it through.

    Returns once the new document is parsed and at rest (#509). `wait_until=
    "domcontentloaded"` cannot be used: app.js is `defer`, and DOMContentLoaded waits for
    deferred scripts. The document's readyState turns "interactive" when parsing ends,
    before deferred scripts run. The flag set on the old page tells the reloaded one from
    it. Then `at_rest`: in WebKit a click on the parsed page while app.css and the fonts
    still arrived opened nothing (11 of 40 isolation runs)."""
    held: list[Route] = []
    page.evaluate("() => { window.beforeReload = true; }")
    page.route(f"{live.url}/static/app.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    page.wait_for_function("() => !window.beforeReload && document.readyState !== 'loading'")
    at_rest(page)

    def release() -> None:
        until(lambda: held)
        held[0].continue_()
        page.unroute(f"{live.url}/static/app.js")  # the next page loads its own

    return release
