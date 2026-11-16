"""The browser interface (#77, #79): server-rendered pages over the JSON API.

Jinja2 with autoescape, one small script, no build step (D-101). The pages (D-244, D-293,
D-663): the library, each document's Prepare page with three steps (check, voice, make)
and its audiobook job inline (#391), Listen, the job page of the other jobs, the voices,
Settings and the privacy page. Every
string comes from the request's language table in `strings/<language>.toml` through `t()`
(D-256, D-288 to D-290); there is no page-wide language, each request gets its own.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path, PurePath
from typing import Annotated, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sci2audio.app import load_settings, shown_original
from sci2audio.app.settings import LETTER_PACES, MAX_SPEED, MIN_SPEED
from sci2audio.app.voice import primary_language
from sci2audio.textprep import DEFAULT_SWITCHED_OFF, PAUSE_MARK, Category
from sci2audio.voices import (
    DEFAULT_VOICE,
    DEFAULT_VOICES,
    ENGLISH,
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
    ANNOUNCE_COOKIE,
    COOKIE,
    COOKIE_AGE,
    LANGUAGES,
    THEME_COOKIE,
    THEMES,
    Strings,
    announce_of,
    data_block,
    known_announce,
    known_language,
    known_theme,
    local_path,
    strings_of,
    theme_of,
)
from sci2audio.web.jobs import JobKind, JobRecord, JobState
from sci2audio.web.library import (
    OPENED,
    Heard,
    heard,
    length_text,
    matches,
    position_age,
    read_about,
    read_opened,
    search_text,
    when,
    write_opened,
)
from sci2audio.web.models import PREVIEW_LIMIT
from sci2audio.web.player import (
    PlayerError,
    PlayerView,
    Position,
    candidate_folders,
    player_for,
    read_position,
    recorded_folder,
)
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


# the rail item each page marks as the current one (#387); other pages mark none
NAV_ITEMS = {
    "index.html": "library",
    "voice.html": "voices",
    "settings.html": "settings",
    "privacy.html": "privacy",
    "job.html": "job",
}


def progress_fraction(progress: Mapping[str, Any] | None) -> float | None:
    """How far a job is, 0 to 1, or None when it can't tell: the same rule as the job
    page's script (`fraction` in app.js), so the rail's meter and the page agree."""
    if not progress:
        return None
    pages = progress.get("pages")
    if progress.get("phase") == "reading" and pages:
        return min(1.0, (progress.get("page") or 0) / pages)
    total = progress.get("chunks_total")
    if total:
        return min(1.0, (progress.get("chunks_done") or 0) / total)
    total = progress.get("bytes_total")
    if total:
        return min(1.0, (progress.get("bytes_done") or 0) / total)
    return None


def _shelf_job(state: ServerState, job: JobRecord, s: Strings) -> dict[str, Any]:
    """The running job as the rail's shelf item (#387): its title, a few words on how far
    it is, and its meter in percent (None while it can't tell)."""
    view = _job_view(state, job, s)
    progress = view.get("progress") or {}
    part = progress_fraction(progress)
    percent = None if part is None else int(100 * part)
    phase = progress.get("phase")
    words = s.table.get(f"phase.{phase}") if phase else None
    if words is None:
        words = s(f"job.state_{view['state']}")
    shelf_text = words if percent is None else s("shelf.made", phase=words, n=percent)
    return {**view, "percent": percent, "shelf_text": shelf_text}


def _page(
    request: Request,
    state: ServerState,
    s: Strings,
    name: str,
    status: int = 200,
    **context: Any,
) -> HTMLResponse:
    current = state.board.current
    context.setdefault("running", None if current is None else _shelf_job(state, current, s))
    context.setdefault("shelf", _shelf(state, s, context.get("shelf_here")))
    if "library_count" not in context:
        context["library_count"] = len(state.store.all()) + len(state.config.outside)
    query = request.url.query
    context.setdefault("nav", NAV_ITEMS.get(name))
    context.update(
        t=s,
        strings=s,
        size_text=s.size,
        script_strings=s.script_json,
        languages=LANGUAGES,
        here=local_path(request.url.path + (f"?{query}" if query else "")),
        theme=theme_of(request),
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


# --- the library and the rail's shelf (#389, D-664) -------------------------------------

SHELF_RECENT = 3  # recent documents on the shelf after Continue listening and the running job
CHIPS = {  # a document's state: its chip's look and icon (DESIGN.md "Chips"), never colour alone
    "making": ("making", "voices"),
    "analysing": ("making", "text"),
    "failed": ("failed", "alert"),
    "ready": ("ready", "check"),
    "cli": ("ready", "check"),
    "analysed": ("idle", "text"),
    "new": ("idle", "open"),
}


def _folders(state: ServerState, document: StoredDocument, saved: Path | None) -> tuple:
    return tuple(candidate_folders(document.folder, document.id, saved, state.config.output_folder))


def _percent(part: float | None) -> int | None:
    return None if part is None else int(100 * min(1.0, max(0.0, part)))


def _state_of(state: ServerState, document: StoredDocument) -> str:
    current = state.board.current
    if current is not None and current.document == document.id:
        return "analysing" if current.kind is JobKind.SCRIPT else "making"
    latest = next(
        (
            job
            for job in state.board.all()
            if job.document == document.id and job.kind in (JobKind.SCRIPT, JobKind.AUDIO)
        ),
        None,
    )
    if latest is not None and latest.state is JobState.FAILED:
        return "failed"
    if document.has_audio:
        return "ready"
    return "analysed" if document.report_file.is_file() else "new"


def _when_text(s: Strings, moment: datetime | None) -> str:
    if moment is None:
        return ""
    kind, value = when(moment, datetime.now(UTC))
    return value if kind == "date" else s(f"library.when_{kind}", value=value)  # ISO (D-290)


def _meta(s: Strings, authors: tuple[str, ...], pages: int | None, got: Heard | None) -> str:
    parts = []
    if authors:
        parts.append(", ".join(authors))
    if pages:
        parts.append(s("library.pages", n=pages))
    if got is not None and got.duration > 0:
        parts.append(length_text(got.duration, s("library.hours"), s("library.minutes")))
    return " · ".join(parts)


def _library_row(
    state: ServerState, s: Strings, document: StoredDocument, saved: Path | None
) -> dict[str, Any]:
    """One document as a row of the library's table."""
    about = read_about(document.folder)
    got = heard(document.folder, document.id, _folders(state, document, saved))
    key = _state_of(state, document)
    made = None
    if key in ("making", "analysing") and state.board.current is not None:
        made = _percent(progress_fraction(state.board.current.snapshot().get("progress")))
    return {
        "id": document.id,
        "title": about.title if about else document.name,
        "file": document.name,
        "find": search_text(
            about.title if about else document.name, about.authors if about else (), document.name
        ),
        "meta": _meta(s, about.authors if about else (), about.pages if about else None, got),
        "kind": document.source.suffix.removeprefix(".").lower(),
        "href": f"/documents/{document.id}/listen" if got else f"/documents/{document.id}",
        "state": key,
        "chip": CHIPS[key],
        "audio": got is not None,
        "listened": None if got is None else _percent(got.fraction),
        "made": made,
        "opened": _when_text(s, read_opened(document.folder)),
        "document": document,
    }


def _outside_row(s: Strings, job: Any) -> dict[str, Any]:
    """An audiobook the command line made (#154) as a row: read-only, no removal."""
    got = heard(job.work, job.document, (job.folder,))
    return {
        "id": job.id,
        "title": job.name,
        "file": job.name,
        "find": search_text(job.name, (), job.name),
        "meta": s("library.outside_meta", folder=str(job.folder)),
        "kind": PurePath(job.name).suffix.removeprefix(".").lower(),
        "href": f"/documents/{job.id}/listen",
        "state": "cli",
        "chip": CHIPS["cli"],
        "audio": got is not None,
        "listened": None if got is None else _percent(got.fraction),
        "made": None,
        "opened": "",
        "document": None,
    }


def _shelf(state: ServerState, s: Strings, here: str | None) -> dict[str, Any]:
    """The rail's "Reading and recent" (#389, D-664): first "Continue listening", where the
    person last stopped in an audiobook; then (the running job is drawn on its own) up to
    SHELF_RECENT documents opened most recently. `here` is the document in view."""
    documents = state.store.all()
    saved, _ = load_settings(state.config.config_file)
    places = [(d.folder, d.id, d.id, _folders(state, d, saved.output_folder)) for d in documents]
    places += [(j.work, j.document, j.id, (j.folder,)) for j in state.config.outside]
    titles = {d.id: (read_about(d.folder) or None) for d in documents}
    names = {d.id: d.name for d in documents} | {j.id: j.name for j in state.config.outside}

    def title(key: str) -> str:
        about = titles.get(key)
        return about.title if about else names[key]

    keep = None
    for work, document, key, folders in sorted(places, key=lambda p: -position_age(p[0])):
        if not position_age(work):
            break
        got = heard(work, document, folders)
        part = None if got is None else got.fraction
        if got is not None and got.resume and got.time is not None and part is not None:
            keep = {
                "id": key,
                "title": title(key),
                "href": f"/documents/{key}/listen#continue",
                "text": s("shelf.continue", time=clock(got.time)),
                "percent": _percent(part),
                "current": key == here,
            }
            break

    running = state.board.current
    shown = {keep["id"] if keep else None, running.document if running else None}

    def opened_at(document: StoredDocument) -> float:
        try:
            return (document.folder / OPENED).stat().st_mtime
        except OSError:
            return 0.0

    recent = []
    for document in sorted(documents, key=opened_at, reverse=True):
        if len(recent) == SHELF_RECENT or not opened_at(document):
            break
        if document.id in shown:
            continue
        key = _state_of(state, document)
        got = heard(document.folder, document.id, _folders(state, document, saved.output_folder))
        part = None if got is None else got.fraction
        if got is not None:
            text = s("library.listened", n=_percent(part)) if part else s("library.not_started")
        else:
            text = s(f"library.state_{key}")
        recent.append(
            {
                "id": document.id,
                "title": title(document.id),
                "href": f"/documents/{document.id}/listen" if got else f"/documents/{document.id}",
                "text": text,
                "percent": _percent(part) if got is not None else None,
                "current": document.id == here,
            }
        )
    return {"continue": keep, "recent": recent}


def _busy_document(state: ServerState) -> str | None:
    """The document this server's running job works on, if any (D-362)."""
    current = state.board.current
    return None if current is None else current.document


# --- the start page --------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def index(request: Request, state: State, q: str = "") -> HTMLResponse:
    s = strings_of(request)
    query = " ".join(q.split())[:200]  # the search (#416): every word in title, authors or file
    suffixes = supported_suffixes()
    documents = state.store.all()
    saved, _ = load_settings(state.config.config_file)
    rows = [_library_row(state, s, document, saved.output_folder) for document in documents]
    rows += [_outside_row(s, job) for job in state.config.outside]
    english = sum(f.size for f in download_plan().files if f.pack == ENGLISH)  # first run
    return _page(
        request,
        state,
        s,
        "index.html",
        documents=documents,
        rows=rows,
        query=query,
        shown={row["id"] for row in rows if matches(query, row["find"])},
        library_count=len(rows),
        removals={document.id: _removal(document) for document in documents},
        busy_document=_busy_document(state),
        voice_size=s.size(english),
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
    if kind == "move":  # a footnote read at its mark (#213)
        return s("check.said_moved", page=_edit_page(edit.get("to") or {}) or "?"), False
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
    except (OSError, ValueError, RecursionError):
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


# --- the paper header and the side column, shared by Prepare and Listen (#391) ----------


def _language_meta(report: Mapping[str, Any] | None, s: Strings) -> str | None:
    """The text's language and where it came from, short, for the paper header (D-499)."""
    primary = primary_language(_text_language(report))
    name = s(f"pack.{primary}") if primary in PACKS else _text_language(report)
    notes = {
        "setting": lambda: s("paper.language_setting", language=name),
        "file": lambda: s("paper.language_file", language=name),
        "text": lambda: s("paper.language_text", language=name),
        "fallback": lambda: s("paper.language_fallback", language=name),
    }
    note = notes.get(str((report or {}).get("language_source")))
    return note() if note else None


def paper_head(
    s: Strings,
    *,
    key: str,
    name: str,
    about: Any,
    report: Mapping[str, Any] | None,
    got: Heard | None,
    has_audio: bool,
    prepare: bool,
) -> dict[str, Any]:
    """The header of a document's pages (#391, DESIGN.md "Paper header"): its title, a
    meta line (authors, pages, the text's language, the audiobook's length) and the tabs
    Prepare and Listen; Listen is a link only when there is an audiobook."""
    meta = []
    if about is not None and about.authors:
        meta.append(", ".join(about.authors))
    if about is not None and about.pages:
        meta.append(s("library.pages", n=about.pages))
    language = _language_meta(report, s)
    if language:
        meta.append(language)
    if got is not None and got.duration > 0:
        length = length_text(got.duration, s("library.hours"), s("library.minutes"))
        meta.append(s("paper.audio", length=length))
    return {
        "id": key,
        "title": about.title if about is not None else name,
        "titled": about is not None,  # the file's own words: in the text's language
        "meta": meta,
        "listen": has_audio,
        "prepare": prepare,  # a command-line audiobook has no Prepare page (#154)
    }


# --- the document page as Prepare, with its audiobook job inline (#391) ------------------


def _latest_audio(state: ServerState, document_id: str) -> JobRecord | None:
    """The newest audio job of this server run for the document, running or ended."""
    return next(
        (
            job
            for job in state.board.all()
            if job.kind is JobKind.AUDIO and job.document == document_id
        ),
        None,
    )


def _stopped_in(progress: Mapping[str, Any]) -> tuple[str, int]:
    """Where an audio job stood when it ended (D-695): ("writing", n) once every chapter
    was spoken, ("chapter", n) in its n-th chapter, ("before", 0) before the first chunk.
    The last progress names the last finished chunk; when that chunk ended its chapter,
    the job was in the next one."""
    phase = progress.get("phase")
    chapters = int(progress.get("chapters") or 0)
    if phase in ("encoding", "done"):
        return "writing", chapters
    number = int(progress.get("chapter_number") or 0)
    if phase != "speaking" or not number:
        return "before", 0
    if progress.get("chapter_done"):
        if number >= chapters:
            return "writing", chapters
        return "chapter", number + 1
    return "chapter", number


def _phase_words(s: Strings, phase: Any) -> str:
    words = s.table.get(f"phase.{phase}") if phase else None
    return (words[:1].upper() + words[1:]) if words else s("job.state_running")


def _running_lines(s: Strings, progress: Mapping[str, Any]) -> dict[str, Any]:
    """The running card's words, drawn as the script draws them (`cardShown` in app.js)."""
    phase = progress.get("phase")
    where, number = _stopped_in(progress)  # while writing the files: every chapter is done
    chapters = int(progress.get("chapters") or 0)
    if phase == "speaking" and where == "chapter":
        head = s("making.speaking", n=number, total=chapters)
    else:
        head = _phase_words(s, phase)
    part = progress_fraction(progress)
    left = []
    if part is not None:
        left.append(s("js.percent", n=int(100 * part)))
    if phase == "speaking":
        seconds = progress.get("seconds_left")
        if seconds is None:
            left.append(s("js.measuring"))
        else:
            left.append(s("js.minutes_left", n=max(1, math.ceil(seconds / 60))))
    total = int(progress.get("chunks_total") or 0)
    done = int(progress.get("chunks_done") or 0)
    current = number if where == "chapter" else (chapters + 1 if where == "writing" else 0)
    return {
        "head": head,
        "left": " · ".join(left),
        "percent": None if part is None else int(100 * part),
        "sentences": s("js.sentences", done=done, n=total) if total else "",
        "segments": _segments(chapters, current),
    }


def _segments(chapters: int, current: int) -> list[str]:
    """One segment per chapter: done before `current`, now at it (counted from 1)."""
    return [
        "done" if n < current else ("now" if n == current else "") for n in range(1, chapters + 1)
    ]


# How long Cancel waits for the job to stop before it gives up and deletes nothing (#433 N3)
STOP_WAIT_MS = 120_000


def making_card(
    state: ServerState, s: Strings, job: JobRecord, document: StoredDocument
) -> dict[str, Any]:
    """The audiobook job as the card at the top of Prepare (#391, DESIGN.md "Job inline"):
    running, paused (Pause is today's cancel; the spoken sentences stay in the cache),
    failed or done. What it says is kept is read from the job's last progress (D-695) and
    the speech cache as it is now: a freed cache keeps nothing."""
    view = _job_view(state, job, s)
    progress = view.get("progress") or {}
    cache = document.speech_cache_bytes
    error = view.get("error") or {}
    card: dict[str, Any] = {
        "job": view,
        "state": view["state"],
        "cache": cache,
        "cache_text": s.size(cache),
        "exists": error.get("error") == "output-exists",
        "stop_wait": STOP_WAIT_MS,
        "resume": False,  # the again button reads Resume: a paused job
    }
    if view["state"] == "running":
        card.update(_running_lines(s, progress))
        return card
    where, number = _stopped_in(progress)
    chapters = int(progress.get("chapters") or 0)
    done = int(progress.get("chunks_done") or 0)
    total = int(progress.get("chunks_total") or 0)
    if view["state"] == "cancelled":
        if not cache and where == "before":
            # paused before the first sentence: nothing was spoken, nothing was freed
            card.update(
                title=s("making.paused"), kept=s("making.kept_none"), segments=[], resume=True
            )
        elif not cache:
            card.update(title=s("making.cancelled"), kept="", segments=[])
        else:
            title = s("making.paused_at", n=number) if where == "chapter" else s("making.paused")
            kept = s("making.kept_sentences", done=done, n=total) if total else ""
            card.update(title=title, kept=kept, segments=_segments(chapters, number), resume=True)
    elif view["state"] == "failed" and not card["exists"]:
        titles = {
            "chapter": lambda: s("making.failed_in", n=number),
            "writing": lambda: s("making.failed_writing"),
            "before": lambda: s("making.failed_before"),
        }
        if not cache:
            kept = s("job.cache_freed") if where != "before" else s("making.kept_none")
        elif where == "writing":
            kept = s("making.kept_all")
        elif where == "chapter" and number > 1:
            kept = s("making.kept_chapters", n=number - 1)
        elif where == "chapter":
            kept = s("making.kept_some")
        else:
            kept = s("making.kept_none")
        card.update(
            title=titles[where](),
            kept=kept,
            segments=_segments(chapters, chapters + 1 if where == "writing" else number),
        )
    elif view["state"] == "done":
        card.update(
            skipped=progress.get("skipped", []),
            folder=view["files"][0]["folder"] if view["files"] else "",
        )
    return card


def _side(
    s: Strings, document: StoredDocument, about: Any, report: Mapping[str, Any] | None
) -> dict[str, Any]:
    """The side column's "This document" (#391): file, pages, sentences, changes and the
    analysis files."""
    chapters = (report or {}).get("chapters", [])
    files = {}
    for path in document.analysis_files():
        files["script" if path.name.endswith(".script.txt") else path.suffix[1:]] = path.name
    return {
        "file": document.name,
        "pages": about.pages if about is not None else None,
        "sentences": sum(int(c.get("utterances") or 0) for c in chapters) if report else None,
        "changes": len((report or {}).get("edits", [])) if report else None,
        "files": files,
    }


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def document(request: Request, state: State, document_id: str) -> HTMLResponse:
    s = strings_of(request)
    found = state.store.get(document_id)
    if found is None:
        return _not_found(request, state, s, s("common.not_found_document", id=document_id))
    write_opened(found.folder, datetime.now(UTC))
    return _prepare(request, state, s, found, _latest_audio(state, found.id))


def _prepare(
    request: Request,
    state: State,
    s: Strings,
    found: StoredDocument,
    job: JobRecord | None,
    **extra: Any,
) -> HTMLResponse:
    """The Prepare page of `found`, with `job` (an audio job of it) as its card."""
    saved, _ = load_settings(state.config.config_file)
    report = _report(found)
    # the controls start from what the report on screen was made with (D-245, D-246)
    report_settings = (report or {}).get("settings") or {}
    switched_off = report_settings.get(
        "switched_off", sorted(str(c) for c in saved.switched_off or DEFAULT_SWITCHED_OFF)
    )
    chapters = (report or {}).get("chapters", [])
    edits = (report or {}).get("edits", [])
    spoken = sum(1 for e in edits if e.get("status") == "accepted" and e.get("spoken"))
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
    about = read_about(found.folder)
    got = heard(found.folder, found.id, _folders(state, found, saved.output_folder))
    # the language the report was made with ("" = automatic); a job made from this page
    # uses it, and it is not remembered for other documents (#212, D-521)
    language = str(report_settings.get("language", saved.language) or "")
    ordered, chosen = _chapter_order(chapters, report_settings.get("chapters"))
    shown = {
        "switched_off": sorted(switched_off),
        "chapters": chosen,
        "language": language,
    }
    return _page(
        request,
        state,
        s,
        "document.html",
        shelf_here=found.id,
        document=found,
        head=paper_head(
            s,
            key=found.id,
            name=found.name,
            about=about,
            report=report,
            got=got,
            has_audio=found.has_audio,
            prepare=True,
        ),
        side=_side(s, found, about, report),
        card=None if job is None else making_card(state, s, job, found),
        report=report,
        text_language=_text_language(report),
        language_note=_language_note(report, s),
        language_options=_language_options(language, s),
        analysing=analysing,
        analysis_job=current.id if analysing and current is not None else None,
        failed=failed,
        categories=_categories(report, switched_off, s),
        chapters=chapters,
        ordered_chapters=ordered,
        chosen_chapters=len(shown["chapters"]),
        edit_count=len(edits),
        heard=spoken,
        shown=json.dumps(shown),
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
        letter_paces=[
            {
                "id": pace,
                "label": s(f"voice.letter_pace_{pace}"),
                "selected": pace == saved.letter_pace,
            }
            for pace in LETTER_PACES
        ],
        preview_limit=PREVIEW_LIMIT,
        preview_text=preview_text(_voice_language(chosen_voice)),
        preview_text_language=primary_language(_voice_language(chosen_voice)),
        preview_texts={primary: preview_text(primary) for primary in DEFAULT_VOICES},
        output_folder=str(saved.output_folder or state.config.output_folder),
        subtitles=saved.subtitles,
        removal=_removal(found),
        busy=_busy_document(state) == found.id,
        **extra,
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
    document = None if found.document is None else state.store.get(found.document)
    if found.kind is JobKind.AUDIO and document is not None:
        # the audiobook job is shown where it was started: on Prepare (#391)
        return _prepare(request, state, s, document, found, nav="job", current_job=found.id)
    view = _job_view(state, found, s)
    return _page(
        request,
        state,
        s,
        "job.html",
        job=view,
        current_job=found.id,
        document=document,
    )


def _chapter_order(
    chapters: list[dict[str, Any]], recorded: Any
) -> tuple[list[dict[str, Any]], list[int]]:
    """The report's chapters in the order the page lists them, and the chosen ones in the
    order they are read (#119): the order the report was made with when it is not printed
    order (the chosen ones first, then the others as printed), else printed order."""
    chosen_set = {c.get("index") for c in chapters if c.get("selected")}
    printed = sorted(chapters, key=lambda c: c.get("index", 0))
    order = [n for n in recorded if n in chosen_set] if isinstance(recorded, list) else []
    order = list(dict.fromkeys(n for n in order if isinstance(n, int)))
    if order != sorted(order) and set(order) == chosen_set:
        by_index = {c.get("index"): c for c in printed}
        rest = [c for c in printed if c.get("index") not in set(order)]
        return [by_index[n] for n in order] + rest, order
    return printed, sorted(n for n in chosen_set if isinstance(n, int))


# --- the listen page (#78) ---------------------------------------------------------------


def _voice_name(voice_id: str) -> str:
    return next((v.name for v in VOICES if v.id == voice_id), voice_id)


def _voice_language(voice_id: str) -> str:
    return next((v.language for v in VOICES if v.id == voice_id), "en")


# the player's own speeds (#152): the playback rate, separate from the voice's speed
PLAYER_SPEEDS = (0.75, 1.0, 1.25, 1.5, 1.75, 2.0)


def _speeds(s: Strings) -> list[tuple[str, str]]:
    """Each speed's value for the select and its label in the page's language."""
    return [(f"{v:g}", s("listen.speed_value", value=s.number(v))) for v in PLAYER_SPEEDS]


def clock(seconds: float) -> str:
    """A time as a player shows it: 3:07, or 1:02:03 from an hour on."""
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _resume(view: Any, position: Position) -> dict[str, Any]:
    """The offer to continue where the person stopped (#153)."""
    return {
        "chapter": position.chapter,
        "number": position.chapter + 1,
        "title": view.chapters[position.chapter].title,
        "time": position.time,
        "clock": clock(position.time),
    }


@router.get("/documents/{document_id}/listen", response_class=HTMLResponse)
def listen(request: Request, state: State, document_id: str) -> HTMLResponse:
    """The player with read-along on the original text (D-294 to D-303)."""
    s = strings_of(request)
    found = state.listening(document_id)
    if found is None:
        return _not_found(request, state, s, s("common.not_found_document", id=document_id))
    if not found.outside:  # a command-line job's folders are read-only to the server (#154)
        write_opened(found.work, datetime.now(UTC))
    stored = None if found.outside else state.store.get(found.id)
    head = paper_head(
        s,
        key=found.id,
        name=found.name,
        about=None if found.outside else read_about(found.work),
        report=None if stored is None else _report(stored),
        got=heard(found.work, found.document, found.folders),
        has_audio=True,  # Listen is the page shown: its tab is the current one
        prepare=not found.outside,
    )
    try:
        view, located = player_for(found.work, found.document, found.folders)
    except PlayerError as error:
        return _page(
            request,
            state,
            s,
            "listen.html",
            shelf_here=found.id,
            document=found,
            head=head,
            view=None,
            problem=s(error.key, **error.values),
        )
    try:
        stamp = located.stamp
        position = read_position(found.work, found.document, stamp, located.readalong)
    except OSError:  # the read-along file went away since the checks: nothing to offer
        stamp, position = "", None
    return _page(
        request,
        state,
        s,
        "listen.html",
        shelf_here=found.id,
        document=found,
        head=head,
        view=view,
        voice=_voice_name(view.voice),
        speeds=_speeds(s),
        resume=None if position is None else _resume(view, position),
        # the stamp goes back with each save of the position (#153, review S1)
        data=data_block({**view.data(found.id), "audiobook": stamp}),
        problem=None,
        announce=announce_of(request),  # each sentence to screen readers, if switched on (#392)
        changes=_listen_changes(view, s),
        outline=_outline(view),
        total=clock(view.duration),
    )


def _listen_changes(view: PlayerView, s: Strings) -> list[dict[str, Any]]:
    """The Listen panel's Changes (#393): each category the audiobook was made with, read-only
    (D-665 conflict 3); its count only where the marks are drawn (D-704b)."""
    return [
        {
            "id": change.category,
            "label": s.table.get(f"category.{change.category}", change.category),
            "on": change.on,
            "count": change.count,
        }
        for change in view.changes
    ]


def _outline(view: PlayerView) -> list[dict[str, Any]]:
    """The chapters with where each starts, on the book's timeline and as a share of it (the
    dock's ticks, #393)."""
    total = view.duration if view.duration > 0 else 1.0
    return [
        {
            "title": chapter.title,
            "clock": clock(chapter.start),
            "at": f"{min(max(chapter.start / total, 0.0), 1.0) * 100:.3f}%",
        }
        for chapter in view.chapters
    ]


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
        # one panel per language pack with its own files (#390); one download for all (VA-03)
        packs=[
            {
                "language": language,
                "name": s(f"setup.pack_{language}"),
                "installed": language in there,
                "voices": _voice_cards(language, s),
                "missing": s.size(sum(f.size for f in missing if f.pack == language)),
                "files": [
                    {"target": f.target, "size": s.size(f.size), "licence": f.licence}
                    for f in plan.files
                    if f.pack == language
                ],
            }
            for language in PACKS
        ],
        total=s.size(plan.total_bytes),
        missing=s.size(sum(f.size for f in missing)),
        hosts=hosts_shown(plan.files, s),
        digest=plan_digest(plan),
    )


def _voice_cards(pack: str, s: Strings) -> list[dict[str, Any]]:
    """The voices of one pack as cards (#419): the default first, then by accent and name;
    each with the sample sentence of its language, the one the document page previews."""
    default = DEFAULT_VOICES.get(pack)
    voices = sorted(
        (v for v in VOICES if voice_pack(v.id) == pack),
        key=lambda v: (v.id != default, v.language, v.name),
    )
    cards = []
    for voice in voices:
        accent = s(f"accent.{voice.language}")
        if voice.gender == "female":
            about = s("setup.voice_female", accent=accent)
        else:
            about = s("setup.voice_male", accent=accent)
        about = about[:1].upper() + about[1:]  # German accents begin in lower case
        language = primary_language(voice.language)
        cards.append(
            {
                "id": voice.id,
                "name": voice.name,
                "about": f"{about} {s('voice.default')}" if voice.id == default else about,
                "text": preview_text(language),
                "language": language,
            }
        )
    return cards


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


# --- Settings (#388) -------------------------------------------------------------------


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, state: State) -> HTMLResponse:
    """Appearance, language and announcements (cookies, D-671) and the defaults for new
    audiobooks (the settings file, saved by the script through `PUT /api/v1/settings`).
    Showing the page never writes anything."""
    s = strings_of(request)
    saved, warnings = load_settings(state.config.config_file)
    return _page(
        request,
        state,
        s,
        "settings.html",
        themes=THEMES,
        announce=announce_of(request),
        output_folder=str(saved.output_folder or state.config.output_folder),
        speed=saved.speed,
        speed_text=s("voice.speed_value", value=s.number(saved.speed)),
        speed_min=MIN_SPEED,
        speed_max=MAX_SPEED,
        speed_step=SPEED_STEP,
        warnings=warnings,
    )


@router.get("/appearance")
def choose_appearance(
    request: Request, theme: str = "", announce: str = "", back: str = ""
) -> RedirectResponse:
    """Remembers the appearance (`system`, `light`, `dark`) or the sentence announcements
    (`on`, `off`) in their own cookies and goes back to the page the form was on, like the
    language switch (D-288, D-321, D-671): a GET form guarded like every page, setting
    nothing but these choices, sending the browser only to a path on this server."""
    response = RedirectResponse(local_path(back), 303)
    for cookie, chosen in (
        (THEME_COOKIE, known_theme(theme)),  # one of THEMES, never the request's text
        (ANNOUNCE_COOKIE, known_announce(announce)),  # one of ANNOUNCE
    ):
        if chosen is not None:
            response.set_cookie(
                cookie, chosen, max_age=COOKIE_AGE, path="/", samesite="strict", httponly=True
            )
    return response
