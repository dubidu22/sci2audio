"""Make small PDFs for extraction tests with pypdfium2, so each case shows one thing.

Positions are given like `core.Box`: points from the top left of the page.
"""

from __future__ import annotations

import ctypes
import io
from dataclasses import dataclass

import pypdfium2 as pdfium
import pypdfium2.raw as raw

WIDTH, HEIGHT = 600.0, 800.0


@dataclass(frozen=True)
class Text:
    text: str
    x: float  # where the baseline starts, from the top left
    y: float
    font: str = "Helvetica"  # one of the 14 standard PDF fonts
    size: float = 10.0
    turned: bool = False  # turned a quarter left, reading upwards (an arXiv side stamp)


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float


def make_pdf(*pages: list[Text | Rect]) -> bytes:
    """A PDF with one page per list, each holding the given texts and filled rectangles."""
    document = pdfium.PdfDocument.new()
    for items in pages:
        page = document.new_page(WIDTH, HEIGHT)
        for item in items:
            obj = _text(document, item) if isinstance(item, Text) else _rect(item)
            raw.FPDFPage_InsertObject(page.raw, obj)
        raw.FPDFPage_GenerateContent(page.raw)
        page.close()
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def _text(document: pdfium.PdfDocument, item: Text) -> object:
    font = raw.FPDFText_LoadStandardFont(document.raw, item.font.encode())
    obj = raw.FPDFPageObj_CreateTextObj(document.raw, font, item.size)
    encoded = ctypes.create_string_buffer((item.text + "\0").encode("utf-16-le"))
    raw.FPDFText_SetText(obj, ctypes.cast(encoded, raw.FPDF_WIDESTRING))
    if item.turned:
        raw.FPDFPageObj_Transform(obj, 0, 1, -1, 0, item.x, HEIGHT - item.y)
    else:
        raw.FPDFPageObj_Transform(obj, 1, 0, 0, 1, item.x, HEIGHT - item.y)
    return obj


def _rect(item: Rect) -> object:
    obj = raw.FPDFPageObj_CreateNewRect(
        item.x0, HEIGHT - item.y1, item.x1 - item.x0, item.y1 - item.y0
    )
    raw.FPDFPath_SetDrawMode(obj, raw.FPDF_FILLMODE_ALTERNATE, False)
    return obj


def in_form(data: bytes, scale: float, dx: float, dy: float) -> bytes:
    """The first page of `data` placed, scaled and moved, as a form XObject on a new page.

    `dx` and `dy` move it in PDF space (y upwards), as the form's matrix does.
    """
    source = pdfium.PdfDocument(data)
    document = pdfium.PdfDocument.new()
    form = raw.FPDF_NewFormObjectFromXObject(
        raw.FPDF_NewXObjectFromPage(document.raw, source.raw, 0)
    )
    raw.FPDFPageObj_Transform(form, scale, 0, 0, scale, dx, dy)
    page = document.new_page(WIDTH, HEIGHT)
    raw.FPDFPage_InsertObject(page.raw, form)
    raw.FPDFPage_GenerateContent(page.raw)
    page.close()
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    source.close()
    return buffer.getvalue()


@dataclass(frozen=True)
class Mark:
    """A bookmark for `outlined_pdf`. `title` as text is stored in UTF-16 with a byte-order
    mark; as bytes it is stored as it is (PDFDocEncoding). `page` counts from 1; a page the
    file does not have points at a missing object. `goto` stores the target as a GoTo action
    instead of a destination; `loop` makes the bookmark's first child its own parent."""

    title: str | bytes
    page: int | None = None
    children: tuple[Mark, ...] = ()
    goto: bool = False
    loop: bool = False  # its /First and /Last point back at its parent, as in a damaged file


def outlined_pdf(pages: int, marks: tuple[Mark, ...], *, circular: bool = False) -> bytes:
    """A PDF written object by object, with `pages` pages of one Helvetica line each and the
    bookmarks `marks`; pypdfium2 cannot write bookmarks. With `circular`, the last top
    bookmark's /Next points back at the first, as in a damaged file."""
    objects: dict[int, bytes] = {}
    first_page = 4
    kids = " ".join(f"{first_page + 2 * i} 0 R" for i in range(pages))
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R /Outlines 3 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode()
    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for i in range(pages):
        number = first_page + 2 * i
        stream = f"BT /F1 12 Tf 72 720 Td (Page {i + 1}) Tj ET".encode()
        objects[number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {WIDTH:g} {HEIGHT:g}]"
            f" /Resources << /Font << /F1 {font} >> >> /Contents {number + 1} 0 R >>"
        ).encode()
        objects[number + 1] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
    numbers = iter(range(first_page + 2 * pages, 1_000_000))

    def target(mark: Mark) -> str:
        if mark.page is None:
            return ""
        page = first_page + 2 * (mark.page - 1) if mark.page <= pages else 999
        dest = f"[{page} 0 R /XYZ 72 750 0]"
        return f" /A << /S /GoTo /D {dest} >>" if mark.goto else f" /Dest {dest}"

    def title(mark: Mark) -> str:
        data = mark.title if isinstance(mark.title, bytes) else mark.title.encode("utf-16")
        if not isinstance(mark.title, bytes) and not data.startswith(b"\xfe\xff"):
            data = b"\xfe\xff" + mark.title.encode("utf-16-be")
        return f"<{data.hex()}>"

    def write(marks: tuple[Mark, ...], parent: int, loop: bool) -> tuple[int, int]:
        ids = [next(numbers) for _ in marks]
        for k, (mark, own) in enumerate(zip(marks, ids, strict=True)):
            links = f" /Parent {parent} 0 R"
            if k > 0:
                links += f" /Prev {ids[k - 1]} 0 R"
            if k + 1 < len(ids):
                links += f" /Next {ids[k + 1]} 0 R"
            elif loop:
                links += f" /Next {ids[0]} 0 R"
            if mark.children:
                first, last = write(mark.children, own, loop=False)
                links += f" /First {first} 0 R /Last {last} 0 R /Count {len(mark.children)}"
            elif mark.loop:
                links += f" /First {parent} 0 R /Last {parent} 0 R /Count 1"
            objects[own] = f"<< /Title {title(mark)}{links}{target(mark)} >>".encode()
        return ids[0], ids[-1]

    outline = "<< /Type /Outlines >>"
    if marks:
        first, last = write(marks, 3, circular)
        outline = f"<< /Type /Outlines /First {first} 0 R /Last {last} 0 R /Count {len(marks)} >>"
    objects[3] = outline.encode()
    out = io.BytesIO()
    out.write(b"%PDF-1.7\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = out.tell()
        out.write(b"%d 0 obj\n%s\nendobj\n" % (number, objects[number]))
    start = out.tell()
    size = max(objects) + 1
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % size)
    for number in range(1, size):
        if number in offsets:
            out.write(b"%010d 00000 n \n" % offsets[number])
        else:
            out.write(b"0000000000 65535 f \n")
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, start))
    return out.getvalue()
