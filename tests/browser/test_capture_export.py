"""The Captures page's files (#399, ADR-008 2.1 item 7, D-850): Zotero (RIS), Obsidian
(Markdown) and the table (CSV), each saved into a folder typed beside it; a file already
there is replaced only after "Replace it", "Keep it" and Escape leave it; a folder that is
not there is named. By keyboard, with axe in light, dark and German, reduced motion, no
highlighter on a button, and at 1440 and 1280 px."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect
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


def test_replace_it_replaces_only_the_file_the_question_named(signed_in: Page, live: Live) -> None:
    """A question about folder A ends as kept when another folder is typed or the filters
    change, so its "Replace it" can never reach B's file or another file name; and the
    request it sends is the one asked about, with the file and folder the server named."""
    page = signed_in
    made = captured(page, live)
    open_captures(page)
    a, b = folder_of(live) / "a", folder_of(live) / "b"
    for folder in (a, b):
        folder.mkdir()
        (folder / "Captures.ris").write_bytes(b"mine")
        (folder / "paper.ris").write_bytes(b"mine too")
    field, save = page.locator("#export-folder-ris"), page.locator("#export-save-ris")
    ask = page.locator("#export-ask-ris")
    field.fill(str(a))
    save.click()
    expect(ask).to_be_visible()
    field.fill(str(b))  # another folder typed: the question was about A
    expect(ask).to_be_hidden()
    expect(state(page, "ris")).to_have_text("Nothing saved. Captures.ris stays as it was.")
    # a filter changed: the question was about what was shown before
    save.click()
    expect(ask).to_be_visible()
    page.locator("#capture-from").select_option(made["document"])
    expect(ask).to_be_hidden()
    page.locator('.cap-kinds button[data-kind="quote"]').click()
    save.click()
    expect(page.locator("#export-ask-ris-title")).to_have_text(
        "paper.ris is in this folder already."
    )
    page.locator('.cap-kinds button[data-kind="all"]').click()
    expect(ask).to_be_hidden()
    for folder in (a, b):
        assert (folder / "Captures.ris").read_bytes() == b"mine"
        assert (folder / "paper.ris").read_bytes() == b"mine too"
    # the yes sends the request asked about: B, the one document, quotes only
    page.locator('.cap-kinds button[data-kind="quote"]').click()
    save.click()
    with page.expect_request("**/api/v1/captures/export") as sent:
        ask.get_by_role("button", name="Replace it").click()
    assert sent.value.post_data_json == {
        "format": "ris",
        "folder": str(b),
        "type": "quote",
        "document": made["document"],
        "file": "paper.ris",
        "overwrite": True,
    }
    expect(state(page, "ris")).to_have_text(f"Saved as paper.ris in {b}.")
    assert (b / "paper.ris").read_bytes().startswith(b"TY  - GEN\r\n")
    assert (b / "Captures.ris").read_bytes() == b"mine"
    assert (a / "paper.ris").read_bytes() == b"mine too"


def test_an_answer_that_comes_after_the_folder_or_a_filter_changed_asks_nothing(
    signed_in: Page, live: Live
) -> None:
    """The request is held while the person types another folder or picks another type: the
    409 that then comes is about a request the page no longer shows, so no question opens
    and no "Replace it" can reach the old target."""
    page = signed_in
    captured(page, live)
    open_captures(page)
    a, b = folder_of(live) / "a", folder_of(live) / "b"
    for folder in (a, b):
        folder.mkdir()
        (folder / "Captures.ris").write_bytes(b"mine")
    held: list[Route] = []

    def hold(route: Route) -> None:
        held.append(route)

    page.route("**/api/v1/captures/export", hold)
    field, save = page.locator("#export-folder-ris"), page.locator("#export-save-ris")
    ask = page.locator("#export-ask-ris")
    kept = "Nothing saved. Captures.ris stays as it was."
    for change in ("folder", "type"):
        field.fill(str(a))
        save.click()
        expect(state(page, "ris")).to_have_text("Saving…")
        for _ in range(200):  # the handler runs while the page is waited on
            if held:
                break
            page.wait_for_timeout(25)
        assert len(held) == 1, change
        if change == "folder":
            field.fill(str(b))
        else:
            page.locator('.cap-kinds button[data-kind="quote"]').click()
        held.pop().continue_()
        expect(state(page, "ris")).to_have_text(kept)
        expect(ask).to_be_hidden()
        page.locator('.cap-kinds button[data-kind="all"]').click()
    page.unroute("**/api/v1/captures/export")
    for folder in (a, b):
        assert (folder / "Captures.ris").read_bytes() == b"mine"
    # unchanged while it was on its way: the question comes as before
    field.fill(str(a))
    save.click()
    expect(ask).to_be_visible()


def refuse_replace(monkeypatch: pytest.MonkeyPatch, *, windows: bool) -> None:
    """Replacing refused after the new file was written: on Windows as a sharing violation
    (winerror 32) while another program holds the file, elsewhere as a sticky folder or an
    immutable file refuses it (#990, #1003)."""
    from sci2audio.app import files
    from sci2audio.web import api

    def refused(partial: Path | str, target: Path | str) -> None:
        error = PermissionError(errno.EACCES, "Access is denied", str(partial), None, str(target))
        error.winerror = 32 if windows else None  # type: ignore[attr-defined]
        raise error

    monkeypatch.setattr(files, "_replace_once", refused)
    monkeypatch.setattr(api, "_IS_WINDOWS", windows)


def test_replacing_a_file_another_program_holds_open_names_the_file(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#990: "Replace it" on a file another program holds open (as Windows refuses it, no
    real Excel) names that file and asks to close it there; the old file stays."""
    page = signed_in
    captured(page, live)
    open_captures(page)
    folder = folder_of(live)
    target = folder / "Captures.csv"
    target.write_bytes(b"open in Excel")
    refuse_replace(monkeypatch, windows=True)
    page.locator("#export-folder-csv").fill(str(folder))
    page.locator("#export-save-csv").click()
    page.locator("#export-ask-csv").get_by_role("button", name="Replace it").click()
    expect(state(page, "csv")).to_contain_text(
        "Not saved. Captures.csv is probably open in another program, so it was not replaced"
        " and stays as it was. Close it there and try again."
    )
    expect(state(page, "csv")).not_to_contain_text("may not write into that folder")
    expect(state(page, "csv")).to_have_attribute("data-state", "failed")
    assert target.read_bytes() == b"open in Excel"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]
    check_axe(page, "captures, a file held open")


def test_a_replace_refused_on_macos_or_linux_blames_no_other_program(
    signed_in: Page, live: Live, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1003: an open file never blocks a replace there, so the page says the file may
    not be replaced, never that another program holds it; the old file stays. It names
    the file, as a file held open is named (#1014), in English and German."""
    page = signed_in
    captured(page, live)
    open_captures(page)
    folder = folder_of(live)
    target = folder / "Captures.csv"
    target.write_bytes(b"old")
    refuse_replace(monkeypatch, windows=False)
    page.locator("#export-folder-csv").fill(str(folder))
    page.locator("#export-save-csv").click()
    page.locator("#export-ask-csv").get_by_role("button", name="Replace it").click()
    expect(state(page, "csv")).to_contain_text(
        "Not saved. sci2audio may not replace Captures.csv, so it stays as it was."
    )
    expect(state(page, "csv")).not_to_contain_text("another program")
    expect(state(page, "csv")).to_have_attribute("data-state", "failed")
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]
    page.set_extra_http_headers({"Accept-Language": "de"})
    page.reload()
    page.wait_for_load_state("load")
    expect(page.locator("#export-save-csv")).to_be_enabled()  # the script is in
    german = folder / "Fundstücke.csv"  # the German name of a file of all documents
    german.write_bytes(b"alt")
    page.locator("#export-folder-csv").fill(str(folder))
    page.locator("#export-save-csv").click()
    page.locator("#export-ask-csv").get_by_role("button", name="Ersetzen").click()
    expect(state(page, "csv")).to_contain_text(
        "Nicht gespeichert. sci2audio darf Fundstücke.csv nicht ersetzen, daher bleibt sie,"
        " wie sie war."
    )
    expect(state(page, "csv")).not_to_contain_text("anderen Programm")
    assert german.read_bytes() == b"alt"
    check_axe(page, "captures, a replace refused, German")
    page.set_extra_http_headers({})


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
