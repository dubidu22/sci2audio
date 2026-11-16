"""Focus listening, the keys and the keyboard shortcuts sheet (#394, WR-10): F and Esc, every
key and every case in which the keys stay out of the way, the sheet on every page, and axe
in light, dark and German in Focus and on the sheet."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect
from test_flow import reload_holding_back_app_js
from test_listen import uncovered
from test_player import highlighted, make_audiobook, paused

from conftest import Live, check_axe

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


def test_the_voice_goes_on_and_the_stage_follows_it_with_the_sweep(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    page.get_by_role("button", name="Focus listening").click()
    assert not paused(page)  # no page load: the voice goes on
    page.wait_for_function(
        "() => document.getElementById('focus-now').getAnimations()[0]?.playState === 'running'"
    )
    first = highlighted(page)
    page.wait_for_function(
        f"() => document.querySelector('#text .s.now')?.id !== '{first}'", timeout=20_000
    )
    now = highlighted(page)
    assert words(page, "#focus-now") == words(page, f"#{now}")
    assert words(page, "#focus-prev") == words(page, f"#{first}")
    # both sweeps stand where the voice stands, at its speed
    page.get_by_label("Speed").select_option("1.5")
    page.wait_for_function(
        "() => document.getElementById('focus-now').getAnimations()[0]?.playbackRate === 1.5"
    )
    page.get_by_role("button", name="Pause").click()
    page.wait_for_function(
        "() => document.getElementById('focus-now').getAnimations()[0]?.playState === 'paused'"
    )
    times = page.evaluate(
        """() => [document.querySelector('#text .s.now').getAnimations()[0].currentTime,
                  document.getElementById('focus-now').getAnimations()[0].currentTime]"""
    )
    assert abs(times[0] - times[1]) < 50, times
    # leaving ends the stage's sweep and brings the reading back into view
    page.keyboard.press("Escape")
    assert page.locator("#focus-now").evaluate("e => e.getAnimations().length") == 0
    expect(page.locator(f"#{now}")).to_be_in_viewport()


def test_under_reduced_motion_focus_highlights_the_whole_sentence(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.emulate_media(reduced_motion="reduce")
    make_audiobook(page, live)
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_visible()
    page.wait_for_timeout(300)
    assert page.locator("#focus-now").evaluate("e => e.getAnimations().length") == 0
    assert page.locator("#focus-now").evaluate("e => getComputedStyle(e).backgroundSize") == (
        "100% 100%"
    )
    assert page.evaluate("() => document.getAnimations().length") == 0


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
    # held Cmd, Ctrl or Alt: the browser's or the system's own
    nobody_focused(page)
    before = highlighted(page)
    for key in ("Control+f", "Meta+f", "Alt+f", "Control+p", "Alt+ArrowRight", "Meta+ArrowLeft"):
        page.keyboard.press(key)
    assert not focusing(page)
    expect(toggle).to_have_attribute("aria-expanded", "true")
    assert highlighted(page) == before
    assert paused(page)
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
