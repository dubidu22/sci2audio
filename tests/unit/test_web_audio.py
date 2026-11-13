"""Audio jobs through the API (#71 on the server, D-199 to D-202, D-208, D-209): with the
fake voice and the real ffmpeg on a few seconds of audio (D-118)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf
from web_helpers import (
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    program,
    upload,
    wait,
)

from sci2audio.app import default_work_folder
from sci2audio.web import create_app
from sci2audio.web.config import default_work_root

pytestmark = pytest.mark.usefixtures("offline")


def note() -> bytes:
    lines = ("A short note.", "It has two lines.")
    return make_pdf([Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(lines)])


def server(tmp_path: Path, voice: FakeVoice) -> tuple[Any, Any]:
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    return program(app, config), config


def start_audio(client: Any, document: str, **body: Any) -> dict[str, Any]:
    response = client.post("/api/v1/jobs", json={"kind": "audio", "document": document, **body})
    assert response.status_code == 202, response.text
    return response.json()


def test_an_audio_job_writes_the_audiobook_to_the_output_folder(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, config = server(tmp_path, voice)
    doc = upload(client, note(), "note.pdf")
    job = start_audio(client, doc["id"])
    assert job["id"] == f"{doc['id']}-audio-1"
    seen = events(client, job["id"])
    assert seen[0][0] == "snapshot"
    assert seen[-1][0] == "end"
    phases = [json.loads(data)["phase"] for name, data in seen if name == "progress"]
    assert set(phases) <= {
        "reading",
        "layout",
        "text-steps",
        "loading-voice",
        "speaking",
        "encoding",
        "done",
    }
    final = json.loads(seen[-1][1])
    assert final["state"] == "done", final["error"]
    assert final["progress"]["phase"] == "done"
    assert final["progress"]["skipped"] == []
    assert final["progress"]["spoken"] == len(voice.spoken) > 0
    names = [f["name"] for f in final["files"]]
    assert names[0].endswith(".m4b")
    assert names[-1].endswith(".readalong.json")
    assert any(name.endswith(".mp3") for name in names)
    assert all(f["folder"] == str(config.output_folder) for f in final["files"])
    assert sorted(p.name for p in config.output_folder.iterdir()) == sorted(names)
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["has_audio"] is True

    base = f"/api/v1/jobs/{job['id']}/files"
    m4b = client.get(f"{base}/{names[0]}")
    assert m4b.status_code == 200
    assert m4b.headers["content-type"] == "audio/mp4"
    mp3 = next(name for name in names if name.endswith(".mp3"))
    part = client.get(f"{base}/{mp3}", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert part.headers["content-type"] == "audio/mpeg"
    assert part.content == (config.output_folder / mp3).read_bytes()[:100]
    readalong = client.get(f"{base}/{names[-1]}").json()
    assert readalong["format"] == "sci2audio-readalong"


def test_an_existing_audiobook_is_kept_unless_the_person_says_replace(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, config = server(tmp_path, voice)
    doc = upload(client, note(), "note.pdf")
    assert wait(client, start_audio(client, doc["id"])["id"])["state"] == "done"
    before = {p.name: p.stat().st_mtime_ns for p in config.output_folder.iterdir()}
    refused = wait(client, start_audio(client, doc["id"])["id"])
    assert refused["state"] == "failed"
    assert refused["error"]["error"] == "output-exists"
    assert any(name in refused["error"]["message"] for name in before)
    assert {p.name: p.stat().st_mtime_ns for p in config.output_folder.iterdir()} == before
    made = voice.made
    again = wait(client, start_audio(client, doc["id"], overwrite=True)["id"])
    assert again["state"] == "done"
    assert again["progress"]["spoken"] == 0
    assert again["progress"]["reused"] > 0
    assert voice.made == made  # every chunk came from the cache: the voice was not loaded


def test_the_settings_choose_the_output_folder_and_voice(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, config = server(tmp_path, voice)
    doc = upload(client, note())
    books = tmp_path / "books"
    job = wait(
        client,
        start_audio(
            client, doc["id"], settings={"output_folder": str(books), "voice": "bm_george"}
        )["id"],
    )
    assert job["state"] == "done", job["error"]
    assert {f["folder"] for f in job["files"]} == {str(books)}
    assert not config.output_folder.exists()
    assert {spoken_voice for _, spoken_voice, _ in voice.spoken} == {"bm_george"}


def test_a_sentence_the_voice_fails_on_is_listed(tmp_path: Path) -> None:
    voice = FakeVoice(fail_on=lambda text: "two lines" in text)
    client, _ = server(tmp_path, voice)
    doc = upload(client, note())
    job = wait(client, start_audio(client, doc["id"])["id"])
    assert job["state"] == "done"
    skipped = job["progress"]["skipped"]
    assert len(skipped) == 1
    assert "two lines" in skipped[0]["text"]
    assert skipped[0]["page"] == 1
    assert skipped[0]["error"]


def test_cancelling_while_speaking_keeps_the_chunks(tmp_path: Path) -> None:
    gate = threading.Event()
    reached = threading.Event()

    def held(text: str) -> bool:
        if "two lines" in text:
            reached.set()
            assert gate.wait(10)
        return False

    voice = FakeVoice(fail_on=held)
    client, config = server(tmp_path, voice)
    doc = upload(client, note())
    job = start_audio(client, doc["id"])
    assert reached.wait(30)
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["cancellable"] is True
    busy = client.delete(f"/api/v1/documents/{doc['id']}/chunks")
    assert busy.status_code == 409
    assert busy.json()["error"] == "busy"
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 202
    gate.set()
    done = wait(client, job["id"])
    assert done["state"] == "cancelled"
    assert done["cancellable"] is False
    assert done["files"] == []
    assert not config.output_folder.exists() or list(config.output_folder.iterdir()) == []
    assert list((config.work_root / doc["id"] / "chunks").rglob("*.wav"))
    rest = wait(client, start_audio(client, doc["id"])["id"])
    assert rest["state"] == "done"
    assert rest["progress"]["reused"] >= 1


def test_clearing_the_chunks(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, config = server(tmp_path, voice)
    doc = upload(client, note())
    wait(client, start_audio(client, doc["id"])["id"])
    chunks = config.work_root / doc["id"] / "chunks"
    assert list(chunks.rglob("*.wav"))
    response = client.delete(f"/api/v1/documents/{doc['id']}/chunks")
    assert response.status_code == 204
    assert list(chunks.rglob("*.wav")) == []
    assert (config.work_root / doc["id"] / "audio.json").is_file()  # records stay
    assert client.delete("/api/v1/documents/0123456789abcdef/chunks").status_code == 404


def test_the_servers_work_folders_are_the_audio_jobs_own(tmp_path: Path) -> None:
    source = tmp_path / "x.pdf"
    source.write_bytes(note())
    assert default_work_folder(source).parent == default_work_root()
