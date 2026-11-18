"""A sentence cut for the voice is one sentence on the Listen page (#480, D-730; the browser
tests of plans/480-c2-tests.md): the mark and the bar stay on it through its pieces, next
and previous step over it whole, a click plays it from its start, M in the first 1.2 s of a
later piece marks it, and its marker's tick stands at its start.

The fake voice speaks 0.1 s per character, so each piece lasts long enough to be seen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect
from test_focus import nobody_focused
from test_player import highlighted, listen_to, paused

from conftest import Live, check_axe

# over the 400-character cut limit (#494): cut once, its later piece the longest
LONG = (
    "In the second survey the share of teachers who use the new material in every lesson has "
    "almost doubled since the start of the programme, while the share of those who never use "
    "it has fallen by half in the same time, in the same schools, with the same questionnaire "
    "and with the same people asking the questions, in every kind of school, from the small "
    "village schools with one class for all ages to the large city schools with several "
    "classes in each year."
)
TEXT = f"A short sentence first.\n\nAnother short one.\n\n{LONG}\n\nA short sentence last.\n"


def listen_to_cut(page: Page, live: Live, tmp_path: Path) -> dict[str, Any]:
    """Make the audiobook of TEXT and open its Listen page; the player's data, with the
    cut sentence's element and pieces."""
    listen_to(page, live, tmp_path / "note.txt", TEXT.encode())
    data: dict[str, Any] = page.evaluate(
        "() => JSON.parse(document.getElementById('player-data').textContent)"
    )
    elements = [chunk[3] for chunk in data["chunks"]]
    pieces = [n for n, e in enumerate(elements) if e and elements.count(e) > 1]
    assert len(pieces) >= 2, f"the long sentence was not cut: {elements}"
    data["pieces"] = pieces
    data["element"] = elements[pieces[0]]
    data["before"] = elements[pieces[0] - 1]
    data["after"] = elements[pieces[-1] + 1]
    return data


def at(page: Page, data: dict[str, Any], time: float) -> None:
    """Put the voice at `time` on the book's timeline (one chapter here), then let the
    page draw."""
    assert len(data["chapters"]) == 1
    page.evaluate(
        """(time) => new Promise((done) => {
            const audio = document.getElementById('audio');
            audio.addEventListener('seeked', () => requestAnimationFrame(() =>
                requestAnimationFrame(done)), { once: true });
            audio.currentTime = time;
        })""",
        time,
    )


def bar_against_sentence(page: Page, bar: str, sentence: str) -> dict[str, float]:
    """How far the bar's top and bottom stand from the sentence's first and last line."""
    found: dict[str, float] = page.evaluate(
        """([bar, sentence]) => {
            const lines = [...document.querySelector(sentence).getClientRects()]
                .filter((r) => r.width && r.height);
            const box = document.querySelector(bar);
            if (box.hidden) return { top: 1e9, bottom: 1e9 };
            const b = box.getBoundingClientRect();
            return {
                top: b.top - Math.min(...lines.map((r) => r.top)),
                bottom: b.bottom - Math.max(...lines.map((r) => r.bottom)),
                lines: lines.length,
            };
        }""",
        [bar, sentence],
    )
    return found


def middle(data: dict[str, Any], n: int) -> float:
    start, end = data["chunks"][n][:2]
    return float((start + end) / 2)


def test_the_mark_and_the_bar_stay_on_the_sentence_through_its_pieces(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    data = listen_to_cut(page, live, tmp_path)
    element = data["element"]
    words = page.locator(f"#{element}").inner_text()
    assert " ".join(words.split()) == LONG  # one element holds the whole sentence
    page.locator("#next-sentence").click()  # loads the file, paused
    for n in data["pieces"]:
        at(page, data, middle(data, n))
        assert highlighted(page) == element, n
        expect(page.locator("#text .s.now")).to_have_count(1)
        bar = bar_against_sentence(page, "#now-bar", f"#{element}")
        assert bar["lines"] > 1, bar  # a sentence of several lines
        assert abs(bar["top"]) <= 1, (n, bar)
        assert abs(bar["bottom"]) <= 1, (n, bar)
    check_axe(page, "Listen, a cut sentence being read")
    # in Focus listening the stage shows the whole sentence in each piece
    nobody_focused(page)
    page.keyboard.press("f")
    expect(page.locator("#focus-view")).to_be_visible()
    for n in data["pieces"]:
        at(page, data, middle(data, n))
        assert highlighted(page) == element, n
        assert " ".join(page.locator("#focus-now").inner_text().split()) == LONG, n
        expect(page.locator("#focus-bar")).to_be_visible()
        bar = bar_against_sentence(page, "#focus-bar", "#focus-now")
        assert abs(bar["top"]) <= 1, (n, bar)
        assert abs(bar["bottom"]) <= 1, (n, bar)
    check_axe(page, "Focus listening, a cut sentence being read")


def test_next_and_previous_step_over_the_cut_sentence_whole(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    data = listen_to_cut(page, live, tmp_path)
    chunks, first, last = data["chunks"], data["pieces"][0], data["pieces"][-1]
    nobody_focused(page)
    # paused, from the sentence before: next is the cut sentence, then the one after it
    page.locator(f"#{data['before']}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.locator("#play").click()
    assert paused(page)
    page.locator("#next-sentence").click()
    assert highlighted(page) == data["element"]
    assert (
        abs(page.evaluate("() => document.getElementById('audio').currentTime") - chunks[first][0])
        < 0.05
    )
    page.locator("#next-sentence").click()
    assert highlighted(page) == data["after"]
    # and previous from there goes to the cut sentence's start, not to its last piece
    page.locator("#previous-sentence").click()
    assert highlighted(page) == data["element"]
    assert (
        abs(page.evaluate("() => document.getElementById('audio').currentTime") - chunks[first][0])
        < 0.05
    )
    page.locator("#next-sentence").click()
    # paused in the last piece, previous goes to the sentence before, not to a piece
    at(page, data, middle(data, last))
    assert highlighted(page) == data["element"]
    page.locator("#previous-sentence").click()
    assert highlighted(page) == data["before"]
    # the arrow keys do the same
    at(page, data, middle(data, last))
    nobody_focused(page)
    page.keyboard.press("ArrowRight")
    assert highlighted(page) == data["after"]
    at(page, data, middle(data, last))
    page.keyboard.press("ArrowLeft")
    assert highlighted(page) == data["before"]
    # playing, half a second into the second piece (well past RESTART_AFTER since the
    # sentence began, though not since the piece began): previous restarts the sentence
    second = data["pieces"][1]
    assert chunks[second][0] - chunks[first][0] > 1.5
    page.locator(f"#{data['element']}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    at(page, data, chunks[second][0] + 0.5)
    page.locator("#previous-sentence").click()
    assert highlighted(page) == data["element"]
    time = page.evaluate("() => document.getElementById('audio').currentTime")
    assert chunks[first][0] - 0.05 <= time < chunks[first][0] + 0.5, time


def test_a_click_on_the_cut_sentence_plays_it_from_its_start(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    data = listen_to_cut(page, live, tmp_path)
    first = data["pieces"][0]
    expect(page.locator(f"#{data['element']}")).to_have_attribute("data-chunk", str(first))
    # a click on the sentence's last line, in its last piece
    line = page.evaluate(
        """(id) => {
            const sentence = document.getElementById(id);
            sentence.scrollIntoView({ block: "center" });
            const rects = [...sentence.getClientRects()].filter((r) => r.width);
            const r = rects[rects.length - 1];
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""",
        data["element"],
    )
    page.mouse.click(line["x"], line["y"])
    page.wait_for_function("() => !document.getElementById('audio').paused")
    assert highlighted(page) == data["element"]
    time = page.evaluate("() => document.getElementById('audio').currentTime")
    assert data["chunks"][first][0] - 0.05 <= time <= data["chunks"][first][0] + 1.5, time


def test_m_early_in_a_later_piece_marks_the_cut_sentence_and_its_tick_is_at_its_start(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    data = listen_to_cut(page, live, tmp_path)
    chunks, first, second = data["chunks"], data["pieces"][0], data["pieces"][1]
    nobody_focused(page)
    # M in the first 1.2 s of the cut sentence still means the sentence before (#397)
    page.locator(f"#{data['element']}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.keyboard.press("m")
    expect(page.locator("#marker-said")).to_have_text("Marker set.")
    expect(page.locator("#marker-flags [data-for]")).to_have_attribute("data-for", data["before"])
    page.locator("#marker-undo").click()
    expect(page.locator("#marker-said")).to_have_text("Marker removed.")
    # M in the first 1.2 s of its second piece: the sentence itself, not the one before
    at(page, data, chunks[second][0] + 0.2)
    assert not paused(page)
    page.keyboard.press("m")
    expect(page.locator("#marker-said")).to_have_text("Marker set.")
    page.locator("#play").click()
    expect(page.locator("#marker-flags [data-for]")).to_have_attribute("data-for", data["element"])
    page.reload()
    (marker,) = page.evaluate(
        "() => JSON.parse(document.getElementById('player-data').textContent).markers"
    )
    # the page names the sentence by its first piece, though a later one overlaps most (#520)
    assert marker["chunk"] == first
    expect(page.locator("#marker-ticks rect")).to_have_count(1)
    # the tick stands at the sentence's start, where the list's Go to and a click go
    x = page.locator("#marker-ticks rect").get_attribute("x")
    length = float(page.locator("#timeline").get_attribute("max") or 0)
    assert x is not None
    assert abs(float(x.removesuffix("%")) - chunks[first][0] / length * 100) < 0.01, x
    # the Markers list says that time and its Go to goes there
    page.locator("#tab-markers").click()
    (row,) = page.locator("#marker-list > li").all()
    seconds = int(chunks[first][0])
    expect(row.locator(".mk-at")).to_have_text(f"Chapter 1 · {seconds // 60}:{seconds % 60:02d}")
    row.get_by_role("button", name="Go to").click()
    expect(page.locator("#text .s.now")).to_have_id(data["element"])
    time = page.evaluate("() => document.getElementById('audio').currentTime")
    assert abs(time - chunks[first][0]) < 0.05, time
