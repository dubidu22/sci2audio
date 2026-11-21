"""Removing a document in the browser (#120, D-359 to D-362, #470): by keyboard alone, with
axe-core on every new page state, in English and German, and without a sideways scroll at
320 pixels. The request goes out as the page's own `fetch`, so the origin check (D-194)
lets it through, and carries the "keep" tick (D-751, S14)."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect
from test_keyboard import press_on
from test_reflow import WIDTH, check_reflow
from web_helpers import pdf_bytes

from conftest import Live, check_axe
from sci2audio.web.player import write_record
from sci2audio.web.project import (
    AudiobookFile,
    AudiobookFolder,
    audiobook_folder,
    read_project,
    record_files,
    write_project,
)
from sci2audio.web.removal import KEPT_LIMIT

EARLIER = "sci2audio made it before each document had its own folder."


def opened(live: Live, name: str, text: str, *, audiobook: bool = False) -> str:
    """A document put in place as the server keeps it; with the records of an audiobook
    made before #469, flat in the output folder."""
    document = live.state.store.store(name, io.BytesIO(pdf_bytes(text)))
    if audiobook:
        (document.folder / "audio.json").write_text("{}", encoding="utf-8")
        write_record(document.folder, document.id, live.config.output_folder)
    return document.id


def with_book(live: Live, name: str, text: str) -> tuple[str, Path]:
    """A document whose audiobook sits in its project's own folder, recorded (#469)."""
    document = live.state.store.store(name, io.BytesIO(pdf_bytes(text)))
    folder = audiobook_folder(document.folder, document.id, name, live.config.output_folder)
    written = [folder / "01 Introduction.mp3", folder / "book.readalong.json"]
    for path in written:
        path.write_bytes(b"ID3 " + path.name.encode())
    (document.folder / "audio.json").write_text("{}", encoding="utf-8")
    write_record(document.folder, document.id, folder)
    record_files(document.folder, document.id, folder, written)
    return document.id, folder


def test_removing_from_the_start_page_by_keyboard(signed_in: Page, live: Live) -> None:
    page = signed_in
    first = opened(live, "first.pdf", "The first note.", audiobook=True)
    second = opened(live, "second.pdf", "The second note.")
    page.goto(live.url + "/")
    check_axe(page, "start page, disclosures closed")

    press_on(page, "Remove first.pdf…")
    button = page.get_by_role("button", name="Remove first.pdf now")
    expect(button).to_be_visible()
    stays = f"Your earlier audiobook in {live.config.output_folder} stays: {EARLIER}"
    expect(page.get_by_text(stays)).to_be_visible()
    check_axe(page, "start page, disclosure open")
    press_on(page, "Remove first.pdf now")

    message = page.locator("#message")
    expect(message).to_have_text(
        f"first.pdf was removed. Your earlier audiobook in {live.config.output_folder} stays: "
        + EARLIER
    )
    expect(message).to_be_focused()
    expect(page.get_by_role("link", name="first.pdf")).to_have_count(0)
    expect(page.get_by_role("link", name="second.pdf")).to_be_visible()
    assert not (live.config.work_root / first).exists()
    assert (live.config.work_root / second / "source" / "second.pdf").is_file()
    check_axe(page, "start page after a removal")

    press_on(page, "Remove second.pdf…")
    press_on(page, "Remove second.pdf now", key="Space")
    expect(message).to_have_text("second.pdf was removed.")
    expect(message).to_be_focused()
    expect(page.locator("#documents")).to_have_count(0)
    expect(page.get_by_role("heading", name="Your library is empty")).to_be_visible()
    check_axe(page, "start page, the last document removed")


def test_removing_from_the_document_page(signed_in: Page, live: Live) -> None:
    page = signed_in
    document = opened(live, "paper.pdf", "A paper.", audiobook=True)
    page.goto(f"{live.url}/documents/{document}")
    expect(page.get_by_role("heading", name="Remove this document")).to_be_visible()
    page.get_by_text("Remove this document…").click()
    check_axe(page, "document page, removal open")
    requests: list[dict[str, str]] = []
    page.on(
        "request",
        lambda request: (
            requests.append({"method": request.method, **request.headers})
            if request.method == "DELETE"
            else None
        ),
    )
    page.get_by_role("button", name="Remove paper.pdf now").click()

    title = page.get_by_role("heading", name="paper.pdf was removed.")
    expect(title).to_be_focused()
    stays = f"Your earlier audiobook in {live.config.output_folder} stays: {EARLIER}"
    expect(page.locator("#removed-text")).to_have_text(stays)
    expect(page.locator("#step-check")).to_have_count(0)
    expect(page.locator("#make")).to_have_count(0)
    assert [r["method"] for r in requests] == ["DELETE"]  # one request
    assert not (live.config.work_root / document).exists()
    check_axe(page, "document page after the removal")
    page.get_by_role("link", name="Back to the library").click()
    expect(page).to_have_url(live.url + "/")
    expect(page.get_by_role("heading", name="Your library is empty")).to_be_visible()


def test_a_failed_removal_says_why_and_keeps_the_button(signed_in: Page, live: Live) -> None:
    page = signed_in
    opened(live, "stuck.pdf", "A stuck note.")
    page.goto(live.url + "/language?language=de&back=/")
    expect(page.locator("html")).to_have_attribute("lang", "de")

    def refuse(route: Route) -> None:
        if route.request.method != "DELETE":
            route.continue_()
            return
        route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps(
                {"error": "remove-failed", "message": "could not remove /x/chunks/ab/c.wav"}
            ),
        )

    page.route(re.compile(r".*/api/v1/documents/[0-9a-f]{16}(\?.*)?$"), refuse)
    page.get_by_text("stuck.pdf entfernen …").click()
    button = page.get_by_role("button", name="stuck.pdf jetzt entfernen")
    button.click()
    message = page.locator("#message")
    expect(message).to_contain_text("sci2audio konnte das Dokument nicht ganz entfernen.")
    expect(message.locator("span[lang=en]")).to_have_text("could not remove /x/chunks/ab/c.wav")
    expect(message).to_be_focused()
    expect(button).not_to_have_attribute("aria-disabled", "true")
    expect(page.get_by_role("link", name="stuck.pdf")).to_be_visible()
    check_axe(page, "start page, removal failed (German)")


@pytest.mark.parametrize("language", ["en", "de"])
def test_the_removal_reflows_at_320_pixels(signed_in: Page, live: Live, language: str) -> None:
    page = signed_in
    long_name = "averylongfilenamewithoutanyspaceorhyphenatallfromajournal" * 2 + ".pdf"
    document = opened(live, long_name, "A note with a long name.", audiobook=True)
    page.set_viewport_size({"width": WIDTH, "height": 800})
    page.goto(f"{live.url}/language?language={language}&back=/")
    expect(page.locator("html")).to_have_attribute("lang", language)
    page.locator("details.remove summary").click()
    check_reflow(page, f"start page, removal open ({language})")
    page.goto(f"{live.url}/documents/{document}")
    page.locator("details.remove summary").click()
    check_reflow(page, f"document page, removal open ({language})")
    page.locator("button.remove-now").click()
    expect(page.locator("#removed-title")).to_be_focused()
    check_reflow(page, f"document page, removed ({language})")


# ---- the project's own audiobook files (#470, D-751, D-754, S14) ---------------------------


def deletes(page: Page) -> list[str]:
    found: list[str] = []
    page.on("request", lambda r: found.append(r.url) if r.method == "DELETE" else None)
    return found


def test_the_audiobook_files_go_by_default(signed_in: Page, live: Live) -> None:
    page = signed_in
    document, folder = with_book(live, "paper.pdf", "A paper.")
    page.goto(f"{live.url}/documents/{document}")
    page.get_by_text("Remove this document…").click()
    box = page.locator("details.remove .remove-box")
    expect(box.get_by_text(f"The 2 audiobook files in {folder} go too:")).to_be_visible()
    keep = page.get_by_role("checkbox", name="Keep the audiobook files")
    expect(keep).not_to_be_checked()
    expect(box.get_by_role("button")).to_have_count(1)  # no safe button beside it (D-733)
    check_axe(page, "document page, removal with audiobook files open")
    urls = deletes(page)
    page.get_by_role("button", name="Remove paper.pdf now").click()
    expect(page.locator("#removed-title")).to_be_focused()
    expect(page.locator("#removed-text")).to_have_text("Its 2 audiobook files were deleted.")
    assert [u.split("?", 1)[1] for u in urls] == ["keep_audiobook=false"]
    assert not folder.exists()


def test_the_keep_tick_goes_with_the_request_and_outlives_a_failure(
    signed_in: Page, live: Live
) -> None:
    page = signed_in
    document, folder = with_book(live, "kept.pdf", "A kept paper.")
    (folder / "my notes.txt").write_text("mine", encoding="utf-8")
    page.goto(f"{live.url}/language?language=de&back=/")
    expect(page.locator("html")).to_have_attribute("lang", "de")
    failing = [True]

    def first_fails(route: Route) -> None:
        if route.request.method == "DELETE" and failing and failing.pop():
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"error": "remove-failed", "message": "could not delete x"}),
            )
            return
        route.continue_()

    page.route(re.compile(r".*/api/v1/documents/[0-9a-f]{16}(\?.*)?$"), first_fails)
    urls = deletes(page)
    # by the keys alone: after a click on the summary WebKit tabs on from the summary
    # without a focus ring, which `tab_to` rightly refuses
    press_on(page, "kept.pdf entfernen …")
    keep = page.get_by_role("checkbox", name="Hörbuchdateien behalten")
    press_on(page, f"remove-keep-{document}", key="Space")
    expect(keep).to_be_checked()
    button = page.get_by_role("button", name="kept.pdf jetzt entfernen")
    button.click()
    message = page.locator("#message")
    expect(message).to_contain_text("sci2audio konnte das Dokument nicht ganz entfernen.")
    expect(keep).to_be_checked()  # the box keeps its state for the next try
    button.click()
    expect(message).to_have_text(f"kept.pdf wurde entfernt. Ihr Hörbuch bleibt in {folder}.")
    assert [u.split("?", 1)[1] for u in urls] == ["keep_audiobook=true"] * 2
    assert sorted(p.name for p in folder.iterdir()) == [
        "01 Introduction.mp3",
        "book.readalong.json",
        "my notes.txt",
    ]


def test_more_files_stay_than_the_answer_names_and_all_are_counted(
    signed_in: Page, live: Live
) -> None:
    """The message counts the files the answer only counts (`kept_more`, #569)."""
    page = signed_in
    _document, folder = with_book(live, "many.pdf", "A paper with many notes.")
    mine = KEPT_LIMIT + 3
    for n in range(mine):
        (folder / f"mine {n:03}.txt").write_text("mine", encoding="utf-8")
    page.goto(live.url + "/")
    page.get_by_text("Remove many.pdf…").click()
    page.get_by_role("button", name="Remove many.pdf now").click()
    expect(page.locator("#message")).to_have_text(
        f"many.pdf was removed. Its 2 audiobook files were deleted. {mine} files stayed in "
        f"{folder}: sci2audio did not write them, or they changed since."
    )
    assert len(list(folder.iterdir())) == mine


def test_files_that_stay_are_counted_after_the_removal(signed_in: Page, live: Live) -> None:
    page = signed_in
    document, folder = with_book(live, "mixed.pdf", "A mixed paper.")
    (folder / "my notes.txt").write_text("mine", encoding="utf-8")
    (folder / "01 Introduction.mp3").write_bytes(b"ID3 changed by the person")
    # a second recorded folder that is now a link: it stays whole and is not counted as a file
    elsewhere = live.config.output_folder.parent / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "book.mp3").write_bytes(b"ID3 elsewhere")
    linked = live.config.output_folder / "mixed (2)"
    linked.symlink_to(elsewhere, target_is_directory=True)
    work = live.config.work_root / document
    project = read_project(work, document)
    assert project is not None
    entry = AudiobookFile("book.mp3", 13, hashlib.sha256(b"ID3 elsewhere").hexdigest())
    write_project(
        work, replace(project, audiobooks=(*project.audiobooks, AudiobookFolder(linked, (entry,))))
    )
    page.goto(live.url + "/")
    page.get_by_text("Remove mixed.pdf…").click()
    expect(page.get_by_text(f"in {folder} go too")).to_be_visible()
    expect(page.get_by_text(f"in {linked} goes too")).to_have_count(0)  # a link: nothing goes
    page.get_by_role("button", name="Remove mixed.pdf now").click()
    expect(page.locator("#message")).to_have_text(
        f"mixed.pdf was removed. Its audiobook file was deleted. 2 files stayed in {folder}: "
        "sci2audio did not write them, or they changed since. "
        f"The folder {linked} was left as it is: "
        "sci2audio could not be sure it is still the audiobook folder it made."
    )  # the folder is named, and only files are counted (#569)
    assert (elsewhere / "book.mp3").read_bytes() == b"ID3 elsewhere"
    assert sorted(p.name for p in folder.iterdir()) == ["01 Introduction.mp3", "my notes.txt"]
    check_axe(page, "start page after a removal that kept files")
