"""A PDF's pages while it is read, on the server (#343), and a cancel while it is read (#344):
the job ends as cancelled, never as a damaged file."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
import reader_targets
from audio_fakes import FakeVoice
from pdf_maker import Text, make_pdf
from web_helpers import (
    make_config,
    offline,  # noqa: F401 - fixture
    program,
    upload,
    wait,
)

from sci2audio.extraction import isolate, pdf
from sci2audio.web import create_app
from sci2audio.web.jobs import JobRecord

pytestmark = [pytest.mark.usefixtures("offline"), pytest.mark.timeout(120)]


def three_pages() -> bytes:
    return make_pdf(
        *(
            [Text(f"Section {n}", 72, 80, size=14), Text("Some words.", 72, 100, size=11)]
            for n in (1, 2, 3)
        )
    )


def recorded(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every progress report of every job, in order."""
    reports: list[dict[str, Any]] = []
    real = JobRecord.report

    def report(self: JobRecord, progress: dict[str, Any]) -> None:
        reports.append(dict(progress))
        real(self, progress)

    monkeypatch.setattr(JobRecord, "report", report)
    return reports


def test_a_script_job_reports_each_page_it_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = make_config(tmp_path)
    client = program(create_app(config), config)
    doc = upload(client, three_pages(), "three.pdf")
    reports = recorded(monkeypatch)
    response = client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]})
    assert response.status_code == 202, response.text
    assert wait(client, response.json()["id"])["state"] == "done"
    assert [report for report in reports if "page" in report] == [
        {"phase": "reading", "page": page, "pages": 3} for page in (1, 2, 3)
    ]
    assert reports[0] == {"phase": "reading"}


def test_an_audio_job_reports_each_page_it_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = make_config(tmp_path)
    client = program(create_app(config, voice=lambda models: FakeVoice().source()), config)
    doc = upload(client, three_pages(), "three.pdf")
    reports = recorded(monkeypatch)
    response = client.post("/api/v1/jobs", json={"kind": "audio", "document": doc["id"]})
    assert response.status_code == 202, response.text
    assert wait(client, response.json()["id"])["state"] == "done"
    reading = [(report["page"], report["pages"]) for report in reports if report.get("pages")]
    assert reading == [(1, 3), (2, 3), (3, 3)]
    assert all(report["phase"] == "reading" for report in reports if report.get("pages"))


@pytest.mark.every_pdf_read
def test_cancelling_an_audio_job_while_its_pdf_is_read_ends_it_as_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = isolate.Readers(pdf.MAX_PDF_READERS)
    monkeypatch.setattr(pdf, "_READERS", readers)
    config = make_config(tmp_path)
    client = program(create_app(config, voice=lambda models: FakeVoice().source()), config)
    doc = upload(client, three_pages(), "three.pdf")
    monkeypatch.setattr(pdf, "_read_file", reader_targets.hanging_read)
    job = client.post("/api/v1/jobs", json={"kind": "audio", "document": doc["id"]}).json()
    deadline = time.monotonic() + 60
    while not list(tmp_path.rglob("started")):
        assert time.monotonic() < deadline, "the read did not start"
        time.sleep(0.02)
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["cancellable"] is True
    cancelled = time.monotonic()
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 202
    done = wait(client, job["id"], timeout=10)
    assert time.monotonic() - cancelled < 2.0
    assert done["state"] == "cancelled"
    assert done["error"] == {"error": "cancelled", "message": "the job was cancelled"}
    assert "damaged" not in json.dumps(done)
    assert readers.alive == 0
