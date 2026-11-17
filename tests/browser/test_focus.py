"""Focus listening, the keys and the keyboard shortcuts sheet (#394, WR-10): F and Esc, every
key and every case in which the keys stay out of the way, the sheet on every page, and axe
in light, dark and German in Focus and on the sheet."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from pdf_maker import Rect, Text, make_pdf
from playwright.sync_api import Page, expect
from test_flow import reload_holding_back_app_js
from test_listen import assert_beside, look, marked_plainly, uncovered
from test_player import chunk_id, highlighted, listen_to, make_audiobook, paused

from conftest import Live, check_axe, click_focuses

FOCUSING = re.compile(r"\bfocus-listening\b")


def focusing(page: Page) -> bool:
    return bool(
        page.evaluate("() => document.documentElement.classList.contains('focus-listening')")
    )


def nobody_focused(page: Page) -> None:
    """The focus on the page itself, as after a click on its text."""
    page.evaluate("() => { document.activeElement?.blur(); }")


def order(page: Page) -> list[str]:
    """The sentence elements in reading order (the player's data)."""
    ids: list[str] = page.evaluate(
        """() => {
            const data = JSON.parse(document.getElementById('player-data').textContent);
            return [...new Set(data.chunks.map((c) => c[3]))];
        }"""
    )
    return ids


def first_of(page: Page, chapter: int) -> str:
    """The element of the first sentence of this chapter."""
    return str(
        page.evaluate(
            """(c) => {
                const data = JSON.parse(document.getElementById('player-data').textContent);
                return data.chunks[data.chapters[c].first][3];
            }""",
            chapter,
        )
    )


def chunk_at(page: Page, time: float) -> str:
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    return str([e for start, _end, _c, e in data["chunks"] if start <= time + 0.0005][-1])


def words(page: Page, selector: str) -> str:
    return " ".join(page.locator(selector).inner_text().split())


def test_f_shows_focus_listening_and_esc_leaves_it(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    sentences = order(page)
    page.locator(f"#{sentences[1]}").click()  # plays from the second sentence
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.get_by_role("button", name="Pause").click()
    nobody_focused(page)
    page.keyboard.press("f")
    expect(page.locator("html")).to_have_class(FOCUSING)
    expect(page.get_by_role("region", name="Focus listening")).to_be_visible()
    expect(page.locator("#focus-view")).to_be_focused()
    for gone in (".rail", ".paper-head", "#context", "#text", "#panel-toggle", "#focus-on"):
        expect(page.locator(gone)).to_be_hidden()
    expect(page.locator("#dock")).to_be_visible()
    # the sentence being read, between its neighbours, in the sheet's own words
    current = highlighted(page)
    at = sentences.index(current)
    assert words(page, "#focus-now") == words(page, f"#{current}")
    assert words(page, "#focus-prev") == words(page, f"#{sentences[at - 1]}")
    assert words(page, "#focus-next") == words(page, f"#{sentences[at + 1]}")
    expect(page.locator("#focus-chapter")).to_have_text("Introduction")
    # the stage is not the dock's width only: the whole window, the rail gone
    assert page.locator("#dock").evaluate("e => e.getBoundingClientRect().left") == 0
    check_axe(page, "focus listening")
    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_class(FOCUSING)
    expect(page.locator("#focus-view")).to_be_hidden()
    expect(page.locator(".rail")).to_be_visible()
    expect(page.locator("#text")).to_be_visible()
    expect(page.get_by_role("button", name="Focus listening")).to_be_focused()
    # the button and Close do the same
    page.get_by_role("button", name="Focus listening").click()
    expect(page.locator("#focus-view")).to_be_focused()
    page.get_by_role("button", name="Close").click()
    expect(page.locator("#focus-view")).to_be_hidden()
    expect(page.get_by_role("button", name="Focus listening")).to_be_focused()
    # German
    page.goto(f"{live.url}/language?language=de&back=/documents/{document}/listen")
    page.get_by_role("button", name="Fokus-Hören").click()
    expect(page.locator("#focus-view")).to_be_focused()
    expect(page.get_by_role("button", name="Schließen")).to_be_visible()
    check_axe(page, "de: focus listening")
    page.goto(f"{live.url}/language?language=en&back=/documents/{document}/listen")


def test_the_voice_goes_on_and_the_stage_marks_its_sentence_plainly(
    signed_in: Page, live: Live
) -> None:
    """The stage follows the voice; its sentence carries the sheet's own plain mark, with no
    motion and no underline (D-709, #452), also under reduced motion."""
    page = signed_in
    make_audiobook(page, live)
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    sheet = marked_plainly(page, "#text .s.now")
    page.get_by_role("button", name="Focus listening").click()
    assert not paused(page)  # no page load: the voice goes on
    stage = marked_plainly(page, "#focus-now")
    assert stage["background"] == sheet["background"], (stage, sheet)
    one_mark(page)
    first = highlighted(page)
    page.wait_for_function(
        f"() => document.querySelector('#text .s.now')?.id !== '{first}'", timeout=20_000
    )
    now = highlighted(page)
    assert words(page, "#focus-now") == words(page, f"#{now}")
    assert words(page, "#focus-prev") == words(page, f"#{first}")
    marked_plainly(page, "#focus-now")
    page.get_by_role("button", name="Pause").click()
    page.emulate_media(reduced_motion="reduce")
    assert marked_plainly(page, "#focus-now")["background"] == stage["background"]
    page.emulate_media(reduced_motion="no-preference")
    # leaving brings the reading back into view
    page.keyboard.press("Escape")
    expect(page.locator(f"#{now}")).to_be_in_viewport()


def colours(page: Page, selector: str) -> tuple[str, str, str]:
    return tuple(  # type: ignore[return-value]
        page.evaluate(
            """(s) => { const st = getComputedStyle(document.querySelector(s));
                       return [st.backgroundColor, st.color, st.borderLeftColor]; }""",
            selector,
        )
    )


def one_mark(page: Page) -> None:
    """D-720, D-724: in Focus the sentence carries the sheet's own fill, text colour and bar,
    in light and in dark; the bar spans the stage's sentence."""
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        stage = colours(page, "#focus-now")
        bar = colours(page, "#focus-bar")
        assert_beside(page, "#focus-bar", "#focus-now")
        page.keyboard.press("Escape")
        assert colours(page, "#text .s.now")[:2] == stage[:2], (scheme, stage)
        assert colours(page, "#now-bar")[2] == bar[2], (scheme, bar)
        assert_beside(page, "#now-bar", "#text .s.now")
        page.get_by_role("button", name="Focus listening").click()
    page.emulate_media(color_scheme="light")


def font_size(page: Page, selector: str) -> float:
    return float(
        page.evaluate(
            "(s) => parseFloat(getComputedStyle(document.querySelector(s)).fontSize)", selector
        )
    )


def test_focus_type_is_only_a_little_larger_than_the_sheet(signed_in: Page, live: Live) -> None:
    """D-720 (#471): the sentence in Focus at most 1.25 times the sheet's size, wide and on a
    phone, and its neighbours no larger than the sheet."""
    page = signed_in
    make_audiobook(page, live)
    for width in (1440, 700):
        page.set_viewport_size({"width": width, "height": 900})
        sheet = font_size(page, ".sheet")
        page.get_by_role("button", name="Focus listening").click()
        assert sheet < font_size(page, ".focus-stage .cur") <= 1.25 * sheet, width
        assert font_size(page, ".focus-stage .prev") <= sheet, width
        page.keyboard.press("Escape")
    page.set_viewport_size({"width": 1280, "height": 720})


def test_every_key_on_the_listen_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    sentences = order(page)
    nobody_focused(page)
    # Space plays and pauses, and the page does not scroll
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press(" ")
    page.wait_for_function("() => document.getElementById('audio').paused")
    assert page.evaluate("() => window.scrollY") == 0
    expect(page.locator("#back-to-reading")).to_be_hidden()  # Space is no scroll by hand
    # the arrows move by sentence
    page.locator(f"#{sentences[2]}").click()
    page.get_by_role("button", name="Pause").click()
    nobody_focused(page)
    page.keyboard.press("ArrowRight")
    expect(page.locator("#text .s.now")).to_have_id(sentences[3])
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#text .s.now")).to_have_id(sentences[2])
    assert paused(page)  # a move while paused does not start the voice
    # Shift with them by chapter
    page.keyboard.press("Shift+ArrowRight")
    expect(page.locator("#now")).to_contain_text("Chapter 2 of 2")
    expect(page.locator("#message")).to_contain_text("Chapter 2 of 2")
    assert highlighted(page) == first_of(page, 1)
    page.keyboard.press("Shift+ArrowLeft")
    expect(page.locator("#now")).to_contain_text("Chapter 1 of 2")
    expect(page.locator("#text .s.now")).to_have_id(first_of(page, 0))
    # minus and plus step the speed, and say it
    speed = page.get_by_label("Speed")
    page.keyboard.press("+")
    expect(speed).to_have_value("1.25")
    expect(page.locator("#message")).to_have_text("Speed 1.25\u00d7")
    page.keyboard.press("=")  # the + key without Shift
    expect(speed).to_have_value("1.5")
    page.keyboard.press("-")
    page.keyboard.press("-")
    page.keyboard.press("-")
    expect(speed).to_have_value("0.75")
    page.keyboard.press("-")  # the slowest stays
    expect(speed).to_have_value("0.75")
    assert page.locator("#audio").evaluate("a => a.playbackRate") == 0.75
    # P hides and shows the side panel
    toggle = page.locator("#panel-toggle")
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#context")).to_be_hidden()
    page.keyboard.press("P")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    # in Focus too, and F again leaves it
    page.keyboard.press("F")
    expect(page.locator("#focus-view")).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#text .s.now")).to_have_id(sentences[1])
    assert words(page, "#focus-now") == words(page, f"#{sentences[1]}")
    page.keyboard.press("p")  # no panel in Focus
    expect(page.locator("#context")).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_hidden()
    expect(page.locator("#context")).to_be_visible()
    # M sets a marker on the sentence being read and removes it again (#474)
    marker = page.locator("#marker")
    page.keyboard.press("m")
    expect(marker).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("M")
    expect(marker).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#message")).to_have_text("Marker removed.")


def test_the_keys_stay_out_of_the_way(signed_in: Page, live: Live) -> None:
    """No key acts while the person types, with ⌘, Ctrl or Alt held, or while the sheet is
    open; Space and the arrows on a control do what the control does."""
    page = signed_in
    make_audiobook(page, live)
    speed = page.get_by_label("Speed")
    toggle = page.locator("#panel-toggle")
    # the speed select is typed into: letters, minus and plus choose nothing here
    speed.focus()
    for key in ("f", "p", "-", "+", "?"):
        page.keyboard.press(key)
    assert not focusing(page)
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(speed).to_have_value("1")
    expect(page.locator("#keys")).not_to_have_attribute("open", "")
    # held Cmd, Ctrl or Alt: the browser's or the system's own. No chord here goes back in
    # the history on any system: Cmd+Left is Back on macOS and Alt+Left on Linux and Windows
    # (#499); with no page ahead, Cmd+Right and Alt+Right do nothing
    nobody_focused(page)
    before = highlighted(page)
    listen = page.url
    chords = ("Control+f", "Meta+f", "Alt+f", "Control+p", "Alt+ArrowRight", "Meta+ArrowRight")
    for key in (*chords, "Control+ArrowLeft"):
        page.keyboard.press(key)
        expect(page).to_have_url(listen)
    assert not focusing(page)
    expect(toggle).to_have_attribute("aria-expanded", "true")
    assert highlighted(page) == before
    assert paused(page)
    # Space on a control does what the control does: the switch switches, nothing plays
    follow = page.locator("#follow")
    follow.focus()
    page.keyboard.press(" ")
    expect(follow).not_to_be_checked()
    assert paused(page)
    page.keyboard.press(" ")
    expect(follow).to_be_checked()
    # the arrows on a button are the button's: they move nothing
    page.get_by_role("button", name="Play").focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Shift+ArrowRight")
    assert highlighted(page) == before
    expect(page.locator("#now")).to_contain_text("Chapter 1 of 2")
    # Space on a button presses that button once; the arrows on the timeline move it
    play = page.get_by_role("button", name="Play")
    play.focus()
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.get_by_role("button", name="Pause").click()
    timeline = page.get_by_role("slider", name="Position in the audiobook")
    timeline.focus()
    page.keyboard.press("ArrowRight")  # 5 s on, not a sentence
    page.wait_for_function("() => document.getElementById('timeline').value === '5'")
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")
    expect(page.locator("#text .s.now")).to_have_id(chunk_at(page, 5))
    # the panel's tabs keep their arrows
    page.locator("#tab-outline").focus()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#tab-changes")).to_be_focused()
    # while the sheet is open, the page's keys wait
    page.keyboard.press("?")
    expect(page.locator("#keys")).to_be_visible()
    page.keyboard.press("f")
    assert not focusing(page)
    page.keyboard.press("Escape")
    expect(page.locator("#keys")).to_be_hidden()
    assert not focusing(page)
    # the library's search (#416) takes every letter, ? included
    page.goto(live.url + "/")
    search = page.get_by_role("searchbox")
    search.click()
    page.keyboard.type("f p?-")
    expect(search).to_have_value("f p?-")
    expect(page.locator("#keys")).to_be_hidden()


def test_a_text_field_takes_every_letter(signed_in: Page, live: Live) -> None:
    """The library's pasted text (and its search, an input like it, #416): ? is typed."""
    page = signed_in
    page.goto(live.url + "/")
    page.get_by_text("Or paste text").click()
    field = page.get_by_label("Text to open")
    field.click()
    page.keyboard.type("f p?-")
    expect(field).to_have_value("f p?-")
    expect(page.locator("#keys")).to_be_hidden()


def test_the_shortcuts_sheet_opens_on_every_page_and_gives_the_focus_back(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.goto(live.url + "/settings")
    sheet = page.get_by_role("dialog", name="Keyboard shortcuts")
    nobody_focused(page)
    page.keyboard.press("?")
    expect(sheet).to_be_visible()
    expect(page.locator("#keys-close")).to_be_focused()
    expect(sheet).to_contain_text("Play or pause")
    expect(sheet).to_contain_text("Previous / next chapter")
    for later in ("Note", "Quote", "Card"):  # with the study layer (#397)
        expect(sheet).not_to_contain_text(later)
    check_axe(page, "the shortcuts sheet")
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    # from the rail, by keyboard; Close gives the focus back to the item
    opener = page.get_by_role("button", name="Keyboard shortcuts")
    opener.focus()
    page.keyboard.press("Enter")
    expect(sheet).to_be_visible()
    page.keyboard.press("Enter")  # on Close
    expect(sheet).to_be_hidden()
    expect(opener).to_be_focused()
    opener.click()
    page.keyboard.press("Escape")
    if click_focuses(page):  # in Safari the click left the focus where it was (#498)
        expect(opener).to_be_focused()
    # German, dark included
    page.goto(f"{live.url}/language?language=de&back=/settings")
    page.get_by_role("button", name="Tastenkürzel").click()
    german = page.get_by_role("dialog", name="Tastenkürzel")
    expect(german).to_contain_text("Abspielen oder Pause")
    expect(german).to_contain_text("Leertaste")
    check_axe(page, "de: the shortcuts sheet")
    page.goto(f"{live.url}/language?language=en&back=/settings")


def test_the_sheet_and_focus_buttons_wait_for_their_scripts(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.goto(live.url + "/privacy")
    release = reload_holding_back_app_js(page, live)
    opener = page.locator("#keys-open")
    expect(opener).to_be_attached()
    expect(opener).to_be_disabled()
    expect(page.locator("#keys-close")).to_be_disabled()
    release()
    expect(opener).to_be_enabled()
    expect(page.locator("#keys-close")).to_be_enabled()


def test_focus_closes_the_panel_over_the_page_first(signed_in: Page, live: Live) -> None:
    """Below 1280 px the open panel covers the page: Focus closes it, so that the focus,
    back on the Focus button, is under nothing."""
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1024, "height": 768})
    page.locator("#panel-toggle").click()
    expect(page.locator("#tab-outline")).to_be_focused()
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_focused()
    check_axe(page, "focus listening at 1024 px")
    page.keyboard.press("Escape")
    expect(page.locator("#context")).to_be_hidden()
    expect(page.locator("#panel-toggle")).to_have_attribute("aria-expanded", "false")
    expect(page.get_by_role("button", name="Focus listening")).to_be_focused()
    assert uncovered(page)
    page.set_viewport_size({"width": 1280, "height": 720})


def test_leaving_focus_brings_the_sentence_into_view(signed_in: Page, live: Live) -> None:
    """While Focus is shown the page is short and its scroll is gone; leaving it scrolls the
    sheet back to the sentence being read (Scroll with the reading is on)."""
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1280, "height": 420})
    last = order(page)[-1]
    page.locator(f"#{last}").click()
    page.get_by_role("button", name="Pause").click()
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_focused()
    page.evaluate("() => window.scrollTo(0, 0)")
    page.keyboard.press("Escape")
    expect(page.locator(f"#{last}")).to_be_in_viewport()
    page.set_viewport_size({"width": 1280, "height": 720})


# --- round 1 of the review of #451 -------------------------------------------------------


def test_esc_leaves_focus_from_the_speed_list(signed_in: Page, live: Live) -> None:
    """S1: Esc leaves Focus wherever the focus is in it, the speed list included, though the
    list takes every other key."""
    page = signed_in
    make_audiobook(page, live)
    nobody_focused(page)
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_focused()
    page.get_by_label("Speed").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#focus-view")).to_be_hidden()
    assert not focusing(page)
    expect(page.get_by_role("button", name="Focus listening")).to_be_focused()


def test_a_held_key_acts_once(signed_in: Page, live: Live) -> None:
    """N1: a key held down repeats; F, P and Space switch once all the same (? opens the
    sheet, whose being open stops the repeats). An even count of presses: toggled by each
    repeat, they would come back to where they began."""
    page = signed_in
    make_audiobook(page, live)
    nobody_focused(page)
    for _ in range(4):  # held: one press and three repeats
        page.keyboard.down("f")
    page.keyboard.up("f")
    assert focusing(page)
    page.keyboard.press("Escape")
    nobody_focused(page)
    toggle = page.locator("#panel-toggle")
    for _ in range(4):  # held: one press and three repeats
        page.keyboard.down("p")
    page.keyboard.up("p")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    nobody_focused(page)
    for _ in range(4):  # held: one press and three repeats
        page.keyboard.down(" ")
    page.keyboard.up(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_timeout(300)
    assert not paused(page)
    assert page.evaluate("() => window.scrollY") == 0  # a held Space scrolls nothing either
    for _ in range(4):  # held: one press and three repeats
        page.keyboard.down("?")
    page.keyboard.up("?")
    expect(page.locator("#keys")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#keys")).to_be_hidden()


def test_with_the_keys_switched_off_only_esc_and_the_rail_item_are_left(
    signed_in: Page, live: Live
) -> None:
    """S3: switched off in Settings, F, P, ?, minus, plus, Space and the arrows do nothing and
    no key is offered; Esc still leaves Focus entered by its button, and the rail's item still
    opens the sheet."""
    page = signed_in
    document = make_audiobook(page, live)
    listen = f"/documents/{document}/listen"
    page.goto(f"{live.url}/appearance?keys=off&back={listen}")
    page.wait_for_url(live.url + listen)
    expect(page.locator("html")).to_have_attribute("data-keys", "off")
    for offered in ("#focus-on", "#panel-toggle"):
        expect(page.locator(offered)).not_to_have_attribute("aria-keyshortcuts", re.compile("."))
    expect(page.locator("#keys-open kbd")).to_have_count(0)
    expect(page.locator(".focus-foot")).to_have_count(0)
    toggle = page.locator("#panel-toggle")
    speed = page.get_by_label("Speed")
    before = highlighted(page)
    nobody_focused(page)
    for key in ("f", "F", "p", "?", "-", "+", "=", " ", "ArrowRight", "Shift+ArrowRight"):
        page.keyboard.press(key)
    page.wait_for_timeout(200)
    assert not focusing(page)
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#keys")).to_be_hidden()
    expect(speed).to_have_value("1")
    assert paused(page)
    assert highlighted(page) == before
    expect(page.locator("#now")).to_contain_text("Chapter 1 of 2")
    page.get_by_role("button", name="Focus listening").click()
    expect(page.locator("#focus-view")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#focus-view")).to_be_hidden()
    expect(page.get_by_role("button", name="Focus listening")).to_be_focused()
    page.get_by_role("button", name="Keyboard shortcuts").click()
    expect(page.locator("#keys")).to_be_visible()
    expect(page.locator("#keys")).to_contain_text("Settings can switch these keys off")
    check_axe(page, "shortcuts sheet, keys off")
    page.keyboard.press("Escape")
    expect(page.locator("#keys")).to_be_hidden()
    page.goto(f"{live.url}/appearance?keys=on&back={listen}")
    expect(page.locator("html")).not_to_have_attribute("data-keys", "off")


def test_the_stage_shows_a_cut_as_the_sheet_does(signed_in: Page, live: Live) -> None:
    """S4 (a): the sentence with a cut on the stage keeps the cut struck through and tells
    screen readers it is not read."""
    page = signed_in
    make_audiobook(page, live)
    sentence = chunk_id(page, "Things happen")
    page.locator(f"#{sentence}").click()
    page.get_by_role("button", name="Pause").click()
    assert highlighted(page) == sentence
    nobody_focused(page)
    page.keyboard.press("f")
    cut = page.locator("#focus-now s.cut")
    expect(cut).to_have_count(1)
    expect(cut).to_have_text("(Smith, 2020)")
    expect(page.locator("#focus-now")).to_contain_text("(not read)")
    assert words(page, "#focus-now") == words(page, f"#{sentence}")


def test_the_stage_reads_a_spoken_notice_only(signed_in: Page, live: Live, tmp_path: Path) -> None:
    """S4 (b): a skipped figure's notice on the stage is its spoken words only, without the
    icon or the caption found in the file."""
    page = signed_in
    pdf = make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Some text before the figure.", 72, 100, size=11),
            Rect(72, 120, 300, 300),
            Text("Figure 1: A grey box.", 72, 320, size=10),
            Text("Text after it.", 72, 350, size=11),
        ]
    )
    listen_to(page, live, tmp_path / "figure.pdf", pdf)
    notice = page.locator(".notice")
    notice.click()
    page.get_by_role("button", name="Pause").click()
    expect(notice).to_have_attribute("aria-current", "true")
    nobody_focused(page)
    page.keyboard.press("f")
    expect(page.locator("#focus-now")).to_have_text("Spoken notice: Figure 1 is skipped.")
    expect(page.locator("#focus-now svg")).to_have_count(0)


def test_focus_and_scrolling_by_hand(signed_in: Page, live: Live) -> None:
    """S4 (c), (d): a wheel in Focus offers no Back to the reading; after scrolling away,
    Focus and Esc bring the reading back, hide the button and follow the reading again."""
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1280, "height": 420})
    back = page.get_by_role("button", name="Back to the reading")
    current = highlighted(page) or order(page)[0]
    page.mouse.move(400, 200)
    page.mouse.wheel(0, 2000)
    expect(back).to_be_visible()
    expect(page.locator(f"#{current}")).not_to_be_in_viewport()
    nobody_focused(page)
    page.keyboard.press("f")
    expect(back).to_be_hidden()
    page.mouse.move(400, 200)
    page.mouse.wheel(0, 300)  # (d) in Focus the wheel is no scroll away from the reading
    page.wait_for_timeout(200)
    expect(back).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(f"#{current}")).to_be_in_viewport()  # (c)
    expect(back).to_be_hidden()
    page.mouse.wheel(0, 300)  # following again: a wheel away offers the way back
    expect(back).to_be_visible()
    page.set_viewport_size({"width": 1280, "height": 720})


def test_plus_at_the_fastest_speed_stays_there(signed_in: Page, live: Live) -> None:
    """S4 (e)."""
    page = signed_in
    make_audiobook(page, live)
    speed = page.get_by_label("Speed")
    speed.select_option("2")
    nobody_focused(page)
    page.keyboard.press("+")
    expect(speed).to_have_value("2")
    assert page.locator("#audio").evaluate("a => a.playbackRate") == 2


def test_after_p_closes_the_panel_space_and_the_arrows_act_on_the_player(
    signed_in: Page, live: Live
) -> None:
    """#461: P leaves the focus where it was, so Space plays and the arrows move by sentence
    after it, as before it; the panel's own buttons still give the focus to the toggle."""
    page = signed_in
    make_audiobook(page, live)
    sentences = order(page)
    toggle = page.locator("#panel-toggle")
    nobody_focused(page)
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).not_to_be_focused()
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    page.keyboard.press(" ")
    page.wait_for_function("() => document.getElementById('audio').paused")
    nobody_focused(page)
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    at = sentences.index(highlighted(page))
    page.keyboard.press("ArrowRight")
    expect(page.locator("#text .s.now")).to_have_id(sentences[at + 1])
    expect(toggle).to_have_attribute("aria-expanded", "false")
    # the toggle itself still keeps the focus on it (#444)
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    toggle.click()
    if click_focuses(page):  # in Safari the click gives the toggle no focus (#498)
        expect(toggle).to_be_focused()
    toggle.click()
    page.locator("#panel-close").click()
    expect(toggle).to_be_focused()  # the Close button gives it, in every browser (#498)


def narrow(page: Page) -> None:
    page.set_viewport_size({"width": 1024, "height": 768})
    # the width's change event comes with a frame; a key before it would race it
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")


def test_p_over_the_page_gives_the_focus_back_where_it_was(signed_in: Page, live: Live) -> None:
    """#461, #489 review S2: below 1280 px the panel opens over the page and takes the focus;
    P closing it gives the focus back to the page, not to the toggle, so Space then plays
    instead of opening the panel again, and the arrows move by sentence."""
    page = signed_in
    make_audiobook(page, live)
    sentences = order(page)
    narrow(page)
    toggle = page.locator("#panel-toggle")
    nobody_focused(page)
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("tab", name="Chapters")).to_be_focused()
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).not_to_be_focused()
    assert not page.evaluate(
        "() => document.getElementById('context').contains(document.activeElement)"
    )
    page.keyboard.press(" ")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    page.keyboard.press(" ")
    page.wait_for_function("() => document.getElementById('audio').paused")
    at = sentences.index(highlighted(page))
    page.keyboard.press("ArrowRight")
    expect(page.locator("#text .s.now")).to_have_id(sentences[at + 1])
    expect(toggle).to_have_attribute("aria-expanded", "false")
    page.set_viewport_size({"width": 1280, "height": 720})


def test_p_over_the_page_gives_the_focus_back_to_the_control_it_left(
    signed_in: Page, live: Live
) -> None:
    """#489 review S2: a control focused when P opened the panel has the focus again when P
    closes it; the close button and Esc still give it to the toggle (#444). (The panel
    covers the toggle here; the wide test above presses it.)"""
    page = signed_in
    make_audiobook(page, live)
    narrow(page)
    toggle = page.locator("#panel-toggle")
    control = page.locator("#next-sentence")
    control.focus()
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("p")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(control).to_be_focused()
    for close in ("button", "Escape"):
        control.focus()
        page.keyboard.press("p")
        expect(toggle).to_have_attribute("aria-expanded", "true")
        if close == "button":
            page.locator("#panel-close").click()
        else:
            page.keyboard.press("Escape")
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(toggle).to_be_focused()
    page.set_viewport_size({"width": 1280, "height": 720})


LONG = (
    "The long-term study of how schools teach sustainable development shows that teachers "
    "who regularly take part in further training and who share what they learn with their "
    "colleagues bring the new material into their own lessons far more often, with more "
    "confidence, and over many more years than those who do not."
)


def test_a_long_sentence_fits_the_stage_without_scrolling(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """Colin's case (#471): a long sentence in Focus at 1512 x 900 fits the window, in light
    and dark and with the German interface, and the stage's bar spans it."""
    page = signed_in
    lines = textwrap.wrap(LONG, 80)
    pdf = make_pdf(
        [Text("Introduction", 72, 80, size=14)]
        + [Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(lines)]
        + [Text("A short one after it.", 72, 120 + 14 * len(lines), size=11)]
    )
    listen_to(page, live, tmp_path / "long.pdf", pdf)
    document = page.url.split("/documents/")[1].split("/")[0]
    page.set_viewport_size({"width": 1512, "height": 900})
    sentence = chunk_id(page, "long-term study")
    page.locator(f"#{sentence}").click()
    page.get_by_role("button", name="Pause").click()
    page.goto(f"{live.url}/language?language=de&back=/documents/{document}/listen")
    page.locator(f"#{sentence}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.locator("#play").click()
    page.wait_for_function("() => document.getElementById('audio').paused")
    page.get_by_role("button", name="Fokus-Hören").click()
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        assert words(page, "#focus-now") == words(page, f"#{sentence}")
        assert page.evaluate(
            "() => document.scrollingElement.scrollHeight <= window.innerHeight"
        ), scheme
        assert_beside(page, "#focus-bar", "#focus-now")
        assert look(page, "#focus-now")["background"] not in ("rgba(0, 0, 0, 0)", "")
        check_axe(page, f"de: focus listening, a long sentence, {scheme}")
    page.emulate_media(color_scheme="light")
    page.goto(f"{live.url}/language?language=en&back=/documents/{document}/listen")
    page.set_viewport_size({"width": 1280, "height": 720})
