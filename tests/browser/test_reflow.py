"""Reflow (WCAG 2.2 SC 1.4.10, AA; D-257): at 320 CSS pixels wide no page state scrolls
sideways, in English and in German (#79, review of PR #142, M1). axe-core does not check
this. Wide tables may scroll inside their own region; the page itself may not."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect
from test_flow import PDF

from conftest import Live

WIDTH = 320


def page_width(page: Page) -> int:
    return int(page.evaluate("() => document.documentElement.scrollWidth"))


def wider_than_the_page(page: Page) -> list[str]:
    """The elements and texts that stick out past the right edge, for a readable failure."""
    return page.evaluate(
        """(width) => {
            const out = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                const range = document.createRange();
                range.selectNodeContents(node);
                const right = range.getBoundingClientRect().right;
                const inside = node.parentElement && node.parentElement.closest(".scroll");
                if (right > width + 0.5 && !inside) {
                    const where = node.parentElement.tagName.toLowerCase();
                    out.push(`text in ${where}: ${node.textContent.trim().slice(0, 60)}`);
                }
            }
            for (const el of document.querySelectorAll("body *")) {
                if (el.getBoundingClientRect().right > width + 0.5 && !el.closest(".scroll")) {
                    out.push(`${el.tagName.toLowerCase()}#${el.id}.${el.className}`);
                }
            }
            return out.slice(0, 8);
        }""",
        WIDTH,
    )


def check_reflow(page: Page, where: str) -> None:
    assert page_width(page) <= WIDTH, (where, page_width(page), wider_than_the_page(page))


@pytest.mark.parametrize("language", ["en", "de"])
def test_no_page_scrolls_sideways_at_320_pixels(signed_in: Page, live: Live, language: str) -> None:
    page = signed_in
    page.set_viewport_size({"width": WIDTH, "height": 800})
    page.goto(f"{live.url}/language?language={language}&back=/")
    expect(page.locator("html")).to_have_attribute("lang", language)
    check_reflow(page, "start page, nothing opened")

    page.set_input_files("#file", files=[PDF])
    page.locator("#open-file button[type=submit]").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    document = page.url.rsplit("/", 1)[1].split("#")[0]
    check_reflow(page, "document, voice missing")
    for details in page.locator("details").all():
        details.locator("summary").click()
    check_reflow(page, "document with every list of changes open")

    page.goto(live.url + "/voice")
    check_reflow(page, "voice page")
    page.goto(live.url + "/privacy")
    check_reflow(page, "privacy page")
    page.goto(live.url + "/jobs/nothing")
    check_reflow(page, "not found")

    live.install_voice()
    page.goto(f"{live.url}/documents/{document}")
    expect(page.locator("#preview")).to_be_visible()
    check_reflow(page, "document, voice installed")
    page.locator("#make").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("ul.files a").first).to_be_visible()
    check_reflow(page, "audiobook done")
    page.goto(live.url + "/")
    check_reflow(page, "start page with a document")
