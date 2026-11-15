"""The job page shows a PDF's pages while it is read (#343), in English and German."""

from __future__ import annotations

import threading

from playwright.sync_api import Page, expect
from test_flow import open_paper

from conftest import Live, check_axe
from sci2audio.web.jobs import JobKind


def test_the_job_page_shows_the_page_being_read(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = open_paper(page, live)
    gate = threading.Event()
    reported = threading.Event()

    def work(job: object) -> list[object]:
        job.report({"phase": "reading"})  # type: ignore[attr-defined]
        job.report({"phase": "reading", "page": 120, "pages": 400})  # type: ignore[attr-defined]
        reported.set()
        gate.wait(30)
        return []

    job = live.state.board.start(JobKind.SCRIPT, document, {}, work, cancellable=False)
    try:
        page.goto(f"{live.url}/jobs/{job.id}")
        assert reported.wait(20)
        expect(page.locator("#job-progress")).to_have_text("reading the file, page 120 of 400")
        expect(page.locator("#job-bar")).to_have_attribute("value", "30")
        check_axe(page, "job page reading a PDF")
    finally:
        gate.set()
        job.join(10)
