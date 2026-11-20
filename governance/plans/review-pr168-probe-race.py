"""Throwaway probe: a job start that passed the document check before a removal began."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from test_web_remove import note, server, start
from web_helpers import offline, upload, wait  # noqa: F401

from sci2audio.web import api, documents

pytestmark = pytest.mark.usefixtures("offline")


def test_probe_start_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _app, client, config = server(tmp_path)
    doc = upload(client, note(), "note.pdf")
    assert wait(client, start(client, doc["id"], "script")["id"])["state"] == "done"
    folder = config.work_root / doc["id"]

    in_start = threading.Event()
    go_start = threading.Event()
    real_load = api.load_settings
    armed = [True]

    def load(*a: Any, **k: Any) -> Any:
        if armed and armed.pop():
            in_start.set()
            assert go_start.wait(10)
        return real_load(*a, **k)

    monkeypatch.setattr(api, "load_settings", load)
    reached = threading.Event()
    go_remove = threading.Event()
    real = documents._remove_entry

    def held(path: Path) -> None:
        if path.name == "source":
            reached.set()
            assert go_remove.wait(20)
        real(path)

    monkeypatch.setattr(documents, "_remove_entry", held)
    answers: dict[str, Any] = {}
    starting = threading.Thread(
        target=lambda: answers.update(
            job=client.post("/api/v1/jobs", json={"kind": "script", "document": doc["id"]})
        )
    )
    starting.start()
    assert in_start.wait(10)
    removing = threading.Thread(
        target=lambda: answers.update(removed=client.delete(f"/api/v1/documents/{doc['id']}"))
    )
    removing.start()
    assert reached.wait(10)
    go_start.set()
    starting.join(10)
    print("job start:", answers["job"].status_code)
    if answers["job"].status_code == 202:
        print("job end:", wait(client, answers["job"].json()["id"])["state"])
    go_remove.set()
    removing.join(10)
    print("removal:", answers["removed"].status_code)
    left = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")) if folder.exists() else []
    print("left:", left)
    print("listed:", client.get("/api/v1/documents").json())
    assert not left
