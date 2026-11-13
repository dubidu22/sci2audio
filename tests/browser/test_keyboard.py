"""The main flow with the keyboard alone (AQ-01, #8; D-257): Tab, Shift+Tab, Space, Enter
and the arrow keys. Every stop shows a visible focus ring, the focus lands on the result of
each action, and Tab never gets stuck."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect
from test_flow import PDF

from conftest import Live

MAX_TABS = 80
# WebKit tabs to links only with Alt held, as Safari does unless its setting is on
TAB = {"webkit": "Alt+Tab"}


def focused(page: Page) -> dict[str, str]:
    return page.evaluate(
        """() => {
            const el = document.activeElement;
            const style = getComputedStyle(el);
            return {
                tag: el.tagName.toLowerCase(),
                id: el.id || "",
                text: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim(),
                outline: style.outlineStyle,
                width: style.outlineWidth,
            };
        }"""
    )


def tab_key(page: Page) -> str:
    return TAB.get(page.context.browser.browser_type.name, "Tab")  # type: ignore[union-attr]


def tab_to(page: Page, wanted: str, *, back: bool = False) -> None:
    """Press Tab (or Shift+Tab) until the focused element matches `wanted` (an id, or the
    start of its text); each stop on the way must show its focus ring."""
    key = f"Shift+{tab_key(page)}" if back else tab_key(page)
    for _ in range(MAX_TABS):
        page.keyboard.press(key)
        now = focused(page)
        if now["tag"] not in ("body", "html"):
            assert now["outline"] != "none", now  # a visible focus ring
            assert float(now["width"].removesuffix("px")) >= 2, now
        if now["id"] == wanted or now["text"].startswith(wanted):
            return
    raise AssertionError(f"{wanted!r} can't be reached with {key}")


def press_on(page: Page, wanted: str, key: str = "Enter", **kwargs: bool) -> None:
    tab_to(page, wanted, **kwargs)
    page.keyboard.press(key)


def test_the_main_flow_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    tab_to(page, "Skip to the content")  # the first stop
    page.keyboard.press("Enter")
    tab_to(page, "file")
    with page.expect_file_chooser() as chooser:
        page.keyboard.press("Space")
    chooser.value.set_files(files=[PDF])
    press_on(page, "Open and analyse")
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()

    # a switch, a chapter, then the update; the focus comes back to the step's heading
    press_on(page, "category-citations", "Space")
    expect(page.locator("#category-citations")).not_to_be_checked()
    press_on(page, "chapter-1", "Space")
    expect(page.locator("#chapter-1")).not_to_be_checked()
    press_on(page, "Update the analysis")
    expect(page.locator("#changed")).to_be_hidden()
    expect(page.locator("#step-check")).to_be_focused()
    expect(page.locator("#counts-citations")).to_contain_text("1 switched off")

    # a list of changes opens with Enter and its table scrolls by keyboard
    press_on(page, "Reference list: left out: 2 changes")
    expect(page.locator("details").filter(has_text="Reference list")).to_have_attribute("open", "")

    # the start button explains itself instead of doing nothing silently
    press_on(page, "make")
    expect(page.locator("#message")).to_have_text("Set up the voice first.")
    expect(page.locator("#message")).to_be_focused()

    # the voice setup, back by Shift+Tab to the link
    press_on(page, "Set up the voice", back=True)
    page.wait_for_url(re.compile(r"/voice$"))
    press_on(page, "voice-consent", "Space")
    press_on(page, "Download the voice")
    page.wait_for_url(re.compile(r"/jobs/voices-\d+"))
    expect(page.locator("#result")).to_be_focused()

    # home by the header link, the document by its link
    press_on(page, "sci2audio", back=True)
    page.wait_for_url(live.url + "/")
    press_on(page, "paper.pdf")
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))

    tab_to(page, "speed")
    for _ in range(4):
        page.keyboard.press("ArrowRight")
    expect(page.locator("#speed-value")).to_have_text("1.2 times")
    press_on(page, "Listen")
    expect(page.locator("#preview-audio")).to_be_focused()
    press_on(page, "make")
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready")
    expect(page.locator("#result")).to_be_focused()
    press_on(page, "Free the speech cache")
    expect(page.locator("#message")).to_be_focused()
    expect(page.locator("#message")).to_have_text("The speech cache is empty.")


def test_tab_goes_round_every_page_without_a_trap(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.set_input_files("#file", files=[PDF])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    for path in (page.url, live.url + "/", live.url + "/voice"):
        page.goto(path)
        stops = []
        for _ in range(MAX_TABS * 2):
            page.keyboard.press(tab_key(page))
            now = focused(page)
            if now["tag"] == "body":
                break
            stops.append((now["tag"], now["id"], now["text"][:30]))
        else:
            raise AssertionError(f"Tab never left {path}: {stops[-5:]}")
        assert stops[0][2] == "Skip to the content"
        assert len(stops) == len(set(stops)), "a stop came twice in one round"
        tabbed = page.evaluate(
            "() => [...document.querySelectorAll('[tabindex]')].map(e => e.tabIndex)"
        )
        assert all(index <= 0 for index in tabbed)  # no tabindex above 0
