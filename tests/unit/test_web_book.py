"""The whole audiobook, built on request through the API (#725, LW-03): the audio job writes
the chapters only, and `POST /documents/{id}/book` serves the file built before or starts a
book job that builds it from the chunk cache. With the fake voice and the real ffmpeg on a
few seconds of audio (D-118)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from fastapi.testclient import TestClient
from web_helpers import (
    book_folder,
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    paper_bytes,
    program,
    upload,
    wait,
)

from sci2audio.app import JobSettings, run_audio_job
from sci2audio.app.playable import read_record
from sci2audio.output import Ffmpeg, OutputSettings, find_ffmpeg
from sci2audio.web import create_app
from sci2audio.web.project import read_project

pytestmark = pytest.mark.usefixtures("offline")


def server(tmp_path: Path, **changes: Any) -> tuple[Any, TestClient, Any]:
    config = make_config(tmp_path, **changes)
    voice = FakeVoice()
    app = create_app(config, voice=lambda models_dir: voice.source())
    return app, program(app, config), config


def made(client: TestClient, chapters: list[int] | None = None) -> dict[str, Any]:
    """The two-chapter paper with an analysis and the chapters chosen made."""
    doc = upload(client, paper_bytes())
    settings = {} if chapters is None else {"chapters": chapters}
    for kind in ("script", "audio"):
        body = {"kind": kind, "document": doc["id"], "settings": settings}
        job = client.post("/api/v1/jobs", json=body)
        assert job.status_code == 202, job.text
        assert wait(client, job.json()["id"])["state"] == "done"
    return doc


def ask(client: TestClient, document: str, **body: Any) -> Any:
    return client.post(f"/api/v1/documents/{document}/book", json=body)


def built(client: TestClient, document: str, **body: Any) -> dict[str, Any]:
    """Ask for the book and wait for its job; the job once done."""
    response = ask(client, document, **body)
    assert response.status_code == 202, response.text
    job = response.json()["job"]
    assert job["kind"] == "book"
    done = wait(client, job["id"])
    assert done["state"] == "done", done["error"]
    return done


def test_the_audio_job_writes_no_m4b(tmp_path: Path) -> None:
    _, client, config = server(tmp_path)
    made(client)
    names = [p.name for p in book_folder(config.output_folder).iterdir()]
    assert any(name.endswith(".mp3") for name in names)
    assert not any(name.endswith(".m4b") for name in names)


def test_a_book_job_builds_the_file_and_the_download_serves_it(tmp_path: Path) -> None:
    _, client, config = server(tmp_path)
    doc = made(client)
    folder = book_folder(config.output_folder)
    response = ask(client, doc["id"], kind="m4b")
    assert response.status_code == 202, response.text
    job = response.json()["job"]
    assert response.json()["name"] is None
    seen = events(client, job["id"])
    progress = [json.loads(data) for name, data in seen if name == "progress"]
    fractions = [p["fraction"] for p in progress if p.get("phase") == "building"]
    assert fractions == sorted(fractions)
    assert all(0 <= f <= 1 for f in fractions)
    done = json.loads(seen[-1][1])
    assert done["state"] == "done", done["error"]
    name = done["progress"]["name"]
    assert name.endswith(".m4b")
    assert not done["progress"]["partial"]
    assert done["progress"]["missing"] == []
    assert [f["name"] for f in done["files"]] == [name]
    assert (folder / name).is_file()

    got = client.get(f"/api/v1/documents/{doc['id']}/audiobook/{name}?download=true")
    assert got.status_code == 200
    assert got.headers["content-type"] == "audio/mp4"
    assert got.headers["content-disposition"].startswith("attachment")
    assert got.content == (folder / name).read_bytes()

    mp3 = built(client, doc["id"], kind="mp3")["progress"]["name"]
    assert mp3.endswith(".mp3")
    assert mp3 != name
    got = client.get(f"/api/v1/documents/{doc['id']}/audiobook/{mp3}")
    assert got.status_code == 200
    assert got.headers["content-type"] == "audio/mpeg"
    assert got.content == (folder / mp3).read_bytes()


def test_a_current_build_is_served_without_a_job(tmp_path: Path) -> None:
    _, client, config = server(tmp_path)
    doc = made(client)
    name = built(client, doc["id"])["progress"]["name"]
    jobs = len(client.get("/api/v1/jobs").json())
    again = ask(client, doc["id"], kind="m4b")
    assert again.status_code == 200, again.text
    assert again.json() == {"name": name, "partial": False, "job": None}
    assert len(client.get("/api/v1/jobs").json()) == jobs

    # a file changed since it was built is not the one the record vouches for: built again
    path = book_folder(config.output_folder) / name
    path.write_bytes(path.read_bytes() + b"\0")
    changed = ask(client, doc["id"], kind="m4b")
    assert changed.status_code == 202, changed.text
    done = wait(client, changed.json()["job"]["id"])
    # sci2audio never replaces a file the record does not vouch for (D-163)
    assert done["state"] == "failed"
    assert done["error"]["error"] == "output-exists"
    # and the other kind is not this one
    assert ask(client, doc["id"], kind="mp3").status_code == 202


def test_missing_chapters_answer_409_unless_partial_is_asked(tmp_path: Path) -> None:
    _, client, config = server(tmp_path)
    doc = upload(client, paper_bytes())
    assert (
        wait(
            client,
            client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]}).json()[
                "id"
            ],
        )["state"]
        == "done"
    )
    titles = [c["title"] for c in client.get(f"/api/v1/documents/{doc['id']}/chapters").json()]
    assert titles[:2] == ["Introduction", "Methods"]  # the default leaves out the references
    gate, reached = threading.Event(), threading.Event()
    voice_job = _held_after_first_chapter(client, doc["id"], gate, reached)
    try:
        assert reached.wait(30)
        busy = ask(client, doc["id"])
        assert busy.status_code == 409
        assert busy.json()["error"] == "busy"
    finally:
        cancel = client.post(f"/api/v1/jobs/{voice_job}/cancel")
        gate.set()
    assert cancel.status_code == 202
    assert wait(client, voice_job)["state"] == "cancelled"

    refused = ask(client, doc["id"], kind="m4b")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"] == "missing-chapters"
    assert refused.json()["chapters"] == ["Methods"]
    assert titles[1] in refused.json()["message"]
    assert not any(p.suffix == ".m4b" for p in book_folder(config.output_folder).iterdir())

    done = built(client, doc["id"], kind="m4b", partial_ok=True)
    name = done["progress"]["name"]
    assert done["progress"]["partial"] is True
    assert done["progress"]["missing"] == ["Methods"]
    assert "(partial)" in name
    again = ask(client, doc["id"], kind="m4b", partial_ok=True)
    assert again.status_code == 200
    assert again.json() == {"name": name, "partial": True, "job": None}


def _held_after_first_chapter(
    client: TestClient, document: str, gate: threading.Event, reached: threading.Event
) -> str:
    """Start an audio job whose voice waits before the second chapter's first sentence."""
    app = client.app
    state = app.state.sci2audio  # type: ignore[attr-defined]
    voice = FakeVoice()

    def held(text: str) -> bool:
        job = state.board.current
        progress = job.snapshot()["progress"] if job is not None else None
        if progress and progress.get("chapter_number", 1) > 1:
            reached.set()
            assert gate.wait(30)
        return False

    voice.fail_on = held
    state.voice = lambda models_dir: voice.source()
    state.kept.dispose()
    response = client.post("/api/v1/jobs", json={"kind": "audio", "document": document})
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def test_a_book_job_can_be_cancelled(tmp_path: Path) -> None:
    app, client, config = server(tmp_path)
    doc = made(client)
    gate, reached = threading.Event(), threading.Event()
    real = Ffmpeg(find_ffmpeg())

    class Held(Ffmpeg):
        def run(self, args: Any, feed: Any = ()) -> str:
            def fed() -> Any:
                for n, piece in enumerate(feed):
                    if n == 1:
                        reached.set()
                        assert gate.wait(30)
                    yield piece

            return real.run(args, fed())

    app.state.sci2audio.book_ffmpeg = Held(real.exe)
    response = ask(client, doc["id"])
    assert response.status_code == 202, response.text
    job = response.json()["job"]
    assert job["cancellable"] is True
    assert reached.wait(30)
    try:
        cancel = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    finally:
        gate.set()
    assert cancel.status_code == 202
    ended = wait(client, job["id"])
    assert ended["state"] == "cancelled"
    folder = book_folder(config.output_folder)
    assert not any(p.suffix in (".m4b", ".partial") for p in folder.iterdir())
    assert not any(".partial" in p.name for p in folder.iterdir())
    work = app.state.sci2audio.store.get(doc["id"]).folder
    record = read_record(work)
    assert record is not None
    assert record.built == ()


def test_removing_the_project_removes_the_built_file(tmp_path: Path) -> None:
    app, client, config = server(tmp_path)
    doc = upload(client, paper_bytes())
    for kind in ("script", "audio"):
        body = {"kind": kind, "document": doc["id"], "settings": {"subtitles": True}}
        job = client.post("/api/v1/jobs", json=body)
        assert job.status_code == 202, job.text
        assert wait(client, job.json()["id"])["state"] == "done"
    name = built(client, doc["id"])["progress"]["name"]
    folder = book_folder(config.output_folder)
    # the book's subtitles come with its M4B (#214) and go with the project too
    pair = {name.removesuffix(".m4b") + suffix for suffix in (".srt", ".vtt")}
    assert pair <= {p.name for p in folder.iterdir()}
    work = app.state.sci2audio.store.get(doc["id"]).folder
    project = read_project(work, doc["id"])
    assert project is not None
    assert {name, *pair} <= {f.name for a in project.audiobooks for f in a.files}
    removed = client.delete(f"/api/v1/documents/{doc['id']}?keep_audiobook=false")
    assert removed.status_code == 200, removed.text
    assert not (folder / name).exists()
    assert not folder.exists()


# ---- the checks each answer rests on ---------------------------------------------------


def test_a_book_built_before_chapters_were_added_is_not_served_as_current(
    tmp_path: Path,
) -> None:
    """A whole-book file holds the chapters made when it was built; once another is
    added it is not the book any more, and asking again builds it anew."""
    _, client, config = server(tmp_path)
    doc = made(client, [0])
    first = built(client, doc["id"])["progress"]["name"]
    folder = book_folder(config.output_folder)
    assert (folder / first).is_file()  # still there, still the file the record vouches for
    job = client.post(
        "/api/v1/jobs",
        json={"kind": "audio", "document": doc["id"], "settings": {"chapters": [1]}},
    )
    assert job.status_code == 202, job.text
    assert wait(client, job.json()["id"])["state"] == "done"
    again = ask(client, doc["id"], kind="m4b")
    assert again.status_code == 202, again.text
    assert again.json()["name"] is None
    done = wait(client, again.json()["job"]["id"])
    assert done["state"] == "done", done["error"]
    assert done["progress"]["name"] == first  # the same name, the file built anew
    assert not done["progress"]["reused"]


def test_an_edited_built_file_is_not_served(tmp_path: Path) -> None:
    """The download serves a built file only as the chapter record vouches for it."""
    _, client, config = server(tmp_path)
    doc = made(client)
    name = built(client, doc["id"])["progress"]["name"]
    url = f"/api/v1/documents/{doc['id']}/audiobook/{name}"
    assert client.get(url).status_code == 200
    path = book_folder(config.output_folder) / name
    path.write_bytes(path.read_bytes() + b"\0")
    assert client.get(url).status_code == 404
    assert client.get(url + "?download=true").status_code == 404


def test_an_audiobook_made_before_the_chapter_record_offers_its_own_m4b(tmp_path: Path) -> None:
    """An audiobook of before #723 has no chapter record: the M4B its job wrote is
    served as it is, and no other kind can be built from it (409 not-buildable)."""
    app, client, config = server(tmp_path)
    doc = made(client)
    stored = app.state.sci2audio.store.get(doc["id"])
    folder = book_folder(config.output_folder)
    # the job of before #725 wrote the M4B with the chapters (D-895)
    app_job = run_audio_job(
        stored.source,
        JobSettings(output_folder=folder),
        stored.folder,
        voice=FakeVoice().source(),
        output_settings=OutputSettings(),
        overwrite=True,
    )
    m4b = app_job.written.m4b
    assert m4b is not None
    (stored.folder / "chapters.json").unlink()  # made before #723
    jobs = len(client.get("/api/v1/jobs").json())
    answer = ask(client, doc["id"], kind="m4b")
    assert answer.status_code == 200, answer.text
    assert answer.json() == {"name": m4b.name, "partial": False, "job": None}
    got = client.get(f"/api/v1/documents/{doc['id']}/audiobook/{m4b.name}?download=true")
    assert got.status_code == 200
    assert got.content == m4b.read_bytes()
    refused = ask(client, doc["id"], kind="mp3")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"] == "not-buildable"
    assert len(client.get("/api/v1/jobs").json()) == jobs  # no job for either


def test_a_build_after_the_speech_cache_was_freed_fails_as_missing_chapters(
    tmp_path: Path,
) -> None:
    """The chapters are made, but their speech was freed since (D-158): the book job
    ends with the kind `missing-chapters`, nothing spoken again, no file written."""
    _, client, config = server(tmp_path)
    doc = made(client)
    freed = client.delete(f"/api/v1/documents/{doc['id']}/chunks")
    assert freed.status_code in (200, 204), freed.text
    answer = ask(client, doc["id"], kind="m4b")
    assert answer.status_code == 202, answer.text
    done = wait(client, answer.json()["job"]["id"])
    assert done["state"] == "failed"
    assert done["error"]["error"] == "missing-chapters"
    assert "no longer in the working folder" in done["error"]["message"]
    assert not any(p.suffix == ".m4b" for p in book_folder(config.output_folder).iterdir())
