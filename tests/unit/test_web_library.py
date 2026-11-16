"""The library and the rail's shelf (#389, D-664): the two records of the web's own
(`opened.json`, `about.json`), how far an audiobook was heard, the words for times, the
library's rows with their chips, and the shelf's items. A record that is broken, too large,
a link or cannot be written never fails a page."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_helpers import ORIGIN, app_and_config, browser, paper_bytes, pdf_bytes, upload, wait
from web_helpers import offline as offline

from sci2audio.app import files
from sci2audio.core import SourceFormat
from sci2audio.testing.documents import make_document
from sci2audio.web import library, pages
from sci2audio.web.documents import StoredDocument
from sci2audio.web.jobs import JobKind, JobState
from sci2audio.web.library import (
    ABOUT,
    OPENED,
    About,
    Heard,
    about_of,
    heard,
    length_text,
    read_about,
    read_opened,
    when,
    write_about,
    write_opened,
)
from sci2audio.web.player import POSITION, Position, audiobook_stamp, write_position

pytestmark = pytest.mark.usefixtures("offline")

DOC = "fedcba9876543210"
NOW = datetime(2026, 11, 16, 9, 14, 0, tzinfo=UTC)
NBSP = "\N{NO-BREAK SPACE}"


# ---- opened.json ---------------------------------------------------------------------------


def test_opened_is_written_and_read_back(tmp_path: Path) -> None:
    write_opened(tmp_path, NOW)
    stored = json.loads((tmp_path / OPENED).read_text(encoding="utf-8"))
    assert stored == {
        "format": "sci2audio-web-opened",
        "version": 1,
        "opened": "2026-11-16T09:14:00+00:00",
    }
    assert read_opened(tmp_path) == NOW
    assert [p.name for p in tmp_path.iterdir()] == [OPENED]  # no partial file left


def test_a_reload_within_a_minute_writes_nothing(tmp_path: Path) -> None:
    write_opened(tmp_path, NOW)
    write_opened(tmp_path, NOW + timedelta(seconds=59))
    assert read_opened(tmp_path) == NOW
    write_opened(tmp_path, NOW + timedelta(seconds=60))
    assert read_opened(tmp_path) == NOW + timedelta(seconds=60)
    # a clock set back is not "within a minute": the record follows it
    write_opened(tmp_path, NOW - timedelta(days=1))
    assert read_opened(tmp_path) == NOW - timedelta(days=1)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        "[]",
        '{"format": "sci2audio-web-opened", "version": 2, "opened": "2026-11-16T09:14:00+00:00"}',
        '{"format": "something-else", "version": 1, "opened": "2026-11-16T09:14:00+00:00"}',
        '{"format": "sci2audio-web-opened", "version": 1, "opened": "yesterday"}',
        '{"format": "sci2audio-web-opened", "version": 1, "opened": 1763284440}',
        '{"format": "sci2audio-web-opened", "version": 1, "opened": "2026-11-16T09:14:00"}',
        '{"format": "sci2audio-web-opened", "version": 1}',
        '{"format": "sci2audio-web-opened", "version": 1, "opened": "'
        + "9" * library.RECORD_LIMIT
        + '"}',
    ],
)
def test_a_broken_opened_record_reads_as_nothing(tmp_path: Path, text: str) -> None:
    (tmp_path / OPENED).write_text(text, encoding="utf-8")
    assert read_opened(tmp_path) is None
    write_opened(tmp_path, NOW)  # and a new one replaces it
    assert read_opened(tmp_path) == NOW


def test_an_opened_record_that_is_a_link_or_a_folder_reads_as_nothing(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    write_opened(elsewhere, NOW)
    work = tmp_path / "work"
    work.mkdir()
    try:
        (work / OPENED).symlink_to(elsewhere / OPENED)
    except OSError:  # Windows without the right to make links
        pytest.skip("cannot make a symbolic link here")
    assert read_opened(work) is None
    (work / OPENED).unlink()
    (work / OPENED).mkdir()
    assert read_opened(work) is None
    write_opened(work, NOW)  # cannot replace a folder: logged, never raised
    assert read_opened(work) is None


def test_an_opened_record_that_cannot_be_written_is_left_and_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    write_opened(tmp_path, NOW)

    def full(*args: Any, **kwargs: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(library, "write_texts", full)
    with caplog.at_level(logging.WARNING, logger="sci2audio.web.library"):
        write_opened(tmp_path, NOW + timedelta(hours=1))
    assert "could not write opened.json" in caplog.text
    assert read_opened(tmp_path) == NOW  # the old record stays as it was


def test_a_missing_working_folder_reads_and_writes_nothing(tmp_path: Path) -> None:
    gone = tmp_path / "gone"
    assert read_opened(gone) is None
    write_opened(gone, NOW)  # write_texts makes no folders: nothing appears, nothing raises
    assert read_about(gone) is None


# ---- about.json ----------------------------------------------------------------------------


def test_about_is_written_and_read_back(tmp_path: Path) -> None:
    about = About("Sleep and reaction time", ("A. Writer", "B. Other"), 12)
    write_about(tmp_path, about)
    stored = json.loads((tmp_path / ABOUT).read_text(encoding="utf-8"))
    assert stored == {
        "format": "sci2audio-web-about",
        "version": 1,
        "title": "Sleep and reaction time",
        "authors": ["A. Writer", "B. Other"],
        "pages": 12,
    }
    assert read_about(tmp_path) == about
    write_about(tmp_path, About("Notes"))
    assert read_about(tmp_path) == About("Notes", (), None)


@pytest.mark.parametrize(
    "change",
    [
        {"format": "other"},
        {"version": 2},
        {"title": ""},
        {"title": "   "},
        {"title": 3},
        {"authors": "A. Writer"},
        {"authors": ["A. Writer", 2]},
        {"pages": 0},
        {"pages": "12"},
        {"pages": True},
        {"pages": 1.5},
    ],
)
def test_a_broken_about_record_reads_as_nothing(tmp_path: Path, change: dict[str, Any]) -> None:
    data = {"format": "sci2audio-web-about", "version": 1, "title": "T", "authors": [], "pages": 1}
    (tmp_path / ABOUT).write_text(json.dumps(data | change), encoding="utf-8")
    assert read_about(tmp_path) is None


def test_about_of_takes_the_title_the_authors_and_a_pdfs_pages() -> None:
    document = make_document([("paragraph", "Words.")], name="notes.txt")
    assert about_of(document) == About("notes", (), None)  # a text file: no page count
    content = document.content
    pdf = dataclasses.replace(
        document,
        content=dataclasses.replace(
            content,
            source=dataclasses.replace(content.source, name="paper.pdf", format=SourceFormat.PDF),
            metadata=dataclasses.replace(
                content.metadata, title="A Title", authors=(" A. Writer ", "", "B. Other")
            ),
        ),
    )
    assert about_of(pdf) == About("A Title", ("A. Writer", "B. Other"), len(content.pages))


# ---- how far it was heard ------------------------------------------------------------------


def audiobook(work: Path, folder: Path, document: str = DOC, duration: float = 100.0) -> str:
    """An audio record in `work` and its read-along file in `folder`; the file's stamp."""
    work.mkdir(parents=True, exist_ok=True)
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "format": "sci2audio-audio",
        "version": 1,
        "source": {"sha256": document + "0" * 48},
        "voice": "af_heart",
        "settings": {"switched_off": []},
        "duration": duration,
        "chunks": {"total": 10, "skipped": 0},
        "files": {"m4b": "Book.m4b", "mp3": [], "readalong": "Book.readalong.json"},
    }
    (work / "audio.json").write_text(json.dumps(record), encoding="utf-8")
    readalong = folder / "Book.readalong.json"
    readalong.write_text("{}", encoding="utf-8")
    return audiobook_stamp(readalong)


def test_heard_reads_the_position_against_the_audiobooks_stamp(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    stamp = audiobook(work, out)
    assert heard(work, DOC, (out,)) == Heard(100.0, None)  # not started
    write_position(work, DOC, stamp, Position(0, 38.0))
    got = heard(work, DOC, (None, tmp_path / "elsewhere", out))
    assert got == Heard(100.0, 38.0)
    assert got is not None
    assert got.fraction == pytest.approx(0.38)


def test_heard_ignores_a_position_for_another_audiobook_or_document(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    stamp = audiobook(work, out)
    write_position(work, DOC, "ffffffffffffffff", Position(0, 38.0))  # a rerun made a new one
    assert heard(work, DOC, (out,)) == Heard(100.0, None)
    write_position(work, "0000000000000000", stamp, Position(0, 38.0))
    assert heard(work, DOC, (out,)) == Heard(100.0, None)
    write_position(work, DOC, stamp, Position(0, 250.0))  # past the end
    assert heard(work, DOC, (out,)) == Heard(100.0, None)
    write_position(work, DOC, stamp, Position(0, 100.5))  # within the second the end rounds
    assert heard(work, DOC, (out,)) == Heard(100.0, 100.5)
    assert Heard(100.0, 100.5).fraction == 1.0


def test_heard_without_an_audiobook(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    assert heard(work, DOC, (out,)) is None  # no audio.json
    stamp = audiobook(work, out)
    write_position(work, DOC, stamp, Position(0, 10.0))
    assert heard(work, "0000000000000000", (out,)) is None  # the record is another file's
    (out / "Book.readalong.json").unlink()
    assert heard(work, DOC, (out,)) == Heard(100.0, None)  # the files went away
    assert heard(work, DOC, (Path("relative"),)) == Heard(100.0, None)
    (work / "audio.json").write_text("{broken", encoding="utf-8")
    assert heard(work, DOC, (out,)) is None
    assert Heard(0.0, 0.0).fraction is None


# ---- words for times -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, f"0{NBSP}min"),
        (1, f"1{NBSP}min"),
        (60, f"1{NBSP}min"),
        (61, f"2{NBSP}min"),
        (54 * 60, f"54{NBSP}min"),
        (3600, f"1{NBSP}h 00{NBSP}min"),
        (68 * 60, f"1{NBSP}h 08{NBSP}min"),
    ],
)
def test_an_audiobooks_length(seconds: float, text: str) -> None:
    assert length_text(seconds, "h", "min") == text


def local(*parts: int) -> datetime:
    """A time on this computer's clock, as the library shows it."""
    return datetime(*parts).astimezone()  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (local(2026, 11, 16, 9, 14), ("today", "09:14")),
        (local(2026, 11, 16, 0, 0), ("today", "00:00")),
        (local(2026, 11, 15, 18, 2), ("yesterday", "18:02")),
        (local(2026, 11, 15, 0, 1), ("yesterday", "00:01")),
        (local(2026, 11, 14, 23, 59), ("date", "2026-11-14")),
        (local(2026, 11, 12, 8, 0), ("date", "2026-11-12")),
        (local(2025, 3, 1, 8, 0), ("date", "2025-03-01")),
        (local(2026, 11, 17, 8, 0), ("date", "2026-11-17")),  # a clock set back
    ],
)
def test_when_something_happened(moment: datetime, expected: tuple[str, str]) -> None:
    now = local(2026, 11, 16, 21, 30)
    assert when(moment, now) == expected
    assert when(moment.astimezone(UTC), now.astimezone(UTC)) == expected  # stored as UTC


@pytest.mark.parametrize(
    ("language", "today", "yesterday"),
    [("en", "Today, 09:14", "Yesterday, 18:02"), ("de", "Heute, 09:14", "Gestern, 18:02")],
)
def test_the_opened_column_in_both_languages(
    monkeypatch: pytest.MonkeyPatch, language: str, today: str, yesterday: str
) -> None:
    from sci2audio.web.i18n import strings

    s = strings(language)
    now = local(2026, 11, 16, 21, 30)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return now.astimezone(tz)

    monkeypatch.setattr(pages, "datetime", Clock)
    assert pages._when_text(s, local(2026, 11, 16, 9, 14)) == today
    assert pages._when_text(s, local(2026, 11, 15, 18, 2)) == yesterday
    assert pages._when_text(s, local(2026, 3, 1, 8, 0)) == "2026-03-01"  # ISO (D-290)
    assert pages._when_text(s, local(2024, 12, 31, 8, 0)) == "2024-12-31"
    assert pages._when_text(s, None) == ""


# ---- the chips -----------------------------------------------------------------------------


def stored(tmp_path: Path, name: str = "paper.pdf") -> StoredDocument:
    folder = tmp_path / "work" / DOC
    (folder / "source").mkdir(parents=True)
    source = folder / "source" / name
    source.write_bytes(b"x")
    return StoredDocument(DOC, folder, source)


def board(current: Any = None, jobs: tuple[Any, ...] = ()) -> Any:
    return SimpleNamespace(board=SimpleNamespace(current=current, all=lambda: list(jobs)))


def job(kind: JobKind, state: JobState = JobState.RUNNING, document: str = DOC) -> Any:
    return SimpleNamespace(kind=kind, state=state, document=document)


def test_every_state_has_a_chip_with_an_icon_and_a_word(tmp_path: Path) -> None:
    from sci2audio.web.i18n import strings

    document = stored(tmp_path)
    assert pages._state_of(board(), document) == "new"
    document.report_file.parent.mkdir(parents=True)
    document.report_file.write_text("{}", encoding="utf-8")
    assert pages._state_of(board(), document) == "analysed"
    (document.folder / "audio.json").write_text("{}", encoding="utf-8")
    assert pages._state_of(board(), document) == "ready"
    failed = job(JobKind.AUDIO, JobState.FAILED)
    assert pages._state_of(board(None, (failed,)), document) == "failed"
    # only this server's latest job on this document counts
    done = job(JobKind.SCRIPT, JobState.DONE)
    assert pages._state_of(board(None, (done, failed)), document) == "ready"
    other = job(JobKind.AUDIO, JobState.FAILED, "0000000000000000")
    assert pages._state_of(board(None, (other,)), document) == "ready"
    voices = job(JobKind.VOICES, JobState.FAILED, None)  # type: ignore[arg-type]
    assert pages._state_of(board(None, (voices,)), document) == "ready"
    assert pages._state_of(board(job(JobKind.SCRIPT)), document) == "analysing"
    assert pages._state_of(board(job(JobKind.AUDIO)), document) == "making"
    assert pages._state_of(board(job(JobKind.AUDIO, document="0" * 16)), document) == "ready"
    for language in ("en", "de"):
        s = strings(language)
        for key, (look, icon) in pages.CHIPS.items():
            assert s(f"library.state_{key}") != f"library.state_{key}", key
            assert look in ("making", "failed", "ready", "idle")  # never a highlighter
            assert icon


# ---- the library page ----------------------------------------------------------------------


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def client_of(server: tuple[FastAPI, Any]) -> TestClient:
    app, config = server
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN
    return client


def row_of(page: str, key: str) -> str:
    return page.split(f'<tr id="row-{key}"')[1].split("</tr>")[0]


def rail_of(page: str) -> str:
    return page.split('<nav class="rail"')[1].split("</nav>")[0]


def test_a_row_shows_the_title_the_meta_line_and_the_state(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, paper_bytes(), "sleep paper.pdf")
    row = row_of(client.get("/").text, doc["id"])
    assert f'<a class="title" href="/documents/{doc["id"]}">sleep paper.pdf</a>' in row
    assert 'class="meta"' not in row  # nothing known before the analysis
    assert '<span class="chip idle" data-state="new">' in row
    assert '<use href="#i-open"' in row  # an icon beside the word, never colour alone
    assert "no audiobook yet" in row  # the empty Listened cell, for a screen reader
    job = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]}).json()
    assert wait(client, job["id"])["state"] == "done"
    _app, config = server
    about = read_about(config.work_root / doc["id"])
    assert about is not None
    assert about.title == "sleep paper"  # the file gives no title
    assert about.pages == 1
    row = row_of(client.get("/").text, doc["id"])
    assert '<a class="title" href="/documents/' in row
    assert ">sleep paper</a>" in row
    assert '<span class="meta">1 page</span>' in row
    assert '<span class="chip idle" data-state="analysed">' in row
    assert "Checked, no audio yet" in row


def test_a_broken_about_record_falls_back_to_the_file_name(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    _app, config = server
    (config.work_root / doc["id"] / ABOUT).write_text("{nope", encoding="utf-8")
    page = client.get("/")
    assert page.status_code == 200
    assert ">paper.pdf</a>" in row_of(page.text, doc["id"])


def test_a_failed_script_job_does_not_fail_on_its_about_record(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")

    def full(*args: Any, **kwargs: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(library, "write_texts", full)
    job = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]}).json()
    assert wait(client, job["id"])["state"] == "done"  # the analysis stands
    assert ">paper.pdf</a>" in row_of(client.get("/").text, doc["id"])


def test_the_document_and_listen_pages_note_when_they_were_opened(
    server: tuple[FastAPI, Any],
) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    _app, config = server
    work = config.work_root / doc["id"]
    row = row_of(client.get("/").text, doc["id"])
    assert '<td class="when"></td>' in row  # never opened
    assert read_opened(work) is None
    before = datetime.now(UTC).replace(microsecond=0)
    assert client.get(f"/documents/{doc['id']}").status_code == 200
    opened = read_opened(work)
    assert opened is not None
    assert opened >= before
    row = row_of(client.get("/").text, doc["id"])
    assert re.search(r'<td class="when">Today, \d\d:\d\d</td>', row), row
    (work / OPENED).unlink()
    assert client.get(f"/documents/{doc['id']}/listen").status_code == 200  # no audiobook yet
    assert read_opened(work) is not None


@pytest.mark.parametrize("fault", ["broken", "huge", "folder", "unwritable", "gone"])
def test_a_page_never_fails_on_its_opened_record(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    _app, config = server
    path = config.work_root / doc["id"] / OPENED
    if fault == "broken":
        path.write_text("{", encoding="utf-8")
    elif fault == "huge":
        path.write_bytes(b" " * (library.RECORD_LIMIT + 1))
    elif fault == "folder":
        path.mkdir()
    elif fault == "unwritable":

        def refused(*args: Any, **kwargs: Any) -> None:
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(library, "write_texts", refused)
    elif fault == "gone":
        real = files.write_texts

        def removed(texts: Any, **kwargs: Any) -> None:  # the folder goes during the write
            for target in texts:
                for item in target.parent.iterdir():
                    if item.is_file():
                        item.unlink()
            real(texts, **kwargs)

        monkeypatch.setattr(library, "write_texts", removed)
    page = client.get("/")
    assert page.status_code == 200
    assert '<td class="when"></td>' in row_of(page.text, doc["id"])
    for address in (f"/documents/{doc['id']}", f"/documents/{doc['id']}/listen", "/"):
        assert client.get(address).status_code == 200, address
    cell = row_of(client.get("/").text, doc["id"])
    if fault in ("broken", "huge"):  # a new record took the broken one's place
        assert re.search(r'<td class="when">Today, \d\d:\d\d</td>', cell), cell
    elif fault != "gone":
        assert '<td class="when"></td>' in cell


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes anyway")
def test_a_read_only_working_folder_still_shows_the_pages(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    _app, config = server
    work = config.work_root / doc["id"]
    work.chmod(0o555)
    try:
        assert client.get(f"/documents/{doc['id']}").status_code == 200
        assert client.get("/").status_code == 200
        assert not (work / OPENED).exists()
    finally:
        work.chmod(0o755)


def test_a_running_job_shows_as_making_with_how_much_is_made(server: tuple[FastAPI, Any]) -> None:
    app, _ = server
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    gate = threading.Event()

    def work(job: Any) -> list[Path]:
        job.report({"phase": "speaking", "chunks_done": 16, "chunks_total": 25})
        gate.wait(10)
        return []

    state = app.state.sci2audio
    running = state.board.start(JobKind.AUDIO, doc["id"], None, work, cancellable=False)
    try:
        for _ in range(100):
            if running.snapshot().get("progress"):
                break
            threading.Event().wait(0.02)
        row = row_of(client.get("/").text, doc["id"])
        assert '<span class="chip making" data-state="making">' in row
        assert "Making audio" in row
        assert '<progress class="meter made" max="100" value="64"' in row
        assert f"64{NBSP}% made" in row
    finally:
        gate.set()
        running.join(10)


def test_an_audiobook_row_links_to_listen_and_shows_how_far(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    doc = upload(client, pdf_bytes(), "paper.pdf")
    _app, config = server
    work = config.work_root / doc["id"]
    stamp = audiobook(work, config.output_folder, doc["id"], duration=68 * 60)
    row = row_of(client.get("/").text, doc["id"])
    assert f'href="/documents/{doc["id"]}/listen"' in row
    assert '<span class="chip ready" data-state="ready">' in row
    assert f"1{NBSP}h 08{NBSP}min" in row
    assert "Not started" in row
    assert '<progress class="meter listened" max="100" value="0"' in row
    write_position(work, doc["id"], stamp, Position(0, 0.38 * 68 * 60))
    row = row_of(client.get("/").text, doc["id"])
    assert f"38{NBSP}% listened" in row
    assert '<progress class="meter listened" max="100" value="38"' in row


def test_a_german_library(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    client.cookies.set("sci2audio-language", "de")
    page = client.get("/").text
    assert "<h1>Bibliothek</h1>" in page
    assert "Ihre Bibliothek ist leer" in page
    assert '<div class="specimen" lang="de">' in page
    assert "Die Stimme ist noch nicht installiert." in page
    doc = upload(client, pdf_bytes(), "paper.pdf")
    client.get(f"/documents/{doc['id']}")
    page = client.get("/").text
    assert "1 Dokument auf diesem Computer" in page
    assert re.search(r'<td class="when">Heute, \d\d:\d\d</td>', row_of(page, doc["id"]))
    assert "Noch nicht analysiert" in row_of(page, doc["id"])


# ---- the shelf -----------------------------------------------------------------------------


def opened_at(config: Any, document: str, seconds: float) -> None:
    write_opened(config.work_root / document, NOW)
    os.utime(config.work_root / document / OPENED, (seconds, seconds))


def test_the_shelf_has_no_heading_while_it_holds_nothing(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    upload(client, pdf_bytes(), "paper.pdf")  # opened in no page yet
    rail = rail_of(client.get("/").text)
    assert "Reading and recent" not in rail
    assert 'class="shelf"' not in rail


def test_the_shelf_lists_the_three_documents_opened_last(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    ids = [upload(client, pdf_bytes(f"Text number {n}."), f"paper {n}.pdf")["id"] for n in range(5)]
    for n, key in enumerate(ids):
        opened_at(config, key, 1_700_000_000 + 100 * n)
    rail = rail_of(client.get("/").text)
    assert "Reading and recent" in rail
    shown = re.findall(r'<a href="/documents/([0-9a-f]{16})" class="recent"', rail)
    assert shown == [ids[4], ids[3], ids[2]]  # newest first, at most three
    assert rail.count('<span class="m">Not analysed yet</span>') == 3
    assert 'aria-current="page"' not in rail.split('class="shelf"')[1]
    # on a document's own page its item is the current one
    rail = rail_of(client.get(f"/documents/{ids[3]}").text)
    item = rail.split(f'<a href="/documents/{ids[3]}" class="recent"')[1].split(">")[0]
    assert 'aria-current="page"' in item
    shown = re.findall(r'<a href="/documents/([0-9a-f]{16})" class="recent"', rail)
    assert shown[0] == ids[3]  # just opened: now the newest


def test_continue_listening_leads_the_shelf(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    one = upload(client, pdf_bytes("One."), "one.pdf")["id"]
    two = upload(client, pdf_bytes("Two."), "two.pdf")["id"]
    stamp = audiobook(config.work_root / one, config.output_folder, one, duration=600.0)
    opened_at(config, one, 1_700_000_000)
    opened_at(config, two, 1_700_000_100)
    rail = rail_of(client.get("/").text)
    assert 'id="shelf-continue"' not in rail  # not started: nothing to continue
    assert f'href="/documents/{one}/listen" class="recent"' in rail
    assert '<span class="m">Not started</span>' in rail
    write_position(config.work_root / one, one, stamp, Position(0, 192.0))
    rail = rail_of(client.get("/").text)
    first = rail.split('class="shelf"')[1]
    assert first.index('id="shelf-continue"') < first.index("two.pdf")
    item = first.split('id="shelf-continue"')[0].rsplit("<a ", 1)[1]
    assert f'href="/documents/{one}/listen#continue"' in item
    assert "Continue from 3:12" in first
    assert '<progress class="meter listened" max="100" value="32"' in first
    assert f'href="/documents/{one}/listen" class="recent"' not in rail  # not twice
    # on its Listen page the item is the current one
    listen = rail_of(client.get(f"/documents/{one}/listen").text)
    assert 'id="shelf-continue" class="continue" aria-current="page"' in listen


def test_continue_listening_skips_an_ended_or_stale_position(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    one = upload(client, pdf_bytes("One."), "one.pdf")["id"]
    work = config.work_root / one
    stamp = audiobook(work, config.output_folder, one, duration=600.0)
    write_position(work, one, stamp, Position(0, 600.0))  # the end
    assert 'id="shelf-continue"' not in client.get("/").text
    write_position(work, one, "ffffffffffffffff", Position(0, 100.0))  # another audiobook
    assert 'id="shelf-continue"' not in client.get("/").text
    (work / POSITION).write_text("{", encoding="utf-8")
    assert client.get("/").status_code == 200
    assert 'id="shelf-continue"' not in client.get("/").text
