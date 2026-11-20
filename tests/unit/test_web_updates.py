"""The update check in the server (#217, D-837): off by default, so a server makes no
request; turned on in Settings through `PUT /api/v1/updates`; the result on the Settings
page and, when a newer version is out, one line in the rail. The request is always a fake
here, and every test runs with the network blocked (`offline`)."""

from __future__ import annotations

import errno
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_helpers import (
    ORIGIN,
    browser,
    make_config,
    offline,  # noqa: F401 - fixture
    pdf_bytes,
    upload,
    wait,
)

from sci2audio.app import updates
from sci2audio.app.updates import STATE_NAME, Outcome, UpdateCheck, load_update_state
from sci2audio.web import create_app
from sci2audio.web.config import OutsideJob

pytestmark = pytest.mark.usefixtures("offline")

START = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
PAGES = ("/", "/settings", "/privacy", "/voice")
NOTICE = 'id="update-notice"'


class Release:
    def __init__(self, tag: str = "v1.5.0") -> None:
        self.tag = tag
        self.calls = 0
        self.gate: threading.Event | None = None
        self.entered = threading.Event()
        self.fail = False

    def __call__(self) -> bytes:
        self.calls += 1
        self.entered.set()
        if self.gate is not None:
            assert self.gate.wait(10)
        if self.fail:
            raise updates.UpdateCheckFailed("ConnectionError")
        return json.dumps({"tag_name": self.tag}).encode()


class Server:
    def __init__(self, tmp_path: Path, release: Release, now: datetime = START) -> None:
        self.config = make_config(tmp_path)
        self.file = self.config.config_file.parent / STATE_NAME
        self.release = release
        self.now = now
        self.check = UpdateCheck(self.file, fetch=release, now=lambda: self.now, current="1.4.0")
        self.app: FastAPI = create_app(self.config, updates=self.check)

    def client(self) -> TestClient:
        client = browser(self.app, self.config)
        client.headers["Origin"] = ORIGIN  # as the page's own script sends
        return client


@pytest.fixture
def release() -> Release:
    return Release()


@pytest.fixture
def server(tmp_path: Path, release: Release) -> Server:
    return Server(tmp_path, release)


def turn(client: TestClient, enabled: bool, server: Server) -> dict[str, Any]:
    response = client.put("/api/v1/updates", json={"enabled": enabled})
    assert response.status_code == 200, response.text
    server.check.join(10)
    return response.json()


# --- off by default ----------------------------------------------------------------------


def test_a_server_as_shipped_makes_no_request(tmp_path: Path, offline: list[str]) -> None:  # noqa: F811
    """No injected fetch: the real one would be used, and `offline` fails on any attempt."""
    config = make_config(tmp_path)
    app = create_app(config)
    state = app.state.sci2audio
    assert state.updates.file == config.config_file.parent / "update-check.json"
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN
    for path in PAGES:
        assert client.get(path).status_code == 200, path
        assert NOTICE not in client.get(path).text
    got = client.get("/api/v1/updates").json()
    assert got == {
        "enabled": False,
        "checked_at": None,
        "outcome": None,
        "latest": None,
        "release_url": None,
    }
    doc = upload(client, pdf_bytes())
    job = client.post(
        "/api/v1/jobs",
        json={"kind": "script", "document": doc["id"], "settings": {}},
    ).json()
    assert wait(client, job["id"])["state"] == "done"
    state.updates.join(10)
    assert offline == []
    assert not state.updates.file.exists()


def test_sci2audio_listen_never_runs_the_check(tmp_path: Path, offline: list[str]) -> None:  # noqa: F811
    """`sci2audio listen` starts the server for its outside job: no check there (D-837)."""
    job = OutsideJob("0123456789abcdef", "paper.pdf", tmp_path / "w", tmp_path / "o")
    config = make_config(tmp_path, outside=(job,))
    file = config.config_file.parent / STATE_NAME
    file.parent.mkdir(parents=True)
    file.write_text('{"version": 1, "enabled": true}', encoding="utf-8")  # on, never checked
    app = create_app(config)  # the real fetch: `offline` fails on any attempt
    client = browser(app, config)
    client.headers["Origin"] = ORIGIN
    for path in ("/", "/settings", "/privacy"):
        page = client.get(path).text
        assert NOTICE not in page
    assert 'id="settings-updates"' not in client.get("/settings").text
    assert client.put("/api/v1/updates", json={"enabled": True}).status_code == 200
    app.state.sci2audio.updates.join(10)
    assert offline == []
    assert load_update_state(file).checked_at is None


def test_turning_it_off_on_a_full_disk_answers_507_and_is_off_for_the_run(
    server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = server.client()
    turn(client, True, server)

    def full(target: Path, text: str, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(updates, "write_text_atomically", full)
    response = client.put("/api/v1/updates", json={"enabled": False})
    assert response.status_code == 507
    assert "could not save" in response.json()["message"]
    assert client.get("/api/v1/updates").json()["enabled"] is False
    server.now = START + timedelta(days=3)
    assert NOTICE not in client.get("/").text
    server.check.join(10)
    assert server.release.calls == 1


def test_a_save_error_without_a_reason_still_says_something(
    server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(target: Path, text: str, *, overwrite: bool) -> None:
        raise OSError("the folder went away")

    monkeypatch.setattr(updates, "write_text_atomically", broken)
    message = server.client().put("/api/v1/updates", json={"enabled": True}).json()["message"]
    assert "None" not in message
    assert "the folder went away" in message


def test_off_by_default_the_fake_is_never_asked(server: Server) -> None:
    client = server.client()
    for path in PAGES:
        client.get(path)
    server.check.join(10)
    assert server.release.calls == 0


# --- turning it on and off ---------------------------------------------------------------


def test_turning_it_on_checks_once_and_shows_the_result(server: Server) -> None:
    client = server.client()
    answer = turn(client, True, server)
    assert answer["enabled"] is True
    assert server.release.calls == 1
    got = client.get("/api/v1/updates").json()
    assert got == {
        "enabled": True,
        "checked_at": "2026-11-20T09:00:00Z",
        "outcome": "newer",
        "latest": "1.5.0",
        "release_url": "https://github.com/dubidu22/sci2audio/releases/tag/v1.5.0",
    }
    for path in PAGES:
        page = client.get(path).text
        assert NOTICE in page, path
        assert 'href="https://github.com/dubidu22/sci2audio/releases/tag/v1.5.0"' in page
    server.check.join(10)
    assert server.release.calls == 1  # the pages asked nothing more within the day


def test_turning_it_off_removes_the_notice_and_the_requests(server: Server) -> None:
    client = server.client()
    turn(client, True, server)
    answer = turn(client, False, server)
    assert answer["enabled"] is False
    assert answer["release_url"] is None
    server.now = START + timedelta(days=5)
    for path in PAGES:
        assert NOTICE not in client.get(path).text
    server.check.join(10)
    assert server.release.calls == 1


def test_the_choice_holds_across_a_restart(tmp_path: Path, release: Release) -> None:
    first = Server(tmp_path, release)
    turn(first.client(), True, first)
    second = Server(tmp_path, release, now=START + timedelta(hours=1))
    assert second.client().get("/api/v1/updates").json()["enabled"] is True
    second.check.join(10)
    assert release.calls == 1


def test_a_server_started_a_day_later_checks_at_start(tmp_path: Path, release: Release) -> None:
    first = Server(tmp_path, release)
    turn(first.client(), True, first)
    later = Server(tmp_path, release, now=START + timedelta(days=1, minutes=1))
    later.check.join(10)  # no page asked yet
    assert release.calls == 2


def test_a_long_running_server_checks_again_on_a_page_the_next_day(server: Server) -> None:
    client = server.client()
    turn(client, True, server)
    server.now = START + timedelta(days=1)
    client.get("/settings")
    server.check.join(10)
    assert server.release.calls == 2


@pytest.mark.parametrize(
    "body",
    [{}, {"enabled": "yes"}, {"enabled": 1}, {"enabled": None}, {"enabled": True, "x": 1}, []],
)
def test_the_switch_takes_only_true_or_false(server: Server, body: Any) -> None:
    response = server.client().put("/api/v1/updates", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid"
    assert server.release.calls == 0


def test_the_switch_needs_the_token_and_the_origin(server: Server) -> None:
    anonymous = TestClient(server.app, base_url=ORIGIN)
    assert anonymous.put("/api/v1/updates", json={"enabled": True}).status_code == 401
    client = browser(server.app, server.config)  # the cookie, but no Origin
    assert client.put("/api/v1/updates", json={"enabled": True}).status_code == 403
    assert server.release.calls == 0
    assert not server.file.exists()


def test_a_full_disk_says_so(server: Server, monkeypatch: pytest.MonkeyPatch) -> None:
    def full(target: Path, text: str, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(updates, "write_text_atomically", full)
    response = server.client().put("/api/v1/updates", json={"enabled": True})
    assert response.status_code == 507
    assert response.json()["error"] == "disk-full"
    assert server.release.calls == 0


# --- never in the way --------------------------------------------------------------------


def test_a_slow_release_source_blocks_nothing(server: Server) -> None:
    server.release.gate = threading.Event()
    client = server.client()
    try:
        assert client.put("/api/v1/updates", json={"enabled": True}).status_code == 200
        assert server.release.entered.wait(10)
        for path in PAGES:
            assert client.get(path).status_code == 200
        assert client.get("/api/v1/updates").json()["checked_at"] is None
        doc = upload(client, pdf_bytes())
        job = client.post(
            "/api/v1/jobs", json={"kind": "script", "document": doc["id"], "settings": {}}
        ).json()
        assert wait(client, job["id"])["state"] == "done"
    finally:
        server.release.gate.set()
    server.check.join(10)
    assert server.release.calls == 1


# --- what Settings shows -----------------------------------------------------------------


def status_of(page: str) -> str:
    start = page.index('id="updates-status"')
    return page[start : page.index("</p>", start)]


def test_settings_shows_the_switch_off_by_default(server: Server) -> None:
    page = server.client().get("/settings").text
    assert 'id="settings-updates"' in page
    switch = page[page.index('id="settings-updates"') :].split(">", 1)[0]
    assert "checked" not in switch
    assert 'href="/privacy#update-check"' in page
    assert "updates-status" not in page


@pytest.mark.parametrize(
    ("tag", "fail", "says"),
    [
        ("v1.5.0", False, "is out: sci2audio 1.5.0"),
        ("v1.4.0", False, "You have the newest version"),
        ("v1.4.0", True, "did not work"),
    ],
)
def test_settings_shows_the_last_result(server: Server, tag: str, fail: bool, says: str) -> None:
    server.release.tag = tag
    server.release.fail = fail
    client = server.client()
    turn(client, True, server)
    page = client.get("/settings").text
    switch = page[page.index('id="settings-updates"') :].split(">", 1)[0]
    assert "checked" in switch
    assert says in status_of(page)
    assert "2026-11-20" in status_of(page)
    assert (NOTICE in page) == (tag == "v1.5.0" and not fail)


def test_settings_before_the_first_answer(server: Server) -> None:
    server.release.gate = threading.Event()
    client = server.client()
    try:
        client.put("/api/v1/updates", json={"enabled": True})
        assert server.release.entered.wait(10)
        assert "Not checked yet" in status_of(client.get("/settings").text)
    finally:
        server.release.gate.set()
    server.check.join(10)


def test_settings_in_german(server: Server) -> None:
    client = server.client()
    turn(client, True, server)
    client.cookies.set("sci2audio-language", "de")
    page = client.get("/settings").text
    assert "ist erschienen: sci2audio 1.5.0" in status_of(page)


def test_the_result_kept_in_memory_when_the_disk_is_full(
    server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = server.client()
    real = updates.write_text_atomically
    writes = 0

    def full_after_one(target: Path, text: str, *, overwrite: bool) -> None:
        nonlocal writes
        writes += 1
        if writes > 1:
            raise OSError(errno.ENOSPC, "No space left on device")
        real(target, text, overwrite=overwrite)

    monkeypatch.setattr(updates, "write_text_atomically", full_after_one)
    turn(client, True, server)
    assert client.get("/api/v1/updates").json()["outcome"] == Outcome.NEWER.value
    assert NOTICE in client.get("/").text
