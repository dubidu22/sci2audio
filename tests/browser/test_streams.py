"""The running job on the rail's shelf without holding the browser's connections (#387, PR
#409 review B2): a page opens one event stream per job, however many of its parts follow
it, and a page that follows no job asks for it now and then instead. A browser keeps at
most six HTTP/1.1 connections to one server, and each open stream holds one for as long as
its job runs."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from test_flow import gated

from conftest import Live
from sci2audio.web.jobs import JobKind

# Counts the event streams a page opens, before any of the page's own script runs.
COUNT = """(() => {
  const Real = window.EventSource;
  window.__streams = [];
  window.EventSource = function (url, options) {
    window.__streams.push(String(url));
    return new Real(url, options);
  };
  window.EventSource.prototype = Real.prototype;
  window.EventSource.CLOSED = Real.CLOSED;
})();"""

# Lets a test say whether the tab is hidden, as switching tabs does.
HIDDEN = """(() => {
  window.__hidden = false;
  Object.defineProperty(document, "hidden", { get: () => window.__hidden });
})();"""


NBSP = "\N{NO-BREAK SPACE}"  # between a number and its % sign, as the strings write it


def seen(page: Page, hidden: bool) -> None:
    """The tab goes to the background or comes back, as switching tabs does."""
    page.evaluate(
        "(hidden) => { window.__hidden = hidden;"
        " document.dispatchEvent(new Event('visibilitychange')); }",
        hidden,
    )


def streams(page: Page) -> list[str]:
    page.wait_for_load_state("load")
    return page.evaluate("() => window.__streams")


def test_a_page_holds_one_stream_per_job_and_the_shelf_none(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.context.add_init_script(COUNT)
    job, gate = gated(live.state, JobKind.VOICES, None)
    events = f"/api/v1/jobs/{job.id}/events"
    try:
        page.goto(f"{live.url}/jobs/{job.id}")
        expect(page.locator("#job-state")).to_have_text("running")
        expect(page.locator("#shelf-job")).to_have_attribute("aria-current", "page")
        assert streams(page) == [events]  # the job page and its shelf share one
        for path in ("/", "/settings", "/voice", "/privacy"):
            page.goto(live.url + path)
            expect(page.locator("#shelf-job")).to_contain_text("Voice download")
            assert streams(page) == [], path  # the shelf alone asks, it holds no stream
    finally:
        gate.set()
        job.join(10)


def test_six_tabs_during_a_job_leave_the_interface_answering(signed_in: Page, live: Live) -> None:
    """On 8982fcc each job tab held two streams, so three of them took all six connections
    and the next request waited for the job to end."""
    page = signed_in
    job, gate = gated(live.state, JobKind.VOICES, None)
    others: list[Page] = []
    try:
        # three tabs follow the job and three show it on the shelf: half the connections
        for path in [f"/jobs/{job.id}"] * 3 + ["/"] * 3:
            other = page.context.new_page()
            other.goto(live.url + path)
            expect(other.locator("#shelf-job")).to_be_visible()
            others.append(other)
        page.goto(live.url + "/settings")
        answer = page.evaluate(
            """() => fetch("/api/v1/settings", { signal: AbortSignal.timeout(2000) })
                .then((r) => r.status).catch((e) => String(e))"""
        )
        assert answer == 200
    finally:
        for other in others:
            other.close()
        gate.set()
        job.join(10)


def test_the_shelf_follows_the_job_by_asking_and_shows_its_end(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.context.add_init_script(HIDDEN)
    job, gate = gated(live.state, JobKind.VOICES, None)
    asked: list[str] = []
    page.on(
        "request",
        lambda request: (
            asked.append(request.url) if request.url.endswith(f"/api/v1/jobs/{job.id}") else None
        ),
    )
    try:
        page.goto(live.url + "/")
        state = page.locator("#shelf-job-state")
        bar = page.locator("#shelf-job-bar")
        expect(page.locator("#shelf-job")).to_contain_text("Voice download")
        job.report({"phase": "downloading", "bytes_done": 1, "bytes_total": 4})
        expect(state).to_have_text(f"downloading, 25{NBSP}% done")
        expect(bar).to_have_js_property("value", 25)

        # a hidden tab asks nothing; shown again, it asks at once
        seen(page, hidden=True)
        page.wait_for_timeout(300)  # a question already on its way may still arrive
        before = len(asked)
        job.report({"phase": "downloading", "bytes_done": 3, "bytes_total": 4})
        page.wait_for_timeout(4500)  # two periods of the shelf's questions
        assert len(asked) == before
        expect(state).to_have_text(f"downloading, 25{NBSP}% done")
        seen(page, hidden=False)
        expect(state).to_have_text(f"downloading, 75{NBSP}% done", timeout=1500)
        expect(bar).to_have_js_property("value", 75)

        gate.set()
        job.join(10)
        expect(state).to_have_text("done")
        expect(bar).to_have_js_property("value", 100)
        page.wait_for_timeout(300)
        after = len(asked)
        page.wait_for_timeout(4500)
        assert len(asked) == after  # an ended job is asked about no more
    finally:
        gate.set()
        job.join(10)


def test_the_shelf_on_the_jobs_own_page_moves_with_its_stream(signed_in: Page, live: Live) -> None:
    page = signed_in
    job, gate = gated(live.state, JobKind.VOICES, None)
    try:
        page.goto(f"{live.url}/jobs/{job.id}")
        expect(page.locator("#job-state")).to_have_text("running")
        job.report({"phase": "downloading", "bytes_done": 1, "bytes_total": 2})
        expect(page.locator("#shelf-job-state")).to_have_text(f"downloading, 50{NBSP}% done")
        expect(page.locator("#shelf-job-bar")).to_have_js_property("value", 50)
        expect(page.locator("#job-progress")).to_contain_text("downloading")  # the same stream
    finally:
        gate.set()
        job.join(10)
