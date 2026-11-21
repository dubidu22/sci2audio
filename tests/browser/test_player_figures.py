"""The figure, table or formula itself in the player (#293, D-771): its crop shows inside its
notice box with its alt text; the text view stays the one view the keys use (no new Tab
stop, a click plays from the notice); an image that can't be shown leaves only the notice;
axe passes in light, dark and German."""

from __future__ import annotations

from pathlib import Path

from pdf_maker import Rect, Text, make_pdf
from playwright.sync_api import Page, Route, expect
from test_player import listen_to

from conftest import Live, at_rest, check_axe, tab_key

FIGURE = "#text .notice img.figure"


def figure_pdf() -> bytes:
    return make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Things happen and the chart below shows them.", 72, 100, size=11),
            Rect(100, 150, 400, 350),
            Text("Figure 1: A chart of things.", 100, 370, size=9),
            Text("More text follows the figure here.", 72, 420, size=11),
        ]
    )


def late_figure_pdf() -> bytes:
    """Six pages of text, then the figure on page 7: far below the first screen."""
    words = "Sentence {n} of page {p} says a little more about things."
    text = [
        [Text(words.format(n=n, p=p), 72, 80 + 30 * n, size=11) for n in range(1, 20)]
        for p in range(1, 7)
    ]
    figure = [
        Text("The last page shows a chart.", 72, 80, size=11),
        Rect(100, 150, 400, 350),
        Text("Figure 1: A late chart.", 100, 370, size=9),
    ]
    return make_pdf(*text, figure)


def open_figure(page: Page, live: Live, tmp_path: Path) -> None:
    listen_to(page, live, tmp_path / "chart.pdf", figure_pdf())
    at_rest(page)


def tab_stops(page: Page, count: int = 60) -> list[str]:
    """What focus visits on `count` presses of Tab: tag names."""
    found = []
    for _ in range(count):
        page.keyboard.press(tab_key(page))
        found.append(page.evaluate("() => document.activeElement?.tagName ?? ''"))
    return found


def test_the_figure_shows_in_its_notice_box(signed_in: Page, live: Live, tmp_path: Path) -> None:
    page = signed_in
    open_figure(page, live, tmp_path)
    figure = page.locator(FIGURE)
    expect(figure).to_have_count(1)
    expect(figure).to_have_attribute("alt", "Figure 1: A chart of things.")
    figure.scroll_into_view_if_needed()
    page.wait_for_function(
        "(s) => { const i = document.querySelector(s); return i.complete && i.naturalWidth > 0; }",
        arg=FIGURE,
    )
    natural = page.evaluate(
        "(s) => { const i = document.querySelector(s); return [i.naturalWidth, i.naturalHeight]; }",
        FIGURE,
    )
    assert natural == [924, 624]
    # inside the notice box, after its words, before the text found in the file
    order = page.evaluate(
        """() => [...document.querySelector('#text .notice').children]
            .map((e) => e.tagName.toLowerCase())"""
    )
    assert order.index("p") < order.index("img")
    shown = figure.bounding_box()
    box = page.locator("#text .notice").bounding_box()
    assert shown is not None
    assert box is not None
    assert shown["width"] <= box["width"]  # never wider than its notice box
    assert not live.outside


def test_the_figure_adds_no_tab_stop_and_a_click_plays_from_its_notice(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    open_figure(page, live, tmp_path)
    figure = page.locator(FIGURE)
    assert figure.get_attribute("tabindex") is None
    assert page.evaluate("(s) => document.querySelector(s).tabIndex", FIGURE) == -1
    assert "IMG" not in tab_stops(page)  # the keys never stop on it
    figure.scroll_into_view_if_needed()
    figure.click()
    notice = page.locator("#text .notice")
    expect(notice).to_have_attribute("aria-current", "true")  # read from the notice on
    expect(page.locator("#text .s.now")).to_have_attribute("id", str(notice.get_attribute("id")))
    assert not page.evaluate("() => document.getElementById('audio').paused")


def test_an_image_that_cannot_be_shown_leaves_only_the_notice(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    open_figure(page, live, tmp_path)

    def gone(route: Route) -> None:
        route.fulfill(status=404, body="")

    page.route("**/figures/**", gone)
    page.reload()
    at_rest(page)
    page.locator("#text .notice").scroll_into_view_if_needed()
    expect(page.locator(FIGURE)).to_be_hidden()
    expect(page.locator("#text .notice > p")).to_contain_text("Figure 1")


def test_the_page_with_a_figure_passes_axe_in_light_dark_and_german(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    open_figure(page, live, tmp_path)
    page.locator(FIGURE).scroll_into_view_if_needed()
    check_axe(page, "listen with a figure")
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.reload()
    at_rest(page)
    expect(page.locator(FIGURE)).to_have_attribute("alt", "Figure 1: A chart of things.")
    check_axe(page, "listen with a figure, German")
    page.set_extra_http_headers({})


def test_a_figure_below_the_first_screen_loads_when_scrolled_to(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """#582: a lazy image that has not started is not hidden as failed at
    start (it would then never load), and it loads once scrolled to."""
    page = signed_in
    listen_to(page, live, tmp_path / "late.pdf", late_figure_pdf())
    at_rest(page)
    figure = page.locator(FIGURE)
    expect(figure).to_have_count(1)
    below = page.evaluate(
        "(s) => document.querySelector(s).getBoundingClientRect().top > window.innerHeight",
        FIGURE,
    )
    assert below
    state = page.evaluate(
        "(s) => { const i = document.querySelector(s); return [i.hidden, i.naturalWidth]; }",
        FIGURE,
    )
    assert state == [False, 0]
    figure.scroll_into_view_if_needed()
    page.wait_for_function(
        "(s) => { const i = document.querySelector(s); return i.complete && i.naturalWidth > 0; }",
        arg=FIGURE,
    )
    expect(figure).to_be_visible()


def test_an_image_that_failed_before_the_script_ran_is_hidden_too(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """player.js hides a figure whose load failed before it was wired, not
    only one whose error event comes after."""
    page = signed_in
    open_figure(page, live, tmp_path)
    held: list[Route] = []

    def gone(route: Route) -> None:
        route.fulfill(status=404, body="")

    page.route("**/static/player.js", lambda route: held.append(route))
    page.route("**/figures/**", gone)
    page.reload(wait_until="commit")
    page.wait_for_function("(s) => document.querySelector(s) !== null", arg=FIGURE)
    page.wait_for_function(
        """(s) => { const i = document.querySelector(s);
            return i.complete && i.naturalWidth === 0; }""",
        arg=FIGURE,
    )
    assert page.evaluate("(s) => document.querySelector(s).hidden", FIGURE) is False
    assert held, "player.js was not requested"
    held[0].continue_()
    at_rest(page)
    expect(page.locator(FIGURE)).to_be_hidden()
    expect(page.locator("#text .notice > p")).to_contain_text("Figure 1")
    page.unroute("**/static/player.js")
    page.unroute("**/figures/**")
