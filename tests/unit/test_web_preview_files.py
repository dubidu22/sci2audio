"""The server additions of #77: the voice preview job (D-249), one engine kept for previews
and audio jobs (D-250), the latest analysis' files and saving files (D-255)."""

from __future__ import annotations

import errno
import wave
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from web_helpers import (
    make_config,
    offline,  # noqa: F401 - fixture
    paper_bytes,
    program,
    upload,
    wait,
)

from sci2audio.voices import PREVIEW_TEXT, EngineError, download_plan
from sci2audio.web import api, create_app, tasks

pytestmark = pytest.mark.usefixtures("offline")


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The voice files count as installed (the fake voice needs none)."""
    monkeypatch.setattr(api, "missing_files", lambda folder: [])


def server(tmp_path: Path, voice: FakeVoice) -> tuple[Any, Any, Any]:
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    return program(app, config), config, app.state.sci2audio


def preview(client: Any, **body: Any) -> Any:
    return client.post("/api/v1/voices/preview", json=body)


@pytest.mark.usefixtures("installed")
def test_a_preview_speaks_at_the_chosen_letter_pace(tmp_path: Path) -> None:
    """#295: the preview lets the listener hear the pace of spelled letters."""
    voice = FakeVoice()
    client, _, _ = server(tmp_path, voice)
    job = preview(client, text="We use NLP.", letter_pace="slowest").json()
    assert job["settings"]["letter_pace"] == "slowest"
    assert wait(client, job["id"])["state"] == "done"
    job = preview(client, text="We use NLP.").json()
    assert wait(client, job["id"])["state"] == "done"
    assert voice.letter_speeds == [0.5, None]
    assert preview(client, letter_pace="fast").status_code == 422


@pytest.mark.usefixtures("installed")
def test_a_preview_speaks_the_sentence_into_a_wav(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, config, _ = server(tmp_path, voice)
    response = preview(client, voice="bm_george", speed=1.25)
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["id"] == "preview-1"
    assert job["kind"] == "preview"
    assert job["cancellable"] is False
    assert job["settings"] == {"voice": "bm_george", "speed": 1.25, "letter_pace": "normal"}
    ended = wait(client, job["id"])
    assert ended["state"] == "done", ended["error"]
    assert ended["progress"]["phase"] == "done"
    assert ended["progress"]["seconds"] > 0
    assert voice.spoken == [(PREVIEW_TEXT, "bm_george", 1.25)]  # #18's sentence by default
    assert [f["name"] for f in ended["files"]] == ["preview.wav"]
    target = config.work_root / "preview" / "preview.wav"
    assert ended["files"][0]["folder"] == str(target.parent)
    answer = client.get("/api/v1/jobs/preview-1/files/preview.wav")
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "audio/wav"
    assert answer.headers["content-disposition"].startswith("inline")
    with wave.open(str(target)) as audio:
        assert audio.getnchannels() == 1
        assert audio.getnframes() > 0
    assert not list(target.parent.glob("*.part"))


@pytest.mark.usefixtures("installed")
def test_a_preview_reads_the_persons_sentence_with_the_default_voice(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, _, _ = server(tmp_path, voice)
    job = preview(client, text="  Water boils\nat 100 °C.  ").json()
    assert wait(client, job["id"])["state"] == "done"
    assert voice.spoken == [("Water boils at 100 °C.", "af_heart", 1.0)]


@pytest.mark.usefixtures("installed")
@pytest.mark.parametrize(
    ("body", "wanted"),
    [
        ({"text": ""}, "text"),
        ({"text": "   "}, "empty"),
        ({"text": "x" * 301}, "text"),
        ({"voice": "zz_nobody"}, "unknown voice"),
        ({"speed": 2.5}, "speed must be between"),
        ({"speed": 0.25}, "speed must be between"),
        ({"loud": True}, "loud"),
    ],
)
def test_a_wrong_preview_is_refused(tmp_path: Path, body: dict[str, Any], wanted: str) -> None:
    voice = FakeVoice()
    client, _, _ = server(tmp_path, voice)
    response = preview(client, **body)
    assert response.status_code == 422
    assert wanted in response.json()["message"]
    assert client.get("/api/v1/jobs").json() == []


def test_no_preview_without_the_voice_files(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, _, _ = server(tmp_path, voice)
    response = preview(client)
    assert response.status_code == 409
    assert response.json()["error"] == "voice-missing"
    assert voice.made == 0


def test_a_preview_needs_only_its_own_voice_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-468: with the German pack missing, Thorsten cannot preview, English voices can."""
    german = list(download_plan(["de"]).files)
    monkeypatch.setattr(api, "missing_files", lambda folder: german)
    voice = FakeVoice()
    client, _, _ = server(tmp_path, voice)
    refused = preview(client, voice="dm_thorsten")
    assert refused.status_code == 409
    assert refused.json()["error"] == "voice-missing"
    assert voice.made == 0
    response = preview(client, voice="af_heart")
    assert response.status_code == 202, response.text
    assert wait(client, response.json()["id"])["state"] == "done"


@pytest.mark.usefixtures("installed")
def test_a_preview_waits_for_a_running_job(tmp_path: Path) -> None:
    import threading

    voice = FakeVoice()
    client, _, state = server(tmp_path, voice)
    gate = threading.Event()
    from sci2audio.web.jobs import JobKind

    job = state.board.start(
        JobKind.VOICES, None, None, lambda job: gate.wait(10) and [], cancellable=False
    )
    try:
        response = preview(client)
        assert response.status_code == 409
        assert response.json()["error"] == "busy"
    finally:
        gate.set()
        job.join(10)


@pytest.mark.usefixtures("installed")
def test_the_voice_stays_loaded_between_previews_and_for_the_audio_job(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, _, state = server(tmp_path, voice)
    for _ in range(3):
        assert wait(client, preview(client).json()["id"])["state"] == "done"
    assert voice.made == 1  # loaded once (D-250)
    assert voice.released == 0
    assert state.kept.loaded
    doc = upload(client, paper_bytes(), "paper.pdf")
    job = client.post("/api/v1/jobs", json={"kind": "audio", "document": doc["id"]}).json()
    assert wait(client, job["id"])["state"] == "done"
    assert voice.made == 1  # the audio job spoke with the same engine
    state.kept.dispose()
    assert voice.released == 1
    assert not state.kept.loaded
    assert wait(client, preview(client).json()["id"])["state"] == "done"
    assert voice.made == 2


@pytest.mark.usefixtures("installed")
def test_a_failed_preview_drops_the_engine(tmp_path: Path) -> None:
    voice = FakeVoice(fail_on=lambda text: "broken" in text)
    client, _, state = server(tmp_path, voice)
    ended = wait(client, preview(client, text="a broken sentence").json()["id"])
    assert ended["state"] == "failed"
    assert ended["error"]["error"] == "voice-failed"
    assert ended["files"] == []
    assert not state.kept.loaded
    assert voice.released == 1


@pytest.mark.usefixtures("installed")
def test_an_engine_that_cannot_load_fails_the_preview(tmp_path: Path) -> None:
    voice = FakeVoice(fail_to_make=EngineError("the model file is damaged"))
    client, _, state = server(tmp_path, voice)
    ended = wait(client, preview(client).json()["id"])
    assert ended["state"] == "failed"
    assert ended["error"] == {"error": "voice-failed", "message": "the model file is damaged"}
    assert not state.kept.loaded


@pytest.mark.usefixtures("installed")
def test_a_full_disk_during_a_preview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    voice = FakeVoice()
    client, config, _ = server(tmp_path, voice)
    real = tasks.speak_to_wav

    def full(session: Any, text: str, voice_id: str, path: Path, **kwargs: Any) -> float:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(tasks, "speak_to_wav", full)
    ended = wait(client, preview(client).json()["id"])
    assert ended["state"] == "failed"
    assert ended["error"]["error"] == "disk-full"
    assert ended["files"] == []
    folder = config.work_root / "preview"
    assert not folder.exists() or list(folder.iterdir()) == []
    monkeypatch.setattr(tasks, "speak_to_wav", real)
    assert wait(client, preview(client).json()["id"])["state"] == "done"


@pytest.mark.usefixtures("installed")
def test_a_new_preview_replaces_the_last_one(tmp_path: Path) -> None:
    voice = FakeVoice()
    client, config, _ = server(tmp_path, voice)
    wait(client, preview(client, text="One.").json()["id"])
    first = (config.work_root / "preview" / "preview.wav").stat().st_size
    wait(client, preview(client, text="A much longer sentence than the first one.").json()["id"])
    assert sorted(p.name for p in (config.work_root / "preview").iterdir()) == ["preview.wav"]
    assert (config.work_root / "preview" / "preview.wav").stat().st_size > first


def test_the_latest_analysis_files_can_be_fetched_by_name(tmp_path: Path) -> None:
    client, _, _ = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes(), "My paper.pdf")
    base = f"/api/v1/documents/{doc['id']}/files"
    assert client.get(f"{base}/My paper.report.md").status_code == 404  # not analysed yet
    job = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]}).json()
    wait(client, job["id"])
    for name, kind in (
        ("My paper.script.txt", "text/plain"),
        ("My paper.report.md", "text/markdown"),
        ("My paper.report.json", "application/json"),
    ):
        answer = client.get(f"{base}/{name}")
        assert answer.status_code == 200, name
        assert answer.headers["content-type"].startswith(kind)
        assert answer.headers["content-disposition"].startswith("inline")
        saved = client.get(f"{base}/{name}", params={"download": "true"})
        assert saved.headers["content-disposition"].startswith("attachment")
        assert saved.content == answer.content
    for name in ("job.json", "..%2Fjob.json", "My paper.pdf", "source"):
        assert client.get(f"{base}/{name}").status_code == 404, name
    assert client.get("/api/v1/documents/0123456789abcdef/files/x.md").status_code == 404


def test_job_files_can_be_saved_instead_of_shown(tmp_path: Path) -> None:
    client, _, _ = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes(), "paper.pdf")
    job = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]}).json()
    ended = wait(client, job["id"])
    name = ended["files"][0]["name"]
    url = f"/api/v1/jobs/{job['id']}/files/{name}"
    assert client.get(url).headers["content-disposition"].startswith("inline")
    assert (
        client.get(url, params={"download": "1"})
        .headers["content-disposition"]
        .startswith("attachment")
    )
    assert client.get(url, params={"download": "maybe"}).status_code == 422


def test_the_speech_cache_size_is_reported_and_freed(tmp_path: Path) -> None:
    client, _, _ = server(tmp_path, FakeVoice())
    doc = upload(client, paper_bytes(), "paper.pdf")
    assert doc["speech_cache_bytes"] == 0
    job = client.post("/api/v1/jobs", json={"kind": "audio", "document": doc["id"]}).json()
    assert wait(client, job["id"])["state"] == "done"
    after = client.get(f"/api/v1/documents/{doc['id']}").json()
    assert after["speech_cache_bytes"] > 0
    assert client.delete(f"/api/v1/documents/{doc['id']}/chunks").status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["speech_cache_bytes"] == 0
