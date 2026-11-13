"""Removing an opened document and its working folder (#120, D-353 to D-363).

The removal deletes the whole working folder and nothing else; it is refused while a job
works on the document; a removal that fails part-way leaves the document listed."""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
import stat
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from fastapi.testclient import TestClient
from markupsafe import escape
from pdf_maker import Text, make_pdf
from web_helpers import (
    ORIGIN,
    browser,
    make_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    program,
    upload,
    wait,
)

from sci2audio.app import JobRunner, JobSettings
from sci2audio.app.job import Phase, ScriptJob
from sci2audio.app.lock import LOCK_NAME, work_folder_lock
from sci2audio.web import create_app, documents
from sci2audio.web.documents import DocumentBusyError, DocumentStore
from sci2audio.web.jobs import JobBoard, JobKind, JobState
from sci2audio.web.tasks import classify

pytestmark = pytest.mark.usefixtures("offline")


def note(text: str = "A short note.") -> bytes:
    lines = (text, "It has two lines.")
    return make_pdf([Text(line, 72, 100 + 14 * n, size=11) for n, line in enumerate(lines)])


class HeldRunner(JobRunner):
    """The real script job, but only after `go` is set."""

    def __init__(self) -> None:
        super().__init__()
        self.go = threading.Event()
        self.started = threading.Event()

    def run_script(
        self, source: Path, settings: JobSettings, work: Path, **kwargs: Any
    ) -> ScriptJob:
        progress = kwargs.get("progress")
        if progress:
            progress(Phase.READING)
        self.started.set()
        assert self.go.wait(30)
        return super().run_script(source, settings, work, **kwargs)


def server(
    tmp_path: Path, voice: FakeVoice | None = None, runner: JobRunner | None = None
) -> tuple[Any, Any, Any]:
    config = make_config(tmp_path)
    voice = voice or FakeVoice()
    app = create_app(config, runner=runner, voice=lambda models_dir: voice.source())
    return app, program(app, config), config


def start(client: TestClient, document: str, kind: str) -> dict[str, Any]:
    response = client.post("/api/v1/jobs", json={"kind": kind, "document": document})
    assert response.status_code == 202, response.text
    return response.json()


def snapshot(folder: Path) -> dict[str, bytes]:
    """Every file under `folder` with its bytes."""
    if not folder.exists():
        return {}
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def tree_size(folder: Path) -> int:
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())


def made(client: TestClient, data: bytes, name: str = "note.pdf") -> dict[str, Any]:
    """A document with an analysis, a speech cache, the records and an audiobook."""
    doc = upload(client, data, name)
    assert wait(client, start(client, doc["id"], "script")["id"])["state"] == "done"
    assert wait(client, start(client, doc["id"], "audio")["id"])["state"] == "done"
    return doc


# --- what goes and what stays (D-353, D-358) ---------------------------------------------


def test_removing_takes_the_whole_working_folder_and_nothing_else(tmp_path: Path) -> None:
    _app, client, config = server(tmp_path)
    doc = made(client, note(), "note.pdf")
    other = made(client, note("Another note."), "other.pdf")
    saved = client.put("/api/v1/settings", json={"speed": 1.25})
    assert saved.status_code == 200
    folder = config.work_root / doc["id"]
    names = {path.name for path in folder.iterdir()}
    assert {"source", "script", "chunks", "job.json", "audio.json", "document.json"} <= names
    assert {"audiobook.json", LOCK_NAME} <= names
    preview = config.work_root / "preview" / "kept.wav"  # the voice preview's folder
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"RIFF")
    kept = {
        "output": snapshot(config.output_folder),
        "other": snapshot(config.work_root / other["id"]),
        "preview": snapshot(preview.parent),
        "settings": config.config_file.read_bytes(),
    }
    assert kept["output"]  # the audiobooks
    size = tree_size(folder)

    response = client.delete(f"/api/v1/documents/{doc['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": doc["id"],
        "name": "note.pdf",
        "freed_bytes": size,
        "audiobook_folder": str(config.output_folder.absolute()),
    }
    assert not folder.exists()
    assert snapshot(config.output_folder) == kept["output"]
    assert snapshot(config.work_root / other["id"]) == kept["other"]
    assert snapshot(preview.parent) == kept["preview"]
    assert config.config_file.read_bytes() == kept["settings"]
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    assert [d["id"] for d in client.get("/api/v1/documents").json()] == [other["id"]]
    again = client.delete(f"/api/v1/documents/{doc['id']}")
    assert again.status_code == 404
    assert again.json()["error"] == "not-found"


def test_a_document_without_an_audiobook_names_no_folder(tmp_path: Path) -> None:
    _app, client, config = server(tmp_path)
    doc = upload(client, pdf_bytes())
    response = client.delete(f"/api/v1/documents/{doc['id']}")
    assert response.status_code == 200
    assert response.json()["audiobook_folder"] is None
    assert response.json()["freed_bytes"] == len(pdf_bytes())
    assert [path.name for path in config.work_root.iterdir()] == [".incoming"]  # uploads


@pytest.mark.parametrize(
    "document_id",
    ["0123456789abcdef", "0123456789ABCDEF", "short", "..", "0123456789abcdef0", "%2E%2E"],
)
def test_unknown_and_malformed_ids_are_not_found(tmp_path: Path, document_id: str) -> None:
    _app, client, config = server(tmp_path)
    doc = upload(client, pdf_bytes())
    before = snapshot(config.work_root)
    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 404
    assert response.json()["error"] == "not-found"
    assert snapshot(config.work_root) == before
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 200


def test_a_link_inside_the_folder_is_removed_not_followed(tmp_path: Path) -> None:
    _app, client, config = server(tmp_path)
    doc = upload(client, pdf_bytes())
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "keep.txt").write_text("mine")
    folder = config.work_root / doc["id"]
    try:
        (folder / "link-to-folder").symlink_to(outside, target_is_directory=True)
        (folder / "script").mkdir()
        (folder / "script" / "link-to-file").symlink_to(outside / "keep.txt")
    except OSError:
        pytest.skip("this system makes no symbolic links for this user")
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200
    assert not folder.exists()
    assert (outside / "keep.txt").read_text() == "mine"


# --- busy (D-356, D-362) -----------------------------------------------------------------


def test_refused_while_an_audio_job_works_on_the_document(tmp_path: Path) -> None:
    gate = threading.Event()
    reached = threading.Event()

    def held(text: str) -> bool:
        if "two lines" in text:
            reached.set()
            assert gate.wait(10)
        return False

    _app, client, config = server(tmp_path, FakeVoice(fail_on=held))
    doc = upload(client, note())
    other = upload(client, note("Another note."), "other.pdf")
    job = start(client, doc["id"], "audio")
    assert reached.wait(30)
    before = snapshot(config.work_root / doc["id"])
    busy = client.delete(f"/api/v1/documents/{doc['id']}")
    assert busy.status_code == 409
    assert busy.json()["error"] == "busy"
    assert job["id"] in busy.json()["message"]
    assert snapshot(config.work_root / doc["id"]) == before
    # a job on another document doesn't block
    assert client.delete(f"/api/v1/documents/{other['id']}").status_code == 200
    gate.set()
    assert wait(client, job["id"])["state"] == "done"
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200


def test_refused_while_a_script_job_works_on_the_document(tmp_path: Path) -> None:
    runner = HeldRunner()
    _app, client, config = server(tmp_path, runner=runner)
    doc = upload(client, pdf_bytes())
    job = start(client, doc["id"], "script")
    assert runner.started.wait(10)
    busy = client.delete(f"/api/v1/documents/{doc['id']}")
    assert busy.status_code == 409
    assert busy.json()["error"] == "busy"
    assert (config.work_root / doc["id"] / "source").is_dir()
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 200  # listed again
    runner.go.set()
    assert wait(client, job["id"])["state"] == "done"
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200


def test_refused_while_another_process_holds_the_working_folder(tmp_path: Path) -> None:
    _app, client, config = server(tmp_path)
    doc = upload(client, pdf_bytes())
    folder = config.work_root / doc["id"]
    with work_folder_lock(folder):  # what a command-line audio job holds (D-161)
        before = snapshot(folder)
        busy = client.delete(f"/api/v1/documents/{doc['id']}")
        assert snapshot(folder) == before
    assert busy.status_code == 409
    assert busy.json()["error"] == "busy"
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 200
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200


def test_a_preview_or_the_voice_download_does_not_block(tmp_path: Path) -> None:
    app, client, _config = server(tmp_path)
    doc = upload(client, pdf_bytes())
    gate = threading.Event()
    board = app.state.sci2audio.board

    def held(job: Any) -> list[Path]:
        assert gate.wait(10)
        return []

    job = board.start(JobKind.PREVIEW, None, None, held, cancellable=False)
    try:
        assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200
    finally:
        gate.set()
        job.join(10)


# --- the origin check stays (D-194, D-358) -----------------------------------------------


def test_a_browser_removes_only_with_its_own_origin(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    app = create_app(config)
    client = browser(app, config)
    data = pdf_bytes()
    doc = client.post(
        "/api/v1/documents",
        files={"file": ("a.pdf", data, "application/pdf")},
        headers={"Origin": ORIGIN},
    ).json()
    folder = config.work_root / doc["id"]
    before = snapshot(folder)
    for headers in ({}, {"Origin": "null"}, {"Origin": "http://127.0.0.1:9999"}):
        refused = client.delete(f"/api/v1/documents/{doc['id']}", headers=headers)
        assert refused.status_code == 403, headers
        assert snapshot(folder) == before
    cross = client.delete(
        f"/api/v1/documents/{doc['id']}",
        headers={"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"},
    )
    assert cross.status_code == 403
    nobody = TestClient(app, base_url=ORIGIN).delete(
        f"/api/v1/documents/{doc['id']}", headers={"Origin": ORIGIN}
    )
    assert nobody.status_code == 401
    assert snapshot(folder) == before
    removed = client.delete(f"/api/v1/documents/{doc['id']}", headers={"Origin": ORIGIN})
    assert removed.status_code == 200
    assert not folder.exists()


# --- this run's jobs (D-357) -------------------------------------------------------------


def test_the_removed_documents_finished_jobs_are_forgotten(tmp_path: Path) -> None:
    _app, client, _config = server(tmp_path)
    doc = made(client, note())
    other = upload(client, note("Another note."), "other.pdf")
    other_job = start(client, other["id"], "script")
    wait(client, other_job["id"])
    jobs = [j["id"] for j in client.get("/api/v1/jobs").json() if j["document"] == doc["id"]]
    assert len(jobs) == 2
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200
    for job_id in jobs:
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert [j["id"] for j in client.get("/api/v1/jobs").json()] == [other_job["id"]]


def test_forget_keeps_a_running_job_and_other_documents_jobs() -> None:
    board = JobBoard(classify)
    gate = threading.Event()

    def held(job: Any) -> list[Path]:
        assert gate.wait(10)
        return []

    ended = board.start(JobKind.SCRIPT, "a" * 16, None, lambda job: [], cancellable=False)
    ended.join(10)
    other = board.start(JobKind.SCRIPT, "b" * 16, None, lambda job: [], cancellable=False)
    other.join(10)
    running = board.start(JobKind.AUDIO, "a" * 16, None, held, cancellable=True)
    try:
        assert board.forget("a" * 16) == 1
        assert board.get(ended.id) is None
        assert board.get(other.id) is other
        assert board.current is running
    finally:
        gate.set()
        running.join(10)
    assert running.state is JobState.DONE
    assert board.forget("a" * 16) == 1
    assert board.all() == [other]


# --- failures part-way (D-355) -----------------------------------------------------------


def _patched_unlink(monkeypatch: pytest.MonkeyPatch, before: Callable[[str, Any], None]) -> None:
    real = os.unlink

    def unlink(path: Any, *args: Any, **kwargs: Any) -> None:
        before(os.fsdecode(path), kwargs.get("dir_fd"))
        real(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)


def test_a_file_removed_during_the_removal_is_fine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app, client, config = server(tmp_path)
    doc = made(client, note())
    folder = config.work_root / doc["id"]
    wavs = sorted((folder / "chunks").rglob("*.wav"))
    assert len(wavs) >= 2
    stolen: list[Path] = []
    started: list[bool] = []

    def steal(name: str, dir_fd: Any) -> None:
        if not started:  # someone else removes the other chunks just before rmtree gets there
            started.append(True)
            for wav in wavs:
                if wav.name != Path(name).name:
                    wav.unlink()
                    stolen.append(wav)
            (folder / "job.json").unlink()

    _patched_unlink(monkeypatch, steal)
    response = client.delete(f"/api/v1/documents/{doc['id']}")
    assert response.status_code == 200, response.text
    assert stolen
    assert not folder.exists()


def test_a_file_that_cant_be_removed_keeps_the_document_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app, client, config = server(tmp_path)
    doc = made(client, note())
    folder = config.work_root / doc["id"]
    stuck = sorted((folder / "chunks").rglob("*.wav"))[0]

    def refuse(name: str, dir_fd: Any) -> None:
        if Path(name).name == stuck.name:
            raise PermissionError(errno.EACCES, "Permission denied", name)

    _patched_unlink(monkeypatch, refuse)
    response = client.delete(f"/api/v1/documents/{doc['id']}")
    assert response.status_code == 500
    assert response.json()["error"] == "remove-failed"
    assert stuck.name in response.json()["message"]
    assert stuck.is_file()
    # the source goes last, so the document is still there for another try
    listed = client.get(f"/api/v1/documents/{doc['id']}")
    assert listed.status_code == 200
    assert (folder / "source" / "note.pdf").is_file()
    monkeypatch.undo()
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 200
    assert not folder.exists()


def test_a_read_only_file_and_folder_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to remove a read-only file; here every system does (the root user on
    Linux would otherwise remove it anyway), and the removal makes it writable once."""
    _app, client, config = server(tmp_path)
    doc = made(client, note())
    folder = config.work_root / doc["id"]
    report = folder / "script" / "note.report.json"
    if not report.is_file():
        report = sorted((folder / "script").iterdir())[0]
    report.chmod(stat.S_IREAD)
    record = folder / "audio.json"
    record.chmod(stat.S_IREAD)
    refused: list[str] = []

    def windows_like(name: str, dir_fd: Any) -> None:
        mode = os.stat(name, dir_fd=dir_fd).st_mode if dir_fd is not None else os.stat(name).st_mode
        if not mode & stat.S_IWUSR:
            refused.append(Path(name).name)
            raise PermissionError(errno.EACCES, "Access is denied", name)

    _patched_unlink(monkeypatch, windows_like)
    response = client.delete(f"/api/v1/documents/{doc['id']}")
    assert response.status_code == 200, response.text
    assert set(refused) == {report.name, record.name}
    assert not folder.exists()


# --- removal and opening the same file at once (D-356) -----------------------------------


def test_during_a_removal_the_document_is_gone_and_opening_it_again_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app, client, config = server(tmp_path)
    data = note()
    doc = made(client, data)
    folder = config.work_root / doc["id"]
    reached = threading.Event()
    go = threading.Event()
    real = documents._remove_entry

    def held(path: Path) -> None:
        if path.name == "source":
            reached.set()
            assert go.wait(10)
        real(path)

    monkeypatch.setattr(documents, "_remove_entry", held)
    answers: dict[str, Any] = {}
    removing = threading.Thread(
        target=lambda: answers.update(removed=client.delete(f"/api/v1/documents/{doc['id']}"))
    )
    removing.start()
    try:
        assert reached.wait(10)
        assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
        assert doc["id"] not in [d["id"] for d in client.get("/api/v1/documents").json()]
        job = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]})
        assert job.status_code == 404
        assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 404
        opening = threading.Thread(
            target=lambda: answers.update(opened=upload(client, data, "again.pdf"))
        )
        opening.start()
        opening.join(0.5)
        assert opening.is_alive()  # waits for the removal
    finally:
        go.set()
        removing.join(10)
    opening.join(10)
    assert answers["removed"].status_code == 200
    assert answers["opened"]["id"] == doc["id"]
    assert answers["opened"]["has_report"] is False
    assert snapshot(folder) == {"source/again.pdf": data}  # a fresh folder


def test_the_store_asks_whether_busy_only_once_the_id_is_gone(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "work", upload_limit=10**6, text_limit=10**6)
    data = pdf_bytes()
    import io

    stored = store.store("a.pdf", io.BytesIO(data))
    seen: list[object] = []

    def busy() -> str | None:
        seen.append(store.get(stored.id))
        return "a job works on it"

    with pytest.raises(DocumentBusyError, match="a job works on it"):
        store.remove(stored.id, busy=busy)
    assert seen == [None]
    assert store.get(stored.id) == stored  # refused: listed again
    assert store.remove("0123456789abcdef", busy=lambda: None) is None
    removed = store.remove(stored.id, busy=lambda: None)
    assert removed is not None
    assert (removed.id, removed.name, removed.freed_bytes) == (stored.id, "a.pdf", len(data))
    assert hashlib.sha256(data).hexdigest()[:16] == stored.id
    assert [path.name for path in (tmp_path / "work").iterdir()] == [".incoming"]


@pytest.mark.skipif(sys.platform == "win32", reason="a folder link needs rights on Windows")
def test_a_working_folder_that_is_a_link_is_refused(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "work", upload_limit=10**6, text_limit=10**6)
    elsewhere = tmp_path / "elsewhere" / "source"
    elsewhere.mkdir(parents=True)
    (elsewhere / "mine.pdf").write_bytes(b"%PDF")
    store.root.mkdir()
    (store.root / ("c" * 16)).symlink_to(elsewhere.parent, target_is_directory=True)
    with pytest.raises(documents.RemoveError, match="link"):
        store.remove("c" * 16, busy=lambda: None)
    assert (elsewhere / "mine.pdf").read_bytes() == b"%PDF"


# --- the pages (D-359, D-360, D-362) -----------------------------------------------------


def test_the_start_page_and_the_document_page_offer_the_removal(tmp_path: Path) -> None:
    app, client, config = server(tmp_path)
    doc = made(client, note(), "note.pdf")
    page = browser(app, config)
    start = page.get("/").text
    assert '<details class="remove">' in start
    assert "<summary>Remove note.pdf…</summary>" in start
    assert f'data-document="{doc["id"]}"' in start
    assert "Remove note.pdf now" in start
    assert f"Your audiobook stays in {config.output_folder.absolute()}." in start
    document = page.get(f"/documents/{doc['id']}").text
    assert '<h2 id="step-remove">Remove this document</h2>' in document
    assert "<summary>Remove this document…</summary>" in document
    assert "Remove note.pdf now" in document
    assert '<section id="removed" aria-labelledby="removed-title" hidden>' in document
    german = page.get("/", headers={"Accept-Language": "de"}).text
    assert "note.pdf jetzt entfernen" in german
    assert "Ihr Hörbuch bleibt in" in german


def test_while_a_job_works_the_page_says_so_instead_of_the_button(tmp_path: Path) -> None:
    runner = HeldRunner()
    app, client, config = server(tmp_path, runner=runner)
    doc = upload(client, pdf_bytes(), "busy.pdf")
    other = upload(client, note(), "free.pdf")
    job = start(client, doc["id"], "script")
    assert runner.started.wait(10)
    page = browser(app, config)
    try:
        start_page = page.get("/").text
        assert start_page.count("is working on this document") == 1
        assert "Remove busy.pdf now" not in start_page
        assert "Remove free.pdf now" in start_page
        document = page.get(f"/documents/{doc['id']}").text
        assert "is working on this document; you can remove it when the job has ended" in document
        assert 'class="remove-now"' not in document
        assert 'class="remove-now"' in page.get(f"/documents/{other['id']}").text
    finally:
        runner.go.set()
        wait(client, job["id"])


def test_the_page_never_trusts_the_file_name(tmp_path: Path) -> None:
    app, client, config = server(tmp_path)
    doc = upload(client, pdf_bytes(), "A&B 'x' <b>.pdf")
    text = browser(app, config).get("/").text
    assert "<b>" not in text
    shown = escape(doc["name"])
    assert f"Remove {shown} now" in text
    assert f"<summary>Remove {shown}…</summary>" in text


def test_the_privacy_page_names_the_removal(tmp_path: Path) -> None:
    app, _client, config = server(tmp_path)
    text = browser(app, config).get("/privacy").text
    assert "can remove a document with all of this" in text
    assert "Remove this document" in text


def test_shutil_rmtree_takes_the_handler() -> None:
    """The removal relies on `onexc` (Python 3.12+), the project's minimum."""
    import inspect

    assert "onexc" in inspect.signature(shutil.rmtree).parameters
