"""The Captures page's files (#399, ADR-008 2.1 item 7, D-850): Zotero (RIS), Obsidian
(Markdown) and the table (CSV), each saved into a folder typed beside it; a file already
there is replaced only after "Replace it", "Keep it" and Escape leave it; a folder that is
not there is named. By keyboard, with axe in light, dark and German, reduced motion, no
highlighter on a button, and at 1440 and 1280 px."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, expect
from test_captures_page import HIGHLIGHTERS, captured, open_captures

from conftest import Live, check_axe, tab_key


def folder_of(live: Live) -> Path:
    folder = Path(live.config.work_root).parent / "exports"
    folder.mkdir(exist_ok=True)
    return folder


def state(page: Page, form: str) -> object:
    return page.locator(f"#export-state-{form}")


def test_save_ask_before_replacing_keep_and_a_missing_folder(signed_in: Page, live: Live) -> None:
    page = signed_in
    captured(page, live)
    open_captures(page)
    folder = folder_of(live)
    aside = page.locator("#capture-export")
    expect(aside.get_by_role("heading", level=2)).to_have_text("Save as files")
    expect(page.locator("#export-count")).to_have_text("Saves the 3 captures shown.")
    # the filters choose what is saved
    page.locator('.cap-kinds button[data-kind="quote"]').click()
    expect(page.locator("#export-count")).to_have_text("Saves the capture shown.")
    page.locator('.cap-kinds button[data-kind="all"]').click()
    expect(page.locator("#export-count")).to_have_text("Saves the 3 captures shown.")
    # each folder field is named by its target
    for form, name in (("ris", "Zotero"), ("md", "Obsidian"), ("csv", "Table")):
        expect(page.locator(f"#export-folder-{form}")).to_have_accessible_name(f"Folder {name}")
    # Zotero: saved into the folder typed
    page.locator("#export-folder-ris").fill(str(folder))
    save = page.locator("#export-save-ris")
    expect(save).to_have_text("Save RIS file")
    save.click()
    expect(state(page, "ris")).to_have_text(f"Saved as Captures.ris in {folder}.")
    expect(state(page, "ris")).to_have_attribute("data-state", "saved")
    target = folder / "Captures.ris"
    assert target.read_bytes().startswith(b"TY  - GEN\r\n")
    # again: the file is there, so the target asks, and nothing is written yet
    target.write_bytes(b"mine")
    save.click()
    ask = page.locator("#export-ask-ris")
    expect(ask).to_be_visible()
    expect(page.locator("#export-ask-ris-title")).to_have_text(
        "Captures.ris is in this folder already."
    )
    expect(page.locator("#export-ask-ris-title")).to_be_focused()
    assert target.read_bytes() == b"mine"
    ask.get_by_role("button", name="Keep it").click()
    expect(ask).to_be_hidden()
    expect(state(page, "ris")).to_have_text("Nothing saved. Captures.ris stays as it was.")
    expect(save).to_be_focused()
    assert target.read_bytes() == b"mine"
    # only "Replace it" replaces it
    save.click()
    ask.get_by_role("button", name="Replace it").click()
    expect(state(page, "ris")).to_have_text(f"Saved as Captures.ris in {folder}.")
    assert target.read_bytes().startswith(b"TY  - GEN\r\n")
    expect(save).to_be_focused()
    # Obsidian into a folder that is not there: named, nothing made
    missing = folder / "not-there"
    page.locator("#export-folder-md").fill(str(missing))
    page.locator("#export-save-md").click()
    expect(state(page, "md")).to_contain_text("Not saved. That folder does not exist")
    expect(state(page, "md")).to_have_attribute("data-state", "failed")
    assert not missing.exists()
    # the table, in the default folder: the audiobook folder
    expect(page.locator("#export-folder-csv")).to_have_value(str(live.config.output_folder))
    page.locator("#export-folder-csv").fill(str(folder))
    page.locator("#export-save-csv").click()
    expect(state(page, "csv")).to_have_text(f"Saved as Captures.csv in {folder}.")
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv", "Captures.ris"]
    assert live.outside == []  # no request left the test server


def test_the_files_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    captured(page, live)
    open_captures(page)
    folder = folder_of(live)
    key = tab_key(page)
    field = page.locator("#export-folder-md")
    field.fill(str(folder))
    page.keyboard.press(key)
    expect(page.locator("#export-save-md")).to_be_focused()
    page.keyboard.press("Enter")
    expect(state(page, "md")).to_have_text(f"Saved as Captures.md in {folder}.")
    # Enter in the field saves too; the file is there, so the question comes, Escape keeps
    field.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#export-ask-md-title")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#export-ask-md")).to_be_hidden()
    expect(state(page, "md")).to_have_text("Nothing saved. Captures.md stays as it was.")
    expect(page.locator("#export-save-md")).to_be_focused()
    # the question's buttons in order: Replace it, then Keep it
    (folder / "Captures.md").write_text("mine", encoding="utf-8")
    page.keyboard.press("Enter")
    expect(page.locator("#export-ask-md-title")).to_be_focused()
    page.keyboard.press(key)
    expect(page.get_by_role("button", name="Replace it")).to_be_focused()
    page.keyboard.press(key)
    expect(page.get_by_role("button", name="Keep it")).to_be_focused()
    page.keyboard.press("Shift+" + key)
    page.keyboard.press("Enter")
    expect(state(page, "md")).to_have_text(f"Saved as Captures.md in {folder}.")
    assert (folder / "Captures.md").read_text(encoding="utf-8").startswith("# ")


def test_axe_in_light_dark_and_german_with_the_question_open(signed_in: Page, live: Live) -> None:
    page = signed_in
    captured(page, live)
    open_captures(page)
    folder = folder_of(live)
    (folder / "Captures.csv").write_bytes(b"mine")
    page.locator("#export-folder-csv").fill(str(folder))
    page.locator("#export-save-csv").click()
    expect(page.locator("#export-ask-csv")).to_be_visible()
    page.locator("#export-folder-md").fill("not a full path")
    page.locator("#export-save-md").click()
    expect(state(page, "md")).to_contain_text("Not saved. Type a full path for the folder.")
    check_axe(page, "captures, the files with a question and a refusal")  # light and dark
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.goto(f"{live.url}/captures")
    expect(page.locator("#capture-export h2")).to_have_text("Als Dateien speichern")
    expect(page.locator("#export-count")).to_have_text("Speichert die 3 gezeigten Fundstücke.")
    expect(page.locator("#export-csv h3")).to_have_text("Tabelle")
    expect(state(page, "csv")).to_have_text("Noch nicht gespeichert")
    page.locator("#export-folder-csv").fill(str(folder))
    page.locator("#export-save-csv").click()
    expect(state(page, "csv")).to_have_text(f"Gespeichert als Fundstücke.csv in {folder}.")
    page.locator("#export-save-csv").click()
    expect(page.locator("#export-ask-csv-title")).to_have_text(
        "Fundstücke.csv liegt schon in diesem Ordner."
    )
    expect(page.get_by_role("button", name="Ersetzen")).to_be_visible()
    expect(page.get_by_role("button", name="Behalten")).to_be_visible()
    check_axe(page, "captures, the files, German")
    page.set_extra_http_headers({})


def test_reduced_motion_no_highlighter_and_every_state_with_an_icon(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    captured(page, live)
    page.emulate_media(reduced_motion="reduce")
    open_captures(page)
    folder = folder_of(live)
    page.locator("#export-folder-ris").fill(str(folder))
    page.locator("#export-save-ris").click()
    expect(state(page, "ris")).to_have_attribute("data-state", "saved")
    page.locator("#export-save-ris").click()
    expect(page.locator("#export-ask-ris")).to_be_visible()
    page.locator("#export-folder-csv").fill(str(folder / "gone"))
    page.locator("#export-save-csv").click()
    expect(state(page, "csv")).to_have_attribute("data-state", "failed")
    assert page.evaluate("() => document.getAnimations().length") == 0
    durations = page.evaluate(
        """() => [...document.querySelectorAll('#capture-export *')]
            .map((e) => getComputedStyle(e).transitionDuration)"""
    )
    assert set(durations) <= {"0s"}, set(durations)
    page.emulate_media(reduced_motion="no-preference")
    highlighters = set(page.evaluate(HIGHLIGHTERS))
    colours = page.evaluate(
        """() => [...document.querySelectorAll('#capture-export, #capture-export *')]
            .flatMap((e) => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color])"""
    )
    assert not set(colours) & highlighters
    # every state: an icon and a word (saved, never, failed, and the question)
    for form in ("ris", "md", "csv"):
        expect(state(page, form).locator("svg")).to_have_count(1)
        expect(state(page, form)).not_to_be_empty()
    expect(page.locator("#export-ask-ris > svg")).to_have_count(1)
    for target in page.locator("#capture-export .target").all():
        expect(target.locator("h3 svg")).to_have_count(1)
        expect(target.locator("button[data-export] svg")).to_have_count(1)


def test_at_1440_and_1280_px_beside_the_list_and_below_it_when_narrower(
    signed_in: Page, live: Live
) -> None:
    """In light and dark, English and German."""
    page = signed_in
    frames = "() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))"
    captured(page, live)
    open_captures(page)
    for language in ("en", "de"):
        page.set_extra_http_headers({"Accept-Language": language})
        page.reload()
        page.wait_for_load_state("load")
        expect(page.locator("html")).to_have_attribute("lang", language)
        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            for width in (1440, 1280, 1024):
                where = (language, scheme, width)
                page.set_viewport_size({"width": width, "height": 900})
                page.evaluate(frames)
                fits = "() => document.documentElement.scrollWidth <= innerWidth"
                assert page.evaluate(fits), where
                rows = page.locator(".cap-main").bounding_box()
                aside = page.locator("#capture-export").bounding_box()
                assert rows is not None
                assert aside is not None
                if width >= 1280:
                    assert aside["x"] >= rows["x"] + rows["width"], where  # beside the list
                else:
                    assert aside["y"] >= rows["y"] + rows["height"], where  # under it
                for form in ("ris", "md", "csv"):
                    box = page.locator(f"#export-folder-{form}").bounding_box()
                    assert box is not None
                    assert box["x"] + box["width"] <= aside["x"] + aside["width"] + 1, where
    page.emulate_media(color_scheme="light")
    page.set_extra_http_headers({})
    page.set_viewport_size({"width": 1280, "height": 720})
