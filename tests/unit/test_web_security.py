"""Local-only security of the server (#7, D-193 to D-196): token, Host, Origin, headers,
no CORS, no docs pages, FastAPI's telemetry off."""

from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from starlette.websockets import WebSocketDisconnect
from web_helpers import (
    ORIGIN,
    PORT,
    anonymous,
    app_and_config,
    browser,
    make_config,
    offline,  # noqa: F401 - fixture
    program,
)

from sci2audio.testing import NetworkUsedError
from sci2audio.web import api, pages
from sci2audio.web.security import CSP, LocalOnly
from sci2audio.web.server import TELEMETRY_OFF

pytestmark = pytest.mark.usefixtures("offline")


@pytest.fixture
def server(tmp_path: Path) -> tuple[FastAPI, Any]:
    return app_and_config(tmp_path)


def every_path(app: FastAPI) -> list[str]:
    """One concrete path per route of the app (path parameters filled in)."""
    routes = [*api.router.routes, *pages.router.routes]
    paths = [re.sub(r"\{[^}]+\}", "0123456789abcdef", route.path) for route in routes]  # type: ignore[attr-defined]
    assert len(paths) >= 15
    return sorted({*paths, "/openapi.json", "/static/app.js", "/static/nothing.css"})


# --- token ------------------------------------------------------------------------------


def test_every_route_needs_the_token(server: tuple[FastAPI, Any]) -> None:
    app, _config = server
    client = anonymous(app)
    paths = [path for path in every_path(app) if path != "/start"]
    assert "/openapi.json" in paths
    assert "/api/v1/settings" in paths
    assert "/" in paths
    for path in paths:
        for method in ("GET", "POST", "PUT", "DELETE"):
            response = client.request(method, path, headers={"Origin": ORIGIN})
            assert response.status_code == 401, (method, path)
    assert client.get("/api/v1/jobs").json()["error"] == "no-token"
    assert "terminal" in client.get("/").text


def test_wrong_tokens_are_refused(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = anonymous(app)
    wrong = config.token[:-1] + ("A" if config.token[-1] != "A" else "B")
    for headers in (
        {"Authorization": f"Bearer {wrong}"},
        {"Authorization": f"Basic {config.token}"},
        {"Authorization": config.token},
        {"Cookie": f"{config.cookie_name}={wrong}"},
        {"Cookie": f"sci2audio-{PORT + 1}={config.token}"},  # another server's cookie
        {"Cookie": f"{config.cookie_name}={wrong}; {config.cookie_name}=x"},
        {"Authorization": "Bearer "},
    ):
        assert client.get("/api/v1/settings", headers=headers).status_code == 401, headers


def test_a_cookie_tossed_from_another_local_port_does_not_lock_the_person_out(
    server: tuple[FastAPI, Any],
) -> None:
    """Cookies ignore ports: a page on 127.0.0.1 at another port can set a second cookie with
    this server's name and a longer path, which the browser then sends first."""
    app, config = server
    client = anonymous(app)
    for cookie in (
        f"{config.cookie_name}=x; {config.cookie_name}={config.token}",
        f"{config.cookie_name}={config.token}; {config.cookie_name}=x",
        f"{config.cookie_name}=; other=1; {config.cookie_name}={config.token}",
    ):
        response = client.get("/api/v1/settings", headers={"Cookie": cookie})
        assert response.status_code == 200, cookie


def test_start_trades_the_token_for_a_strict_cookie(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = anonymous(app)
    response = client.get(f"/start?token={config.token}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"  # the token leaves the address bar
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"sci2audio-{PORT}={config.token};")
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert attributes == {"httponly", "samesite=strict", "path=/"}
    assert client.get("/api/v1/settings").status_code == 200
    assert client.get("/").status_code == 200


@pytest.mark.parametrize(
    "query", ["", "?token=", "?token=wrong", "?tok=x", "?token={t}&token={t}", "?token={t}x"]
)
def test_start_with_a_wrong_token_sets_no_cookie(server: tuple[FastAPI, Any], query: str) -> None:
    app, config = server
    response = anonymous(app).get("/start" + query.format(t=config.token), follow_redirects=False)
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_start_is_get_only(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    response = anonymous(app).post(f"/start?token={config.token}", headers={"Origin": ORIGIN})
    assert response.status_code == 405
    assert "set-cookie" not in response.headers


def test_a_program_uses_the_bearer_token_without_origin(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    response = program(app, config).put("/api/v1/settings", json={})
    assert response.status_code == 200


# --- Host, Origin, Sec-Fetch-Site --------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        f"evil.example:{PORT}",  # DNS rebinding: an attacker's name pointing at 127.0.0.1
        f"127.0.0.1:{PORT + 1}",
        "127.0.0.1",
        f"[::1]:{PORT}",
        f"0.0.0.0:{PORT}",
        f"127.0.0.1:{PORT}.evil.example",
        f"LOCALHOST:{PORT}x",
        "",
    ],
)
def test_wrong_host_is_refused_before_the_token(server: tuple[FastAPI, Any], host: str) -> None:
    app, config = server
    client = program(app, config)
    for path in ("/api/v1/settings", "/", f"/start?token={config.token}", "/openapi.json"):
        response = client.get(path, headers={"Host": host})
        assert response.status_code == 421, (host, path)
        assert "set-cookie" not in response.headers


def test_both_local_names_are_answered(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    for host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
        response = program(app, config).get("/api/v1/settings", headers={"Host": host})
        assert response.status_code == 200, host


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        f"http://127.0.0.1:{PORT + 1}",  # another program's page on this computer
        f"https://127.0.0.1:{PORT}",
        "null",
        f"http://evil.example:{PORT}",
        "",
    ],
)
def test_other_origins_are_refused(server: tuple[FastAPI, Any], origin: str) -> None:
    app, config = server
    for client in (browser(app, config), program(app, config)):
        assert client.get("/api/v1/settings", headers={"Origin": origin}).status_code == 403
        response = client.put("/api/v1/settings", json={}, headers={"Origin": origin})
        assert response.status_code == 403
    assert not config.config_file.exists()


@pytest.mark.parametrize("site", ["cross-site", "same-site", "other"])
def test_cross_site_fetches_are_refused(server: tuple[FastAPI, Any], site: str) -> None:
    app, config = server
    client = browser(app, config)
    assert client.get("/api/v1/settings", headers={"Sec-Fetch-Site": site}).status_code == 403
    response = client.get(f"/start?token={config.token}", headers={"Sec-Fetch-Site": site})
    assert response.status_code == 403


@pytest.mark.parametrize("site", ["same-origin", "none"])
def test_own_and_typed_fetches_are_answered(server: tuple[FastAPI, Any], site: str) -> None:
    app, config = server
    response = browser(app, config).get("/api/v1/settings", headers={"Sec-Fetch-Site": site})
    assert response.status_code == 200


def test_a_cookie_write_needs_the_own_origin(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = browser(app, config)
    for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
        response = client.request(method, "/api/v1/settings", json={})
        assert response.status_code == 403, method
    for origin in (ORIGIN, f"http://localhost:{PORT}"):
        response = client.put("/api/v1/settings", json={}, headers={"Origin": origin})
        assert response.status_code == 200, origin


def test_a_header_sent_twice_is_refused(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    scope_headers = [(b"host", f"127.0.0.1:{PORT}".encode())] * 2
    seen: list[int] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b""}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            seen.append(message["status"])

    import asyncio

    middleware = LocalOnly(app, config)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": scope_headers}
    asyncio.run(middleware(scope, receive, send))  # type: ignore[arg-type]
    assert seen == [421]


@given(st.text(max_size=40))
def test_only_the_two_local_hosts_pass(host: str) -> None:
    config = make_config(Path("/unused"))
    allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
    assert (host in config.hosts) == (host in allowed)
    assert (host in {o.removeprefix("http://") for o in config.origins}) == (host in allowed)


# --- response headers, CORS, docs, websockets -------------------------------------------


def test_security_headers_on_every_kind_of_answer(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    answers = [
        client.get("/api/v1/settings"),
        client.get("/"),
        client.get("/static/app.js"),
        client.get("/api/v1/jobs/nothing"),
        client.get("/no/such/page"),
        anonymous(app).get("/api/v1/settings"),
        client.get("/", headers={"Host": "evil.example"}),
        client.get("/", headers={"Origin": "https://evil.example"}),
    ]
    assert [a.status_code for a in answers] == [200, 200, 200, 404, 404, 401, 421, 403]
    for answer in answers:
        assert answer.headers["content-security-policy"] == CSP
        assert answer.headers["x-content-type-options"] == "nosniff"
        assert answer.headers["referrer-policy"] == "no-referrer"
        assert answer.headers["x-frame-options"] == "DENY"
        assert answer.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in answer.headers
    assert "frame-ancestors 'none'" in CSP
    assert "script-src 'self'" in CSP


def test_no_cors_preflight_is_answered(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    response = program(app, config).options(
        "/api/v1/settings",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    assert response.status_code == 403
    response = program(app, config).options("/api/v1/settings")
    assert response.status_code == 405
    assert not any(name.startswith("access-control-") for name in response.headers)


def test_docs_pages_are_off_and_the_schema_needs_the_token(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/docs/oauth2-redirect").status_code == 404
    assert client.get("/openapi.json").status_code == 200
    assert anonymous(app).get("/openapi.json").status_code == 401


def test_websockets_are_never_accepted(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    client = program(app, config)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/v1/jobs"):
        pass


def test_the_server_header_names_nothing(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    response = program(app, config).get("/api/v1/settings")
    assert "x-powered-by" not in response.headers


# --- FastAPI's telemetry (D-195) ----------------------------------------------------------


def test_fastapis_telemetry_is_switched_off(server: tuple[FastAPI, Any]) -> None:
    app, _ = server
    config = app._telemetry  # type: ignore[attr-defined]
    for key, value in TELEMETRY_OFF.items():
        assert config[key] is value, key
    assert not app._native_telemetry.enabled()  # type: ignore[attr-defined]


def test_no_tracer_is_asked_for_even_when_one_is_installed(
    server: tuple[FastAPI, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a configured tracer provider FastAPI would trace every request; ours never asks."""
    from opentelemetry import trace

    asked: list[str] = []

    class Recording(trace.NoOpTracerProvider):
        def get_tracer(self, *args: Any, **kwargs: Any) -> trace.Tracer:
            asked.append(str(args[:1]))
            return super().get_tracer(*args, **kwargs)

    monkeypatch.setattr(trace, "get_tracer_provider", lambda: Recording())
    app, config = server
    assert not app._native_telemetry.enabled()  # type: ignore[attr-defined]
    assert program(app, config).get("/api/v1/settings").status_code == 200
    assert asked == []
    plain = FastAPI()
    assert plain._native_telemetry.enabled()  # type: ignore[attr-defined]  # the default


def test_export_from_environment_variables_stays_off(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """FastAPI's own environment switch for exporting telemetry is ignored by our app; a
    default FastAPI app tries to set up the exporter (and only fails for the missing extra)."""
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.example:4318")
    app, config = app_and_config(Path("/unused"))
    with caplog.at_level("DEBUG"), TestClient(app, base_url=ORIGIN) as client:  # lifespan runs
        headers = {"Authorization": f"Bearer {config.token}"}
        assert client.get("/api/v1/settings", headers=headers).status_code == 200
    assert not [r for r in caplog.records if "telemetry" in r.getMessage().lower()]
    with caplog.at_level("DEBUG"), TestClient(FastAPI()):
        pass
    assert [r for r in caplog.records if "telemetry" in r.getMessage().lower()]


def test_the_api_documents_every_api_route(server: tuple[FastAPI, Any]) -> None:
    app, config = server
    documented = set(program(app, config).get("/openapi.json").json()["paths"])
    assert documented == {route.path for route in api.router.routes}  # type: ignore[attr-defined]
    assert all(path.startswith("/api/v1/") for path in documented)


def test_the_web_tests_block_every_connect_but_a_socketpairs_own(
    offline: list[str],  # noqa: F811 - the fixture
) -> None:
    """The `offline` fixture lets Windows' emulated socketpair connect to its own loopback
    listener (every event loop makes one), and nothing else."""
    first, second = socket.socketpair()
    with first, second:
        first.sendall(b"x")
        assert second.recv(1) == b"x"
    assert offline == []
    for address in [("192.0.2.1", 80), ("127.0.0.1", 9)]:
        with socket.socket() as sock, pytest.raises(NetworkUsedError):
            sock.connect(address)
    assert len(offline) == 2
    offline.clear()
