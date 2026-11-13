"""The minimal pages that exercise the API by hand (D-204).

Server-rendered with Jinja2 (autoescape on), one small script, no build step (D-101).
The accessible interface of #77 builds on these routes.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Annotated, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sci2audio.voices import missing_files
from sci2audio.web.documents import supported_suffixes
from sci2audio.web.state import ServerState, state_of

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(files("sci2audio.web") / "templates"))

State = Annotated[ServerState, state_of]


def _page(request: Request, name: str, status: int = 200, **context: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, name, context, status_code=status)


def _not_found(request: Request, what: str) -> HTMLResponse:
    return _page(request, "missing.html", 404, what=what)


@router.get("/", response_class=HTMLResponse)
def index(request: Request, state: State) -> HTMLResponse:
    return _page(
        request,
        "index.html",
        documents=state.store.all(),
        voice_installed=not missing_files(state.config.models_dir),
        suffixes=", ".join(supported_suffixes()),
        jobs=state.board.all(),
    )


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def document(request: Request, state: State, document_id: str) -> HTMLResponse:
    found = state.store.get(document_id)
    if found is None:
        return _not_found(request, f"document {document_id}")
    report = None
    try:
        report = json.loads(found.report_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    if not isinstance(report, dict):
        report = None
    return _page(request, "document.html", document=found, report=report)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job(request: Request, state: State, job_id: str) -> HTMLResponse:
    found = state.board.get(job_id)
    if found is None:
        return _not_found(request, f"job {job_id}")
    return _page(request, "job.html", job=found.snapshot())
