"""The Listen page of the Working Reader in Chromium (#392, #393): the sentence being read
is marked plainly, without motion (D-709, #452), with a pale fill and a bar beside it
(D-724), and a heard one keeps no tint (D-720); a sentence
is told to screen readers only when the person switched that on; the context panel beside
the desk and over it, the timeline, the buttons drawn disabled until the script wires them,
and a book of 1,000 pages.

The fake voice speaks 0.1 s per character (`test_player.PER_CHARACTER`), so the sentences
last long enough to be seen.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from long_book import long_book
from playwright.sync_api import Page, Route, expect
from test_player import choose_speed, chunk_id, highlighted, make_audiobook, paused

from conftest import Live, check_axe, tab_key
from sci2audio.core.export import to_data
from sci2audio.output.readalong import to_json
from sci2audio.web.player import recorded_folder

NOW = "#text .s.now"


def look(page: Page, selector: str) -> dict[str, Any]:
    """How an element is drawn: its animations (and the page's), its background and lines."""
    return dict(
        page.evaluate(
            """(selector) => {
                const e = document.querySelector(selector);
                if (!e) return {id: ''};
                const style = getComputedStyle(e);
                return {id: e.id, animations: e.getAnimations().length,
                        all: document.getAnimations().length,
                        background: style.backgroundColor, image: style.backgroundImage,
                        line: style.textDecorationLine};
            }""",
            selector,
        )
    )


def marked_plainly(page: Page, selector: str) -> dict[str, Any]:
    """The mark of the sentence being read (D-709): a colour of its own, nothing moving,
    no underline, no growing gradient."""
    now = look(page, selector)
    assert now["id"], now
    assert now["animations"] == 0, now
    assert now["all"] == 0, now
    assert now["line"] == "none", now
    assert now["image"] == "none", now
    assert now["background"] not in ("", "rgba(0, 0, 0, 0)", "transparent"), now
    return now


def change_theme(page: Page, scheme: Literal["light", "dark"]) -> None:
    """Switch the colour scheme and let the transitions it starts end (#500). Firefox and
    WebKit on macOS run the switches' 0.2 s colour transition on a theme change, which
    `document.getAnimations()` counts; Chromium does not start it. Only CSS transitions are
    awaited, so a keyframe animation still fails `marked_plainly`'s `all == 0` (D-709)."""
    page.emulate_media(color_scheme=scheme)
    page.evaluate(
        """() => new Promise((done) => requestAnimationFrame(() => done(Promise.allSettled(
            document.getAnimations().filter((a) => a instanceof CSSTransition)
                .map((a) => a.finished)))))"""
    )


def book_time(page: Page) -> float:
    return float(
        page.evaluate(
            """() => {
                const data = JSON.parse(document.getElementById('player-data').textContent);
                const audio = document.getElementById('audio');
                const name = decodeURIComponent(audio.getAttribute('src').split('/').pop());
                const c = data.chapters.find((c) => c.file === name) || data.chapters[0];
                return audio.currentTime + c.offset;
            }"""
        )
    )


def stretch_of(page: Page, element: str) -> tuple[float, float]:
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    times = [(start, end) for start, end, _c, e in data["chunks"] if e == element]
    return times[0][0], times[-1][1]


def bar_beside(page: Page, bar: str, element: str) -> dict[str, float]:
    """The bar (D-724) against the element's lines: where its top and bottom are off from the
    lines' (in px), and its left edge against the text column and the box it is in."""
    found: dict[str, float] = page.evaluate(
        """([bar, element]) => {
            const b = document.querySelector(bar);
            const e = document.querySelector(element);
            if (!b || !e || b.hidden) return {shown: 0};
            const box = b.getBoundingClientRect();
            const lines = [...e.getClientRects()].filter((r) => r.width && r.height);
            const style = getComputedStyle(b);
            return {
                shown: 1,
                top: box.top - Math.min(...lines.map((r) => r.top)),
                bottom: box.bottom - Math.max(...lines.map((r) => r.bottom)),
                left: box.left,
                lines: Math.min(...lines.map((r) => r.left)),
                width: parseFloat(style.borderLeftWidth),
                colour: style.borderLeftColor,
                animations: b.getAnimations().length,
                transition: parseFloat(style.transitionDuration) || 0,
                outer: b.offsetParent.getBoundingClientRect().left,
            };
        }""",
        [bar, element],
    )
    return found


def assert_beside(page: Page, bar: str, element: str) -> dict[str, float]:
    """The bar is shown, spans exactly the element's lines and stands left of them: on the
    sheet inside it, in its left padding; in Focus inside the window."""
    page.wait_for_timeout(50)  # placed in the next frame
    at = bar_beside(page, bar, element)
    assert at["shown"], at
    assert abs(at["top"]) <= 1, at
    assert abs(at["bottom"]) <= 1, at
    assert at["left"] < at["lines"], at
    assert at["left"] >= (at["outer"] if bar == "#now-bar" else 0), at
    assert at["width"] == 3, at
    assert at["animations"] == 0, at
    assert at["transition"] == 0, at
    return at


def test_the_sentence_being_read_is_marked_plainly_and_a_heard_one_has_no_tint(
    signed_in: Page, live: Live
) -> None:
    """D-709 (#452), D-720, D-724: the sentence being read is marked at once, without motion
    or underline, with a pale fill and a bar beside its lines, while the voice reads, at
    another speed and paused; a heard one has no tint left, nor one under the pointer."""
    page = signed_in
    make_audiobook(page, live)
    expect(page.locator("#now-bar")).to_be_hidden()  # nothing read yet
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    first = marked_plainly(page, NOW)
    assert_beside(page, "#now-bar", NOW)
    page.wait_for_timeout(400)  # well into the sentence: still the same plain mark
    assert marked_plainly(page, NOW) == first
    # the next sentence takes the mark and the bar over; the one read keeps nothing
    page.wait_for_function(
        f"() => document.querySelector('{NOW}')?.id !== '{first['id']}'", timeout=20_000
    )
    heard = look(page, f"#{first['id']}")
    assert heard["background"] in ("rgba(0, 0, 0, 0)", "transparent"), heard
    expect(page.locator(f"#{first['id']}")).not_to_have_class(re.compile(r"\bdone\b"))
    assert heard["line"] == "none", heard
    marked_plainly(page, NOW)
    assert_beside(page, "#now-bar", NOW)
    choose_speed(page, "1.5\u00d7")
    page.wait_for_function("() => document.getElementById('audio').playbackRate === 1.5")
    marked_plainly(page, NOW)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_function("() => document.getElementById('audio').paused")
    marked_plainly(page, NOW)
    assert_beside(page, "#now-bar", NOW)
    # under the pointer: no tint either
    page.locator(f"#{first['id']}").hover()
    assert look(page, f"#{first['id']}")["background"] in ("rgba(0, 0, 0, 0)", "transparent")
    check_axe(page, "listen, reading")
    change_theme(page, "dark")
    marked_plainly(page, NOW)
    assert_beside(page, "#now-bar", NOW)
    check_axe(page, "listen, reading, dark")
    page.emulate_media(color_scheme="light")


def test_the_bar_follows_the_sentence_when_the_text_reflows(signed_in: Page, live: Live) -> None:
    """D-724: the bar is placed again when the window's width changes the sentence's lines,
    stays inside the sheet on a phone, and stays visible in forced colours."""
    page = signed_in
    make_audiobook(page, live)
    target = chunk_id(page, "We measured it twice.")
    page.locator(f"#{target}").click()
    page.get_by_role("button", name="Pause").click()
    page.wait_for_function("() => document.getElementById('audio').paused")
    wide = assert_beside(page, "#now-bar", NOW)
    page.set_viewport_size({"width": 700, "height": 720})
    page.wait_for_timeout(200)
    narrow = assert_beside(page, "#now-bar", NOW)
    assert narrow["left"] != wide["left"], (wide, narrow)
    page.set_viewport_size({"width": 1280, "height": 720})
    page.emulate_media(forced_colors="active")
    bar = assert_beside(page, "#now-bar", NOW)
    assert bar["colour"] not in ("rgba(0, 0, 0, 0)", "transparent"), bar
    page.emulate_media(forced_colors="none")


def test_under_reduced_motion_the_mark_is_the_same(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    moving = marked_plainly(page, NOW)
    page.get_by_role("button", name="Pause").click()
    page.emulate_media(reduced_motion="reduce")
    still = marked_plainly(page, NOW)
    assert still["background"] == moving["background"]
    page.emulate_media(reduced_motion="no-preference")


def watch_reading(page: Page) -> None:
    page.locator("#reading").evaluate(
        """region => {
            window.read = [];
            new MutationObserver(() => window.read.push(region.textContent))
                .observe(region, {childList: true, characterData: true, subtree: true});
        }"""
    )


def test_each_sentence_is_announced_only_when_switched_on(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    # off by default: no region speaks the reading (D-300); test_player watches #message
    expect(page.locator("#reading")).to_have_count(0)
    page.goto(f"{live.url}/appearance?announce=on&back=/documents/{document}/listen")
    page.wait_for_url(f"{live.url}/documents/{document}/listen")
    region = page.locator("#reading")
    expect(region).to_have_attribute("aria-live", "polite")
    watch_reading(page)
    page.get_by_role("button", name="Play").click()
    ids: list[str] = []
    while len(ids) < 3:
        last = json.dumps(ids[-1] if ids else "")
        page.wait_for_function(
            f"() => (document.querySelector('{NOW}')?.id ?? '') !== {last}", timeout=20_000
        )
        ids.append(highlighted(page))
    page.get_by_role("button", name="Pause").click()
    read = page.evaluate("() => window.read")
    texts = [page.locator(f"#{i}").evaluate("e => e.textContent.trim()") for i in ids]
    assert read[: len(texts)] == texts, (read, texts)  # once per sentence, its words
    count = len(read)
    page.wait_for_timeout(1500)  # paused: nothing more is said
    assert len(page.evaluate("() => window.read")) == count


def test_the_panel_beside_the_desk_and_over_it(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    panel = page.locator("#context")
    toggle = page.locator("#panel-toggle")
    # from 1280 px: beside the desk, hidden and shown by its button
    expect(panel).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    toggle.click()
    expect(panel).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_have_accessible_name("Show the side panel")
    toggle.click()
    expect(panel).to_be_visible()
    # the tabs: one tab stop, the arrow keys move between them
    page.locator("#tab-outline").focus()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#tab-changes")).to_be_focused()
    expect(page.locator("#tab-changes")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#panel-changes")).to_be_visible()
    expect(page.locator("#panel-outline")).to_be_hidden()
    expect(page.locator("#panel-changes")).to_contain_text("Citations")
    expect(page.locator("#panel-changes").get_by_role("link", name="Open Prepare")).to_be_visible()
    page.keyboard.press("End")
    expect(page.locator("#tab-markers")).to_be_focused()  # the third tab (#474)
    expect(page.locator("#tab-markers")).to_have_text("Markers (0)")
    expect(page.locator("#panel-markers")).to_be_visible()
    expect(page.locator("#markers-empty")).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#tab-outline")).to_be_focused()
    expect(page.locator("#panel-outline")).to_be_visible()
    check_axe(page, "listen, panel beside the desk")
    # below 1280 px: closed, then over the page; Esc closes it and gives the focus back
    page.set_viewport_size({"width": 1024, "height": 768})
    expect(panel).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    width = page.locator(".sheet").evaluate("e => e.getBoundingClientRect().width")
    toggle.click()
    expect(panel).to_be_visible()
    expect(page.locator("#tab-outline")).to_be_focused()
    assert page.locator(".sheet").evaluate("e => e.getBoundingClientRect().width") == width
    assert panel.evaluate("e => getComputedStyle(e).position") == "fixed"
    check_axe(page, "listen, panel over the page")
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(toggle).to_be_focused()
    toggle.click()
    page.locator("#panel-close").click()
    expect(panel).to_be_hidden()
    expect(toggle).to_be_focused()
    # where a click gives a button no focus, as in Safari, the Close button still gives the
    # focus to the toggle (#498): here the press leaves the focus nowhere first
    toggle.click()
    page.evaluate("() => document.activeElement.blur()")
    page.locator("#panel-close").dispatch_event("click")
    expect(panel).to_be_hidden()
    expect(toggle).to_be_focused()
    page.set_viewport_size({"width": 1280, "height": 720})


def uncovered(page: Page) -> bool:
    """True when nothing is drawn over the middle of the focused element."""
    return bool(
        page.evaluate(
            """() => {
                const e = document.activeElement;
                const r = e.getBoundingClientRect();
                e.scrollIntoView({ block: "center" });
                const s = e.getBoundingClientRect();
                const hit = document.elementFromPoint(s.left + s.width / 2, s.top + s.height / 2);
                return r.width > 0 && !!hit && (hit === e || e.contains(hit));
            }"""
        )
    )


def test_below_1280_px_the_focus_never_goes_under_the_panel(signed_in: Page, live: Live) -> None:
    """#444 (WCAG 2.4.11): the open panel closes when the focus leaves it, by Tab
    past its last control or Shift+Tab before its first, and the focus stays where it went."""
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1024, "height": 768})
    panel = page.locator("#context")
    toggle = page.locator("#panel-toggle")
    toggle.click()
    expect(panel).to_be_visible()
    page.locator("#follow").focus()
    expect(panel).to_be_visible()
    # WebKit, like Safari, leaves buttons out of plain Tab: tab_key() moves to every item (#497)
    page.keyboard.press(tab_key(page))  # past its last control
    expect(panel).to_be_hidden()
    expect(page.locator("#follow")).not_to_be_focused()
    assert uncovered(page)
    toggle.click()
    expect(page.locator("#tab-outline")).to_be_focused()
    page.keyboard.press(f"Shift+{tab_key(page)}")  # before its first: the toggle it covered
    expect(panel).to_be_hidden()
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    assert uncovered(page)
    page.set_viewport_size({"width": 1280, "height": 720})


def test_below_1280_px_a_click_on_text_inside_the_panel_leaves_it_open(
    signed_in: Page, live: Live
) -> None:
    """#447: a click on text inside the open panel sends the focus nowhere (no related
    target); the panel stays open, and only a move of the focus outside it closes it."""
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1024, "height": 768})
    panel = page.locator("#context")
    page.locator("#panel-toggle").click()
    expect(page.locator("#tab-outline")).to_be_focused()
    page.locator("#tab-changes").click()
    expect(page.locator("#tab-changes")).to_be_focused()
    page.locator("#panel-changes .chg-name").first.click()
    expect(page.locator("#tab-changes")).not_to_be_focused()
    expect(panel).to_be_visible()
    expect(page.locator("#panel-toggle")).to_have_attribute("aria-expanded", "true")
    page.keyboard.press(tab_key(page))  # from where the press left the focus: out of the panel
    if page.context.browser.browser_type.name == "webkit":  # type: ignore[union-attr]
        # WebKit starts Tab from the pressed text, the panel's last item, not from <main>,
        # which the press focused: the focus leaves the page for the browser's own bar and
        # nothing is covered. The next Tab comes back into the page and closes it (#502)
        expect(panel).to_be_visible()
        assert page.evaluate("() => document.activeElement === document.body")
        page.keyboard.press(tab_key(page))
    expect(panel).to_be_hidden()
    assert uncovered(page)
    page.locator("#panel-toggle").click()
    page.locator("#tab-outline").click()
    page.locator("#panel-outline .chapter-button").last.click()  # the press is not lost
    expect(panel).to_be_visible()
    expect(page.locator("#panel-outline .chapter-button").last).to_have_attribute(
        "aria-current", "true"
    )
    page.set_viewport_size({"width": 1280, "height": 720})


def test_below_1280_px_a_press_that_never_ends_does_not_hold_the_panel_open(
    signed_in: Page, live: Live
) -> None:
    """#451: a press inside the panel whose release never comes (a drag out of the
    window, a context menu, another window) ends with the next key, a context menu or the
    window losing the focus; the next move of the focus outside then closes the panel."""
    page = signed_in
    make_audiobook(page, live)
    page.set_viewport_size({"width": 1024, "height": 768})
    panel = page.locator("#context")
    toggle = page.locator("#panel-toggle")
    pressed = "e => e.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))"
    toggle.click()
    page.locator("#tab-outline").evaluate(pressed)  # down, and never up
    page.locator("#follow").focus()
    page.keyboard.press("Tab")  # the key ends the press: out of the panel
    expect(panel).to_be_hidden()
    expect(page.locator("#follow")).not_to_be_focused()
    assert uncovered(page)
    for ended in (
        "() => window.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true}))",
        "() => window.dispatchEvent(new Event('blur'))",
    ):
        toggle.click()
        expect(panel).to_be_visible()
        page.locator("#tab-outline").evaluate(pressed)
        page.evaluate(ended)
        page.get_by_role("button", name="Play").focus()  # no key: the focus moves by itself
        expect(panel).to_be_hidden()
        expect(toggle).to_have_attribute("aria-expanded", "false")
    page.set_viewport_size({"width": 1280, "height": 720})


def test_the_timeline_moves_the_reading_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    timeline = page.get_by_role("slider", name="Position in the audiobook")
    expect(timeline).to_have_attribute("aria-valuetext", re.compile(r"^0:00 of 0:\d\d$"))
    timeline.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.wait_for_function("() => document.getElementById('timeline').value === '10'")
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")
    assert paused(page)  # moving while paused does not start the voice
    assert abs(book_time(page) - 10) < 0.2, book_time(page)
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    expected = [e for start, _end, _c, e in data["chunks"] if start <= 10.0005][-1]
    assert highlighted(page) == expected
    expect(timeline).to_have_attribute("aria-valuetext", re.compile(r"^0:10 of 0:\d\d$"))
    expect(page.locator("#clock")).to_have_text(re.compile(r"^0:10 of 0:\d\d$"))
    expect(timeline).to_be_focused()


def test_a_jump_ahead_while_playing_leaves_no_tint(signed_in: Page, live: Live) -> None:
    """#444 (a): only a sentence the voice read through in order keeps the tint;
    one left by a jump of two or more sentences while playing does not."""
    page = signed_in
    make_audiobook(page, live)
    left = chunk_id(page, "Things happen")
    page.locator(f"#{left}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    expect(page.locator(NOW)).to_have_id(left)
    target = chunk_id(page, "We measured it twice.")
    assert target != left
    page.locator(f"#{target}").click()
    expect(page.locator(NOW)).to_have_id(target)
    page.wait_for_function("() => !document.getElementById('audio').paused")  # its chapter's file
    expect(page.locator(f"#{left}")).not_to_have_class(re.compile(r"\bdone\b"))
    expect(page.locator("#text .s.done")).to_have_count(0)


def test_a_timeline_move_saves_the_position_and_reaches_the_end(
    signed_in: Page, live: Live
) -> None:
    """#444 (b): a move on the timeline is saved like every move (#153);
    End reaches the book's end, which a 5 s step could not."""
    page = signed_in
    make_audiobook(page, live)
    timeline = page.get_by_role("slider", name="Position in the audiobook")
    timeline.focus()
    with page.expect_request(
        lambda request: request.url.endswith("/position") and request.method == "POST"
    ) as saved:
        page.keyboard.press("ArrowRight")
    assert json.loads(saved.value.post_data or "{}")["time"] == 5
    end = float(timeline.get_attribute("max") or 0)
    assert end % 5, end  # not a multiple of the old step
    with page.expect_request(
        lambda request: request.url.endswith("/position") and request.method == "POST"
    ) as saved:
        page.keyboard.press("End")
    assert json.loads(saved.value.post_data or "{}")["time"] == end
    assert float(timeline.input_value()) == end
    total = page.locator("#clock").inner_text().split(" of ")[1]
    expect(page.locator("#clock")).to_have_text(f"{total} of {total}")
    page.keyboard.press("Home")
    page.wait_for_function("() => document.getElementById('timeline').value === '0'")


def test_every_button_waits_for_the_script(signed_in: Page, live: Live) -> None:
    """Drawn disabled until player.js wires it (#350, #427): a press before is never lost."""
    page = signed_in
    make_audiobook(page, live)
    held: list[Route] = []
    page.route("**/static/player.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    page.wait_for_function("() => document.getElementById('dock') !== null")
    page.wait_for_function("() => document.readyState !== 'loading'")
    controls = (
        "#dock button:not([hidden]), #dock input, #context button, #panel-toggle, #focus-on, "
        "#focus-off"
    )
    states = page.evaluate(
        f"() => [...document.querySelectorAll('{controls}')].map(e => e.disabled)"
    )
    assert len(states) >= 10, states
    assert all(states), states
    assert held, "player.js was not requested"
    held[0].continue_()
    # the marker button stays disabled while no sentence is being read (#474)
    page.wait_for_function(
        f"() => [...document.querySelectorAll('{controls}')]"
        ".every(e => !e.disabled || e.id === 'marker')"
    )
    page.locator("#next-sentence").click()
    expect(page.locator("#marker")).to_be_enabled()
    page.unroute("**/static/player.js")


def test_a_book_of_a_thousand_pages_moves_one_sentence_at_a_time(
    signed_in: Page, live: Live
) -> None:
    """#392: a sentence step touches the old and the new sentence only, whatever the book's
    length (no timing: the count of changed elements)."""
    page = signed_in
    document = make_audiobook(page, live)
    stored = live.state.store.get(document)
    assert stored is not None
    work = stored.folder
    folder = recorded_folder(work, document)
    assert folder is not None
    record = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    book, readalong = long_book(m4b=record["files"]["m4b"])
    (work / "document.json").write_text(json.dumps(to_data(book)), encoding="utf-8")
    (folder / record["files"]["readalong"]).write_text(to_json(readalong), encoding="utf-8")
    record["files"]["mp3"] = []
    record["duration"] = readalong.duration
    record["chunks"] = {**record["chunks"], "total": len(readalong.chunks), "skipped": 0}
    (work / "audio.json").write_text(json.dumps(record), encoding="utf-8")
    page.goto(f"{live.url}/documents/{document}/listen", timeout=120_000)
    expect(page.locator("#text .s")).to_have_count(len(readalong.chunks), timeout=60_000)
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    start = int(highlighted(page).removeprefix("s"))
    page.locator("#text").evaluate(
        """text => {
            window.changed = [];
            new MutationObserver((all) => window.changed.push(new Set(all.map(m => m.target)).size))
                .observe(text, {attributes: true, childList: true, subtree: true});
        }"""
    )
    following = page.get_by_role("button", name="Next sentence")
    for _ in range(3):
        following.click()
        page.wait_for_function("() => window.changed.length > 0")
        page.wait_for_timeout(100)
        changed = page.evaluate(
            "() => { const c = window.changed; window.changed = []; return c; }"
        )
        assert sum(changed) <= 2, changed
    assert highlighted(page) == f"s{start + 3}"
