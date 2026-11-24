"""The library and the rail's shelf (#389, D-664): the two records of the web's own
(`opened.json`, `about.json`), how far an audiobook was heard, the words for times, the
library's rows with their chips, and the shelf's items. A record that is broken, too large,
a link or cannot be written never fails a page."""

from __future__ import annotations

import dataclasses
import html
import json
import logging
import os
import re
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import time_ns
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_helpers import ORIGIN, app_and_config, browser, paper_bytes, pdf_bytes, upload, wait
from web_helpers import offline as offline

from sci2audio.app import files
from sci2audio.app.captures import CAPTURES, write_captures
from sci2audio.core import Anchor, Capture, CaptureFile, CaptureType, SourceFormat
from sci2audio.testing.documents import make_document
from sci2audio.web import library, pages, player
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
    matches,
    read_about,
    read_opened,
    search_text,
    when,
    write_about,
    write_opened,
)
from sci2audio.web.markers import MARKERS, Marker, markers_text
from sci2audio.web.markers import Anchor as MarkerAnchor
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
        # a record that would read well, but is larger than any record of ours
        '{"format": "sci2audio-web-opened", "version": 1, "opened": "2026-11-16T09:14:00+00:00"}'
        + " " * library.RECORD_LIMIT,
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


def readalong_text(duration: float) -> str:
    """A read-along file of one chapter and ten sentences, each followed by a pause: the
    first ends at 9 % of the book, the last at 99 %."""
    step = duration / 10
    chunks = [
        {"chapter": 0, "start": n * step, "end": n * step + 0.9 * step}
        | {"block": n, "start_char": 0, "end_char": 5}
        for n in range(10)
    ]
    chapter = {"title": "One", "mp3": None, "start": 0.0, "end": duration, "first_chunk": 0}
    data = {"format": "sci2audio-readalong", "version": 1, "sample_rate": 24000}
    data |= {"duration": duration, "m4b": "Book.m4b", "chapters": [chapter], "chunks": chunks}
    return json.dumps(data)


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
    readalong.write_text(readalong_text(duration), encoding="utf-8")
    return audiobook_stamp(readalong)


def test_heard_reads_the_position_against_the_audiobooks_stamp(tmp_path: Path) -> None:
    work, out = tmp_path / "work", tmp_path / "out"
    stamp = audiobook(work, out)
    assert heard(work, DOC, (out,)) == Heard(100.0, None)  # not started
    write_position(work, DOC, stamp, Position(0, 38.0))
    got = heard(work, DOC, (None, tmp_path / "elsewhere", out))
    assert got == Heard(100.0, 38.0, resume=True)
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
    assert heard(work, DOC, (out,)) == Heard(100.0, 100.5)  # heard to the end: no resume
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
    (work / "audio.json").write_text("{broken", encoding="utf-8")
    assert heard(work, DOC, (out,)) is None
    assert Heard(0.0, 0.0).fraction is None


def test_heard_offers_to_continue_only_where_the_listen_page_would(tmp_path: Path) -> None:
    """The shelf's Continue item takes Listen's condition (`read_position`): after the first
    sentence ended and before the last one ended, in the chapter the position names."""
    work, out = tmp_path / "work", tmp_path / "out"
    stamp = audiobook(work, out)  # sentences end at 9, 19, ... 99 s of 100 s
    data = player.load_readalong(out / "Book.readalong.json")
    # 99.0 is exactly where the last sentence ends: nothing left to continue (#430)
    cases = ((5.0, False), (9.0, True), (38.0, True), (98.9, True), (99.0, False), (99.5, False))
    for time, resume in cases:
        write_position(work, DOC, stamp, Position(0, time))
        assert heard(work, DOC, (out,)) == Heard(100.0, time, resume), time
        offered = player.read_position(work, DOC, stamp, data)
        assert (offered is not None) is resume, time
    write_position(work, DOC, stamp, Position(1, 38.0))  # a chapter the book does not have
    assert heard(work, DOC, (out,)) == Heard(100.0, 38.0, resume=False)
    assert player.read_position(work, DOC, stamp, data) is None


def test_the_bounds_of_a_fresh_read_along_file_are_read_again(tmp_path: Path) -> None:
    """The bounds are kept per (inode, mtime, size), which a rewrite in place within one
    clock tick keeps (#403): a file changed in the last two seconds is read each time."""
    path = tmp_path / "Book.readalong.json"
    first = readalong_text(100.0)
    path.write_text(first, encoding="utf-8")
    seen = os.stat(path).st_mtime_ns
    assert player.audiobook_bounds(path).duration == 100.0
    second = first.replace('"duration": 100.0', '"duration": 200.0', 1)
    assert len(second) == len(first)  # same size: only the time could tell them apart
    with path.open("r+", encoding="utf-8") as stream:  # in place: the same inode
        stream.write(second)
    os.utime(path, ns=(seen, seen))  # and the same time, as within one tick
    assert player.audiobook_bounds(path).duration == 200.0
    old = seen - 10 * player.RACY_NS  # long settled: kept
    os.utime(path, ns=(old, old))
    assert player.audiobook_bounds(path).duration == 200.0


def test_a_settled_read_along_file_made_again_gives_its_new_bounds(tmp_path: Path) -> None:
    """The bounds are kept per version of the file (inode, mtime, size): a settled file
    rewritten by a new Make, the same size and in place, but with another time, is read
    again (#430)."""
    path = tmp_path / "Book.readalong.json"
    first = readalong_text(100.0)
    path.write_text(first, encoding="utf-8")
    old = time_ns() - 10 * player.RACY_NS  # settled: its bounds are kept
    os.utime(path, ns=(old, old))
    assert player.audiobook_bounds(path).duration == 100.0
    second = first.replace('"duration": 100.0', '"duration": 200.0', 1)
    assert len(second) == len(first)  # same size and the same inode: only the time differs
    with path.open("r+", encoding="utf-8") as stream:
        stream.write(second)
    later = old + player.RACY_NS // 2  # still settled, but another version
    os.utime(path, ns=(later, later))
    assert player.audiobook_bounds(path).duration == 200.0


def test_heard_skips_a_relative_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The folders come from records and settings: a relative one would be read against
    wherever the server was started, so it is never tried, even where it would be found."""
    work, out = tmp_path / "work", tmp_path / "out"
    stamp = audiobook(work, out)
    write_position(work, DOC, stamp, Position(0, 38.0))
    monkeypatch.chdir(tmp_path)
    assert (Path("out") / "Book.readalong.json").is_file()  # it is there, seen from here
    assert heard(work, DOC, (Path("out"),)) == Heard(100.0, None)
    assert heard(work, DOC, (out,)) == Heard(100.0, 38.0, resume=True)


@pytest.mark.parametrize("time", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
def test_a_position_that_is_not_a_time_is_never_offered(
    server: tuple[FastAPI, Any], time: str
) -> None:
    """Python's json reads NaN and Infinity, and 1e400 as infinity: none is a time."""
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    work = config.work_root / doc
    stamp = audiobook(work, config.output_folder, doc)
    record = (
        f'{{"format": "sci2audio-web-position", "version": 1, "document": "{doc}", '
        f'"audiobook": "{stamp}", "chapter": 0, "time": {time}}}'
    )
    (work / POSITION).write_text(record, encoding="utf-8")
    page = client.get("/")
    assert page.status_code == 200
    assert 'id="shelf-continue"' not in page.text
    data = player.load_readalong(config.output_folder / "Book.readalong.json")
    assert player.read_position(work, doc, stamp, data) is None
    assert heard(work, doc, (config.output_folder,)) == Heard(100.0, None)


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
        record = {"format": "sci2audio-web-opened", "version": 1, "opened": NOW.isoformat()}
        path.write_text(json.dumps(record) + " " * library.RECORD_LIMIT, encoding="utf-8")
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


def test_continue_listening_needs_something_left_to_continue(server: tuple[FastAPI, Any]) -> None:
    """Listen offers nothing inside the first sentence or in the pause after the last one,
    so neither does the shelf (it would open Listen at the start)."""
    client = client_of(server)
    _app, config = server
    one = upload(client, pdf_bytes("One."), "one.pdf")["id"]
    work = config.work_root / one
    stamp = audiobook(work, config.output_folder, one, duration=600.0)  # first ends at 54 s
    for time, shown in ((20.0, False), (54.0, True), (593.0, True), (597.0, False)):
        write_position(work, one, stamp, Position(0, time))
        assert ('id="shelf-continue"' in client.get("/").text) is shown, time
        data = player.load_readalong(config.output_folder / "Book.readalong.json")
        assert (player.read_position(work, one, stamp, data) is not None) is shown, time


# ---- a record nested too deep, or not readable, never fails a page ------------------------

DEEP = {"open": "[" * 16000, "closed": "[" * 500000 + "]" * 500000}  # json gives RecursionError


def deep_place(config: Any, doc: str, record: str) -> Path:
    work = config.work_root / doc
    return {
        "opened.json": work / OPENED,
        "about.json": work / ABOUT,
        "audio.json": work / "audio.json",
        "audiobook.json": work / player.RECORD,
        "readalong": config.output_folder / "Book.readalong.json",
        "report.json": StoredDocument(doc, work, work / "source" / "paper.pdf").report_file,
    }[record]


@pytest.mark.parametrize("shape", sorted(DEEP))
@pytest.mark.parametrize(
    "record",
    ["opened.json", "about.json", "audio.json", "audiobook.json", "readalong", "report.json"],
)
def test_a_record_nested_too_deep_fails_no_page(
    server: tuple[FastAPI, Any], record: str, shape: str
) -> None:
    """The shelf reads every document's records on every page (#420): one deep record
    must read as nothing, or as broken on its own Listen page, never as a server error."""
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    work = config.work_root / doc
    stamp = audiobook(work, config.output_folder, doc)
    write_position(work, doc, stamp, Position(0, 38.0))
    write_opened(work, NOW)
    player.write_record(work, doc, config.output_folder)
    assert (work / "source" / "paper.pdf").is_file()
    place = deep_place(config, doc, record)
    place.parent.mkdir(parents=True, exist_ok=True)
    place.write_text(DEEP[shape], encoding="utf-8")
    for path in ("/", "/settings", "/privacy", f"/documents/{doc}"):
        assert client.get(path).status_code == 200, path
    assert client.get(f"/api/v1/documents/{doc}/report").status_code in (200, 404)
    listen = client.get(f"/documents/{doc}/listen")
    assert listen.status_code == 200
    if record == "audio.json":
        assert "The record of this audiobook can't be read." in html.unescape(listen.text)


def test_a_record_that_cannot_be_read_reads_as_nothing(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record whose read is refused (its rights, or it went during the read) is no record."""
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    work = config.work_root / doc
    write_opened(work, NOW)
    write_about(work, About("A Title", ("A. Writer",)))
    real = Path.read_text

    def refused(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name in (OPENED, ABOUT):
            raise PermissionError(13, "Permission denied", str(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", refused)
    assert read_opened(work) is None
    assert read_about(work) is None
    page = client.get("/")
    assert page.status_code == 200
    assert '<a class="title" href="/documents/' + doc + '">paper.pdf</a>' in row_of(page.text, doc)


# ---- the search (#416) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "found"),
    [
        ("", True),
        ("SLEEP", True),  # case aside
        ("reaction schäfer", True),  # every word, anywhere, in any order
        ("schafer", True),  # accents aside
        ("Schaefer", False),  # no spelling rules: only accents and case
        ("strasse", True),  # ß as ss
        ("STRASSE", True),
        ("ﬁeld", True),  # a ligature as its letters
        ("notes.pdf", True),  # the file name
        ("sleep naps", False),  # every word must be there
    ],
)
def test_the_search_ignores_case_and_accents(query: str, found: bool) -> None:
    row = search_text("Sleep and reaction time in the field", ("J. Schäfer", "Straße"), "notes.pdf")
    assert matches(query, row) is found


def test_the_search_filters_the_rows_and_keeps_the_counts(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    sleep = upload(client, pdf_bytes(), "sleep.pdf")["id"]
    other = upload(client, pdf_bytes(), "other.pdf")["id"]
    write_about(config.work_root / sleep, About("Sleep and naps", ("Ana Müller",), 3))
    page = client.get("/", params={"q": "  MULLER  "}).text
    assert 'value="MULLER"' in page  # the query, its spaces tidied
    assert " hidden" not in row_of(page, sleep).split(">")[0]
    assert row_of(page, other).split(">")[0].endswith(" hidden")
    assert 'data-find="sleep and naps ana muller sleep.pdf"' in row_of(page, sleep)
    assert '<p class="sub" id="library-count">2 documents on this computer</p>' in page
    assert '<p class="no-match" id="no-match" role="status"></p>' in page
    rail = rail_of(page)
    assert re.search(r">\s*2\s*<", rail)  # the rail's count is of every document
    none = client.get("/", params={"q": "nothing like it"}).text
    assert "No document matches “nothing like it”." in none
    assert (
        'id="library" role="region" aria-labelledby="library-caption" tabindex="0" hidden' in none
    )
    german = client.get("/", params={"q": "nichts"}, cookies={"sci2audio-language": "de"}).text
    assert "Kein Dokument passt zu „nichts“." in german
    plain = client.get("/").text
    assert " hidden>" not in row_of(plain, other)[:200]
    assert 'id="no-match" role="status"></p>' in plain


def test_without_documents_there_is_no_search(server: tuple[FastAPI, Any]) -> None:
    page = client_of(server).get("/", params={"q": "x"}).text
    assert 'id="search"' not in page
    assert 'id="no-match"' not in page


# ---- captures on the library and the shelf (#418) ------------------------------------------


def capture_file(work: Path, document: str, kinds: str) -> None:
    """A `captures.json` with one capture per letter of `kinds` (n note, q quote, m mark)."""
    names = {"n": CaptureType.NOTE, "q": CaptureType.QUOTE, "m": CaptureType.MARK}
    captures = tuple(
        Capture(
            f"{at:016x}",
            names[letter],
            "2026-11-20T19:04:00Z",
            "2026-11-20T19:04:00Z",
            Anchor(at, 0, 5, "Words."),
            "Ask Sam." if letter == "n" else "",
        )
        for at, letter in enumerate(kinds)
    )
    work.mkdir(parents=True, exist_ok=True)
    write_captures(work, CaptureFile(document, captures))


def captures_cell(page: str, key: str) -> str:
    return row_of(page, key).split('<td class="captures">')[1].split("</td>")[0]


def shelf_item(rail: str, start: str) -> str:
    return rail.split(start)[1].split("</a>")[0]


def flags(html_text: str) -> list[tuple[str, str, str]]:
    """Each flag of a strip: its type, its icon and the count beside it."""
    return re.findall(
        r'class="flag f-(\w+)".*?<use href="#i-(\w+)".*?class="num">(\d+)<', html_text, re.S
    )


def test_the_captures_column_counts_each_type_with_its_icon(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    bare = upload(client, pdf_bytes("Other."), "bare.pdf")["id"]
    capture_file(config.work_root / doc, doc, "nqmmnm")
    page = client.get("/").text
    heads = re.findall(r'<th scope="col"[^>]*>([^<]+)</th>', page)
    assert heads == ["Document", "State", "Listened", "Captures", "Opened"]
    cell = captures_cell(page, doc)
    assert '<span class="flagstrip" aria-hidden="true">' in cell
    # the dock's order, each type a flag with its icon and its count: never colour alone
    assert flags(cell) == [("note", "note", "2"), ("quote", "quote", "1"), ("mark", "mark", "3")]
    assert '<span class="visually-hidden">2 notes, 1 quote, 3 marks</span>' in cell
    empty = captures_cell(page, bare)
    assert '<span aria-hidden="true">—</span>' in empty
    assert '<span class="visually-hidden">no captures yet</span>' in empty
    assert "flagstrip" not in empty


def test_a_type_without_captures_is_left_out(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    capture_file(config.work_root / doc, doc, "q")
    cell = captures_cell(client.get("/").text, doc)
    assert flags(cell) == [("quote", "quote", "1")]
    assert '<span class="visually-hidden">1 quote</span>' in cell


def test_a_file_that_holds_no_capture_any_more_reads_as_none(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    capture_file(config.work_root / doc, doc, "")
    cell = captures_cell(client.get("/").text, doc)
    assert '<span class="visually-hidden">no captures yet</span>' in cell


def test_the_library_reads_v13_markers_without_carrying_them_over(
    server: tuple[FastAPI, Any],
) -> None:
    """Counted as the carry-over will map them (a marker with a note a note, one without a
    mark), and nothing is written: no `captures.json`, `markers.json` as it was."""
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    work = config.work_root / doc
    markers = [
        Marker("0" * 15 + "1", "t", "t", MarkerAnchor(0, 0, 5, "Words."), "A note."),
        Marker("0" * 15 + "2", "t", "t", MarkerAnchor(1, 0, 5, "Other."), ""),
        Marker("0" * 15 + "3", "t", "t", MarkerAnchor(2, 0, 5, "Third."), ""),
    ]
    (work / MARKERS).write_text(markers_text(doc, markers), encoding="utf-8")
    opened_at(config, doc, 1_700_000_000)
    before = sorted((p.name, p.stat().st_mtime_ns) for p in work.iterdir())
    page = client.get("/").text
    assert '<span class="visually-hidden">1 note, 2 marks</span>' in captures_cell(page, doc)
    assert "1 note, 2 marks" in rail_of(page)
    assert not (work / CAPTURES).exists()
    assert sorted((p.name, p.stat().st_mtime_ns) for p in work.iterdir()) == before


@pytest.mark.parametrize("file", [CAPTURES, MARKERS])
def test_a_captures_file_that_cannot_be_read_is_said_and_left(
    server: tuple[FastAPI, Any], file: str
) -> None:
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    path = config.work_root / doc / file
    path.write_text("{not json", encoding="utf-8")
    opened_at(config, doc, 1_700_000_000)
    page = client.get("/").text
    cell = captures_cell(page, doc)
    assert "Can\N{RIGHT SINGLE QUOTATION MARK}t be read" in cell
    assert "flagstrip" not in cell
    assert path.read_text(encoding="utf-8") == "{not json"
    assert file == CAPTURES or not (config.work_root / doc / CAPTURES).exists()
    assert "flagstrip" not in rail_of(page)


def test_a_shelf_item_has_the_flag_strip_and_its_counts_in_the_links_name(
    server: tuple[FastAPI, Any],
) -> None:
    client = client_of(server)
    _app, config = server
    one = upload(client, pdf_bytes("One."), "one.pdf")["id"]
    two = upload(client, pdf_bytes("Two."), "two.pdf")["id"]
    capture_file(config.work_root / one, one, "nqm")
    opened_at(config, one, 1_700_000_000)
    opened_at(config, two, 1_700_000_100)
    rail = rail_of(client.get("/").text)
    item = shelf_item(rail, f'<a href="/documents/{one}" class="recent"')
    assert '<span class="flagstrip" aria-hidden="true">' in item
    assert flags(item) == [("note", "note", "1"), ("quote", "quote", "1"), ("mark", "mark", "1")]
    assert '<span class="visually-hidden">1 note, 1 quote, 1 mark</span>' in item
    bare = shelf_item(rail, f'<a href="/documents/{two}" class="recent"')
    assert "flagstrip" not in bare  # nothing to show: no strip, no words
    assert "visually-hidden" not in bare


def test_continue_listening_has_the_flag_strip_too(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    one = upload(client, pdf_bytes("One."), "one.pdf")["id"]
    stamp = audiobook(config.work_root / one, config.output_folder, one, duration=600.0)
    write_position(config.work_root / one, one, stamp, Position(0, 192.0))
    capture_file(config.work_root / one, one, "mm")
    rail = rail_of(client.get("/").text)
    item = shelf_item(rail, 'id="shelf-continue"')
    assert flags(item) == [("mark", "mark", "2")]
    assert '<span class="visually-hidden">2 marks</span>' in item


def test_captures_in_german(server: tuple[FastAPI, Any]) -> None:
    client = client_of(server)
    _app, config = server
    doc = upload(client, pdf_bytes(), "paper.pdf")["id"]
    bare = upload(client, pdf_bytes("Other."), "bare.pdf")["id"]
    capture_file(config.work_root / doc, doc, "nnqm")
    client.cookies.set("sci2audio-language", "de")
    page = client.get("/").text
    assert '<th scope="col">Fundstücke</th>' in page
    cell = captures_cell(page, doc)
    assert '<span class="visually-hidden">2 Notizen, 1 Zitat, 1 Marke</span>' in cell
    assert "noch keine Fundstücke" in captures_cell(page, bare)
    assert "Nicht lesbar" not in cell


def test_each_documents_captures_are_read_once_per_library_page(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#962: the row, its removal box and the shelf share one count of a document's
    captures, so `GET /` reads each file once however many places show it."""
    client = client_of(server)
    _app, config = server
    one = upload(client, pdf_bytes("One."), "one.pdf")["id"]
    two = upload(client, pdf_bytes("Two."), "two.pdf")["id"]
    capture_file(config.work_root / one, one, "nqm")
    capture_file(config.work_root / two, two, "mm")
    opened_at(config, one, 1_700_000_000)
    opened_at(config, two, 1_700_000_100)
    stamp = audiobook(config.work_root / one, config.output_folder, one, duration=600.0)
    write_position(config.work_root / one, one, stamp, Position(0, 192.0))
    real = pages.count_captures
    read: list[str] = []

    def counting(work: Path, document_id: str) -> dict[str, Any]:
        read.append(document_id)
        return real(work, document_id)

    monkeypatch.setattr(pages, "count_captures", counting)
    page = client.get("/").text
    assert sorted(read) == sorted([one, two])
    # each place still shows the counts
    assert flags(captures_cell(page, one)) == [
        ("note", "note", "1"),
        ("quote", "quote", "1"),
        ("mark", "mark", "1"),
    ]
    assert flags(shelf_item(rail_of(page), 'id="shelf-continue"'))[0] == ("note", "note", "1")
    assert flags(shelf_item(rail_of(page), f'<a href="/documents/{two}" class="recent"')) == [
        ("mark", "mark", "2")
    ]
    assert "Your 2 marks go too." in page  # the removal box
    read.clear()
    assert client.get("/").status_code == 200  # a page of its own: counted anew
    assert sorted(read) == sorted([one, two])


@pytest.mark.benchmark
def test_the_captures_column_costs_the_library_little_with_many_captures(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#962: `GET /` with 200 documents of 500 captures each takes at most 15% longer than
    without the Captures column and the shelf's strips (the removal boxes count them
    either way), each timed as the middle of five runs taken in turn."""
    client = client_of(server)
    _app, config = server
    for n in range(200):
        doc = upload(client, pdf_bytes(f"Paper {n}."), f"paper-{n}.pdf")["id"]
        capture_file(config.work_root / doc, doc, "nqm" * 166 + "nq")
        opened_at(config, doc, 1_700_000_000 + n)
    real = pages._capture_flags

    def none(*_: Any) -> dict[str, Any]:
        return {"kinds": [], "said": "", "unread": False}

    def timed(column: bool) -> int:
        monkeypatch.setattr(pages, "_capture_flags", real if column else none)
        start = time_ns()
        assert client.get("/").status_code == 200
        return time_ns() - start

    timed(True)  # the first page warms the templates and the file cache
    times: dict[bool, list[int]] = {True: [], False: []}
    for _ in range(5):
        for column in (True, False):
            times[column].append(timed(column))
    with_column, without = (sorted(times[c])[2] for c in (True, False))
    assert with_column <= 1.15 * without, (with_column / 1e6, without / 1e6)
