"""Generating the remaining chapters later (#726, LW-04) through the web: every chapter of
the book listed with its state on the project page, the Listen page and the API, "Generate"
and "Generate the remaining chapters" starting an audio job in the same project, other
settings ending the job before any speech with both choices offered (D-909), the book's
stamp kept as chapters are added, and a listening position kept by its chapter (D-909).
With the fake voice and the real ffmpeg on a few seconds of audio (D-118)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from test_web_listen_growing import GATE_TEXT, TITLES, three_chapters
from test_web_player import player_data, server, work_of
from web_helpers import (
    book_folder,
    offline,  # noqa: F401 - fixture
    upload,
    wait,
)

from sci2audio.app.playable import read_record
from sci2audio.web import player, tasks
from sci2audio.web.player import POSITION

pytestmark = pytest.mark.usefixtures("offline")


class Gate:
    """The voice waits inside the Results chapter while `closed`."""

    def __init__(self) -> None:
        self.open = threading.Event()
        self.open.set()
        self.reached = threading.Event()

    def __call__(self, text: str) -> None:
        if GATE_TEXT in text and not self.open.is_set():
            self.reached.set()
            assert self.open.wait(60)


def project(tmp_path: Path, chapters: list[int], **settings: Any) -> tuple[Any, Any, str, Gate]:
    """A project whose analysis ran and whose audiobook holds the chapters given."""
    gate = Gate()
    client, config = server(tmp_path, FakeVoice(on_speak=gate))
    doc = upload(client, three_chapters())["id"]
    script = client.post("/api/v1/jobs", json={"kind": "script", "document": doc})
    assert wait(client, script.json()["id"])["state"] == "done"
    done = audio(client, doc, chapters, **settings)
    assert done["state"] == "done", done["error"]
    return client, config, doc, gate


def start(client: Any, doc: str, chapters: list[int], **body: Any) -> str:
    settings = {"chapters": chapters, **body.pop("settings", {})}
    answer = client.post(
        "/api/v1/jobs", json={"kind": "audio", "document": doc, "settings": settings, **body}
    )
    assert answer.status_code == 202, answer.text
    return str(answer.json()["id"])


def audio(client: Any, doc: str, chapters: list[int], **body: Any) -> dict[str, Any]:
    return wait(client, start(client, doc, chapters, **body))


def states(client: Any, doc: str) -> list[tuple[str, str | None]]:
    chapters = client.get(f"/api/v1/documents/{doc}/chapters").json()
    return [(c["title"], c["state"]) for c in chapters]


def files(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}


def test_the_chapters_list_their_states(tmp_path: Path) -> None:
    client, _config, doc, _gate = project(tmp_path, [0])
    assert states(client, doc) == [
        ("Introduction", "generated"),
        ("Methods", "not-generated"),
        ("Results", "not-generated"),
    ]
    # the project page: each chapter's state, Generate for those not made, and the rest
    page = client.get(f"/documents/{doc}").text
    assert re.search(r'id="chapter-state-0"[^>]*>generated<', page)
    assert re.search(r'id="chapter-state-1"[^>]*>not generated<', page)
    assert page.count('class="sm generate"') == 2
    assert 'data-chapter="1"' in page
    assert 'data-chapter="2"' in page
    rest = re.search(r'<button[^>]*id="generate-rest"[^>]*>', page)
    assert rest is not None
    assert 'data-chapters="[1, 2]"' in rest[0]
    # the Listen page: the made chapter plays, the others are rows with their state
    listen = client.get(f"/documents/{doc}/listen").text
    assert listen.count('class="chapter-button"') == 1
    assert 'class="chapter-later" data-index="1"' in listen
    assert 'class="chapter-later" data-index="2"' in listen
    assert listen.count('chapter-state">not generated<') == 2
    assert listen.count('class="sm generate"') == 2
    assert 'id="generate-rest"' in listen


def test_a_chapter_file_changed_after_it_was_made_reads_as_not_generated(tmp_path: Path) -> None:
    """A chapter counts as generated only while its files are the ones the chapter record
    vouches for: one edited in place, its size kept, is offered again."""
    client, config, doc, _gate = project(tmp_path, [0, 1])
    folder = book_folder(config.output_folder)
    methods = folder / "paper - 02 Methods.mp3"
    data = bytearray(methods.read_bytes())
    data[-1] ^= 0xFF
    methods.write_bytes(bytes(data))
    stamp = methods.stat().st_mtime_ns + 5_000_000_000
    os.utime(methods, ns=(stamp, stamp))
    assert states(client, doc) == [
        ("Introduction", "generated"),
        ("Methods", "not-generated"),
        ("Results", "not-generated"),
    ]
    page = client.get(f"/documents/{doc}").text
    assert re.search(r'id="chapter-state-1"[^>]*>not generated<', page)
    assert re.search(r'<button type="button" class="sm generate" data-chapter="1"', page)
    rest = re.search(r'<button[^>]*id="generate-rest"[^>]*>', page)
    assert rest is not None
    assert 'data-chapters="[1, 2]"' in rest[0]


def test_a_project_without_an_audiobook_lists_no_states(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    doc = upload(client, three_chapters())["id"]
    script = client.post("/api/v1/jobs", json={"kind": "script", "document": doc})
    assert wait(client, script.json()["id"])["state"] == "done"
    assert [state for _title, state in states(client, doc)] == [None, None, None]
    page = client.get(f"/documents/{doc}").text
    assert 'class="sm generate"' not in page
    assert 'id="generate-rest"' not in page


def test_generate_one_chapter_starts_a_job_in_the_same_project(tmp_path: Path) -> None:
    client, config, doc, _gate = project(tmp_path, [0])
    folder = book_folder(config.output_folder)
    before = files(folder)
    first = next(name for name in before if name.endswith(".mp3"))
    done = audio(client, doc, [2], keep_settings=True)
    assert done["state"] == "done", done["error"]
    assert done["keep_settings"] is True
    # the same project folder, the first chapter's file untouched, the new one beside it
    after = files(folder)
    assert after[first] == before[first]
    assert sorted(n for n in after if n.endswith(".mp3")) == [
        "paper - 01 Introduction.mp3",
        "paper - 03 Results.mp3",
    ]
    assert done["progress"]["reused"] > 0
    assert states(client, doc) == [
        ("Introduction", "generated"),
        ("Methods", "not-generated"),
        ("Results", "generated"),
    ]


def test_generate_the_remaining_chapters_chooses_every_missing_one(tmp_path: Path) -> None:
    client, config, doc, _gate = project(tmp_path, [1])
    page = client.get(f"/documents/{doc}").text
    rest = re.search(r'id="generate-rest"[^>]*data-chapters="([^"]*)"', page)
    if rest is None:
        rest = re.search(r'data-chapters="([^"]*)"[^>]*id="generate-rest"', page)
    assert rest is not None
    chosen = json.loads(rest[1])
    assert chosen == [0, 2]
    done = audio(client, doc, chosen, keep_settings=True)
    assert done["state"] == "done", done["error"]
    assert [state for _title, state in states(client, doc)] == ["generated"] * 3
    # played in the book's order, whatever order they were made in
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    assert [c["title"] for c in data["chapters"]] == TITLES
    assert "growing" not in data
    page = client.get(f"/documents/{doc}").text
    assert 'id="generate-rest"' not in page
    assert 'class="sm generate"' not in page
    assert len([n for n in files(book_folder(config.output_folder)) if n.endswith(".mp3")]) == 3


def test_changed_settings_end_the_job_with_both_choices(tmp_path: Path) -> None:
    client, config, doc, _gate = project(tmp_path, [0])
    folder = book_folder(config.output_folder)
    before = files(folder)
    done = audio(client, doc, [1], settings={"speed": 1.2})
    assert done["state"] == "failed"
    error = done["error"]
    assert error["error"] == "settings-changed"
    assert any(change.startswith("settings speed: 1.0, now 1.2") for change in error["changes"])
    assert files(folder) == before  # nothing spoken, nothing written
    # the job page names what differs and offers both choices
    page = client.get(f"/jobs/{done['id']}").text
    assert "settings speed: 1.0, now 1.2" in page
    assert re.search(r'<button[^>]*id="job-keep-settings"', page)
    assert re.search(r'<button[^>]*id="job-replace"', page)
    assert set(error) == {"error", "message", "changes"}


def test_keep_settings_starts_the_job_with_the_old_settings(tmp_path: Path) -> None:
    client, config, doc, _gate = project(tmp_path, [0])
    work = work_of(config, doc)
    record = read_record(work)
    assert record is not None
    assert record.made is not None
    old = record.made
    done = audio(client, doc, [1], settings={"speed": 1.2}, keep_settings=True)
    assert done["state"] == "done", done["error"]
    assert done["keep_settings"] is True
    assert done["error"] is None
    record = read_record(work)
    assert record is not None
    assert record.made == old  # the new chapter was made with the speed the first had
    assert [c.index for c in record.chapters] == [0, 1]
    # Replace instead makes every chapter anew with the settings given
    replaced = audio(client, doc, [0, 1], settings={"speed": 1.2}, overwrite=True)
    assert replaced["state"] == "done", replaced["error"]
    record = read_record(work)
    assert record is not None
    assert record.made is not None
    assert record.made["settings"]["speed"] == 1.2


def test_generate_notes_the_projects_settings_not_the_forms(tmp_path: Path) -> None:
    """Generate keeps the project's settings, whatever the form holds now: the web's record
    of what the book is made with, written while the job runs, says the project's."""
    client, config, doc, gate = project(tmp_path, [0])
    work = work_of(config, doc)
    made_first = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    kept = sorted(made_first["settings"]["switched_off"])
    other = sorted({"citations", "links"} ^ set(kept))
    assert other != kept
    gate.open.clear()
    job = start(client, doc, [1, 2], settings={"switched_off": other}, keep_settings=True)
    try:
        assert gate.reached.wait(60)
        record = json.loads((work / "audiobook.json").read_text(encoding="utf-8"))
        assert record["made"]["switched_off"] == kept
        assert record["made"]["voice"] == made_first["voice"]
    finally:
        gate.open.set()
    done = wait(client, job)
    assert done["state"] == "done", done["error"]
    made_last = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    assert sorted(made_last["settings"]["switched_off"]) == kept


def test_the_stamp_stays_when_a_chapter_is_added(tmp_path: Path) -> None:
    client, config, doc, _gate = project(tmp_path, [0])
    stamp = player_data(client.get(f"/documents/{doc}/listen").text)["audiobook"]
    record = read_record(work_of(config, doc))
    assert record is not None
    assert stamp == player.book_key(record)
    assert audio(client, doc, [2], keep_settings=True)["state"] == "done"
    assert player_data(client.get(f"/documents/{doc}/listen").text)["audiobook"] == stamp
    # Replace is another audiobook: another stamp
    replaced = audio(client, doc, [0, 2], settings={"speed": 1.2}, overwrite=True)
    assert replaced["state"] == "done", replaced["error"]
    assert player_data(client.get(f"/documents/{doc}/listen").text)["audiobook"] != stamp


def resume_of(page: str) -> tuple[int, float]:
    found = re.search(r'id="resume-continue"[^>]*data-chapter="(\d+)" data-time="([^"]+)"', page)
    assert found is not None, "no offer to continue"
    return int(found[1]), float(found[2])


def test_a_position_after_an_added_chapter_keeps_its_place_in_its_chapter(
    tmp_path: Path,
) -> None:
    client, config, doc, _gate = project(tmp_path, [0, 2])
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    results = data["chapters"][1]
    assert results["title"] == "Results"
    within = 0.3
    body = {"chapter": 1, "time": results["start"] + within, "audiobook": data["audiobook"]}
    answer = client.post(f"/api/v1/documents/{doc}/position", json=body)
    assert answer.status_code == 204, answer.text
    assert audio(client, doc, [1], keep_settings=True)["state"] == "done"
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    assert [c["title"] for c in data["chapters"]] == TITLES
    chapter, at = resume_of(client.get(f"/documents/{doc}/listen").text)
    assert chapter == 2  # Results, now after Methods
    assert at == pytest.approx(data["chapters"][2]["start"] + within, abs=0.01)
    # a page drawn before Methods was added saves by its own chapter: the server places it
    stale = {**body, "index": 2, "within": within}
    answer = client.post(f"/api/v1/documents/{doc}/position", json=stale)
    assert answer.status_code == 204, answer.text
    assert resume_of(client.get(f"/documents/{doc}/listen").text)[0] == 2
    saved = json.loads((work_of(config, doc) / POSITION).read_text())
    assert (saved["chapter"], saved["index"]) == (2, 2)
    assert saved["within"] == pytest.approx(within)


def test_a_position_saved_before_this_version_is_still_offered_and_kept(tmp_path: Path) -> None:
    """A position kept with the old stamp (settings and planned chapters) and without its
    chapter's index is offered as before, and an added chapter does not lose it (D-909)."""
    client, config, doc, _gate = project(tmp_path, [0, 2])
    work = work_of(config, doc)
    record = read_record(work)
    assert record is not None
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    results = data["chapters"][1]
    old_stamp = hashlib.sha256(
        json.dumps([record.settings, list(record.planned)], separators=(",", ":")).encode()
    ).hexdigest()[:16]
    assert old_stamp != data["audiobook"]
    old = {
        "format": "sci2audio-web-position",
        "version": 1,
        "document": doc,
        "audiobook": old_stamp,
        "chapter": 1,
        "time": results["start"] + 0.3,
    }
    (work / POSITION).write_text(json.dumps(old) + "\n", encoding="utf-8")
    assert resume_of(client.get(f"/documents/{doc}/listen").text) == (1, old["time"])
    assert audio(client, doc, [1], keep_settings=True)["state"] == "done"
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    chapter, at = resume_of(client.get(f"/documents/{doc}/listen").text)
    assert chapter == 2
    assert at == pytest.approx(data["chapters"][2]["start"] + 0.3, abs=0.01)


def test_a_save_while_the_job_keeps_the_position_by_chapter_is_not_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#790: the audio job reads the kept position, then writes it again with its chapter's
    index. A save by the player that lands between the read and the write is the newer
    place and must survive: the read and the write take one turn with the player's saves."""
    client, _config, doc, _gate = project(tmp_path, [0, 2])
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    results = data["chapters"][1]
    body = {"chapter": 1, "time": results["start"] + 0.3, "audiobook": data["audiobook"]}
    assert client.post(f"/api/v1/documents/{doc}/position", json=body).status_code == 204
    answers: list[int] = []
    original = tasks.chapter_index

    def save_in_between(work: Path, n: int) -> int | None:
        # the job has read the position: the player saves a newer place now
        monkeypatch.setattr(tasks, "chapter_index", original)
        newer = {**body, "time": results["start"] + 0.4}
        saver = threading.Thread(
            target=lambda: answers.append(
                client.post(f"/api/v1/documents/{doc}/position", json=newer).status_code
            )
        )
        saver.start()
        saver.join(timeout=1.0)  # a save that waits for the job's turn goes on after it
        return original(work, n)

    monkeypatch.setattr(tasks, "chapter_index", save_in_between)
    assert audio(client, doc, [1], keep_settings=True)["state"] == "done"
    deadline = time.monotonic() + 30
    while not answers and time.monotonic() < deadline:
        time.sleep(0.01)
    assert answers == [204]
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    chapter, at = resume_of(client.get(f"/documents/{doc}/listen").text)
    assert chapter == 2  # Results, now after Methods
    assert at == pytest.approx(data["chapters"][2]["start"] + 0.4, abs=0.01)  # the newer place


def test_adding_to_a_finished_project_shows_the_growing_view_until_done(tmp_path: Path) -> None:
    client, _config, doc, gate = project(tmp_path, [0])
    gate.open.clear()
    job = start(client, doc, [1, 2], keep_settings=True)
    try:
        assert gate.reached.wait(60)
        deadline = time.monotonic() + 60
        while True:
            page = client.get(f"/documents/{doc}/listen").text
            data = player_data(page)
            if len(data.get("chapters", [])) == 2:
                break
            # clock-bound: the wait loop's way out after 60 s; Methods takes a second
            assert time.monotonic() < deadline
            time.sleep(0.05)
        assert data["growing"]["events"] == f"/api/v1/jobs/{job}/events"
        planned = data["growing"]["planned"]
        assert [(p["title"], p["state"]) for p in planned] == [
            ("Introduction", "ready"),
            ("Methods", "ready"),
            ("Results", "generating"),
        ]
        assert 'class="sm generate"' not in page  # one job at a time
        assert states(client, doc) == [
            ("Introduction", "generated"),
            ("Methods", "generated"),
            ("Results", "generating"),
        ]
        project_page = client.get(f"/documents/{doc}").text
        assert re.search(r'id="chapter-state-2"[^>]*>being generated<', project_page)
    finally:
        gate.open.set()
    assert wait(client, job)["state"] == "done"
    data = player_data(client.get(f"/documents/{doc}/listen").text)
    assert "growing" not in data
    assert [c["title"] for c in data["chapters"]] == TITLES


def test_chapters_the_analysis_left_out_can_be_generated(tmp_path: Path) -> None:
    """The analysis counts what is said only in the chapters it was asked for: one it left
    out may still say something, so it gets Generate."""
    client, _config, doc, _gate = project(tmp_path, [0])
    body = {"kind": "script", "document": doc, "settings": {"chapters": [0]}}
    script = client.post("/api/v1/jobs", json=body)
    assert wait(client, script.json()["id"])["state"] == "done"
    chapters = client.get(f"/api/v1/documents/{doc}/chapters").json()
    assert [(c["selected"], c["utterances"] > 0) for c in chapters] == [
        (True, True),
        (False, False),
        (False, False),
    ]
    page = client.get(f"/documents/{doc}").text
    assert page.count('class="sm generate"') == 2
    assert 'data-chapters="[1, 2]"' in page


def test_adding_paused_mid_chapter_resumes_with_the_same_choice(tmp_path: Path) -> None:
    """Pause (the web's cancel) while a chapter is added, then Resume as the card does: the
    paused job's keep_settings goes with it, the chapters made stay, nothing is mixed."""
    client, config, doc, gate = project(tmp_path, [0])
    gate.open.clear()
    job = start(client, doc, [1, 2], settings={"speed": 1.2}, keep_settings=True)
    try:
        assert gate.reached.wait(60)
        cancel = client.post(f"/api/v1/jobs/{job}/cancel")
        assert cancel.status_code == 202, cancel.text
    finally:
        gate.open.set()
    paused = wait(client, job)
    assert paused["state"] == "cancelled"
    assert paused["keep_settings"] is True
    assert states(client, doc) == [
        ("Introduction", "generated"),
        ("Methods", "generated"),
        ("Results", "not-generated"),
    ]
    # the card's data carries the choice on: Resume sends it back
    page = client.get(f"/jobs/{job}").text
    assert 'data-keep-settings="true"' in page
    resumed = audio(
        client, doc, paused["settings"]["chapters"], settings=paused["settings"], keep_settings=True
    )
    assert resumed["state"] == "done", resumed["error"]
    assert [state for _title, state in states(client, doc)] == ["generated"] * 3
    record = read_record(work_of(config, doc))
    assert record is not None
    assert record.made is not None
    assert record.made["settings"]["speed"] == 1.0  # all three as the first was made
