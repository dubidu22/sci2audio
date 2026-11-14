"""The main flow in a real browser (#77, #8): open a file, read the pre-analysis, switch a
category and chapters, set up the voice with consent, listen to a preview, choose the
speed, make the audiobook, replace it, free the speech cache; with axe-core on every page
on the way (D-257)."""

from __future__ import annotations

import re
import threading
import time
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect
from web_helpers import paper_bytes

from conftest import Live, check_axe, inside, settled
from sci2audio.voices import PREVIEW_TEXT
from sci2audio.web.jobs import JobKind, JobRecord

PDF = {"name": "paper.pdf", "mimeType": "application/pdf", "buffer": paper_bytes()}


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


def test_the_main_flow(signed_in: Page, live: Live) -> None:
    page = signed_in
    expect(page.get_by_role("heading", level=1)).to_have_text("Open a document")
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
    page.get_by_role("checkbox", name=re.compile("^Citations")).uncheck()
    expect(page.locator("#changed")).to_be_visible()
    update(page)
    expect(page.locator("#counts-citations")).to_contain_text("0 heard")
    expect(page.locator("#counts-citations")).to_contain_text("1 switched off")
    expect(page.get_by_role("checkbox", name=re.compile("^Citations"))).not_to_be_checked()

    # back on, and its chapter not chosen: listed as not spoken (UC-03, D-100)
    page.get_by_role("checkbox", name=re.compile("^Citations")).check()
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
    page.get_by_role("button", name="Listen").click()
    player = page.locator("#preview-audio")
    expect(player).to_be_visible()
    expect(player).to_be_focused()
    until(lambda: player.evaluate("audio => audio.readyState") >= 1)  # the WAV loaded
    assert live.voice.spoken[-1] == (PREVIEW_TEXT, "bm_george", 1.25)
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
    expect(page.get_by_text(str(live.config.output_folder))).to_be_visible()
    check_axe(page, "audiobook done")
    settings = page.request.get(f"{live.url}/api/v1/settings").json()["settings"]
    assert settings["voice"] == "bm_george"  # remembered for the next document (D-246)
    assert settings["speed"] == 1.25
    assert settings["output_folder"] == str(live.config.output_folder)
    spoken = {text for text, _, _ in live.voice.spoken}
    assert "We measured it twice." in spoken
    assert not any("Smith" in text for text in spoken)  # chapter 1 was not chosen

    # again: the files exist; replacing them is its own button (D-254)
    page.get_by_role("link", name="Back to the document").click()
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text(
        "The job failed: The audiobook files exist already."
    )
    # the app's own words follow as details, in English (D-291)
    expect(page.locator("#job p span[lang=en]")).to_contain_text("these files exist already")
    check_axe(page, "audiobook files exist")
    page.get_by_role("button", name="Replace these files").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")

    # free the speech cache (D-158)
    expect(page.locator("#cache-text")).to_contain_text("sci2audio keeps the spoken sentences")
    page.get_by_role("button", name="Free the speech cache").click()
    expect(page.locator("#message")).to_have_text("The speech cache is empty.")
    expect(page.locator("#message")).to_be_focused()
    folder = live.config.work_root / document / "chunks"
    assert not folder.exists() or not any(folder.rglob("*.wav"))


def slow(seconds: float) -> Any:
    def wait(text: str) -> bool:
        time.sleep(seconds)
        return False  # never fails, just takes its time

    return wait


def test_progress_while_speaking_and_cancel(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.install_voice()
    live.voice.fail_on = slow(1.0)
    open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#job-progress")).to_contain_text("speaking")
    expect(page.locator("#job-progress")).to_contain_text(re.compile(r"\d of \d sentences"))
    expect(page.locator("#job-progress")).to_contain_text("measuring the speed")
    expect(page.locator("#job-bar")).to_have_attribute("aria-valuetext", re.compile("speaking"))
    expect(page.locator(".running")).to_contain_text("A job is running: Audiobook of paper.pdf.")
    check_axe(page, "audiobook running")
    page.get_by_role("button", name="Cancel").click()
    expect(page.locator("#result")).to_have_text("The job was cancelled.")
    expect(page.get_by_role("button", name="Start again")).to_be_visible()
    check_axe(page, "audiobook cancelled")


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
        expect(page.locator(".running")).to_contain_text("A job is running: Voice download.")
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
    page.get_by_label("Or paste text").fill(pasted)
    page.get_by_label("Name for the pasted text").fill("My notes")
    check_axe(page, "start page with pasted text")
    page.get_by_role("button", name="Open the text").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    expect(page.get_by_role("heading", level=1)).to_contain_text("My notes.txt")
    check_axe(page, "document from pasted text")


def test_a_damaged_file_shows_the_apps_message(signed_in: Page, live: Live) -> None:
    page = signed_in
    damaged = {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 nothing"}
    page.set_input_files("#file", files=[damaged])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#analysis-error")).to_contain_text("The analysis failed:")
    expect(page.get_by_role("button", name="Analyse the document")).to_be_visible()
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
        expect(page.get_by_role("progressbar", name="Progress")).to_be_visible()
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
    page.get_by_role("checkbox", name=re.compile("^Citations")).uncheck()
    expect(make).to_have_attribute("aria-disabled", "true")
    expect(page.locator("#make-note")).to_have_text(
        "Update the analysis first to see what your changes do."
    )
    make.click(force=True)  # aria-disabled: Playwright would wait for it to be enabled
    expect(page.locator("#message")).to_have_text(
        "Update the analysis first to see what your changes do."
    )
    expect(page.locator("#message")).to_be_focused()
    page.get_by_role("checkbox", name=re.compile("^Citations")).check()

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
