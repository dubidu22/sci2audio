"""Removing a document in the browser (#120, D-359 to D-362): by keyboard alone, with
axe-core on every new page state, in English and German, and without a sideways scroll at
320 pixels. The request goes out as the page's own `fetch`, so the origin check (D-194)
lets it through."""

from __future__ import annotations

import io
import json
import re

import pytest
from playwright.sync_api import Page, Route, expect
from test_keyboard import press_on
from test_reflow import WIDTH, check_reflow
from web_helpers import pdf_bytes

from conftest import Live, check_axe
from sci2audio.web.player import write_record


def opened(live: Live, name: str, text: str, *, audiobook: bool = False) -> str:
    """A document put in place as the server keeps it; with the records of an audiobook."""
    document = live.state.store.store(name, io.BytesIO(pdf_bytes(text)))
    if audiobook:
        (document.folder / "audio.json").write_text("{}", encoding="utf-8")
        write_record(document.folder, document.id, live.config.output_folder)
    return document.id


def test_removing_from_the_start_page_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    first = opened(live, "first.pdf", "The first note.", audiobook=True)
    second = opened(live, "second.pdf", "The second note.")
    page.goto(live.url + "/")
    check_axe(page, "start page, disclosures closed")

    press_on(page, "Remove first.pdf…")
    button = page.get_by_role("button", name="Remove first.pdf now")
    expect(button).to_be_visible()
    stays = f"Your audiobook stays in {live.config.output_folder}."
    expect(page.get_by_text(stays)).to_be_visible()
    check_axe(page, "start page, disclosure open")
    press_on(page, "Remove first.pdf now")

    message = page.locator("#message")
    expect(message).to_have_text(
        f"first.pdf was removed. Your audiobook stays in {live.config.output_folder}."
    )
    expect(message).to_be_focused()
    expect(page.get_by_role("link", name="first.pdf")).to_have_count(0)
    expect(page.get_by_role("link", name="second.pdf")).to_be_visible()
    assert not (live.config.work_root / first).exists()
    assert (live.config.work_root / second / "source" / "second.pdf").is_file()
    check_axe(page, "start page after a removal")

    press_on(page, "Remove second.pdf…")
    press_on(page, "Remove second.pdf now", key="Space")
    expect(message).to_have_text("second.pdf was removed.")
    expect(message).to_be_focused()
    expect(page.locator("#documents")).to_have_count(0)
    expect(page.get_by_text("No document opened yet.")).to_be_visible()
    check_axe(page, "start page, the last document removed")


def test_removing_from_the_document_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = opened(live, "paper.pdf", "A paper.", audiobook=True)
    page.goto(f"{live.url}/documents/{document}")
    expect(page.get_by_role("heading", name="Remove this document")).to_be_visible()
    page.get_by_text("Remove this document…").click()
    check_axe(page, "document page, removal open")
    requests: list[dict[str, str]] = []
    page.on(
        "request",
        lambda request: (
            requests.append({"method": request.method, **request.headers})
            if request.method == "DELETE"
            else None
        ),
    )
    page.get_by_role("button", name="Remove paper.pdf now").click()

    title = page.get_by_role("heading", name="paper.pdf was removed.")
    expect(title).to_be_focused()
    stays = f"Your audiobook stays in {live.config.output_folder}."
    expect(page.get_by_text(stays)).to_be_visible()
    expect(page.locator("#step-check")).to_have_count(0)
    expect(page.locator("#make")).to_have_count(0)
    assert [r["method"] for r in requests] == ["DELETE"]  # one request
    assert not (live.config.work_root / document).exists()
    check_axe(page, "document page after the removal")
    page.get_by_role("link", name="Back to the start page").click()
    expect(page).to_have_url(live.url + "/")
    expect(page.get_by_text("No document opened yet.")).to_be_visible()


def test_a_failed_removal_says_why_and_keeps_the_button(signed_in: Page, live: Live) -> None:
    page = signed_in
    opened(live, "stuck.pdf", "A stuck note.")
    page.goto(live.url + "/language?language=de&back=/")
    expect(page.locator("html")).to_have_attribute("lang", "de")

    def refuse(route: Route) -> None:
        if route.request.method != "DELETE":
            route.continue_()
            return
        route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps(
                {"error": "remove-failed", "message": "could not remove /x/chunks/ab/c.wav"}
            ),
        )

    page.route(re.compile(r".*/api/v1/documents/[0-9a-f]{16}$"), refuse)
    page.get_by_text("stuck.pdf entfernen …").click()
    button = page.get_by_role("button", name="stuck.pdf jetzt entfernen")
    button.click()
    message = page.locator("#message")
    expect(message).to_contain_text("sci2audio konnte das Dokument nicht ganz entfernen.")
    expect(message.locator("span[lang=en]")).to_have_text("could not remove /x/chunks/ab/c.wav")
    expect(message).to_be_focused()
    expect(button).not_to_have_attribute("aria-disabled", "true")
    expect(page.get_by_role("link", name="stuck.pdf")).to_be_visible()
    check_axe(page, "start page, removal failed (German)")


@pytest.mark.parametrize("language", ["en", "de"])
def test_the_removal_reflows_at_320_pixels(signed_in: Page, live: Live, language: str) -> None:
    page = signed_in
    long_name = "averylongfilenamewithoutanyspaceorhyphenatallfromajournal" * 2 + ".pdf"
    document = opened(live, long_name, "A note with a long name.", audiobook=True)
    page.set_viewport_size({"width": WIDTH, "height": 800})
    page.goto(f"{live.url}/language?language={language}&back=/")
    expect(page.locator("html")).to_have_attribute("lang", language)
    page.locator("details.remove summary").click()
    check_reflow(page, f"start page, removal open ({language})")
    page.goto(f"{live.url}/documents/{document}")
    page.locator("details.remove summary").click()
    check_reflow(page, f"document page, removal open ({language})")
    page.locator("button.remove-now").click()
    expect(page.locator("#removed-title")).to_be_focused()
    check_reflow(page, f"document page, removed ({language})")
