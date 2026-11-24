"""Capture while listening (#397, ADR-008; built on the v1.3 marker, #474): N, Q and M and
the dock's three keys, the flags and the ticks, the Captures tab, the note box, the toast's
Undo, the sounds, reduced motion and the highlighter rule."""

from __future__ import annotations

import errno
import json
import re
from pathlib import Path
from typing import Any

import pytest
from pdf_maker import Text, make_pdf
from playwright.sync_api import Page, Route, expect
from test_focus import colours, nobody_focused, order
from test_player import listen_to, make_audiobook, paused

from conftest import Live, check_axe, tab_key

# counts the tones the page plays (#397): the page makes them itself, nothing is fetched
COUNT_TONES = """
    window.tones = [];
    const Real = window.AudioContext;
    if (Real) {
        window.AudioContext = class extends Real {
            createOscillator() {
                const tone = super.createOscillator();
                const start = tone.start.bind(tone);
                tone.start = (...at) => { window.tones.push(tone.frequency.value); start(...at); };
                return tone;
            }
        };
    }
"""


def flags_at(page: Page, element: str) -> list[dict[str, Any]]:
    """The flags of the element, in the order they stand, with where each stands against the
    element's first line and the sheet's text column, after the next frames."""
    page.wait_for_timeout(600)  # past the slide
    found: list[dict[str, Any]] = page.evaluate(
        """(id) => {
            const line = [...document.getElementById(id).getClientRects()].find((r) => r.width);
            const column = document.getElementById('text').getBoundingClientRect();
            return [...document.querySelectorAll(`#capture-flags [data-for="${id}"]`)]
                .filter((flag) => !flag.hidden)
                .map((flag) => {
                    const box = flag.getBoundingClientRect();
                    return {
                        kind: flag.dataset.kind,
                        middle: box.top + box.height / 2 - (line.top + line.height / 2),
                        left: box.left - column.right, x: box.left,
                        width: box.width, height: box.height,
                        background: getComputedStyle(flag).backgroundColor,
                    };
                })
                .sort((a, b) => a.x - b.x);
        }""",
        element,
    )
    return found


def said(page: Page) -> Any:
    return page.locator("#capture-said")


def toast(page: Page) -> Any:
    return page.locator("#capture-toast")


def told(page: Page, words: str) -> None:
    """The toast is shown and says `words`: never the text of one hidden before."""
    expect(toast(page)).to_be_visible()
    expect(said(page)).to_have_text(words)


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
    return page.locator("#capture-list > li")


def tab(page: Page) -> Any:
    return page.locator("#tab-captures")


def test_m_and_q_capture_at_once_with_a_flag_a_tick_and_undo(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    mark, quote = page.locator("#capture-mark"), page.locator("#capture-quote")
    expect(mark).to_have_attribute("aria-pressed", "false")
    page.keyboard.press("m")
    expect(toast(page)).to_be_visible()
    expect(said(page)).to_have_text("Marked: page 1.")
    expect(page.locator("#capture-toast-flag")).to_have_class("flag f-mark")
    expect(page.locator("#message")).to_have_text("Marked: page 1.")  # for screen readers
    expect(mark).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote captured: page 1.")
    expect(quote).to_have_attribute("aria-pressed", "true")
    assert paused(page)  # nothing started or stopped the voice
    expect(tab(page)).to_have_text("Captures (2)")
    # one flag per type, side by side in the dock's order, at the sentence's first line
    flags = flags_at(page, sentence)
    assert [f["kind"] for f in flags] == ["quote", "mark"], flags
    for flag in flags:
        assert abs(flag["middle"]) <= 1, flag
        assert flag["left"] > 0, flag  # right of the text column
        assert flag["height"] == 18, flag
        assert flag["width"] == (24 if page.viewport_size["width"] > 1399 else 14), flag  # type: ignore[index]
    assert flags[0]["background"] != flags[1]["background"]  # each its own highlighter
    assert page.locator("#capture-flags").get_attribute("aria-hidden") == "true"
    expect(page.locator("#capture-ticks rect.f-quote")).to_have_count(1)
    expect(page.locator("#capture-ticks rect.f-mark")).to_have_count(1)
    # no fill: the sentence keeps the reading mark's own colours (D-724)
    page.keyboard.press("ArrowRight")
    plain = colours(page, "#text .s.now")
    page.keyboard.press("ArrowLeft")
    assert colours(page, "#text .s.now") == plain
    # Q again removes the quote, the toast's Undo brings it back
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote removed.")
    expect(quote).to_have_attribute("aria-pressed", "false")
    assert [f["kind"] for f in flags_at(page, sentence)] == ["mark"]
    page.locator("#capture-undo").click()
    expect(said(page)).to_have_text("Put back.")
    expect(page.locator("#capture-undo")).to_be_hidden()
    expect(quote).to_have_attribute("aria-pressed", "true")
    # the Undo of a new capture takes it back; a hidden toast says nothing, so each check
    # reads the toast of the change just made
    page.keyboard.press("m")
    told(page, "Mark removed.")
    page.keyboard.press("m")
    told(page, "Marked: page 1.")
    page.locator("#capture-undo").click()
    told(page, "Mark removed.")
    expect(tab(page)).to_have_text("Captures (1)")
    page.reload()
    expect(tab(page)).to_have_text("Captures (1)")
    assert [f["kind"] for f in flags_at(page, sentence)] == ["quote"]


def test_a_new_change_hides_the_toast_before_it_and_undo_waits_its_turn(
    signed_in: Page, live: Live
) -> None:
    """The Undo on screen while the next change is asked for would undo the one before it:
    the toast goes as soon as a key asks for a change."""
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("m")
    told(page, "Marked: page 1.")
    page.keyboard.press("q")  # the key's handler runs before press() returns
    assert page.evaluate(
        "() => document.getElementById('capture-toast').hidden"
        " || document.getElementById('capture-said').textContent === 'Quote captured: page 1.'"
    )
    told(page, "Quote captured: page 1.")
    page.locator("#capture-undo").click()  # the quote's Undo, not the mark's
    told(page, "Quote removed.")
    expect(page.locator("#capture-mark")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#capture-quote")).to_have_attribute("aria-pressed", "false")
    # Undo, then a key at once: the two run in the order asked
    page.locator("#capture-undo").click()
    page.keyboard.press("q")
    told(page, "Quote removed.")
    page.reload()
    expect(tab(page)).to_have_text("Captures (1)")


def test_n_pauses_opens_the_box_and_saves_with_ctrl_enter(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    nobody_focused(page)
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("n")
    box = page.get_by_role("textbox", name="Your note on this sentence")
    expect(box).to_be_focused()
    assert paused(page)  # while the box is open
    expect(tab(page)).to_have_attribute("aria-selected", "true")
    composer = page.locator("#capture-composer")
    expect(composer).to_contain_text("Paused while you write")
    expect(composer).to_contain_text(re.compile(r"(⌘|Ctrl)\+Enter saves, Esc cancels"))
    # the voice was in the first 1.2 s of the sentence: the note is for the one just heard
    quoted = composer.locator("blockquote").inner_text()
    assert quoted.strip()
    box.fill("n q m and space are letters here")
    expect(tab(page)).to_have_text("Captures (0)")  # no key acted
    page.keyboard.press("Control+Enter")
    expect(said(page)).to_have_text("Note saved: page 1.")
    expect(rows(page).first.locator(".cp-note")).to_have_text("n q m and space are letters here")
    expect(rows(page).first.get_by_role("button", name="Edit note")).to_be_focused()
    expect(rows(page).first.locator("blockquote")).to_have_text(quoted)
    page.wait_for_function("() => !document.getElementById('audio').paused")  # goes on
    page.locator("#play").click()
    # N on a sentence with a note opens that note; Esc leaves it unchanged
    noted = page.locator("#capture-flags [data-for]").get_attribute("data-for")
    assert noted in (sentence, *order(page))
    page.locator(f"#{noted}").click()
    page.locator("#play").click()
    nobody_focused(page)
    page.keyboard.press("n")
    box = page.get_by_role("textbox", name="Your note on this sentence")
    expect(box).to_have_value("n q m and space are letters here")
    box.fill("x" * 3700)
    expect(page.locator(".cp-left")).to_have_text("300 characters left")
    page.keyboard.press("Escape")
    expect(page.locator("#context")).to_be_visible()  # Esc closed the box, not the panel
    expect(rows(page).first.locator(".cp-note")).to_have_text("n q m and space are letters here")
    # emptied and saved, the note is removed, with Undo
    rows(page).first.get_by_role("button", name="Edit note").click()
    page.get_by_role("textbox", name="Your note on this sentence").fill("  ")
    page.get_by_role("button", name="Save and continue").click()
    expect(said(page)).to_have_text("Note removed.")
    expect(rows(page)).to_have_count(0)
    page.locator("#capture-undo").click()
    expect(rows(page).first.locator(".cp-note")).to_have_text("n q m and space are letters here")
    page.reload()
    page.locator("#tab-captures").click()
    expect(rows(page).first.locator(".cp-note")).to_have_text("n q m and space are letters here")


def test_a_new_note_cancelled_or_left_empty_keeps_nothing(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.locator("#capture-note").click()
    box = page.get_by_role("textbox", name="Your note on this sentence")
    expect(box).to_be_focused()
    box.fill("Not this one.")
    page.keyboard.press("Escape")
    expect(page.locator("#capture-composer textarea")).to_have_count(0)
    expect(page.locator("#capture-note")).to_be_focused()
    page.keyboard.press("Enter")  # the focused Note button opens the box again
    page.get_by_role("button", name="Save and continue").click()  # nothing written
    expect(tab(page)).to_have_text("Captures (0)")
    expect(page.locator("#captures-empty")).to_be_visible()


def test_an_open_draft_is_never_thrown_away(signed_in: Page, live: Live) -> None:
    """N again, the Note key, n on the box's own buttons and another note's Edit note all
    go back to the open box, with its text."""
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("n")
    page.get_by_role("textbox", name="Your note on this sentence").fill("First.")
    page.keyboard.press("Control+Enter")
    told(page, "Note saved: page 1.")
    nobody_focused(page)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("n")
    box = page.locator("#capture-composer textarea")
    box.fill("A draft I want to keep.")
    page.locator("#capture-composer").get_by_role("button", name="Cancel").focus()
    page.keyboard.press("n")  # on the box's own button: no new box
    expect(box).to_be_focused()
    expect(box).to_have_value("A draft I want to keep.")
    message = "Your note is still open. Save it or cancel it first."
    expect(page.locator("#message")).to_have_text(message)
    page.locator("#capture-note").click()
    expect(box).to_be_focused()
    rows(page).first.get_by_role("button", name="Edit note").click()
    expect(box).to_be_focused()
    expect(box).to_have_value("A draft I want to keep.")
    expect(rows(page).first.locator("textarea")).to_have_count(0)
    # a row's open box keeps what is typed while the list is drawn again (a quote set)
    page.keyboard.press("Escape")
    rows(page).first.get_by_role("button", name="Edit note").click()
    rows(page).first.locator("textarea").fill("Changed, not saved yet.")
    page.locator("#capture-quote").click()
    told(page, "Quote captured: page 1.")
    expect(page.locator("#capture-list textarea")).to_have_value("Changed, not saved yet.")


def test_a_second_windows_note_on_the_sentence_keeps_the_text_typed_here(
    signed_in: Page, live: Live
) -> None:
    """The server refuses a second note, and the box stays open with the text typed here."""
    page = signed_in
    document = make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("n")
    box = page.locator("#capture-composer textarea")
    box.fill("Typed here.")
    chunk, stamp = page.evaluate(
        """() => {
            const data = JSON.parse(document.getElementById('player-data').textContent);
            const now = document.querySelector('#text .s.now');
            return [Number(now.dataset.chunk), data.audiobook];
        }"""
    )
    other = page.request.post(  # the other window
        f"{live.url}/api/v1/documents/{document}/captures",
        data={"type": "note", "chunk": chunk, "audiobook": stamp, "text": "From the other."},
        headers={"Origin": live.url},
    )
    assert other.status == 201, other.text()
    page.get_by_role("button", name="Save and continue").click()
    expect(page.locator("#message")).to_contain_text("has a note already")
    expect(box).to_have_value("Typed here.")
    expect(toast(page)).to_be_hidden()
    expect(tab(page)).to_have_text("Captures (0)")  # nothing said it was saved


def test_a_new_note_saved_twice_at_once_is_sent_and_saved_once(signed_in: Page, live: Live) -> None:
    """A double click on Save and two quick Ctrl+Enter send one request each (#921)."""
    page = signed_in
    document = make_audiobook(page, live)
    posts: list[str] = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.url)
            if request.method == "POST" and request.url.endswith("/captures")
            else None
        ),
    )
    at_sentence(page)
    page.keyboard.press("n")
    page.locator("#capture-composer textarea").fill("Once.")
    page.get_by_role("button", name="Save and continue").dblclick()
    told(page, "Note saved: page 1.")
    expect(page.locator("#capture-undo")).to_be_visible()
    expect(tab(page)).to_have_text("Captures (1)")
    nobody_focused(page)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("n")
    page.locator("#capture-composer textarea").fill("Twice pressed.")
    page.keyboard.press("Control+Enter")
    page.keyboard.press("Control+Enter")
    told(page, "Note saved: page 1.")
    expect(page.locator("#capture-undo")).to_be_visible()
    expect(tab(page)).to_have_text("Captures (2)")
    page.wait_for_timeout(300)  # a second answer would have come by now
    told(page, "Note saved: page 1.")
    assert len(posts) == 2, posts
    path = Path(live.config.work_root) / document / "captures.json"
    notes = [c["text"] for c in json.loads(path.read_text(encoding="utf-8"))["captures"]]
    assert sorted(notes) == ["Once.", "Twice pressed."]


def test_the_undo_of_a_saved_note_keeps_the_text_typed_in_its_open_box(
    signed_in: Page, live: Live
) -> None:
    """The toast's Undo goes back to the note's open box when text is typed there; with
    nothing typed it removes the note, closes the box and the voice goes on (#921)."""
    page = signed_in
    document = make_audiobook(page, live)
    path = Path(live.config.work_root) / document / "captures.json"
    at_sentence(page)
    nobody_focused(page)
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("n")
    page.locator("#capture-composer textarea").fill("First.")
    page.keyboard.press("Control+Enter")
    told(page, "Note saved: page 1.")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    rows(page).first.get_by_role("button", name="Edit note").click()
    box = rows(page).first.locator("textarea")
    box.fill("First, and more typed.")
    assert paused(page)
    page.locator("#capture-undo").click()
    expect(box).to_be_focused()
    expect(box).to_have_value("First, and more typed.")
    expect(page.locator("#message")).to_have_text(
        "Your note is still open. Save it or cancel it first."
    )
    assert paused(page)  # the box is still open
    expect(tab(page)).to_have_text("Captures (1)")
    assert len(json.loads(path.read_text(encoding="utf-8"))["captures"]) == 1
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    # nothing typed: the Undo removes the note and its box, and the voice goes on
    nobody_focused(page)
    page.keyboard.press(" ")
    page.wait_for_function("() => document.getElementById('audio').paused")
    page.keyboard.press("ArrowRight")  # off the first note's sentence
    page.keyboard.press("ArrowRight")
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("n")
    second = page.locator("#capture-composer textarea")
    expect(second).to_be_focused()
    second.fill("Second.")
    page.keyboard.press("Control+Enter")
    told(page, "Note saved: page 1.")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    rows(page).filter(has_text="Second.").get_by_role("button", name="Edit note").click()
    expect(page.locator("#capture-list textarea")).to_have_value("Second.")
    assert paused(page)
    page.locator("#capture-undo").click()
    told(page, "Note removed.")
    expect(page.locator("#capture-list textarea")).to_have_count(0)
    expect(tab(page)).to_have_text("Captures (1)")
    page.wait_for_function("() => !document.getElementById('audio').paused")


def test_text_typed_while_an_undo_removes_the_note_is_never_dropped_unsaid(
    signed_in: Page, live: Live
) -> None:
    """#955: while the toast's Undo removes a new note whose box is open, the box takes no
    typing and its live line says why; if the removal fails, the box takes typing again,
    and once it is done the box closes with nothing typed in it lost."""
    page = signed_in
    document = make_audiobook(page, live)
    path = Path(live.config.work_root) / document / "captures.json"
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method == "DELETE":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/v1/documents/*/captures/*", hold)
    at_sentence(page)
    for words, answer in (("First.", "refused"), ("Second.", "removed")):
        page.keyboard.press("n")
        page.locator("#capture-composer textarea").fill(words)
        page.keyboard.press("Control+Enter")
        told(page, "Note saved: page 1.")
        made = rows(page).filter(has_text=words).get_attribute("data-capture")
        row = page.locator(f'#capture-list li[data-capture="{made}"]')
        row.get_by_role("button", name="Edit note").click()
        box = row.locator("textarea")
        expect(box).to_have_value(words)
        page.locator("#capture-undo").click()
        for _ in range(200):  # the handler runs while the page is waited on
            if held:
                break
            page.wait_for_timeout(25)
        assert len(held) == 1, answer
        expect(box).not_to_be_editable()
        expect(box).to_have_attribute("aria-busy", "true")
        expect(row.locator(".cp-left")).to_have_text("Removing this note…")
        box.click()
        page.keyboard.type(" And more.")
        expect(box).to_have_value(words)  # nothing typed went in, so nothing goes out
        if answer == "refused":
            held.pop().abort("connectionrefused")
            expect(box).to_be_editable()
            expect(box).to_have_attribute("aria-busy", "false")
            expect(row.locator(".cp-left")).to_have_text("")
            box.press_sequentially(" Kept.")
            expect(box).to_have_value(f"{words} Kept.")
            page.keyboard.press("Control+Enter")
            told(page, "Note saved: page 1.")
            nobody_focused(page)
            page.keyboard.press("ArrowRight")  # on to the next sentence's note
            page.keyboard.press("ArrowRight")
        else:
            held.pop().continue_()
            told(page, "Note removed.")
            expect(page.locator("#capture-list textarea")).to_have_count(0)
            expect(tab(page)).to_have_text("Captures (1)")
    page.unroute("**/api/v1/documents/*/captures/*")
    notes = [c["text"] for c in json.loads(path.read_text(encoding="utf-8"))["captures"]]
    assert notes == ["First. Kept."]


def test_every_capture_state_has_an_icon_and_a_word_and_passes_axe(
    signed_in: Page, live: Live
) -> None:
    """#955: found, not read, not found and no audiobook, side by side in the Captures
    tab; each state but found has an icon beside its word; axe in light and dark."""
    page = signed_in
    document = make_audiobook(page, live)
    work = Path(live.config.work_root) / document
    at_sentence(page)
    page.keyboard.press("q")
    told(page, "Quote captured: page 1.")
    nobody_focused(page)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("m")
    told(page, "Marked: page 1.")
    # a sentence of the reference list, which this audiobook leaves out, and one it lost
    blocks = json.loads((work / "document.json").read_text(encoding="utf-8"))["blocks"]
    unread = len(blocks) - 1
    assert blocks[unread]["text"] == "Smith, J. 2020. A book about things."
    path = work / "captures.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for id_, text, block in (("d" * 16, blocks[unread]["text"], unread),
                             ("f" * 16, "Not in here.", 0)):  # fmt: skip
        other = json.loads(json.dumps(data["captures"][0]))
        other.update(id=id_, type="note", text="Still mine.")
        other["anchor"] = {"block": block, "start": 0, "end": len(text), "text": text}
        data["captures"].append(other)
    path.write_text(json.dumps(data), encoding="utf-8")
    page.reload()
    page.locator("#tab-captures").click()
    expect(rows(page)).to_have_count(4)
    (work / "audio.json").unlink()
    mark = rows(page).filter(has_text="Mark")
    mark.get_by_role("button", name="Remove").click()
    told(page, "Mark removed.")
    page.locator("#capture-undo").click()
    told(page, "Put back.")
    expect(rows(page)).to_have_count(4)
    states = {
        "d" * 16: "Not read in this audiobook",
        "f" * 16: "Not found in this audiobook",
    }
    for id_, word in states.items():
        notice = page.locator(f'#capture-list li[data-capture="{id_}"] .cp-state')
        expect(notice).to_contain_text(word)
        expect(notice.locator("svg")).to_have_count(1)
    put_back = rows(page).filter(has_text="Mark").locator(".cp-state")
    expect(put_back).to_contain_text("This document has no audiobook now")
    expect(put_back.locator("svg")).to_have_count(1)
    expect(rows(page).filter(has_text="Quote to cite").locator(".cp-at")).to_be_visible()
    check_axe(page, "listen, captures in every state")


def test_a_capture_put_back_with_no_audiobook_is_labelled_so_and_listed_last(
    signed_in: Page, live: Live
) -> None:
    """The audiobook went away behind the page: Remove and Undo still work, and the capture
    put back says so with its own word and icon, after the ones placed (#934)."""
    page = signed_in
    document = make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("q")
    told(page, "Quote captured: page 1.")
    nobody_focused(page)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("m")
    told(page, "Marked: page 1.")
    page.locator("#tab-captures").click()
    expect(rows(page)).to_have_count(2)
    (Path(live.config.work_root) / document / "audio.json").unlink()
    quote = rows(page).filter(has_text="Quote to cite")
    quote.get_by_role("button", name="Remove").click()
    told(page, "Quote removed.")
    page.locator("#capture-undo").click()
    told(page, "Put back.")
    expect(rows(page)).to_have_count(2)
    last = rows(page).nth(1)
    expect(last.locator(".cp-kind")).to_have_text("Quote to cite")
    expect(last.locator(".cp-state")).to_have_text(
        "This document has no audiobook now. The sentence and what you wrote are kept."
    )
    expect(last.locator(".cp-state svg")).to_have_count(1)
    expect(last).not_to_contain_text("Not found")
    expect(last.get_by_role("button", name="Play from here")).to_have_count(0)
    expect(rows(page).nth(0).locator(".cp-kind")).to_have_text("Mark")


def test_play_from_here_and_a_capture_not_found_is_listed_without_it(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    target = at_sentence(page, 3)
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote captured: page 1.")
    path = Path(live.config.work_root) / document / "captures.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    lost = dict(data["captures"][0])
    lost.update(id="f" * 16, type="note", text="Still mine.")
    lost["anchor"] = {"block": 0, "start": 0, "end": 12, "text": "Not in here."}
    data["captures"].insert(0, lost)
    path.write_text(json.dumps(data), encoding="utf-8")
    page.reload()
    page.locator("#tab-captures").click()
    expect(rows(page)).to_have_count(2)
    found, missing = rows(page).nth(0), rows(page).nth(1)
    expect(found.locator(".cp-kind")).to_have_text("Quote to cite")
    expect(missing.locator(".cp-kind")).to_have_text("Note")
    expect(missing).to_contain_text("Not found in this audiobook")
    expect(missing).to_contain_text("Still mine.")
    expect(missing.get_by_role("button", name="Play from here")).to_have_count(0)
    expect(found.locator(".cp-at")).to_have_text(re.compile(r"^Chapter \d+ · \d+:\d\d$"))
    assert page.locator("#text .s.now").count() == 0 or highlighted_sentence(page) != target
    found.get_by_role("button", name="Play from here").click()
    expect(page.locator("#text .s.now")).to_have_id(target)
    assert paused(page)  # keeps play or pause


def test_with_the_keys_off_the_letters_do_nothing_and_the_buttons_work(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.context.add_cookies([{"name": "sci2audio-keys", "value": "off", "url": live.url}])
    page.reload()
    page.locator("#next-sentence").click()
    page.locator("#next-sentence").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    for key in "nqm":
        page.keyboard.press(key)
    expect(tab(page)).to_have_text("Captures (0)")
    expect(page.locator(".capkeys kbd")).to_have_count(0)
    page.locator("#capture-quote").click()
    expect(tab(page)).to_have_text("Captures (1)")
    expect(page.locator("#capture-quote")).to_have_attribute("aria-pressed", "true")


def test_in_focus_listening_q_flags_the_stage_and_n_leaves_for_the_box(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_visible()
    for word in ("Note", "Quote", "Mark"):
        expect(page.locator(".focus-foot")).to_contain_text(word)
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote captured: page 1.")
    staged = page.locator("#focus-flags .flag.f-quote")
    expect(staged).to_be_visible()
    box = staged.bounding_box()
    now = page.locator("#focus-now").bounding_box()
    assert box is not None
    assert now is not None
    assert box["x"] >= now["x"] + now["width"] - 1  # right of the stage's sentence
    page.keyboard.press("n")
    expect(page.locator("#focus-view")).to_be_hidden()
    expect(page.get_by_role("textbox", name="Your note on this sentence")).to_be_focused()
    page.keyboard.press("Escape")
    assert [f["kind"] for f in flags_at(page, sentence)] == ["quote"]


def test_two_quick_presses_set_and_remove_in_order(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    page.keyboard.press("m")
    page.keyboard.press("m")  # before the first answer came back
    expect(said(page)).to_have_text("Mark removed.")
    expect(tab(page)).to_have_text("Captures (0)")
    assert flags_at(page, sentence) == []


def test_a_key_early_in_a_sentence_takes_the_one_that_just_ended(
    signed_in: Page, live: Live
) -> None:
    """Within 1.2 s of a new sentence, while the voice reads, a key means the one heard."""
    page = signed_in
    make_audiobook(page, live)
    sentences = order(page)
    nobody_focused(page)
    page.locator(f"#{sentences[3]}").click()  # plays from its start
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote captured: page 1.")
    page.locator("#play").click()
    expect(page.locator("#capture-flags [data-for]")).to_have_attribute("data-for", sentences[2])


def test_the_undo_ends_after_sixty_seconds_and_with_the_next_capture(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.clock.install()
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("m")
    expect(page.locator("#capture-undo")).to_be_visible()
    page.clock.fast_forward(59_000)
    expect(page.locator("#capture-undo")).to_be_visible()
    page.clock.fast_forward(2_000)
    expect(toast(page)).to_be_hidden()
    page.keyboard.press("q")
    expect(tab(page)).to_have_text("Captures (2)")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("m")  # the next capture: the toast is the new one's
    expect(tab(page)).to_have_text("Captures (3)")
    page.locator("#capture-undo").click()
    expect(tab(page)).to_have_text("Captures (2)")
    expect(page.locator("#capture-mark")).to_have_attribute("aria-pressed", "false")


def test_the_sounds_play_unless_switched_off_in_settings(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.add_init_script(COUNT_TONES)
    make_audiobook(page, live)
    listen = page.url
    at_sentence(page)
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote captured: page 1.")
    page.keyboard.press("m")
    expect(said(page)).to_have_text("Marked: page 1.")
    assert page.evaluate("() => window.tones") == [880, 990]  # each type its own tone
    page.goto(f"{live.url}/settings")
    switch = page.get_by_role("switch", name="Play a short sound when something is captured")
    expect(switch).to_be_checked()
    switch.uncheck()
    page.locator("#sounds-form").get_by_role("button", name="Save").click()
    page.wait_for_url(re.compile(r"/settings$"))
    expect(switch).not_to_be_checked()
    check_axe(page, "settings with the sounds switch")
    page.goto(listen)
    at_sentence(page, 3)
    page.keyboard.press("m")
    expect(said(page)).to_have_text("Marked: page 1.")
    assert page.evaluate("() => window.tones") == []


def test_a_new_flag_slides_out_and_with_reduced_motion_it_just_stands(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentence = at_sentence(page)
    page.keyboard.press("m")
    expect(said(page)).to_have_text("Marked: page 1.")
    flag = page.locator(f'#capture-flags [data-for="{sentence}"]')
    assert flag.evaluate("(f) => getComputedStyle(f).transitionDuration").startswith("0.45s")
    page.emulate_media(reduced_motion="reduce")
    page.keyboard.press("q")
    expect(said(page)).to_have_text("Quote captured: page 1.")
    for each in flag.all():
        assert each.evaluate("(f) => getComputedStyle(f).transitionDuration") == "0s"
        assert each.evaluate("(f) => getComputedStyle(f).transform") == "none"
    assert toast(page).evaluate("(t) => getComputedStyle(t).animationName") == "none"
    page.emulate_media(reduced_motion="no-preference")


def test_no_highlighter_on_a_button_and_every_state_has_a_word(signed_in: Page, live: Live) -> None:
    """DESIGN.md, the Highlighter Rule: the colour stands on the key's flag only; a pressed
    key says so by its border and aria-pressed, never by a highlighter fill."""
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    before = colours(page, "#capture-mark")
    page.keyboard.press("m")
    expect(page.locator("#capture-mark")).to_have_attribute("aria-pressed", "true")
    after = colours(page, "#capture-mark")
    assert before[0] == after[0]  # the button's own background does not change
    highlighters = page.evaluate(
        """() => ['--hl-read', '--hl-note', '--hl-quote', '--hl-mark'].map((name) => {
            const probe = document.createElement('span');
            probe.style.background = `var(${name})`;
            document.body.append(probe);
            const colour = getComputedStyle(probe).backgroundColor;
            probe.remove();
            return colour;
        })"""
    )
    backgrounds = page.evaluate(
        """() => [...document.querySelectorAll('button, [role="tab"], nav a, .chip')]
            .map((e) => getComputedStyle(e).backgroundColor)"""
    )
    assert not set(backgrounds) & set(highlighters)
    for kind, word in (("note", "Note"), ("quote", "Quote"), ("mark", "Mark")):
        key = page.locator(f"#capture-{kind}")
        expect(key).to_have_accessible_name(re.compile(word))
        expect(key.locator("svg")).to_have_count(1)  # an icon and a word


def test_at_1440_and_1280_px_the_keys_and_flags_fit_and_below_the_panel_overlays(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    for width, words in ((1440, True), (1280, False)):
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate(
            "() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        sentence = at_sentence(page, 1)
        page.keyboard.press("q")
        page.keyboard.press("m")
        page.keyboard.press("n")
        page.get_by_role("textbox", name="Your note on this sentence").fill("Fits.")
        page.keyboard.press("Control+Enter")
        expect(said(page)).to_have_text("Note saved: page 1.")
        assert [f["kind"] for f in flags_at(page, sentence)] == ["note", "quote", "mark"]
        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
        panel = page.locator("#context").bounding_box()
        for flag in page.locator(f'#capture-flags [data-for="{sentence}"]').all():
            box = flag.bounding_box()
            assert box is not None
            assert panel is None or box["x"] + box["width"] <= panel["x"], (width, box, panel)
        # at 1399 px and below the words drop and the key caps stay (DESIGN.md)
        label = page.locator("#capture-note .lbl").bounding_box()
        assert label is not None
        assert (label["width"] > 1) is words, (width, label)
        expect(page.locator("#capture-note kbd")).to_be_visible()
        expect(page.locator("#capture-note")).to_have_accessible_name(re.compile("Note"))
        for key in "qm":  # clear the sentence for the next width
            page.keyboard.press(key)
        page.locator("#tab-captures").click()
        rows(page).first.get_by_role("button", name="Remove").click()
    # below 1280 px the panel opens over the page and the reading column stays as it is
    page.set_viewport_size({"width": 1024, "height": 768})
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    column = page.locator("#text").bounding_box()
    at_sentence(page, 1)
    page.keyboard.press("n")
    expect(page.locator("#context")).to_be_visible()
    expect(page.get_by_role("textbox", name="Your note on this sentence")).to_be_focused()
    assert page.locator("#text").bounding_box() == column
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 1280, "height": 720})


def test_the_panels_keyboard_order_over_the_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1024, "height": 768})
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    at_sentence(page)
    page.keyboard.press("n")
    box = page.get_by_role("textbox", name="Your note on this sentence")
    expect(box).to_be_focused()
    box.fill("Over the page.")
    page.keyboard.press("Control+Enter")
    edit = rows(page).first.get_by_role("button", name="Edit note")
    expect(edit).to_be_focused()
    # WebKit, like Safari, leaves buttons out of plain Tab: tab_key() moves to every item (#496)
    page.keyboard.press(f"Shift+{tab_key(page)}")
    expect(rows(page).first.get_by_role("button", name="Play from here")).to_be_focused()
    page.keyboard.press(tab_key(page))
    page.keyboard.press(tab_key(page))
    expect(rows(page).first.get_by_role("button", name="Remove")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#context")).to_be_hidden()
    page.set_viewport_size({"width": 1280, "height": 720})


def test_the_captures_tab_passes_axe_in_light_dark_and_german(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("q")
    page.keyboard.press("m")
    page.keyboard.press("n")
    page.get_by_role("textbox", name="Your note on this sentence").fill("A note.")
    check_axe(page, "listen, the note box")
    page.keyboard.press("Control+Enter")
    expect(rows(page).first.locator(".cp-note")).to_have_text("A note.")  # stored (#506)
    for theme in ("light", "dark"):
        page.emulate_media(color_scheme=theme)
        check_axe(page, f"listen, captures tab, {theme}")
    page.emulate_media(color_scheme="light")
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.reload()
    page.locator("#tab-captures").click()
    expect(tab(page)).to_have_text("Fundstücke (3)")
    expect(rows(page).first.get_by_role("button", name="Notiz bearbeiten")).to_be_visible()
    expect(page.locator(".capkeys")).to_have_attribute("aria-label", "Festhalten")
    for kind, word in (("note", "Notiz"), ("quote", "Zitat"), ("mark", "Marke")):
        expect(page.locator(f"#capture-{kind}")).to_contain_text(word)
    check_axe(page, "listen, captures tab, German")
    page.set_extra_http_headers({})


def test_a_broken_captures_file_is_named_and_left_alone(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    path = Path(live.config.work_root) / document / "captures.json"
    path.write_text("{broken", encoding="utf-8")
    page.reload()
    page.locator("#tab-captures").click()
    expect(page.locator("#captures-broken")).to_contain_text(str(path))
    at_sentence(page)
    for kind in ("note", "quote", "mark"):
        expect(page.locator(f"#capture-{kind}")).to_be_disabled()
    page.keyboard.press("m")
    expect(page.locator("#message")).to_contain_text("can't be read")
    assert path.read_text(encoding="utf-8") == "{broken"


def test_markers_whose_carry_over_cannot_be_written_say_so_on_n_q_and_m(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#910: a full disk while the v1.3 markers are carried over: the page names
    markers.json, and N, Q and M each say the captures could not be saved, never that a
    captures file can't be read."""
    from sci2audio.app import files
    from sci2audio.web.markers import markers_text

    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    page = signed_in
    document = make_audiobook(page, live)
    work = Path(live.config.work_root) / document
    raw = markers_text(document, []).encode("utf-8")
    (work / "markers.json").write_bytes(raw)
    monkeypatch.setattr(files, "_write_partial", full)
    page.reload()
    page.locator("#tab-captures").click()
    note = page.locator("#captures-broken")
    expect(note).to_contain_text("could not be saved as captures")
    expect(note).to_contain_text(str(work / "markers.json"))
    at_sentence(page)
    message = page.locator("#message")
    for key in "nqm":
        page.evaluate("() => { document.activeElement?.blur(); }")
        page.evaluate("() => { document.getElementById('message').textContent = ''; }")
        page.keyboard.press(key)
        expect(message).to_have_text("sci2audio could not save your captures.")
    expect(page.get_by_role("textbox", name="Your note on this sentence")).to_have_count(0)
    assert (work / "markers.json").read_bytes() == raw
    assert not (work / "captures.json").exists()


def at_words(page: Page, words: str) -> None:
    """Move sentence by sentence, paused, until the one being read holds `words`."""
    nobody_focused(page)
    for _ in range(12):
        page.keyboard.press("ArrowRight")
        page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
        if words in page.locator("#text .s.now").inner_text():
            return
    raise AssertionError(f"no sentence with {words!r}")


def test_the_toast_names_the_pdf_page_and_no_page_for_a_text(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """#888: for a PDF the toast names the page on which the sentence starts, in English
    and German; for a text it names none."""
    page = signed_in
    pdf = make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Sleep came late on the first night.", 72, 100, size=11),
        ],
        [
            Text("Methods", 72, 80, size=14),
            Text("We measured reaction times twice.", 72, 100, size=11),
        ],
    )
    listen_to(page, live, tmp_path / "two.pdf", pdf)
    at_words(page, "first night")
    page.keyboard.press("m")
    told(page, "Marked: page 1.")
    at_words(page, "twice")
    page.keyboard.press("q")
    told(page, "Quote captured: page 2.")
    expect(page.locator("#message")).to_have_text("Quote captured: page 2.")  # read out
    check_axe(page, "listen, the toast with a page")
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.reload()
    at_words(page, "twice")
    page.keyboard.press("n")
    page.get_by_role("textbox", name="Ihre Notiz zu diesem Satz").fill("Warum zweimal?")
    page.keyboard.press("Control+Enter")
    told(page, "Notiz gespeichert: Seite 2.")
    page.set_extra_http_headers({})
    page.goto(live.url)
    listen_to(page, live, tmp_path / "note.md", b"# Notes\n\nSleep came late. We slept twice.\n")
    at_words(page, "twice")
    page.keyboard.press("q")
    told(page, "Quote captured.")
    check_axe(page, "listen, the toast without a page")


def tab_row(page: Page) -> dict[str, Any]:
    """The panel's tab row: each tab's top and height, the row's height, and whether every
    tab ends before the close button."""
    found: dict[str, Any] = page.evaluate(
        """() => {
            const row = document.querySelector('#context .context-tabs');
            const tabs = [...row.querySelectorAll('[role="tab"]')];
            const close = document.getElementById('panel-close').getBoundingClientRect();
            const boxes = tabs.map((tab) => tab.getBoundingClientRect());
            return {
                tops: boxes.map((box) => box.top),
                heights: boxes.map((box) => box.height),
                row: row.getBoundingClientRect().height,
                fits: boxes.every((box) => box.right <= close.left),
                widths: boxes.map((box) => box.width),
                room: close.left - row.getBoundingClientRect().left,
            };
        }"""
    )
    return found


def on_one_row(page: Page, case: str) -> None:
    """Every panel tab one line high, side by side on one row, left of the close button."""
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    row = tab_row(page)
    where = f"{case}: {row}"
    assert len(set(row["tops"])) == 1, where  # no tab on a second row
    assert set(row["heights"]) == {44}, where  # each tab one line high
    assert row["row"] == 43, where  # one tab high, on the hairline it overlaps
    assert row["fits"], where


def test_the_panels_tabs_stay_on_one_line_in_german_and_english(
    signed_in: Page, live: Live
) -> None:
    """#889: at 1280 and 1440 px, light and dark, in English and German, every panel tab
    stays on one line, the third one with its count too."""
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("q")
    page.keyboard.press("m")
    page.keyboard.press("n")
    page.get_by_role("textbox", name="Your note on this sentence").fill("Three.")
    page.keyboard.press("Control+Enter")
    expect(tab(page)).to_have_text("Captures (3)")
    for language, third in (("de", "Fundstücke (3)"), ("en", "Captures (3)")):
        page.set_extra_http_headers({"Accept-Language": language})
        page.reload()
        expect(tab(page)).to_have_text(third)
        for width in (1280, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            for theme in ("light", "dark"):
                page.emulate_media(color_scheme=theme)
                on_one_row(page, f"{language} {width} {theme}")
    # a two-digit count fits too, in German at the narrower panel
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.reload()
    page.set_viewport_size({"width": 1280, "height": 900})
    page.evaluate("(words) => { document.getElementById('tab-captures').textContent = words; }",
                  "Fundstücke (32)")  # fmt: skip
    expect(tab(page)).to_have_text("Fundstücke (32)")
    on_one_row(page, "de 1280, two digits")
    page.emulate_media(color_scheme="light")
    page.set_extra_http_headers({})
    page.set_viewport_size({"width": 1280, "height": 720})


def test_the_panels_tabs_stay_on_one_line_with_a_three_digit_count(
    signed_in: Page, live: Live
) -> None:
    """#1000: at 1280 and 1440 px, in German and English, a count of 999 keeps every tab
    on one line, at 13 px text or more, and the tab's name still says the whole number."""
    page = signed_in
    make_audiobook(page, live)
    at_sentence(page)
    page.keyboard.press("q")
    expect(tab(page)).to_have_text("Captures (1)")
    for language, name in (("de", "Fundstücke (999)"), ("en", "Captures (999)")):
        page.set_extra_http_headers({"Accept-Language": language})
        page.reload()
        # the tab as the page draws it for 999 captures, without making 999 of them
        page.evaluate("(words) => { document.getElementById('tab-captures').textContent = words; }",
                      name)  # fmt: skip
        expect(tab(page)).to_have_accessible_name(name)
        assert page.evaluate(
            "() => [...document.querySelectorAll('#context [role=tab]')]"
            ".map((t) => parseFloat(getComputedStyle(t).fontSize))"
        ) == [13, 13, 13]
        for width in (1280, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            for theme in ("light", "dark"):
                page.emulate_media(color_scheme=theme)
                on_one_row(page, f"{language} {width} {theme}, three digits")
    page.emulate_media(color_scheme="light")
    page.set_extra_http_headers({})
    page.set_viewport_size({"width": 1280, "height": 720})


def test_the_shelf_item_of_the_document_follows_its_captures(signed_in: Page, live: Live) -> None:
    """#962: on the Listen page the rail's item of this document shows its flags and counts
    as captures are added and removed, drawn as the server draws them after a reload."""
    page = signed_in
    make_audiobook(page, live)
    page.reload()  # opened now, so the shelf holds it
    item = page.locator(".shelf a[aria-current='page']")
    expect(item).to_have_count(1)
    expect(item.locator(".flagstrip")).to_have_count(0)
    at_sentence(page)
    page.keyboard.press("q")
    told(page, "Quote captured: page 1.")
    expect(item).to_have_accessible_name(re.compile(r"1 quote$"))
    page.keyboard.press("m")
    told(page, "Marked: page 1.")
    expect(item).to_have_accessible_name(re.compile(r"1 quote, 1 mark$"))
    expect(item.locator(".flagstrip .num")).to_have_text(["1", "1"])
    strip = "(a) => [a.querySelector('.flagstrip').outerHTML, a.lastElementChild.outerHTML]"
    drawn = item.evaluate(strip)
    page.reload()  # the item may now be Continue listening: its strip is drawn alike
    assert item.evaluate(strip) == drawn
    at_sentence(page)
    page.keyboard.press("q")  # the same sentence: the quote goes
    told(page, "Quote removed.")
    expect(item).to_have_accessible_name(re.compile(r"1 mark$"))
    expect(item.locator(".flag")).to_have_count(1)
    page.keyboard.press("m")
    told(page, "Mark removed.")
    expect(item.locator(".flagstrip")).to_have_count(0)
    expect(item.locator(".visually-hidden")).to_have_count(0)
    page.locator("#capture-undo").click()
    told(page, "Put back.")
    expect(item).to_have_accessible_name(re.compile(r"1 mark$"))
    check_axe(page, "listen, the shelf with its flags")
