"""Record what a PDF holds as `Content`, with pypdfium2, deciding nothing (D-63, D-65).

Characters become styled runs, runs become lines, and lines, pictures and drawings keep their
boxes and the order the file stores them in. The bookmarks become the outline, as stored (#24).
Reading order, headings and page furniture are the layout stage's work. Coordinates are points
with the origin at the top left of the page.

PDFium crashes when two threads call it at once, even for different files, so every call goes
through `_PDFIUM`: the one piece of global state this stage has (KB audit "PDFium thread-safety
crash", D-65).

A file from a user is read in a child process (`extract_pdf`, `extract_pdf_cover`; #185, #28,
D-581): PDFium decodes streams and loads pages before our limits can count anything, so the
child has a memory limit (`MAX_MEMORY`) and a time limit for each step (`STEP_SECONDS`), and
a crash inside PDFium ends only the child. Each read has its own process, so two reads no
longer wait for each other's lock; at most `MAX_PDF_READERS` children run at once. The child
reports each page it starts ("page 3 of 400"), which `extract_pdf` hands on as progress
(#343), and a cancelled read ends the child at once (#344).
`read_pdf` reads bytes in this process, without those limits: it is the child's own work.
"""

from __future__ import annotations

import ctypes
import hashlib
import math
import re
import threading
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
# over 5 pt letters is 0.16 em, so the limit leaves room above that (review R1-2 of #323).
FRACTION_BAR = 0.25  # em of the larger letter: a fraction bar is at most this thick ...
FRACTION_REACH = 0.6  # em: ... with numerator and denominator at most this far from it
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
# a long run of digits or white space costs one pass, not one per start (review M2 of #188).
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
) -> object:
    try:
        return isolate.run(
            target,  # type: ignore[arg-type]
            (path, {name: globals()[name] for name in _LIMITS}),
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
    """True if the file starts like a PDF but its end is missing (D-395, as applied after
    review rounds 1 and 2 of #188): object data follows its last %%EOF, so the cut fell
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
            textpage = page.get_textpage()
            try:
                count = textpage.count_chars()
                if count > MAX_PAGE_CHARS:
                    detail = f"page {number} holds more than {MAX_PAGE_CHARS:,} characters"
                    raise _too_large(name, detail)
                total += max(count, 0)
                if total > MAX_CHARS:
                    raise _too_large(name, f"more than {MAX_CHARS:,} characters")
                pictures, drawings = _graphics(page, height, number, name, graphics)
                graphics += len(pictures) + len(drawings)
                lines = _lines(textpage, height, number, _Bars.of(drawings))
            finally:
                textpage.close()
        finally:
            page.close()
        pages.append(Page(number, lines, pictures, drawings, width=width, height=height))
    return tuple(pages)


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
        if abs(char.angle - last.angle) > 0.01:
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
            # set as 1 over 2), which would read as one number, "12" (review M2 of #128),
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
        loose boxes may overlap this one's, is no script (review M1 of #128)."""
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
    height: float,
    number: int,
    bars: _Bars | None = None,
) -> tuple[TextLine, ...]:
    lines: list[_Line] = []
    space: str | None = None
    for char in _chars(textpage, height):
        if isinstance(char, str):
            space = _SPACE if _SPACE in (space, char) else char
            continue
        if not (lines and lines[-1].accepts(char)):
            line = _Line(bars=bars or _Bars())
            if lines and lines[-1].stacks(char):
                line.before = max(c.u1 for c in lines[-1].chars)
            lines.append(line)
        lines[-1].add(char, space)
        space = None
    return tuple(_text_line(line, f"p{number}-l{i}") for i, line in enumerate(lines, 1))


def _chars(textpage: pdfium.PdfTextPage, height: float) -> Iterator[_Char | str]:
    """Each character in stored order; `_SPACE` for a space or a line end between words
    that the file holds, `_GENERATED` for one PDFium added itself."""
    handle = textpage.raw
    name = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    rect = raw.FS_RECTF()
    matrix = raw.FS_MATRIX()
    origin_x, origin_y = ctypes.c_double(), ctypes.c_double()
    for i in range(textpage.count_chars()):
        hyphen = raw.FPDFText_IsHyphen(handle, i) == 1
        text = _char_text(raw.FPDFText_GetUnicode(handle, i), hyphen)
        generated = raw.FPDFText_IsGenerated(handle, i) == 1
        if text is None or generated:
            yield _GENERATED if generated else _SPACE
            continue
        if not raw.FPDFText_GetLooseCharBox(handle, i, rect):
            continue
        left, right, bottom, top = rect.left, rect.right, rect.bottom, rect.top
        coords = (left, height - top, right, height - bottom)
        if not all(math.isfinite(c) for c in coords):
            continue
        x0, y0 = min(coords[0], coords[2]), min(coords[1], coords[3])
        x1, y1 = max(coords[0], coords[2]), max(coords[1], coords[3])
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
        angle = angle if math.isfinite(angle) and angle >= 0 else 0.0
        u0, v0, u1, v1 = _in_text_direction((x0, y0, x1, y1), angle)
        base = math.nan
        if raw.FPDFText_GetCharOrigin(handle, i, ctypes.byref(origin_x), ctypes.byref(origin_y)):
            origin = (origin_x.value, height - origin_y.value)
            base = _in_text_direction((*origin, *origin), angle)[1]
        style = (font, size, bold, italic)
        yield _Char(text, style, (x0, y0, x1, y1), angle, u0, u1, v0, v1, base)


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
    page: pdfium.PdfPage, height: float, number: int, name: str, before: int
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
        box = _bounds(handle, matrix, height)
        if box is None:
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


def _bounds(handle: object, matrix: _Matrix, height: float) -> Box | None:
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
    xs = [x for x, _ in corners]
    ys = [height - y for _, y in corners]
    if not all(math.isfinite(v) for v in xs + ys):
        return None
    return Box(min(xs), min(ys), max(xs), max(ys))
