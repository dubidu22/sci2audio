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


def width(text: str, font: str = "Helvetica", size: float = 10.0) -> float:
    """How wide the text is set, in points, to place the next piece right after it."""
    document = pdfium.PdfDocument.new()
    obj = _text(document, Text(text, 0.0, 0.0, font, size))
    left, bottom, right, top = (ctypes.c_float() for _ in range(4))
    raw.FPDFPageObj_GetBounds(
        obj, ctypes.byref(left), ctypes.byref(bottom), ctypes.byref(right), ctypes.byref(top)
    )
    raw.FPDFPageObj_Destroy(obj)
    document.close()
    return right.value - left.value


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
