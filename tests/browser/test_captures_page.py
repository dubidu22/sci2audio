"""The Captures page (#398, ADR-008): every document's captures as ruled rows with a hanging
flag, the filters by type and document, Remove with Undo in the toast (no struck-through
row), "Listen from here", "Not read in this audiobook" and "Not found", by keyboard, with
axe in light, dark and German, reduced motion and the highlighter rule."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect
from test_player import make_audiobook, paused

from conftest import Live, check_axe, tab_key

HIGHLIGHTERS = """() => ['--hl-read', '--hl-note', '--hl-quote', '--hl-mark', '--marker']
.map((name) => {
    const probe = document.createElement('span');
    probe.style.background = `var(${name})`;
    document.body.append(probe);
    const colour = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return colour;
})"""


def captured(page: Page, live: Live) -> dict[str, Any]:
    """An audiobook with a mark and a note on one sentence and a quote on the next, set
    through the API as the Listen page sets them; the page is left on the Listen page."""
    document = make_audiobook(page, live)
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    firsts = sorted({chunk for chunk, at in enumerate(data["sentences"]) if at == chunk})
    starts = [n for n in firsts if data["chunks"][n][3]][1:3]
    url = f"{live.url}/api/v1/documents/{document}/captures"
    ids = {}
    for kind, chunk, text in (
        ("mark", starts[0], ""),
        ("note", starts[0], "Ask Sam."),
        ("quote", starts[1], ""),
    ):
        body = {"type": kind, "chunk": chunk, "audiobook": data["audiobook"], "text": text}
        answer = page.request.post(url, data=body, headers={"Origin": live.url})
        assert answer.status == 201, answer.text()
        ids[kind] = answer.json()["id"]
    elements = {"mark": data["chunks"][starts[0]][3], "quote": data["chunks"][starts[1]][3]}
    return {
        "document": document,
        "ids": ids,
        "elements": elements,
        "file": captures_file(live, document),
    }


def captures_file(live: Live, document: str) -> Path:
    return Path(live.config.work_root) / document / "captures.json"


def open_captures(page: Page) -> None:
    page.locator("#nav-captures").click()
    page.wait_for_url("**/captures")
    expect(page.get_by_role("heading", level=1)).to_have_text("Captures")
    expect(page.locator("#nav-captures")).to_have_attribute("aria-current", "page")
    page.wait_for_load_state("load")
    expect(page.locator("button[data-remove]").first).to_be_enabled()  # the script is in


def shown(page: Page) -> Any:
    return page.locator(".capture-row:visible")


def said(page: Page) -> Any:
    return page.locator("#capture-said")


def stored(path: Path) -> list[str]:
    return [c["id"] for c in json.loads(path.read_text(encoding="utf-8"))["captures"]]


def test_the_page_filters_removes_with_undo_and_opens_the_player_there(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    made = captured(page, live)
    ids, path = made["ids"], made["file"]
    open_captures(page)
    expect(page.locator("#captures-summary")).to_have_text("3 captures from 1 document")
    expect(shown(page)).to_have_count(3)
    expect(shown(page).nth(0).locator(".cp-kind")).to_have_text("Note")  # the dock's order
    expect(shown(page).nth(0).locator(".cp-note")).to_have_text("Ask Sam.")
    expect(shown(page).nth(1).locator(".cp-kind")).to_have_text("Mark")
    expect(shown(page).nth(2).locator(".cp-kind")).to_have_text("Quote to cite")
    # by type, in place: the address keeps the choice
    quotes = page.locator('.cap-kinds button[data-kind="quote"]')
    quotes.click()
    expect(quotes).to_have_attribute("aria-pressed", "true")
    expect(shown(page)).to_have_count(1)
    assert "type=quote" in page.url
    page.reload()
    expect(shown(page)).to_have_count(1)
    expect(page.locator("#capture-show")).to_be_hidden()  # the choice applies as it is made
    page.locator('.cap-kinds button[data-kind="all"]').click()
    expect(shown(page)).to_have_count(3)
    # by document
    page.locator("#capture-from").select_option(made["document"])
    expect(shown(page)).to_have_count(3)
    # Remove takes the row out at once; the toast's Undo puts it back
    row = page.locator(f"#capture-{ids['quote']}")
    row.get_by_role("button", name="Remove").click()
    expect(row).to_be_hidden()
    struck = page.locator(".capture-row.cancelled, .capture-row s, .capture-row del")
    expect(struck).to_have_count(0)  # no struck-through row (ADR-008 2.1 item 6)
    expect(said(page)).to_have_text("Quote removed.")
    expect(page.locator("#message")).to_have_text("Quote removed.")  # for screen readers
    expect(page.locator("#capture-toast-flag")).to_have_class("flag f-quote")
    expect(page.locator('[data-count="quote"]')).to_have_text("0")
    expect(page.locator("#captures-summary")).to_have_text("2 captures from 1 document")
    assert ids["quote"] not in stored(path)
    page.locator("#capture-undo").click()
    expect(said(page)).to_have_text("Put back.")
    expect(page.locator("#capture-undo")).to_be_hidden()
    expect(row).to_be_visible()
    expect(page.locator('[data-count="quote"]')).to_have_text("1")
    assert ids["quote"] in stored(path)
    # Listen from here: the player opens at that sentence, paused
    page.locator(f"#capture-{ids['mark']}").get_by_role("link", name="Listen from here").click()
    page.wait_for_url(f"{live.url}/documents/{made['document']}/listen")
    expect(page.locator("#text .s.now")).to_have_id(made["elements"]["mark"])
    assert paused(page)


def test_the_page_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    made = captured(page, live)
    ids = made["ids"]
    open_captures(page)
    key = tab_key(page)
    page.locator('.cap-kinds button[data-kind="all"]').focus()
    for _ in range(3):  # All, Note, Quote
        page.keyboard.press(key)
    expect(page.locator('.cap-kinds button[data-kind="mark"]')).to_be_focused()
    page.keyboard.press("Enter")
    expect(shown(page)).to_have_count(1)
    expect(page.locator('.cap-kinds button[data-kind="mark"]')).to_be_focused()  # stays
    page.locator('.cap-kinds button[data-kind="all"]').focus()
    page.keyboard.press("Enter")
    expect(shown(page)).to_have_count(3)
    # the note's row: its link, then Remove
    note = page.locator(f"#capture-{ids['note']}")
    note.get_by_role("link", name="Listen from here").focus()
    page.keyboard.press(key)
    expect(note.get_by_role("button", name="Remove")).to_be_focused()
    page.keyboard.press("Enter")
    expect(note).to_be_hidden()
    undo = page.locator("#capture-undo")
    expect(undo).to_be_focused()  # the button pressed went with its row
    page.keyboard.press("Enter")
    expect(note).to_be_visible()
    expect(note.get_by_role("button", name="Remove")).to_be_focused()
    expect(said(page)).to_have_text("Put back.")


def test_not_read_and_not_found_are_listed_and_kept(signed_in: Page, live: Live) -> None:
    """ADR-008 2.1 item 3: neither is dropped, and the stored anchor is never rewritten."""
    page = signed_in
    made = captured(page, live)
    path = made["file"]
    data = json.loads(path.read_text(encoding="utf-8"))
    lost = dict(data["captures"][0])
    lost.update(id="f" * 16, type="note", text="Still mine.")
    lost["anchor"] = {"block": 0, "start": 0, "end": 12, "text": "Not in here."}
    data["captures"].append(lost)
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    open_captures(page)
    row = page.locator(f"#capture-{'f' * 16}")
    expect(row.locator(".cp-state")).to_contain_text("Not found in this audiobook")
    expect(row.locator(".cp-note")).to_have_text("Still mine.")
    expect(row.get_by_role("link")).to_have_count(0)
    expect(row.get_by_role("button", name="Remove")).to_be_visible()
    expect(shown(page).last).to_have_id(f"capture-{'f' * 16}")  # after those found
    assert path.read_bytes() == before
    check_axe(page, "captures, a capture not found")


def test_axe_in_light_dark_and_german_with_the_toast(signed_in: Page, live: Live) -> None:
    page = signed_in
    made = captured(page, live)
    open_captures(page)
    page.locator(f"#capture-{made['ids']['mark']}").get_by_role("button", name="Remove").click()
    expect(said(page)).to_have_text("Mark removed.")
    check_axe(page, "captures, the toast")  # light and dark
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.goto(f"{live.url}/captures")
    expect(page.get_by_role("heading", level=1)).to_have_text("Fundstücke")
    expect(page.locator("#nav-captures")).to_have_text("Fundstücke")
    expect(page.locator("#captures-summary")).to_have_text("2 Fundstücke aus 1 Dokument")
    expect(page.locator(".cap-kinds")).to_have_attribute("aria-label", "Art")
    expect(page.get_by_label("Aus")).to_be_visible()
    row = page.locator(f"#capture-{made['ids']['quote']}")
    expect(row.locator(".cp-kind")).to_have_text("Zitat zum Belegen")
    expect(row.get_by_role("link", name="Ab hier hören")).to_be_visible()
    row.get_by_role("button", name="Entfernen").click()
    expect(said(page)).to_have_text("Zitat entfernt.")
    expect(page.locator("#capture-undo")).to_have_text("Rückgängig")
    check_axe(page, "captures, German")
    page.set_extra_http_headers({})


def test_reduced_motion_and_no_highlighter_on_a_button(signed_in: Page, live: Live) -> None:
    """Nothing on the page moves with reduced motion; the colour stands on the flags only,
    and every type and state has an icon and a word."""
    page = signed_in
    made = captured(page, live)
    page.emulate_media(reduced_motion="reduce")
    open_captures(page)
    page.locator(f"#capture-{made['ids']['quote']}").get_by_role("button", name="Remove").click()
    expect(said(page)).to_have_text("Quote removed.")
    assert page.evaluate("() => document.getAnimations().length") == 0
    durations = page.evaluate(
        """() => [...document.querySelectorAll('#captures *')]
            .map((e) => getComputedStyle(e).transitionDuration)"""
    )
    assert set(durations) <= {"0s"}, set(durations)
    page.emulate_media(reduced_motion="no-preference")
    highlighters = page.evaluate(HIGHLIGHTERS)
    for pressed in ("all", "note", "quote", "mark"):
        page.locator(f'.cap-kinds button[data-kind="{pressed}"]').click()
        backgrounds = page.evaluate(
            """() => [...document.querySelectorAll('button, a.btn, nav a, .chip, select')]
                .map((e) => getComputedStyle(e).backgroundColor)"""
        )
        assert not set(backgrounds) & set(highlighters), pressed
    for kind, word in (("note", "Note"), ("quote", "Quote"), ("mark", "Mark")):
        button = page.locator(f'.cap-kinds button[data-kind="{kind}"]')
        expect(button).to_contain_text(word)
        expect(button.locator("svg")).to_have_count(1)
    for row in shown(page).all():
        expect(row.locator(".flag svg")).to_have_count(1)
        expect(row.locator(".cp-kind")).not_to_be_empty()


def test_at_1440_and_1280_px_and_narrower_nothing_scrolls_sideways(
    signed_in: Page, live: Live
) -> None:
    """In light and dark, English and German (#934)."""
    page = signed_in
    frames = "() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))"
    captured(page, live)
    open_captures(page)
    for language in ("en", "de"):
        page.set_extra_http_headers({"Accept-Language": language})
        page.reload()
        page.wait_for_load_state("load")
        expect(page.locator("html")).to_have_attribute("lang", language)
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            for width in (1440, 1280, 1024):
                where = (language, scheme, width)
                page.set_viewport_size({"width": width, "height": 900})
                page.evaluate(frames)
                fits = "() => document.documentElement.scrollWidth <= innerWidth"
                assert page.evaluate(fits), where
                flag = shown(page).first.locator(".flag").bounding_box()
                kind = shown(page).first.locator(".cp-kind").bounding_box()
                assert flag is not None
                assert kind is not None
                assert flag["x"] + flag["width"] <= kind["x"], where  # hangs in the margin
    page.emulate_media(color_scheme="light")
    page.set_extra_http_headers({})
    page.set_viewport_size({"width": 1280, "height": 720})
