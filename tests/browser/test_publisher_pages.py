"""A publisher's page in the document page's chapter list (#376, #190): the EPUB's
imprint, colophon and licence pages are not chosen by default and the list says why, as
it does for the reference list; they can still be chosen. axe finds nothing."""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect

from conftest import Live, check_axe, settled

TIME_MACHINE = Path(__file__).parent.parent / "corpus" / "epub" / "wells-the-time-machine.epub"
HINT = "publisher's page, not read by default"


def test_the_publishers_pages_say_why_they_are_not_chosen(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.set_input_files("#file", files=[TIME_MACHINE])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    for index in (1, 16, 17):  # 2. Imprint, 17. Colophon, 18. Uncopyright
        expect(page.locator(f"#chapter-details-{index}")).to_contain_text(HINT)
        box = page.locator(f"#chapter-{index}")
        expect(box).not_to_be_checked()
        expect(box).to_be_enabled()
    for index in (0, 2, 14, 15):  # the title page, I, Epilogue, Endnotes
        expect(page.locator(f"#chapter-details-{index}")).not_to_contain_text(HINT)
        expect(page.locator(f"#chapter-{index}")).to_be_checked()
    page.locator("#chapter-16").check()  # still choosable
    expect(page.locator("#chapter-16")).to_be_checked()
    check_axe(page, "document page of an EPUB with publisher's pages")
