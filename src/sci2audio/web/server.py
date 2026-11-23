"""The app factory: one FastAPI app per server run, everything passed in (no global state)."""

from __future__ import annotations

import errno
import mimetypes
import time
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match
from starlette.types import ASGIApp, Receive, Scope, Send

from sci2audio import __version__
from sci2audio.app import JobRunner, VoiceSource
from sci2audio.app.updates import UpdateCheck
from sci2audio.web import api, pages
from sci2audio.web.config import ServerConfig
from sci2audio.web.limits import BodyLimit
from sci2audio.web.markers import MarkerBook
from sci2audio.web.security import LocalOnly
from sci2audio.web.state import ApiError, ServerState
from sci2audio.web.tasks import Fetch

# FastAPI (0.143 and later) instruments every request with OpenTelemetry. Without an SDK
# and exporter that does nothing, but sci2audio promises no telemetry, so all of it is
# switched off here, including the export it would set up from environment variables
# (D-195). `test_web_security.py` checks this.
TELEMETRY_OFF: dict[str, Any] = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}
_STATUS_KINDS = {
    400: "bad-request",
    404: "not-found",
    405: "method-not-allowed",
    413: "too-large",
    415: "unsupported-file",
}


def _allowed(request: Request) -> list[str]:
    """Every method some route at this path answers."""
    methods: set[str] = set()
    for route in request.app.router.routes:
        match, _ = route.matches({**request.scope, "method": "\x00"})
        if match is not Match.NONE:
            methods |= getattr(route, "methods", None) or set()
    return sorted(methods)


def create_app(
    config: ServerConfig,
    *,
    runner: JobRunner | None = None,
    fetch: Fetch | None = None,
    voice: Callable[[Path], VoiceSource] | None = None,
    clock: Callable[[], float] | None = None,
    updates: UpdateCheck | None = None,
) -> FastAPI:
    """The server's app. `fetch` replaces the voice download's network fetch, `voice` the
    Kokoro voice, `clock` the markers' undo clock and `updates` the update check (tests)."""
    app = FastAPI(
        title="sci2audio",
        version=__version__,
        description="The local sci2audio server: documents, jobs, settings and voices.",
        docs_url=None,  # Swagger and ReDoc load scripts from a CDN (D-196)
        redoc_url=None,
        openapi_url="/openapi.json",  # behind the token like everything else
        telemetry=TELEMETRY_OFF,  # type: ignore[arg-type]
    )
    state = ServerState(config, runner or JobRunner(), fetch)
    if clock is not None:
        state.clock = clock
        state.markers = MarkerBook(clock)
    if voice is not None:
        state.voice = voice
    if updates is not None:
        state.updates = updates
    state.updates.poll()  # turned on and not checked for a day: check now (#217)
    app.state.sci2audio = state
    app.include_router(api.router)
    app.include_router(pages.router)
    static = files("sci2audio.web") / "static"
    # the bundled fonts (#385): not in every system's table of types (Windows, older Pythons)
    mimetypes.add_type("font/woff2", ".woff2")
    app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError) -> JSONResponse:
        body: dict[str, Any] = {"error": error.kind, "message": error.message}
        if error.chapters is not None:
            body["chapters"] = error.chapters
        return JSONResponse(body, error.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        kind = _STATUS_KINDS.get(error.status_code, "error")
        headers = dict(error.headers or {})
        if error.status_code == 405:  # Starlette names only the first route's methods
            headers["Allow"] = ", ".join(_allowed(request))
        return JSONResponse(
            {"error": kind, "message": str(error.detail)}, error.status_code, headers
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        parts = []
        for problem in error.errors():
            where = ".".join(str(part) for part in problem.get("loc", ()) if part != "body")
            parts.append(f"{where}: {problem.get('msg', 'invalid')}" if where else problem["msg"])
        return JSONResponse({"error": "invalid", "message": "; ".join(parts)}, 422)

    @app.exception_handler(OSError)
    async def disk(request: Request, error: OSError) -> JSONResponse:
        if error.errno == errno.ENOSPC:
            return JSONResponse(
                {"error": "disk-full", "message": "not enough disk space; free some space"}, 507
            )
        raise error

    app.add_middleware(Seen, state=state)  # innermost: only requests that passed the checks
    app.add_middleware(BodyLimit, upload_limit=config.upload_limit, text_limit=config.text_limit)
    app.add_middleware(LocalOnly, config=config)  # added last = outermost
    return app


class Seen:
    """Notes when the server last answered a request that passed the security checks, for
    the app without a window, which stops when nothing has asked for a while (#215)."""

    def __init__(self, app: ASGIApp, state: ServerState) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            self.state.seen = time.monotonic()
        await self.app(scope, receive, send)
