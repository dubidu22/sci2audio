"""Jobs through the API (D-199 to D-202): the pre-analysis as a script job, progress
events, files, one job at a time, cancel, and how failures are reported."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from web_helpers import (
    ORIGIN,
    app_and_config,
    browser,
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    program,
    upload,
    wait,
)

from sci2audio.app import JobBusyError, JobRunner, JobSettings, Phase, ScriptJob
from sci2audio.textprep import Category
from sci2audio.web import api, create_app
from sci2audio.web.jobs import JobBoard, JobKind, JobState
from sci2audio.web.tasks import classify

pytestmark = pytest.mark.usefixtures("offline")


class BlockingRunner(JobRunner):
    """Runs the real script job, but only after `go` is set; reports one phase first."""

    def __init__(self, fail: BaseException | None = None) -> None:
        super().__init__()
        self.go = threading.Event()
        self.started = threading.Event()
        self.fail = fail

    def run_script(
        self, source: Path, settings: JobSettings, work: Path, **kwargs: Any
    ) -> ScriptJob:
        progress = kwargs.get("progress")
        if progress:
            progress(Phase.READING)
        self.started.set()
        assert self.go.wait(30)
        if self.fail is not None:
            raise self.fail
        return super().run_script(source, settings, work, **kwargs)


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def start(client: Any, document: str, kind: str = "script", **body: Any) -> dict[str, Any]:
    response = client.post("/api/v1/jobs", json={"kind": kind, "document": document, **body})
    assert response.status_code == 202, response.text
    return response.json()


def test_a_script_job_from_start_to_files(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes(), "note.pdf")
    job = start(client, doc["id"])
    assert job["id"] == f"{doc['id']}-script-1"
    assert job["kind"] == "script"
    assert job["document"] == doc["id"]
    assert job["cancellable"] is False
    seen = events(client, job["id"])
    names = [name for name, _ in seen]
    assert names[0] == "snapshot"
    assert names[-1] == "end"
    assert set(names[1:-1]) <= {"progress"}
    for name, data in seen:
        if name == "progress":
            assert json.loads(data)["phase"] in {str(phase) for phase in Phase}
    final = json.loads(seen[-1][1])
    assert final["state"] == "done"
    assert final["error"] is None
    assert [f["name"] for f in final["files"]] == [
        "note.script.txt",
        "note.report.json",
        "note.report.md",
    ]
    script_folder = config.work_root / doc["id"] / "script"
    assert all(f["folder"] == str(script_folder) for f in final["files"])
    assert (config.work_root / doc["id"] / "job.json").is_file()
    assert not config.output_folder.exists()  # a pre-analysis never writes to the person's folder
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["has_report"] is True

    report = client.get(f"/api/v1/documents/{doc['id']}/report").json()
    assert report["format"] == "sci2audio-report"
    assert report["source"]["name"] == "note.pdf"
    chapters = client.get(f"/api/v1/documents/{doc['id']}/chapters").json()
    assert chapters == [
        {key: chapter[key] for key in chapters[0]} for chapter in report["chapters"]
    ]
    assert chapters[0]["index"] == 0

    base = f"/api/v1/jobs/{job['id']}/files"
    text = client.get(f"{base}/note.script.txt")
    assert text.status_code == 200
    assert text.headers["content-type"] == "text/plain; charset=utf-8"
    assert text.text == (script_folder / "note.script.txt").read_text(encoding="utf-8")
    assert client.get(f"{base}/note.report.json").json() == report
    assert client.get(f"{base}/note.report.md").headers["content-type"].startswith("text/markdown")
    part = client.get(f"{base}/note.report.json", headers={"Range": "bytes=0-9"})
    assert part.status_code == 206
    assert part.content == (script_folder / "note.report.json").read_bytes()[:10]


def test_a_second_analysis_replaces_the_first(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes(), "note.pdf")
    wait(client, start(client, doc["id"])["id"])
    job = wait(client, start(client, doc["id"], settings={"switched_off": ["links"]})["id"])
    assert job["state"] == "done"
    report = client.get(f"/api/v1/documents/{doc['id']}/report").json()
    assert "links" in report["settings"]["switched_off"]


def test_job_settings_come_from_the_saved_ones_with_the_jobs_choices_on_top(
    server: tuple[FastAPI, Any],
) -> None:
    app, config = server
    client = program(app, config)
    saved = {
        "language": "en-GB",
        "switched_off": ["citations"],
        "speed": 1.5,
        "voice": "bf_emma",
        "letter_pace": "slowest",
    }
    assert client.put("/api/v1/settings", json=saved).status_code == 200
    doc = upload(client, pdf_bytes())
    chosen = {"chapters": [0], "speed": 0.8, "letter_pace": "slower"}
    job = wait(client, start(client, doc["id"], settings=chosen)["id"])
    assert job["settings"] == {
        "language": "en-GB",
        "switched_off": ["citations"],
        "chapters": [0],
        "voice": "bf_emma",
        "speed": 0.8,
        "letter_pace": "slower",
        "output_folder": None,
    }
    report = client.get(f"/api/v1/documents/{doc['id']}/report").json()
    assert report["settings"]["chapters"] == [0]
    assert report["settings"]["switched_off"] == ["citations"]
    # a job never saves settings
    assert client.get("/api/v1/settings").json()["settings"]["speed"] == 1.5


@pytest.mark.parametrize(
    "settings",
    [
        {"speed": 9},
        {"switched_off": ["nothing"]},
        {"chapters": [-1]},
        {"voice": "xx_nobody"},
        {"language": "not a tag"},
        {"output_folder": "relative/folder"},
        {"output_folder": "/books\u0000"},
        {"other": 1},
    ],
)
def test_wrong_job_settings_are_refused(
    server: tuple[FastAPI, Any], settings: dict[str, Any]
) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    response = client.post(
        "/api/v1/jobs", json={"kind": "script", "document": doc["id"], "settings": settings}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid"
    assert client.get("/api/v1/jobs").json() == []


@pytest.mark.parametrize("loose", ["yes", "true", "1", 1, 0, None])
def test_overwrite_is_true_or_false_and_nothing_else(
    server: tuple[FastAPI, Any], loose: Any
) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    response = client.post(
        "/api/v1/jobs", json={"kind": "audio", "document": doc["id"], "overwrite": loose}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid"
    assert client.get("/api/v1/jobs").json() == []


def test_unknown_documents_and_kinds(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    response = client.post("/api/v1/jobs", json={"kind": "script", "document": "0123456789abcdef"})
    assert response.status_code == 404
    doc = upload(client, pdf_bytes())
    assert (
        client.post("/api/v1/jobs", json={"kind": "voices", "document": doc["id"]}).status_code
        == 422
    )


def test_one_job_at_a_time(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    runner = BlockingRunner()
    app = create_app(config, runner=runner)
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    first = start(client, doc["id"])
    assert runner.started.wait(10)
    for body in ({"kind": "script", "document": doc["id"]},):
        response = client.post("/api/v1/jobs", json=body)
        assert response.status_code == 409
        assert response.json()["error"] == "busy"
        assert first["id"] in response.json()["message"]
    voices = client.get("/api/v1/voices").json()["plan"]["digest"]
    response = client.post("/api/v1/voices/download", json={"consent": True, "plan": voices})
    assert response.status_code == 409
    running = client.get(f"/api/v1/jobs/{first['id']}").json()
    assert running["state"] == "running"
    assert running["progress"] == {"phase": "reading"}
    cancel = client.post(f"/api/v1/jobs/{first['id']}/cancel")
    assert cancel.status_code == 409
    assert cancel.json()["error"] == "not-cancellable"
    runner.go.set()
    assert wait(client, first["id"])["state"] == "done"
    assert client.post(f"/api/v1/jobs/{first['id']}/cancel").json()["error"] == "finished"
    second = start(client, doc["id"])
    assert second["id"] == f"{doc['id']}-script-2"
    assert wait(client, second["id"])["state"] == "done"
    assert [j["id"] for j in client.get("/api/v1/jobs").json()] == [second["id"], first["id"]]


def test_reopening_a_document_under_a_running_job_keeps_its_file(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    runner = BlockingRunner()
    app = create_app(config, runner=runner)
    client = program(app, config)
    data = pdf_bytes()
    doc = upload(client, data, "a.pdf")
    job = start(client, doc["id"])
    assert runner.started.wait(10)
    assert upload(client, data, "b.pdf")["id"] == doc["id"]
    assert (config.work_root / doc["id"] / "source" / "a.pdf").is_file()
    runner.go.set()
    assert wait(client, job["id"])["state"] == "done"


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (JobBusyError("another job is running"), "busy"),
        (RuntimeError("something odd"), "internal"),
    ],
)
def test_failures_are_reported_with_a_kind_and_words(
    tmp_path: Path, error: BaseException, kind: str
) -> None:
    config = make_config(tmp_path)
    runner = BlockingRunner(fail=error)
    runner.go.set()
    app = create_app(config, runner=runner)
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    job = wait(client, start(client, doc["id"])["id"])
    assert job["state"] == "failed"
    assert job["error"]["error"] == kind
    assert str(error) in job["error"]["message"]
    assert job["files"] == []
    seen = events(client, job["id"])
    assert [name for name, _ in seen] == ["snapshot", "end"]


def test_a_source_removed_before_the_run_fails_with_a_message(
    server: tuple[FastAPI, Any],
) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes(), "gone.pdf")
    source = config.work_root / doc["id"] / "source" / "gone.pdf"
    source.write_bytes(b"not a pdf at all")
    job = wait(client, start(client, doc["id"])["id"])
    assert job["state"] == "failed"
    assert job["error"]["error"] == "job-failed"
    assert "gone.pdf" in job["error"]["message"]


def test_only_files_the_job_wrote_are_served(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes(), "note.pdf")
    job = wait(client, start(client, doc["id"])["id"])
    (config.work_root / doc["id"] / "script" / "other.txt").write_text("secret")
    base = f"/api/v1/jobs/{job['id']}/files"
    for name in (
        "other.txt",
        "..%2F..%2Fsource%2Fnote.pdf",
        "../job.json",
        "%2E%2E",
        "note.pdf",
        "",
    ):
        response = client.get(f"{base}/{name}")
        assert response.status_code == 404, name
    assert client.get("/api/v1/jobs/nothing/files/note.script.txt").status_code == 404
    (config.work_root / doc["id"] / "script" / "note.script.txt").unlink()
    assert client.get(f"{base}/note.script.txt").status_code == 404  # removed since


def test_unknown_jobs(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    for method, path in (
        ("GET", "/api/v1/jobs/nothing"),
        ("GET", "/api/v1/jobs/nothing/events"),
        ("POST", "/api/v1/jobs/nothing/cancel"),
    ):
        response = client.request(method, path)
        assert response.status_code == 404
        assert response.json()["error"] == "not-found"


def test_events_keep_the_stream_alive_and_end_when_the_server_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "KEEP_ALIVE", 0.05)
    config = make_config(tmp_path)
    runner = BlockingRunner()
    app = create_app(config, runner=runner)
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    job = start(client, doc["id"])
    assert runner.started.wait(10)
    timer = threading.Timer(0.5, app.state.sci2audio.stopping.set)
    timer.start()
    try:
        seen = events(client, job["id"])
    finally:
        timer.cancel()
        runner.go.set()
    assert seen[0][0] == "snapshot"
    assert ("", ": keep-alive") in seen
    assert "end" not in [name for name, _ in seen]


def test_a_browser_starts_jobs_with_its_cookie_and_origin(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = browser(app, config)
    doc = client.post(
        "/api/v1/documents",
        files={"file": ("a.pdf", pdf_bytes(), "application/pdf")},
        headers={"Origin": ORIGIN},
    )
    assert doc.status_code == 201
    response = client.post(
        "/api/v1/jobs",
        json={"kind": "script", "document": doc.json()["id"]},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 202
    assert wait(client, response.json()["id"])["state"] == "done"


def test_the_board_names_jobs_and_keeps_them_apart() -> None:
    board = JobBoard(classify)
    gate = threading.Event()

    def held(job: Any) -> list[Path]:
        assert gate.wait(10)
        return []

    first = board.start(JobKind.VOICES, None, None, held, cancellable=True)
    assert first.id == "voices-1"
    assert board.current is first
    with pytest.raises(Exception, match="voices-1 is running"):
        board.start(JobKind.SCRIPT, "0123456789abcdef", None, lambda job: [], cancellable=False)
    gate.set()
    first.join(10)
    assert first.state is JobState.DONE
    assert board.current is None
    second = board.start(JobKind.SCRIPT, "0123456789abcdef", {}, lambda job: [], cancellable=False)
    assert second.id == "0123456789abcdef-script-2"
    second.join(10)
    assert board.get("voices-1") is first
    assert board.get("nothing") is None


def test_shutdown_cancels_the_running_job() -> None:
    board = JobBoard(classify)

    def work(job: Any) -> list[Path]:
        assert job.cancel.wait(10)
        from sci2audio.web.jobs import JobCancelled

        raise JobCancelled

    job = board.start(JobKind.VOICES, None, None, work, cancellable=True)
    board.shutdown(10)
    assert job.state is JobState.CANCELLED
    assert job.snapshot()["error"] == {"error": "cancelled", "message": "the job was cancelled"}


def test_categories_reach_the_job_as_categories(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    doc = upload(client, pdf_bytes())
    every = [str(c) for c in Category]
    job = wait(client, start(client, doc["id"], settings={"switched_off": every})["id"])
    assert job["state"] == "done"
    assert job["settings"]["switched_off"] == sorted(every)
