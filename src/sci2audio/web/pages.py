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

from sci2audio.app import load_settings, shown_original
from sci2audio.app.settings import MAX_SPEED, MIN_SPEED
from sci2audio.app.voice import primary_language
from sci2audio.textprep import DEFAULT_SWITCHED_OFF, PAUSE_MARK, Category
from sci2audio.voices import (
    DEFAULT_VOICE,
    DEFAULT_VOICES,
    PACKS,
    VOICES,
    download_plan,
    missing_files,
    preview_text,
    voice_pack,
)
from sci2audio.web.api import REDIRECTS, plan_hosts
from sci2audio.web.config import UPLOAD_LIMIT
from sci2audio.web.documents import StoredDocument, supported_suffixes
from sci2audio.web.i18n import (
    COOKIE,
    COOKIE_AGE,
    LANGUAGES,
    Strings,
    data_block,
    known_language,
    local_path,
    strings_of,
)
from sci2audio.web.jobs import JobKind, JobRecord, JobState
from sci2audio.web.models import PREVIEW_LIMIT
from sci2audio.web.player import PlayerError, player_for, recorded_folder
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


def _removal(document: StoredDocument) -> dict[str, Any]:
    """What removing the document takes away and where its audiobook stays (D-359)."""
    folder = recorded_folder(document.folder, document.id)
    return {
        "bytes": document.folder_bytes,
        "folder": None if folder is None else str(folder),
        "has_audio": document.has_audio,
    }


def _busy_document(state: ServerState) -> str | None:
    """The document this server's running job works on, if any (D-362)."""
    current = state.board.current
    return None if current is None else current.document


# --- the start page --------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def index(request: Request, state: State) -> HTMLResponse:
    s = strings_of(request)
    suffixes = supported_suffixes()
    documents = state.store.all()
    return _page(
        request,
        state,
        s,
        "index.html",
        documents=documents,
        removals={document.id: _removal(document) for document in documents},
        busy_document=_busy_document(state),
        voice_installed=not missing_files(state.config.models_dir),
        voice_partly=_missing_packs(state, s),
        types=", ".join(suffix.removeprefix(".").upper() for suffix in suffixes),
        accept=",".join(suffixes),
        limit=UPLOAD_LIMIT // (1024 * 1024),
        paste=".txt" in suffixes,  # pasted text is kept as a .txt file and read as text (#74)
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
        printed=shown_original(str(original)) if original else s("check.position"),
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
    defaults = set(DEFAULT_VOICES.values())
    ordered = sorted(
        VOICES, key=lambda v: (v.id != default, v.id not in defaults, v.language, v.name)
    )
    options = []
    for voice in ordered:
        key = "voice.accent_female" if voice.gender == "female" else "voice.accent_male"
        label = s(key, name=voice.name, accent=s(f"accent.{voice.language}"))
        if voice.id == default:
            label = f"{label} {s('voice.default')}"
        elif voice.id in defaults:
            label = f"{label} {s('voice.default_for', language=s(f'pack.{voice_pack(voice.id)}'))}"
        options.append(
            {
                "id": voice.id,
                "label": label,
                "selected": voice.id == chosen,
                "language": voice.language,
            }
        )
    return options


def _document_voice(saved_voice: str, text_language: str) -> str:
    """The voice the page starts with: the saved one if it speaks the text's language,
    else that language's default (the rule the audio job follows, D-469)."""
    primary = primary_language(text_language)
    default = DEFAULT_VOICES.get(primary)
    speaks = {v.id: primary_language(v.language) for v in VOICES}
    if default is None:
        return saved_voice or DEFAULT_VOICE
    return saved_voice if speaks.get(saved_voice) == primary else default


def _packs() -> set[str]:
    """The voice packs the download has files for."""
    return {f.pack for f in download_plan().files}


def _installed(state: ServerState) -> tuple[str, ...]:
    """The voice packs whose files are all installed (D-468)."""
    packs = _packs()
    missing = {f.pack for f in missing_files(state.config.models_dir)}
    return tuple(language for language in PACKS if language in packs - missing)


def _missing_packs(state: ServerState, s: Strings) -> str:
    """The languages whose voices are not installed, for a note when some others are
    ("" when every pack or none is installed)."""
    there = _installed(state)
    if not there:
        return ""
    packs = _packs()
    return ", ".join(
        s(f"pack.{language}") for language in PACKS if language in packs and language not in there
    )


def _text_language(report: Mapping[str, Any] | None) -> str:
    """The language of the document's own words, for their `lang` attribute (D-291)."""
    language = str((report or {}).get("language") or "en")
    return language if _TAG.match(language) else "en"


def _language_note(report: Mapping[str, Any] | None, s: Strings) -> str | None:
    """The text's language and where it came from (D-499), or None for a report that
    doesn't say (made before v1.1)."""
    language = _text_language(report)
    primary = primary_language(language)
    name = s(f"pack.{primary}") if primary in PACKS else language
    notes = {
        "setting": lambda: s("voice.text_language_setting", language=name),
        "file": lambda: s("voice.text_language_file", language=name),
        "text": lambda: s("voice.text_language_text", language=name),
        "fallback": lambda: s("voice.text_language_fallback", language=name),
    }
    note = notes.get(str((report or {}).get("language_source")))
    return note() if note else None


def _language_options(chosen: str, s: Strings) -> list[dict[str, Any]]:
    """The choices for the text's language (#212, D-521, D-522): automatic, then each
    language sci2audio reads; a tag the report was made with that is none of these (from the
    config file or the command line) is offered too, chosen, so nothing changes unseen."""
    options = [{"value": "", "label": s("check.language_auto")}]
    options += [{"value": code, "label": s(f"pack.{code}")} for code in PACKS]
    if chosen not in {option["value"] for option in options}:
        options.append({"value": chosen, "label": s("check.language_other", language=chosen)})
    return [{**option, "selected": option["value"] == chosen} for option in options]


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
    chosen_voice = _document_voice(saved.voice, _text_language(report))
    installed = _installed(state)
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
    # the language the report was made with ("" = automatic); a job made from this page
    # uses it, and it is not remembered for other documents (#212, D-521)
    language = str(report_settings.get("language", saved.language) or "")
    shown = {
        "switched_off": sorted(switched_off),
        "chapters": sorted(c["index"] for c in chapters if c.get("selected")),
        "language": language,
    }
    return _page(
        request,
        state,
        s,
        "document.html",
        document=found,
        report=report,
        text_language=_text_language(report),
        language_note=_language_note(report, s),
        language_options=_language_options(language, s),
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
        voice_installed=bool(installed),  # some voice: the preview works
        # the voice a job on this text uses (D-469) has its files: making can start (D-468)
        job_voice_installed=voice_pack(chosen_voice) in installed,
        voice_partly=_missing_packs(state, s),
        speed=saved.speed,
        speed_text=s("voice.speed_value", value=s.number(saved.speed)),
        speed_min=MIN_SPEED,
        speed_max=MAX_SPEED,
        speed_step=SPEED_STEP,
        preview_limit=PREVIEW_LIMIT,
        preview_text=preview_text(_voice_language(chosen_voice)),
        preview_text_language=primary_language(_voice_language(chosen_voice)),
        preview_texts={primary: preview_text(primary) for primary in DEFAULT_VOICES},
        output_folder=str(saved.output_folder or state.config.output_folder),
        removal=_removal(found),
        busy=_busy_document(state) == found.id,
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


# --- the listen page (#78) ---------------------------------------------------------------


def _voice_name(voice_id: str) -> str:
    return next((v.name for v in VOICES if v.id == voice_id), voice_id)


def _voice_language(voice_id: str) -> str:
    return next((v.language for v in VOICES if v.id == voice_id), "en")


@router.get("/documents/{document_id}/listen", response_class=HTMLResponse)
def listen(request: Request, state: State, document_id: str) -> HTMLResponse:
    """The player with read-along on the original text (D-294 to D-303)."""
    s = strings_of(request)
    found = state.store.get(document_id)
    if found is None:
        return _not_found(request, state, s, s("common.not_found_document", id=document_id))
    saved, _ = load_settings(state.config.config_file)
    try:
        view, _located = player_for(
            found.folder, found.id, saved.output_folder, state.config.output_folder
        )
    except PlayerError as error:
        return _page(
            request,
            state,
            s,
            "listen.html",
            document=found,
            view=None,
            problem=s(error.key, **error.values),
        )
    return _page(
        request,
        state,
        s,
        "listen.html",
        document=found,
        view=view,
        voice=_voice_name(view.voice),
        data=data_block(view.data(found.id)),
        problem=None,
    )


# --- the voice setup page --------------------------------------------------------------


@router.get("/voice", response_class=HTMLResponse)
def voice(request: Request, state: State) -> HTMLResponse:
    s = strings_of(request)
    plan = download_plan()
    missing = missing_files(state.config.models_dir)
    there = _installed(state)
    return _page(
        request,
        state,
        s,
        "voice.html",
        installed=not missing,
        packs=[
            {"name": s(f"setup.pack_{language}"), "installed": language in there}
            for language in PACKS
        ],
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

    A GET form, not a POST (D-321): every answer carries `Referrer-Policy: no-referrer`
    (D-194), so browsers send `Origin: null` with a form POST, which the origin check
    refuses. The GET is guarded like every page (start cookie, `Sec-Fetch-Site`), sets
    nothing but the language, and another site can't reach it: its navigation is
    cross-site and carries no `SameSite=Strict` start cookie.
    """
    response = RedirectResponse(local_path(back), 303)
    chosen = known_language(language)  # one of LANGUAGES, never the request's text
    if chosen is not None:
        response.set_cookie(
            COOKIE, chosen, max_age=COOKIE_AGE, path="/", samesite="strict", httponly=True
        )
    return response
