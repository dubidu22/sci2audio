"""Captures saved as files from the Captures page (#399, ADR-008 2.1 item 7, D-850):
Markdown for Obsidian, RIS for Zotero and the CSV, each into a folder the person types.
`app.capture_export` writes the file, whole or not at all, and never over an existing one
unless the person said yes; this module only gathers what goes in.

What goes in is what the page shows: every document in the Library's order, filtered by
type and document as the page's filters are. A document's title is the Library's. Its
captures are put in reading order by where their sentence is found in the document now,
with the finder the pages place captures with, so a sentence the layout has moved is
still in its place; those not found follow in the order they were captured, and have no
page. On one sentence the dock's order holds (note, quote, mark), as on the page.

A document whose captures file can't be read has nothing that could be saved; the page
names it, and it is left out here and left as it is.
"""

from __future__ import annotations

from sci2audio.app.capture_export import (
    ExportedCapture,
    ExportedDocument,
    ExportLabels,
    PageFinder,
    Reference,
    file_stem,
    reference_of,
)
from sci2audio.core import Capture
from sci2audio.web.captures import CapturesUnreadable, MarkersWaiting
from sci2audio.web.i18n import Strings
from sci2audio.web.library import read_about
from sci2audio.web.markers import finder
from sci2audio.web.player import PlayerError, load_document
from sci2audio.web.state import Listening, ServerState

KINDS = ("note", "quote", "mark")  # the dock's order (ADR-008 2.2 B)


def labels(s: Strings) -> ExportLabels:
    """The headings' words in the page's language; the CSV's type column stays data."""
    return ExportLabels(
        mark=s("capture.mark"),
        note=s("capture.note"),
        quote=s("capture.quote"),
        page=s("export.page"),
    )


def stem(s: Strings, documents: list[ExportedDocument], one: bool) -> str:
    """The file's name without its extension: the document's title for one document, else
    the page's word for captures."""
    return file_stem(documents[0].reference.title if one else s("export.stem"))


def keys(state: ServerState) -> list[str]:
    """Every document the Captures page lists, in the Library's order."""
    return [document.id for document in state.store.all()] + [
        job.id for job in state.config.outside
    ]


def exported(state: ServerState, kind: str, chosen: str) -> list[ExportedDocument]:
    """The documents with the captures the page shows for type `kind` ("all" or one of
    KINDS) and document `chosen` ("" for all), each with its captures in reading order;
    documents with none shown are left out."""
    documents = []
    for key in keys(state):
        if chosen and key != chosen:
            continue
        found = state.listening(key)
        if found is None:
            continue
        document = _exported(state, found, kind)
        if document is not None and document.captures:
            documents.append(document)
    return documents


def _exported(state: ServerState, found: Listening, kind: str) -> ExportedDocument | None:
    try:
        file = state.captures.read(found.work, found.document)
    except (MarkersWaiting, CapturesUnreadable, OSError):
        return None
    if file is None:
        return None
    captures = [c for c in file.captures if kind == "all" or c.type.value == kind]
    about = None if found.outside else read_about(found.work)
    title = about.title if about else found.name
    try:
        document = load_document(found.work)
    except PlayerError:  # no analysis to find the sentences in: as captured, no page
        return ExportedDocument(Reference(title), tuple(ExportedCapture(c) for c in captures))
    find = finder(document)
    pages = PageFinder(document)
    placed: list[tuple[tuple[int, int, int, int, int], ExportedCapture]] = []
    for order, capture in enumerate(captures):
        where = find(capture.anchor)
        if where is None:
            placed.append(((1, 0, 0, 0, order), ExportedCapture(capture)))
            continue
        block, start, _ = where
        at = (0, block, start, _dock(capture), order)
        placed.append((at, ExportedCapture(capture, pages.page(block, start))))
    placed.sort(key=lambda entry: entry[0])
    reference = reference_of(title, document.content)
    return ExportedDocument(reference, tuple(item for _, item in placed))


def _dock(capture: Capture) -> int:
    return KINDS.index(capture.type.value)
