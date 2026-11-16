"""Prepare with the audiobook job inline (#391; DESIGN.md "Prepare", screens prepare, making,
failed): axe at the design's widths and at 320 px, light, dark (by the system and chosen in
Settings) and German; no highlighter colour on the tabs, the job's bar or its segments; and
nothing moves under reduced motion."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, expect
from test_flow import open_paper
from test_shell import HIGHLIGHTED, axe_with_dark_chosen, scrolls_sideways

from conftest import Hold, Live, axe_problems
from sci2audio.web.i18n import COOKIE

SIZES = {1440: 900, 1280: 800, 320: 640}
# the switches are left out: DESIGN.md gives a switched-on switch quote blue in dark
PARTS = ".tabs a, .tabs .tab-off, #making button, #making .btn, #job-bar, .seg"


@contextmanager
def speaking(page: Page, live: Live) -> Iterator[str]:
    """A job held after its first sentence, shown on Prepare; yields the job page's path."""
    live.install_voice()
    hold = Hold(after=1)
    live.voice.fail_on = hold
    open_paper(page, live)
    try:
        page.get_by_role("button", name="Make the audiobook").click()
        page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
        assert hold.reached.wait(30)
        expect(page.locator("#job-segments .seg.now")).to_have_count(1)
        yield page.url.removeprefix(live.url).split("#")[0]
    finally:
        hold.gate.set()


def test_axe_on_prepare_with_the_job_at_every_size_scheme_and_language(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    problems: list[str] = []
    with speaking(page, live) as path:
        for language in ("en", "de"):
            page.context.add_cookies([{"name": COOKIE, "value": language, "url": live.url}])
            for width, height in SIZES.items():
                page.set_viewport_size({"width": width, "height": height})
                page.goto(live.url + path)
                expect(page.locator("#making[data-state=running]")).to_have_count(1)
                expect(page.locator("html")).to_have_attribute("lang", language)
                where = f"{language} at {width}"
                assert not scrolls_sideways(page), where
                problems += axe_problems(page, where)
                page.emulate_media(color_scheme="dark")
                problems += axe_problems(page, f"{where} (dark by the system)")
                page.emulate_media(color_scheme="light")
                problems += axe_with_dark_chosen(page, where)
                page.locator("#job-cancel-open").click()  # the confirm, open
                problems += axe_problems(page, f"{where} with the cancel confirm open")
    assert problems == []


def test_no_highlighter_on_the_tabs_the_bar_or_the_segments(signed_in: Page, live: Live) -> None:
    page = signed_in
    with speaking(page, live) as path:
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            page.goto(live.url + path)
            expect(page.locator("#job-segments .seg")).to_have_count(2)
            assert page.evaluate(HIGHLIGHTED, PARTS) == [], scheme
        page.emulate_media(color_scheme="light")
        # the check sees one: a segment painted reading yellow
        page.locator(".seg").first.evaluate(
            "s => s.style.setProperty('background-color', 'var(--hl-read)')"
        )
        assert page.evaluate(HIGHLIGHTED, PARTS) != []


def test_the_bar_and_the_segments_do_not_move_under_reduced_motion(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    with speaking(page, live) as path:
        page.emulate_media(reduced_motion="reduce")
        page.goto(live.url + path)
        expect(page.locator("#job-segments .seg")).to_have_count(2)
        durations = page.evaluate(
            """() => [...document.querySelectorAll('*')].map((el) => getComputedStyle(el))
                .flatMap((s) => [s.transitionDuration, s.animationDuration])"""
        )
        assert set(",".join(durations).replace(" ", "").split(",")) <= {"0s"}
        assert page.evaluate("() => document.getAnimations().length") == 0
        page.emulate_media(reduced_motion="no-preference")
