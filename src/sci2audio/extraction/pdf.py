"""Record what a PDF holds as `Content`, with pypdfium2, deciding nothing (D-63, D-65).

Characters become styled runs, runs become lines, and lines, pictures and drawings keep their
boxes and the order the file stores them in. The bookmarks become the outline, as stored (#24).
Reading order, headings and page furniture are the layout stage's work. Coordinates are points
with the origin at the top left of the page.

PDFium crashes when two threads call it at once, even for different files, so every call goes
through `_PDFIUM`: the one piece of global state this stage has (KB audit "PDFium thread-safety
crash", D-65).
"""

from __future__ import annotations

import ctypes
import hashlib
import math
import re
import threading
from collections.abc import Iterator
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

_PDFIUM = threading.Lock()

LINE_GAP = 1.0  # a gap this many em wide ends a line, so columns and table cells stay apart
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


class ExtractionError(Exception):
    """A file that cannot be read, with a message a user can act on."""


def extract_pdf(path: Path) -> Content:
    """Read the PDF at `path` into `Content`; raise ExtractionError if it can't be read."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ExtractionError(f"{path.name}: cannot be opened ({error.strerror})") from error
    return read_pdf(data, path.name)


def read_pdf(data: bytes, name: str) -> Content:
    """Read PDF bytes into `Content`; `name` is the bare file name the source keeps."""
    if not data:
        raise ExtractionError(f"{name}: the file is empty")
    source = Source(name, SourceFormat.PDF, sha256=hashlib.sha256(data).hexdigest())
    with _PDFIUM:
        try:
            document = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as error:
            raise ExtractionError(_load_message(name, data, str(error))) from error
        try:
            if len(document) == 0:
                raise ExtractionError(f"{name}: the PDF has no pages")
            pages = tuple(_page(document, index) for index in range(len(document)))
            metadata = _metadata(document)
            outline = _outline(document, len(pages))
        except pdfium.PdfiumError as error:
            raise ExtractionError(f"{name}: the PDF is damaged ({error})") from error
        finally:
            document.close()
    return Content(source=source, pages=pages, metadata=metadata, outline=outline)


def _load_message(name: str, data: bytes, detail: str) -> str:
    # PDFium's error code can be left over from an earlier file (it isn't reset on every
    # failure), so a password is only blamed when the file really is encrypted.
    if "password" in detail.lower() and b"/Encrypt" in data:
        return f"{name}: the PDF is password-protected; remove the password and try again"
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
    return buffer.raw[: size - 2].decode("utf-16-le", errors="replace").strip()


def _page(document: pdfium.PdfDocument, index: int) -> Page:
    page = document[index]
    try:
        width, height = page.get_size()
        number = index + 1
        textpage = page.get_textpage()
        try:
            lines = _lines(textpage, height, number)
        finally:
            textpage.close()
        pictures, drawings = _graphics(page, height, number)
    finally:
        page.close()
    return Page(number, lines, pictures, drawings, width=width, height=height)


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


@dataclass
class _Line:
    chars: list[_Char] = field(default_factory=list)
    spaces: set[int] = field(default_factory=set)  # a space goes before chars[i]
    top: float = math.inf  # extent across the line so far
    bottom: float = -math.inf

    def accepts(self, char: _Char) -> bool:
        last = self.chars[-1]
        if abs(char.angle - last.angle) > 0.01:
            return False
        size = max(last.style[1], char.style[1], 1.0)
        if char.u0 < last.u0 - 0.5 * size or char.u0 - last.u1 > LINE_GAP * size:
            return False  # back to the start of a line, or a wide gap: a new line
        overlap = min(self.bottom, char.v1) - max(self.top, char.v0)
        return overlap >= SAME_LINE * min(self.bottom - self.top, char.v1 - char.v0)

    def add(self, char: _Char, space: bool) -> None:
        if space and self.chars:
            self.spaces.add(len(self.chars))
        self.chars.append(char)
        self.top, self.bottom = min(self.top, char.v0), max(self.bottom, char.v1)


def _lines(textpage: pdfium.PdfTextPage, height: float, number: int) -> tuple[TextLine, ...]:
    lines: list[_Line] = []
    space = False
    for char in _chars(textpage, height):
        if char is None:
            space = True
            continue
        if not (lines and lines[-1].accepts(char)):
            lines.append(_Line())
        lines[-1].add(char, space)
        space = False
    return tuple(_text_line(line, f"p{number}-l{i}") for i, line in enumerate(lines, 1))


def _chars(textpage: pdfium.PdfTextPage, height: float) -> Iterator[_Char | None]:
    """Each character in stored order; None for a space or a line end between words."""
    handle = textpage.raw
    name = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    rect = raw.FS_RECTF()
    matrix = raw.FS_MATRIX()
    for i in range(textpage.count_chars()):
        hyphen = raw.FPDFText_IsHyphen(handle, i) == 1
        text = _char_text(raw.FPDFText_GetUnicode(handle, i), hyphen)
        if text is None or raw.FPDFText_IsGenerated(handle, i) == 1:
            yield None
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
        yield _Char(text, (font, size, bold, italic), (x0, y0, x1, y1), angle, u0, u1, v0, v1)


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
    page: pdfium.PdfPage, height: float, number: int
) -> tuple[tuple[Picture, ...], tuple[Drawing, ...]]:
    """Pictures and visible vector drawings, also those inside form XObjects."""
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
