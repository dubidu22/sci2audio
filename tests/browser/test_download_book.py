"""Downloading the whole audiobook as one file (#725, LW-03), in the browser: the box on the
library's row and on the Listen page, the job page that builds the file with its progress
and Cancel, the chapters not made yet named in the box with the ready ones offered as a
partial file, the keyboard and axe-core."""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable, Iterator
from typing import Any

from playwright.sync_api import Page, expect
from test_flow import until
from test_listen_growing import FIRST_READY, making
from test_player import make_audiobook

from conftest import Live, at_rest, check_axe
from sci2audio.output import Ffmpeg, find_ffmpeg

# The page may add a #making or #result fragment to its address (app.js reloadAt), so
# neither pattern may take one in or stop matching because of it (#1088, #1090).
JOB_PAGE = re.compile(r"/jobs/[0-9a-f]{16}-book-\d+(?:#[\w-]*)?$")
JOB_ID = re.compile(r"/jobs/([0-9a-f]{16}-[a-z]+-\d+)(?:#[\w-]*)?$")


def save_link_answers(page: Page, live: Live) -> str:
    """The job page's Save link serves the file as an attachment; returns the file's name."""
    link = page.locator("#book-save")
    expect(link).to_be_visible()
    href = link.get_attribute("href")
    assert href is not None
    answer = page.request.get(live.url + href)
    assert answer.status == 200
    assert answer.headers["content-disposition"].startswith("attachment")
    name = re.sub(r"^Save (.*) \(.*\)$", r"\1", link.inner_text().strip())
    assert (
        name in answer.headers["content-disposition"]
        or "filename*" in answer.headers["content-disposition"]
    )
    return name


def test_download_the_audiobook_from_the_library_row(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.goto(live.url + "/")
    at_rest(page)
    row = page.locator("tr", has=page.get_by_role("link", name="paper", exact=True))
    box = row.locator("details.book")
    box.locator("summary").click()
    expect(box.get_by_role("radio", name="M4B")).to_be_checked()
    expect(box.get_by_role("group", name="One file for the whole book")).to_be_visible()
    check_axe(page, "library with the download box open")
    box.get_by_role("button", name="Download", exact=True).click()
    page.wait_for_url(JOB_PAGE)
    expect(page.locator("#result")).to_have_text("Your audiobook file is ready", timeout=60_000)
    expect(page.locator("#result")).to_be_focused()
    name = save_link_answers(page, live)
    assert name.endswith(".m4b")
    expect(page.get_by_text(str(live.config.output_folder), exact=False)).to_be_visible()
    check_axe(page, "audiobook file ready")

    # asked again, the file built before is saved at once, without a job
    page.goto(live.url + "/")
    at_rest(page)
    box = page.locator("tr", has=page.get_by_role("link", name="paper", exact=True)).locator(
        "details.book"
    )
    box.locator("summary").click()
    button = box.get_by_role("button", name="Download", exact=True)
    button.focus()
    with page.expect_download() as saved:
        page.keyboard.press("Enter")
    assert saved.value.suggested_filename == name
    expect(page.locator("#message")).to_have_text(f"Saving {name}.")
    assert JOB_PAGE.search(page.url) is None


def test_download_from_the_listen_page_with_missing_chapters_names_them(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    with making(page, live, FIRST_READY) as hold:
        found = JOB_ID.search(page.url)
        assert found, page.url
        job = found[1]
        expect(page.locator("#start-listening")).to_be_visible()
        at_rest(page)
        page.locator("#job-pause").click()  # the chapters made stay; the others are not
        hold.gate.set()

        def ended() -> bool:
            state = page.request.get(f"{live.url}/api/v1/jobs/{job}").json()["state"]
            return bool(state != "running")

        until(ended, timeout=60)
    document = job.split("-")[0]
    # the card redraws its page when the job ends: go on from the redrawn one
    expect(page.locator("#making")).not_to_have_attribute("data-state", "running", timeout=30_000)
    at_rest(page)
    page.goto(f"{live.url}/documents/{document}/listen")
    at_rest(page)
    box = page.locator(".listen-book details.book")
    box.locator("summary").click()
    box.get_by_role("radio", name="MP3").check()
    box.get_by_role("button", name="Download", exact=True).click()
    missing = box.locator(".book-missing")
    expect(missing).to_be_visible()
    expect(missing).to_be_focused()
    expect(missing.locator("li")).to_have_text(["Methods", "Results"])
    check_axe(page, "listen page with missing chapters named")
    box.get_by_role("button", name="Download the ready chapters").click()
    page.wait_for_url(JOB_PAGE)
    expect(page.locator("#result")).to_have_text("Your audiobook file is ready", timeout=60_000)
    expect(page.locator("#book-partial-note")).to_be_visible()
    expect(page.locator("ul.book-left li")).to_have_text(["Methods", "Results"])
    name = save_link_answers(page, live)
    assert name.endswith("(partial).mp3")
    page.get_by_role("link", name="Back to listening").click()
    page.wait_for_url(f"{live.url}/documents/{document}/listen")


class _Held(Ffmpeg):
    """The bundled ffmpeg, fed slowly: it waits after the first piece until `gate` opens."""

    reached = threading.Event()
    gate = threading.Event()

    def run(self, args: Any, feed: Iterable[bytes] = ()) -> str:
        def fed() -> Iterator[bytes]:
            for n, piece in enumerate(feed):
                if n == 1:
                    _Held.reached.set()
                    _Held.gate.wait(120)
                yield piece

        return Ffmpeg(self.exe).run(args, fed())


def test_the_build_shows_progress_and_cancels(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    _Held.reached.clear()
    _Held.gate.clear()
    live.state.book_ffmpeg = _Held(find_ffmpeg())
    try:
        box = page.locator(".listen-book details.book")
        box.locator("summary").click()
        box.get_by_role("button", name="Download", exact=True).click()
        page.wait_for_url(JOB_PAGE)
        assert _Held.reached.wait(60)
        expect(page.locator("#job-progress")).to_contain_text("making the audiobook file")
        bar = page.get_by_role("progressbar", name="Progress")
        expect(bar).to_be_visible()
        check_axe(page, "audiobook file being made")
        cancel = page.get_by_role("button", name="Cancel")
        expect(cancel).to_be_enabled()
        cancel.click()
    finally:
        _Held.gate.set()
    expect(page.locator("#result")).to_have_text("The job was cancelled.", timeout=60_000)
    folder = live.state.listening(document)
    assert folder is not None
    written = [p for f in folder.folders if f is not None and f.is_dir() for p in f.iterdir()]
    assert not [p for p in written if p.suffix == ".m4b" or ".partial" in p.name]
