"""The library and the rail's shelf in the browser (#389, D-664): a full table read by axe in
both schemes and in German at the design's widths, the paste box by keyboard, the table
scrolling in its own region at 320 px, and "Continue listening" opening the player at the
saved time without playing (#153, D-300)."""

from __future__ import annotations

import io
import json
import re

from playwright.sync_api import Page, expect
from test_keyboard import press_on
from test_player import chunk_id, make_audiobook, paused
from test_remove import opened
from test_shell import WIDTHS, scrolls_sideways
from web_helpers import pdf_bytes

from conftest import Live, check_axe
from sci2audio.web.library import About, write_about


def full_library(live: Live) -> None:
    """A document in each state the table shows, with long names and a record each."""
    plain = opened(live, "not-analysed.pdf", "A note.")
    analysed = live.state.store.store("checked.pdf", io.BytesIO(pdf_bytes("Checked.")))
    (analysed.report_file.parent).mkdir(parents=True, exist_ok=True)
    analysed.report_file.write_text("{}", encoding="utf-8")
    write_about(
        analysed.folder,
        About(
            "A rather long title about sleep, reaction times and the naps after lunch",
            ("A. Writer", "B. Other", "C. Third"),
            12,
        ),
    )
    ready = opened(live, "ready.pdf", "Ready.", audiobook=True)
    del plain, ready


def test_the_full_library_passes_axe_in_both_schemes_and_languages(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    full_library(live)
    for width, height in WIDTHS.items():
        page.set_viewport_size({"width": width, "height": height})
        page.goto(live.url + "/")
        expect(page.locator("#documents tbody tr")).to_have_count(3)
        check_axe(page, f"library, {width} px")
    page.goto(f"{live.url}/language?language=de&back=/")
    expect(page.get_by_role("heading", level=1)).to_have_text("Bibliothek")
    expect(page.get_by_role("columnheader", name="Gehört")).to_be_visible()
    check_axe(page, "de: library")
    page.goto(f"{live.url}/language?language=en&back=/")


def test_the_empty_library_and_its_specimen(signed_in: Page, live: Live) -> None:
    page = signed_in
    expect(page.get_by_role("heading", name="Your library is empty")).to_be_visible()
    expect(page.locator(".specimen .cut").first).to_have_text("(Smith et al., 2020)")
    family = page.locator(".specimen p").first.evaluate("p => getComputedStyle(p).fontFamily")
    assert family.split(",")[0].strip().strip("\"'") == "Literata", family
    check_axe(page, "library, empty")


def test_pasted_text_opens_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    press_on(page, "Or paste text")  # the disclosure opens with Enter
    expect(page.get_by_label("Text to open")).to_be_visible()
    page.keyboard.press("Tab")
    page.keyboard.type("Pasted words for the keyboard test.")
    page.keyboard.press("Tab")
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.type("Typed notes")
    press_on(page, "Open the text")
    page.wait_for_url(re.compile(r"/documents/[0-9a-f]{16}"))
    expect(page.get_by_role("heading", level=1)).to_contain_text("Typed notes.txt")


def test_the_table_scrolls_in_its_own_region_at_320_px(signed_in: Page, live: Live) -> None:
    page = signed_in
    full_library(live)
    page.set_viewport_size({"width": 320, "height": 640})
    page.goto(live.url + "/")
    expect(page.locator("#documents tbody tr")).to_have_count(3)
    assert not scrolls_sideways(page)
    region = page.locator("#library")
    assert region.evaluate("r => r.scrollWidth > r.clientWidth")  # the table itself scrolls
    region.focus()  # and can be scrolled by keyboard
    page.keyboard.press("ArrowRight")
    page.wait_for_function("() => document.getElementById('library').scrollLeft > 0")
    check_axe(page, "library at 320 px")


def test_no_highlighter_on_the_librarys_chips(signed_in: Page, live: Live) -> None:
    page = signed_in
    full_library(live)
    page.goto(live.url + "/")
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        colours = page.locator(".papers .chip").evaluate_all(
            """chips => {
                const probe = document.createElement("span");
                document.body.append(probe);
                const hl = ["--hl-read", "--hl-note", "--hl-quote", "--hl-card", "--hl-mark"]
                    .map((name) => { probe.style.color = `var(${name})`;
                                     return getComputedStyle(probe).color; });
                probe.remove();
                return chips.flatMap((c) => {
                    const s = getComputedStyle(c);
                    return [s.color, s.backgroundColor, s.borderTopColor]
                        .filter((x) => hl.includes(x));
                });
            }"""
        )
        assert colours == [], scheme
        icons = page.locator(".papers .chip svg").count()
        assert icons == page.locator(".papers .chip").count() == 3  # an icon and a word each
    page.emulate_media(color_scheme="light")


def test_continue_listening_opens_the_player_paused_at_the_saved_time(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    document = make_audiobook(page, live)
    later = chunk_id(page, "We measured it twice.")
    page.locator(f"#{later}").click()  # chapter 2
    page.wait_for_function("() => !document.getElementById('audio').paused")
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_function("() => document.getElementById('audio').paused")
    page.wait_for_timeout(300)  # the save on pause reaches the server
    kept = json.loads((live.config.work_root / document / "position.json").read_text("utf-8"))

    page.goto(live.url + "/settings")  # any page: the shelf leads with it (D-664)
    item = page.locator("#shelf-continue")
    expect(item).to_contain_text("Continue listening")
    expect(item).to_contain_text("paper")  # the title the analysis found (about.json)
    expect(item).to_contain_text("Continue from 0:")
    expect(item).to_have_attribute("href", f"/documents/{document}/listen#continue")
    check_axe(page, "settings with Continue listening on the shelf")
    item.click()
    page.wait_for_url(f"{live.url}/documents/{document}/listen")  # the #continue is taken
    expect(page.locator("#resume")).to_have_count(0)  # the offer was taken at once
    expect(page.get_by_role("button", name="Play")).to_be_focused()
    page.wait_for_function("() => document.getElementById('audio').currentTime > 0")
    assert paused(page)  # never plays by itself (D-300)
    time = page.evaluate(
        "() => { const d = JSON.parse(document.getElementById('player-data').textContent);"
        " const a = document.getElementById('audio');"
        " return a.currentTime + d.chapters[1].offset; }"
    )
    assert abs(time - kept["time"]) < 1.0, (time, kept)  # within one sentence
    expect(page.locator("#shelf-continue")).to_have_attribute("aria-current", "page")
