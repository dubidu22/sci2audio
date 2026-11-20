"""The app without a window (#215, D-797): the rail's Quit item, the page that asks, and
the page that says sci2audio has stopped, by keyboard and with axe-core."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from conftest import FakeVoice, Live, SlowFetch, axe_problems, inside, serve, small_plan
from sci2audio.voices import download as download_module
from sci2audio.web import api, pages


@pytest.fixture
def app_page(
    page: Page,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offline: list[str],
) -> Iterator[tuple[Page, Live]]:
    plan = small_plan()
    for module in (download_module, api, pages):
        monkeypatch.setattr(module, "download_plan", lambda: plan)
    with serve(tmp_path, FakeVoice(), SlowFetch(), launched_as="browser") as live:

        def fence(route: Route) -> None:
            if inside(route.request.url, live.url):
                route.continue_()
            else:
                live.outside.append(route.request.url)
                route.abort()

        page.route("**/*", fence)
        page.set_default_timeout(15_000)
        page.goto(live.start_url)
        yield page, live
        assert live.outside == []


def test_quit_from_the_rail_by_keyboard(app_page: tuple[Page, Live]) -> None:
    page, live = app_page
    quit_item = page.locator("#quit")
    expect(quit_item).to_have_text("Quit sci2audio")
    quit_item.focus()
    page.keyboard.press("Enter")
    page.wait_for_url(f"{live.url}/quit")
    expect(page.locator("h1")).to_have_text("Quit sci2audio")
    expect(page.locator("#quit")).to_have_attribute("aria-current", "page")
    assert axe_problems(page, "the quit page") == []
    assert not live.state.quit.is_set()
    page.locator("#quit-now").focus()
    page.keyboard.press("Enter")
    done = page.locator("#quit-done")
    expect(done).to_have_text("sci2audio has stopped. You can close this tab.")
    expect(done).to_be_focused()
    expect(page.locator("#quit-ask")).to_be_hidden()
    assert live.state.quit.is_set()
    assert axe_problems(page, "the stopped page") == []


def jobs_list_requests(page: Page, origin: str) -> list[str]:
    asked: list[str] = []
    url = f"{origin}/api/v1/jobs"
    page.on("request", lambda r: asked.append(r.url) if r.url == url else None)
    return asked


def test_a_page_in_sight_keeps_the_app_without_a_window_awake(
    app_page: tuple[Page, Live],
) -> None:
    """Reading is no request: the page asks for the job list once a minute while it is in
    sight, so the idle stop never ends sci2audio under a reader (#631)."""
    page, live = app_page
    page.clock.install()
    page.goto(f"{live.url}/privacy")
    asked = jobs_list_requests(page, live.url)
    before = live.state.seen
    page.clock.run_for(59_000)
    assert asked == []
    with page.expect_response(f"{live.url}/api/v1/jobs") as answer:
        page.clock.run_for(2_000)
    assert answer.value.status == 200
    assert live.state.seen > before
    assert len(asked) == 1


def test_a_page_of_sci2audio_in_a_terminal_asks_nothing_to_stay_awake(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.clock.install()
    page.goto(f"{live.url}/privacy")
    asked = jobs_list_requests(page, live.url)
    page.clock.run_for(5 * 60_000)
    page.wait_for_timeout(300)
    assert asked == []
