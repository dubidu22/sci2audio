"""Record what a PDF holds as `Content`, with pypdfium2, deciding nothing (D-63, D-65).

Characters become styled runs, runs become lines, and lines, pictures and drawings keep their
boxes and the order the file stores them in. The bookmarks become the outline, as stored (#24).
Reading order, headings and page furniture are the layout stage's work. Coordinates are points
with the origin at the top left of the page as shown: its crop box, turned by its /Rotate.

PDFium crashes when two threads call it at once, even for different files, so every call goes
through `_PDFIUM`: the one piece of global state this stage has (KB audit "PDFium thread-safety
crash", D-65).

A file from a user is read in a child process (`extract_pdf`, `extract_pdf_cover`,
`extract_pdf_regions`; #185, #28, D-581): PDFium decodes streams and loads pages before our
limits can count anything, so the child has a memory limit (`MAX_MEMORY`) and a time limit for
each step (`STEP_SECONDS`), and a crash inside PDFium ends only the child. Each read has its
own process, so two reads no longer wait for each other's lock; at most `MAX_PDF_READERS`
children run at once. The child reports each page it starts ("page 3 of 400"), which
`extract_pdf` hands on as progress (#343), and a cancelled read ends the child at once (#344).
`read_pdf` reads bytes in this process, without those limits: it is the child's own work.
"""

from __future__ import annotations

import ctypes
import hashlib
import math
import re
import threading
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw

from sci2audio.core import (
    Box,
    Content,
    Drawing,
    Metadata,
    OutlineEntry,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.extraction import isolate
from sci2audio.extraction.cover import Cover, png
from sci2audio.extraction.errors import ExtractionError, ReadCancelled
from sci2audio.extraction.language import stated_language

_PDFIUM = threading.Lock()

LINE_GAP = 1.0  # a gap this many em wide ends a line, so columns and table cells stay apart
# A space PDFium adds itself (the file has none there) is kept only where white of a space
# stands: never between letters that touch, and between two baselines (a sub- or superscript
# and its neighbour) only from SPACE em on. TeX leaves 0.05 em after a script and 0.12 em at a
# fraction; a thin space is 0.17 em (#36, D-274 to D-276). Layout joins the pieces of a line
# by the same measure (LayoutSettings.word_space).
SPACE = 0.15  # em of the larger letter: the narrowest white that is a space between baselines
SHIFT = 0.1  # em of the smaller letter: baselines further apart than this are two baselines
STACK = 2.0  # em: a script stacked under another starts at most this far back under it
# An inline fraction's numerator and denominator touch along the line like a script stacked
# under another, but a bar is drawn between them: there the space PDFium adds stays, so the
# two never read as one word ("1ℏ", #202, D-575). Layout keeps a space between pieces of a
# line by the same measure (LayoutSettings.fraction_bar, fraction_reach).
# TeX keeps a fraction rule's thickness when it sets the fraction smaller: liu's 0.8 pt bar
# over 5 pt letters is 0.16 em, so the limit leaves room above that (#323).
FRACTION_BAR = 0.25  # em of the larger letter: a fraction bar is at most this thick ...
FRACTION_REACH = 0.6  # em: ... with numerator and denominator at most this far from it
# A spacing accent drawn as a glyph of its own over its letter, but stored apart from it (after
# the word, or a few words on), jumps back along the line and so comes out as a line holding
# only the accent (Chi p6 "Marasovic," with its acute apart, #125). It goes onto the letter
# it stands over. An accent stored in reading order inside a line stays as stored: the text
# step of #65 joins a TeX accent onto its letter as a marked edit and leaves a hat in maths
# alone (D-835).
ACCENT_LINES = 8  # lines stored before and after a lone accent searched for its letter
ACCENT_REACH = 0.5  # em: an accent stands at most this far above or below its letter's line
# Each spacing accent's combining form: textprep has its own (`characters`), which extraction
# cannot import.
_COMBINING = {
    "\u00b4": "\u0301",  # acute
    "`": "\u0300",  # grave
    "\u02c7": "\u030c",  # caron
    "\u02c6": "\u0302",  # circumflex
    "\u02dc": "\u0303",  # tilde
    "\u00a8": "\u0308",  # diaeresis
    "\u00af": "\u0304",  # macron
    "\u02d8": "\u0306",  # breve
    "\u02d9": "\u0307",  # dot above
    "\u00b8": "\u0327",  # cedilla
    "\u02db": "\u0328",  # ogonek
    "\u02da": "\u030a",  # ring
    "\u02dd": "\u030b",  # double acute
}
SAME_LINE = 0.3  # a character overlapping the line by this share of its height continues it
BOLD_WEIGHT = 600  # a font weight from this value on is bold
_ITALIC_FLAG = 1 << 6  # PDF font descriptor flag "Italic"
_FORCE_BOLD_FLAG = 1 << 18
# "Medi" is URW's bold cut (NimbusRomNo9L-Medi); "-Medium" (weight 500) is not bold.
# CM-Super and EC fonts (the T1 Computer Modern, e.g. SFBX1095) name their cut before the
# design size. Bold cuts: bx, bl, bi, xc, oc, rb, bm, sx, so; italic or slanted cuts: sl, ti,
# ci, sc, bl, bi, oc, si, so, it, st, vi (from the cm-super AFM files: Weight Bold, or an
# ItalicAngle other than 0). Upright italic (ui) and the other cuts stay plain.
_TEX_CUT = r"(?:^|\+)(?:sf|ec)"
_BOLD_NAME = re.compile(
    rf"bold|black|heavy|demi|medi(?!um)|cm\w*bx|{_TEX_CUT}(?:bx|bl|bi|xc|oc|rb|bm|sx|so)\d{{4}}",
    re.IGNORECASE,
)
_ITALIC_NAME = re.compile(
    rf"ital|oblique|cmti|cmbxti|cmsl|cmmi|{_TEX_CUT}(?:sl|ti|ci|sc|bl|bi|oc|si|so|it|st|vi)\d{{4}}",
    re.IGNORECASE,
)
_LINE_END_HYPHEN = 0x02  # how PDFium reports a hyphen printed at a line end
_SOFT_HYPHEN = "\u00ad"  # kept as it is: joining words is a text step (TP-02)
_UNKNOWN = "\ufffd"  # a glyph PDFium can't map to Unicode: recorded, not dropped
_SUBSET = re.compile(r"^[A-Z]{6}\+")
_PDF_DATE = re.compile(r"^D:(\d{4})(\d{2})?(\d{2})?")
OUTLINE_DEPTH = 15  # bookmark levels read; deeper ones are left out (D-267)
# Limits against hostile files, checked before the per-character work (D-394): a 2 KB file of
# shared page-tree nodes holds half a million pages, and a few KB of compressed text a million
# characters on one page, while the corpus's densest page holds under 6,000.
MAX_PAGES = 10_000
MAX_PAGE_CHARS = 100_000
MAX_CHARS = 10_000_000
# Drawings and pictures, counted as they are found (D-581): a 26 KB stream can hold a million
# rectangles, which a child reads within its memory and this process then has to take back.
# The corpus's busiest page holds 1,836 (a chart).
MAX_PAGE_GRAPHICS = 100_000
MAX_GRAPHICS = 500_000
# The child process (#185, D-581): a read at MAX_CHARS needs about 200 MB, the corpus under 40.
MAX_MEMORY = 1024**3  # bytes
STEP_SECONDS = 60  # opening the file, each page, the outline; the densest page took 2 s
MAX_PDF_READERS = 2  # children alive at once; each may take MAX_MEMORY
_READERS = isolate.Readers(MAX_PDF_READERS)
HEADER_ZONE = 1024  # a PDF's %PDF- header stands within its first 1,024 bytes (PDF 32000-1)
# "12 0 obj": the start of an object. Anchored at the start of a digit run and possessive, so
# a long run of digits or white space costs one pass, not one per start (#188).
_OBJECT = re.compile(rb"(?<!\d)\d++\s++\d++\s++obj\b")
# Permission bits of the /P entry (PDF 32000-1, table 22), counted from 1 as the standard does
_COPY = 1 << 4  # bit 5: copy or extract text
_ACCESSIBILITY = 1 << 9  # bit 10: extract text for accessibility (revision 3 on)


def extract_pdf(
    path: Path,
    *,
    pages: Callable[[int, int], None] | None = None,
    cancel: threading.Event | None = None,
) -> Content:
    """Read the PDF at `path` into `Content` in a child process with the limits above;
    raise ExtractionError if it can't be read.

    `pages(number, total)` is called as the child starts each page, counted from 1 (#343).
    Once `cancel` is set, the child is ended and ReadCancelled raised (#344)."""
    on_step = None if pages is None else _page_steps(pages)
    result = _isolated(_read_file, str(path), on_step=on_step, cancel=cancel)
    if isinstance(result, isolate.Stopped):
        if result.reason == "cancelled":
            raise ReadCancelled(f"{path.name}: the read was cancelled")
        raise _stopped(path.name, result)
    return result


_PAGE_STEP = re.compile(r"page (\d+) of (\d+)")


def _page_steps(pages: Callable[[int, int], None]) -> Callable[[str], None]:
    """A step handler that hands each "page N of M" on to `pages`; other steps are not
    pages."""

    def on_step(step: str) -> None:
        if found := _PAGE_STEP.fullmatch(step):
            pages(int(found[1]), int(found[2]))

    return on_step


def _isolated(
    target: object,
    path: str,
    *,
    on_step: Callable[[str], None] | None = None,
    cancel: threading.Event | None = None,
    extra: tuple[object, ...] = (),
) -> object:
    try:
        return isolate.run(
            target,  # type: ignore[arg-type]
            (path, {name: globals()[name] for name in _LIMITS}, *extra),
            memory=MAX_MEMORY,
            step_seconds=STEP_SECONDS,
            readers=_READERS,
            on_step=on_step,
            cancel=cancel,
        )
    except isolate.NotStarted as error:  # D-581: no reading without a child
        name = Path(path).name
        raise ExtractionError(
            f"{name}: cannot be read: sci2audio could not start its PDF reader ({error})"
        ) from error


# The limits in force in this process hold in the child too (a test lowers them here).
_LIMITS = (
    "MAX_PAGES",
    "MAX_PAGE_CHARS",
    "MAX_CHARS",
    "MAX_PAGE_GRAPHICS",
    "MAX_GRAPHICS",
    "OUTLINE_DEPTH",
    "COVER_SIZE",
    "REGION_SIDE",
    "REGION_PIXELS",
)


def _read_file(path: str, limits: dict[str, int]) -> Content:
    """The child's work for `extract_pdf`."""
    globals().update(limits)
    file = Path(path)
    try:
        data = file.read_bytes()
    except OSError as error:
        raise ExtractionError(f"{file.name}: cannot be opened ({error.strerror})") from error
    return read_pdf(data, file.name)


def _stopped(name: str, stopped: isolate.Stopped) -> ExtractionError:
    if stopped.step == "starting":  # not the file's doing: the reader never began to read it
        why = (
            f"it did not start within {isolate.START_SECONDS:g} seconds"
            if stopped.reason == "time"
            else "it ended while starting"
        )
        return ExtractionError(
            f"{name}: cannot be read: sci2audio could not start its PDF reader ({why})"
        )
    if stopped.reason == "memory":
        size = (
            f"{MAX_MEMORY / 1024**3:g} GB"
            if MAX_MEMORY >= 1024**3
            else f"{MAX_MEMORY // 1024**2} MB"
        )
        return _too_large(name, f"reading it needs more than {size} of memory")
    if stopped.reason == "time":
        if stopped.step == "opening":
            what = "opening it"
        elif stopped.step == "outline":
            what = "reading its outline"
        else:  # "page 7 of 400" reads "reading page 7"
            what = f"reading {stopped.step.split(' of ')[0]}"
        return _too_large(name, f"{what} took more than {STEP_SECONDS:g} seconds")
    return ExtractionError(f"{name}: the PDF is damaged (the PDF reader stopped unexpectedly)")


def read_pdf(data: bytes, name: str) -> Content:
    """Read PDF bytes into `Content` in this process, without the child's limits;
    `name` is the bare file name the source keeps."""
    if not data:
        raise ExtractionError(f"{name}: the file is empty")
    source = Source(name, SourceFormat.PDF, sha256=hashlib.sha256(data).hexdigest())
    with _PDFIUM:
        try:
            document = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as error:
            raise ExtractionError(_load_message(name, data, error)) from error
        try:
            _check(document, name, data)
            pages = _pages(document, name)
            isolate.report("outline")
            metadata = _metadata(document)
            outline = _outline(document, len(pages))
        except pdfium.PdfiumError as error:
            raise ExtractionError(f"{name}: the PDF is damaged ({error})") from error
        finally:
            document.close()
    if not any(page.lines for page in pages):
        raise ExtractionError(
            f"{name}: the PDF holds no text; a scanned PDF needs text recognition,"
            " which sci2audio can't do yet"
        )  # D-393
    return Content(source=source, pages=pages, metadata=metadata, outline=outline)


def _check(document: pdfium.PdfDocument, name: str, data: bytes) -> None:
    """Refuse, before reading any page, a file cut short (D-395), one whose owner forbids
    reading its text out (D-396), and one without pages or with too many (D-394)."""
    if _cut_short(data, bool(raw.FPDF_DocumentHasValidCrossReferenceTable(document.raw))):
        raise ExtractionError(_CUT_SHORT.format(name=name))
    if _forbids_reading(document):
        raise ExtractionError(
            f"{name}: the PDF's owner does not allow its text to be read out;"
            " ask for a copy without this restriction"
        )
    count = len(document)
    if count == 0:
        raise ExtractionError(f"{name}: the PDF has no pages")
    if count > MAX_PAGES:
        raise _too_large(name, f"more than {MAX_PAGES:,} pages")


_CUT_SHORT = "{name}: the PDF is cut short (an unfinished download?); download it again"


def _cut_short(data: bytes, xref_valid: bool) -> bool:
    """True if the file starts like a PDF but its end is missing (D-395, as applied in
    #188): object data follows its last %%EOF, so the cut fell
    inside a later section (an incremental update, the rest of a linearized file); or it
    has no %%EOF at all and PDFium had to rebuild the cross-reference table or couldn't
    open the file. PDFium reads a cut file as far as it can, and the rest is lost without
    a word. A file without %%EOF whose table PDFium found valid ends where its startxref
    says; at most the marker is missing. Bytes after a whole file's last %%EOF that hold no
    object (zeros, a web page) are no cut. One search from the last %%EOF on, linear in
    what follows it; nothing walks the objects."""
    if b"%PDF-" not in data[:HEADER_ZONE]:
        return False
    end = data.rfind(b"%%EOF")
    if end < 0:
        return not xref_valid
    return _OBJECT.search(data, end) is not None


def _forbids_reading(document: pdfium.PdfDocument) -> bool:
    """True if the owner password's permissions forbid both copying the text and
    extracting it for accessibility. Revision 2 has no accessibility bit: there copying
    decides both (PDF 32000-1, table 22)."""
    revision = raw.FPDF_GetSecurityHandlerRevision(document.raw)
    if revision < 2:  # -1: the file is not encrypted
        return False
    permissions = raw.FPDF_GetDocPermissions(document.raw) & 0xFFFFFFFF
    copy = bool(permissions & _COPY)
    accessibility = bool(permissions & _ACCESSIBILITY) if revision >= 3 else copy
    return not copy and not accessibility


def _too_large(name: str, detail: str) -> ExtractionError:
    return ExtractionError(f"{name}: the PDF is too large or damaged ({detail})")


COVER_SIZE = 1400  # pixels on the longer side of a PDF's cover (D-313)


def extract_pdf_cover(path: Path) -> Cover | None:
    """The PDF's first page as a PNG, `COVER_SIZE` pixels on its longer side, rendered in a
    child process with the limits of `extract_pdf`; None if the file can't be read or
    rendered, or the child is stopped (a missing cover never stops a job)."""
    try:
        result = _isolated(_cover_of_file, str(path))
    except ExtractionError:
        return None
    return result if isinstance(result, Cover) else None


def _cover_of_file(path_text: str, limits: dict[str, int]) -> Cover | None:
    """The child's work for `extract_pdf_cover`."""
    globals().update(limits)
    path = Path(path_text)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    with _PDFIUM:
        try:
            document = pdfium.PdfDocument(data)
        except pdfium.PdfiumError:
            return None
        try:
            if len(document) == 0:
                return None
            page = document[0]
            try:
                width, height = page.get_size()
                if not (math.isfinite(width) and math.isfinite(height)) or min(width, height) <= 0:
                    return None
                bitmap = page.render(scale=COVER_SIZE / max(width, height), rev_byteorder=True)
                try:
                    if bitmap.n_channels != 3:
                        return None
                    pixels = bytes(
                        ctypes.cast(
                            bitmap.buffer,
                            ctypes.POINTER(ctypes.c_ubyte * (bitmap.stride * bitmap.height)),
                        ).contents
                    )
                    image = png(bitmap.width, bitmap.height, pixels, bitmap.stride)
                finally:
                    bitmap.close()
            finally:
                page.close()
        except (pdfium.PdfiumError, ValueError):
            return None
        finally:
            document.close()
    return Cover(image, "image/png")


# ---- regions of a page, for the player (#293) -----------------------------------------
REGION_SCALE = 3.0  # pixels a point (216 dpi): a formula's small type stays sharp
REGION_SIDE = 2_000  # pixels on a region image's longer side, at most ...
REGION_PIXELS = 4_000_000  # ... and in all


@dataclass(frozen=True)
class Region:
    """A part of a page to render: the page's number (from 1) and a box in points from the
    top left of the page as shown, as `Content` places its items, at `scale` pixels a point.
    The part of the box outside the page is left out."""

    page: int
    box: Box
    scale: float = REGION_SCALE


def region_scale(box: Box, scale: float) -> float:
    """`scale`, lowered so the box's image has at most `REGION_SIDE` pixels on its longer
    side and `REGION_PIXELS` in all."""
    width, height = box.x1 - box.x0, box.y1 - box.y0
    if width <= 0 or height <= 0 or not math.isfinite(scale) or scale <= 0:
        return 0.0
    scale = min(scale, REGION_SIDE / max(width, height))
    return min(scale, math.sqrt(REGION_PIXELS / (width * height)))


def extract_pdf_regions(path: Path, regions: list[Region]) -> list[bytes | None]:
    """Each region of the PDF at `path` as a PNG, rendered in a child process with the
    limits of `extract_pdf` (one step a region); None for a region that is not on its page
    or can't be rendered, and for all of them if the file can't be read or the child is
    stopped (a missing image never stops anything)."""
    if not regions:
        return []
    try:
        result = _isolated(_regions_of_file, str(path), extra=(list(regions),))
    except ExtractionError:
        return [None] * len(regions)
    if not isinstance(result, list) or len(result) != len(regions):
        return [None] * len(regions)
    return [image if isinstance(image, bytes) else None for image in result]


def _regions_of_file(
    path_text: str, limits: dict[str, int], regions: list[Region]
) -> list[bytes | None]:
    """The child's work for `extract_pdf_regions`."""
    globals().update(limits)
    try:
        data = Path(path_text).read_bytes()
    except OSError:
        return [None] * len(regions)
    found: list[bytes | None] = []
    with _PDFIUM:
        try:
            document = pdfium.PdfDocument(data)
        except pdfium.PdfiumError:
            return [None] * len(regions)
        try:
            for number, region in enumerate(regions, 1):
                isolate.report(f"region {number} of {len(regions)}")
                found.append(_region(document, region))
        finally:
            document.close()
    return found


def _region(document: pdfium.PdfDocument, region: Region) -> bytes | None:
    if not 1 <= region.page <= len(document):
        return None
    try:
        page = document[region.page - 1]
    except pdfium.PdfiumError:
        return None
    try:
        width, height = page.get_size()  # as shown: PDFium turns the page by its /Rotate
        if not (math.isfinite(width) and math.isfinite(height)) or min(width, height) <= 0:
            return None
        box = region.box
        x0, y0 = max(box.x0, 0.0), max(box.y0, 0.0)
        x1, y1 = min(box.x1, width), min(box.y1, height)
        if x1 - x0 < 1 or y1 - y0 < 1:  # off the page, or less than a point
            return None
        scale = region_scale(Box(x0, y0, x1, y1), region.scale)
        if scale <= 0:
            return None
        bitmap = page.render(
            scale=scale, crop=(x0, height - y1, width - x1, y0), rev_byteorder=True
        )
        try:
            if bitmap.n_channels != 3:
                return None
            pixels = bytes(
                ctypes.cast(
                    bitmap.buffer,
                    ctypes.POINTER(ctypes.c_ubyte * (bitmap.stride * bitmap.height)),
                ).contents
            )
            return png(bitmap.width, bitmap.height, pixels, bitmap.stride)
        finally:
            bitmap.close()
    except (pdfium.PdfiumError, ValueError):
        return None
    finally:
        page.close()


def _load_message(name: str, data: bytes, error: pdfium.PdfiumError) -> str:
    # PDFium's error code can be left over from an earlier file (it isn't reset on every
    # failure), so a password or a protection is only blamed when the file really is
    # encrypted.
    encrypted = b"/Encrypt" in data
    if encrypted and error.err_code == raw.FPDF_ERR_PASSWORD:
        return f"{name}: the PDF is password-protected; remove the password and try again"
    if encrypted and error.err_code == raw.FPDF_ERR_SECURITY:  # D-397
        return (
            f"{name}: the PDF is protected by DRM or a certificate;"
            " sci2audio can read only PDFs without it"
        )
    if _cut_short(data, xref_valid=False):  # D-395
        return _CUT_SHORT.format(name=name)
    return f"{name}: not a PDF, or the file is damaged"


def _metadata(document: pdfium.PdfDocument) -> Metadata:
    info = document.get_metadata_dict(skip_empty=True)
    # The Author entry is kept whole: files separate names with ";", "," or "and", and
    # "Last, First" makes any split a guess.
    author = info.get("Author", "").strip()
    date = ""
    if found := _PDF_DATE.match(info.get("CreationDate", "")):
        date = "-".join(part for part in found.groups() if part)
    return Metadata(
        title=info.get("Title", "").strip(),
        authors=(author,) if author else (),
        date=date,
        language=_language(document),
    )


def _outline(document: pdfium.PdfDocument, pages: int) -> tuple[OutlineEntry, ...]:
    """The bookmarks in the file's order, titles as stored (D-266). A damaged outline gives
    what could be read and never fails the file (D-268): pypdfium2 stops at a bookmark that
    points back at an earlier one, and levels below `OUTLINE_DEPTH` are left out (D-267)."""
    return tuple(
        OutlineEntry(_title(bookmark.raw), bookmark.level + 1, _target(bookmark, pages))
        for bookmark in document.get_toc(max_depth=OUTLINE_DEPTH)
    )


def _title(bookmark: object) -> str:
    """The bookmark's title as stored, as PDFium reads it: PDFium turns a control character
    (a line break, a zero byte) into a space; nothing is stripped or dropped. A code PDFium
    can't decode becomes U+FFFD."""
    size = raw.FPDFBookmark_GetTitle(bookmark, None, 0)
    if size <= 2:  # nothing but the terminating zero
        return ""
    buffer = ctypes.create_string_buffer(size)
    raw.FPDFBookmark_GetTitle(bookmark, buffer, size)
    return buffer.raw[: size - 2].decode("utf-16-le", errors="replace")


def _target(bookmark: pdfium.PdfBookmark, pages: int) -> int | None:
    """The number of the page the bookmark points at, or None. PDFium follows a GoTo action
    as well as a destination; a URI or launch action, or a page the file lacks, give None."""
    dest = bookmark.get_dest()
    if dest is None:
        return None
    index = dest.get_index()
    return index + 1 if index is not None and 0 <= index < pages else None


def _language(document: pdfium.PdfDocument) -> str:
    size = raw.FPDFCatalog_GetLanguage(document.raw, None, 0)
    if size <= 2:  # nothing but the terminating zero
        return ""
    buffer = ctypes.create_string_buffer(size)
    raw.FPDFCatalog_GetLanguage(
        document.raw, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort)), size
    )
    return stated_language(buffer.raw[: size - 2].decode("utf-16-le", errors="replace"))


def _pages(document: pdfium.PdfDocument, name: str) -> tuple[Page, ...]:
    """Every page in order. A page PDFium can't load fails the whole file, named (D-398):
    reading on would lose its text without a word. PDFium counts each page's characters
    before any of ours are made, so the limits cost nothing on a real file (D-394)."""
    pages: list[Page] = []
    total = 0
    graphics = 0  # drawings and pictures so far
    page_count = len(document)
    for index in range(page_count):
        number = index + 1
        isolate.report(f"page {number} of {page_count}")
        try:
            page = document[index]
        except pdfium.PdfiumError as error:
            raise ExtractionError(
                f"{name}: the PDF is damaged (page {number} cannot be read)"
            ) from error
        try:
            width, height = page.get_size()
            frame = _Frame.of(page)
            textpage = page.get_textpage()
            try:
                count = textpage.count_chars()
                if count > MAX_PAGE_CHARS:
                    detail = f"page {number} holds more than {MAX_PAGE_CHARS:,} characters"
                    raise _too_large(name, detail)
                total += max(count, 0)
                if total > MAX_CHARS:
                    raise _too_large(name, f"more than {MAX_CHARS:,} characters")
                pictures, drawings = _graphics(page, frame, number, name, graphics)
                graphics += len(pictures) + len(drawings)
                lines, unmapped = _lines(textpage, frame, number, _Bars.of(drawings))
            finally:
                textpage.close()
        finally:
            page.close()
        pages.append(
            Page(number, lines, pictures, drawings, width=width, height=height, unmapped=unmapped)
        )
    return tuple(pages)


@dataclass(frozen=True)
class _Frame:
    """The page as printed: its crop box, where PDFium shows and measures the page, and our
    positions are taken from its top left corner (#458). A crop box need not start at the
    file's origin: a page cut from a larger sheet (a journal page set on A4, one page of a
    spread) keeps the sheet's coordinates, and positions taken from the sheet's corner are
    all shifted. What the sheet prints outside the crop box is cut off, so not read; text
    outside the sheet itself is kept, as it always was. The sheet is the media box, also
    where the page takes it from the page tree (#543).

    A page with /Rotate is shown turned clockwise by that much, and PDFium measures it as
    shown, while the file places everything on the unturned page: every point is turned
    the same way, so positions are those of the page as shown (#537)."""

    left: float
    top: float
    width: float  # as shown: crop box height and width swapped on a page turned 90 or 270
    height: float
    sheet: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1 in page points
    turn: int = 0  # the page's /Rotate in degrees, clockwise: 0, 90, 180 or 270

    @classmethod
    def of(cls, page: pdfium.PdfPage) -> _Frame:
        left, bottom, right, top = page.get_bbox()
        turn = page.get_rotation() % 360
        wide, high = right - left, top - bottom
        frame = cls(left, top, *((high, wide) if turn in (90, 270) else (wide, high)), turn=turn)
        media = _media_box(page, (left, bottom, right, top))
        x0, y0 = frame.point(media[0], media[3])
        x1, y1 = frame.point(media[2], media[1])
        sheet = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if not all(map(math.isfinite, sheet)) or sheet == (0.0, 0.0, frame.width, frame.height):
            return frame
        return cls(frame.left, frame.top, frame.width, frame.height, sheet, turn)

    def point(self, x: float, y: float) -> tuple[float, float]:
        """A point of the file (y upwards) in page points from the top left (y downwards),
        on the page as shown."""
        u, v = x - self.left, self.top - y  # on the unturned page
        if self.turn == 90:
            return self.width - v, u
        if self.turn == 180:
            return self.width - u, self.height - v
        if self.turn == 270:
            return v, self.height - u
        return u, v

    def angle(self, angle: float) -> float:
        """A character's angle on the unturned page as the page shows it, in [0, 2π)."""
        turned = math.fmod(angle + math.radians(self.turn), math.tau)
        return 0.0 if math.tau - turned < 1e-6 else turned

    def shows(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """False for a box the crop box cuts off: wholly outside it, on the sheet."""
        if x1 >= 0 and y1 >= 0 and x0 <= self.width and y0 <= self.height:
            return True
        if self.sheet is None:
            return True
        x, y = (x0 + x1) / 2, (y0 + y1) / 2
        return not (self.sheet[0] <= x <= self.sheet[2] and self.sheet[1] <= y <= self.sheet[3])


_UNBOUNDED = 1e9  # points: a crop box wider than any media box


def _media_box(
    page: pdfium.PdfPage, crop: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """The page's media box as PDFium uses it: its own, else the one it inherits from the
    page tree, else PDFium's default (US Letter). `FPDFPage_GetMediaBox` reads only the
    page's own entry (crbug.com/pdfium/1786), but the bounding box PDFium gives is the crop
    box cut to the inherited media box: with the crop box opened wide for one call, it is
    the media box. The crop box is set back to `crop` (the crop box as PDFium used it) before
    any text is read; the file is never saved."""
    raw.FPDFPage_SetCropBox(page.raw, -_UNBOUNDED, -_UNBOUNDED, _UNBOUNDED, _UNBOUNDED)
    try:
        return page.get_bbox()
    finally:
        raw.FPDFPage_SetCropBox(page.raw, *crop)


@dataclass
class _Char:
    text: str
    style: tuple[str, float, bool, bool]  # font, size, bold, italic
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in page points, y downwards
    angle: float
    u0: float  # extent along the line, in the text's own direction
    u1: float
    v0: float  # extent across the line
    v1: float
    base: float = math.nan  # where the baseline stands across the line (nan if unknown)
    unmapped: bool = False  # from a font with no Unicode source (#442)


# what stands between two characters: a space the file holds, or one PDFium added itself
_SPACE, _GENERATED = "space", "generated"


@dataclass
class _Line:
    chars: list[_Char] = field(default_factory=list)
    spaces: set[int] = field(default_factory=set)  # a space goes before chars[i]
    top: float = math.inf  # extent across the line so far
    bottom: float = -math.inf
    # where the letters of the line before end, when this line starts back under them as a
    # script stacked under another ("0" under "1st" in J with 1st over 0)
    before: float = -math.inf
    bars: _Bars = field(default_factory=lambda: _Bars())  # the page's possible fraction bars

    def accepts(self, char: _Char) -> bool:
        last = self.chars[-1]
        turn = abs(char.angle - last.angle)  # around the circle: 0.003 and 6.280 are close
        if min(turn, math.tau - turn) > 0.01:
            return False
        size = max(last.style[1], char.style[1], 1.0)
        if char.u0 < last.u0 - 0.5 * size or char.u0 - last.u1 > LINE_GAP * size:
            return False  # back to the start of a line, or a wide gap: a new line
        overlap = min(self.bottom, char.v1) - max(self.top, char.v0)
        return overlap >= SAME_LINE * min(self.bottom - self.top, char.v1 - char.v0)

    def add(self, char: _Char, space: str | None) -> None:
        """Add the character; `space` is what stood before it in the file, if anything."""
        if self.chars and (space == _SPACE or (space == _GENERATED and self._white(char))):
            self.spaces.add(len(self.chars))
        self.chars.append(char)
        self.top, self.bottom = min(self.top, char.v0), max(self.bottom, char.v1)

    def _white(self, char: _Char) -> bool:
        """True if white as wide as a space stands before the char (for a space PDFium
        added): the letters don't touch, and across a change of baseline the white from
        where the letters so far end is at least `SPACE` em."""
        last = self.chars[-1]
        small = min(last.style[1], char.style[1]) or 1.0
        shifted = abs(char.base - last.base) > SHIFT * small
        if char.u0 - last.u1 <= 0:
            # letters that touch get no space, except a digit under a digit (a fraction 1/2
            # set as 1 over 2), which would read as one number, "12" (#128),
            # and a denominator under its numerator's bar ("1ℏ" for 1 over ℏ, #202)
            digits = last.text.isdigit() and char.text.isdigit()
            return shifted and (digits or self._across_bar(last, char))
        if not shifted:
            return True
        reach = max(last.u1, self.before)
        return char.u0 - reach >= SPACE * max(last.style[1], char.style[1], 1.0)

    def _across_bar(self, last: _Char, char: _Char) -> bool:
        """True if a fraction bar is drawn between the last char and the char under it."""
        size = max(last.style[1], char.style[1], 1.0)
        top = (last.box[1] + last.box[3]) / 2
        bottom = (char.box[1] + char.box[3]) / 2
        return any(
            _fraction_bar(bar, last.box, char.box, size) for bar in self.bars.between(top, bottom)
        )

    def stacks(self, char: _Char) -> bool:
        """True if the char starts back under the end of this line's letters and beside
        them, as a subscript stored after the superscript above it: at most `STACK` em back,
        and after the line's first letter, so the next printed line of a paragraph, whose
        loose boxes may overlap this one's, is no script (#128)."""
        reach = max(c.u1 for c in self.chars)
        size = max(self.chars[-1].style[1], char.style[1], 1.0)
        overlap = min(self.bottom, char.v1) - max(self.top, char.v0)
        back = reach - char.u0
        return self.chars[0].u0 < char.u0 and 0 < back <= STACK * size and overlap > 0


@dataclass(frozen=True)
class _Bars:
    """A page's drawings that could be fraction bars (wider than thick), as (x0, y0, x1, y1)
    sorted by their top, so a check looks only at those between two letters' middles: a
    page of a million drawings costs no more per letter (#185)."""

    boxes: tuple[tuple[float, float, float, float], ...] = ()
    tops: tuple[float, ...] = ()

    @staticmethod
    def of(drawings: Iterable[Drawing]) -> _Bars:
        boxes = sorted(
            ((d.box.x0, d.box.y0, d.box.x1, d.box.y1) for d in drawings),
            key=lambda box: box[1],
        )
        thin = tuple(b for b in boxes if b[2] - b[0] >= 3 * (b[3] - b[1]))
        return _Bars(thin, tuple(b[1] for b in thin))

    def between(self, top: float, bottom: float) -> tuple[tuple[float, float, float, float], ...]:
        """The bars whose top lies strictly between `top` and `bottom`."""
        return self.boxes[bisect_right(self.tops, top) : bisect_left(self.tops, bottom)]


def _fraction_bar(
    bar: tuple[float, float, float, float],
    upper: tuple[float, float, float, float],
    lower: tuple[float, float, float, float],
    size: float,
) -> bool:
    """True if the drawing is a fraction bar with `upper` over it and `lower` under it:
    at most `FRACTION_BAR` em thick and three times as wide, both boxes overlapping it
    across, their middles on either side of it and their edges within `FRACTION_REACH` em."""
    x0, y0, x1, y1 = bar
    thick = y1 - y0
    if thick > FRACTION_BAR * size or x1 - x0 < 3 * thick:
        return False
    if min(upper[2], x1) <= max(upper[0], x0) or min(lower[2], x1) <= max(lower[0], x0):
        return False
    if not (upper[1] + upper[3]) / 2 < y0 < y1 < (lower[1] + lower[3]) / 2:
        return False
    return y0 - upper[3] <= FRACTION_REACH * size and lower[1] - y1 <= FRACTION_REACH * size


def _lines(
    textpage: pdfium.PdfTextPage,
    frame: _Frame,
    number: int,
    bars: _Bars | None = None,
) -> tuple[tuple[TextLine, ...], int]:
    """The page's lines, and how many of their characters come from a font with no Unicode
    source (#442)."""
    lines: list[_Line] = []
    space: str | None = None
    unmapped = 0
    for char in _chars(textpage, frame):
        if isinstance(char, str):
            space = _SPACE if _SPACE in (space, char) else char
            continue
        if not (lines and lines[-1].accepts(char)):
            line = _Line(bars=bars or _Bars())
            if lines and lines[-1].stacks(char):
                line.before = max(c.u1 for c in lines[-1].chars)
            lines.append(line)
        lines[-1].add(char, space)
        unmapped += char.unmapped
        space = None
    placed = _accents_onto_letters(lines)
    return tuple(
        _text_line(line, f"p{number}-l{i}")
        for i, line in enumerate(lines, 1)
        if i - 1 not in placed  # the page keeps its numbering: the accent's id goes missing
    ), unmapped


def _accents_onto_letters(lines: list[_Line]) -> set[int]:
    """Each line that holds only spacing accents (one, or two stacked over one letter) is
    put onto the letters they stand over in the `ACCENT_LINES` lines stored before or after
    it (#125): for each accent, of the letters under it, the one overlapping it most across,
    so not a letter of the line under the accent's own, whose loose box may touch it (Chi p6
    "Doug" under "Marasovic,"); the nearest line stored wins a tie. A line is placed only if
    each of its accents finds a letter, so none is lost. The indexes of the lines placed."""
    placed: set[int] = set()
    for i, line in enumerate(lines):
        if not _only_accents(line):
            continue
        near = range(max(0, i - ACCENT_LINES), min(len(lines), i + ACCENT_LINES + 1))
        found = [_letter_under(accent, lines, near, i) for accent in line.chars]
        letters = [letter for letter in found if letter is not None]
        if len(letters) == len(line.chars):
            for accent, letter in zip(line.chars, letters, strict=True):
                letter.text = unicodedata.normalize("NFC", letter.text + _COMBINING[accent.text])
            placed.add(i)
    return placed


def _letter_under(accent: _Char, lines: list[_Line], near: range, i: int) -> _Char | None:
    found = [
        (_across(c, accent), -abs(j - i), c)
        for j in near
        if j != i
        for c in lines[j].chars
        if _under(c, accent)
    ]
    return max(found, key=lambda f: (f[0], f[1]))[2] if found else None


def _only_accents(line: _Line) -> bool:
    return bool(line.chars) and all(c.text in _COMBINING for c in line.chars)


def _under(letter: _Char, accent: _Char) -> bool:
    """True if the accent stands over (or, a cedilla, under) the letter: the letter's extent
    along the line holds the accent's middle, and across they overlap or stand at most
    `ACCENT_REACH` em apart."""
    if not _letter(letter.text):
        return False
    turn = abs(letter.angle - accent.angle)
    if min(turn, math.tau - turn) > 0.01:
        return False
    reach = ACCENT_REACH * max(letter.style[1], accent.style[1], 1.0)
    return (
        letter.u0 <= (accent.u0 + accent.u1) / 2 <= letter.u1 and _across(letter, accent) >= -reach
    )


def _letter(text: str) -> bool:
    """True if the text is one letter, with any accents already put onto it. A spacing
    accent is none, though `isalpha` holds for some (circumflex and caron are modifier letters): a
    second accent stacked over the same letter goes onto the letter, not onto the first
    accent, whose line is left out (#671)."""
    base, *marks = unicodedata.normalize("NFD", text) or " "
    return (
        text not in _COMBINING
        and base.isalpha()
        and all(unicodedata.combining(mark) for mark in marks)
    )


def _across(a: _Char, b: _Char) -> float:
    """How far the two characters overlap across the line (negative: the white between)."""
    return min(a.v1, b.v1) - max(a.v0, b.v0)


def _chars(textpage: pdfium.PdfTextPage, frame: _Frame) -> Iterator[_Char | str]:
    """Each character in stored order; `_SPACE` for a space or a line end between words
    that the file holds, `_GENERATED` for one PDFium added itself."""
    handle = textpage.raw
    name = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    rect = raw.FS_RECTF()
    matrix = raw.FS_MATRIX()
    origin_x, origin_y = ctypes.c_double(), ctypes.c_double()
    sourceless = _SourcelessFonts()
    for i in range(textpage.count_chars()):
        hyphen = raw.FPDFText_IsHyphen(handle, i) == 1
        text = _char_text(raw.FPDFText_GetUnicode(handle, i), hyphen)
        generated = raw.FPDFText_IsGenerated(handle, i) == 1
        if text is None or generated:
            yield _GENERATED if generated else _SPACE
            continue
        if not raw.FPDFText_GetLooseCharBox(handle, i, rect):
            continue
        coords = (*frame.point(rect.left, rect.top), *frame.point(rect.right, rect.bottom))
        if not all(math.isfinite(c) for c in coords):
            continue
        x0, y0 = min(coords[0], coords[2]), min(coords[1], coords[3])
        x1, y1 = max(coords[0], coords[2]), max(coords[1], coords[3])
        if not frame.shows(x0, y0, x1, y1):
            continue  # outside the crop box: not printed
        flags.value = 0
        needed = raw.FPDFText_GetFontInfo(handle, i, name, len(name), ctypes.byref(flags))
        if needed > len(name):
            name = ctypes.create_string_buffer(needed)
            needed = raw.FPDFText_GetFontInfo(handle, i, name, len(name), ctypes.byref(flags))
        # On failure the buffer still holds the previous character's font: don't inherit it.
        font = _SUBSET.sub("", name.value.decode("utf-8", errors="replace")) if needed else ""
        size = raw.FPDFText_GetFontSize(handle, i) * _scale(handle, i, matrix)
        size = round(size, 1) if math.isfinite(size) and size > 0 else 0.0
        bold, italic = _style(font, raw.FPDFText_GetFontWeight(handle, i), flags.value)
        angle = raw.FPDFText_GetCharAngle(handle, i)
        angle = frame.angle(angle if math.isfinite(angle) and angle >= 0 else 0.0)
        u0, v0, u1, v1 = _in_text_direction((x0, y0, x1, y1), angle)
        base = math.nan
        if raw.FPDFText_GetCharOrigin(handle, i, ctypes.byref(origin_x), ctypes.byref(origin_y)):
            origin = frame.point(origin_x.value, origin_y.value)
            base = _in_text_direction((*origin, *origin), angle)[1]
        style = (font, size, bold, italic)
        unmapped = bool(needed) and sourceless.has(handle, i, name.value)
        yield _Char(text, style, (x0, y0, x1, y1), angle, u0, u1, v0, v1, base, unmapped)


_SFNT = (b"\x00\x01\x00\x00", b"true", b"OTTO")  # TrueType and OpenType font programs
_UNICODE_TABLES = {b"cmap", b"post"}  # a program's own ways to name its glyphs


class _SourcelessFonts:
    """Which characters of a page come from a font with no Unicode source (#442): the
    font's embedded program is TrueType or OpenType without a cmap or a post table, and
    PDFium found no Unicode for the character (its map error: no ToUnicode map, and no
    encoding or glyph name it knows). Nothing in the file then says which letter a glyph
    is, and PDFium gives the glyph number as the character.

    The map error is asked first, for every character; a font is looked at (its program
    copied and its table directory read) only for a character PDFium could not map, and
    then once per page. Fonts are told apart by the name PDFium gives (a subset's name
    carries its own tag).

    Simple fonts with glyph names PDFium does not know (TeX's math fonts, matplotlib's Type 3
    fonts) are not counted: in the corpus they set symbols and correct text (D-762). Text
    that reads as nonsense from any font is what `extraction.legibility` finds."""

    def __init__(self) -> None:
        self._fonts: dict[bytes, bool] = {}  # by font name, for this page only

    def has(self, textpage: object, index: int, name: bytes) -> bool:
        """True if the character at `index`, whose font PDFium names `name`, comes from a
        font with no Unicode source."""
        if raw.FPDFText_HasUnicodeMapError(textpage, index) != 1:
            return False
        sourceless = self._fonts.get(name)
        if sourceless is None:
            sourceless = self._fonts[name] = _sourceless(textpage, index)
        return sourceless


def _sourceless(textpage: object, index: int) -> bool:
    """True if the font of the character at `index` is embedded as a TrueType or OpenType
    program without a cmap or a post table."""
    text = raw.FPDFText_GetTextObject(textpage, index)
    font = raw.FPDFTextObj_GetFont(text) if text else None
    if not font or raw.FPDFFont_GetIsEmbedded(font) != 1:
        return False
    return _names_no_glyph(_program(font))


def _program(font: object) -> bytes:
    """The font's program as PDFium decoded it; empty if it gives none."""
    size = ctypes.c_size_t()
    if not raw.FPDFFont_GetFontData(font, None, 0, ctypes.byref(size)) or not size.value:
        return b""
    buffer = (ctypes.c_ubyte * size.value)()
    if not raw.FPDFFont_GetFontData(font, buffer, size.value, ctypes.byref(size)):
        return b""
    return bytes(buffer)


def _names_no_glyph(program: bytes) -> bool:
    """True for a TrueType or OpenType program whose table directory holds neither a cmap
    nor a post table. Anything else, a damaged directory too, counts as naming its glyphs."""
    if program[:4] not in _SFNT:
        return False
    count = int.from_bytes(program[4:6], "big")
    end = 12 + 16 * count
    if count == 0 or len(program) < end:
        return False
    return not {program[i : i + 4] for i in range(12, end, 16)} & _UNICODE_TABLES


def _char_text(code: int, hyphen: bool) -> str | None:
    """The character's text, or None where it only separates words (a space, a line end)."""
    if code == _LINE_END_HYPHEN or (hyphen and code != ord(_SOFT_HYPHEN)):
        return "-"
    if code == ord(_SOFT_HYPHEN):
        return _SOFT_HYPHEN
    if not 0 < code < 0x110000:
        return _UNKNOWN  # code 0: a glyph without a Unicode mapping
    text = chr(code)
    if text.isspace() or not text.isprintable():
        return None
    return text


def _style(font: str, weight: int, flags: int) -> tuple[bool, bool]:
    """Bold and italic, from the font's weight and flags or, failing those, its name."""
    bold = weight >= BOLD_WEIGHT or bool(flags & _FORCE_BOLD_FLAG) or bool(_BOLD_NAME.search(font))
    italic = bool(flags & _ITALIC_FLAG) or bool(_ITALIC_NAME.search(font))
    return bold, italic


def _scale(handle: object, index: int, matrix: raw.FS_MATRIX) -> float:
    """How much the character's matrix scales its font size (1 when it doesn't).

    Only the height counts: a matrix that only stretches the text sideways (justified lines)
    leaves the size alone.
    """
    if not raw.FPDFText_GetMatrix(handle, index, matrix):
        return 1.0
    scale = math.hypot(matrix.c, matrix.d)
    return scale if math.isfinite(scale) and scale > 0 else 1.0


def _in_text_direction(box: tuple[float, float, float, float], angle: float) -> tuple[float, ...]:
    """The box turned so the text runs left to right: (u0, v0, u1, v1)."""
    cos, sin = math.cos(angle), math.sin(angle)
    corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    # PDFium turns text clockwise; with y pointing down it runs along (cos, sin).
    us = [x * cos + y * sin for x, y in corners]
    vs = [y * cos - x * sin for x, y in corners]
    return min(us), min(vs), max(us), max(vs)


def _text_line(line: _Line, line_id: str) -> TextLine:
    runs: list[TextRun] = []
    text, boxes = "", []
    style = line.chars[0].style
    for i, char in enumerate(line.chars):
        if char.style != style:
            runs.append(_run(text, style, boxes))
            text, boxes, style = "", [], char.style
        text += (" " if i in line.spaces else "") + char.text
        boxes.append(char.box)
    runs.append(_run(text, style, boxes))
    return TextLine(line_id, tuple(runs), _union([run.box for run in runs if run.box]))


def _run(text: str, style: tuple[str, float, bool, bool], boxes: list) -> TextRun:
    font, size, bold, italic = style
    return TextRun(text, font, size, bold, italic, _union([Box(*b) for b in boxes]))


def _union(boxes: list[Box]) -> Box:
    return Box(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


_Matrix = tuple[float, float, float, float, float, float]
_IDENTITY: _Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _graphics(
    page: pdfium.PdfPage, frame: _Frame, number: int, name: str, before: int
) -> tuple[tuple[Picture, ...], tuple[Drawing, ...]]:
    """Pictures and visible vector drawings, also those inside form XObjects; the file is
    refused as soon as the page holds more than `MAX_PAGE_GRAPHICS`, or the file with the
    `before` of earlier pages more than `MAX_GRAPHICS` (D-581)."""
    pictures: list[Picture] = []
    drawings: list[Drawing] = []
    handles = [
        raw.FPDFPage_GetObject(page.raw, i) for i in range(raw.FPDFPage_CountObjects(page.raw))
    ]
    for handle, matrix in _walk(handles, _IDENTITY):
        kind = raw.FPDFPageObj_GetType(handle)
        if kind not in (raw.FPDF_PAGEOBJ_IMAGE, raw.FPDF_PAGEOBJ_PATH, raw.FPDF_PAGEOBJ_SHADING):
            continue
        if kind == raw.FPDF_PAGEOBJ_PATH and not _visible(handle):
            continue
        box = _bounds(handle, matrix, frame)
        if box is None or not frame.shows(box.x0, box.y0, box.x1, box.y1):
            continue
        found = len(pictures) + len(drawings) + 1
        if found > MAX_PAGE_GRAPHICS:
            detail = f"page {number} holds more than {MAX_PAGE_GRAPHICS:,} drawings and pictures"
            raise _too_large(name, detail)
        if before + found > MAX_GRAPHICS:
            raise _too_large(name, f"more than {MAX_GRAPHICS:,} drawings and pictures")
        if kind == raw.FPDF_PAGEOBJ_IMAGE:
            pictures.append(Picture(f"p{number}-i{len(pictures) + 1}", box))
        else:
            drawings.append(Drawing(f"p{number}-d{len(drawings) + 1}", box))
    return tuple(pictures), tuple(drawings)


def _walk(handles: list, matrix: _Matrix, depth: int = 0) -> Iterator[tuple[object, _Matrix]]:
    for handle in handles:
        if raw.FPDFPageObj_GetType(handle) != raw.FPDF_PAGEOBJ_FORM:
            yield handle, matrix
        elif depth < 8:  # forms inside forms; deeper nesting is a damaged or hostile file
            inner = raw.FS_MATRIX()
            raw.FPDFPageObj_GetMatrix(handle, inner)
            own = (inner.a, inner.b, inner.c, inner.d, inner.e, inner.f)
            count = raw.FPDFFormObj_CountObjects(handle)
            children = [raw.FPDFFormObj_GetObject(handle, i) for i in range(count)]
            yield from _walk(children, _compose(own, matrix), depth + 1)


def _compose(first: _Matrix, then: _Matrix) -> _Matrix:
    a, b, c, d, e, f = first
    a2, b2, c2, d2, e2, f2 = then
    return (
        a * a2 + b * c2,
        a * b2 + b * d2,
        c * a2 + d * c2,
        c * b2 + d * d2,
        e * a2 + f * c2 + e2,
        e * b2 + f * d2 + f2,
    )


def _visible(path: object) -> bool:
    fill, stroke = ctypes.c_int(), ctypes.c_int()
    if not raw.FPDFPath_GetDrawMode(path, ctypes.byref(fill), ctypes.byref(stroke)):
        return False
    return fill.value != 0 or bool(stroke.value)


def _bounds(handle: object, matrix: _Matrix, frame: _Frame) -> Box | None:
    left, bottom, right, top = (ctypes.c_float() for _ in range(4))
    if not raw.FPDFPageObj_GetBounds(
        handle, ctypes.byref(left), ctypes.byref(bottom), ctypes.byref(right), ctypes.byref(top)
    ):
        return None
    a, b, c, d, e, f = matrix
    corners = [
        (x * a + y * c + e, x * b + y * d + f)
        for x in (left.value, right.value)
        for y in (bottom.value, top.value)
    ]
    points = [frame.point(x, y) for x, y in corners]
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    if not all(math.isfinite(v) for v in xs + ys):
        return None
    return Box(min(xs), min(ys), max(xs), max(ys))
