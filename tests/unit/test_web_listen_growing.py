"""Listening while the audiobook is still being made (#724, LW-02): the Listen page plays
the chapters the audio job has finished (#723), lists every chapter asked for with its state,
hands out each new chapter as it becomes playable, and keeps the listening position and the
markers across the growth and the end of the job.

A real audio job with the fake voice and real ffmpeg (a few seconds, allowed in the fast
tier) on a three-chapter PDF; the voice waits at a gate inside the third chapter, so the
first two are playable while the job still runs.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf
from test_web_player import player_data, server, work_of
from web_helpers import (
    events,
    offline,  # noqa: F401 - fixture
    program,
    set_capture,
    upload,
    wait,
)

from sci2audio.app.playable import read_record
from sci2audio.web import create_app, player
from sci2audio.web.documents import AUDIO_RECORD
from sci2audio.web.player import RECORD as WEB_RECORD

GATE_TEXT = "It worked well."
TITLES = ["Introduction", "Methods", "Results"]


def three_chapters() -> bytes:
    return make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Things happen and more.", 72, 100, size=11),
            Text("Methods", 72, 140, size=14),
            Text("We measured it twice.", 72, 160, size=11),
            Text("Results", 72, 200, size=14),
            Text(GATE_TEXT, 72, 220, size=11),
        ]
    )


@dataclass
class Growing:
    """A server whose audio job waits inside the third chapter, the first two playable."""

    client: Any
    config: Any
    doc: str
    job: str
    gate: threading.Event

    @property
    def work(self) -> Path:
        return work_of(self.config, self.doc)

    def page(self) -> str:
        answer = self.client.get(f"/documents/{self.doc}/listen")
        assert answer.status_code == 200, answer.text
        return answer.text

    def data(self) -> dict[str, Any]:
        return player_data(self.page())

    def finish(self) -> dict[str, Any]:
        self.gate.set()
        return wait(self.client, self.job)

    def stop(self) -> dict[str, Any]:
        """Pause the job (the web's cancel) while it waits at the gate."""
        answer = self.client.post(f"/api/v1/jobs/{self.job}/cancel")
        assert answer.status_code in (200, 202), answer.text
        return self.finish()


def playable(client: Any, job: str) -> list[int]:
    progress = client.get(f"/api/v1/jobs/{job}").json().get("progress") or {}
    return list(progress.get("playable") or [])


def start_growing(tmp_path: Path, ready: int = 2, gate_text: str = GATE_TEXT) -> Growing:
    gate = threading.Event()

    def at_gate(text: str) -> None:
        if gate_text in text:
            gate.wait(60)

    client, config = server(tmp_path, FakeVoice(on_speak=at_gate))
    doc = upload(client, three_chapters())["id"]
    body = {"kind": "audio", "document": doc, "settings": {}}
    job = client.post("/api/v1/jobs", json=body).json()["id"]
    deadline = time.monotonic() + 60
    while len(playable(client, job)) < ready:
        # clock-bound: the wait loop's way out after 60 s; the two chapters take a second
        assert time.monotonic() < deadline, client.get(f"/api/v1/jobs/{job}").json()
        time.sleep(0.02)
    return Growing(client, config, doc, job, gate)


@pytest.fixture
def growing(tmp_path: Path) -> Iterator[Growing]:
    found = start_growing(tmp_path)
    try:
        yield found
    finally:
        found.gate.set()
        wait(found.client, found.job)


def fragment(book: Growing, n: int) -> Any:
    return book.client.get(f"/documents/{book.doc}/listen/chapters/{n}")


# ---- the page while the job runs -----------------------------------------------------------


def test_the_listen_page_plays_the_first_chapter_while_the_job_runs(growing: Growing) -> None:
    text = growing.page()
    assert '<script src="/static/player.js" defer></script>' in text
    assert "read by a synthetic voice (Heart)" in text
    data = player_data(text)
    assert data["mode"] == "mp3"
    assert [c["title"] for c in data["chapters"]] == TITLES[:2]
    assert data["growing"]["events"] == f"/api/v1/jobs/{growing.job}/events"
    for _start, _end, chapter, element in data["chunks"]:
        assert f'id="{element}"' in text
        assert chapter in (0, 1)
    for chapter in data["chapters"]:
        audio = growing.client.get(f"/api/v1/documents/{growing.doc}/audiobook/{chapter['file']}")
        assert audio.status_code == 200
        assert audio.headers["content-type"] == "audio/mpeg"
    # the job is still at its third chapter: nothing of it is written yet
    record = read_record(growing.work)
    assert record is not None
    assert not record.complete
    assert not (growing.work / "audio.json").exists()


def test_the_chapter_list_shows_every_planned_chapter_with_its_state(growing: Growing) -> None:
    text = growing.page()
    planned = player_data(text)["growing"]["planned"]
    assert [(p["title"], p["state"], p["chapter"]) for p in planned] == [
        ("Introduction", "ready", 0),
        ("Methods", "ready", 1),
        ("Results", "generating", None),
    ]
    assert text.count('class="chapter-button"') == 2
    assert 'class="chapter-later" data-index="2"' in text
    assert 'chapter-state">being generated<' in text
    assert 'chapter-state">not generated<' not in text
    # the lines the page says as the book grows are there, in a live region
    assert 'id="growing-status" class="visually-hidden" aria-live="polite"' in text
    assert 'id="waiting"' in text


def test_chapters_not_ready_read_not_generated_once_the_job_stopped(tmp_path: Path) -> None:
    book = start_growing(tmp_path)
    final = book.stop()
    assert final["state"] == "cancelled", final
    text = book.page()
    data = player_data(text)
    assert [c["title"] for c in data["chapters"]] == TITLES[:2]
    assert [p["state"] for p in data["growing"]["planned"]] == ["ready", "ready", "missing"]
    assert data["growing"]["events"] == ""  # no job to follow
    assert 'chapter-state">not generated<' in text
    assert 'chapter-state">being generated<' not in text


# ---- each new chapter ------------------------------------------------------------------------


def test_the_chapter_fragment_continues_the_chunk_numbers(growing: Growing) -> None:
    data = growing.data()
    for n, chapter in enumerate(data["chapters"]):
        answer = fragment(growing, n)
        assert answer.status_code == 200, answer.text
        part = answer.json()
        assert part["chapter"] == chapter
        assert part["first"] == chapter["first"]
        end = data["chapters"][n + 1]["first"] if n + 1 < len(data["chapters"]) else None
        assert part["chunks"] == data["chunks"][chapter["first"] : end]
        assert part["sentences"] == data["sentences"][chapter["first"] : end]
        assert part["html"].startswith(f'<section class="sheet-chapter" id="chapter-{n}">')
        for _start, _end, _chapter, element in part["chunks"]:
            assert f'id="{element}"' in part["html"]
        assert part["audiobook"] == data["audiobook"]
        assert part["growing"]["planned"] == data["growing"]["planned"]
    # once the job is done, the book's next chapter continues where the page stopped
    growing.finish()
    last = fragment(growing, 2).json()
    assert last["first"] == len(data["chunks"])
    assert last["chapter"]["start"] == pytest.approx(data["chunks"][-1][1], abs=0.5)
    assert "growing" not in last


def test_a_chapter_not_ready_has_no_fragment(growing: Growing) -> None:
    assert fragment(growing, 2).status_code == 404
    assert fragment(growing, -1).status_code == 404
    assert growing.client.get(f"/documents/{growing.doc}/listen/chapters/x").status_code == 422
    assert growing.client.get("/documents/0123456789abcdef/listen/chapters/0").status_code == 404


def test_only_the_recorded_files_of_ready_chapters_are_served(growing: Growing) -> None:
    data = growing.data()
    folder = Path(json.loads((growing.work / WEB_RECORD).read_text())["folder"])
    url = f"/api/v1/documents/{growing.doc}/audiobook/"
    record = read_record(growing.work)
    assert record is not None
    readalong = next(f.name for f in record.book if f.name.endswith(".readalong.json"))
    assert growing.client.get(url + readalong).status_code == 200
    # a file in the folder that the record does not name is never served
    (folder / "paper - 03 Results.mp3").write_bytes(b"not ours")
    (folder / "notes.txt").write_text("not ours")
    for name in ("paper - 03 Results.mp3", "notes.txt", "../audiobook.json"):
        assert growing.client.get(url + name).status_code == 404, name
    # a ready chapter's MP3 of another size is not the book's: nothing of the book is served
    mp3 = folder / data["chapters"][0]["file"]
    mp3.write_bytes(mp3.read_bytes() + b"x")
    assert growing.client.get(url + data["chapters"][1]["file"]).status_code == 404


def test_a_readalong_file_the_record_does_not_vouch_for_shows_no_growing_view(
    growing: Growing,
) -> None:
    folder = Path(json.loads((growing.work / WEB_RECORD).read_text())["folder"])
    readalong = next(folder.glob("*.readalong.json"))
    readalong.write_text(readalong.read_text() + " ", encoding="utf-8")
    text = growing.page()
    assert 'id="listen-problem"' in text
    assert 'id="player-data"' not in text
    assert fragment(growing, 0).status_code == 404


@pytest.mark.parametrize(
    "spoil",
    [
        lambda work: (work / "chapters.json").write_text("{}", encoding="utf-8"),
        lambda work: (work / "chapters.json").unlink(),
        lambda work: (work / WEB_RECORD).unlink(),
        lambda work: (work / WEB_RECORD).write_text(
            json.dumps({**json.loads((work / WEB_RECORD).read_text()), "made": {"voice": 1}}),
            encoding="utf-8",
        ),
        lambda work: (work / WEB_RECORD).write_text(
            json.dumps({**json.loads((work / WEB_RECORD).read_text()), "document": "f" * 16}),
            encoding="utf-8",
        ),
    ],
    ids=["broken-record", "no-record", "no-web-record", "broken-made", "other-document"],
)
def test_a_broken_or_foreign_chapter_record_shows_no_growing_view(
    growing: Growing, spoil: Any
) -> None:
    spoil(growing.work)
    text = growing.page()
    assert 'id="player-data"' not in text
    assert "There is no audiobook of this document yet." in text


def test_the_finished_audiobook_wins_over_a_growing_record(growing: Growing) -> None:
    final = growing.finish()
    assert final["state"] == "done", final
    text = growing.page()
    data = player_data(text)
    assert "growing" not in data
    assert [c["title"] for c in data["chapters"]] == TITLES
    assert 'chapter-state">' not in text
    assert 'class="chapter-later"' not in text
    # once the book is done, audio.json says what it is made with, not the web's record
    assert "made" not in json.loads((growing.work / WEB_RECORD).read_text())


# ---- the listening position (#153) and the markers (#474) ---------------------------------------


def test_the_stamp_stays_while_the_book_grows_and_when_it_is_done(growing: Growing) -> None:
    folder = Path(json.loads((growing.work / WEB_RECORD).read_text())["folder"])
    readalong = next(folder.glob("*.readalong.json"))
    during = growing.data()["audiobook"]
    assert during != player.audiobook_stamp(readalong)
    record = read_record(growing.work)
    assert record is not None
    assert during == player.book_key(record)
    growing.finish()
    assert growing.data()["audiobook"] == during


def test_a_position_kept_mid_run_is_offered_after_the_job_is_done(growing: Growing) -> None:
    data = growing.data()
    at = data["chapters"][1]["start"] + 0.2
    body = {"chapter": 1, "time": at, "audiobook": data["audiobook"]}
    answer = growing.client.post(f"/api/v1/documents/{growing.doc}/position", json=body)
    assert answer.status_code == 204, answer.text
    assert 'id="resume"' in growing.page()  # offered on the growing book itself
    assert growing.finish()["state"] == "done"
    page = growing.page()
    assert 'id="resume"' in page
    assert 'data-chapter="1"' in page
    # the library's shelf offers it too (#389)
    assert (growing.work / player.POSITION).is_file()


def test_an_audiobook_without_a_chapter_record_keeps_the_readalong_stamp(
    growing: Growing,
) -> None:
    growing.finish()
    (growing.work / "chapters.json").unlink()
    folder = Path(json.loads((growing.work / WEB_RECORD).read_text())["folder"])
    readalong = next(folder.glob("*.readalong.json"))
    assert growing.data()["audiobook"] == player.audiobook_stamp(readalong)


def test_captures_in_a_chapter_that_just_arrived_get_their_sentence(growing: Growing) -> None:
    data = growing.data()
    chunk = data["chapters"][1]["first"] + 1  # the second chapter's sentence
    set_capture(growing.client, growing.doc, "quote", chunk, data["audiobook"])
    part = fragment(growing, 1).json()
    placed = [c for c in part["captures"] if c["chunk"] is not None]
    assert [c["chunk"] for c in placed] == [chunk]
    assert placed[0]["sentence"] == "We measured it twice."
    # the page follows the job's events, which say which chapters are playable
    assert playable(growing.client, growing.job) == [0, 1]
    growing.finish()
    final = [json.loads(data) for name, data in events(growing.client, growing.job) if name]
    assert final[-1]["state"] == "done"


# ---- after a restart (#1059) ---------------------------------------------------------------
#
# A paused, failed or restarted job leaves its playable chapters in `chapters.json` and no
# `audio.json`, which only the job's end writes. The next run of the server has no job on
# its board, so nothing but the folder says a chapter can be played.

LISTEN_NONE = "Listen · No audio yet"


def restart(book: Growing) -> Any:
    """The next run of sci2audio on the same folders: its board holds no job."""
    app = create_app(book.config, voice=lambda models_dir: FakeVoice().source())
    return program(app, book.config)


def listen_tab(client: Any, doc: str) -> str:
    """The Listen tab on the document's Prepare page, as drawn."""
    answer = client.get(f"/documents/{doc}")
    assert answer.status_code == 200, answer.text
    found = re.search(r'<(a|span)[^>]*id="tab-listen".*?</\1>', answer.text, re.S)
    assert found is not None, answer.text
    return found[0]


def test_after_a_restart_the_chapters_made_open_the_listen_tab_and_play(tmp_path: Path) -> None:
    # held inside chapter 2, so only chapter 1 is playable when the job is paused
    book = start_growing(tmp_path, ready=1, gate_text="We measured it twice.")
    assert book.stop()["state"] == "cancelled"
    record = read_record(book.work)
    assert record is not None
    assert not record.complete
    assert [c.title for c in record.chapters] == TITLES[:1]
    assert not (book.work / AUDIO_RECORD).exists()

    client = restart(book)
    tab = listen_tab(client, book.doc)
    assert tab.startswith(f'<a href="/documents/{book.doc}/listen" id="tab-listen"'), tab
    assert LISTEN_NONE not in tab
    answer = client.get(f"/documents/{book.doc}/listen")
    assert answer.status_code == 200, answer.text
    data = player_data(answer.text)
    assert [c["title"] for c in data["chapters"]] == TITLES[:1]
    assert data["growing"]["events"] == ""  # no job to follow
    audio = client.get(f"/api/v1/documents/{book.doc}/audiobook/{data['chapters'][0]['file']}")
    assert audio.status_code == 200
    assert audio.content


def test_after_a_restart_a_book_with_no_playable_chapter_has_no_audio_yet(
    tmp_path: Path,
) -> None:
    # held inside chapter 1: nothing is playable when the job is paused
    book = start_growing(tmp_path, ready=0, gate_text="Things happen and more.")
    assert book.stop()["state"] == "cancelled"
    record = read_record(book.work)
    assert record is None or not record.chapters

    tab = listen_tab(restart(book), book.doc)
    assert tab.startswith('<span class="tab-off" id="tab-listen"'), tab
    assert LISTEN_NONE in tab


def test_after_a_restart_a_finished_audiobook_opens_the_listen_tab_as_before(
    tmp_path: Path,
) -> None:
    book = start_growing(tmp_path)
    assert book.finish()["state"] == "done"
    assert (book.work / AUDIO_RECORD).is_file()

    client = restart(book)
    tab = listen_tab(client, book.doc)
    assert tab.startswith(f'<a href="/documents/{book.doc}/listen" id="tab-listen"'), tab
    data = player_data(client.get(f"/documents/{book.doc}/listen").text)
    assert "growing" not in data
    assert [c["title"] for c in data["chapters"]] == TITLES
