"""The library and the rail's shelf in the browser (#389, D-664): a full table read by axe in
both schemes and in German at the design's widths, the paste box by keyboard, the table
scrolling in its own region at 320 px, and "Continue listening" opening the player at the
saved time without playing (#153, D-300)."""

from __future__ import annotations

import io
import json
import re
import sys

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
    expect(page.get_by_role("heading", level=1)).to_have_text("Typed notes")


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
    assert page.evaluate("() => document.activeElement.id") == "library"
    if page.context.browser.browser_type.name == "webkit" and sys.platform == "darwin":  # type: ignore[union-attr]
        # WebKit on macOS, as Playwright drives it, scrolls no focused box with the arrow
        # keys; here the region is reached and focused, and the release's VoiceOver pass
        # scrolls it by keyboard on a Mac (as for the speed select, D-678)
        check_axe(page, "library at 320 px")
        return
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


def test_the_search_filters_as_the_person_types_and_works_without_the_script(
    signed_in: Page, live: Live
) -> None:
    """#416: by keyboard, case and accents aside; the GET form does the same without
    app.js; the counts stay those of every document."""
    page = signed_in
    full_library(live)
    page.goto(live.url + "/")
    rows = page.locator("#documents tbody tr")
    expect(rows).to_have_count(3)
    search = page.get_by_role("searchbox", name="Search titles, authors and file names")
    search.focus()
    page.keyboard.type("NAPS wríter")
    expect(rows.locator("visible=true")).to_have_count(1)
    expect(rows.locator("visible=true").locator(".title")).to_contain_text("naps after lunch")
    expect(page).to_have_url(re.compile(r"\?q=NAPS\+wr%C3%ADter$"))
    expect(page.locator("#library-count")).to_have_text("3 documents on this computer")
    check_axe(page, "library, filtered")
    page.keyboard.type("x")
    expect(page.locator("#no-match")).to_have_text("No document matches “NAPS wríterx”.")
    expect(page.locator("#library")).to_be_hidden()
    check_axe(page, "library, nothing found")
    for _ in "wríterx":
        page.keyboard.press("Backspace")
    page.keyboard.press("Backspace")
    page.keyboard.press("Enter")  # the form, with the script: filters, stays on the page
    expect(rows.locator("visible=true")).to_have_count(1)
    expect(page.locator("#no-match")).to_be_empty()
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    expect(rows.locator("visible=true")).to_have_count(3)
    expect(page).to_have_url(live.url + "/")
    # without the script: the server filters for the form's GET
    page.route(f"{live.url}/static/app.js", lambda route: route.abort())
    page.goto(live.url + "/")
    page.get_by_role("searchbox").fill("ready")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page).to_have_url(live.url + "/?q=ready")
    expect(rows.locator("visible=true")).to_have_count(1)
    expect(rows.locator("visible=true").locator(".title")).to_have_text("ready.pdf")
    page.get_by_role("searchbox").fill("zzz")
    page.get_by_role("searchbox").press("Enter")
    expect(page.locator("#no-match")).to_have_text("No document matches “zzz”.")
    page.unroute(f"{live.url}/static/app.js")


def drop_files(page: Page, files: list[tuple[str, bytes]]) -> None:
    """A synthetic drag of `files` onto the opener: enter, over, then drop."""
    data = page.evaluate_handle(
        """(files) => {
            const data = new DataTransfer();
            for (const [name, bytes] of files) {
              data.items.add(new File([new Uint8Array(bytes)], name));
            }
            return data;
        }""",
        [[name, list(content)] for name, content in files],
    )
    opener = page.locator("#open-file")
    opener.dispatch_event("dragenter", {"dataTransfer": data})
    opener.dispatch_event("dragover", {"dataTransfer": data})
    expect(opener).to_have_class(re.compile(r"\bover\b"))
    opener.dispatch_event("drop", {"dataTransfer": data})
    expect(opener).not_to_have_class(re.compile(r"\bover\b"))


def test_a_file_dropped_on_the_opener_opens_and_is_analysed(signed_in: Page, live: Live) -> None:
    """#417: one file opens as "Open and analyse" does; two files or a kind sci2audio
    cannot read give a message in the status region; leaving ends the `over` state."""
    page = signed_in
    page.goto(live.url + "/")
    expect(page.locator("#drop-hint")).to_be_visible()
    expect(page.locator("#drop-hint")).to_have_text("Or drop a file here.")
    opener = page.locator("#open-file")
    data = page.evaluate_handle(
        "() => { const d = new DataTransfer(); d.items.add(new File(['x'], 'a.txt')); return d; }"
    )
    opener.dispatch_event("dragenter", {"dataTransfer": data})
    expect(opener).to_have_class(re.compile(r"\bover\b"))
    opener.dispatch_event("dragleave", {"dataTransfer": data})
    expect(opener).not_to_have_class(re.compile(r"\bover\b"))
    message = page.locator("#message")
    drop_files(page, [("a.pdf", pdf_bytes("One.")), ("b.pdf", pdf_bytes("Two."))])
    expect(message).to_have_text("Drop one file at a time.")
    expect(message).to_be_focused()
    drop_files(page, [("program.exe", b"MZ not a document")])
    expect(message).to_contain_text("sci2audio can't read this kind of file.")
    assert live.state.store.all() == []
    drop_files(page, [("dropped.pdf", pdf_bytes("A dropped paper."))])
    page.wait_for_url(re.compile(r"/documents/[^/]+$"))
    expect(page.get_by_role("heading", level=1)).to_have_text(re.compile("dropped"))
    assert [document.name for document in live.state.store.all()] == ["dropped.pdf"]


def test_a_file_dropped_beside_the_opener_stays_out_of_the_tab(signed_in: Page, live: Live) -> None:
    """#446 review N1: a file dropped elsewhere on the library page would open in the tab
    and leave the app; the page cancels that drop and opens nothing."""
    page = signed_in
    page.goto(live.url + "/")
    expect(page.locator("#drop-hint")).to_be_visible()
    cancelled = page.evaluate(
        """() => {
            const data = new DataTransfer();
            data.items.add(new File(["x"], "beside.pdf"));
            const where = document.querySelector(".rail");
            const options = { dataTransfer: data, bubbles: true, cancelable: true };
            const fire = (type) => !where.dispatchEvent(new DragEvent(type, options));
            return [fire("dragover"), fire("drop")];
        }"""
    )
    assert cancelled == [True, True]  # the browser's own drop (open the file) is cancelled
    assert page.url == live.url + "/"
    assert live.state.store.all() == []
    # a drag that carries no file (text from the page) keeps the browser's own way
    text = page.evaluate(
        """() => {
            const data = new DataTransfer();
            data.setData("text/plain", "words");
            return !document.querySelector(".rail").dispatchEvent(
                new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true }));
        }"""
    )
    assert text is False


def test_without_the_script_the_hint_does_not_promise_dropping(signed_in: Page, live: Live) -> None:
    page = signed_in
    page.route(f"{live.url}/static/app.js", lambda route: route.abort())
    page.goto(live.url + "/")
    expect(page.locator("#file-hint")).to_be_visible()
    expect(page.locator("#drop-hint")).to_be_hidden()
    page.unroute(f"{live.url}/static/app.js")
