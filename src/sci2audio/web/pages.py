"""The browser interface (#77): server-rendered pages over the JSON API.

Jinja2 with autoescape, one small script, no build step (D-101). Four pages (D-244): the
start page, one page per document with three steps (check, voice, make), the job page
with progress and results, and the voice setup page. Every string comes from the table
in `strings/en.toml` through `t()` (D-256), so #79 can add German without touching the
templates.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Annotated, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
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
from sci2audio.web.api import plan_hosts
from sci2audio.web.config import UPLOAD_LIMIT
from sci2audio.web.documents import StoredDocument, supported_suffixes
from sci2audio.web.jobs import JobKind, JobRecord, JobState
from sci2audio.web.models import PREVIEW_LIMIT
from sci2audio.web.player import PlayerError, player_for
from sci2audio.web.state import ServerState, state_of
from sci2audio.web.tasks import plan_digest

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(files("sci2audio.web") / "templates"))

State = Annotated[ServerState, state_of]

EDITS_SHOWN = 500  # per category on the page; all of them are in report.md (D-248)
SPEED_STEP = 0.05


def _flatten(table: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in table.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(_flatten(value, f"{name}."))
        else:
            flat[name] = str(value)
    return flat


def load_strings(language: str = "en") -> dict[str, str]:
    """One language's table as `section.key` → text."""
    text = (files("sci2audio.web") / "strings" / f"{language}.toml").read_text(encoding="utf-8")
    return _flatten(tomllib.loads(text))


STRINGS = load_strings()


def t(key: str, /, **values: Any) -> str:
    """The interface text `key`, its placeholders filled in (escaped later by Jinja)."""
    text = STRINGS[key]
    return text.format(**values) if values else text


SCRIPT_KEYS = ("js.", "phase.", "make.needs_", "job.state_", "voice.speed_value", "player.")


def script_strings() -> str:
    """The strings the script uses, as JSON for the page's data block."""
    keys = {k: v for k, v in STRINGS.items() if k.startswith(SCRIPT_KEYS)}
    # `</` can't end the data block early: JSON allows `\/`
    return json.dumps(keys, ensure_ascii=False).replace("</", "<\\/")


def size_text(n: int) -> str:
    if n >= 1_000_000:
        return t("common.megabytes", n=f"{n / 1_000_000:.1f}".removesuffix(".0"))
    if n >= 1000:
        return t("common.kilobytes", n=round(n / 1000))
    return t("common.bytes", n=n)


templates.env.globals.update(t=t, size_text=size_text, script_strings=script_strings)


def _page(
    request: Request, state: ServerState, name: str, status: int = 200, **context: Any
) -> HTMLResponse:
    current = state.board.current
    context.setdefault("running", None if current is None else _job_view(state, current))
    return templates.TemplateResponse(request, name, context, status_code=status)


def _not_found(request: Request, state: ServerState, what: str) -> HTMLResponse:
    return _page(request, state, "missing.html", 404, what=what)


# --- the start page --------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def index(request: Request, state: State) -> HTMLResponse:
    suffixes = supported_suffixes()
    return _page(
        request,
        state,
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


@dataclass(frozen=True)
class CategoryView:
    id: str
    label: str
    on: bool
    counts: dict[str, int]
    rows: list[EditRow]
    total: int


def _said(edit: Mapping[str, Any]) -> str:
    kind = edit.get("kind")
    if kind == "remove":
        return t("check.said_removed")
    if kind == "pause" or edit.get("said") == PAUSE_MARK:
        return t("check.said_pause")
    if kind == "ask":
        return t("check.said_ask")
    return str(edit.get("said", ""))


def _status(edit: Mapping[str, Any]) -> str:
    status = edit.get("status")
    if status == "accepted":
        return t("check.status_applied") if edit.get("spoken") else t("check.status_not_spoken")
    if status == "set-aside":
        won = edit.get("won_by") or {}
        return t("check.status_set_aside", step=won.get("step", "?"))
    return t("check.status_switched_off")


def _edit_page(edit: Mapping[str, Any]) -> str:
    printed = edit.get("printed_page") or ""
    if printed:
        return str(printed)
    page = edit.get("page")
    return "" if page is None else str(page)


def _categories(
    report: Mapping[str, Any] | None, switched_off: Iterable[str]
) -> list[CategoryView]:
    off = set(switched_off)
    counts = (report or {}).get("counts", {})
    chapters = {c.get("index"): c.get("title", "") for c in (report or {}).get("chapters", [])}
    edits = (report or {}).get("edits", [])
    views = []
    for category in Category:
        mine = [edit for edit in edits if edit.get("category") == str(category)]
        rows = [
            EditRow(
                page=_edit_page(edit),
                chapter=str(chapters.get(edit.get("chapter"), "")),
                printed=str(edit.get("original") or t("check.position")),
                said=_said(edit),
                reason=str(edit.get("reason", "")),
                status=_status(edit),
            )
            for edit in mine[:EDITS_SHOWN]
        ]
        count = counts.get(str(category), {})
        views.append(
            CategoryView(
                id=str(category),
                label=STRINGS.get(f"category.{category}", category.label),
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


def _voice_options(chosen: str) -> list[dict[str, Any]]:
    default = DEFAULT_VOICE
    ordered = sorted(ENGLISH_VOICES, key=lambda v: (v.id != default, v.language, v.name))
    options = []
    for voice in ordered:
        key = "voice.accent_female" if voice.gender == "female" else "voice.accent_male"
        label = t(key, name=voice.name, accent=t(f"accent.{voice.language}"))
        if voice.id == default:
            label = f"{label} {t('voice.default')}"
        options.append({"id": voice.id, "label": label, "selected": voice.id == chosen})
    return options


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def document(request: Request, state: State, document_id: str) -> HTMLResponse:
    found = state.store.get(document_id)
    if found is None:
        return _not_found(request, state, t("common.not_found_document", id=document_id))
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
        last.snapshot()["error"]
        if last is not None and last.state is JobState.FAILED and not analysing
        else None
    )
    plan = download_plan()
    chosen_voice = saved.voice or DEFAULT_VOICE
    analysis_files = found.analysis_files()
    labels = {
        "script": t("document.file_script"),
        "json": t("document.file_report_json"),
        "md": t("document.file_report_md"),
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
        "document.html",
        document=found,
        report=report,
        analysing=analysing,
        analysis_job=current.id if analysing and current is not None else None,
        failed=failed,
        categories=_categories(report, switched_off),
        chapters=chapters,
        chosen_chapters=len(shown["chapters"]),
        edit_count=len(edits),
        heard=heard,
        shown=json.dumps(shown),
        file_links=file_links,
        voices=_voice_options(chosen_voice),
        licences=" ".join(dict.fromkeys(plan.licences)),
        voice_installed=not missing_files(state.config.models_dir),
        speed=saved.speed,
        speed_min=MIN_SPEED,
        speed_max=MAX_SPEED,
        speed_step=SPEED_STEP,
        preview_limit=PREVIEW_LIMIT,
        preview_text=PREVIEW_TEXT,
        output_folder=str(saved.output_folder or state.config.output_folder),
    )


# --- the job page ----------------------------------------------------------------------


def _job_view(state: ServerState, job: JobRecord) -> dict[str, Any]:
    snapshot = job.snapshot()
    document = None if job.document is None else state.store.get(job.document)
    name = "" if document is None else document.name
    title = t(f"job.title_{job.kind}", name=name)
    return {**snapshot, "title": title, "name": name}


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job(request: Request, state: State, job_id: str) -> HTMLResponse:
    found = state.board.get(job_id)
    if found is None:
        return _not_found(request, state, t("common.not_found_job", id=job_id))
    view = _job_view(state, found)
    document = None if found.document is None else state.store.get(found.document)
    progress = view.get("progress") or {}
    return _page(
        request,
        state,
        "job.html",
        job=view,
        document=document,
        cache_bytes=0 if document is None else document.speech_cache_bytes,
        skipped=progress.get("skipped", []) if view["state"] == "done" else [],
        folder=view["files"][0]["folder"] if view["files"] else "",
    )


# --- the listen page (#78) ---------------------------------------------------------------


def _voice_name(voice_id: str) -> str:
    return next((v.name for v in ENGLISH_VOICES if v.id == voice_id), voice_id)


@router.get("/documents/{document_id}/listen", response_class=HTMLResponse)
def listen(request: Request, state: State, document_id: str) -> HTMLResponse:
    """The player with read-along on the original text (D-294 to D-303)."""
    found = state.store.get(document_id)
    if found is None:
        return _not_found(request, state, t("common.not_found_document", id=document_id))
    saved, _ = load_settings(state.config.config_file)
    try:
        view, _located = player_for(
            found.folder, found.id, saved.output_folder, state.config.output_folder
        )
    except PlayerError as error:
        return _page(
            request,
            state,
            "listen.html",
            document=found,
            view=None,
            problem=t(error.key, **error.values),
        )
    data = json.dumps(view.data(found.id), ensure_ascii=False).replace("</", "<\\/")
    return _page(
        request,
        state,
        "listen.html",
        document=found,
        view=view,
        voice=_voice_name(view.voice),
        data=data,
        problem=None,
    )


# --- the voice setup page --------------------------------------------------------------


@router.get("/voice", response_class=HTMLResponse)
def voice(request: Request, state: State) -> HTMLResponse:
    plan = download_plan()
    missing = missing_files(state.config.models_dir)
    return _page(
        request,
        state,
        "voice.html",
        installed=not missing,
        files=[
            {"target": f.target, "size": size_text(f.size), "licence": f.licence}
            for f in plan.files
        ],
        total=size_text(plan.total_bytes),
        missing=size_text(sum(f.size for f in missing)),
        hosts=plan_hosts([file.url for file in plan.files]),
        digest=plan_digest(plan),
    )
