"""Captures saved as files from the Captures page (#399, ADR-008 2.1 item 7, D-850):
Markdown, RIS and CSV through `app.capture_export`, each into a folder the person types,
never over a file without their yes; the Library title, the PDF page where the sentence
starts, reading order by where the sentence is found, German headings, and the refusals
for a folder that is not there, can't be written or fills up."""

from __future__ import annotations

import csv
import errno
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf
from test_web_captures_api import capture, file_of, page_data, sentences
from test_web_captures_page import page
from test_web_player import make, work_of
from web_helpers import (
    ORIGIN,
    FakeClock,
    anonymous,
    browser,
    make_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    program,
)

from sci2audio.app import capture_export
from sci2audio.app.captures import CAPTURES
from sci2audio.core import Anchor
from sci2audio.web import create_app
from sci2audio.web.markers import finder
from sci2audio.web.player import load_document

pytestmark = pytest.mark.usefixtures("offline")

URL = "/api/v1/captures/export"


def two_pages() -> bytes:
    return make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Sleep came late on the first night.", 72, 100, size=11),
        ],
        [
            Text("Methods", 72, 80, size=14),
            Text("We measured reaction times twice.", 72, 100, size=11),
        ],
    )


@pytest.fixture
def studied(tmp_path: Path) -> dict[str, Any]:
    """Two documents: a PDF of two pages with a quote on page 2 set first, then a mark and
    a note on page 1 (stored out of reading order); a second PDF with a quote."""
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source(), clock=FakeClock())
    client = program(app, config)
    doc = make(client, two_pages(), "sleep.pdf")["doc"]["id"]
    data = page_data(client, doc)
    # each chapter's last sentence: the one after its heading
    on_one, on_two = (
        [n for n in sentences(data) if data["chunks"][n][2] == chapter][-1] for chapter in (0, 1)
    )
    quote = capture(client, doc, "quote", on_two, data["audiobook"])
    mark = capture(client, doc, "mark", on_one, data["audiobook"])
    note = capture(client, doc, "note", on_one, data["audiobook"], "=1+1, ask Sam.")
    assert "twice" in quote["sentence"]
    assert "first night" in mark["sentence"]
    ids = {"quote": quote["id"], "mark": mark["id"], "note": note["id"]}
    other = make(client, pdf_bytes("Work came early. Rest came never."), "other.pdf")["doc"]["id"]
    other_data = page_data(client, other)
    capture(client, other, "quote", sentences(other_data)[1], other_data["audiobook"])
    folder = tmp_path / "exports"
    folder.mkdir()
    return {
        "app": app,
        "client": client,
        "config": config,
        "doc": doc,
        "other": other,
        "ids": ids,
        "work": work_of(config, doc),
        "folder": folder,
    }


def export(client: Any, folder: Path | str, form: str, status: int = 201, **more: Any) -> Any:
    body = {"format": form, "folder": str(folder), **more}
    answer = client.post(URL, json=body)
    assert answer.status_code == status, answer.text
    return answer.json()


def sentence_of(work: Path, capture_id: str) -> str:
    found = next(c for c in file_of(work)["captures"] if c["id"] == capture_id)
    text: str = found["anchor"]["text"]
    return text


def rows_of(path: Path) -> list[list[str]]:
    data = path.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")  # Excel reads umlauts only with the mark
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))


def test_the_csv_holds_every_capture_in_reading_order_with_its_page_and_title(
    studied: dict[str, Any],
) -> None:
    client, folder, work, ids = (studied[k] for k in ("client", "folder", "work", "ids"))
    saved = export(client, folder, "csv")
    assert saved == {
        "file": "Captures.csv",
        "folder": str(folder),
        "path": str(folder / "Captures.csv"),
        "count": 4,
    }
    first, second = sentence_of(work, ids["mark"]), sentence_of(work, ids["quote"])
    header, *rows = rows_of(folder / "Captures.csv")
    assert header == ["document", "type", "page", "sentence", "text"]
    # the documents in the Library's order, as the page lists them
    listed = [g.one(tag="h2").text for g in page(client).all("capture-group")]
    assert listed == list(dict.fromkeys(row[0] for row in rows))
    # in each, by where the sentence is found, and on one sentence in the dock's order
    # (note, quote, mark); a formula start is guarded
    assert [row for row in rows if row[0] == "sleep.pdf"] == [
        ["sleep.pdf", "note", "1", first, "'=1+1, ask Sam."],
        ["sleep.pdf", "mark", "1", first, ""],
        ["sleep.pdf", "quote", "2", second, ""],
    ]
    assert [row[:3] for row in rows if row[0] == "other.pdf"] == [["other.pdf", "quote", "1"]]
    # the export writes into the chosen folder only, and changes no captures file
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]
    assert [c["id"] for c in file_of(work)["captures"]] == [ids["quote"], ids["mark"], ids["note"]]


def test_markdown_and_ris_hold_the_sentences_verbatim(studied: dict[str, Any]) -> None:
    client, folder, work, ids = (studied[k] for k in ("client", "folder", "work", "ids"))
    doc = studied["doc"]
    export(client, folder, "md", document=doc)
    export(client, folder, "ris", document=doc)
    first, second = sentence_of(work, ids["mark"]), sentence_of(work, ids["quote"])
    markdown = (folder / "sleep.pdf.md").read_text(encoding="utf-8")
    assert markdown == (
        f"# sleep.pdf\n\n## Note · p. 1\n\n> {first}\n\n=1+1, ask Sam.\n\n"
        f"## Mark · p. 1\n\n> {first}\n\n## Quote · p. 2\n\n> {second}\n"
    )
    ris = (folder / "sleep.pdf.ris").read_bytes().decode("utf-8")
    # a PDF's date is the file's, not one the document states: no PY
    assert ris == (
        "TY  - GEN\r\nTI  - sleep.pdf\r\n"
        f"N1  - Note · p. 1\r\n {first}\r\n \r\n =1+1, ask Sam.\r\n"
        f"N1  - Mark · p. 1\r\n {first}\r\n"
        f"N1  - Quote · p. 2\r\n {second}\r\nER  - \r\n"
    )
    export(client, folder, "ris")
    assert (folder / "Captures.ris").read_text(encoding="utf-8").count("TY  - GEN") == 2


def test_the_filters_choose_what_is_saved_and_one_document_names_the_file(
    studied: dict[str, Any],
) -> None:
    client, folder, other = studied["client"], studied["folder"], studied["other"]
    quotes = export(client, folder, "csv", type="quote")
    assert quotes["count"] == 2
    assert {row[1] for row in rows_of(folder / "Captures.csv")[1:]} == {"quote"}
    one = export(client, folder, "md", document=other)
    assert (one["file"], one["count"]) == ("other.pdf.md", 1)
    assert (folder / "other.pdf.md").read_text(encoding="utf-8").startswith("# other.pdf\n")
    none = export(client, folder, "ris", 422, document=other, type="mark")
    assert none["error"] == "export-empty"
    assert not (folder / "other.pdf.ris").exists()
    unknown = export(client, folder, "ris", 404, document="f" * 16)
    assert unknown["error"] == "not-found"
    refused = client.post(URL, json={"format": "apkg", "folder": str(folder)})
    assert refused.status_code == 422  # no Anki file (D-850)


def test_german_headings_and_file_name(studied: dict[str, Any]) -> None:
    client, folder = studied["client"], studied["folder"]
    client.cookies.set("sci2audio-language", "de")
    saved = export(client, folder, "md")
    assert saved["file"] == "Fundstücke.md"
    markdown = (folder / "Fundstücke.md").read_text(encoding="utf-8")
    assert "## Notiz · S. 1\n" in markdown
    assert "## Marke · S. 1\n" in markdown
    assert "## Zitat · S. 2\n" in markdown
    # the CSV's type column is data, the same in every language
    export(client, folder, "csv")
    assert {row[1] for row in rows_of(folder / "Fundstücke.csv")[1:]} == {"note", "mark", "quote"}


def test_a_file_there_is_replaced_only_on_a_yes(studied: dict[str, Any]) -> None:
    client, folder = studied["client"], studied["folder"]
    target = folder / "Captures.ris"
    target.write_bytes(b"mine")
    asked = export(client, folder, "ris", 409)
    assert asked["error"] == "export-exists"
    assert (asked["file"], asked["folder"]) == ("Captures.ris", str(folder))
    assert target.read_bytes() == b"mine"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.ris"]  # no partial file
    # a yes replaces only the file the answer named: without it, or for another file
    # (the filters or the folder changed since), the person is asked again
    for named in ("", "Captures.md", "other.pdf.ris"):
        again = export(client, folder, "ris", 409, overwrite=True, file=named)
        assert (again["error"], again["file"]) == ("export-exists", "Captures.ris")
        assert target.read_bytes() == b"mine"
    one = folder / "other.pdf.ris"
    one.write_bytes(b"also mine")
    other = studied["other"]
    yes_for_all = export(client, folder, "ris", 409, overwrite=True, file="Captures.ris",
                         document=other)  # fmt: skip
    assert yes_for_all["file"] == "other.pdf.ris"
    assert one.read_bytes() == b"also mine"
    export(client, folder, "ris", overwrite=True, file="Captures.ris")
    assert target.read_bytes().startswith(b"TY  - GEN\r\n")
    assert one.read_bytes() == b"also mine"


def test_a_capture_answer_names_the_pdf_page_where_its_sentence_starts(
    studied: dict[str, Any],
) -> None:
    """#888: the toast's page, as the files name it; a text document has none."""
    client, doc = studied["client"], studied["doc"]
    data = page_data(client, doc)
    on_one, on_two = (
        [n for n in sentences(data) if data["chunks"][n][2] == chapter][-1] for chapter in (0, 1)
    )
    assert capture(client, doc, "note", on_two, data["audiobook"], "Why?")["page"] == 2
    assert capture(client, doc, "quote", on_one, data["audiobook"])["page"] == 1
    text = make(client, b"Sleep came late. We measured it twice.\n", "note.txt")["doc"]["id"]
    text_data = page_data(client, text)
    answer = capture(client, text, "mark", sentences(text_data)[0], text_data["audiobook"])
    assert answer["page"] is None


def test_a_yes_for_another_file_asks_again_only_when_the_new_file_is_there(
    studied: dict[str, Any],
) -> None:
    """#975: the yes was for Captures.ris, the language changed since, so the request now
    writes Fundstücke.ris. With no such file it is written, never over anything; with one
    there the question names it, a file that exists."""
    client, folder = studied["client"], studied["folder"]
    (folder / "Captures.ris").write_bytes(b"mine")
    client.cookies.set("sci2audio-language", "de")
    saved = export(client, folder, "ris", overwrite=True, file="Captures.ris")
    assert saved["file"] == "Fundstücke.ris"
    assert (folder / "Fundstücke.ris").read_bytes().startswith(b"TY  - GEN\r\n")
    assert (folder / "Captures.ris").read_bytes() == b"mine"
    (folder / "Fundstücke.ris").write_bytes(b"also mine")
    again = export(client, folder, "ris", 409, overwrite=True, file="Captures.ris")
    assert (again["error"], again["file"]) == ("export-exists", "Fundstücke.ris")
    assert (folder / again["file"]).is_file()
    assert (folder / "Fundstücke.ris").read_bytes() == b"also mine"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.ris", "Fundstücke.ris"]


def test_a_new_file_that_appears_during_a_yes_for_another_is_never_replaced(
    studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#975: the yes was for another file, so the new one is written without `overwrite`,
    and one put there meanwhile is asked about, not replaced."""
    client, folder = studied["client"], studied["folder"]
    (folder / "Captures.ris").write_bytes(b"mine")
    real = capture_export.write_bytes_atomically

    def appears(target: Path, data: bytes, *, overwrite: bool) -> None:
        target.write_bytes(b"theirs")
        real(target, data, overwrite=overwrite)

    monkeypatch.setattr(capture_export, "write_bytes_atomically", appears)
    client.cookies.set("sci2audio-language", "de")
    asked = export(client, folder, "ris", 409, overwrite=True, file="Captures.ris")
    assert (asked["error"], asked["file"]) == ("export-exists", "Fundstücke.ris")
    assert (folder / "Fundstücke.ris").read_bytes() == b"theirs"


def refused_replace(
    monkeypatch: pytest.MonkeyPatch, *, windows: bool, code: int, winerror: int | None
) -> None:
    """Replacing refused after the folder took the new file's partial, as `windows` (or
    macOS and Linux) refuses it: `winerror` 32 is a sharing violation, 5 access denied, as
    Windows says while another program holds the file open (after the retries); a sticky
    folder or an immutable file gives EACCES or EPERM elsewhere (#990, #1003)."""
    from sci2audio.app import files
    from sci2audio.web import api

    def refused(partial: Path | str, target: Path | str) -> None:
        error = PermissionError(code, os.strerror(code), str(partial), None, str(target))
        error.winerror = winerror  # type: ignore[attr-defined]  # only Windows sets it
        raise error

    monkeypatch.setattr(files, "_replace_once", refused)
    monkeypatch.setattr(api, "_IS_WINDOWS", windows)


@pytest.mark.parametrize("winerror", [32, 33, 5])
def test_replacing_a_file_another_program_holds_open_names_the_file(
    studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch, winerror: int
) -> None:
    """#990: on Windows the file is held, not the folder refused; the old file stays."""
    client, folder = studied["client"], studied["folder"]
    target = folder / "Captures.csv"
    target.write_bytes(b"open in Excel")
    refused_replace(monkeypatch, windows=True, code=errno.EACCES, winerror=winerror)
    answer = export(client, folder, "csv", 423, overwrite=True, file="Captures.csv")
    assert answer["error"] == "export-file-held"
    assert (answer["file"], answer["folder"]) == ("Captures.csv", str(folder))
    assert "Captures.csv" in answer["message"]
    assert target.read_bytes() == b"open in Excel"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]  # no partial file


REFUSED_NOT_HELD = [
    pytest.param(False, errno.EACCES, None, id="posix-sticky-folder"),
    pytest.param(False, errno.EPERM, None, id="posix-immutable-file"),
    pytest.param(False, errno.EACCES, 32, id="posix-never-held"),
    pytest.param(True, errno.EACCES, None, id="windows-no-code"),
    pytest.param(True, errno.EACCES, 1920, id="windows-other-code"),
]


@pytest.mark.parametrize(("windows", "code", "winerror"), REFUSED_NOT_HELD)
def test_a_refused_replace_that_is_no_held_file_never_blames_another_program(
    studied: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    windows: bool,
    code: int,
    winerror: int | None,
) -> None:
    """#1003: on macOS and Linux an open file never blocks a replace, so a refusal there
    (a sticky folder, an immutable flag) names the file as refused, not held, and so does
    a Windows refusal that is no sharing violation. The old file stays, no partial."""
    client, folder = studied["client"], studied["folder"]
    target = folder / "Captures.csv"
    target.write_bytes(b"old")
    refused_replace(monkeypatch, windows=windows, code=code, winerror=winerror)
    answer = export(client, folder, "csv", 403, overwrite=True, file="Captures.csv")
    assert answer["error"] == "export-file-refused"
    assert (answer["file"], answer["folder"]) == ("Captures.csv", str(folder))
    assert "Captures.csv" in answer["message"]
    assert "program" not in answer["message"]
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="not as root")
def test_access_denied_on_windows_for_a_read_only_file_is_no_held_file(
    studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1003: Windows says access denied (5) for a read-only file too, which no program
    holds: that refusal names the file as refused."""
    client, folder = studied["client"], studied["folder"]
    target = folder / "Captures.csv"
    target.write_bytes(b"old")
    target.chmod(0o444)
    refused_replace(monkeypatch, windows=True, code=errno.EACCES, winerror=5)
    try:
        answer = export(client, folder, "csv", 403, overwrite=True, file="Captures.csv")
    finally:
        target.chmod(0o644)
    assert answer["error"] == "export-file-refused"
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="POSIX permissions, not as root"
)
def test_replacing_in_a_folder_it_may_not_write_into_names_the_folder(
    studied: dict[str, Any],
) -> None:
    """#990: a folder that refuses the new file is still the folder's fault."""
    client, folder = studied["client"], studied["folder"]
    target = folder / "Captures.csv"
    target.write_bytes(b"old")
    folder.chmod(0o500)
    try:
        refused = export(client, folder, "csv", 403, overwrite=True, file="Captures.csv")
    finally:
        folder.chmod(0o700)
    assert refused["error"] == "export-folder-refused"
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]


def test_a_folder_with_the_files_name_is_named_and_never_offered_to_replace(
    studied: dict[str, Any],
) -> None:
    client, folder = studied["client"], studied["folder"]
    (folder / "Captures.md").mkdir()
    (folder / "Captures.md" / "inside.txt").write_text("kept", encoding="utf-8")
    for yes in ({}, {"overwrite": True, "file": "Captures.md"}):
        answer = export(client, folder, "md", 422, **yes)
        assert answer["error"] == "export-name-is-folder"
    assert (folder / "Captures.md" / "inside.txt").read_text(encoding="utf-8") == "kept"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.md"]


def test_a_path_too_long_is_named(studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def too_long(target: Path, data: bytes, *, overwrite: bool) -> None:
        raise OSError(errno.ENAMETOOLONG, "File name too long", str(target))

    monkeypatch.setattr(capture_export, "write_bytes_atomically", too_long)
    folder = studied["folder"]
    assert export(studied["client"], folder, "md", 422)["error"] == "export-name-too-long"
    assert list(folder.iterdir()) == []


def test_a_sentence_split_over_a_page_break_has_the_page_where_it_starts(
    tmp_path: Path,
) -> None:
    """The layout reads the sentence as two blocks, the second, on page 2, holding most of
    it: the finder places it there, but the export names page 1, where it starts."""
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source(), clock=FakeClock())
    client = program(app, config)
    pdf = make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Sleep came first. The effect held after", 72, 100, size=11),
        ],
        [
            Text("controlling for age, caffeine, the season and the time of day in", 72, 100),
            Text("every one of the groups of shift workers we followed for a year.", 72, 114),
        ],
    )
    doc = make(client, pdf, "split.pdf")["doc"]["id"]
    work = work_of(config, doc)
    document = load_document(work)
    texts = [block.text for block in document.blocks]
    first = next(n for n, text in enumerate(texts) if text.endswith("held after"))
    second = next(n for n, text in enumerate(texts) if text.startswith("controlling"))
    assert first < second  # two blocks: the finder goes across them
    sentence = f"The effect held after {texts[second]}"
    assert len(texts[second]) > len("The effect held after")
    data = page_data(client, doc)
    capture(client, doc, "quote", sentences(data)[1], data["audiobook"])
    stored = file_of(work)
    stored["captures"][0]["anchor"] = {
        "block": second,
        "start": 0,
        "end": len(texts[second]),
        "text": sentence,
    }
    (work / CAPTURES).write_text(json.dumps(stored), encoding="utf-8")
    assert finder(document)(Anchor(second, 0, len(texts[second]), sentence)) == (
        first,
        texts[first].index("The effect"),
    )
    folder = tmp_path / "exports"
    folder.mkdir()
    export(client, folder, "csv")
    (row,) = rows_of(folder / "Captures.csv")[1:]
    assert (row[2], row[3]) == ("1", sentence)


@pytest.mark.parametrize(
    ("folder", "status", "kind"),
    [
        ("", 422, "export-folder-needed"),
        ("exports", 422, "export-folder-needed"),
        ("~/exports", 422, "export-folder-needed"),
    ],
)
def test_a_folder_that_is_not_a_full_path_is_refused(
    studied: dict[str, Any], folder: str, status: int, kind: str
) -> None:
    assert export(studied["client"], folder, "md", status)["error"] == kind


def test_a_missing_folder_or_a_file_in_its_place_is_named(studied: dict[str, Any]) -> None:
    client, folder = studied["client"], studied["folder"]
    gone = export(client, folder / "not-there", "md", 422)
    assert gone["error"] == "export-folder-missing"
    assert not (folder / "not-there").exists()  # never made
    a_file = folder / "a-file"
    a_file.write_text("x", encoding="utf-8")
    assert export(client, a_file, "md", 422)["error"] == "export-folder-missing"
    nul = client.post(URL, json={"format": "md", "folder": f"{folder}\x00x"})
    assert nul.status_code == 422
    body = json.dumps({"format": "md", "folder": f"{folder}/\ud800"})  # escaped as \ud800
    surrogate = client.post(URL, content=body, headers={"content-type": "application/json"})
    assert (surrogate.status_code, surrogate.json()["error"]) == (422, "invalid")
    assert sorted(p.name for p in folder.iterdir()) == ["a-file"]


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="POSIX permissions, not as root"
)
def test_a_folder_it_may_not_write_into_is_named(studied: dict[str, Any]) -> None:
    folder = studied["folder"]
    folder.chmod(0o500)
    try:
        refused = export(studied["client"], folder, "csv", 403)
    finally:
        folder.chmod(0o700)
    assert refused["error"] == "export-folder-refused"
    assert list(folder.iterdir()) == []


def test_a_full_disk_leaves_no_file_and_says_so(
    studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from sci2audio.app import files

    def full(partial: Path, content: str | bytes) -> None:
        assert isinstance(content, bytes)
        partial.write_bytes(content[: len(content) // 2])
        raise OSError(errno.ENOSPC, "No space left on device", str(partial))

    monkeypatch.setattr(files, "_write_partial", full)
    folder = studied["folder"]
    answer = export(studied["client"], folder, "md", 507)
    assert answer["error"] == "disk-full"
    assert list(folder.iterdir()) == []
    # replacing on a yes: the old file stays as it was
    (folder / "Captures.csv").write_bytes(b"old")
    export(studied["client"], folder, "csv", 507, overwrite=True, file="Captures.csv")
    assert (folder / "Captures.csv").read_bytes() == b"old"
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.csv"]


def test_the_folder_removed_during_the_write_is_named(
    studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = studied["folder"]
    real = capture_export.write_bytes_atomically

    def vanish(target: Path, data: bytes, *, overwrite: bool) -> None:
        folder.rmdir()
        real(target, data, overwrite=overwrite)

    monkeypatch.setattr(capture_export, "write_bytes_atomically", vanish)
    assert export(studied["client"], folder, "csv", 422)["error"] == "export-folder-missing"
    assert not folder.exists()


def test_another_failure_says_nothing_was_half_written(
    studied: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(target: Path, data: bytes, *, overwrite: bool) -> None:
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(capture_export, "write_bytes_atomically", broken)
    folder = studied["folder"]
    assert export(studied["client"], folder, "ris", 500)["error"] == "export-failed"
    assert list(folder.iterdir()) == []


def test_the_route_needs_the_token_and_the_origin(studied: dict[str, Any]) -> None:
    app, config, folder = studied["app"], studied["config"], studied["folder"]
    body = {"format": "md", "folder": str(folder)}
    assert anonymous(app).post(URL, json=body).status_code == 401
    foreign = browser(app, config).post(URL, json=body, headers={"Origin": "http://evil.test"})
    assert foreign.status_code == 403
    no_origin = browser(app, config).post(URL, json=body)
    assert no_origin.status_code == 403  # a cookie alone is not enough to write
    same = browser(app, config).post(URL, json=body, headers={"Origin": ORIGIN})
    assert same.status_code == 201
    assert sorted(p.name for p in folder.iterdir()) == ["Captures.md"]


def test_without_captures_nothing_is_saved(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    client = program(create_app(config), config)
    (tmp_path / "exports").mkdir()
    answer = export(client, tmp_path / "exports", "csv", 422)
    assert answer["error"] == "export-empty"
    assert list((tmp_path / "exports").iterdir()) == []


def test_an_unreadable_captures_file_is_left_out_and_left_as_it_is(
    studied: dict[str, Any],
) -> None:
    path = studied["work"] / CAPTURES
    path.write_text("{not json", encoding="utf-8")
    saved = export(studied["client"], studied["folder"], "csv")
    assert saved["count"] == 1  # the other document's quote
    assert path.read_text(encoding="utf-8") == "{not json"


# ---- the page ---------------------------------------------------------------------------


def test_the_page_offers_the_three_files_each_with_its_folder(studied: dict[str, Any]) -> None:
    client, config = studied["client"], studied["config"]
    root = page(client)
    aside = root.by_id("capture-export")
    assert aside is not None
    assert aside.one(tag="h2").text == "Save as files"
    count = aside.by_id("export-count")
    assert count is not None
    assert count.text == "Saves the 4 captures shown."
    targets = aside.all("target")
    assert [t.attrs.get("data-format") for t in targets] == ["ris", "md", "csv"]
    assert [t.one(tag="h3").text for t in targets] == ["Zotero", "Obsidian", "Table"]
    for target in targets:
        form = target.attrs["data-format"]
        field = target.by_id(f"export-folder-{form}")
        assert field is not None
        assert field.attrs.get("value") == str(config.output_folder)  # the audiobook folder
        button = target.by_id(f"export-save-{form}")
        assert button is not None
        assert "disabled" in button.attrs  # until the script is in (#350)
        state = target.by_id(f"export-state-{form}")
        assert state is not None
        assert state.text == "Not saved yet"
        assert state.all(tag="svg")  # an icon beside the word
    filtered = page(client, type="quote")
    count = filtered.by_id("export-count")
    assert count is not None
    assert count.text == "Saves the 2 captures shown."


def test_the_page_offers_no_export_without_captures(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    client = program(create_app(config), config)
    assert page(client).by_id("capture-export") is None


def test_the_export_in_german(studied: dict[str, Any]) -> None:
    client = studied["client"]
    client.cookies.set("sci2audio-language", "de")
    root = page(client)
    aside = root.by_id("capture-export")
    assert aside is not None
    assert aside.one(tag="h2").text == "Als Dateien speichern"
    assert [t.one(tag="h3").text for t in aside.all("target")] == ["Zotero", "Obsidian", "Tabelle"]
    state = aside.by_id("export-state-csv")
    assert state is not None
    assert state.text == "Noch nicht gespeichert"
