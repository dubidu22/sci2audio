"""Shared helpers for the web tests: a server app with its folders in a temporary
directory, clients that authenticate like the browser or a program, a small PDF."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pdf_maker import Text, make_pdf

from sci2audio.testing import no_network
from sci2audio.web import ServerConfig, create_app, new_token

PORT = 8123
ORIGIN = f"http://127.0.0.1:{PORT}"


_CONNECT = socket.socket.connect  # the real one, taken before any test blocks it


@contextmanager
def _socketpair_allowed() -> Iterator[None]:
    """Let `socket.socketpair` work under `no_network`.

    Windows has no native socketpair: Python emulates it by connecting a socket to a
    listener it just bound on 127.0.0.1, and every asyncio event loop (TestClient's
    included) makes one for its self-pipe. Only that connect, to a loopback address, in
    the thread that is making the pair, goes through; every other connect is still
    refused and recorded. Elsewhere the native socketpair makes no connect at all.
    """
    pairing = threading.local()
    refused = socket.socket.connect
    original = socket.socketpair

    def connect(self: socket.socket, address: Any) -> None:
        if getattr(pairing, "active", False) and address[0] in ("127.0.0.1", "::1"):
            return _CONNECT(self, address)
        return refused(self, address)

    def socketpair(*args: Any, **kwargs: Any) -> tuple[socket.socket, socket.socket]:
        pairing.active = True
        try:
            return original(*args, **kwargs)
        finally:
            pairing.active = False

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socketpair = socketpair  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = refused  # type: ignore[method-assign]
        socket.socketpair = original


@pytest.fixture
def offline() -> Iterator[list[str]]:
    """Every web test runs with the network blocked (only the launcher tests connect, and
    only to 127.0.0.1)."""
    with no_network() as attempts, _socketpair_allowed():
        yield attempts
    assert attempts == []


def make_config(tmp_path: Path, **changes: Any) -> ServerConfig:
    values: dict[str, Any] = {
        "token": new_token(),
        "port": PORT,
        "work_root": tmp_path / "work",
        "models_dir": tmp_path / "models",
        "config_file": tmp_path / "config" / "settings.json",
        "output_folder": tmp_path / "out",
    }
    values.update(changes)
    return ServerConfig(**values)


def program(app: FastAPI, config: ServerConfig) -> TestClient:
    """A client that sends the token as a bearer header, as a program would."""
    return TestClient(app, base_url=ORIGIN, headers={"Authorization": f"Bearer {config.token}"})


def browser(app: FastAPI, config: ServerConfig) -> TestClient:
    """A client that went through /start and holds the cookie, as the browser does."""
    client = TestClient(app, base_url=ORIGIN)
    response = client.get(f"/start?token={config.token}", follow_redirects=False)
    assert response.status_code == 303
    return client


def anonymous(app: FastAPI) -> TestClient:
    return TestClient(app, base_url=ORIGIN)


def pdf_bytes(text: str = "A short note about things.") -> bytes:
    return make_pdf([Text("Introduction", 72, 80, size=14), Text(text, 72, 100, size=11)])


def paper_bytes() -> bytes:
    """Three chapters, one citation and a reference list (deselected by default, Q6)."""
    return make_pdf(
        [
            Text("Introduction", 72, 80, size=14),
            Text("Things happen (Smith, 2020) and more.", 72, 100, size=11),
            Text("Methods", 72, 140, size=14),
            Text("We measured it twice.", 72, 160, size=11),
            Text("References", 72, 200, size=14),
            Text("Smith, J. 2020. A book about things.", 72, 220, size=11),
        ]
    )


def upload(client: TestClient, data: bytes, name: str = "paper.pdf") -> dict[str, Any]:
    response = client.post("/api/v1/documents", files={"file": (name, data, "application/pdf")})
    assert response.status_code == 201, response.text
    return response.json()


def wait(client: TestClient, job_id: str, timeout: float = 60.0) -> dict[str, Any]:
    """The job once it has ended."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] != "running":
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not end within {timeout} s")


def events(client: TestClient, job_id: str) -> list[tuple[str, str]]:
    """The (event, data) pairs of a job's stream, and comment lines as ("", text)."""
    found: list[tuple[str, str]] = []
    name = ""
    with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        for line in stream.iter_lines():
            if line.startswith(":"):
                found.append(("", line))
            elif line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                found.append((name, line.removeprefix("data: ")))
    return found


def app_and_config(tmp_path: Path, **changes: Any) -> tuple[FastAPI, ServerConfig]:
    config = make_config(tmp_path, **changes)
    return create_app(config), config
