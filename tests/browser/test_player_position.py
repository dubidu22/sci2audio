"""The listening position across server runs (#153): the player keeps where the person
stopped; the next run of sci2audio, on another port, offers to continue there or start
from the beginning, and never plays by itself (D-300)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import Page, Route, expect
from test_player import chunk_id, highlighted, make_audiobook, paused, watch_status

from conftest import Live, SlowFetch, check_axe, inside, serve, tab_key
from sci2audio.web.player import POSITION


def wait_until_saved(page: Page, live: Live, document: str, time: float) -> None:
    """Wait until the working folder holds this position (the save on pause can take longer
    than a fixed wait on a busy runner: nightly run 43774244578 read the save before it)."""
    path = live.state.store.get(document).folder / POSITION
    for _ in range(100):
        try:
            if abs(json.loads(path.read_text(encoding="utf-8"))["time"] - time) < 0.05:
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        page.wait_for_timeout(50)
    raise AssertionError(f"the position {time} was not saved: {path}")


def test_the_next_run_offers_to_continue_where_the_person_stopped(
    signed_in: Page, live: Live, tmp_path: Path
) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    later = chunk_id(page, "We measured it twice.")
    page.locator(f"#{later}").click()  # chapter 2
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_function("() => document.getElementById('audio').paused")
    stopped = page.evaluate(
        "() => { const d = JSON.parse(document.getElementById('player-data').textContent);"
        " return document.getElementById('audio').currentTime + d.chapters[1].offset; }"
    )
    wait_until_saved(page, live, document, stopped)  # the save on pause reached the server

    with serve(tmp_path, live.voice, SlowFetch()) as second:
        assert second.url != live.url  # another port: the browser's storage starts empty
        page.unroute("**/*")
        exit_save = f"{live.url}/api/v1/documents/{document}/position"
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if inside(route.request.url, second.url)
                # the first run's page saves its position on its way out, to its own server
                # (Firefox sends that save after this route is set)
                or (route.request.method == "POST" and route.request.url == exit_save)
                else (live.outside.append(route.request.url), route.abort())
            ),
        )
        page.goto(second.start_url)
        page.goto(f"{second.url}/documents/{document}/listen")
        offer = page.locator("#resume")
        expect(offer).to_be_visible()
        expect(offer).to_contain_text("You stopped in chapter 2 at 0:")
        expect(offer).to_contain_text("Methods")
        check_axe(page, "player, continue offer")
        page.emulate_media(color_scheme="dark")
        check_axe(page, "player, continue offer, dark")
        page.emulate_media(color_scheme="light")
        assert paused(page)  # nothing plays by itself (D-300)
        watch_status(page)
        # by keyboard: the offer's buttons are reached with Tab
        page.locator("#listen-title").focus()
        while page.evaluate("() => document.activeElement.id") != "resume-continue":
            page.keyboard.press(tab_key(page))
        page.keyboard.press("Enter")
        expect(page.locator("#resume")).to_have_count(0)
        expect(page.get_by_role("button", name="Play")).to_be_focused()
        assert paused(page)
        assert highlighted(page) == later
        page.wait_for_function("() => document.getElementById('audio').currentTime > 0")
        state = page.evaluate(
            "() => { const d = JSON.parse(document.getElementById('player-data').textContent);"
            " const a = document.getElementById('audio');"
            " return {src: a.getAttribute('src'), time: a.currentTime + d.chapters[1].offset}; }"
        )
        assert state["src"].endswith("02%20Methods.mp3"), state
        assert abs(state["time"] - stopped) < 0.6, (state, stopped)
        assert page.evaluate("() => window.said") == ["Chapter 2 of 2: Methods"]
        page.keyboard.press("Space")
        page.wait_for_function("() => !document.getElementById('audio').paused")


def test_start_from_the_beginning(signed_in: Page, live: Live, tmp_path: Path) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    page.locator(f"#{chunk_id(page, 'We measured it twice.')}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_timeout(300)
    page.reload()  # the same run: the server kept it too
    expect(page.locator("#resume")).to_be_visible()
    page.get_by_role("button", name="Start from the beginning").click()
    expect(page.locator("#resume")).to_have_count(0)
    assert paused(page)
    src = page.evaluate("() => document.getElementById('audio').getAttribute('src')")
    assert src.endswith("01%20Introduction.mp3"), src
    assert page.evaluate("() => document.getElementById('audio').currentTime") < 0.5
    page.get_by_role("button", name="Play").click()
    page.wait_for_function(
        f"() => document.getElementById('{chunk_id(page, 'Introduction')}')"
        ".classList.contains('now')"
    )
    del document


def test_nothing_is_offered_before_anything_was_heard(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    page.reload()  # opening the page and leaving it again saves nothing
    page.reload()
    expect(page.locator("#resume")).to_have_count(0)
    assert re.search("resume", page.content()) is None


def test_the_offer_waits_for_the_script_before_it_can_be_pressed(
    signed_in: Page, live: Live
) -> None:
    """#373 (the #350 lesson): the server draws the offer's buttons, the
    deferred script wires them, so they start disabled and are enabled once wired."""
    page = signed_in
    make_audiobook(page, live)
    page.locator(f"#{chunk_id(page, 'We measured it twice.')}").click()
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_timeout(300)
    held: list[Route] = []
    page.route("**/static/player.js", lambda route: held.append(route))
    page.reload(wait_until="commit")
    expect(page.locator("#resume-continue")).to_be_disabled()
    expect(page.locator("#resume-start")).to_be_disabled()
    while not held:
        page.wait_for_timeout(50)
    held[0].continue_()
    expect(page.locator("#resume-continue")).to_be_enabled()
    expect(page.locator("#resume-start")).to_be_enabled()


def test_the_end_of_the_audio_sends_one_save(signed_in: Page, live: Live) -> None:
    """#763: `pause` and `ended` both kept the place when the audio ended, and the two
    requests at once could fail on the server. Now the same place is sent once."""
    page = signed_in
    document = make_audiobook(page, live)
    saves: list[str] = []
    page.on(
        "request",
        lambda request: (
            saves.append(request.post_data or "")
            if request.method == "POST" and request.url.endswith(f"/{document}/position")
            else None
        ),
    )
    answers: list[int] = []
    page.on(
        "response",
        lambda response: (
            answers.append(response.status)
            if response.request.method == "POST" and response.url.endswith(f"/{document}/position")
            else None
        ),
    )
    page.locator(f"#{chunk_id(page, 'We measured it twice.')}").click()  # the last chapter
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.evaluate(
        "() => { const a = document.getElementById('audio'); a.currentTime = a.duration - 0.3; }"
    )
    page.wait_for_function("() => document.getElementById('audio').ended")
    page.wait_for_timeout(500)  # a second save, if there were one, is sent by now
    assert saves
    assert len(saves) == len(set(saves)), saves  # no place was sent twice
    assert json.loads(saves[-1])["chapter"] == 1
    assert 503 not in answers, answers  # no save failed because of another
