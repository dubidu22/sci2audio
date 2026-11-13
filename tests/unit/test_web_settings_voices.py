"""Settings (D-139 through the API) and the voice list and download with consent (D-203)."""

from __future__ import annotations

import errno
import hashlib
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

import pytest
from fastapi import FastAPI
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from web_helpers import (
    app_and_config,
    make_config,
    offline,  # noqa: F401 - fixture
    program,
    wait,
)

from sci2audio.textprep import Category
from sci2audio.voices import ENGLISH_VOICES, DownloadPlan, NetworkError, RemoteFile, download_plan
from sci2audio.voices import download as download_module
from sci2audio.web import api, create_app
from sci2audio.web.tasks import plan_digest

pytestmark = pytest.mark.usefixtures("offline")


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


# --- settings ---------------------------------------------------------------------------


def test_settings_start_from_the_defaults_with_every_choice(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    data = program(app, config).get("/api/v1/settings").json()
    assert data["settings"] == {
        "language": "",
        "switched_off": ["footnote-texts"],
        "voice": "",
        "speed": 1.0,
        "output_folder": None,
    }
    assert data["warnings"] == []
    assert [c["id"] for c in data["categories"]] == [str(c) for c in Category]
    assert {c["id"]: c["label"] for c in data["categories"]}["links"] == (
        "URLs, DOIs and e-mail addresses"
    )
    assert [c["id"] for c in data["categories"] if not c["on_by_default"]] == ["footnote-texts"]
    assert data["speed"] == {"min": 0.5, "max": 2.0}
    assert len(data["voices"]) == len(ENGLISH_VOICES) == 28
    assert data["default_voice"] == "af_heart"
    assert data["default_output_folder"] == str(config.output_folder)


def test_settings_are_saved_to_the_settings_file(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    folder = str(config.output_folder.parent / "books")
    chosen = {
        "language": "en-GB",
        "switched_off": ["links", "citations"],
        "voice": "bm_george",
        "speed": 1.25,
        "output_folder": folder,
    }
    response = client.put("/api/v1/settings", json=chosen)
    assert response.status_code == 200
    assert response.json() == {**chosen, "switched_off": ["citations", "links"]}
    saved = json.loads(config.config_file.read_text(encoding="utf-8"))
    assert saved["voice"] == "bm_george"
    assert saved["output_folder"] == folder
    assert client.get("/api/v1/settings").json()["settings"] == response.json()


def test_a_broken_settings_file_is_reported_not_fatal(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    config.config_file.parent.mkdir(parents=True)
    config.config_file.write_text("[" * 100_000, encoding="utf-8")
    data = program(app, config).get("/api/v1/settings").json()
    assert data["settings"]["speed"] == 1.0
    assert data["warnings"]
    assert "damaged" in data["warnings"][0]


@pytest.mark.parametrize(
    "body",
    [
        {"speed": 3},
        {"speed": "fast"},
        {"switched_off": ["nothing"]},
        {"voice": "xx_nobody"},
        {"language": "English!"},
        {"output_folder": "relative"},
        {"chapters": [1]},  # not a kept setting
        {"unknown": True},
    ],
)
def test_wrong_settings_are_refused_and_not_saved(
    server: tuple[FastAPI, Any], body: dict[str, Any]
) -> None:
    app, config = server
    response = program(app, config).put("/api/v1/settings", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid"
    assert response.json()["message"]
    assert not config.config_file.exists()


def test_a_settings_file_that_cant_be_written(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, config = server

    def full(settings: Any, file: Path) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(api, "save_settings", full)
    response = program(app, config).put("/api/v1/settings", json={})
    assert response.status_code == 507
    assert "No space left" in response.json()["message"]


JSON = st.recursive(
    st.none()
    | st.booleans()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.integers()
    | st.text(max_size=8),
    lambda inner: (
        st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=8), inner, max_size=4)
    ),
    max_leaves=12,
)
SETTINGS = st.fixed_dictionaries(
    {},
    optional={
        "language": st.sampled_from(["", "en", "en-GB", "de", "x"]) | st.text(max_size=6),
        "switched_off": st.lists(st.sampled_from([*map(str, Category), "nothing"]), max_size=4),
        "voice": st.sampled_from(["", "af_heart", "bm_lewis", "nobody"]),
        "speed": st.floats(0.0, 3.0) | st.integers(-1, 3),
        "output_folder": st.none() | st.sampled_from(["/books", "books", ""]),
        "other": JSON,
    },
)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(body=SETTINGS | JSON)
def test_any_settings_body_is_saved_and_read_back_or_refused(tmp_path: Path, body: Any) -> None:
    config = make_config(tmp_path / hashlib.sha256(repr(body).encode()).hexdigest()[:12])
    client = program(create_app(config), config)
    response = client.put("/api/v1/settings", json=body)
    assert response.status_code in (200, 422), response.text
    if response.status_code == 200:
        assert client.get("/api/v1/settings").json()["settings"] == response.json()
    else:
        assert not config.config_file.exists()


# --- voices -----------------------------------------------------------------------------


def test_the_voice_list_shows_the_whole_download_before_anything_happens(
    server: tuple[FastAPI, Any],
) -> None:
    app, config = server
    data = program(app, config).get("/api/v1/voices").json()
    plan = download_plan()
    assert [v["id"] for v in data["voices"]] == [v.id for v in ENGLISH_VOICES]
    assert data["installed"] is False
    assert data["plan"]["digest"] == plan_digest(plan)
    assert data["plan"]["total_bytes"] == data["plan"]["missing_bytes"] == plan.total_bytes
    assert len(data["plan"]["files"]) == len(plan.files)
    assert all(f["licence"] and f["sha256"] and f["size"] > 0 for f in data["plan"]["files"])
    assert data["plan"]["licences"] == list(plan.licences)
    hosts = data["plan"]["hosts"]
    assert hosts == [
        "github.com",
        "huggingface.co",
        "objects.githubusercontent.com (GitHub's download server)",
        "Hugging Face's download servers (its CDN and LFS/Xet storage)",
    ]
    assert not config.models_dir.exists()


def test_the_digest_changes_with_any_file_of_the_plan() -> None:
    plan = download_plan()
    first = plan.files[0]
    changed = RemoteFile(first.url, first.target, first.size + 1, first.sha256, first.licence)
    other = DownloadPlan((changed, *plan.files[1:]), plan.total_bytes + 1, plan.licences)
    assert plan_digest(plan) != plan_digest(other)
    assert plan_digest(plan) == plan_digest(download_plan())


class FakeServer:
    """Serves bytes from memory in blocks of 100; `on_block` can stop or break it."""

    def __init__(self, served: dict[str, bytes]) -> None:
        self.served = served
        self.fetched: list[str] = []
        self.on_block: Callable[[str, int], None] | None = None

    def __call__(self, url: str, out: BinaryIO, on_bytes: Callable[[int], None]) -> None:
        self.fetched.append(url)
        data = self.served[url]
        for start in range(0, len(data), 100):
            if self.on_block:
                self.on_block(url, start)
            out.write(data[start : start + 100])
            on_bytes(len(data[start : start + 100]))


SERVED = {"https://example.test/a.bin": b"a" * 1000, "https://example.test/b.bin": b"b" * 500}


@pytest.fixture
def small_plan(monkeypatch: pytest.MonkeyPatch) -> DownloadPlan:
    files = tuple(
        RemoteFile(
            url,
            f"voice/{url.rsplit('/', 1)[1]}",
            len(data),
            hashlib.sha256(data).hexdigest(),
            "MIT",
        )
        for url, data in SERVED.items()
    )
    plan = DownloadPlan(files, sum(f.size for f in files), ("MIT",))
    monkeypatch.setattr(download_module, "download_plan", lambda: plan)
    monkeypatch.setattr(api, "download_plan", lambda: plan)
    return plan


def voices_app(tmp_path: Path, fake: FakeServer) -> tuple[Any, Any]:
    config = make_config(tmp_path)
    app = create_app(config, fetch=fake)
    return program(app, config), config


def test_no_download_without_consent(tmp_path: Path, small_plan: DownloadPlan) -> None:
    fake = FakeServer(SERVED)
    client, config = voices_app(tmp_path, fake)
    digest = plan_digest(small_plan)
    for body, status, kind in (
        ({"consent": False, "plan": digest}, 422, "no-consent"),
        ({"plan": digest}, 422, "invalid"),
        ({"consent": True}, 422, "invalid"),
        ({"consent": True, "plan": "0" * 64}, 409, "stale-plan"),
        # the real plan, not the one the server shows here: agreed to something else
        ({"consent": True, "plan": plan_digest(download_plan())}, 409, "stale-plan"),
    ):
        response = client.post("/api/v1/voices/download", json=body)
        assert (response.status_code, response.json()["error"]) == (status, kind), body
    assert fake.fetched == []
    assert client.get("/api/v1/jobs").json() == []
    assert not config.models_dir.exists()


def test_the_download_with_consent_puts_the_files_in_place(
    tmp_path: Path, small_plan: DownloadPlan
) -> None:
    fake = FakeServer(SERVED)
    client, config = voices_app(tmp_path, fake)
    response = client.post(
        "/api/v1/voices/download", json={"consent": True, "plan": plan_digest(small_plan)}
    )
    assert response.status_code == 202
    job = response.json()
    assert job["id"] == "voices-1"
    assert job["kind"] == "voices"
    assert job["document"] is None
    assert job["cancellable"] is True
    done = wait(client, job["id"])
    assert done["state"] == "done", done
    assert done["progress"] == {"phase": "done"}
    assert (config.models_dir / "voice" / "a.bin").read_bytes() == SERVED[
        "https://example.test/a.bin"
    ]
    assert fake.fetched == list(SERVED)
    assert client.get("/api/v1/voices").json()["installed"] is True
    again = client.post(
        "/api/v1/voices/download", json={"consent": True, "plan": plan_digest(small_plan)}
    )
    assert wait(client, again.json()["id"])["state"] == "done"
    assert fake.fetched == list(SERVED)  # nothing fetched twice


def test_download_progress_counts_bytes(tmp_path: Path, small_plan: DownloadPlan) -> None:
    fake = FakeServer(SERVED)
    gate = threading.Event()
    reached = threading.Event()

    def pause(url: str, start: int) -> None:
        if url.endswith("b.bin") and start == 0:
            reached.set()
            assert gate.wait(10)

    fake.on_block = pause
    client, _ = voices_app(tmp_path, fake)
    job = client.post(
        "/api/v1/voices/download", json={"consent": True, "plan": plan_digest(small_plan)}
    ).json()
    assert reached.wait(10)
    progress = client.get(f"/api/v1/jobs/{job['id']}").json()["progress"]
    assert progress == {
        "phase": "downloading",
        "bytes_done": 1000,
        "bytes_total": 1500,
        "file": "voice/a.bin",
    }
    gate.set()
    assert wait(client, job["id"])["state"] == "done"


def test_cancelling_the_download_keeps_no_part_file(
    tmp_path: Path, small_plan: DownloadPlan
) -> None:
    fake = FakeServer(SERVED)
    gate = threading.Event()
    reached = threading.Event()

    def pause(url: str, start: int) -> None:
        if start == 300:
            reached.set()
            assert gate.wait(10)

    fake.on_block = pause
    client, config = voices_app(tmp_path, fake)
    job = client.post(
        "/api/v1/voices/download", json={"consent": True, "plan": plan_digest(small_plan)}
    ).json()
    assert reached.wait(10)
    response = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert response.status_code == 202
    gate.set()
    done = wait(client, job["id"])
    assert done["state"] == "cancelled"
    assert done["error"]["error"] == "cancelled"
    assert list(config.models_dir.rglob("*.part")) == []
    assert not (config.models_dir / "voice" / "a.bin").exists()
    assert fake.fetched == ["https://example.test/a.bin"]


@pytest.mark.parametrize(
    ("error", "kind"),
    [(NetworkError("could not download: no route to host"), "network")],
)
def test_a_failed_download_is_reported(
    tmp_path: Path, small_plan: DownloadPlan, error: Exception, kind: str
) -> None:
    fake = FakeServer(SERVED)

    def broken(url: str, start: int) -> None:
        raise error

    fake.on_block = broken
    client, config = voices_app(tmp_path, fake)
    job = client.post(
        "/api/v1/voices/download", json={"consent": True, "plan": plan_digest(small_plan)}
    ).json()
    done = wait(client, job["id"])
    assert done["state"] == "failed"
    assert done["error"] == {"error": kind, "message": str(error)}
    assert list(config.models_dir.rglob("*.part")) == []


def test_a_full_disk_during_the_download_is_reported(
    tmp_path: Path, small_plan: DownloadPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeServer(SERVED)

    def full(url: str, start: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    fake.on_block = full
    client, _ = voices_app(tmp_path, fake)
    job = client.post(
        "/api/v1/voices/download", json={"consent": True, "plan": plan_digest(small_plan)}
    ).json()
    done = wait(client, job["id"])
    assert done["state"] == "failed"
    assert done["error"]["error"] == "download-failed"
    assert "disk space" in done["error"]["message"]
