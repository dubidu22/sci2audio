"""Starting the server (D-192, D-193, D-207): 127.0.0.1 only, a port the system picks, the
start link, `sci2audio ui`, stopping, and a restart after the server was killed."""

from __future__ import annotations

import http.cookiejar
import json
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from pdf_maker import Text, make_pdf

from sci2audio import cli
from sci2audio.web import bind, launch

SERVER = """
import sys
from pathlib import Path
from sci2audio.web import ServerConfig, bind, serve
root = Path(sys.argv[1])
sock = bind()
config = ServerConfig(
    token=sys.argv[2], port=sock.getsockname()[1], work_root=root / "work",
    models_dir=root / "models", config_file=root / "settings.json", output_folder=root / "out",
)
serve(sock, config, open_browser=False)
"""
TOKEN = "t" * 43


def test_bind_listens_on_127_0_0_1_at_a_port_the_system_picks() -> None:
    first, second = bind(), bind()
    try:
        assert first.getsockname()[0] == "127.0.0.1"
        assert first.family == socket.AF_INET
        assert first.getsockname()[1] > 0
        assert first.getsockname()[1] != second.getsockname()[1]
    finally:
        first.close()
        second.close()


def test_serve_prints_the_link_opens_the_browser_and_cancels_on_the_way_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    said: list[str] = []
    ran: list[Any] = []
    monkeypatch.setattr(launch.webbrowser, "open", opened.append)
    monkeypatch.setattr(launch.uvicorn.Server, "run", lambda self, sockets: ran.append(self))
    sock = bind()
    try:
        from web_helpers import make_config

        config = make_config(tmp_path, port=sock.getsockname()[1], token=TOKEN)
        launch.serve(sock, config, say=said.append)
    finally:
        sock.close()
    assert opened == [config.start_url]
    assert config.start_url == f"http://127.0.0.1:{config.port}/start?token={TOKEN}"
    assert said[0] == f"sci2audio is running at {config.start_url}"
    server_config = ran[0].config
    assert server_config.access_log is False  # it would print the token
    assert server_config.server_header is False
    assert server_config.timeout_graceful_shutdown == launch.SHUTDOWN_WAIT


def test_sci2audio_ui_starts_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("sci2audio.web.run", lambda **kwargs: calls.append(kwargs) or 0)
    assert cli.main(["ui"]) == 0
    assert cli.main(["ui", "--no-browser"]) == 0
    assert calls == [{"open_browser": True}, {"open_browser": False}]


def test_the_command_line_does_not_load_the_web_framework() -> None:
    code = (
        "import sys, sci2audio.cli; "
        "sys.exit(int('fastapi' in sys.modules or 'uvicorn' in sys.modules))"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


# --- a real server in a subprocess --------------------------------------------------------


def no_proxy() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)
    )


class Running:
    def __init__(self, root: Path) -> None:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-c", SERVER, str(root), TOKEN],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=flags,
        )
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        assert line.startswith("sci2audio is running at http://127.0.0.1:"), line
        self.url = line.split(" at ", 1)[1].strip()
        self.port = int(self.url.split(":")[2].split("/")[0])
        self.origin = f"http://127.0.0.1:{self.port}"

    def call(self, path: str, data: bytes | None = None, **headers: str) -> tuple[int, bytes]:
        request = urllib.request.Request(  # noqa: S310 - always http://127.0.0.1
            self.origin + path,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}", **headers},
        )
        try:
            with no_proxy().open(request, timeout=30) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def stop(self) -> int:
        if sys.platform == "win32":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.process.send_signal(signal.SIGINT)
        return self.process.wait(30)

    def kill(self) -> None:
        self.process.kill()
        self.process.wait(30)


def multipart(name: str, data: bytes) -> tuple[bytes, str]:
    boundary = "sci2audio-test-boundary"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def other_address() -> str | None:
    """An address of this computer that is not loopback, if it has one (no packet is sent)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # TEST-NET-1; connecting a UDP socket sends nothing
        address = probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()
    return None if address.startswith("127.") or address == "0.0.0.0" else address  # noqa: S104


def test_a_real_server_answers_only_on_127_0_0_1_and_stops_on_ctrl_c(tmp_path: Path) -> None:
    server = Running(tmp_path)
    try:
        opener = no_proxy()
        with opener.open(server.url, timeout=30) as response:  # the start link: cookie, redirect
            assert response.status == 200
            assert b"Open a document" in response.read()
        with opener.open(server.origin + "/api/v1/settings", timeout=30) as response:
            assert json.loads(response.read())["settings"]["speed"] == 1.0
        status, _ = server.call("/api/v1/settings", Host=f"evil.example:{server.port}")
        assert status == 421
        address = other_address()
        if address is not None:
            with (
                pytest.raises(OSError),  # noqa: PT011 - refused or timed out, per system
                socket.create_connection((address, server.port), 2),
            ):
                pass
    finally:
        code = server.stop()
    if sys.platform != "win32":
        assert code == 0  # uvicorn stops cleanly on Ctrl-C


def test_a_killed_server_starts_again_and_finds_its_documents(tmp_path: Path) -> None:
    data = make_pdf([Text("A note that survives a restart.", 72, 100, size=11)])
    body, content_type = multipart("note.pdf", data)
    server = Running(tmp_path)
    try:
        status, answer = server.call("/api/v1/documents", body, **{"Content-Type": content_type})
        assert status == 201
        doc = json.loads(answer)["id"]
        start = json.dumps({"kind": "script", "document": doc}).encode()
        status, _ = server.call("/api/v1/jobs", start, **{"Content-Type": "application/json"})
        assert status == 202
    finally:
        server.kill()  # mid-job or just after; no clean-up runs
    server = Running(tmp_path)
    try:
        status, answer = server.call("/api/v1/documents")
        assert [d["id"] for d in json.loads(answer)] == [doc]
        status, answer = server.call("/api/v1/documents", body, **{"Content-Type": content_type})
        assert json.loads(answer)["id"] == doc
        status, answer = server.call("/api/v1/jobs", start, **{"Content-Type": "application/json"})
        assert status == 202
        job = json.loads(answer)["id"]
        assert job == f"{doc}-script-1"  # a new run counts from 1 again
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            state = json.loads(server.call(f"/api/v1/jobs/{job}")[1])["state"]
            if state != "running":
                break
            time.sleep(0.1)
        assert state == "done"
        assert list((tmp_path / "work").rglob("*.part")) == []
    finally:
        server.stop()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal")
def test_nothing_listens_after_the_server_stopped(tmp_path: Path) -> None:
    server = Running(tmp_path)
    port = server.port
    server.stop()
    with pytest.raises(ConnectionRefusedError), socket.create_connection(("127.0.0.1", port), 2):
        pass
