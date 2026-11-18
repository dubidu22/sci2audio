"""The JSON API under `/api/v1` (D-197): documents, jobs, settings and voices.

Every error answers `{"error": <kind>, "message": <words>}` (`models.ErrorOut`).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, File, Query, Response, UploadFile
from fastapi import Path as Path_
from fastapi.responses import FileResponse, StreamingResponse

from sci2audio.app import JobBusyError, JobSettings, clean_work_folder, load_settings, save_settings
from sci2audio.app.settings import MAX_SPEED, MIN_SPEED
from sci2audio.core import Document, Span, SpanError
from sci2audio.textprep import Category
from sci2audio.voices import (
    DEFAULT_VOICE,
    PACKS,
    VOICES,
    download_plan,
    missing_files,
    voice_pack,
)
from sci2audio.web import models
from sci2audio.web.documents import DocumentBusyError, RemoveError, StoredDocument, StoreError
from sci2audio.web.jobs import BoardBusyError, JobKind, JobRecord, JobState
from sci2audio.web.markers import (
    MarkedAgain,
    Marker,
    MarkerError,
    MarkerLimit,
    MarkerMissing,
    MarkersBroken,
    NoteRefused,
    Placed,
    UndoExpired,
    anchor_of,
    place,
)
from sci2audio.web.player import (
    PlayerError,
    Position,
    audiobook_file,
    fits,
    load_document,
    locate,
    read_audio_record,
    recorded_folder,
    sentence_starts,
    write_position,
)
from sci2audio.web.state import ApiError, Listening, ServerState, state_of
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
    ".wav": "audio/wav",
    ".m4b": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".srt": "application/x-subrip; charset=utf-8",
    ".vtt": "text/vtt; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


# Our own words for answers whose standard phrase reads like a leaked server error: the
# OpenAPI document must never say "Internal Server Error" (the ZAP baseline scan flags it
# as error disclosure, alerts 90022 and 10023; #120 review round 3)
DESCRIPTIONS = {500: "sci2audio could not finish; the message says what is left to do"}


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    """The error answers of a route, for the OpenAPI document; every route can answer 400
    (a body or path that can't be read) and 422 (one that doesn't fit)."""
    answers: dict[int | str, dict[str, Any]] = {}
    for code in sorted({*codes, 400, 422}):
        answers[code] = {"model": models.ErrorOut}
        if code in DESCRIPTIONS:
            answers[code]["description"] = DESCRIPTIONS[code]
    return answers


BODY = (411, 413)  # from the size limit (limits.py)


State = Annotated[ServerState, state_of]
Download = Annotated[
    bool, Query(description="true: sent as an attachment to save, not shown (D-255)")
]
_FILE_ANSWERS: dict[int | str, dict[str, Any]] = {
    200: {"content": {"application/octet-stream": {}}, "description": "the file"},
    206: {"content": {"application/octet-stream": {}}, "description": "part of the file"},
}


# --- documents -------------------------------------------------------------------------


def _document_out(document: StoredDocument) -> models.DocumentOut:
    return models.DocumentOut(
        id=document.id,
        name=document.name,
        size=document.size,
        has_report=document.report_file.is_file(),
        has_audio=document.has_audio,
        speech_cache_bytes=document.speech_cache_bytes,
    )


def _document(state: ServerState, document_id: str) -> StoredDocument:
    document = state.store.get(document_id)
    if document is None:
        raise ApiError(404, "not-found", f"no document {document_id}; open the file again")
    return document


def _job_on(state: ServerState, document_id: str) -> str | None:
    """Why the document can't be changed now: this server's running job works on it."""
    job = state.board.current
    if job is not None and job.document == document_id:
        return f"job {job.id} is working on this document; wait for it"
    return None


def _not_in_use(state: ServerState, document_id: str) -> None:
    reason = _job_on(state, document_id)
    if reason is not None:
        raise ApiError(409, "busy", reason)


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


@router.delete(
    "/documents/{document_id}",
    response_model=models.RemovedOut,
    responses=_errors(404, 409, 500),
    summary="Remove a document and its whole working folder",
)
def remove_document(state: State, document_id: str) -> models.RemovedOut:
    """Removes the copy of the file, its analysis, the speech cache and the records; never
    anything in an output folder, so the audiobook stays (#120, D-353 to D-358). Refused
    with 409 while a job works on the document; 500 names what could not be removed, and
    the document then stays listed for another try."""
    document = _document(state, document_id)
    folder = recorded_folder(document.folder, document.id)
    try:
        removed = state.store.remove(document_id, busy=lambda: _job_on(state, document_id))
    except DocumentBusyError as error:
        raise ApiError(409, "busy", str(error)) from error
    except RemoveError as error:
        raise ApiError(500, "remove-failed", str(error)) from error
    if removed is None:  # removed meanwhile by another request
        raise ApiError(404, "not-found", f"no document {document_id}; open the file again")
    state.board.forget(document_id)
    return models.RemovedOut(
        id=removed.id,
        name=removed.name,
        freed_bytes=removed.freed_bytes,
        audiobook_folder=None if folder is None else str(folder),
    )


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
    except (OSError, ValueError, RecursionError) as error:
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


@router.get(
    "/documents/{document_id}/files/{name}",
    response_class=FileResponse,
    responses={**_FILE_ANSWERS, **_errors(404)},
    summary="A file of the latest pre-analysis: the script or the report",
)
def document_file(
    state: State, document_id: str, name: str, download: Download = False
) -> FileResponse:
    """The listening script, `report.json` or `report.md` of the latest pre-analysis, by
    name as written (D-255); they outlast the job that wrote them."""
    document = _document(state, document_id)
    found = next((path for path in document.analysis_files() if path.name == name), None)
    if found is None:
        raise ApiError(404, "not-found", f"{document.name} has no analysis file {name!r}")
    return _file(found, download)


@router.get(
    "/documents/{document_id}/audiobook/{name}",
    response_class=FileResponse,
    responses={**_FILE_ANSWERS, **_errors(404)},
    summary="A file of the document's latest audiobook: an MP3, the M4B or the read-along",
)
def audiobook(
    state: State, document_id: str, name: str, download: Download = False
) -> FileResponse:
    """A file the document's latest audio job wrote, by name as written, for the player
    (#78, D-295): only names its record lists, only from the recorded, the saved or the
    default output folder, and only once the read-along file there agrees with the
    record. Range requests answer 206, so the player can seek."""
    document = state.listening(document_id)
    if document is None:
        raise ApiError(404, "not-found", f"no document {document_id}")
    found = audiobook_file(document.work, document.document, name, document.folders)
    if found is None:
        raise ApiError(404, "not-found", f"{document.name} has no audiobook file {name!r}")
    return _file(found, download)


@router.post(
    "/documents/{document_id}/position",
    status_code=204,
    responses=_errors(404, 409, 503),
    summary="Keep where the person stopped listening to the document's audiobook",
)
def save_position(state: State, document_id: str, given: models.PositionIn) -> None:
    """The player saves the position while it plays, so the next server run can offer to
    continue there (#153). It is kept in the working folder, stamped with the read-along
    file it is a time in; a position the audiobook does not have is refused (422), and so
    is one sent by a page drawn for another audiobook than the one there now (409: the
    audio job ran again while the page stayed open). An audiobook `sci2audio listen` opened
    keeps its position in its own working folder too (#154)."""
    document = state.listening(document_id)
    if document is None:
        raise ApiError(404, "not-found", f"no document {document_id}")
    try:
        record = read_audio_record(document.work, document.document)
        located = locate(record, document.folders)
        stamp = located.stamp
    except (PlayerError, OSError) as error:
        raise ApiError(404, "not-found", f"{document.name} has no audiobook") from error
    if given.audiobook != stamp:
        raise ApiError(409, "other-audiobook", "the audiobook was made again since this page")
    position = Position(given.chapter, given.time)
    if not fits(located.readalong, position):
        raise ApiError(422, "no-such-time", "the audiobook has no such chapter and time")
    try:
        write_position(document.work, document.document, stamp, position)
    except OSError as error:
        raise ApiError(
            503, "not-saved", f"the listening position could not be saved: {error.strerror}"
        ) from error


# ---- markers (#474, D-723, D-728) ------------------------------------------------------------
# On the sentence the page reads: the page names the chunk and the audiobook it was drawn
# for, the server takes the sentence from the read-along and the document. Every change goes
# through the one locked read-modify-write of `MarkerBook.change` (D-728 ruling 2).

_MARKER_STATUS = {
    MarkersBroken: 409,
    MarkedAgain: 409,
    MarkerMissing: 404,
    UndoExpired: 410,
    MarkerLimit: 422,
    NoteRefused: 422,
    MarkerError: 503,  # a file it would not read back: nothing is written
}


@dataclass(frozen=True)
class _Book:
    """A document's audiobook as the markers see it."""

    listening: Listening
    document: Document
    spans: list[Span]
    stamp: str
    firsts: list[int]  # each chunk's sentence, by its first piece (#480)

    def placed(self, marker: Marker) -> Placed:
        """Where this audiobook shows the marker (it does not depend on the others)."""
        return place([marker], self.document, self.spans)[0]

    def sentence(self, chunk: int) -> Span:
        """The whole sentence chunk `chunk` is a piece of: from its first piece's start to its
        last piece's end (#480). A sentence that was not cut is its one chunk's span."""
        first = self.firsts[chunk]
        group = [n for n in range(first, len(self.spans)) if self.firsts[n] == first]
        return Span(self.spans[first].block, self.spans[first].start, self.spans[group[-1]].end)

    def on_sentence(self, chunk: int | None, markers: list[Marker]) -> Marker | None:
        """The marker shown on the sentence chunk `chunk` is a piece of, if one is: on any of
        its pieces (#480)."""
        if chunk is None:
            return None
        first = self.firsts[chunk]
        placed = place(markers, self.document, self.spans)
        return next(
            (p.marker for p in placed if p.chunk is not None and self.firsts[p.chunk] == first),
            None,
        )


def _book(state: ServerState, document_id: str) -> _Book:
    listening = state.listening(document_id)
    if listening is None:
        raise ApiError(404, "not-found", f"no document {document_id}")
    try:
        record = read_audio_record(listening.work, listening.document)
        located = locate(record, listening.folders)
        document = load_document(listening.work)
        stamp = located.stamp
    except (PlayerError, OSError) as error:
        raise ApiError(404, "not-found", f"{listening.name} has no audiobook") from error
    spans = [chunk.span for chunk in located.readalong.chunks]
    return _Book(listening, document, spans, stamp, sentence_starts(located.readalong))


def _marker_out(book: _Book, marker: Marker) -> models.MarkerOut:
    placed = book.placed(marker)
    return models.MarkerOut(
        id=marker.id,
        created=marker.created,
        changed=marker.changed,
        text=marker.anchor.text,
        note=marker.note,
        # the sentence by its first piece, as the page and the player name it (#520)
        chunk=None if placed.chunk is None else book.firsts[placed.chunk],
        state=placed.state,
    )


def _marking[T](change: Callable[[], T]) -> T:
    """Run a change of the markers file, with its refusals as answers."""
    try:
        return change()
    except MarkerError as error:
        status = next(s for kind, s in _MARKER_STATUS.items() if isinstance(error, kind))
        raise ApiError(status, error.kind, str(error)) from error
    except OSError as error:
        raise ApiError(
            503, "markers-not-saved", f"the markers could not be saved: {error.strerror}"
        ) from error


_MARKER_ERRORS = _errors(404, 409, 503)
_MARKER_ID = Annotated[str, Path_(pattern=r"^[0-9a-f]{16}$", description="the marker's id")]


@router.post(
    "/documents/{document_id}/markers",
    status_code=201,
    responses={
        200: {"model": models.MarkerOut, "description": "the sentence's marker"},
        **_MARKER_ERRORS,
    },
    summary="Set a marker on a sentence of the document's audiobook",
)
def set_marker(
    state: State, document_id: str, given: models.MarkerIn, response: Response
) -> models.MarkerOut:
    """A marker on the sentence the page reads: chunk `chunk` of the audiobook the page was
    drawn for (409 if it was made again since). A sentence that has a marker answers it
    (200); the page toggles."""
    book = _book(state, document_id)
    if given.audiobook != book.stamp:
        raise ApiError(409, "other-audiobook", "the audiobook was made again since this page")
    piece = book.spans[given.chunk] if given.chunk < len(book.spans) else None
    try:
        if piece is None or piece.start >= piece.end:
            raise SpanError("no sentence")
        span = book.sentence(given.chunk)
        book.document.check_span(span)
    except SpanError:
        raise ApiError(422, "no-such-sentence", "the audiobook has no such sentence") from None
    listening = book.listening
    marker, new = _marking(
        lambda: state.markers.set(
            listening.work,
            listening.document,
            anchor_of(book.document, span),
            lambda markers: book.on_sentence(given.chunk, markers),
        )
    )
    if not new:
        response.status_code = 200
    return _marker_out(book, marker)


@router.patch(
    "/documents/{document_id}/markers/{marker_id}",
    responses=_MARKER_ERRORS,
    summary="Change a marker's note",
)
def note_marker(
    state: State, document_id: str, marker_id: _MARKER_ID, given: models.NoteIn
) -> models.MarkerOut:
    """The note is plain text, at most 4000 characters; "" leaves the marker without one."""
    book = _book(state, document_id)
    listening = book.listening
    marker = _marking(
        lambda: state.markers.note(listening.work, listening.document, marker_id, given.note)
    )
    return _marker_out(book, marker)


@router.delete(
    "/documents/{document_id}/markers/{marker_id}",
    responses=_MARKER_ERRORS,
    summary="Remove a marker and its note",
)
def remove_marker(state: State, document_id: str, marker_id: _MARKER_ID) -> models.MarkerOut:
    """It leaves the file at once; this server keeps it for 10 minutes (the last 20 of the
    document) so the page's Undo can put it back (D-723 ruling 1)."""
    book = _book(state, document_id)
    listening = book.listening
    marker = _marking(lambda: state.markers.remove(listening.work, listening.document, marker_id))
    return _marker_out(book, marker)


@router.post(
    "/documents/{document_id}/markers/{marker_id}/restore",
    status_code=201,
    responses=_errors(404, 409, 410, 503),
    summary="Put back a marker removed in the last 10 minutes (Undo)",
)
def restore_marker(state: State, document_id: str, marker_id: _MARKER_ID) -> models.MarkerOut:
    """The marker comes back unchanged, from what this server kept: 410 once it no longer
    holds it (10 minutes, a restart, 20 later removals), 409 if its sentence has a marker
    again."""
    book = _book(state, document_id)
    listening = book.listening

    def clash(marker: Marker, markers: list[Marker]) -> bool:
        if any(other.anchor == marker.anchor for other in markers):
            return True
        return book.on_sentence(book.placed(marker).chunk, markers) is not None

    marker = _marking(
        lambda: state.markers.restore(listening.work, listening.document, marker_id, clash)
    )
    return _marker_out(book, marker)


@router.delete(
    "/documents/{document_id}/chunks",
    status_code=204,
    responses=_errors(404, 409),
    summary="Remove the kept speech chunks of a document",
)
def clean_chunks(state: State, document_id: str) -> None:
    """The next audio job of this document speaks everything again (D-158, D-209)."""
    document = _document(state, document_id)
    _not_in_use(state, document_id)
    try:
        clean_work_folder(document.folder)
    except JobBusyError as error:  # another process holds the working folder
        raise ApiError(409, "busy", str(error)) from error
    except OSError as error:
        raise ApiError(500, "clean-failed", f"could not remove the chunks: {error}") from error


# --- settings --------------------------------------------------------------------------


def _settings_model(settings: JobSettings) -> models.SettingsModel:
    return models.SettingsModel(
        language=settings.language,
        switched_off=sorted(settings.switched_off),
        voice=settings.voice,
        speed=settings.speed,
        letter_pace=cast(models.LetterPace, settings.letter_pace),
        subtitles=settings.subtitles,
        output_folder=None if settings.output_folder is None else str(settings.output_folder),
    )


def _folder(text: str | None) -> Path | None:
    if text is None or text == "":
        return None
    if "\0" in text:
        raise ApiError(422, "invalid", "output_folder must not contain a NUL character")
    folder = Path(text)
    if not folder.is_absolute():
        raise ApiError(422, "invalid", f"output_folder must be a full path, got {text!r}")
    return folder


def _voice(voice: str) -> str:
    if voice and voice not in {info.id for info in VOICES}:
        raise ApiError(422, "invalid", f"unknown voice {voice!r}")
    return voice


def _job_settings(**fields: Any) -> JobSettings:
    try:
        return JobSettings(**fields)
    except (TypeError, ValueError) as error:
        raise ApiError(422, "invalid", str(error)) from error


def _voice_list() -> list[models.VoiceOut]:
    return [
        models.VoiceOut(id=v.id, name=v.name, language=v.language, gender=v.gender) for v in VOICES
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
        letter_pace=body.letter_pace,
        subtitles=body.subtitles,
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
        chapters=None if given.chapters is None else tuple(given.chapters),
        voice=saved.voice if given.voice is None else _voice(given.voice),
        speed=saved.speed if given.speed is None else given.speed,
        letter_pace=saved.letter_pace if given.letter_pace is None else given.letter_pace,
        subtitles=saved.subtitles if given.subtitles is None else given.subtitles,
        output_folder=saved.output_folder
        if given.output_folder is None
        else _folder(given.output_folder),
    )


def _settings_data(settings: JobSettings) -> dict[str, Any]:
    return {
        "language": settings.language,
        "switched_off": sorted(str(c) for c in settings.switched_off),
        "chapters": None if settings.chapters is None else list(settings.chapters),
        "voice": settings.voice,
        "speed": settings.speed,
        "letter_pace": settings.letter_pace,
        "subtitles": settings.subtitles,
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
    responses=_errors(404, 409, *BODY),
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
    # the check and the start are one step against a removal (D-356): either the job runs
    # before the removal looks for one (409 there), or the removal began and this is 404
    with state.store.unchanged(document.id) as still:
        if still is None:
            raise ApiError(404, "not-found", f"no document {document.id}; open the file again")
        try:
            job = state.board.start(
                kind,
                document.id,
                _settings_data(settings),
                work,
                cancellable=kind is JobKind.AUDIO,
                overwrite=kind is JobKind.AUDIO and body.overwrite,
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
    responses={**_FILE_ANSWERS, **_errors(404)},
    summary="A file the job wrote",
)
def job_file(state: State, job_id: str, name: str, download: Download = False) -> FileResponse:
    job = _job(state, job_id)
    file = job.file(name)
    if file is None or not file.path.is_file():
        raise ApiError(404, "not-found", f"job {job_id} wrote no file {name!r}")
    return _file(file.path, download)


def _file(path: Path, download: bool) -> FileResponse:
    """A file as the browser shows it (`inline`) or saves it (`download`, D-255)."""
    media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path, media_type=media_type, filename=path.name, content_disposition_type=disposition
    )


# --- voices ----------------------------------------------------------------------------


def plan_hosts(urls: list[str]) -> list[str]:
    """The hosts the voice download talks to, then where they redirect (D-141)."""
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
        installed_languages=[
            p for p in PACKS if p in {f.pack for f in plan.files} - {f.pack for f in missing}
        ],
        plan=models.PlanOut(
            digest=plan_digest(plan),
            total_bytes=plan.total_bytes,
            missing_bytes=sum(file.size for file in missing),
            licences=list(plan.licences),
            hosts=plan_hosts([file.url for file in plan.files]),
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


@router.post(
    "/voices/preview",
    status_code=202,
    response_model=models.JobOut,
    responses=_errors(409, *BODY),
    summary="Speak a preview sentence with one voice at one speed",
)
def preview_voice(state: State, body: models.PreviewIn) -> models.JobOut:
    """A preview job (D-249): its one file is the WAV to play. The voice stays loaded
    afterwards for the next preview and the audio job (D-250)."""
    text = " ".join(body.text.split())
    if not text:
        raise ApiError(422, "invalid", "text: the preview sentence is empty")
    settings = _job_settings(
        voice=_voice(body.voice), speed=body.speed, letter_pace=body.letter_pace
    )
    pack = voice_pack(settings.voice or DEFAULT_VOICE)
    if any(f.pack == pack for f in missing_files(state.config.models_dir)):
        raise ApiError(409, "voice-missing", "the voice is not installed yet; download it first")
    work = state.preview_work(text, settings.voice, settings.speed, settings.letter_speed)
    try:
        job = state.board.start(
            JobKind.PREVIEW,
            None,
            {
                "voice": settings.voice,
                "speed": settings.speed,
                "letter_pace": settings.letter_pace,
            },
            work,
            cancellable=False,
        )
    except BoardBusyError as error:
        raise ApiError(409, "busy", str(error)) from error
    return _job_out(job)
