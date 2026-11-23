"""Generating the remaining chapters later (#726, LW-04), in the browser: the project page
lists each chapter's state, "Generate the remaining chapters" adds them to the same project
and the Listen page plays the chapters made while the others are made; other settings than
the chapters were made with end the job with both choices, which the keyboard reaches
(D-909); axe-core on each new state."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect
from test_flow import update
from test_listen_growing import PDF, PER_CHARACTER

from conftest import Hold, Live, at_rest, check_axe, settled, tab_key

JOB_PAGE = re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+$")


def first_chapter_only(page: Page, live: Live) -> str:
    """Open the three-chapter paper and make its audiobook of the first chapter only;
    returns the document id, with the page on the finished job."""
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    page.set_input_files("#file", files=[PDF])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    at_rest(page)
    document = page.url.rsplit("/", 1)[1].split("#")[0]
    page.locator("#chapter-1").uncheck()
    page.locator("#chapter-2").uncheck()
    update(page)
    at_rest(page)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(JOB_PAGE)
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    at_rest(page)
    return document


def test_generate_the_remaining_chapters_and_listen_while_they_are_made(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    document = first_chapter_only(page, live)
    page.goto(f"{live.url}/documents/{document}")
    at_rest(page)
    expect(page.locator("#chapter-state-0")).to_have_text("generated")
    expect(page.locator("#chapter-state-1")).to_have_text("not generated")
    expect(page.locator("#chapter-state-2")).to_have_text("not generated")
    expect(page.get_by_role("button", name="Generate: Methods")).to_be_visible()
    check_axe(page, "project page with each chapter's state")
    # Methods passes, the voice holds at the Results title: Methods plays while it waits
    hold = Hold(after=2)
    live.voice.fail_on = hold
    try:
        page.get_by_role("button", name="Generate the remaining chapters").click()
        page.wait_for_url(JOB_PAGE)
        assert hold.reached.wait(60)
        expect(page.locator("#start-listening")).to_be_visible(timeout=30_000)
        page.get_by_role("link", name="Start listening").click()
        page.wait_for_url(f"{live.url}/documents/{document}/listen")
        at_rest(page)
        buttons = page.locator(".chapter-button .ot")
        expect(buttons).to_have_text(["Introduction", "Methods"])
        later = page.locator("li.chapter-later")
        expect(later).to_have_count(1)
        expect(later).to_contain_text("Results")
        expect(later).to_contain_text("being generated")
        expect(page.locator("button.generate")).to_have_count(0)  # one job at a time
        page.locator('.chapter-button[data-chapter="1"]').click()
        expect(page.locator("#now")).to_contain_text("Methods")
        check_axe(page, "listen page while the remaining chapters are made")
        page.evaluate("() => { window.sameLoad = true; }")
        hold.gate.set()
        expect(page.locator(".chapter-button")).to_have_count(3, timeout=60_000)
        expect(buttons).to_have_text(["Introduction", "Methods", "Results"])
        assert page.evaluate("() => window.sameLoad === true")  # added at the end, no reload
    finally:
        hold.gate.set()
    page.goto(f"{live.url}/documents/{document}")
    at_rest(page)
    for n in range(3):
        expect(page.locator(f"#chapter-state-{n}")).to_have_text("generated")
    expect(page.locator("button.generate")).to_have_count(0)
    expect(page.locator("#generate-rest")).to_have_count(0)


def test_generate_one_chapter_from_the_listen_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = first_chapter_only(page, live)
    page.goto(f"{live.url}/documents/{document}/listen")
    at_rest(page)
    rows = page.locator("li.chapter-later")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("not generated")
    check_axe(page, "listen page with chapters not generated")
    page.get_by_role("button", name="Generate: Results").click()
    page.wait_for_url(JOB_PAGE)
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    at_rest(page)
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(f"{live.url}/documents/{document}/listen")
    expect(page.locator(".chapter-button .ot")).to_have_text(["Introduction", "Results"])
    expect(page.locator("li.chapter-later")).to_have_count(1)
    expect(page.locator("li.chapter-later")).to_contain_text("Methods")


def test_the_settings_changed_dialog_offers_both_choices(signed_in: Page, live: Live) -> None:
    """Keyboard only: more chapters chosen with another speed end the job before any
    speech; Keep the earlier settings adds the chapter as the first was made."""
    page = signed_in
    tab = tab_key(page)
    document = first_chapter_only(page, live)
    page.goto(f"{live.url}/documents/{document}")
    at_rest(page)
    page.locator("#chapter-1").focus()
    page.keyboard.press("Space")
    expect(page.locator("#chapter-1")).to_be_checked()
    page.locator("#update").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#changed")).to_be_hidden()
    expect(page.locator("#step-check")).to_be_focused()
    settled(page)
    at_rest(page)
    speed = page.locator("#speed")
    before = speed.input_value()
    speed.focus()
    page.keyboard.press("ArrowRight")
    expect(speed).not_to_have_value(before)
    page.locator("#make").focus()
    page.keyboard.press("Enter")
    page.wait_for_url(JOB_PAGE)
    result = page.locator("#result")
    expect(result).to_have_text(
        "The chapters made so far were made with other settings", timeout=60_000
    )
    expect(result).to_be_focused()
    expect(page.locator("#job-changes li")).to_have_count(1)
    expect(page.locator("#job-changes")).to_contain_text("speed")
    expect(page.get_by_role("button", name="Make every chapter again")).to_be_visible()
    check_axe(page, "the settings-changed choice")
    page.keyboard.press(tab)
    keep = page.get_by_role("button", name="Keep the earlier settings")
    expect(keep).to_be_focused()
    page.keyboard.press("Enter")
    page.wait_for_url(JOB_PAGE)
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    at_rest(page)
    page.goto(f"{live.url}/documents/{document}/listen")
    at_rest(page)
    expect(page.locator(".chapter-button .ot")).to_have_text(["Introduction", "Methods"])
