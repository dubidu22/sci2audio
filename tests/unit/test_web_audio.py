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
    paper_bytes,
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


def test_the_progress_numbers_the_chapter_in_the_job_and_its_stream(tmp_path: Path) -> None:
    """D-695: the job's progress carries `chapter_number` and `chapter_done`, and the
    stream sends them; the existing fields keep their meaning."""
    seen: list[dict[str, Any]] = []
    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    client = program(app, config)
    doc = upload(client, paper_bytes())

    def look(text: str) -> bool:  # before each chunk: the progress after the one before
        job = app.state.sci2audio.board.current
        progress = job.snapshot()["progress"] if job is not None else None
        if progress and progress.get("phase") == "speaking" and progress["chunks_done"]:
            seen.append(progress)
        return False

    voice.fail_on = look
    job = start_audio(client, doc["id"])
    stream = events(client, job["id"])
    assert wait(client, job["id"])["state"] == "done"
    assert [p["chapter_number"] for p in seen] == sorted(p["chapter_number"] for p in seen)
    assert {p["chapter"]: p["chapter_number"] for p in seen} == {0: 1, 1: 2}
    boundary = next(n for n, p in enumerate(seen) if p["chapter_done"])
    assert seen[boundary]["chapter_number"] == 1
    assert seen[boundary + 1]["chapter_number"] == 2
    assert not seen[boundary + 1]["chapter_done"]
    assert all(p["chapters"] == 2 and p["chunks_total"] >= p["chunks_done"] for p in seen)
    # every progress the job tells carries the new fields; the server's own last word,
    # {"phase": "done", ...} with the files, is not one of them, and whether the stream
    # catches it before it ends depends on timing (seen on macOS)
    sent = [json.loads(data) for name, data in stream if name == "progress"]
    told = [p for p in sent if p.get("phase") != "done"]
    assert told
    assert all("chapter_number" in p and "chapter_done" in p for p in told)


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


def six_sentences() -> bytes:
    lines = [
        f"Sentence number {word} is here."
        for word in ("one", "two", "three", "four", "five", "six")
    ]
    return make_pdf([Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(lines)])


def resumed_as_the_card_sends(client: Any, paused: dict[str, Any]) -> dict[str, Any]:
    """Resume posts the paused job's settings and its own `overwrite` (app.js, D-733)."""
    return start_audio(
        client, paused["document"], settings=paused["settings"], overwrite=paused["overwrite"]
    )


def test_a_paused_replace_resumes_without_asking_again(tmp_path: Path) -> None:
    """Colin, 17 Nov: a run replacing a finished audiobook, paused and resumed, stopped at
    "these files exist already". The paused job keeps its "replace" so Resume goes on and
    speaks only the sentences it had not spoken (D-733)."""
    gate, reached, hold = threading.Event(), threading.Event(), {"on": False}

    def held(text: str) -> bool:
        if hold["on"] and "three" in text:
            reached.set()
            assert gate.wait(10)
        return False

    voice = FakeVoice(fail_on=held)
    client, config = server(tmp_path, voice)
    doc = upload(client, six_sentences())
    assert wait(client, start_audio(client, doc["id"])["id"])["state"] == "done"
    assert client.delete(f"/api/v1/documents/{doc['id']}/chunks").status_code == 204
    finished = {p.name: p.stat().st_mtime_ns for p in config.output_folder.iterdir()}

    hold["on"] = True
    job = start_audio(client, doc["id"], overwrite=True)
    assert job["overwrite"] is True
    assert reached.wait(30)
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 202
    gate.set()
    paused = wait(client, job["id"])
    assert paused["state"] == "cancelled"
    assert paused["overwrite"] is True
    done_before = paused["progress"]["chunks_done"]
    assert 0 < done_before < paused["progress"]["chunks_total"]
    # paused mid-speech, the earlier audiobook is untouched: nothing half-written
    assert {p.name: p.stat().st_mtime_ns for p in config.output_folder.iterdir()} == finished

    hold["on"] = False
    spoken = len(voice.spoken)
    resumed = wait(client, resumed_as_the_card_sends(client, paused)["id"])
    assert resumed["state"] == "done", resumed["error"]
    assert resumed["progress"]["reused"] == done_before
    assert resumed["progress"]["spoken"] == paused["progress"]["chunks_total"] - done_before
    assert len(voice.spoken) - spoken == resumed["progress"]["spoken"]


def test_a_replace_paused_while_writing_resumes_without_asking_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paused while the files are written: output has already taken away the old read-along
    (D-119), so the old set is incomplete; Resume writes the whole new set (D-733)."""
    from sci2audio.app import audio

    encode = audio._encode
    writing, gate = threading.Event(), threading.Event()

    def held(*args: Any, **kwargs: Any) -> Any:
        writing.set()
        assert gate.wait(30)
        return encode(*args, **kwargs)

    voice = FakeVoice()
    client, config = server(tmp_path, voice)
    doc = upload(client, six_sentences())
    assert wait(client, start_audio(client, doc["id"])["id"])["state"] == "done"
    names = sorted(p.name for p in config.output_folder.iterdir())

    monkeypatch.setattr(audio, "_encode", held)
    job = start_audio(client, doc["id"], overwrite=True)
    assert writing.wait(30)
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 202
    gate.set()
    paused = wait(client, job["id"])
    assert paused["state"] == "cancelled"
    assert sorted(p.name for p in config.output_folder.iterdir()) != names  # a partial set

    monkeypatch.setattr(audio, "_encode", encode)
    resumed = wait(client, resumed_as_the_card_sends(client, paused)["id"])
    assert resumed["state"] == "done", resumed["error"]
    assert resumed["progress"]["spoken"] == 0  # every sentence came from the cache
    assert sorted(p.name for p in config.output_folder.iterdir()) == names


def test_a_paused_first_build_still_refuses_a_file_that_appeared(tmp_path: Path) -> None:
    """Resume of a run that replaced nothing does not say "replace": an audiobook that
    appeared meanwhile is refused as before (D-163)."""
    gate, reached = threading.Event(), threading.Event()

    def held(text: str) -> bool:
        if "three" in text:
            reached.set()
            assert gate.wait(10)
        return False

    voice = FakeVoice(fail_on=held)
    client, config = server(tmp_path, voice)
    doc = upload(client, six_sentences())
    job = start_audio(client, doc["id"])
    assert job["overwrite"] is False
    assert reached.wait(30)
    client.post(f"/api/v1/jobs/{job['id']}/cancel")
    gate.set()
    paused = wait(client, job["id"])
    assert paused["state"] == "cancelled"
    assert paused["overwrite"] is False
    config.output_folder.mkdir(parents=True, exist_ok=True)
    (config.output_folder / "paper.m4b").write_bytes(b"someone else's")
    voice.fail_on = lambda text: False
    refused = wait(client, resumed_as_the_card_sends(client, paused)["id"])
    assert refused["state"] == "failed"
    assert refused["error"]["error"] == "output-exists"
    assert (config.output_folder / "paper.m4b").read_bytes() == b"someone else's"


def test_script_jobs_never_say_overwrite(tmp_path: Path) -> None:
    client, _ = server(tmp_path, FakeVoice())
    doc = upload(client, note())
    job = client.post(
        "/api/v1/jobs", json={"kind": "script", "document": doc["id"], "overwrite": True}
    ).json()
    assert job["overwrite"] is False
