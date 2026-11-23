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

import pdf_maker
from pdf_maker import Rect, Text, make_pdf
from playwright.sync_api import Page, expect
from test_flow import open_paper

from conftest import Live, at_rest, check_axe, settled, tab_key
from sci2audio.app import build_book
from sci2audio.output import BookKind
from sci2audio.web.player import recorded_folder

PER_CHARACTER = 2400  # samples at 24 kHz: 0.1 s per character


def make_audiobook(page: Page, live: Live) -> str:
    """Open the paper, make its audiobook and open the player; returns the document id."""
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    document = open_paper(page, live)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    # the job page reloads itself when the job ends; a click while the reloaded page's
    # fonts still arrived followed no link (Firefox, nightly-green PR 3 isolation)
    at_rest(page)
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(f"{live.url}/documents/{document}/listen")
    expect(page.get_by_role("heading", level=1)).to_have_text("paper")  # the title (#391)
    expect(page.get_by_role("link", name="Listen")).to_have_attribute("aria-current", "page")
    return document


def built_m4b(live: Live, document: str) -> tuple[Path, str]:
    """Build the made audiobook's M4B, as the download does (#725): the web job writes none.
    Returns the project's audiobook folder and the M4B's name."""
    work = live.state.store.get(document).folder
    folder = recorded_folder(work, document)
    assert folder is not None
    return folder, build_book(work, folder, BookKind.M4B).path.name


def listen_to(page: Page, live: Live, path: Path, pdf: bytes) -> None:
    """Open this PDF, make its audiobook and open the player. The start waits until the
    page no longer follows the analysis: a page drawn while the analysis job ends shows
    the Make button and still reloads itself, which cancels the start's move to the job
    page (#289, as `open_paper` does for #138)."""
    live.install_voice()
    live.voice.samples_per_character = PER_CHARACTER
    path.write_bytes(pdf)
    page.set_input_files("#file", files=[path])
    page.get_by_role("button", name="Open and analyse").click()
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.locator("#summary")).to_be_visible()
    settled(page)
    # a click while the page's fonts still arrived did nothing (WebKit, #699), as in
    # `make_audiobook`
    at_rest(page)
    page.get_by_role("button", name="Make the audiobook").click()
    page.wait_for_url(re.compile(r"/jobs/[0-9a-f]{16}-audio-\d+"))
    expect(page.locator("#result")).to_have_text("Your audiobook is ready", timeout=60_000)
    at_rest(page)  # the job page reloads itself when the job ends
    page.get_by_role("link", name="Listen with the text").click()
    page.wait_for_url(re.compile(r"/listen$"))


def highlighted(page: Page) -> str:
    return str(page.evaluate("() => document.querySelector('[aria-current=true]')?.id ?? ''"))


def chunk_id(page: Page, words: str) -> str:
    return str(page.locator(".s", has_text=words).first.get_attribute("id"))


def choose_speed(page: Page, preset: str) -> None:
    """Chooses one of the player's usual speeds (#651), named as its button shows it (1.5
    and a times sign): the dock's speed button opens them; Esc closes them again."""
    page.locator("#speed").click()
    page.locator("#speed-panel").get_by_role("button", name=preset, exact=True).click()
    page.keyboard.press("Escape")
    expect(page.locator("#speed-panel")).to_be_hidden()


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
    expect(page.locator("#text")).to_contain_text(
        "Things happen (Smith, 2020) (not read) and more."
    )  # #444
    expect(page.locator("#text")).not_to_contain_text("A book about things")  # not chosen
    # the Chapters panel lists the chosen chapters only, and names no other (#472)
    expect(page.locator(".outline .ot")).to_have_text(["Introduction", "Methods"])
    expect(page.locator("#panel-outline")).not_to_contain_text("Not in this audiobook")
    expect(page.locator("#panel-outline")).not_to_contain_text("References")
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


def test_the_buttons_move_by_sentence_and_the_chapter_list_by_chapter(
    signed_in: Page, live: Live
) -> None:
    """The dock's previous and next move by sentence (#393, D-704 point 6); the panel's list
    of chapters moves by chapter, and says which chapter is being read."""
    page = signed_in
    make_audiobook(page, live)
    watch_status(page)
    chapters = page.get_by_role("navigation", name="Chapters").get_by_role("button")
    expect(chapters.first).to_have_attribute("aria-current", "true")
    page.get_by_role("button", name="Next sentence").click()
    assert highlighted(page) == chunk_id(page, "Introduction")
    page.get_by_role("button", name="Next sentence").click()
    assert highlighted(page) == chunk_id(page, "Things happen")
    assert paused(page)  # moving while paused does not start the voice
    page.get_by_role("button", name="Previous sentence").click()
    assert highlighted(page) == chunk_id(page, "Introduction")
    chapters.filter(has_text="Methods").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    assert highlighted(page) == chunk_id(page, "Methods")
    expect(page.locator("#message")).to_have_text("Chapter 2 of 2: Methods")
    expect(page.locator("#now")).to_have_text("Chapter 2 of 2: Methods")
    expect(chapters.nth(1)).to_have_attribute("aria-current", "true")
    expect(chapters.first).not_to_have_attribute("aria-current", "true")
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
    page.get_by_role("switch", name="Scroll with the reading").uncheck()
    page.mouse.wheel(0, 300)
    expect(back).to_be_hidden()  # following is off: nothing to come back to


def test_the_player_by_keyboard_only(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.locator("#listen-title").focus()
    order: list[str] = []
    while "follow" not in order and len(order) < 25:
        page.keyboard.press(tab_key(page))
        order.append(
            page.evaluate("() => document.activeElement.id || document.activeElement.tagName")
        )
        outline = page.evaluate("() => getComputedStyle(document.activeElement).outlineStyle")
        assert outline != "none", f"no focus ring on {order[-1]} after {order}"
    # the paper header's tabs first (#391), then the dock in the order it shows (#393), the
    # Focus button (#394), the panel's button, and the panel: its selected tab, the
    # chapters, the whole-book download (#725) and the follow switch; the hidden button, the
    # status line and the panel's other tab are skipped
    assert order == [
        "tab-prepare",
        "tab-listen",
        "previous-sentence",
        "play",
        "next-sentence",
        "timeline",
        "speed",
        "focus-on",
        "panel-toggle",
        "tab-outline",
        "panel-close",
        "BUTTON",
        "BUTTON",
        "SUMMARY",
        "follow",
    ], order
    sentences = page.evaluate(
        "() => [...document.querySelectorAll('.s')].some(s => s.tabIndex >= 0)"
    )
    assert not sentences  # thousands of sentences are not tab stops (D-298)
    page.locator("#next-sentence").focus()
    page.keyboard.press("Enter")
    assert highlighted(page) == chunk_id(page, "Introduction")
    expect(page.locator("#next-sentence")).to_be_focused()  # the focus stays where it was
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
    for file in live.config.output_folder.rglob("*.mp3"):  # in the project's folder (D-749)
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
    expect(notice).to_have_text("Spoken notice: Figure 1 is skipped.")
    check_axe(page, "player with a notice")
    notice.click()  # the notice is a sentence like any other
    page.wait_for_function("() => !document.getElementById('audio').paused")
    expect(notice).to_have_attribute("aria-current", "true")
    page.wait_for_function(
        f"() => document.getElementById('{chunk_id(page, 'Figure 1: A grey box.')}')"
        ".classList.contains('now')"
    )


def test_a_footnote_lights_up_after_the_sentence_with_its_mark(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """#213 (plan Q8): the note is read after the sentence that holds its mark, and the page
    shows it after that paragraph, so the highlight goes from the sentence to the note and
    back to the paragraph's next sentence."""
    page = signed_in
    words = "It works on every page we tried"
    after = 72 + pdf_maker.width(words, size=11)
    pdf = make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text(words, 72, 100, size=11),
            Text("1", after, 96, size=7),
            Text(". It holds for the rest.", after + pdf_maker.width("1", size=7), 100, size=11),
            *[
                Text(
                    f"Then the text goes on, line {k}, in the body size.", 72, 114 + 14 * k, size=11
                )
                for k in range(25)
            ],
            Rect(72, 700, 140, 700.5),
            Text("1", 72, 712, size=6),
            Text(" A note on the pages we tried.", 72 + pdf_maker.width("1", size=6), 714, size=8),
        ]
    )
    listen_to(page, live, tmp_path / "note.pdf", pdf)
    sentence = chunk_id(page, words)
    note = chunk_id(page, "A note on the pages we tried.")
    rest = chunk_id(page, "It holds for the rest.")
    # the note shows after the paragraph it is read in
    order = page.evaluate(
        "ids => ids.map(id => document.getElementById(id))"
        ".map((e, i, all) => i === 0 || (all[i - 1].compareDocumentPosition(e) & 4) > 0)",
        [sentence, rest, note],
    )
    assert order == [True, True, True]
    page.locator(f"#{sentence}").click()
    for heard in (sentence, note, rest):
        page.wait_for_function(
            f"() => document.getElementById('{heard}').classList.contains('now')",
            timeout=30_000,
        )
    check_axe(page, "player with a moved note")


# a page of running text: code is told from text only where the text is not itself set in
# a typewriter font (#289), so a made-up PDF with a listing needs some
PROSE_PAGE = [
    Text(f"Running text on the second page, line {k}, set in a proportional font.", 72, 80 + 14 * k)
    for k in range(30)
]


def test_a_skipped_code_block_shows_its_notice_and_its_code(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """#280, D-546: the voice reads the notice; the code is shown open below it."""
    page = signed_in
    code = ["import seaborn as sns", "g = sns.relplot(data=fmri)", 'g.savefig("demo.pdf")']
    pdf = make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("The following example makes a figure.", 72, 100, size=11),
            *(Text(line, 72, 124 + 13 * k, "Courier", 10) for k, line in enumerate(code)),
            Text("Text after it.", 72, 190, size=11),
        ],
        PROSE_PAGE,
    )
    listen_to(page, live, tmp_path / "code.pdf", pdf)
    notice = page.locator(".notice")
    expect(notice.locator("p")).to_have_text("Spoken notice: A code block is skipped.")
    expect(notice.locator("pre.code")).to_have_text("\n".join(code))
    expect(notice.locator("pre.code")).to_be_visible()
    check_axe(page, "player with a code block")


def test_a_pdf_listing_is_shown_with_its_printed_indent(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """#282: a line printed four Courier characters in (6 points each at 10 point) is shown
    four spaces in; the notice is unchanged."""
    page = signed_in
    rows = [("g = sns.relplot(", 0), ('data=fmri, kind="line",', 4), (")", 0)]
    pdf = make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("The following example makes a figure.", 72, 100, size=11),
            *(
                Text(line, 72 + 6 * indent, 124 + 13 * k, "Courier", 10)
                for k, (line, indent) in enumerate(rows)
            ),
            Text("Text after it.", 72, 190, size=11),
        ],
        PROSE_PAGE,
    )
    listen_to(page, live, tmp_path / "indent.pdf", pdf)
    notice = page.locator(".notice")
    expect(notice.locator("p")).to_have_text("Spoken notice: A code block is skipped.")
    shown = "\n".join(" " * indent + line for line, indent in rows)
    # exact: `to_have_text` folds white space
    expect(notice.locator("pre.code")).to_have_js_property("textContent", shown)


def test_a_listing_taller_than_the_window_keeps_its_spoken_notice_in_view(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    """#288: when the reading reaches a code block taller than the window, its
    top, where the spoken notice stands, comes to rest at the window's top, above the dock."""
    page = signed_in
    page.set_viewport_size({"width": 1280, "height": 720})
    page.emulate_media(reduced_motion="reduce")
    lines = [f"value_{k} = compute({k}, scale=2)" for k in range(44)]
    pdf = make_pdf(
        [
            Text("Introduction", 72, 60, size=14),
            Text("The following example sets up the values.", 72, 80, size=11),
            *(Text(line, 72, 100 + 13 * k, "Courier", 10) for k, line in enumerate(lines)),
            Text("Text after it.", 72, 100 + 13 * 44 + 20, size=11),
        ],
        PROSE_PAGE,
    )
    listen_to(page, live, tmp_path / "long-code.pdf", pdf)
    notice = page.locator(".notice")
    assert notice.bounding_box()["height"] > 720  # type: ignore[index]
    page.locator(".s", has_text="The following example").first.click()
    expect(notice).to_have_attribute("aria-current", "true", timeout=20_000)
    page.wait_for_timeout(300)  # reduced motion: the scroll is instant; let it land
    said, dock = page.evaluate(
        """() => [
            document.querySelector('.notice p').getBoundingClientRect().toJSON(),
            document.getElementById('dock').getBoundingClientRect().top,
        ]"""
    )
    assert said["top"] >= 0, said
    assert said["bottom"] <= dock, (said, dock)


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


def test_a_second_step_while_the_file_loads_stays_on_its_sentence(
    signed_in: Page, live: Live
) -> None:
    """Two steps in one go, paused, before the file has loaded (#699): the second jump finds
    the file chosen but not loaded. WebKit then reads `currentTime` as 0, so a jump that set
    it at once fell back to the start of the chapter, with no sentence marked."""
    page = signed_in
    make_audiobook(page, live)
    second = chunk_id(page, "Things happen")
    page.evaluate(
        """() => {
            const next = document.getElementById('next-sentence');
            next.click();
            next.click();
        }"""
    )
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    assert paused(page)
    assert highlighted(page) == second
    start = page.evaluate(
        f"""() => {{
            const data = JSON.parse(document.getElementById('player-data').textContent);
            const chunk = Number(document.getElementById('{second}').dataset.chunk);
            return data.chunks[chunk][0] - data.chapters[data.chunks[chunk][2]].offset;
        }}"""
    )
    time = page.evaluate("() => document.getElementById('audio').currentTime")
    assert abs(time - start) < 0.05, (time, start)
    expect(page.locator("#marker")).to_be_enabled()


def test_steps_while_the_audio_still_seeks_end_on_the_last_one(signed_in: Page, live: Live) -> None:
    """Back and on again, paused, inside one file, the second step while the first one's seek
    may still run (#720): Linux WebKit lost the position of a seek started over a running one
    and ended at 0, with no sentence marked. So the page never sets the time while the element
    seeks (counted through the element's own `currentTime` setter), and each pair ends on the
    sentence it started from, at its start. Tried at several gaps between the two steps, the
    first none: both in one task, where every browser still seeks at the second one."""
    page = signed_in
    make_audiobook(page, live)
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")
    page.locator("#next-sentence").click()
    page.locator("#next-sentence").click()
    found = page.evaluate(
        """async (gaps) => {
            const audio = document.getElementById('audio');
            const next = document.getElementById('next-sentence');
            const previous = document.getElementById('previous-sentence');
            const data = JSON.parse(document.getElementById('player-data').textContent);
            const order = [...new Set(data.chunks.map((c) => c[3]))];
            const own = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'currentTime');
            let over = 0; // times set while the element still sought
            Object.defineProperty(audio, 'currentTime', {
                configurable: true,
                get() { return own.get.call(this); },
                set(value) { if (this.seeking) over += 1; own.set.call(this, value); },
            });
            const wait = (ms) => new Promise((done) => setTimeout(done, ms));
            // at rest: the file's metadata in and no seek running, still so a moment later
            // (a jump waiting for a seek starts its own in that seek's `seeked`)
            const quiet = () => !audio.seeking && audio.readyState >= 1;
            const settle = async () => {
                const deadline = performance.now() + 10000;
                do {
                    while (!quiet()) {
                        if (performance.now() > deadline) throw new Error('audio never settled');
                        await wait(5);
                    }
                    await wait(50);
                } while (!quiet());
            };
            const now = () => document.querySelector('#text .s.now')?.id ?? '';
            const chunkOf = (id) => data.chunks[Number(document.getElementById(id).dataset.chunk)];
            const startOf = (id) => chunkOf(id)[0] - data.chapters[chunkOf(id)[2]].offset;
            await settle();
            const want = now();
            const before = order[order.indexOf(want) - 1];
            const src = audio.getAttribute('src');
            if (!before || chunkOf(before)[2] !== chunkOf(want)[2]) {
                return { want, before, gaps: [] };
            }
            const lost = [];
            for (const gap of gaps) {
                previous.click();
                if (gap > 0) await wait(gap);
                next.click();
                await settle();
                const time = audio.currentTime;
                if (now() !== want || Math.abs(time - startOf(want)) > 0.05) {
                    lost.push({ gap, marked: now(), time });
                    break;
                }
            }
            return { want, before, same_file: audio.getAttribute('src') === src, over, lost, gaps };
        }""",
        [0, 1, 2, 4, 6, 8, 10, 12, 15, 20, 25, 30, 40],
    )
    assert found["gaps"], found  # the sentence before is in the same chapter, so the same file
    assert found["same_file"], found
    assert found["over"] == 0, found
    assert found["lost"] == [], found
    assert paused(page)


def test_text_from_the_file_cannot_change_how_the_page_parses(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    # `<!--<script>` in a heading would make the browser read the rest of the page as
    # part of the data block, if `<` were not escaped there (#144)
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
    buttons = page.locator(".chapter-button .ot")
    expect(buttons).to_have_count(2)
    expect(buttons.first).to_have_text("Intro <!--<script>")
    expect(page.locator("#text")).to_contain_text("We measured it twice.")
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    assert data["chapters"][0]["title"] == "Intro <!--<script>"
    page.get_by_role("button", name="Next sentence").click()
    assert highlighted(page) == chunk_id(page, "Intro")


# 320x256 is 1280x1024 at 400 % zoom
SIZES = [(1280, 800), (768, 640), (768, 576), (390, 844), (320, 568), (320, 256)]


def test_the_dock_never_hides_the_page(signed_in: Page, live: Live) -> None:
    # #144: the sticky bar covered the text at small widths and at zoom; the
    # dock (#393) is pinned to the window's foot by the same rule
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
                const bar = document.getElementById('dock');
                const box = bar.getBoundingClientRect();
                return {fixed: getComputedStyle(bar).position === 'fixed',
                        height: box.height, bottom: box.bottom};
            }"""
        )
        # pinned exactly while it takes at most a quarter of the window
        assert bar["fixed"] == (bar["height"] <= height / 4), f"{where}: {bar}"
        if (width, height) == (1280, 800):
            assert bar["fixed"], f"{where}: a wide window keeps the dock in view: {bar}"
            # Firefox lays out in sub-pixels: 799.99998 is the foot of an 800 px window (#501)
            assert abs(bar["bottom"] - height) < 0.5, f"{where}: the dock stands at the foot: {bar}"
        padding = page.evaluate("() => document.documentElement.style.scrollPaddingBottom")
        assert (padding != "") == bar["fixed"], f"{where}: scroll padding {padding!r}"
        # the end of the page can be scrolled out from under the dock
        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        last = page.evaluate(
            """() => {
                const all = document.querySelectorAll('#text .block');
                const box = all[all.length - 1].getBoundingClientRect();
                return box.bottom <= document.getElementById('dock').getBoundingClientRect().top
                    || getComputedStyle(document.getElementById('dock')).position !== 'fixed';
            }"""
        )
        assert last, f"{where}: the last paragraph stays under the dock"
        # every chapter button reached by keyboard is in view and not under the dock
        if width < 1280:
            page.get_by_role("button", name="Show the side panel").click()
        page.locator("#tab-outline").focus()
        for _ in range(2):
            page.keyboard.press(tab_key(page))
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
