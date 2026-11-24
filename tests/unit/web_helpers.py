"""Shared helpers for the web tests: a server app with its folders in a temporary
directory, clients that authenticate like the browser or a program, a small PDF, and the
v1.3 markers file as v1.3 wrote and read it."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pdf_maker import Text, make_pdf

from sci2audio.app.captures import MARKERS
from sci2audio.testing import no_network
from sci2audio.web import ServerConfig, create_app, new_token
from sci2audio.web.markers import Anchor
from sci2audio.web.project import folder_name

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


class FakeClock:
    """A clock for the markers' undo store (#474): seconds that move only when told."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


def markers_of(work: Path) -> dict[str, Any]:
    """A document's v1.3 markers file as written (#474), for field and byte checks."""
    data: dict[str, Any] = json.loads((work / MARKERS).read_text(encoding="utf-8"))
    return data


# ---- the v1.3 markers file (#474), as v1.3 wrote and read it --------------------------------
# Nothing in the server writes it since the captures (#397), and only the carry-over in
# `app.captures` reads it (#887). The tests keep v1.3's writer to make the files a person
# brings from v1.3, and its reader to hold the carry-over to v1.3's verdict on each file.

MARKERS_FORMAT = "sci2audio-web-markers"
MARKERS_VERSION = 1
MAX_MARKERS = 2000
FILE_LIMIT = 2_000_000  # bytes
NOTE_LIMIT = 4000  # characters
_ID_DIGITS = frozenset("0123456789abcdef")
_ANCHOR_KEYS = frozenset({"block", "start", "end", "text"})
_MARKER_KEYS = frozenset({"id", "created", "changed", "anchor", "note"})
_FILE_KEYS = frozenset({"format", "version", "document", "markers"})


class MarkerError(Exception):
    """A markers file v1.3 would not write: it could not read it back."""


class MarkersBroken(MarkerError):
    """The file is there but v1.3 can't read it."""


class MarkerLimit(MarkerError):
    """Too many markers, or the file would grow past its limit."""


class MarkersTooLarge(MarkerLimit):
    """The file would grow past its limit."""


@dataclass(frozen=True)
class Marker:
    id: str
    created: str
    changed: str
    anchor: Anchor
    note: str = ""


def note_problem(note: str) -> str | None:
    """Why v1.3 can't keep a note, or None."""
    if len(note) > NOTE_LIMIT:
        return f"a note holds at most {NOTE_LIMIT} characters"
    if "\x00" in note:
        return "a note can't hold a NUL character"
    return None


def _no_constant(name: str) -> None:
    raise ValueError(f"{name} is not a number")


def _is_int(value: object) -> bool:
    return type(value) is int


def _anchor(data: object) -> Anchor:
    if not isinstance(data, dict) or set(data) != _ANCHOR_KEYS:
        raise ValueError("an anchor has block, start, end and text")
    block, start, end, text = data["block"], data["start"], data["end"], data["text"]
    if not (_is_int(block) and _is_int(start) and _is_int(end) and isinstance(text, str)):
        raise ValueError("an anchor's block and offsets are whole numbers, its text a text")
    if block < 0 or start < 0 or end < start or not text:
        raise ValueError("an anchor's offsets don't fit")
    return Anchor(block, start, end, text)


def _marker(data: object) -> Marker:
    if not isinstance(data, dict) or set(data) != _MARKER_KEYS:
        raise ValueError("a marker has id, created, changed, anchor and note")
    marker_id, created, changed, note = data["id"], data["created"], data["changed"], data["note"]
    if not (isinstance(marker_id, str) and len(marker_id) == 16 and set(marker_id) <= _ID_DIGITS):
        raise ValueError("a marker's id is 16 hex digits")
    if not (isinstance(created, str) and isinstance(changed, str) and isinstance(note, str)):
        raise ValueError("a marker's times and note are texts")
    if len(created) > 40 or len(changed) > 40 or note_problem(note):
        raise ValueError("a marker's times or note are too long")
    return Marker(marker_id, created, changed, _anchor(data["anchor"]), note)


def read_markers(work: Path, document_id: str) -> list[Marker]:
    """The document's markers as v1.3 read them, in the file's order; [] if there is no
    file. Raises MarkersBroken if v1.3 can't read the file, OSError if it can't be read at
    all."""
    path = work / MARKERS
    if not path.exists() and not path.is_symlink():
        return []
    if path.is_symlink() or not path.is_file():
        raise MarkersBroken(f"{path} is not a plain file")
    if path.stat().st_size > FILE_LIMIT:
        raise MarkersBroken(f"{path} is larger than {FILE_LIMIT} bytes")
    try:
        return _parse_markers(path.read_bytes().decode("utf-8"), document_id)
    except ValueError as error:  # UnicodeDecodeError is a ValueError
        raise MarkersBroken(f"{path} can't be read: {error}") from None


def _parse_markers(text: str, document_id: str) -> list[Marker]:
    """The markers of a file's text. Raises ValueError if v1.3 can't read it."""
    try:
        data = json.loads(text, parse_constant=_no_constant)
        if not isinstance(data, dict) or set(data) != _FILE_KEYS:
            raise ValueError("not a markers file")
        if data["format"] != MARKERS_FORMAT or data["version"] != MARKERS_VERSION:
            raise ValueError("another format or version")
        if data["document"] != document_id:
            raise ValueError("the markers of another document")
        entries = data["markers"]
        if not isinstance(entries, list) or len(entries) > MAX_MARKERS:
            raise ValueError(f"the markers are not a list of at most {MAX_MARKERS}")
        markers = [_marker(entry) for entry in entries]
    except RecursionError:
        raise ValueError("nested too deeply") from None
    if len({marker.id for marker in markers}) != len(markers):
        raise ValueError("one marker is named twice")
    return markers


def _marker_data(marker: Marker) -> dict[str, Any]:
    a = marker.anchor
    return {
        "id": marker.id,
        "created": marker.created,
        "changed": marker.changed,
        "anchor": {"block": a.block, "start": a.start, "end": a.end, "text": a.text},
        "note": marker.note,
    }


def markers_text(document_id: str, markers: Sequence[Marker]) -> str:
    """The file's text for these markers, as v1.3 wrote it. Raises MarkerLimit past the
    limits."""
    if len(markers) > MAX_MARKERS:
        raise MarkerLimit(f"a document holds at most {MAX_MARKERS} markers")
    data = {
        "format": MARKERS_FORMAT,
        "version": MARKERS_VERSION,
        "document": document_id,
        "markers": [_marker_data(marker) for marker in markers],
    }
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if len(text.encode("utf-8")) > FILE_LIMIT:
        raise MarkersTooLarge(f"the markers file would be larger than {FILE_LIMIT} bytes")
    try:  # v1.3 never wrote a file it could not read back
        _parse_markers(text, document_id)
    except ValueError as error:
        raise MarkerError(f"the markers would not be readable: {error}") from None
    return text


def set_capture(
    client: TestClient, doc: str, kind: str, chunk: int, stamp: str, status: int = 201
) -> Any:
    """Capture a mark or a quote at chunk `chunk` of the page drawn for audiobook `stamp`
    (#397)."""
    body = {"type": kind, "chunk": chunk, "audiobook": stamp}
    response = client.post(f"/api/v1/documents/{doc}/captures", json=body)
    assert response.status_code == status, response.text
    return response.json()


def book_folder(output: Path, name: str = "paper.pdf") -> Path:
    """Where the audiobook of a document opened as `name` goes in `output`: its project's
    own folder (D-749)."""
    return output / folder_name(name)


def plugin_steps(distribution: str = "sci2audio-example", version: str = "0.1") -> Any:
    """The built-in steps with `example_text_plugin.AmpersandStep` loaded as an installed
    plugin of `distribution` (#216): what a server's runner holds with that plugin."""
    from importlib.metadata import EntryPoint

    from sci2audio.textprep import Category, InstalledSteps, installed_steps
    from sci2audio.textprep.plugins import PLUGIN_GROUP, PluginInfo

    point = EntryPoint("ampersand-and", "example_text_plugin:AmpersandStep", PLUGIN_GROUP)
    loaded = installed_steps(entry_points=[point])
    info = PluginInfo(
        "ampersand-and",
        Category.CHARACTERS,
        distribution,
        version,
        "example_text_plugin:AmpersandStep",
    )
    return InstalledSteps(loaded, (info,), ())


AMPERSAND_TEXT = "Salt & pepper are on the table."
