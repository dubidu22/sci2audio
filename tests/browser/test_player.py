"""The read-along player in Chromium (#78, OU-02; D-294 to D-303): the highlight follows
the voice, a click jumps, the buttons move by sentence and chapter, the page scrolls with
the reading until the person scrolls away, the keyboard reaches everything, nothing is
announced while it plays, and axe finds nothing in light or dark.

The fake voice speaks 0.1 s per character here, so the sentences last long enough to be
seen; ffmpeg encodes the MP3s for real.
"""

from __future__ import annotations

import re
from pathlib import Path

from pdf_maker import Rect, Text, make_pdf
from playwright.sync_api import Page, expect
from test_flow import open_paper

from conftest import Live, check_axe

PER_CHARACTER = 2400  # samples at 24 kHz: 0.1 s per character


def make_audiobook(page: Page, live: Live) -> str:
    """Open the paper, make its audiobook and open the player; returns the document id."""
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    document = open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(f"{live.url}/documents/{document}/listen")
    expect(page.get_by_role("heading", level=1)).to_have_text("Listen: paper.pdf")
    return document


def listen_to(page: Page, live: Live, path: Path, pdf: bytes) -> None:
    """Open this PDF, make its audiobook and open the player."""
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    path.write_bytes(pdf)
    page.set_input_files("#file", files=[path])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    page.get_by_role("button", name="Make the audiobook").click()
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(re.compile(r"/listen$"))


def highlighted(page: Page) -> str:
    return str(page.evaluate("() => document.querySelector('[aria-current=true]')?.id ?? ''"))


def chunk_id(page: Page, words: str) -> str:
    return str(page.locator(".s", has_text=words).first.get_attribute("id"))


def paused(page: Page) -> bool:
    return bool(page.evaluate("() => document.getElementById('audio').paused"))


def watch_status(page: Page) -> None:
    page.locator("#message").evaluate(
        """region => {
            window.said = [];
            new MutationObserver(() => window.said.push(region.textContent))
                .observe(region, {childList: true, characterData: true, subtree: true});
        }"""
    )


def test_the_highlight_follows_the_voice_into_the_next_chapter(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    expect(page.locator("#text")).to_contain_text("Things happen (Smith, 2020) and more.")
    expect(page.locator("#text")).not_to_contain_text("A book about things")  # not chosen
    expect(page.get_by_text("Not in this audiobook: References.")).to_be_visible()
    expect(page.get_by_text(re.compile("read by a synthetic voice"))).to_be_visible()
    expect(page.locator(".page-mark").first).to_have_text("Page 1")
    check_axe(page, "player, ready")

    watch_status(page)
    first = chunk_id(page, "Introduction")
    second = chunk_id(page, "Things happen")
    later = chunk_id(page, "We measured it twice.")
    page.get_by_role("button", name="Play").click()
    expect(page.get_by_role("button", name="Pause")).to_be_visible()
    page.wait_for_function(f"() => document.getElementById('{first}').classList.contains('now')")
    check_axe(page, "player, playing")
    page.wait_for_function(
        f"() => document.getElementById('{second}').getAttribute('aria-current') === 'true'"
    )
    assert not page.locator(f"#{first}").evaluate("e => e.classList.contains('now')")
    # chapter 1 ends: chapter 2's file follows by itself, and its sentence lights up
    page.wait_for_function(
        f"() => document.getElementById('{later}').classList.contains('now')", timeout=30_000
    )
    src = page.evaluate("() => document.getElementById('audio').getAttribute('src')")
    assert src.endswith("02%20Methods.mp3"), src
    expect(page.locator("#now")).to_have_text("Chapter 2 of 2: Methods")
    # the reading itself was never announced (D-300)
    assert page.evaluate("() => window.said") == []


def test_a_click_on_a_sentence_plays_from_it(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    target = chunk_id(page, "We measured it twice.")
    page.locator(f"#{target}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    assert highlighted(page) == target
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    index = int(target.removeprefix("s"))
    start, _end, chapter, _ = data["chunks"][index]
    offset = data["chapters"][chapter]["offset"]
    state = page.evaluate(
        "() => ({src: document.getElementById('audio').getAttribute('src'),"
        " time: document.getElementById('audio').currentTime})"
    )
    name = data["chapters"][chapter]["file"]
    expected = page.evaluate("name => encodeURIComponent(name)", name)
    assert state["src"] == f"/api/v1/documents/{data['document']}/audiobook/{expected}"
    assert start - offset - 0.05 <= state["time"] <= start - offset + 1.5


def test_the_buttons_move_by_sentence_and_chapter(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    watch_status(page)
    page.get_by_role("button", name="Next sentence").click()
    assert highlighted(page) == chunk_id(page, "Introduction")
    page.get_by_role("button", name="Next sentence").click()
    assert highlighted(page) == chunk_id(page, "Things happen")
    assert paused(page)  # moving while paused does not start the voice
    page.get_by_role("button", name="Next chapter").click()
    assert highlighted(page) == chunk_id(page, "Methods")
    expect(page.locator("#message")).to_have_text("Chapter 2 of 2: Methods")
    expect(page.locator("#now")).to_have_text("Chapter 2 of 2: Methods")
    assert paused(page)
    page.get_by_role("button", name="Previous sentence").click()
    assert highlighted(page) == chunk_id(page, "Things happen")
    page.get_by_role("button", name="Previous chapter").click()
    assert highlighted(page) == chunk_id(page, "Introduction")
    page.get_by_role("navigation").get_by_role("button", name="Methods").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    assert highlighted(page) == chunk_id(page, "Methods")
    assert page.evaluate("() => window.said")[-1] == "Chapter 2 of 2: Methods"


def test_scrolling_away_stops_following_until_asked(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    back = page.get_by_role("button", name="Back to the reading")
    expect(back).to_be_hidden()
    page.mouse.move(200, 400)
    page.mouse.wheel(0, 300)
    expect(back).to_be_visible()
    back.click()
    expect(back).to_be_hidden()
    expect(page.get_by_role("button", name="Play")).to_be_focused()
    page.get_by_role("checkbox", name="Scroll with the reading").uncheck()
    page.mouse.wheel(0, 300)
    expect(back).to_be_hidden()  # following is off: nothing to come back to


def test_the_player_by_keyboard_only(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.locator("#listen-title").focus()
    order: list[str] = []
    while "follow" not in order and len(order) < 25:
        page.keyboard.press("Tab")
        order.append(
            page.evaluate("() => document.activeElement.id || document.activeElement.tagName")
        )
        outline = page.evaluate("() => getComputedStyle(document.activeElement).outlineStyle")
        assert outline != "none", f"no focus ring on {order[-1]}"
    assert order[:5] == [
        "play",
        "previous-sentence",
        "next-sentence",
        "previous-chapter",
        "next-chapter",
    ], order
    # the native player's own controls, then the follow switch; the hidden button is skipped
    assert order[5] == "audio", order
    assert order[-1] == "follow", order
    assert "back-to-reading" not in order
    page.keyboard.press("Tab")  # the status line is focused only by script: on to the chapters
    assert page.evaluate("() => document.activeElement.textContent") == "Introduction"
    sentences = page.evaluate(
        "() => [...document.querySelectorAll('.s')].some(s => s.tabIndex >= 0)"
    )
    assert not sentences  # thousands of sentences are not tab stops (D-298)
    page.locator("#next-chapter").focus()
    page.keyboard.press("Enter")
    assert highlighted(page) == chunk_id(page, "Methods")
    expect(page.locator("#next-chapter")).to_be_focused()  # the focus stays where it was
    page.locator("#play").focus()
    page.keyboard.press("Space")
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("Space")
    page.wait_for_function("() => document.getElementById('audio').paused")
    expect(page.get_by_role("button", name="Play")).to_be_focused()


def test_the_page_says_when_there_is_nothing_to_play(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = open_paper(page, live)
    page.goto(f"{live.url}/documents/{document}/listen")
    expect(page.locator("#listen-problem")).to_have_text(
        "There is no audiobook of this document yet."
    )
    check_axe(page, "player, no audiobook yet")


def test_the_page_says_when_the_files_are_gone(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    for file in live.config.output_folder.iterdir():
        if file.suffix == ".mp3":
            file.unlink()
    page.goto(f"{live.url}/documents/{document}/listen")
    expect(page.locator("#listen-problem")).to_contain_text("The audiobook files are no longer in")
    check_axe(page, "player, files missing")


def test_a_skipped_figure_shows_and_lights_up_its_notice(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
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
    expect(notice).to_have_text("Figure 1 is skipped.")
    check_axe(page, "player with a notice")
    notice.click()  # the notice is a sentence like any other
    page.wait_for_function("() => !document.getElementById('audio').paused")
    expect(notice).to_have_attribute("aria-current", "true")
    page.wait_for_function(
        f"() => document.getElementById('{chunk_id(page, 'Figure 1: A grey box.')}')"
        ".classList.contains('now')"
    )


def test_a_second_jump_while_a_file_loads_wins(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    later = chunk_id(page, "We measured it twice.")
    early = chunk_id(page, "Things happen")
    page.evaluate(
        f"() => {{ document.getElementById('{later}').click();"
        f" document.getElementById('{early}').click(); }}"
    )
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_timeout(500)
    src = page.evaluate("() => document.getElementById('audio').getAttribute('src')")
    assert src.endswith("01%20Introduction.mp3"), src
    time = page.evaluate("() => document.getElementById('audio').currentTime")
    assert time < 6, time  # in chapter 1, not at the later sentence's time
    assert highlighted(page) == early


def test_text_from_the_file_cannot_change_how_the_page_parses(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    # `<!--<script>` in a heading would make the browser read the rest of the page as
    # part of the data block, if `<` were not escaped there (review of PR #144, M1)
    page = signed_in
    pdf = make_pdf(
        [
            Text("Intro <!--<script>", 72, 80, size=14),
            Text("A sentence after it.", 72, 100, size=11),
            Text("Methods", 72, 140, size=14),
            Text("We measured it twice.", 72, 160, size=11),
        ]
    )
    listen_to(page, live, tmp_path / "odd.pdf", pdf)
    buttons = page.locator(".chapter-button")
    expect(buttons).to_have_count(2)
    expect(buttons.first).to_have_text("Intro <!--<script>")
    expect(page.locator("#text")).to_contain_text("We measured it twice.")
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    assert data["chapters"][0]["title"] == "Intro <!--<script>"
    page.get_by_role("button", name="Next sentence").click()
    assert highlighted(page) == chunk_id(page, "Intro")


# 320x256 is 1280x1024 at 400 % zoom
SIZES = [(1280, 800), (768, 640), (768, 576), (390, 844), (320, 568), (320, 256)]


def test_the_player_bar_never_hides_the_page(signed_in: Page, live: Live) -> None:
    # review of PR #144, M2: the sticky bar covered the text at small widths and at zoom
    page = signed_in
    document = make_audiobook(page, live)
    for width, height in SIZES:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{live.url}/documents/{document}/listen")
        where = f"{width}x{height}"
        sideways = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert sideways <= 0, f"{where}: scrolls sideways by {sideways} px"
        bar = page.evaluate(
            """() => {
                const bar = document.querySelector('.player-bar');
                return {sticky: getComputedStyle(bar).position === 'sticky',
                        height: bar.getBoundingClientRect().height};
            }"""
        )
        if bar["sticky"]:
            assert bar["height"] <= height / 4, f"{where}: a sticky bar of {bar}"
        # every chapter button reached by keyboard is in view and not under the bar
        page.locator("#follow").focus()
        for _ in range(2):
            page.keyboard.press("Tab")
            covered = page.evaluate(
                """() => {
                    const e = document.activeElement;
                    const box = e.getBoundingClientRect();
                    const x = box.left + Math.min(box.width / 2, 10);
                    const y = box.top + box.height / 2;
                    const top = document.elementFromPoint(x, y);
                    if (top === e || e.contains(top)) return '';
                    return `${e.textContent} under ${top?.className}`;
                }"""
            )
            assert covered == "", f"{where}: {covered}"
    page.set_viewport_size({"width": 1280, "height": 720})
