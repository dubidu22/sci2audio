"""The shell of "The Working Reader" in a real browser (#385, #387; D-663, D-670, D-672):
the rail at the design's widths, its focus ring, the bundled fonts, the Highlighter rule,
reduced motion, and axe on every page with dark chosen in Settings as well as by the system.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from test_flow import open_paper

from conftest import Live, axe_problems, check_axe

WIDTHS = {1440: 900, 1280: 800}

# What a page may never paint in a highlighter colour (DESIGN.md, the Highlighter rule): the
# wordmark's "2" is the one place the design gives reading yellow outside the text.
CONTROLS = "button, .btn, .chip, .nav a, .rail-foot a, .shelf a, .seg, input, select, progress"
HIGHLIGHTED = """(selector) => {
    const probe = document.createElement("span");
    document.body.append(probe);
    const names = ["--hl-read", "--hl-note", "--hl-quote", "--hl-card", "--hl-mark"];
    const colours = names.map((name) => {
        probe.style.setProperty("color", `var(${name})`);
        return getComputedStyle(probe).color;
    });
    probe.remove();
    const found = [];
    for (const el of document.querySelectorAll(selector)) {
        const style = getComputedStyle(el);
        for (const part of ["backgroundColor", "borderTopColor", "color"]) {
            const where = `${el.tagName}#${el.id}.${el.className} ${part}`;
            if (colours.includes(style[part])) found.push(where);
        }
    }
    return found;
}"""


def pages(page: Page, live: Live) -> list[str]:
    document = open_paper(page, live)
    return ["/", f"/documents/{document}", "/voice", "/privacy", "/settings", "/jobs/nothing"]


def rail_width(page: Page) -> float:
    width = page.evaluate("() => document.querySelector('.rail').getBoundingClientRect().width")
    return float(width)


def scrolls_sideways(page: Page) -> bool:
    return bool(
        page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
    )


def test_the_rail_at_the_designs_widths(signed_in: Page, live: Live) -> None:
    page = signed_in
    for path in pages(page, live):
        for width, height in WIDTHS.items():
            page.set_viewport_size({"width": width, "height": height})
            page.goto(live.url + path)
            assert rail_width(page) == (264 if width == 1440 else 232), (path, width)
            assert not scrolls_sideways(page), (path, width)


def test_the_rail_stays_in_view_while_the_page_scrolls(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.set_viewport_size({"width": 1280, "height": 500})
    open_paper(page, live)
    page.mouse.move(800, 300)
    page.mouse.wheel(0, 2000)
    page.wait_for_function("() => window.scrollY > 300")
    top = page.evaluate("() => document.querySelector('.rail').getBoundingClientRect().top")
    assert top == 0
    expect(page.get_by_role("link", name="Settings")).to_be_in_viewport()


def focus_colour(page: Page, selector: str) -> str:
    page.locator(selector).first.focus()
    return str(page.evaluate("() => getComputedStyle(document.activeElement).outlineColor"))


@pytest.mark.parametrize("dark", [False, True])
def test_the_focus_ring_in_the_rail_and_on_paper(signed_in: Page, live: Live, dark: bool) -> None:
    page = signed_in
    if dark:
        page.emulate_media(color_scheme="dark")
    page.goto(live.url + "/settings")
    page.keyboard.press("Tab")  # keyboard focus, so :focus-visible applies
    yellow = "rgb(255, 233, 74)" if not dark else "rgb(242, 220, 58)"
    on_paper = "rgb(35, 64, 168)" if not dark else "rgb(95, 182, 240)"  # cobalt, quote blue
    assert focus_colour(page, ".nav a") == yellow
    assert focus_colour(page, "#settings-folder") == on_paper
    page.emulate_media(color_scheme="light")


def test_the_bundled_fonts_load(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/settings")
    page.evaluate("() => document.fonts.load('15px \"Atkinson Hyperlegible\"')")
    page.evaluate("() => document.fonts.load('20px Literata')")
    page.evaluate("() => document.fonts.ready")
    assert page.evaluate("() => document.fonts.check('15px \"Atkinson Hyperlegible\"')")
    assert page.evaluate("() => document.fonts.check('700 15px \"Atkinson Hyperlegible\"')")
    assert page.evaluate("() => document.fonts.check('20px Literata')")
    family = page.evaluate("() => getComputedStyle(document.body).fontFamily")
    # Chromium and Firefox write the name in quotes, WebKit without them
    assert family.split(",")[0].strip().strip("\"'") == "Atkinson Hyperlegible", family
    # every request stayed on this server: the fence in conftest fails the test otherwise


def test_no_highlighter_on_controls_navigation_or_chips(signed_in: Page, live: Live) -> None:
    page = signed_in
    for path in pages(page, live):
        page.goto(live.url + path)
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            assert page.evaluate(HIGHLIGHTED, CONTROLS) == [], (path, scheme)
        page.emulate_media(color_scheme="light")
    # the check sees one: a button painted reading yellow
    page.goto(live.url + "/settings")
    page.locator("#settings-save").evaluate(
        "b => b.style.setProperty('background-color', 'var(--hl-read)')"
    )
    assert page.evaluate(HIGHLIGHTED, CONTROLS) != []


def test_nothing_moves_under_reduced_motion(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.emulate_media(reduced_motion="reduce")
    page.goto(live.url + "/settings")
    durations = page.evaluate(
        """() => [...document.querySelectorAll('*')].map((el) => getComputedStyle(el))
            .flatMap((s) => [s.transitionDuration, s.animationDuration])"""
    )
    assert set(",".join(durations).replace(" ", "").split(",")) <= {"0s"}
    page.locator(".nav a").first.hover()
    assert page.evaluate("() => document.getAnimations().length") == 0
    page.emulate_media(reduced_motion="no-preference")
    page.goto(live.url + "/settings")
    switch = page.evaluate(
        "() => getComputedStyle(document.querySelector('.switch')).transitionDuration"
    )
    assert switch != "0s"  # the motion exists, and reduced motion is what stops it


def axe_with_dark_chosen(page: Page, where: str) -> list[str]:
    """axe with dark chosen in Settings while the system is light."""
    page.evaluate("() => { document.documentElement.dataset.theme = 'dark'; }")
    found = axe_problems(page, f"{where} (dark chosen)")
    page.evaluate("() => { delete document.documentElement.dataset.theme; }")
    return found


def test_axe_on_every_page_at_both_widths_and_in_every_scheme(signed_in: Page, live: Live) -> None:
    page = signed_in
    problems: list[str] = []
    for path in pages(page, live):
        for width, height in WIDTHS.items():
            page.set_viewport_size({"width": width, "height": height})
            page.goto(live.url + path)
            check_axe(page, f"{path} at {width}")
            problems += axe_with_dark_chosen(page, f"{path} at {width}")
    assert problems == []
