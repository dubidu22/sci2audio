"""A click on "Make the audiobook" on a page drawn while the analysis ends (#299): the
analysis has written its report, so the page shows it and the Make button, but its job
has not ended, so the page still follows it and reloads itself at the end. The button
waits for the reloaded page, so the start is never cut off by that reload: it ends on
the job page, and the choices are remembered."""

from __future__ import annotations

import re
import threading
from typing import Any

import pytest
from playwright.sync_api import Page, expect
from test_flow import PDF

from conftest import Live
from sci2audio.app import job as job_module


def held_after_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[threading.Event, threading.Event]:
    """The first analysis writes its report and script, then waits for `gate` (the probe of
    review R3-1 of #289, with an event in place of a pause)."""
    real = job_module._write
    written = threading.Event()
    gate = threading.Event()

    def write(*args: Any, **kwargs: Any) -> Any:
        out = real(*args, **kwargs)
        if not written.is_set():
            written.set()
            gate.wait(30)
        return out

    monkeypatch.setattr(job_module, "_write", write)
    return written, gate


def test_make_waits_for_the_page_to_stop_following_the_analysis(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = signed_in
    live.install_voice()
    written, gate = held_after_the_report(monkeypatch)
    try:
        page.set_input_files("#file", files=[PDF])
        page.get_by_role("button", name="Open and analyse").click()
        page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
        assert written.wait(30)
        page.reload()  # drawn in the window: the report is there, the job still runs
        expect(page.locator("#summary")).to_be_visible()
        expect(page.locator("#document[data-events]")).to_have_count(1)
        expect(page.locator("#choose-all")).to_be_enabled()  # the page's script has run
        make = page.get_by_role("button", name="Make the audiobook")
        expect(make).to_be_disabled()
        expect(page.locator("#message")).to_have_text("Analysing the document…")
    finally:
        gate.set()

    def saved(answer: Any) -> bool:
        return answer.request.method == "PUT" and answer.url.endswith("/api/v1/settings")

    with page.expect_response(saved) as put:
        make.click()  # waits for the page the end of the analysis reloads
    assert put.value.ok
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    remembered = page.request.get(f"{live.url}/api/v1/settings").json()["settings"]
    assert remembered["output_folder"]
