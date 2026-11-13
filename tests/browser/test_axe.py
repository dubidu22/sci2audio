"""axe-core on the page states the flow tests don't reach (D-257), a proof that the check
finds a real problem, and the throttled progress announcements (D-253)."""

from __future__ import annotations

import asyncio
import re
import threading
import time
from typing import Any

import pytest
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import Page, expect
from test_flow import open_paper

from conftest import Live, axe_problems, check_axe
from sci2audio.voices import EngineError
from sci2audio.web.jobs import JobKind


def test_the_check_finds_a_real_problem(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.locator("label[for=file]").evaluate("label => label.remove()")
    found = axe_problems(page, "start page without its label")
    assert any("label" in line for line in found), found


def test_pages_for_things_that_dont_exist(signed_in: Page, live: Live) -> None:
    page = signed_in
    for path in ("/documents/0123456789abcdef", "/jobs/nothing"):
        response = page.goto(live.url + path)
        assert response is not None
        assert response.status == 404
        expect(page.get_by_role("heading", level=1)).to_have_text("Not found")
        check_axe(page, f"not found: {path}")


def test_the_start_page_with_documents_and_the_voice(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    page.goto(live.url + "/")
    expect(page.get_by_text("The voice is installed.")).to_be_visible()
    expect(page.get_by_role("link", name="paper.pdf")).to_be_visible()
    check_axe(page, "start page with a document")
    page.goto(live.url + "/voice")
    expect(
        page.get_by_text("The voice is installed. Nothing needs to be downloaded.")
    ).to_be_visible()
    expect(page.get_by_role("button", name="Download the voice")).to_have_count(0)
    check_axe(page, "voice page, installed")


def test_a_running_download_and_its_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.fetch.delay = 0.4
    page.goto(live.url + "/voice")
    page.get_by_role("checkbox", name=re.compile("I agree")).check()
    page.get_by_role("button", name="Download the voice").click()
    page.wait_for_url(re.compile(r"/jobs/voices-\d+"))
    expect(page.locator("#job-progress")).to_contain_text(re.compile(r"downloading, \d+\s%"))
    expect(page.get_by_role("button", name="Cancel")).to_be_visible()
    check_axe(page, "voice download running")
    page.get_by_role("button", name="Cancel").click()
    expect(page.locator("#result")).to_have_text("The job was cancelled.")
    check_axe(page, "voice download cancelled")


def test_progress_is_announced_at_most_every_30_seconds(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = open_paper(page, live)
    gate = threading.Event()
    sent = threading.Event()

    def work(job: object) -> list[object]:
        for n in range(1, 21):
            job.report({"phase": "speaking", "chunks_done": n, "chunks_total": 100})  # type: ignore[attr-defined]
            time.sleep(0.15)  # the event stream looks every 0.1 s
        sent.set()
        gate.wait(30)
        return []

    page.clock.install()  # the page's clock stands still until the test moves it
    job = live.state.board.start(JobKind.AUDIO, document, {}, work, cancellable=False)
    try:
        page.goto(f"{live.url}/jobs/{job.id}")
        page.locator("#job-status").evaluate(
            """region => {
                window.said = [];
                new MutationObserver(() => window.said.push(region.textContent))
                    .observe(region, {childList: true, characterData: true, subtree: true});
            }"""
        )
        assert sent.wait(20)
        expect(page.locator("#job-progress")).to_contain_text("20 of 100 sentences")
        said = page.evaluate("() => window.said")
        assert len(said) <= 1, said  # the phase was announced, the sentences were not
        page.clock.fast_forward(31_000)
        job.report({"phase": "speaking", "chunks_done": 21, "chunks_total": 100})
        expect(page.locator("#job-progress")).to_contain_text("21 of 100 sentences")
        said = page.evaluate("() => window.said")
        assert said[-1].startswith("speaking, 21 of 100 sentences"), said
        assert len(said) <= 2, said
        job.report({"phase": "encoding"})  # a new phase is announced at once
        expect(page.locator("#job-status")).to_have_text("making the audio files")
    finally:
        gate.set()
        job.join(10)


def test_a_job_that_failed(signed_in: Page, live: Live) -> None:
    page = signed_in
    live.install_voice()
    open_paper(page, live)
    live.voice.fail_to_make = EngineError("the model file is damaged")
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_contain_text("The job failed")
    expect(page.get_by_role("button", name="Start again")).to_be_visible()
    check_axe(page, "audiobook failed")


def test_the_check_waits_for_the_stylesheet(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """axe on a page whose app.css hasn't arrived finds problems that aren't there (small
    inline links next to each other: target-size), so the check waits for the page's load
    event. The stylesheet comes late here, and the check runs right after the click."""
    serve = StaticFiles.get_response

    async def late(self: StaticFiles, path: str, scope: Any) -> Any:
        if path == "app.css":
            await asyncio.sleep(1.5)
        return await serve(self, path, scope)

    monkeypatch.setattr(StaticFiles, "get_response", late)
    page = signed_in
    page.get_by_role("link", name="Set up the voice").click()
    check_axe(page, "voice setup page right after the click")
