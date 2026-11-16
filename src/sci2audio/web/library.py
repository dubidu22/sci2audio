"""The library and the rail's shelf (#389, D-664): what the start page lists about each
document and the small records behind it.

Two records of the web's own sit in a document's working folder next to the app's:

- `opened.json`: when the document page or its Listen page was last opened.
- `about.json`: the title and authors the file gives, and a PDF's page count, written by
  the web's script task after an analysis.

Neither is ever needed: a record that is missing, too large, a link, not ours or not
readable reads as nothing, and a record that cannot be written is left as it was. A page
never fails because of them.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sci2audio.app.chapters import document_title
from sci2audio.app.files import write_texts
from sci2audio.core import Document
from sci2audio.web.player import (
    POSITION,
    PlayerError,
    audiobook_stamp,
    in_folder,
    read_audio_record,
    recorded_position,
)

logger = logging.getLogger(__name__)

OPENED = "opened.json"
OPENED_FORMAT = "sci2audio-web-opened"
ABOUT = "about.json"
ABOUT_FORMAT = "sci2audio-web-about"
RECORD_VERSION = 1
RECORD_LIMIT = 16384  # bytes: an about record is a title and a few names
OPENED_AGAIN_AFTER = timedelta(seconds=60)  # a reload within a minute writes nothing
NBSP = "\N{NO-BREAK SPACE}"  # between a number and its unit, as the strings write it


# ---- the records ---------------------------------------------------------------------------


def _read_record(path: Path, form: str) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > RECORD_LIMIT:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(data, dict)
        or data.get("format") != form
        or data.get("version") != RECORD_VERSION
    ):
        return None
    return data


def _write_record(path: Path, data: dict[str, Any]) -> None:
    try:
        write_texts({path: json.dumps(data, ensure_ascii=False) + "\n"}, overwrite=True)
    except OSError as error:  # a full disk or a read-only folder: the page goes on
        logger.warning("could not write %s: %s", path.name, error)


def read_opened(work: Path) -> datetime | None:
    """When the document was last opened (UTC), or None."""
    data = _read_record(work / OPENED, OPENED_FORMAT)
    if data is None or not isinstance(data.get("opened"), str):
        return None
    try:
        moment = datetime.fromisoformat(data["opened"])
    except ValueError:
        return None
    return moment.astimezone(UTC) if moment.tzinfo is not None else None


def write_opened(work: Path, now: datetime) -> None:
    """Keep that the document was opened at `now` (UTC); a reload within a minute keeps
    the record as it is. Never raises for the file system."""
    last = read_opened(work)
    if last is not None and timedelta(0) <= now - last < OPENED_AGAIN_AFTER:
        return
    data = {"format": OPENED_FORMAT, "version": RECORD_VERSION, "opened": now.isoformat()}
    _write_record(work / OPENED, data)


@dataclass(frozen=True)
class About:
    """What the file says about itself (#389): its title, its authors and, for a PDF, its
    number of pages."""

    title: str
    authors: tuple[str, ...] = ()
    pages: int | None = None


def about_of(document: Document) -> About:
    content = document.content
    pdf = str(content.source.format) == "pdf"
    return About(
        title=document_title(document),
        authors=tuple(a.strip() for a in content.metadata.authors if a.strip()),
        pages=len(content.pages) if pdf and content.pages else None,
    )


def write_about(work: Path, about: About) -> None:
    """Keep what the file says about itself. Never raises for the file system."""
    data = {
        "format": ABOUT_FORMAT,
        "version": RECORD_VERSION,
        "title": about.title,
        "authors": list(about.authors),
        "pages": about.pages,
    }
    _write_record(work / ABOUT, data)


def read_about(work: Path) -> About | None:
    data = _read_record(work / ABOUT, ABOUT_FORMAT)
    if data is None:
        return None
    title, authors, pages = data.get("title"), data.get("authors"), data.get("pages")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
        return None
    if pages is not None and (not isinstance(pages, int) or isinstance(pages, bool) or pages < 1):
        return None
    return About(title.strip(), tuple(a for a in authors if a.strip()), pages)


# ---- the audiobook and how far it was heard -----------------------------------------------


@dataclass(frozen=True)
class Heard:
    """A document's audiobook as the library shows it: its length, and how far the person
    listened (None: never started, or the record is for another audiobook)."""

    duration: float
    time: float | None

    @property
    def fraction(self) -> float | None:
        if self.time is None or self.duration <= 0:
            return None
        return min(1.0, max(0.0, self.time / self.duration))


def heard(work: Path, document_id: str, folders: tuple[Path | None, ...]) -> Heard | None:
    """The audiobook of this document and the remembered position in it (#153), checked
    against the audiobook's stamp, not against the read-along file (that is the Listen
    page's job); None when there is no usable audiobook record."""
    try:
        record = read_audio_record(work, document_id)
    except PlayerError:
        return None
    stamp = None
    for folder in folders:
        if folder is None or not folder.is_absolute():
            continue
        path = in_folder(folder, record.readalong)
        if path is None:
            continue
        try:
            stamp = audiobook_stamp(path)
        except OSError:
            continue
        break
    if stamp is None:
        return Heard(record.duration, None)
    position = recorded_position(work, document_id, stamp)
    time = None if position is None or position.time > record.duration + 1 else position.time
    return Heard(record.duration, time)


def position_age(work: Path) -> float:
    """When the position was last kept (a file time), 0 when there is none."""
    try:
        return (work / POSITION).stat().st_mtime
    except OSError:
        return 0.0


# ---- words for times ------------------------------------------------------------------------


def length_text(seconds: float, hours_word: str, minutes_word: str) -> str:
    """An audiobook's length as "1 h 08 min" or "54 min" (the table's words)."""
    minutes = max(1, math.ceil(seconds / 60)) if seconds > 0 else 0
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}{NBSP}{hours_word} {minutes:02d}{NBSP}{minutes_word}"
    return f"{minutes}{NBSP}{minutes_word}"


def when(moment: datetime, now: datetime) -> tuple[str, str]:
    """When something happened, as (kind, value) in this computer's time: ("today", "09:14"),
    ("yesterday", "18:02") or ("date", "2026-11-12"), ISO dates as everywhere else (D-290)."""
    local, today = moment.astimezone(), now.astimezone()
    clock = f"{local:%H:%M}"
    if local.date() == today.date():
        return "today", clock
    if local.date() == today.date() - timedelta(days=1):
        return "yesterday", clock
    return "date", local.date().isoformat()
