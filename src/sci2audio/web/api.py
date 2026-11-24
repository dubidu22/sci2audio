"""The JSON API under `/api/v1` (D-197): documents, jobs, settings and voices.

Every error answers `{"error": <kind>, "message": <words>}` (`models.ErrorOut`).
"""

from __future__ import annotations

import asyncio
import errno
import json
import os
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, File, Query, Request, Response, UploadFile
from fastapi import Path as Path_
from fastapi.responses import FileResponse, StreamingResponse

from sci2audio.app import JobBusyError, JobSettings, clean_work_folder, load_settings, save_settings
from sci2audio.app.capture_export import ExportFormat, export_captures
from sci2audio.app.settings import MAX_SPEED, MIN_SPEED
from sci2audio.core import Anchor, Capture, CaptureType, Document, Span, SpanError
from sci2audio.output import BookKind
from sci2audio.textprep import Category
from sci2audio.voices import (
    DEFAULT_VOICE,
    PACKS,
    VOICES,
    download_plan,
    missing_files,
    voice_pack,
)
from sci2audio.web import exports, models
from sci2audio.web.captures import (
    CapturedAgain,
    CaptureError,
    CaptureLimit,
    CaptureMissing,
    CapturesUnreadable,
    MarkersWaiting,
    NoteThere,
    TextRefused,
)
from sci2audio.web.captures import UndoExpired as CaptureUndoExpired
from sci2audio.web.documents import DocumentBusyError, RemoveError, StoredDocument, StoreError
from sci2audio.web.i18n import (
    COOKIE_AGE,
    PLAYER_SPEED_COOKIE,
    known_player_speed,
    player_speed_text,
    strings_of,
)
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
    locate,
    place,
    same_sentence,
)
from sci2audio.web.player import (
    Bounds,
    PlayerError,
    Position,
    audiobook_file,
    chapter_index,
    chapter_place,
    current_audiobook,
    load_document,
    recorded_folder,
    sentence_starts,
    whole_book,
)
from sci2audio.web.project import read_project
from sci2audio.web.removal import KEPT_LIMIT, AudiobookRemoved, Kept, carry_out, plan
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
# as error disclosure, alerts 90022 and 10023; #120)
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
    summary="Remove a document, its working folder and, unless kept, its audiobook files",
)
def remove_document(
    state: State,
    document_id: str,
    keep_audiobook: Annotated[
        bool,
        Query(description="true keeps the audiobook files; required, so every removal says"),
    ],
) -> models.RemovedOut:
    """Removes the copy of the file, its analysis, the speech cache and the records, and,
    unless `keep_audiobook`, the audiobook files sci2audio wrote into the project's own
    folders and which are unchanged since (#470, D-751); never anything else. Refused with
    409 while a job works on the document; 500 names what could not be removed, and the
    document then stays listed for another try."""
    document = _document(state, document_id)
    folder = recorded_folder(document.folder, document.id)

    def audiobook(found: StoredDocument) -> AudiobookRemoved:
        project = read_project(found.folder, found.id)
        if keep_audiobook:
            folders = [] if project is None else project.folders()
            return AudiobookRemoved(kept=tuple(Kept(f, "kept-by-choice", f) for f in folders))
        others = [
            other
            for d in state.store.all()
            if d.id != found.id and (other := read_project(d.folder, d.id)) is not None
        ]
        return carry_out(plan(project, state.protected_folders(), others))

    try:
        removed = state.store.remove(
            document_id, busy=lambda: _job_on(state, document_id), audiobook=audiobook
        )
    except DocumentBusyError as error:
        raise ApiError(409, "busy", str(error)) from error
    except RemoveError as error:
        raise ApiError(500, "remove-failed", str(error)) from error
    if removed is None:  # removed meanwhile by another request
        raise ApiError(404, "not-found", f"no document {document_id}; open the file again")
    state.board.forget(document_id)
    done = removed.audiobook or AudiobookRemoved()
    # whole folders first, so the limit cuts files, which the answer counts (R3)
    stayed = sorted(done.kept, key=lambda k: not k.whole)
    return models.RemovedOut(
        id=removed.id,
        name=removed.name,
        freed_bytes=removed.freed_bytes,
        audiobook_folder=None if folder is None else str(folder),
        deleted_files=done.files,
        deleted_bytes=done.bytes,
        kept=[
            models.KeptOut(path=str(k.path), reason=k.reason, folder=str(k.folder))
            for k in stayed[:KEPT_LIMIT]
        ],
        kept_more=max(0, len(stayed) - KEPT_LIMIT),
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
    """Each chapter with its state once the project has a chapter made (#726)."""
    chapters = _report(state, document_id).get("chapters", [])
    states = state.chapter_states(document_id)
    return [
        models.ChapterOut.model_validate(
            {**chapter, "state": None if states is None else states.of(chapter["index"])}
        )
        for chapter in chapters
    ]


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
    (#78, D-295): only names its record lists, only from the recorded folder, the project's
    own audiobook folders (D-749), the saved or the default output folder, and only once
    the read-along file there agrees with the record. Range requests answer 206, so the
    player can seek."""
    document = state.listening(document_id)
    if document is None:
        raise ApiError(404, "not-found", f"no document {document_id}")
    found = audiobook_file(document.work, document.document, name, document.folders)
    if found is None:
        raise ApiError(404, "not-found", f"{document.name} has no audiobook file {name!r}")
    return _file(found, download)


@router.post(
    "/documents/{document_id}/book",
    response_model=models.BookOut,
    responses={
        202: {"model": models.BookOut, "description": "the job that builds it"},
        **_errors(404, *BODY),
        409: {"model": models.BookErrorOut},
    },
    summary="The whole audiobook as one M4B or MP3: the file built before, or a job to build it",
)
def whole_audiobook(
    state: State, document_id: str, body: models.BookIn, response: Response
) -> models.BookOut:
    """The document's whole audiobook as one file of `kind` (#725), built from the chapters
    made, into the folder they are in. A file built before from exactly these chapters
    answers 200 with its name; otherwise a book job builds it (202). Chosen chapters not
    made yet answer 409 `missing-chapters` with their titles, unless `partial_ok`: then
    the file holds the chapters made and is named partial. The file is downloaded from
    `…/audiobook/{name}?download=true`."""
    document = _document(state, document_id)
    if state.board.current is not None:
        raise ApiError(409, "busy", "a job is running; wait until it has finished")
    listening = state.listening(document_id)
    if listening is None:
        raise ApiError(404, "not-found", f"no document {document_id}; open the file again")
    try:
        current = current_audiobook(listening.work, listening.document, listening.folders)
    except PlayerError as error:
        raise ApiError(404, "not-found", f"{document.name} has no audiobook yet") from error
    book = whole_book(listening.work, current, body.kind)
    if book.missing and not body.partial_ok:
        raise ApiError(
            409,
            "missing-chapters",
            f"these chapters are not made yet: {', '.join(book.missing)}",
            chapters=book.missing,
        )
    if book.name is not None:
        return models.BookOut(name=book.name, partial=bool(book.missing), job=None)
    if not book.buildable:
        raise ApiError(
            409,
            "not-buildable",
            "this audiobook was made by an earlier version of sci2audio; make it again to "
            "download it as one file",
        )
    work = state.book_work(document, current.located.folder, BookKind(body.kind), body.partial_ok)
    with state.store.unchanged(document.id) as still:
        if still is None:
            raise ApiError(404, "not-found", f"no document {document.id}; open the file again")
        try:
            job = state.board.start(
                JobKind.BOOK,
                document.id,
                {"kind": body.kind, "partial_ok": body.partial_ok},
                work,
                cancellable=True,
            )
        except BoardBusyError as error:
            raise ApiError(409, "busy", str(error)) from error
    response.status_code = 202
    return models.BookOut(name=None, partial=bool(book.missing), job=_job_out(job))


@router.get(
    "/documents/{document_id}/figures/{block}/{image}",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}, "image/jpeg": {}}, "description": "The image"},
        **_errors(404),
    },
    summary="A figure, table or formula as the file shows it, for the player",
)
def figure(
    state: State,
    document_id: str,
    block: Annotated[int, Path_(ge=0)],
    image: Annotated[int, Path_(ge=0)],
) -> Response:
    """Image `image` of placeholder block `block` (#293, D-771): a crop of the PDF page
    rendered in the PDF reader's child process, or an EPUB picture read from the book by its
    `ref`. The address holds only numbers: the region or the picture comes from the
    project's own `document.json`, which must name this document, and the file from its own
    copy. Not for a command-line job (its folders are read-only to the server, #154)."""
    stored = state.store.get(document_id)
    found = None
    if stored is not None:
        try:
            document = load_document(stored.folder)
        except PlayerError:
            document = None
        if document is not None:
            found = state.figures.image(
                document_id,
                document,
                block,
                image,
                stored.source,
                stored.folder,
                lambda: state.store.unchanged(document_id),
            )
    if found is None:
        raise ApiError(404, "not-found", f"no image {image} of block {block} in {document_id}")
    return Response(found.data, media_type=found.media_type)


@router.post(
    "/documents/{document_id}/position",
    status_code=204,
    responses=_errors(404, 409, 503),
    summary="Keep where the person stopped listening to the document's audiobook",
)
def save_position(state: State, document_id: str, given: models.PositionIn) -> None:
    """The player saves the position while it plays, so the next server run can offer to
    continue there (#153). It is kept in the working folder, stamped with the read-along
    file it is a time in. A position the audiobook does not have is refused (422), except
    one a frame's padding past a chapter's end, which is kept as that end (#779); one sent
    by a page drawn for another audiobook than the one there now is refused too (409: the
    audio job ran again while the page stayed open). An audiobook `sci2audio listen` opened
    keeps its position in its working folder too (#154): with the default folders that is
    the file's cache folder, shared with the interface's document of the same file, whose
    Listen page offers the position only for the same read-along file (#381)."""
    document = state.listening(document_id)
    if document is None:
        raise ApiError(404, "not-found", f"no document {document_id}")
    try:
        located = current_audiobook(document.work, document.document, document.folders).located
        stamp = located.stamp
    except (PlayerError, OSError) as error:
        raise ApiError(404, "not-found", f"{document.name} has no audiobook") from error
    if given.audiobook != stamp:
        raise ApiError(409, "other-audiobook", "the audiobook was made again since this page")
    bounds = Bounds.of(located.readalong)
    starts = bounds.starts
    chapter, time = given.chapter, given.time
    if given.index is not None and given.within is not None:
        # the page's own chapter (#726, D-909): a chapter added before it since the page
        # was drawn moved it, not the time inside it
        place = chapter_place(document.work, given.index)
        if place is None or place >= len(starts):
            raise ApiError(422, "no-such-time", "the audiobook has no such chapter")
        chapter, time = place, starts[place] + given.within
    # the place kept at the end of a chapter's file can lie a frame's padding past the
    # chapter's end (#779): it is kept as that end
    position = bounds.settled(Position(chapter, time))
    if not bounds.fits(position):
        raise ApiError(422, "no-such-time", "the audiobook has no such chapter and time")
    chapter, time = position.chapter, position.time
    index = chapter_index(document.work, chapter)
    if index is not None:
        position = Position(chapter, time, index, time - starts[chapter])
    try:
        state.positions.save(document.work, document.document, stamp, position)
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
    return _book_of(listening)


def _book_or_none(state: ServerState, document_id: str) -> tuple[Listening, _Book | None]:
    """The document, and its audiobook if it has one now (#398): a capture can be removed
    and put back also when its audiobook is gone, so the Captures page never lists one it
    can't remove."""
    listening = state.listening(document_id)
    if listening is None:
        raise ApiError(404, "not-found", f"no document {document_id}")
    try:
        return listening, _book_of(listening)
    except ApiError:
        return listening, None


def _document_or_none(listening: Listening) -> Document | None:
    try:
        return load_document(listening.work)
    except (PlayerError, OSError):
        return None


def _book_of(listening: Listening) -> _Book:
    try:
        located = current_audiobook(listening.work, listening.document, listening.folders).located
        document = load_document(listening.work)
        stamp = located.stamp
    except (PlayerError, OSError) as error:
        raise ApiError(404, "not-found", f"{listening.name} has no audiobook") from error
    spans = [chunk.span for chunk in located.readalong.chunks]
    return _Book(listening, document, spans, stamp, sentence_starts(located.readalong, document))


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


# ---- captures (#397, ADR-008) -----------------------------------------------------------------
# Marks, notes and quotes at the sentence the page reads, as the markers: the page names the
# chunk and the audiobook it was drawn for, and every change goes through the one locked
# read-modify-write of `CaptureBook.change`. A sentence holds one capture of each type.

_CAPTURE_STATUS = {
    CapturesUnreadable: 409,
    MarkersWaiting: 409,
    CapturedAgain: 409,
    NoteThere: 409,
    CaptureMissing: 404,
    CaptureUndoExpired: 410,
    CaptureLimit: 422,
    TextRefused: 422,
    CaptureError: 503,  # a file it would not read back: nothing is written
}


def _capture_chunk(book: _Book, capture: Capture) -> tuple[int | None, str]:
    """Where this audiobook shows the capture: its sentence's first chunk, and the state."""
    ((_, chunk, state),) = locate([capture], lambda c: c.anchor, book.document, book.spans)
    return (None if chunk is None else book.firsts[chunk]), state


def _capture_on(
    book: _Book, chunk: int | None, kind: CaptureType, captures: list[Capture]
) -> Capture | None:
    """The capture of `kind` shown on the sentence chunk `chunk` is a piece of, if any."""
    if chunk is None:
        return None
    first = book.firsts[chunk]
    of_kind = [c for c in captures if c.type is kind]
    return next(
        (
            capture
            for capture, at, _ in locate(of_kind, lambda c: c.anchor, book.document, book.spans)
            if at is not None and book.firsts[at] == first
        ),
        None,
    )


def _capture_out(book: _Book | None, capture: Capture) -> models.CaptureOut:
    chunk, state = (None, "no-audiobook") if book is None else _capture_chunk(book, capture)
    return models.CaptureOut(
        id=capture.id,
        type=capture.type.value,
        created=capture.created,
        changed=capture.changed,
        sentence=capture.anchor.text,
        text=capture.text,
        chunk=chunk,
        state=state,  # type: ignore[arg-type]
    )


def _capturing[T](change: Callable[[], T]) -> T:
    """Run a change of the captures file, with its refusals as answers."""
    try:
        return change()
    except CaptureError as error:
        status = next(s for kind, s in _CAPTURE_STATUS.items() if isinstance(error, kind))
        raise ApiError(status, error.kind, str(error)) from error
    except OSError as error:
        raise ApiError(
            503, "captures-not-saved", f"the captures could not be saved: {error.strerror}"
        ) from error


_CAPTURE_ID = Annotated[str, Path_(pattern=r"^[0-9a-f]{16}$", description="the capture's id")]


@router.post(
    "/documents/{document_id}/captures",
    status_code=201,
    responses={
        200: {"model": models.CaptureOut, "description": "the sentence's capture of that type"},
        **_errors(404, 409, 503),
    },
    summary="Capture a mark, a note or a quote at a sentence of the document's audiobook",
)
def add_capture(
    state: State, document_id: str, given: models.CaptureIn, response: Response
) -> models.CaptureOut:
    """A capture on the sentence the page reads: chunk `chunk` of the audiobook the page was
    drawn for (409 if it was made again since). A sentence that has a mark or a quote
    answers it unchanged (200), and the page toggles; a new note on a sentence that has one
    is refused (409 `note-exists`), so its text is never dropped."""
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
    kind = CaptureType(given.type)
    printed = anchor_of(book.document, span)
    anchor = Anchor(printed.block, printed.start, printed.end, printed.text)
    listening = book.listening
    capture, new = _capturing(
        lambda: state.captures.add(
            listening.work,
            listening.document,
            kind,
            anchor,
            given.text,
            lambda captures: _capture_on(book, given.chunk, kind, captures),
        )
    )
    if not new:
        response.status_code = 200
    return _capture_out(book, capture)


@router.patch(
    "/documents/{document_id}/captures/{capture_id}",
    responses=_errors(404, 409, 503),
    summary="Change a note's text",
)
def write_capture_note(
    state: State, document_id: str, capture_id: _CAPTURE_ID, given: models.CaptureTextIn
) -> models.CaptureOut:
    """Plain text, at most 4000 characters; a note without text is removed instead."""
    book = _book(state, document_id)
    listening = book.listening
    capture = _capturing(
        lambda: state.captures.write_note(
            listening.work, listening.document, capture_id, given.text
        )
    )
    return _capture_out(book, capture)


@router.delete(
    "/documents/{document_id}/captures/{capture_id}",
    responses=_errors(404, 409, 503),
    summary="Remove a capture",
)
def remove_capture(state: State, document_id: str, capture_id: _CAPTURE_ID) -> models.CaptureOut:
    """It leaves the file at once; this server keeps it for 10 minutes (the last 20 of the
    document) so the page's Undo can put it back (ADR-008 2.1 item 6). A document without
    an audiobook now answers it with state `no-audiobook`."""
    listening, book = _book_or_none(state, document_id)
    capture = _capturing(
        lambda: state.captures.remove(listening.work, listening.document, capture_id)
    )
    return _capture_out(book, capture)


@router.post(
    "/documents/{document_id}/captures/{capture_id}/restore",
    status_code=201,
    responses=_errors(404, 409, 410, 503),
    summary="Put back a capture removed in the last 10 minutes (Undo)",
)
def restore_capture(state: State, document_id: str, capture_id: _CAPTURE_ID) -> models.CaptureOut:
    """The capture comes back unchanged, from what this server kept: 410 once it no longer
    holds it (10 minutes, a restart, 20 later removals), 409 if its sentence has a capture of
    its type again."""
    listening, book = _book_or_none(state, document_id)

    def clash(capture: Capture, captures: list[Capture]) -> bool:
        if any(c.anchor == capture.anchor and c.type is capture.type for c in captures):
            return True
        if book is None:  # no audiobook to place it in: its sentence in the document
            of_kind = [c.anchor for c in captures if c.type is capture.type]
            return same_sentence(capture.anchor, of_kind, _document_or_none(listening))
        chunk, _ = _capture_chunk(book, capture)
        return _capture_on(book, chunk, capture.type, captures) is not None

    capture = _capturing(
        lambda: state.captures.restore(listening.work, listening.document, capture_id, clash)
    )
    return _capture_out(book, capture)


FULL_DISK = frozenset({errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)})


@router.post(
    "/captures/export",
    status_code=201,
    responses={
        **_errors(403, 404, 500, 507, *BODY),
        409: {"model": models.ExportExistsOut, "description": "a file of that name is there"},
    },
    summary="Save the captures as a Markdown, RIS or CSV file in a folder",
)
def export_captures_file(
    request: Request, state: State, given: models.CaptureExportIn
) -> models.CaptureExportOut:
    """The captures the Captures page shows (`type`, `document`), in reading order, as
    `<folder>/<name>.<format>`: the document's title for one document, else "Captures" in
    the page's language (#399, ADR-008 2.1 item 7). A file of that name is never replaced
    without `overwrite` (409 `export-exists`, nothing written); the file is written whole
    or not at all. No network call."""
    try:
        os.fsencode(given.folder)  # a lone surrogate from JSON names no path
    except UnicodeError as error:
        raise ApiError(422, "invalid", "the folder is not a path this system can name") from error
    folder = Path(given.folder)
    if not given.folder or not folder.is_absolute():
        raise ApiError(422, "export-folder-needed", f"the folder must be a full path: {folder}")
    if given.document and given.document not in exports.keys(state):
        raise ApiError(404, "not-found", f"no document {given.document}")
    documents = exports.exported(state, given.type, given.document)
    count = sum(len(document.captures) for document in documents)
    if not count:
        raise ApiError(422, "export-empty", "no captures are shown, so there is nothing to save")
    s = strings_of(request)
    form = ExportFormat(given.format)
    name = exports.stem(s, documents, bool(given.document))
    file = f"{name}.{form.value}"
    try:
        path = export_captures(
            folder,
            name,
            form,
            documents,
            overwrite=given.overwrite,
            labels=exports.labels(s),
        )
    except FileExistsError as error:
        raise ApiError(
            409,
            "export-exists",
            f"{file} is in {folder} already; it is replaced only when asked to",
            fields={"file": file, "folder": str(folder)},
        ) from error
    except (NotADirectoryError, FileNotFoundError) as error:
        raise ApiError(
            422, "export-folder-missing", f"{folder} is not a folder: {error.strerror}"
        ) from error
    except PermissionError as error:
        raise ApiError(
            403, "export-folder-refused", f"may not write into {folder}: {error.strerror}"
        ) from error
    except OSError as error:
        if error.errno in FULL_DISK:
            raise ApiError(507, "disk-full", f"could not save {file}: {error.strerror}") from error
        raise ApiError(
            500, "export-failed", f"could not save {file}: {error.strerror or error}"
        ) from error
    return models.CaptureExportOut(file=path.name, folder=str(folder), path=str(path), count=count)


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


def _updates(state: ServerState) -> models.UpdatesOut:
    found = state.updates.state()
    return models.UpdatesOut(
        enabled=found.enabled,
        checked_at=found.checked_at,
        outcome=None if found.outcome is None else found.outcome.value,
        latest=found.latest,
        release_url=state.updates.release_url(),
    )


@router.get(
    "/updates",
    response_model=models.UpdatesOut,
    responses=_errors(),
    summary="The update check",
)
def get_updates(state: State) -> models.UpdatesOut:
    return _updates(state)


@router.put(
    "/updates",
    response_model=models.UpdatesOut,
    responses=_errors(507, *BODY),
    summary="Turn the update check on or off",
    description="On: at most one request a day to the release source (#217); off by default.",
)
def put_updates(state: State, body: models.UpdatesIn) -> models.UpdatesOut:
    try:
        state.updates.set_enabled(body.enabled)
    except OSError as error:
        raise ApiError(
            507, "disk-full", f"could not save the choice: {error.strerror or error}"
        ) from error
    return _updates(state)


@router.put(
    "/player/speed",
    response_model=models.PlayerSpeed,
    responses=_errors(*BODY),
    summary="Keep the player's speed for the next Listen page",
)
def put_player_speed(body: models.PlayerSpeed, response: Response) -> models.PlayerSpeed:
    """The player keeps its playback speed in a cookie like the appearance (#651, D-671):
    a choice of the interface that grants nothing, set here so it stays HttpOnly."""
    speed = known_player_speed(repr(body.speed)) or 1.0
    response.set_cookie(
        PLAYER_SPEED_COOKIE,
        player_speed_text(speed),
        max_age=COOKIE_AGE,
        path="/",
        samesite="strict",
        httponly=True,
    )
    return models.PlayerSpeed(speed=speed)


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
        work = state.audio_work(document, settings, body.overwrite, body.keep_settings)
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
                keep_settings=kind is JobKind.AUDIO and body.keep_settings,
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
