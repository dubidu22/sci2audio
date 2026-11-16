"""Voices, Privacy, not found and the removal disclosure in the new design (#390): one panel
per voice pack, read by axe in both schemes and in German, and the removal by keyboard on
the document page, where the busy note and the danger button keep their roles."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from test_keyboard import press_on, tab_to
from test_remove import opened

from conftest import Live, check_axe


def test_the_voices_page_has_a_panel_per_pack(signed_in: Page, live: Live) -> None:
    page = signed_in
    for language, english, german, chip in (
        ("en", "English voices (Kokoro)", "German voice Thorsten", "Not installed"),
        ("de", "Englische Stimmen (Kokoro)", "Deutsche Stimme Thorsten", "Nicht installiert"),
    ):
        page.goto(f"{live.url}/language?language={language}&back=/voice")
        expect(page.locator("#pack-en h2")).to_have_text(english)
        expect(page.locator("#pack-de h2")).to_contain_text(german)
        for pack in ("#pack-en", "#pack-de"):
            state = page.locator(f"{pack} .chip")
            expect(state).to_have_text(chip)
            expect(state.locator("svg")).to_have_count(1)  # an icon beside the word
        expect(page.locator("#pack-en tbody tr")).to_have_count(2)  # the test plan's files
        check_axe(page, f"voices, nothing installed ({language})")
    page.goto(f"{live.url}/language?language=en&back=/voice")
    live.install_voice()
    page.reload()
    expect(page.locator("#voice-installed")).to_contain_text("Nothing needs to be downloaded.")
    expect(page.locator("#pack-en .chip")).to_have_text("Installed")
    expect(page.get_by_role("button", name="Download the voice")).to_have_count(0)
    check_axe(page, "voices, installed")


def test_privacy_and_not_found_read_as_panels(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/privacy")
    expect(page.locator("article.prose h2").first).to_be_visible()
    size = page.locator("article.prose h2 + p").first.evaluate("p => getComputedStyle(p).fontSize")
    assert size == "15.5px", size
    check_axe(page, "privacy")
    page.goto(live.url + "/jobs/nothing")
    link = page.get_by_role("link", name="Back to the library")
    expect(link).to_be_visible()
    link.click()
    expect(page).to_have_url(live.url + "/")


def test_removing_from_the_document_page_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = opened(live, "paper.pdf", "A paper.")
    page.goto(f"{live.url}/documents/{document}")
    page.locator("#step-remove").scroll_into_view_if_needed()
    press_on(page, "Remove this document…")  # the disclosure opens with Enter
    button = page.get_by_role("button", name="Remove paper.pdf now")
    expect(button).to_be_visible()
    check_axe(page, "document page, removal open, by keyboard")
    tab_to(page, "Remove paper.pdf now")
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="paper.pdf was removed.")).to_be_focused()
    assert not (live.config.work_root / document).exists()
