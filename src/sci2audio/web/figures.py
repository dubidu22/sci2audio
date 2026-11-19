"""The figure, table or formula itself, shown in the player where its notice is read (#293,
D-771).

A PDF placeholder is shown as a crop of its page: one region a page its parts lie on, the
union of their boxes with a small margin, rendered by extraction in the PDF reader's child
process (`extract_pdf_regions`). An EPUB picture is read from the book by its `ref`
(`extract_epub_picture`, D-310); an EPUB table or formula without a picture keeps its text
view. Markdown and plain text show none: sci2audio keeps only the text file, not the pictures
beside it (D-771 Q1). Nothing here takes a path from a request: the address names a block
and an image by number, and everything else comes from the project's own records.

Crops are kept in the project data folder's `figures/` (removed with the project, #470),
under a name made from what they show, so a new analysis that moves a box never meets an old
crop. A crop is written only while the project is still there (`DocumentStore.unchanged`,
D-356), never by making the project folder again, and the folder is kept under
`CACHE_LIMIT` by removing the oldest crops first.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import stat
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sci2audio.core import BlockKind, Box, Document, Picture, SourceFormat
from sci2audio.extraction import Region, extract_epub_picture, extract_pdf_regions

if TYPE_CHECKING:
    from sci2audio.web.documents import StoredDocument

KINDS = frozenset({BlockKind.FIGURE, BlockKind.TABLE, BlockKind.FORMULA})
MAX_IMAGES = 4  # images one block shows, at most
MARGIN = 4.0  # points around a crop
CSS_PER_POINT = 96 / 72  # a crop is shown at its printed size, no wider than the text
BATCH = 12  # crops one child renders, at most
CACHE_FOLDER = "figures"
CACHE_LIMIT = 64 * 1024 * 1024  # bytes of crops a project keeps
FILE_LIMIT = 8 * 1024 * 1024  # bytes a kept crop may have; a larger file is not ours
CACHE_VERSION = 1
PNG = "image/png"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class Shown:
    """One image of a placeholder block: `n` counts the block's images from 0. A PDF crop has
    its `region` and its size in CSS pixels; an EPUB picture its `ref` and no size (unknown
    until read)."""

    block: int
    n: int
    alt: str
    region: Region | None = None
    ref: str = ""
    width: int = 0
    height: int = 0


@dataclass(frozen=True)
class _Item:
    page: int
    box: Box | None
    picture: Picture | None


class Catalog:
    """Where a document's items lie, gathered once, for the images of all its blocks."""

    def __init__(self, document: Document) -> None:
        self.document = document
        self.format = document.content.source.format
        self.items: dict[str, _Item] = {}
        self.pages: dict[int, tuple[float, float]] = {}
        for page in document.content.pages:
            if page.width is not None and page.height is not None:
                self.pages[page.number] = (page.width, page.height)
            for line in page.lines:
                self.items[line.id] = _Item(page.number, line.box, None)
            for picture in page.pictures:
                self.items[picture.id] = _Item(page.number, picture.box, picture)
            for drawing in page.drawings:
                self.items[drawing.id] = _Item(page.number, drawing.box, None)
        self.captions: dict[int, str] = {}
        for block in document.blocks:
            text = _fold(block.text)
            if block.describes is not None and text:
                self.captions.setdefault(block.describes, text)

    def images(self, index: int, notice: str = "") -> list[Shown]:
        """The images block `index` shows in the player: none unless it is a figure, table
        or formula placeholder of a PDF (its page regions) or an EPUB (its pictures; a table
        keeps its text view). Alt text: the picture's own, else the caption's text, else
        `notice` (AC-293.3)."""
        blocks = self.document.blocks
        if not 0 <= index < len(blocks):
            return []
        block = blocks[index]
        if block.kind not in KINDS or not block.is_placeholder:
            return []
        caption = self.captions.get(index, "")
        items = [self.items[part.item] for part in block.parts if part.item in self.items]
        if self.format is SourceFormat.PDF:
            return self._crops(index, items, caption or notice)
        if self.format is SourceFormat.EPUB and block.kind is not BlockKind.TABLE:
            pictures = [item.picture for item in items if item.picture and item.picture.ref]
            return [
                Shown(index, n, _fold(p.alt) or caption or notice, ref=p.ref)
                for n, p in enumerate(_unique(pictures)[:MAX_IMAGES])
            ]
        return []

    def _crops(self, index: int, items: list[_Item], alt: str) -> list[Shown]:
        """One region a page, in the order the block's parts first reach each page."""
        boxes: dict[int, list[Box]] = {}
        for item in items:
            if item.box is not None and item.page in self.pages:
                boxes.setdefault(item.page, []).append(item.box)
        shown: list[Shown] = []
        for number, found in list(boxes.items())[:MAX_IMAGES]:
            width, height = self.pages[number]
            box = _clipped(
                min(b.x0 for b in found) - MARGIN,
                min(b.y0 for b in found) - MARGIN,
                max(b.x1 for b in found) + MARGIN,
                max(b.y1 for b in found) + MARGIN,
                width,
                height,
            )
            if box is None:
                continue
            shown.append(
                Shown(
                    index,
                    len(shown),
                    alt,
                    region=Region(number, box),
                    width=round((box.x1 - box.x0) * CSS_PER_POINT),
                    height=round((box.y1 - box.y0) * CSS_PER_POINT),
                )
            )
        return shown


def images(document: Document, index: int, notice: str = "") -> list[Shown]:
    """`Catalog(document).images(index, notice)`, for one block."""
    return Catalog(document).images(index, notice)


def _clipped(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> Box | None:
    x0, y0, x1, y1 = max(x0, 0.0), max(y0, 0.0), min(x1, width), min(y1, height)
    return Box(x0, y0, x1, y1) if x1 - x0 >= 1 and y1 - y0 >= 1 else None


def _unique(pictures: list[Picture]) -> list[Picture]:
    """Each picture once, where it first stands."""
    seen: set[str] = set()
    unique: list[Picture] = []
    for picture in pictures:
        if picture.id not in seen:
            seen.add(picture.id)
            unique.append(picture)
    return unique


def _fold(text: str) -> str:
    return " ".join(text.split())


# ---- serving them ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Image:
    data: bytes
    media_type: str


class Figures:
    """Serves the images; one lock a document, so a page of lazy images costs one child for
    up to `BATCH` crops, not one for each (D-771 D6). Held by the server state."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def _lock(self, document_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(document_id, threading.Lock())

    def image(
        self,
        document_id: str,
        document: Document,
        block: int,
        n: int,
        source: Path,
        folder: Path,
        unchanged: Callable[[], contextlib.AbstractContextManager[StoredDocument | None]],
    ) -> Image | None:
        """Image `n` of block `block`, or None. `document` must be the project's own record
        and `source` its own copy of the file; `folder` is the project data folder, and
        `unchanged()` holds off a removal while it gives the project (None once it is
        gone, D-356)."""
        if document.content.source.sha256[:16] != document_id:
            return None
        catalog = Catalog(document)
        found = [shown for shown in catalog.images(block) if shown.n == n]
        if not found:
            return None
        shown = found[0]
        if shown.region is None:
            # the reader holds the whole book in memory: one read a document at a time, so
            # a page of lazy images does not hold it six times over (#582 review F1)
            with self._lock(document_id):
                picture = extract_epub_picture(source, shown.ref)
            return None if picture is None else Image(picture.data, picture.media_type)
        name = cache_name(document_id, shown.region)
        cached = read_cached(folder, name)
        if cached is not None:
            return Image(cached, PNG)
        with self._lock(document_id):
            cached = read_cached(folder, name)  # rendered while this request waited
            if cached is not None:
                return Image(cached, PNG)
            batch = [shown.region, *_following(catalog, document_id, shown, folder)]
            rendered = extract_pdf_regions(source, batch)
            with unchanged() as still:
                if still is not None and still.folder == folder:
                    for region, data in zip(batch, rendered, strict=True):
                        if data is not None:
                            write_cached(folder, cache_name(document_id, region), data)
        data = rendered[0]
        return None if data is None else Image(data, PNG)


def _following(catalog: Catalog, document_id: str, asked: Shown, folder: Path) -> list[Region]:
    """The crops after the asked one, in reading order, that are not kept yet: rendered in
    the same child, up to `BATCH` in all."""
    found: list[Region] = []
    for index in range(asked.block, len(catalog.document.blocks)):
        for shown in catalog.images(index):
            if shown.region is None or (index == asked.block and shown.n <= asked.n):
                continue
            if not is_kept(folder, cache_name(document_id, shown.region)):
                found.append(shown.region)
            if len(found) >= BATCH - 1:
                return found
    return found


def cache_name(document_id: str, region: Region) -> str:
    """The kept crop's file name: what it shows, hashed."""
    key = {
        "version": CACHE_VERSION,
        "document": document_id,
        "page": region.page,
        "box": [region.box.x0, region.box.y0, region.box.x1, region.box.y1],
        "scale": region.scale,
    }
    canonical = json.dumps(key, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:32] + ".png"


def _real_folder(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def is_kept(folder: Path, name: str) -> bool:
    """Whether a crop looks kept, without reading it: a regular file (never a link) of at
    most `FILE_LIMIT` bytes in a real `figures/` folder. `read_cached` still checks it
    before it is served, so a bad file is rendered again when it is asked for."""
    figures = folder / CACHE_FOLDER
    if not _real_folder(figures):
        return False
    try:
        info = (figures / name).lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_size <= FILE_LIMIT


def read_cached(folder: Path, name: str) -> bytes | None:
    """A kept crop: only a regular file (never a link) in a real `figures/` folder, of at
    most `FILE_LIMIT` bytes, that starts as a PNG; None otherwise."""
    figures = folder / CACHE_FOLDER
    if not _real_folder(figures):
        return None
    path = figures / name
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > FILE_LIMIT:
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as file:
            data = file.read(FILE_LIMIT + 1)
    except OSError:
        return None
    if len(data) > FILE_LIMIT or not data.startswith(_PNG_SIGNATURE):
        return None
    return data


def write_cached(folder: Path, name: str, data: bytes) -> bool:
    """Keep a crop (atomically: a reader meets the old file or the whole new one), then
    keep the folder under `CACHE_LIMIT`. The project folder itself is never made: once it
    is gone, nothing is written. False when nothing was kept (a full disk costs only the
    cache)."""
    figures = folder / CACHE_FOLDER
    part = figures / f".{uuid.uuid4().hex}.part"
    try:
        figures.mkdir(exist_ok=True)  # never parents: a removed project stays removed
        if not _real_folder(figures):
            return False
        with part.open("xb") as file:
            file.write(data)
        os.replace(part, figures / name)
    except OSError:
        with contextlib.suppress(OSError):
            part.unlink(missing_ok=True)
        return False
    prune(figures)
    return True


def prune(figures: Path, limit: int | None = None) -> None:
    """Remove the oldest crops until those left take at most `limit` bytes."""
    limit = CACHE_LIMIT if limit is None else limit
    kept = sorted(_crops_in(figures), key=lambda entry: (entry[1], entry[0].name))
    total = sum(size for _, _, size in kept)
    for path, _, size in kept:
        if total <= limit:
            return
        with contextlib.suppress(OSError):
            path.unlink()
            total -= size


def _crops_in(figures: Path) -> Iterator[tuple[Path, float, int]]:
    try:
        with os.scandir(figures) as entries:
            for entry in entries:
                if entry.name.endswith(".png") and entry.is_file(follow_symlinks=False):
                    info = entry.stat(follow_symlinks=False)
                    yield Path(entry.path), info.st_mtime, info.st_size
    except OSError:
        return
