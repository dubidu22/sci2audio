"""Make small PDFs for extraction tests, so each case shows one thing: with pypdfium2, or
written object by object (`raw_pdf`) where PDFium can't write what the case needs (bookmarks,
metadata, encryption, damage).

Positions are given like `core.Box`: points from the top left of the page.
"""

from __future__ import annotations

import ctypes
import hashlib
import io
import zlib
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
    return raw_pdf(objects)


def raw_pdf(objects: dict[int, bytes], *, trailer: bytes = b"", xref: bool = True) -> bytes:
    """A PDF written object by object: `objects` maps an object number to its body, and
    object 1 is the catalog. The cross-reference table gives each object's true offset;
    `trailer` adds entries to the trailer (an /Encrypt, an /ID). Without `xref` the file
    has no table at all, as a damaged file, and PDFium has to rebuild it."""
    out = io.BytesIO()
    out.write(b"%PDF-1.7\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = out.tell()
        out.write(b"%d 0 obj\n%s\nendobj\n" % (number, objects[number]))
    start = out.tell()
    size = max(objects) + 1
    if xref:
        out.write(b"xref\n0 %d\n0000000000 65535 f \n" % size)
        for number in range(1, size):
            if number in offsets:
                out.write(b"%010d 00000 n \n" % offsets[number])
            else:
                out.write(b"0000000000 65535 f \n")
    extra = b" " + trailer if trailer else b""
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R%s >>\nstartxref\n%d\n%%%%EOF\n" % (size, extra, start)
    )
    return out.getvalue()


def stream(data: bytes, entries: bytes = b"", *, compress: bool = False) -> bytes:
    """The body of a stream object holding `data`, Flate-compressed if `compress`;
    `entries` adds to its dictionary (an image's /Width, a form's /BBox)."""
    if compress:
        data = zlib.compress(data, 9)
        entries += b" /Filter /FlateDecode"
    return b"<< /Length %d%s >>\nstream\n%s\nendstream" % (
        len(data),
        b" " + entries.strip() if entries.strip() else b"",
        data,
    )


# The padding string of the standard security handler (PDF 32000-1, 7.6.3.3, algorithm 2)
_PAD = bytes.fromhex("28bf4e5e4e758a4164004e56fffa01082e2e00b6d0683e802f0ca9fe6453697a")


def _md5(data: bytes) -> bytes:
    return hashlib.md5(data, usedforsecurity=False).digest()  # the PDF standard's hash


def _rc4(key: bytes, data: bytes) -> bytes:
    box = list(range(256))
    j = 0
    for i in range(256):
        j = (j + box[i] + key[i % len(key)]) % 256
        box[i], box[j] = box[j], box[i]
    out, i, j = bytearray(), 0, 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + box[i]) % 256
        box[i], box[j] = box[j], box[i]
        out.append(byte ^ box[(box[i] + box[j]) % 256])
    return bytes(out)


def owner_locked_pdf(text: str, permissions: int, revision: int = 3) -> bytes:
    """A one-page PDF with `text`, encrypted by the standard security handler with RC4, an
    owner password and an empty user password, so it opens without a password but carries
    `permissions` (the /P bits). Revision 2 uses a 40-bit key, revision 3 a 128-bit key.
    pikepdf and qpdf always allow accessibility from revision 3 on, so these files are made
    here (algorithms 2, 3 and 4 or 5 of PDF 32000-1, 7.6.3)."""
    length = 5 if revision == 2 else 16
    rounds = 0 if revision == 2 else 50
    file_id = _md5(text.encode())
    p = permissions - (1 << 32) if permissions >= 1 << 31 else permissions
    p_bytes = (p & 0xFFFFFFFF).to_bytes(4, "little")

    owner_key = _md5(_PAD)  # owner password "" too: only /P protects
    for _ in range(rounds):
        owner_key = _md5(owner_key[:length])
    owner = _rc4(owner_key[:length], _PAD)
    if revision >= 3:
        for i in range(1, 20):
            owner = _rc4(bytes(b ^ i for b in owner_key[:length]), owner)

    key = _md5(_PAD + owner + p_bytes + file_id)
    for _ in range(rounds):
        key = _md5(key[:length])
    key = key[:length]
    if revision == 2:
        user = _rc4(key, _PAD)
    else:
        user = _rc4(key, _md5(_PAD + file_id))
        for i in range(1, 20):
            user = _rc4(bytes(b ^ i for b in key), user)
        user += bytes(16)

    content = f"BT /F1 12 Tf 20 150 Td ({text}) Tj ET".encode()
    object_key = _md5(key + (4).to_bytes(3, "little") + bytes(2))
    secret = _rc4(object_key[: min(length + 5, 16)], content)
    bits = length * 8
    return raw_pdf(
        {
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200]"
            b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            4: stream(secret),
            5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            6: b"<< /Filter /Standard /V %d /R %d /Length %d /O <%s> /U <%s> /P %d >>"
            % (
                1 if revision == 2 else 2,
                revision,
                bits,
                owner.hex().encode(),
                user.hex().encode(),
                p,
            ),
        },
        trailer=b"/Encrypt 6 0 R /ID [<%s> <%s>]"
        % (file_id.hex().encode(), file_id.hex().encode()),
    )


# Hand-written PDFs for the broken-file tests (#5): each shows one way a file can be damaged
# or hostile, in a few hundred bytes.

_HELVETICA = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
_PAGE = b"<< /Type /Page /Parent 2 0 R /MediaBox %s /Resources %s /Contents 4 0 R%s >>"


def one_page_pdf(
    content: bytes = b"BT /F1 12 Tf 72 720 Td (Hello world) Tj ET",
    *,
    media_box: bytes = b"[0 0 612 792]",
    page: bytes = b"",
    compress: bool = False,
    extra: dict[int, bytes] | None = None,
    resources: bytes = b"<< /Font << /F1 5 0 R >> >>",
    trailer: bytes = b"",
    xref: bool = True,
) -> bytes:
    """One page drawing `content` with Helvetica as /F1; `page` adds entries to the page,
    `extra` adds objects from number 6 on."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: _PAGE % (media_box, resources, b" " + page if page else b""),
        4: stream(content, compress=compress),
        5: _HELVETICA,
        **(extra or {}),
    }
    return raw_pdf(objects, trailer=trailer, xref=xref)


def image_only_pdf(*, ocr_text: str | None = None) -> bytes:
    """A page holding only a grey picture, as a scan without a text layer; with `ocr_text`,
    the text is laid over it invisibly (text render mode 3), as text recognition does."""
    picture = stream(
        b"\x80" * 100 * 100,
        b"/Type /XObject /Subtype /Image /Width 100 /Height 100"
        b" /ColorSpace /DeviceGray /BitsPerComponent 8",
    )
    content = b"q 500 0 0 700 50 50 cm /Im1 Do Q"
    if ocr_text is not None:
        content += b" BT 3 Tr /F1 12 Tf 72 720 Td (%s) Tj ET" % ocr_text.encode()
    return one_page_pdf(
        content,
        resources=b"<< /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >>",
        extra={6: picture},
    )


def page_tree_bomb(levels: int) -> bytes:
    """2 ** levels pages from a file of about 100 bytes per level: each node of the page
    tree names the node below it twice, so the nodes are shared, not copied."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        4: stream(b"BT /F1 12 Tf 72 720 Td (Hello world) Tj ET"),
        5: _HELVETICA,
    }
    below = 3
    for level in range(levels):
        number = 10 + level
        objects[number] = b"<< /Type /Pages /Kids [%d 0 R %d 0 R] /Count %d >>" % (
            below,
            below,
            2 ** (level + 1),
        )
        below = number
    objects[2] = b"<< /Type /Pages /Kids [%d 0 R] /Count %d >>" % (below, 2**levels)
    return raw_pdf(objects)


def dense_pdf(pages: int, chars: int) -> bytes:
    """`pages` pages sharing one compressed content stream of `chars` letters, in rows of
    1,000 tiny letters: a few KB that hold `pages` times `chars` characters."""
    rows, rest = divmod(chars, 1000)
    row = b"(" + b"a" * 1000 + b") Tj 0 -2 Td\n"
    content = b"BT /F1 2 Tf 10 780 Td " + row * rows
    content += b"(" + b"a" * rest + b") Tj ET" if rest else b"ET"
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % (10 + i) for i in range(pages)), pages),
        4: stream(content, compress=True),
        5: _HELVETICA,
    }
    for i in range(pages):
        objects[10 + i] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        )
    return raw_pdf(objects)


def protected_pdf(handler: bytes) -> bytes:
    """A page encrypted by a security handler PDFium does not have: `handler` is the
    /Encrypt dictionary's /Filter and the entries after it (a DRM plug-in, a certificate)."""
    return one_page_pdf(
        extra={6: b"<< /Filter " + handler + b" >>"},
        trailer=b"/Encrypt 6 0 R /ID [<0102> <0102>]",
    )
