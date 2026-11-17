"""Markers with a note on the Listen page and in Focus listening (#474, D-723, D-728): M and
the dock's button, the flag and the tick, the Markers tab, the note box, the toast's Undo."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect
from test_focus import colours, nobody_focused, order
from test_player import make_audiobook, paused

from conftest import Live, check_axe


def marker_flag(page: Page, element: str) -> dict[str, Any]:
    """Where the flag of the element stands against the element's first line and the sheet's
    text column, after the next frame."""
    page.wait_for_timeout(50)
    found: dict[str, Any] = page.evaluate(
        """(id) => {
            const flag = document.querySelector(`#marker-flags [data-for="${id}"]`);
            if (!flag || flag.hidden) return { shown: false };
            const line = [...document.getElementById(id).getClientRects()].find((r) => r.width);
            const box = flag.getBoundingClientRect();
            const column = document.getElementById('text').getBoundingClientRect();
            const sheet = document.querySelector('.sheet').getBoundingClientRect();
            return {
                shown: true, middle: box.top + box.height / 2 - (line.top + line.height / 2),
                left: box.left - column.right, right: sheet.right - box.right,
                width: box.width, height: box.height,
                hidden: flag.parentElement.getAttribute('aria-hidden'),
            };
        }""",
        element,
    )
    return found


def toast(page: Page) -> Any:
    return page.locator("#marker-toast")


def at_sentence(page: Page, steps: int = 2) -> str:
    """Move a few sentences in, paused; the sentence being read."""
    nobody_focused(page)
    for _ in range(steps):
        page.keyboard.press("ArrowRight")
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    return highlighted_sentence(page)


def highlighted_sentence(page: Page) -> str:
    return str(page.locator("#text .s.now").get_attribute("id"))


def rows(page: Page) -> Any:
    return page.locator("#marker-list > li")


def test_m_sets_a_marker_with_a_flag_and_a_tick_and_undo_removes_it(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    button = page.locator("#marker")
    expect(button).to_have_attribute("aria-pressed", "false")
    page.keyboard.press("m")
    expect(toast(page)).to_be_visible()
    expect(page.locator("#marker-said")).to_have_text("Marker set.")
    expect(page.locator("#message")).to_have_text("Marker set.")  # for screen readers
    expect(button).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#tab-markers")).to_have_text("Markers (1)")
    flag = marker_flag(page, sentence)
    assert flag["shown"], flag
    assert abs(flag["middle"]) <= 1, flag  # at the sentence's first line
    assert flag["left"] > 0, flag  # in the sheet's right padding
    assert flag["right"] > 0, flag
    assert (flag["width"], flag["height"]) == (24, 18), flag
    assert flag["hidden"] == "true", flag
    expect(page.locator("#marker-ticks rect")).to_have_count(1)
    # no fill: the sentence keeps the reading mark's own colours (D-724)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#text .s.now")).to_have_id(sentence)
    marked_colours = colours(page, "#text .s.now")
    page.keyboard.press("ArrowRight")
    plain_colours = colours(page, "#text .s.now")
    assert marked_colours == plain_colours
    page.keyboard.press("ArrowLeft")
    # Undo removes it, and that toast's Undo brings it back
    page.locator("#marker-undo").click()
    expect(page.locator("#marker-said")).to_have_text("Marker removed.")
    expect(button).to_have_attribute("aria-pressed", "false")
    assert not marker_flag(page, sentence)["shown"]
    expect(page.locator("#marker-ticks rect")).to_have_count(0)
    page.locator("#marker-undo").click()
    expect(page.locator("#marker-said")).to_have_text("Marker put back.")
    expect(page.locator("#marker-undo")).to_be_hidden()
    expect(button).to_have_attribute("aria-pressed", "true")
    page.reload()
    expect(page.locator("#tab-markers")).to_have_text("Markers (1)")
    assert marker_flag(page, sentence)["shown"]


def test_m_on_a_marked_sentence_removes_it_and_undo_brings_back_its_note(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    page.keyboard.press("m")
    page.locator("#marker-add-note").click()  # opens the panel on the row
    box = page.get_by_role("textbox", name="Note")
    expect(box).to_be_focused()
    expect(page.locator("#tab-markers")).to_have_attribute("aria-selected", "true")
    box.fill("Ask Sam about the cohort.")
    page.keyboard.press("Control+Enter")
    expect(rows(page).first.locator(".mk-note")).to_have_text("Ask Sam about the cohort.")
    expect(rows(page).first.get_by_role("button", name="Edit note")).to_be_focused()
    nobody_focused(page)
    expect(page.locator("#text .s.now")).to_have_id(sentence)
    page.keyboard.press("m")
    expect(page.locator("#marker-said")).to_have_text("Marker and note removed.")
    expect(rows(page)).to_have_count(0)
    expect(page.locator("#markers-empty")).to_be_visible()
    page.locator("#marker-undo").click()
    expect(rows(page).first.locator(".mk-note")).to_have_text("Ask Sam about the cohort.")


def test_the_note_box_pauses_esc_leaves_it_and_a_note_survives_a_reload(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("m")
    page.locator("#tab-markers").click()
    nobody_focused(page)
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    rows(page).first.get_by_role("button", name="Add note").click()
    box = page.get_by_role("textbox", name="Note")
    expect(box).to_be_focused()
    assert paused(page)  # while the box is open (#397)
    box.fill("m and space and p are letters here")
    expect(page.locator("#tab-markers")).to_have_text("Markers (1)")  # m did not toggle
    page.keyboard.press("Escape")
    expect(box).to_have_count(0)
    expect(page.locator("#context")).to_be_visible()  # Esc closed the box, not the panel
    expect(rows(page).first.locator(".mk-note")).to_have_count(0)  # left unchanged
    page.wait_for_function("() => !document.getElementById('audio').paused")  # goes on
    page.locator("#play").click()
    rows(page).first.get_by_role("button", name="Add note").click()
    page.get_by_role("textbox", name="Note").fill("x" * 3700)
    expect(page.locator(".mk-left")).to_have_text("300 characters left")
    page.get_by_role("textbox", name="Note").fill("Kept.\nTwo lines.")
    rows(page).first.get_by_role("button", name="Save").click()
    page.reload()
    page.locator("#tab-markers").click()
    expect(rows(page).first.locator(".mk-note")).to_have_text("Kept.\nTwo lines.")


def test_go_to_moves_the_reading_there_and_a_marker_not_found_is_listed_without_it(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    target = at_sentence(page, 3)
    page.keyboard.press("m")
    expect(page.locator("#marker-said")).to_have_text("Marker set.")
    work = Path(live.config.work_root) / document / "markers.json"
    data = json.loads(work.read_text(encoding="utf-8"))
    lost = dict(data["markers"][0])
    lost["id"] = "f" * 16
    lost["anchor"] = {"block": 0, "start": 0, "end": 12, "text": "Not in here."}
    lost["note"] = "Still mine."
    data["markers"].insert(0, lost)
    work.write_text(json.dumps(data), encoding="utf-8")
    page.reload()
    page.locator("#tab-markers").click()
    expect(rows(page)).to_have_count(2)
    found, missing = rows(page).nth(0), rows(page).nth(1)
    expect(missing).to_contain_text("Not found in this audiobook")
    expect(missing).to_contain_text("Still mine.")
    expect(missing.get_by_role("button", name="Go to")).to_have_count(0)
    expect(found.locator(".mk-at")).to_have_text(re.compile(r"^Chapter \d+ · \d+:\d\d$"))
    assert page.locator("#text .s.now").count() == 0 or highlighted_sentence(page) != target
    found.get_by_role("button", name="Go to").click()
    expect(page.locator("#text .s.now")).to_have_id(target)
    assert paused(page)  # Go to keeps play or pause


def test_with_the_keys_off_m_does_nothing_and_the_button_still_works(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.context.add_cookies([{"name": "sci2audio-keys", "value": "off", "url": live.url}])
    page.reload()
    at_sentence_by_buttons(page)
    page.keyboard.press("m")
    expect(page.locator("#tab-markers")).to_have_text("Markers (0)")
    expect(page.locator("#marker kbd")).to_have_count(0)
    page.locator("#marker").click()
    expect(page.locator("#tab-markers")).to_have_text("Markers (1)")
    expect(page.locator("#marker")).to_have_attribute("aria-pressed", "true")


def at_sentence_by_buttons(page: Page) -> None:
    page.locator("#next-sentence").click()
    page.locator("#next-sentence").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")


def test_m_in_focus_listening_marks_the_stage_sentence(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_visible()
    expect(page.locator(".focus-foot")).to_contain_text("Marker")
    page.keyboard.press("m")
    expect(page.locator("#marker-said")).to_have_text("Marker set.")
    flag = page.locator("#focus-flag")
    expect(flag).to_be_visible()
    box = flag.bounding_box()
    now = page.locator("#focus-now").bounding_box()
    assert box is not None
    assert now is not None
    assert box["x"] >= now["x"] + now["width"] - 1  # right of the stage's sentence
    page.keyboard.press("Escape")
    assert marker_flag(page, sentence)["shown"]


def test_two_quick_presses_set_and_remove_in_order(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    page.keyboard.press("m")
    page.keyboard.press("m")  # before the first answer came back
    expect(page.locator("#marker-said")).to_have_text("Marker removed.")
    expect(page.locator("#tab-markers")).to_have_text("Markers (0)")
    assert not marker_flag(page, sentence)["shown"]


def test_m_early_in_a_sentence_marks_the_one_that_just_ended(signed_in: Page, live: Live) -> None:
    """#397: within 1.2 s of a new sentence, while the voice reads, M means the one heard."""
    page = signed_in
    make_audiobook(page, live)
    sentences = order(page)
    nobody_focused(page)
    page.locator(f"#{sentences[3]}").click()  # plays from its start
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("m")
    expect(page.locator("#marker-said")).to_have_text("Marker set.")
    page.locator("#play").click()
    page.locator("#tab-markers").click()
    expect(page.locator("#marker-flags [data-for]")).to_have_attribute("data-for", sentences[2])


def test_the_undo_ends_after_sixty_seconds_and_with_the_next_marker(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.clock.install()
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("m")
    expect(page.locator("#marker-undo")).to_be_visible()
    page.clock.fast_forward(59_000)
    expect(page.locator("#marker-undo")).to_be_visible()
    page.clock.fast_forward(2_000)
    expect(toast(page)).to_be_hidden()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("m")
    expect(page.locator("#tab-markers")).to_have_text("Markers (2)")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("m")  # the next marker action: the toast is the new one's
    expect(page.locator("#tab-markers")).to_have_text("Markers (3)")
    page.locator("#marker-undo").click()
    expect(page.locator("#tab-markers")).to_have_text("Markers (2)")
    expect(page.locator("#marker")).to_have_attribute("aria-pressed", "false")


def test_add_note_over_the_page_and_the_panels_keyboard_order(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1024, "height": 768})
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    at_sentence(page)
    page.keyboard.press("m")
    page.locator("#marker-add-note").click()
    expect(page.locator("#context")).to_be_visible()
    box = page.get_by_role("textbox", name="Note")
    expect(box).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#context")).to_be_visible()
    edit = rows(page).first.get_by_role("button", name="Add note")
    expect(edit).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(rows(page).first.get_by_role("button", name="Go to")).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(rows(page).first.get_by_role("button", name="Remove")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#context")).to_be_hidden()
    page.set_viewport_size({"width": 1280, "height": 720})


def test_the_markers_tab_passes_axe_in_light_dark_and_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("m")
    page.locator("#marker-add-note").click()
    page.get_by_role("textbox", name="Note").fill("A note.")
    page.keyboard.press("Control+Enter")
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        check_axe(page, f"listen, markers tab, {theme}")
    page.emulate_media(color_scheme="light")
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.reload()
    page.locator("#tab-markers").click()
    expect(page.locator("#tab-markers")).to_have_text("Markierungen (1)")
    expect(rows(page).first.get_by_role("button", name="Notiz bearbeiten")).to_be_visible()
    expect(page.locator("#marker")).to_contain_text("Markierung")
    check_axe(page, "listen, markers tab, German")
    page.set_extra_http_headers({})


def test_a_broken_markers_file_is_named_and_left_alone(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    work = Path(live.config.work_root) / document / "markers.json"
    work.write_text("{broken", encoding="utf-8")
    page.reload()
    page.locator("#tab-markers").click()
    expect(page.locator("#markers-broken")).to_contain_text(str(work))
    at_sentence(page)
    expect(page.locator("#marker")).to_be_disabled()
    page.keyboard.press("m")
    expect(page.locator("#message")).to_contain_text("can't be read")
    assert work.read_text(encoding="utf-8") == "{broken"
