"""The player's own speed control (#152): a native select that sets the playback rate,
keeps the pitch, keeps the chosen speed across chapter files, jumps and the M4B, and keeps
the highlight in step with the voice at 2x."""

from __future__ import annotations

import json
import sys

from playwright.sync_api import Page, expect
from test_player import chunk_id, highlighted, make_audiobook

from conftest import Live, check_axe, tab_key


def rate(page: Page) -> dict[str, object]:
    return dict(
        page.evaluate(
            """() => { const a = document.getElementById('audio');
                return {rate: a.playbackRate, pitch: a.preservesPitch,
                        src: a.getAttribute('src')}; }"""
        )
    )


def test_the_speed_select_sets_the_rate_and_keeps_the_pitch(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    speed = page.get_by_label("Speed")
    expect(speed).to_have_value("1")
    # read in the page: a Playwright locator on the <option>s crashes Firefox's page
    options = page.evaluate(
        "() => [...document.querySelectorAll('#speed option')].map(o => o.text)"
    )
    times = "\u00d7"  # the multiplication sign
    assert options == [f"{n}{times}" for n in ("0.75", "1", "1.25", "1.5", "1.75", "2")]
    speed.select_option("2")
    assert rate(page)["rate"] == 2
    assert rate(page)["pitch"] is True
    check_axe(page, "player, speed 2x")
    page.emulate_media(color_scheme="dark")
    check_axe(page, "player, speed 2x, dark")


def test_the_speed_stays_across_chapters_and_jumps(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.get_by_label("Speed").select_option("1.5")
    first_file = rate(page)["src"]
    # a jump into the next chapter's file, from the list of chapters (#393)
    page.locator(".chapter-button").nth(1).click()
    page.wait_for_function("() => document.getElementById('audio').readyState >= 1")
    state = rate(page)
    assert state["src"] != first_file
    assert state["rate"] == 1.5
    assert state["pitch"] is True
    # a sentence jump and a click on a sentence
    page.get_by_role("button", name="Previous sentence").click()
    assert rate(page)["rate"] == 1.5
    page.locator(f"#{chunk_id(page, 'Things happen')}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    assert rate(page)["rate"] == 1.5
    assert str(rate(page)["src"]) == first_file


def test_at_2x_the_highlight_stays_with_the_voice(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.get_by_label("Speed").select_option("2")
    page.get_by_role("button", name="Play").click()
    data = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    chunks = data["chunks"]
    for wait in (1500, 1500, 2500):
        page.wait_for_timeout(wait)
        state = page.evaluate(
            """() => { const a = document.getElementById('audio');
                const id = document.querySelector('[aria-current=true]')?.id ?? '';
                return {time: a.currentTime, src: a.getAttribute('src'), id}; }"""
        )
        chapter = next(
            n
            for n, c in enumerate(data["chapters"])
            if state["src"].endswith(page.evaluate("n => encodeURIComponent(n)", c["file"]))
        )
        book = state["time"] + data["chapters"][chapter]["offset"]
        at = max((n for n, c in enumerate(chunks) if c[0] <= book + 0.0005), default=-1)
        # the element of the chunk being spoken, or the one just before (a frame behind)
        expected = {chunks[n][3] if n >= 0 else "" for n in (at, at - 1)}
        assert state["id"] in expected, (state, book)
    assert highlighted(page)
    assert rate(page)["rate"] == 2


def test_the_speed_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.locator("#audio").focus()
    while page.evaluate("() => document.activeElement.id") != "speed":
        page.keyboard.press(tab_key(page))
    if page.context.browser.browser_type.name == "webkit" and sys.platform == "darwin":  # type: ignore[union-attr]
        # macOS opens a closed select's native menu with the arrow keys instead of moving
        # its value, and Playwright cannot drive that menu: here the select is only reached
        # and focused; the release's VoiceOver pass tries it by keyboard on a Mac (D-678)
        return
    page.keyboard.press("ArrowDown")  # a closed select changes its value with the arrows
    assert page.evaluate("() => document.getElementById('speed').value") == "1.25"
    assert rate(page)["rate"] == 1.25


def test_the_speed_stays_on_the_m4b(signed_in: Page, live: Live) -> None:
    """An audiobook with only an M4B (written by the command line with MP3s off) plays one
    file: the chosen speed stays when a jump moves within it."""
    page = signed_in
    document = make_audiobook(page, live)
    work = live.state.store.get(document).folder
    record = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    for name in record["files"]["mp3"]:
        (live.config.output_folder / name).unlink()
    record["files"]["mp3"] = []
    (work / "audio.json").write_text(json.dumps(record), encoding="utf-8")
    readalong = live.config.output_folder / record["files"]["readalong"]
    data = json.loads(readalong.read_text(encoding="utf-8"))
    for chapter in data["chapters"]:
        chapter["mp3"] = None
    readalong.write_text(json.dumps(data), encoding="utf-8")
    page.reload()
    player = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    assert player["mode"] == "m4b"
    page.get_by_label("Speed").select_option("0.75")
    page.locator(".chapter-button").nth(1).click()
    page.get_by_role("button", name="Next sentence").click()
    state = rate(page)
    assert str(state["src"]).endswith(".m4b")
    assert state["rate"] == 0.75
    assert state["pitch"] is True
