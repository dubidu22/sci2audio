"""The player's own speed control (#152, #651): a button in the dock opens the usual speeds
and a speed field for any speed from 0.50 to 3.00 in steps of 0.01. It sets the playback
rate, keeps the pitch, keeps the chosen speed across chapter files, jumps and the M4B and
for the next Listen page, and keeps the highlight in step with the voice at 2x."""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect
from test_player import built_m4b, choose_speed, chunk_id, highlighted, make_audiobook

from conftest import Live, check_axe, click_focuses, tab_key
from sci2audio.web.i18n import PLAYER_SPEED_COOKIE


def rate(page: Page) -> dict[str, object]:
    return dict(
        page.evaluate(
            """() => { const a = document.getElementById('audio');
                return {rate: a.playbackRate, pitch: a.preservesPitch,
                        src: a.getAttribute('src')}; }"""
        )
    )


TIMES = "\u00d7"  # the multiplication sign


def test_the_usual_speeds_set_the_rate_and_keep_the_pitch(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    button = page.locator("#speed")
    expect(button).to_have_text(f"Speed 1.00{TIMES}")  # two decimals: its width stays
    expect(button).to_have_attribute("aria-expanded", "false")
    panel = page.locator("#speed-panel")
    expect(panel).to_be_hidden()
    button.click()
    expect(button).to_have_attribute("aria-expanded", "true")
    expect(panel).to_be_visible()
    if click_focuses(page):  # in Safari the click gives the button no focus (#498)
        expect(button).to_be_focused()  # a pointer leaves the focus on the button
    presets = panel.locator("button[data-speed]")
    expect(presets).to_have_text([f"{n}{TIMES}" for n in ("0.75", "1", "1.25", "1.5", "1.75", "2")])
    expect(presets.nth(1)).to_have_attribute("aria-pressed", "true")
    check_axe(page, "player, speed panel open")
    page.emulate_media(color_scheme="dark")
    check_axe(page, "player, speed panel open, dark")
    page.emulate_media(color_scheme="light")
    panel.get_by_role("button", name=f"2{TIMES}", exact=True).click()
    assert rate(page)["rate"] == 2
    assert rate(page)["pitch"] is True
    expect(button).to_have_text(f"Speed 2.00{TIMES}")
    expect(presets.nth(5)).to_have_attribute("aria-pressed", "true")
    expect(presets.nth(1)).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#speed-exact")).to_have_value("2.00")
    expect(panel).to_be_visible()  # it stays open while the person tries speeds
    # a click elsewhere closes it
    page.locator(".nowplaying").click()
    expect(panel).to_be_hidden()
    expect(button).to_have_attribute("aria-expanded", "false")


def test_the_speed_stays_across_chapters_and_jumps(signed_in: Page, live: Live) -> None:
    page = signed_in
    make_audiobook(page, live)
    choose_speed(page, "1.5\u00d7")
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
    choose_speed(page, "2\u00d7")
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


def test_the_speed_field_by_keyboard(signed_in: Page, live: Live) -> None:
    """The arrows step 0.01, the Page keys 0.10, Home and End reach the limits; Slower and
    Faster step 0.05 and stay usable at a limit; Esc closes the panel and gives the focus back."""
    page = signed_in
    make_audiobook(page, live)
    page.locator("#audio").focus()
    while page.evaluate("() => document.activeElement.id") != "speed":
        page.keyboard.press(tab_key(page))
    page.keyboard.press("Enter")  # by keyboard the panel opens with the focus in the field
    field = page.get_by_role("spinbutton", name="Exact speed")
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-valuemin", "0.50")
    expect(field).to_have_attribute("aria-valuemax", "3.00")
    for key, value in (
        ("ArrowUp", "1.01"),
        ("ArrowUp", "1.02"),
        ("PageUp", "1.12"),
        ("ArrowDown", "1.11"),
        ("PageDown", "1.01"),
        ("End", "3.00"),
        ("ArrowUp", "3.00"),
        ("Home", "0.50"),
        ("ArrowDown", "0.50"),
    ):
        page.keyboard.press(key)
        expect(field).to_have_value(value)
        expect(field).to_have_attribute("aria-valuenow", value)
        expect(field).to_have_attribute("aria-valuetext", f"{value}{TIMES}")
        assert rate(page)["rate"] == float(value), key
    # at the slowest, Slower says so and keeps the focus; Faster steps 0.05
    slower = page.get_by_role("button", name="Slower")
    faster = page.get_by_role("button", name="Faster")
    expect(slower).to_have_attribute("aria-disabled", "true")
    slower.focus()
    page.keyboard.press("Enter")
    expect(slower).to_be_focused()
    expect(field).to_have_value("0.50")
    faster.focus()
    page.keyboard.press("Enter")
    expect(field).to_have_value("0.55")
    expect(slower).to_have_attribute("aria-disabled", "false")
    assert rate(page)["rate"] == 0.55
    # Esc closes the panel, gives the focus to the button and leaves the speed
    page.keyboard.press("Escape")
    expect(page.locator("#speed-panel")).to_be_hidden()
    expect(page.locator("#speed")).to_be_focused()
    expect(page.locator("#speed")).to_have_text(f"Speed 0.55{TIMES}")
    # Tab out of the open panel closes it too
    page.keyboard.press("Enter")
    expect(field).to_be_focused()
    for _ in range(2):  # to Faster, then out of the panel
        page.keyboard.press(tab_key(page))
    expect(page.locator("#speed-panel")).to_be_hidden()


def test_a_typed_speed(signed_in: Page, live: Live) -> None:
    """Typed with a point or a comma, with or without a times sign, used on Enter or on leaving the
    field;
    out of range it is the nearest limit; text that is no number is marked, its hint shown,
    and the last speed comes back when the field is left."""
    page = signed_in
    make_audiobook(page, live)
    page.locator("#speed").click()
    field = page.locator("#speed-exact")
    hint = page.locator("#speed-exact-hint")
    expect(hint).to_be_hidden()
    expect(hint).to_have_text("Type a number from 0.50 to 3.00, such as 1.07.")
    for typed, value in (
        ("1.07", "1.07"),
        ("1,37", "1.37"),
        ("2.4\u00d7", "2.40"),
        (" 0.8 x", "0.80"),
        ("9", "3.00"),
        ("0.1", "0.50"),
        ("1.234", "1.23"),
        (".75", "0.75"),
    ):
        field.fill(typed)
        field.press("Enter")
        expect(field, typed).to_have_value(value)
        assert rate(page)["rate"] == float(value), typed
    field.fill("1.6")
    page.locator("#speed-panel").get_by_role("button", name="Faster").click()  # leaves the field
    expect(field).to_have_value("1.65")
    for wrong in ("abc", "-1", "1,2,3", "1 5"):
        field.fill(wrong)
        expect(field, wrong).to_have_attribute("aria-invalid", "true")
        expect(hint).to_be_visible()
        assert rate(page)["rate"] == 1.65, wrong
    check_axe(page, "player, a speed that is no number")
    field.press("Enter")  # nothing is used
    assert rate(page)["rate"] == 1.65
    field.blur()
    expect(field).to_have_value("1.65")
    expect(field).not_to_have_attribute("aria-invalid", "true")
    expect(hint).to_be_hidden()


def test_the_speed_helpers_read_round_and_write_speeds(signed_in: Page, live: Live) -> None:
    """app.js's parseSpeed, roundSpeed and speedText, on a table of cases."""
    page = signed_in
    make_audiobook(page, live)
    parsed = page.evaluate(
        "texts => texts.map(t => { const v = parseSpeed(t); return isNaN(v) ? null : v; })",
        [
            "1",
            "1.07",
            "1,07",
            "1,07\u00d7",
            "1.07x",
            "1.07X",
            " 2 ",
            ".5",
            "1.",
            "007",
            "",
            " ",
            ",",
            "x",
            "-1",
            "+1",
            "1e2",
            "1,2,3",
            "1..2",
            "1 5",
            "\u00d71",
            "1000",
            "Infinity",
        ],
    )
    assert parsed == [
        1,
        1.07,
        1.07,
        1.07,
        1.07,
        1.07,
        2,
        0.5,
        1,
        7,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]
    rounded = page.evaluate(
        "pairs => pairs.map(v => roundSpeed(v, 0.5, 3))",
        [0.1, 0.5, 0.504, 0.505, 1.07 + 0.01, 1.1 + 0.05, 2.999, 3, 7, 1.125],
    )
    assert rounded == [0.5, 0.5, 0.5, 0.51, 1.08, 1.15, 3, 3, 3, 1.13]
    assert page.evaluate("[1, 0.5, 1.07, 2.4, 3].map(speedText)") == [
        "1.00",
        "0.50",
        "1.07",
        "2.40",
        "3.00",
    ]


def test_the_speed_is_kept_for_the_next_listen_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    page.locator("#speed").click()
    field = page.locator("#speed-exact")
    with page.expect_response("**/api/v1/player/speed") as answer:
        field.fill("1.37")
        field.press("Enter")
    assert answer.value.status == 200
    cookies = {c["name"]: c for c in page.context.cookies()}
    kept = cookies[PLAYER_SPEED_COOKIE]
    assert kept["value"] == "1.37"
    assert kept["httpOnly"] is True
    assert kept["sameSite"] == "Strict"
    page.goto(f"{live.url}/documents/{document}/listen")
    expect(page.locator("#speed")).to_have_text(f"Speed 1.37{TIMES}")
    expect(page.locator("#speed-exact")).to_have_value("1.37")
    page.wait_for_function("() => document.getElementById('audio').playbackRate === 1.37")
    # a preset is pressed only when the speed is exactly it
    pressed = page.locator("#speed-panel button[aria-pressed='true']")
    expect(pressed).to_have_count(0)


def test_the_speed_in_german(signed_in: Page, live: Live) -> None:
    """The German page writes and reads the decimal comma (D-290); a point is read too."""
    page = signed_in
    document = make_audiobook(page, live)
    listen = f"/documents/{document}/listen"
    page.goto(f"{live.url}/language?language=de&back={listen}")
    page.wait_for_url(live.url + listen)
    button = page.locator("#speed")
    expect(button).to_have_text(f"Tempo 1,00{TIMES}")
    button.click()
    field = page.get_by_role("spinbutton", name="Genaues Tempo")
    expect(field).to_have_value("1,00")
    field.fill("1,07")
    field.press("Enter")
    expect(field).to_have_value("1,07")
    expect(field).to_have_attribute("aria-valuetext", f"1,07{TIMES}")
    assert rate(page)["rate"] == 1.07
    field.fill("1.5")
    field.press("Enter")
    expect(field).to_have_value("1,50")
    presets = page.locator("#speed-panel button[data-speed]")
    expect(presets).to_have_text([f"{n}{TIMES}" for n in ("0,75", "1", "1,25", "1,5", "1,75", "2")])
    expect(presets.nth(3)).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Schneller").click()
    expect(field).to_have_value("1,55")
    field.fill("zwei")
    expect(page.locator("#speed-exact-hint")).to_have_text(
        "Geben Sie eine Zahl von 0,50 bis 3,00 ein, etwa 1,07."
    )
    check_axe(page, "player, German speed field")


def test_the_speed_stays_on_the_m4b(signed_in: Page, live: Live) -> None:
    """An audiobook with only an M4B (written by the command line with MP3s off) plays one
    file: the chosen speed stays when a jump moves within it."""
    page = signed_in
    document = make_audiobook(page, live)
    work = live.state.store.get(document).folder
    record = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    # the project's own audiobook folder (D-749), and its M4B as the download builds it
    folder, m4b = built_m4b(live, document)
    for name in record["files"]["mp3"]:
        (folder / name).unlink()
    record["files"]["mp3"] = []
    record["files"]["m4b"] = m4b
    (work / "audio.json").write_text(json.dumps(record), encoding="utf-8")
    readalong = folder / record["files"]["readalong"]
    data = json.loads(readalong.read_text(encoding="utf-8"))
    data["m4b"] = m4b
    for chapter in data["chapters"]:
        chapter["mp3"] = None
    readalong.write_text(json.dumps(data), encoding="utf-8")
    page.reload()
    player = page.evaluate("() => JSON.parse(document.getElementById('player-data').textContent)")
    assert player["mode"] == "m4b"
    choose_speed(page, "0.75\u00d7")
    page.locator(".chapter-button").nth(1).click()
    page.get_by_role("button", name="Next sentence").click()
    state = rate(page)
    assert str(state["src"]).endswith(".m4b")
    assert state["rate"] == 0.75
    assert state["pitch"] is True
