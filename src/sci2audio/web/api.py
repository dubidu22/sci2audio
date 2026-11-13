"""The JSON API under `/api/v1` (D-197): documents, jobs, settings and voices.

Every error answers `{"error": <kind>, "message": <words>}` (`models.ErrorOut`).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from sci2audio.app import JobSettings, load_settings, save_settings
from sci2audio.app.settings import MAX_SPEED, MIN_SPEED
from sci2audio.textprep import Category
from sci2audio.voices import DEFAULT_VOICE, ENGLISH_VOICES, download_plan, missing_files
from sci2audio.web import models
from sci2audio.web.documents import StoredDocument, StoreError
from sci2audio.web.jobs import BoardBusyError, JobKind, JobRecord, JobState
from sci2audio.web.state import ApiError, ServerState, state_of
from sci2audio.web.tasks import plan_digest, script_work, voices_work

router = APIRouter(prefix="/api/v1")

KEEP_ALIVE = 15.0  # seconds between comment lines on an idle event stream (D-201)
POLL = 0.1  # seconds between looks at a job's progress
# hosts the voice download talks to, with where they redirect (D-141)
REDIRECTS = {
    "huggingface.co": "Hugging Face's download servers (its CDN and LFS/Xet storage)",
    "github.com": "objects.githubusercontent.com (GitHub's download server)",
}
MEDIA_TYPES = {
    ".m4b": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    """The error answers of a route, for the OpenAPI document; every route can answer 400
    (a body or path that can't be read) and 422 (one that doesn't fit)."""
    return {code: {"model": models.ErrorOut} for code in sorted({*codes, 400, 422})}


BODY = (411, 413)  # from the size limit (limits.py)


State = Annotated[ServerState, state_of]


# --- documents -------------------------------------------------------------------------


def _document_out(document: StoredDocument) -> models.DocumentOut:
    try:
        size = document.source.stat().st_size
    except OSError:
        size = 0
    return models.DocumentOut(
        id=document.id,
        name=document.name,
        size=size,
        has_report=document.report_file.is_file(),
        has_audio=document.has_audio,
    )


def _document(state: ServerState, document_id: str) -> StoredDocument:
    document = state.store.get(document_id)
    if document is None:
        raise ApiError(404, "not-found", f"no document {document_id}; open the file again")
    return document


def _not_in_use(state: ServerState, document_id: str) -> None:
    job = state.board.current
    if job is not None and job.document == document_id:
        raise ApiError(409, "busy", f"job {job.id} is working on this document; wait for it")


def _stored(state: ServerState, store: Any) -> models.DocumentOut:
    try:
        document = store()
    except StoreError as error:
        status = {"unsupported-file": 415, "too-large": 413, "disk-full": 507}.get(error.kind, 500)
        raise ApiError(status, error.kind, str(error)) from error
    return _document_out(document)


@router.post(
    "/documents",
    status_code=201,
    response_model=models.DocumentOut,
    responses=_errors(409, 415, 507, *BODY),
    summary="Open a file",
)
def open_file(state: State, file: Annotated[UploadFile, File()]) -> models.DocumentOut:
    name = file.filename or ""
    current = state.board.current
    in_use = None if current is None else current.document
    return _stored(state, lambda: state.store.store(name, file.file, in_use=in_use))


@router.post(
    "/documents/text",
    status_code=201,
    response_model=models.DocumentOut,
    responses=_errors(409, 415, 507, *BODY),
    summary="Open pasted text",
)
def open_text(state: State, body: models.TextIn) -> models.DocumentOut:
    current = state.board.current
    in_use = None if current is None else current.document
    return _stored(state, lambda: state.store.store_text(body.text, body.name, in_use=in_use))


@router.get(
    "/documents",
    response_model=list[models.DocumentOut],
    responses=_errors(),
    summary="Opened documents",
)
def list_documents(state: State) -> list[models.DocumentOut]:
    return [_document_out(document) for document in state.store.all()]


@router.get(
    "/documents/{document_id}",
    response_model=models.DocumentOut,
    responses=_errors(404),
    summary="One document",
)
def get_document(state: State, document_id: str) -> models.DocumentOut:
    return _document_out(_document(state, document_id))


def _report(state: ServerState, document_id: str) -> dict[str, Any]:
    document = _document(state, document_id)
    try:
        data = json.loads(document.report_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ApiError(
            404, "no-report", f"{document.name} has no pre-analysis yet; start a script job"
        ) from error
    if not isinstance(data, dict):
        raise ApiError(404, "no-report", f"{document.name} has no readable pre-analysis")
    return data


@router.get(
    "/documents/{document_id}/report",
    response_model=dict[str, Any],
    responses=_errors(404),
    summary="The latest pre-analysis report (sci2audio-report v1)",
)
def get_report(state: State, document_id: str) -> dict[str, Any]:
    return _report(state, document_id)


@router.get(
    "/documents/{document_id}/chapters",
    response_model=list[models.ChapterOut],
    responses=_errors(404),
    summary="The chapters of the latest pre-analysis",
)
def get_chapters(state: State, document_id: str) -> list[models.ChapterOut]:
    chapters = _report(state, document_id).get("chapters", [])
    return [models.ChapterOut.model_validate(chapter) for chapter in chapters]


# --- settings --------------------------------------------------------------------------


def _settings_model(settings: JobSettings) -> models.SettingsModel:
    return models.SettingsModel(
        language=settings.language,
        switched_off=sorted(settings.switched_off),
        voice=settings.voice,
        speed=settings.speed,
        output_folder=None if settings.output_folder is None else str(settings.output_folder),
    )


def _folder(text: str | None) -> Path | None:
    if text is None or text == "":
        return None
    folder = Path(text)
    if not folder.is_absolute():
        raise ApiError(422, "invalid", f"output_folder must be a full path, got {text!r}")
    return folder


def _voice(voice: str) -> str:
    if voice and voice not in {info.id for info in ENGLISH_VOICES}:
        raise ApiError(422, "invalid", f"unknown voice {voice!r}")
    return voice


def _job_settings(**fields: Any) -> JobSettings:
    try:
        return JobSettings(**fields)
    except (TypeError, ValueError) as error:
        raise ApiError(422, "invalid", str(error)) from error


def _voice_list() -> list[models.VoiceOut]:
    return [
        models.VoiceOut(id=v.id, name=v.name, language=v.language, gender=v.gender)
        for v in ENGLISH_VOICES
    ]


@router.get(
    "/settings",
    response_model=models.SettingsOut,
    responses=_errors(),
    summary="The saved settings",
)
def get_settings(state: State) -> models.SettingsOut:
    settings, warnings = load_settings(state.config.config_file)
    return models.SettingsOut(
        settings=_settings_model(settings),
        warnings=warnings,
        categories=[
            models.CategoryOut(id=str(c), label=c.label, on_by_default=c.on_by_default)
            for c in Category
        ],
        speed=models.SpeedRange(min=MIN_SPEED, max=MAX_SPEED),
        voices=_voice_list(),
        default_voice=DEFAULT_VOICE,
        default_output_folder=str(state.config.output_folder),
    )


@router.put(
    "/settings",
    response_model=models.SettingsModel,
    responses=_errors(507, *BODY),
    summary="Save the settings",
)
def put_settings(state: State, body: models.SettingsModel) -> models.SettingsModel:
    settings = _job_settings(
        language=body.language,
        switched_off=frozenset(body.switched_off),
        voice=_voice(body.voice),
        speed=body.speed,
        output_folder=_folder(body.output_folder),
    )
    try:
        save_settings(settings, state.config.config_file)
    except OSError as error:
        raise ApiError(
            507, "disk-full", f"could not save the settings: {error.strerror}"
        ) from error
    return _settings_model(settings)


# --- jobs ------------------------------------------------------------------------------


def _merged(saved: JobSettings, given: models.JobSettingsIn) -> JobSettings:
    """The saved settings with the job's own choices on top (D-200)."""
    return _job_settings(
        language=saved.language if given.language is None else given.language,
        switched_off=saved.switched_off
        if given.switched_off is None
        else frozenset(given.switched_off),
        chapters=None if given.chapters is None else frozenset(given.chapters),
        voice=saved.voice if given.voice is None else _voice(given.voice),
        speed=saved.speed if given.speed is None else given.speed,
        output_folder=saved.output_folder
        if given.output_folder is None
        else _folder(given.output_folder),
    )


def _settings_data(settings: JobSettings) -> dict[str, Any]:
    return {
        "language": settings.language,
        "switched_off": sorted(str(c) for c in settings.switched_off),
        "chapters": None if settings.chapters is None else sorted(settings.chapters),
        "voice": settings.voice,
        "speed": settings.speed,
        "output_folder": None if settings.output_folder is None else str(settings.output_folder),
    }


def _job(state: ServerState, job_id: str) -> JobRecord:
    job = state.board.get(job_id)
    if job is None:
        raise ApiError(404, "not-found", f"no job {job_id} in this run of sci2audio")
    return job


def _job_out(job: JobRecord) -> models.JobOut:
    return models.JobOut.model_validate(job.snapshot())


@router.post(
    "/jobs",
    status_code=202,
    response_model=models.JobOut,
    responses=_errors(404, 409, 501, *BODY),
    summary="Start a job",
)
def start_job(state: State, body: models.JobIn) -> models.JobOut:
    document = _document(state, body.document)
    saved, _ = load_settings(state.config.config_file)
    settings = _merged(saved, body.settings)
    if body.kind == "audio":
        work = state.audio_work(document, settings, body.overwrite)
        kind = JobKind.AUDIO
    else:
        work = script_work(state.runner, document, settings)
        kind = JobKind.SCRIPT
    try:
        job = state.board.start(
            kind, document.id, _settings_data(settings), work, cancellable=kind is JobKind.AUDIO
        )
    except BoardBusyError as error:
        raise ApiError(409, "busy", str(error)) from error
    return _job_out(job)


@router.get(
    "/jobs", response_model=list[models.JobOut], responses=_errors(), summary="Jobs of this run"
)
def list_jobs(state: State) -> list[models.JobOut]:
    return [_job_out(job) for job in state.board.all()]


@router.get(
    "/jobs/{job_id}", response_model=models.JobOut, responses=_errors(404), summary="One job"
)
def get_job(state: State, job_id: str) -> models.JobOut:
    return _job_out(_job(state, job_id))


@router.post(
    "/jobs/{job_id}/cancel",
    status_code=202,
    response_model=models.JobOut,
    responses=_errors(404, 409),
    summary="Ask a job to stop",
)
def cancel_job(state: State, job_id: str) -> models.JobOut:
    job = _job(state, job_id)
    if job.state is not JobState.RUNNING:
        raise ApiError(409, "finished", f"job {job_id} has already ended")
    if not job.cancellable:
        raise ApiError(
            409, "not-cancellable", "a pre-analysis takes seconds and can't be stopped; wait"
        )
    state.board.cancel(job_id)
    return _job_out(job)


_JOB = {"$ref": "#/components/schemas/JobOut"}
# one event of the stream (Open API 3.1: the schema of an event stream describes one event)
EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["event", "data"],
    "properties": {
        "event": {"enum": ["snapshot", "progress", "end"]},
        "data": {"type": "string", "contentMediaType": "application/json"},
    },
    "if": {"properties": {"event": {"const": "progress"}}},
    "then": {
        "properties": {"data": {"contentSchema": {"type": ["object", "null"]}}},
    },
    "else": {"properties": {"data": {"contentSchema": _JOB}}},
}


def _event(name: str, data: Any) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


@router.get(
    "/jobs/{job_id}/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {"schema": EVENT_SCHEMA}},
            "description": "snapshot, then progress events, then one end event (D-201)",
        },
        **_errors(404),
    },
    summary="Progress as server-sent events",
)
async def job_events(state: State, job_id: str) -> StreamingResponse:
    job = _job(state, job_id)

    async def stream() -> AsyncIterator[bytes]:
        sent = job.version
        snapshot = job.snapshot()
        yield _event("snapshot", snapshot)
        beat = time.monotonic()
        while True:
            if snapshot["state"] != JobState.RUNNING:
                yield _event("end", snapshot)
                return
            if state.stopping.is_set():
                return
            await asyncio.sleep(POLL)
            if job.version != sent:
                sent = job.version
                snapshot = job.snapshot()
                if snapshot["state"] == JobState.RUNNING:
                    yield _event("progress", snapshot["progress"])
                beat = time.monotonic()
            elif time.monotonic() - beat >= KEEP_ALIVE:
                yield b": keep-alive\n\n"
                beat = time.monotonic()

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"x-accel-buffering": "no"}
    )


@router.get(
    "/jobs/{job_id}/files/{name}",
    response_class=FileResponse,
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "the file"},
        206: {"content": {"application/octet-stream": {}}, "description": "part of the file"},
        **_errors(404),
    },
    summary="A file the job wrote",
)
def job_file(state: State, job_id: str, name: str) -> FileResponse:
    job = _job(state, job_id)
    file = job.file(name)
    if file is None or not file.path.is_file():
        raise ApiError(404, "not-found", f"job {job_id} wrote no file {name!r}")
    media_type = MEDIA_TYPES.get(file.path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        file.path, media_type=media_type, filename=file.name, content_disposition_type="inline"
    )


# --- voices ----------------------------------------------------------------------------


def _hosts(urls: list[str]) -> list[str]:
    hosts = sorted({urlsplit(url).hostname or "" for url in urls} - {""})
    return [*hosts, *(REDIRECTS[host] for host in hosts if host in REDIRECTS)]


@router.get(
    "/voices",
    response_model=models.VoicesOut,
    responses=_errors(),
    summary="Voices and the voice download",
)
def get_voices(state: State) -> models.VoicesOut:
    plan = download_plan()
    missing = missing_files(state.config.models_dir)
    return models.VoicesOut(
        voices=_voice_list(),
        default_voice=DEFAULT_VOICE,
        installed=not missing,
        plan=models.PlanOut(
            digest=plan_digest(plan),
            total_bytes=plan.total_bytes,
            missing_bytes=sum(file.size for file in missing),
            licences=list(plan.licences),
            hosts=_hosts([file.url for file in plan.files]),
            files=[
                models.PlanFileOut(
                    url=f.url, target=f.target, size=f.size, sha256=f.sha256, licence=f.licence
                )
                for f in plan.files
            ],
        ),
    )


@router.post(
    "/voices/download",
    status_code=202,
    response_model=models.JobOut,
    responses=_errors(409, *BODY),
    summary="Download the voice files, with the person's consent",
)
def download_voices(state: State, body: models.DownloadIn) -> models.JobOut:
    if not body.consent:
        raise ApiError(422, "no-consent", "the voice download needs the person's consent")
    if body.plan != plan_digest(download_plan()):
        raise ApiError(409, "stale-plan", "the download changed since it was shown; show it again")
    work = voices_work(state.config.models_dir, state.fetch)
    try:
        job = state.board.start(JobKind.VOICES, None, None, work, cancellable=True)
    except BoardBusyError as error:
        raise ApiError(409, "busy", str(error)) from error
    return _job_out(job)
