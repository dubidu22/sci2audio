"""The Listen page of the Working Reader in Chromium (#392, #393): the sweep follows the
voice and stands still under reduced motion, a sentence is told to screen readers only when
the person switched that on, the context panel beside the desk and over it, the timeline,
the buttons drawn disabled until the script wires them, and a book of 1,000 pages.

The fake voice speaks 0.1 s per character (`test_player.PER_CHARACTER`), so the sentences
last long enough to be seen.
"""

from __future__ import annotations

import json
import re
from typing import Any

from long_book import long_book
from playwright.sync_api import Page, Route, expect
from test_player import chunk_id, highlighted, make_audiobook, paused

from conftest import Live, check_axe
from sci2audio.core.export import to_data
from sci2audio.output.readalong import to_json
from sci2audio.web.player import recorded_folder

NOW = "#text .s.now"


def sweep(page: Page) -> dict[str, Any]:
    """The sentence being read and its animations."""
    return dict(
        page.evaluate(
            """() => {
                const e = document.querySelector('#text .s.now');
                if (!e) return {id: '', count: 0};
                const all = e.getAnimations();
                return {id: e.id, count: all.length, state: all[0]?.playState ?? '',
                        rate: all[0]?.playbackRate ?? 0, time: all[0]?.currentTime ?? 0,
                        size: getComputedStyle(e).backgroundSize};
            }"""
        )
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


def test_the_sweep_follows_the_voice_and_a_heard_sentence_keeps_its_tint(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    first = sweep(page)
    assert first["count"] == 1, first
    assert first["state"] == "running", first
    # the next sentence takes the sweep over; the one read keeps the pale tint
    page.wait_for_function(
        f"() => document.querySelector('{NOW}')?.id !== '{first['id']}'", timeout=20_000
    )
    expect(page.locator(f"#{first['id']}")).to_have_class(re.compile(r"\bdone\b"))
    assert page.locator(f"#{first['id']}").evaluate("e => e.getAnimations().length") == 0
    # the speed is the sweep's speed too
    page.get_by_label("Speed").select_option("1.5")
    page.wait_for_function(
        "() => document.querySelector('#text .s.now')?.getAnimations()[0]?.playbackRate === 1.5"
    )
    # paused, the sweep stands where the voice stands
    page.get_by_role("button", name="Pause").click()
    page.wait_for_function(
        "() => document.querySelector('#text .s.now')?.getAnimations()[0]?.playState === 'paused'"
    )
    now = sweep(page)
    start, _end = stretch_of(page, now["id"])
    expected = (book_time(page) - start) * 1000
    assert abs(now["time"] - expected) < 250, (now, expected)
    # a jump while paused: no tint for a sentence that was not heard through
    target = chunk_id(page, "We measured it twice.")
    page.locator(f"#{target}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    expect(page.locator(f"#{now['id']}")).not_to_have_class(re.compile(r"\bdone\b"))
    check_axe(page, "listen, sweeping")


def test_under_reduced_motion_the_whole_sentence_is_highlighted_at_once(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    page.emulate_media(reduced_motion="reduce")
    make_audiobook(page, live)
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('#text .s.now') !== null")
    page.wait_for_timeout(300)
    now = sweep(page)
    assert now["count"] == 0, now  # nothing moves
    assert now["size"] == "100% 100%", now
    animated = page.evaluate("() => document.getAnimations().map((a) => a.animationName ?? '')")
    assert animated == [], animated


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
    """#444 review S2 (WCAG 2.4.11): the open panel closes when the focus leaves it, by Tab
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
    page.keyboard.press("Tab")  # past its last control
    expect(panel).to_be_hidden()
    expect(page.locator("#follow")).not_to_be_focused()
    assert uncovered(page)
    toggle.click()
    expect(page.locator("#tab-outline")).to_be_focused()
    page.keyboard.press("Shift+Tab")  # before its first: the toggle it covered
    expect(panel).to_be_hidden()
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    assert uncovered(page)
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
    """#444 review S4 (a): only a sentence the voice read through in order keeps the tint;
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
    """#444 review S4 (b) and N1: a move on the timeline is saved like every move (#153);
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
    controls = "#dock button:not([hidden]), #dock input, #context button, #panel-toggle"
    states = page.evaluate(
        f"() => [...document.querySelectorAll('{controls}')].map(e => e.disabled)"
    )
    assert len(states) >= 10, states
    assert all(states), states
    assert held, "player.js was not requested"
    held[0].continue_()
    page.wait_for_function(
        f"() => [...document.querySelectorAll('{controls}')].every(e => !e.disabled)"
    )
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
