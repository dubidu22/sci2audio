import re
import time
from pathlib import Path

import pytest
import test_player as tp
from pdf_maker import Text, make_pdf
from playwright.sync_api import Page, Route

from conftest import Live, settled
from sci2audio.app import job as job_module

PDF = make_pdf([Text("Introduction", 72, 80, size=14), Text("Some text here.", 72, 100, size=11)])


def slow(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    """The analysis takes 2 s; the settings PUT after the audio start takes 3 s."""
    real = job_module._write
    calls = []

    def write(*args, **kwargs):
        calls.append(1)
        out = real(*args, **kwargs)
        print("WROTE", len(calls), time.monotonic())
        if len(calls) == 1:
            time.sleep(1.0)  # the report is on disk, the job not yet ended
        return out

    monkeypatch.setattr(job_module, "_write", write)

    def settings(route: Route) -> None:
        if route.request.method == "PUT":
            time.sleep(3.0)
        route.continue_()

    page.route(re.compile(r".*/api/v1/settings$"), settings)


def test_probe_old_helper(signed_in: Page, live: Live, tmp_path: Path, monkeypatch) -> None:
    slow(signed_in, monkeypatch)
    page = signed_in
    page.on("request", lambda r: print("REQ", time.monotonic(), r.method, r.url[-60:]))
    page.on("framenavigated", lambda f: print("NAV", time.monotonic(), f.url[-50:]))
    tp.listen_to(signed_in, live, tmp_path / "a.pdf", PDF)


def test_probe_waiting_helper(signed_in: Page, live: Live, tmp_path: Path, monkeypatch) -> None:
    page = signed_in
    slow(page, monkeypatch)
    live.install_voice()
    (tmp_path / "a.pdf").write_bytes(PDF)
    page.set_input_files("#file", files=[tmp_path / "a.pdf"])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    settled(page)
    page.get_by_role("button", name="Make the audiobook").click()
    tp.expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
