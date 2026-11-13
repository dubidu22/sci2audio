"""The browser interface (#77, #79): server-rendered pages over the JSON API.

Jinja2 with autoescape, one small script, no build step (D-101). Five pages (D-244,
D-293): the start page, one page per document with three steps (check, voice, make), the
job page with progress and results, the voice setup page and the privacy page. Every
string comes from the request's language table in `strings/<language>.toml` through `t()`
(D-256, D-288 to D-290); there is no page-wide language, each request gets its own.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Annotated, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sci2audio.app import load_settings
from sci2audio.app.settings import MAX_SPEED, MIN_SPEED
from sci2audio.textprep import DEFAULT_SWITCHED_OFF, PAUSE_MARK, Category
from sci2audio.voices import (
    DEFAULT_VOICE,
    ENGLISH_VOICES,
    PREVIEW_TEXT,
    download_plan,
    missing_files,
)
from sci2audio.web.api import REDIRECTS, plan_hosts
from sci2audio.web.config import UPLOAD_LIMIT
from sci2audio.web.documents import StoredDocument, supported_suffixes
from sci2audio.web.i18n import (
    COOKIE,
    COOKIE_AGE,
    LANGUAGES,
    Strings,
    local_path,
    strings_of,
)
from sci2audio.web.jobs import JobKind, JobRecord, JobState
from sci2audio.web.models import PREVIEW_LIMIT
from sci2audio.web.state import ServerState, state_of
from sci2audio.web.tasks import plan_digest

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(files("sci2audio.web") / "templates"))

State = Annotated[ServerState, state_of]

EDITS_SHOWN = 500  # per category on the page; all of them are in report.md (D-248)
SPEED_STEP = 0.05


_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")


def hosts_shown(remote: Iterable[Any], s: Strings) -> list[str]:
    """The hosts the voice download talks to (`api.plan_hosts`), with the words for where
    they send it on in the page's language."""
    redirects = {text: host for host, text in REDIRECTS.items()}
    hosts = plan_hosts([file.url for file in remote])
    return [s(f"redirect.{redirects[host]}") if host in redirects else host for host in hosts]


def failure(s: Strings, error: Mapping[str, Any] | None) -> dict[str, str] | None:
    """A job's or the server's error in the page's language: the table's sentence for its
    kind, with the app's own words as details; an unknown kind shows those words alone
    (D-291)."""
    if not error:
        return None
    message = str(error.get("message", ""))
    reason = s.table.get(f"error.{error.get('error')}")
    if reason is None:
        return {"reason": message, "details": ""}
    return {"reason": reason, "details": message}


def _page(
    request: Request,
    state: ServerState,
    s: Strings,
    name: str,
    status: int = 200,
    **context: Any,
) -> HTMLResponse:
    current = state.board.current
    context.setdefault("running", None if current is None else _job_view(state, current, s))
    query = request.url.query
    context.update(
        t=s,
        strings=s,
        size_text=s.size,
        script_strings=s.script_json,
        languages=LANGUAGES,
        here=local_path(request.url.path + (f"?{query}" if query else "")),
    )
    return templates.TemplateResponse(request, name, context, status_code=status)


def _not_found(request: Request, state: ServerState, s: Strings, what: str) -> HTMLResponse:
    return _page(request, state, s, "missing.html", 404, what=what)


# --- the start page --------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def index(request: Request, state: State) -> HTMLResponse:
    suffixes = supported_suffixes()
    return _page(
        request,
        state,
        strings_of(request),
        "index.html",
        documents=state.store.all(),
        voice_installed=not missing_files(state.config.models_dir),
        types=", ".join(suffix.removeprefix(".").upper() for suffix in suffixes),
        accept=",".join(suffixes),
        limit=UPLOAD_LIMIT // (1024 * 1024),
        paste=".txt" in suffixes,  # pasted text is kept as .txt; readable once #74 lands
    )


# --- the document page -----------------------------------------------------------------


@dataclass(frozen=True)
class EditRow:
    page: str
    chapter: str
    printed: str
    said: str
    reason: str
    status: str
    printed_is_text: bool  # the document's words, not the interface's
    said_is_text: bool


@dataclass(frozen=True)
class CategoryView:
    id: str
    label: str
    on: bool
    counts: dict[str, int]
    rows: list[EditRow]
    total: int


def _said(edit: Mapping[str, Any], s: Strings) -> tuple[str, bool]:
    """What is read instead, and whether that is the document's text."""
    kind = edit.get("kind")
    if kind == "remove":
        return s("check.said_removed"), False
    if kind == "pause" or edit.get("said") == PAUSE_MARK:
        return s("check.said_pause"), False
    if kind == "ask":
        return s("check.said_ask"), False
    return str(edit.get("said", "")), True


def _status(edit: Mapping[str, Any], s: Strings) -> str:
    status = edit.get("status")
    if status == "accepted":
        return s("check.status_applied") if edit.get("spoken") else s("check.status_not_spoken")
    if status == "set-aside":
        won = edit.get("won_by") or {}
        return s("check.status_set_aside", step=won.get("step", "?"))
    return s("check.status_switched_off")


def _edit_page(edit: Mapping[str, Any]) -> str:
    printed = edit.get("printed_page") or ""
    if printed:
        return str(printed)
    page = edit.get("page")
    return "" if page is None else str(page)


def _row(edit: Mapping[str, Any], chapters: Mapping[Any, Any], s: Strings) -> EditRow:
    original = edit.get("original")
    said, said_is_text = _said(edit, s)
    return EditRow(
        page=_edit_page(edit),
        chapter=str(chapters.get(edit.get("chapter"), "")),
        printed=str(original or s("check.position")),
        said=said,
        reason=str(edit.get("reason", "")),
        status=_status(edit, s),
        printed_is_text=bool(original),
        said_is_text=said_is_text,
    )


def _categories(
    report: Mapping[str, Any] | None, switched_off: Iterable[str], s: Strings
) -> list[CategoryView]:
    off = set(switched_off)
    counts = (report or {}).get("counts", {})
    chapters = {c.get("index"): c.get("title", "") for c in (report or {}).get("chapters", [])}
    edits = (report or {}).get("edits", [])
    views = []
    for category in Category:
        mine = [edit for edit in edits if edit.get("category") == str(category)]
        rows = [_row(edit, chapters, s) for edit in mine[:EDITS_SHOWN]]
        count = counts.get(str(category), {})
        views.append(
            CategoryView(
                id=str(category),
                label=s.table.get(f"category.{category}", category.label),
                on=str(category) not in off,
                counts={
                    key: int(count.get(key, 0))
                    for key in ("applied", "not_spoken", "set_aside", "switched_off")
                },
                rows=rows,
                total=len(mine),
            )
        )
    return views


def _report(document: StoredDocument) -> dict[str, Any] | None:
    try:
        report = json.loads(document.report_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return report if isinstance(report, dict) else None


def _last_script_job(state: ServerState, document_id: str) -> JobRecord | None:
    return next(
        (
            job
            for job in state.board.all()
            if job.kind is JobKind.SCRIPT and job.document == document_id
        ),
        None,
    )


def _voice_options(chosen: str, s: Strings) -> list[dict[str, Any]]:
    default = DEFAULT_VOICE
    ordered = sorted(ENGLISH_VOICES, key=lambda v: (v.id != default, v.language, v.name))
    options = []
    for voice in ordered:
        key = "voice.accent_female" if voice.gender == "female" else "voice.accent_male"
        label = s(key, name=voice.name, accent=s(f"accent.{voice.language}"))
        if voice.id == default:
            label = f"{label} {s('voice.default')}"
        options.append({"id": voice.id, "label": label, "selected": voice.id == chosen})
    return options


def _text_language(report: Mapping[str, Any] | None) -> str:
    """The language of the document's own words, for their `lang` attribute (D-291)."""
    language = str((report or {}).get("language") or "en")
    return language if _TAG.match(language) else "en"


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def document(request: Request, state: State, document_id: str) -> HTMLResponse:
    s = strings_of(request)
    found = state.store.get(document_id)
    if found is None:
        return _not_found(request, state, s, s("common.not_found_document", id=document_id))
    saved, _ = load_settings(state.config.config_file)
    report = _report(found)
    # the controls start from what the report on screen was made with (D-245, D-246)
    report_settings = (report or {}).get("settings") or {}
    switched_off = report_settings.get(
        "switched_off", sorted(str(c) for c in saved.switched_off or DEFAULT_SWITCHED_OFF)
    )
    chapters = (report or {}).get("chapters", [])
    edits = (report or {}).get("edits", [])
    heard = sum(1 for e in edits if e.get("status") == "accepted" and e.get("spoken"))
    current = state.board.current
    analysing = (
        current is not None and current.kind is JobKind.SCRIPT and current.document == found.id
    )
    last = _last_script_job(state, found.id)
    failed = (
        failure(s, last.snapshot()["error"])
        if last is not None and last.state is JobState.FAILED and not analysing
        else None
    )
    plan = download_plan()
    chosen_voice = saved.voice or DEFAULT_VOICE
    analysis_files = found.analysis_files()
    labels = {
        "script": s("document.file_script"),
        "json": s("document.file_report_json"),
        "md": s("document.file_report_md"),
    }
    file_links = [
        {
            "name": path.name,
            "label": labels["script" if path.name.endswith(".script.txt") else path.suffix[1:]],
        }
        for path in analysis_files
    ]
    shown = {
        "switched_off": sorted(switched_off),
        "chapters": sorted(c["index"] for c in chapters if c.get("selected")),
    }
    return _page(
        request,
        state,
        s,
        "document.html",
        document=found,
        report=report,
        text_language=_text_language(report),
        analysing=analysing,
        analysis_job=current.id if analysing and current is not None else None,
        failed=failed,
        categories=_categories(report, switched_off, s),
        chapters=chapters,
        chosen_chapters=len(shown["chapters"]),
        edit_count=len(edits),
        heard=heard,
        shown=json.dumps(shown),
        file_links=file_links,
        voices=_voice_options(chosen_voice, s),
        licences=" ".join(dict.fromkeys(plan.licences)),
        voice_installed=not missing_files(state.config.models_dir),
        speed=saved.speed,
        speed_text=s("voice.speed_value", value=s.number(saved.speed)),
        speed_min=MIN_SPEED,
        speed_max=MAX_SPEED,
        speed_step=SPEED_STEP,
        preview_limit=PREVIEW_LIMIT,
        preview_text=PREVIEW_TEXT,
        output_folder=str(saved.output_folder or state.config.output_folder),
    )


# --- the job page ----------------------------------------------------------------------


def _job_view(state: ServerState, job: JobRecord, s: Strings) -> dict[str, Any]:
    snapshot = job.snapshot()
    document = None if job.document is None else state.store.get(job.document)
    name = "" if document is None else document.name
    title = s(f"job.title_{job.kind}", name=name)
    return {**snapshot, "title": title, "name": name, "failure": failure(s, snapshot["error"])}


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job(request: Request, state: State, job_id: str) -> HTMLResponse:
    s = strings_of(request)
    found = state.board.get(job_id)
    if found is None:
        return _not_found(request, state, s, s("common.not_found_job", id=job_id))
    view = _job_view(state, found, s)
    document = None if found.document is None else state.store.get(found.document)
    progress = view.get("progress") or {}
    return _page(
        request,
        state,
        s,
        "job.html",
        job=view,
        document=document,
        cache_bytes=0 if document is None else document.speech_cache_bytes,
        skipped=progress.get("skipped", []) if view["state"] == "done" else [],
        folder=view["files"][0]["folder"] if view["files"] else "",
    )


# --- the voice setup page --------------------------------------------------------------


@router.get("/voice", response_class=HTMLResponse)
def voice(request: Request, state: State) -> HTMLResponse:
    s = strings_of(request)
    plan = download_plan()
    missing = missing_files(state.config.models_dir)
    return _page(
        request,
        state,
        s,
        "voice.html",
        installed=not missing,
        files=[
            {"target": f.target, "size": s.size(f.size), "licence": f.licence} for f in plan.files
        ],
        total=s.size(plan.total_bytes),
        missing=s.size(sum(f.size for f in missing)),
        hosts=hosts_shown(plan.files, s),
        digest=plan_digest(plan),
    )


# --- the privacy page (D-293) ----------------------------------------------------------


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, state: State) -> HTMLResponse:
    """What stays on this computer, with the hosts and folders of this very server, so the
    page can't say something the program doesn't do."""
    s = strings_of(request)
    saved, _ = load_settings(state.config.config_file)
    plan = download_plan()
    return _page(
        request,
        state,
        s,
        "privacy.html",
        hosts=hosts_shown(plan.files, s),
        folders=[
            ("work", str(state.config.work_root)),
            ("output", str(saved.output_folder or state.config.output_folder)),
            ("settings", str(state.config.config_file)),
            ("voice", str(state.config.models_dir)),
        ],
    )


# --- the language switch (D-288) -------------------------------------------------------


@router.get("/language")
def choose_language(request: Request, language: str = "", back: str = "") -> RedirectResponse:
    """Remembers the chosen language in its own cookie and goes back to the page the switch
    was on: a path on this server, never another address.

    A GET form, not a POST (D-321): every answer carries `Referrer-Policy: no-referrer` (D-194), so
    browsers send `Origin: null` with a form POST, which the origin check refuses. The GET
    is guarded like every page (start cookie, `Sec-Fetch-Site`), sets nothing but the
    language, and another site can't reach it: its navigation is cross-site and carries no
    `SameSite=Strict` start cookie.
    """
    response = RedirectResponse(local_path(back), 303)
    if language in LANGUAGES:
        response.set_cookie(
            COOKIE, language, max_age=COOKIE_AGE, path="/", samesite="strict", httponly=True
        )
    return response
