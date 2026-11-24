"""Make small PDFs for extraction tests, so each case shows one thing: with pypdfium2, or
written object by object (`raw_pdf`) where PDFium can't write what the case needs (bookmarks,
metadata, encryption, damage).

Positions are given like `core.Box`: points from the top left of the page.
"""

from __future__ import annotations

import ctypes
import hashlib
import io
import random
import re
import struct
import zlib
from dataclasses import dataclass, replace
from pathlib import Path

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


_FILE_ID = re.compile(rb"/ID\[<([0-9A-F]+)><([0-9A-F]+)>\]")
_CREATED = re.compile(rb"/CreationDate\(D:\d{14}[^)]*\)")
FIXED_DATE = b"/CreationDate(D:20200101000000+00'00')"


def steady(data: bytes) -> bytes:
    """`data` (a PDF from `make_pdf`) with a fixed creation date and its file /ID made from
    its own content: PDFium stamps the time to the second and writes a random /ID, so the
    same pages give other bytes, and another SHA-256, on every call (#422). Both keep their
    length, so no offset moves."""
    created = _CREATED.search(data)
    if created is None or len(created.group(0)) != len(FIXED_DATE):
        raise ValueError("no creation date of the expected length to replace")
    data = data[: created.start()] + FIXED_DATE + data[created.end() :]
    found = _FILE_ID.search(data)
    if found is None:
        raise ValueError("no file /ID to replace")
    size = len(found.group(1))
    rest = data[: found.start()] + data[found.end() :]
    digest = hashlib.sha256(rest).hexdigest().upper()[:size].encode()
    return data[: found.start()] + b"/ID[<%s><%s>]" % (digest, digest) + data[found.end() :]


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


def cropped(
    data: bytes,
    crop: tuple[float, float, float, float],
    media: tuple[float, float, float, float] | None = None,
) -> bytes:
    """`data` with every page's /CropBox (and /MediaBox, if given) set, in PDF space: left,
    bottom, right, top, y upwards. A journal page cut from a larger sheet looks like this
    (#458)."""
    document = pdfium.PdfDocument(data)
    for index in range(len(document)):
        page = document[index]
        if media is not None:
            page.set_mediabox(*media)
        page.set_cropbox(*crop)
        page.close()
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    return buffer.getvalue()


def turned(data: bytes, turn: int) -> bytes:
    """`data` with every page stored unturned and shown through /Rotate `turn` (90, 180 or
    270, clockwise): each page is placed as a form XObject on a page of the unturned size,
    turned back the other way, so the page as shown is the page of `data` (#537)."""
    source = pdfium.PdfDocument(data)
    document = pdfium.PdfDocument.new()
    for index in range(len(source)):
        width, height = source[index].get_size()
        # x' = a x + c y + e, y' = b x + d y + f: the shown page's point on the unturned page
        a, b, c, d, e, f = {
            90: (0, 1, -1, 0, height, 0),
            180: (-1, 0, 0, -1, width, height),
            270: (0, -1, 1, 0, 0, width),
        }[turn]
        form = raw.FPDF_NewFormObjectFromXObject(
            raw.FPDF_NewXObjectFromPage(document.raw, source.raw, index)
        )
        raw.FPDFPageObj_Transform(form, a, b, c, d, e, f)
        page = document.new_page(*((height, width) if turn in (90, 270) else (width, height)))
        raw.FPDFPage_InsertObject(page.raw, form)
        raw.FPDFPage_GenerateContent(page.raw)
        page.set_rotation(turn)
        page.close()
    buffer = io.BytesIO()
    document.save(buffer)
    document.close()
    source.close()
    return buffer.getvalue()


def spread(texts: list[Text], *, inherited: bool = True) -> bytes:
    """Two pages cut from one sheet of twice the page width (1200 x 800): one content
    stream draws `texts` (Helvetica, positions on the sheet from its top left) and each
    page's /CropBox covers one half. With `inherited` the /MediaBox stands only on the
    /Pages node, as in the seaborn corpus paper, so the pages inherit it (#543); else each
    page states its own."""
    content = b"".join(
        b"BT /F1 %g Tf %g %g Td (%s) Tj ET\n" % (t.size, t.x, HEIGHT - t.y, t.text.encode())
        for t in texts
    )
    media = b" /MediaBox [0 0 %g %g]" % (2 * WIDTH, HEIGHT)
    page = b"<< /Type /Page /Parent 2 0 R /CropBox [%g 0 %g %g] /Contents 4 0 R%s >>"
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2"
        b" /Resources << /Font << /F1 5 0 R >> >>%s >>" % (media if inherited else b""),
        3: page % (0, WIDTH, HEIGHT, b"" if inherited else media),
        4: stream(content),
        5: _HELVETICA,
        6: page % (WIDTH, 2 * WIDTH, HEIGHT, b"" if inherited else media),
    }
    return raw_pdf(objects)


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
    Written here, after algorithms 2, 3 and 4 or 5 of PDF 32000-1, 7.6.3, so the tests need
    no pikepdf (MPL-2.0, not a dependency) and cover revision 2 too. pikepdf can write
    revision 3 with accessibility forbidden; from revision 4 on (AES) qpdf always allows it
    (#188)."""
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


def with_page_added(data: bytes, text: str) -> bytes:
    """`data` with a page holding `text` added by an incremental update: the new objects, a
    second cross-reference section and a second %%EOF are appended to the file as it was."""
    document = pdfium.PdfDocument(data)
    page = document.new_page(WIDTH, HEIGHT)
    raw.FPDFPage_InsertObject(page.raw, _text(document, Text(text, 50, 50)))
    raw.FPDFPage_GenerateContent(page.raw)
    page.close()
    buffer = io.BytesIO()
    document.save(buffer, flags=raw.FPDF_INCREMENTAL)
    document.close()
    updated = buffer.getvalue()
    assert updated.startswith(data)
    return updated


def flate_bomb(spaces: int, chunk: int = 1 << 20) -> bytes:
    """One page whose content stream is `spaces` spaces and then "Hello", Flate-compressed:
    about 1 KB of file per MB of stream (#185). The stream is built from one flushed block
    repeated, so a gigabyte takes a fraction of a second to write."""
    compressor = zlib.compressobj(9)
    block = compressor.compress(b" " * chunk) + compressor.flush(zlib.Z_FULL_FLUSH)
    repeat = compressor.compress(b" " * chunk) + compressor.flush(zlib.Z_FULL_FLUSH)
    tail_text = b"BT /F1 12 Tf 72 720 Td (Hello) Tj ET"
    tail = compressor.compress(tail_text) + compressor.flush()
    count = spaces // chunk
    checksum = 1
    for _ in range(count):
        checksum = zlib.adler32(b" " * chunk, checksum)
    checksum = zlib.adler32(tail_text, checksum)
    body = block + repeat * (count - 1) + tail[:-4] + struct.pack(">I", checksum)
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: _PAGE % (b"[0 0 612 792]", b"<< /Font << /F1 5 0 R >> >>", b""),
        4: stream(body, b"/Filter /FlateDecode"),
        5: _HELVETICA,
    }
    return raw_pdf(objects)


# ---- fonts with no Unicode source (#442) ----------------------------------------------------

GLYPH_ORDERS = {"shifted": -29, "far": 300}  # glyph number minus code point, per font kind


def glyph_number_pdf(
    lines: list[str],
    *,
    order: str = "shifted",
    cmap: bool = False,
    post: bool = False,
    to_unicode: bool = False,
    plain: tuple[str, ...] = (),
) -> bytes:
    """One page whose `lines` are set in a CID font with Identity-H encoding, as Acrobat
    Distiller writes a TrueType font it subsets: each character's code is its glyph number,
    the code point moved by `GLYPH_ORDERS[order]` ("shifted" is the usual TrueType glyph
    order, "DV" for "as"; "far" lands past Latin Extended-A, as Calibri's glyph numbers do).
    The embedded program is written here (`truetype_program`, rectangles for glyphs, no real
    font, so no licence), with a cmap and a post table only if asked; `to_unicode` adds the
    map that gives the right letters. `plain` lines follow in Helvetica, 20 pt apart."""
    shift = GLYPH_ORDERS[order]
    codes = sorted({ord(c) + shift for line in lines for c in line})
    content = b""
    for k, line in enumerate(lines):
        hexed = "".join(f"{ord(c) + shift:04X}" for c in line).encode()
        content += b"BT /F1 10 Tf 72 %d Td <%s> Tj ET\n" % (720 - 20 * k, hexed)
    for k, line in enumerate(plain, len(lines)):
        content += b"BT /F2 10 Tf 72 %d Td (%s) Tj ET\n" % (720 - 20 * k, line.encode())
    program = truetype_program(max(codes) + 1, cmap=cmap, post=post)
    descendant = (
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+GlyphNumbers"
        b" /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
        b" /FontDescriptor 8 0 R /CIDToGIDMap /Identity /DW 500 >>"
    )
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: _PAGE % (b"[0 0 612 792]", b"<< /Font << /F1 6 0 R /F2 5 0 R >> >>", b""),
        4: stream(content),
        5: _HELVETICA,
        6: b"<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+GlyphNumbers"
        b" /Encoding /Identity-H /DescendantFonts [7 0 R]%s >>"
        % (b" /ToUnicode 10 0 R" if to_unicode else b""),
        7: descendant,
        8: b"<< /Type /FontDescriptor /FontName /ABCDEF+GlyphNumbers /Flags 6"
        b" /FontBBox [0 -200 1000 800] /ItalicAngle 0 /Ascent 800 /Descent -200"
        b" /CapHeight 700 /StemV 80 /FontFile2 9 0 R >>",
        9: stream(program, b"/Length1 %d" % len(program)),
    }
    if to_unicode:
        entries = [f"<{code:04X}> <{code - shift:04X}>" for code in codes]
        blocks = "".join(
            f"{len(chunk)} beginbfchar {' '.join(chunk)} endbfchar "
            for chunk in (entries[i : i + 100] for i in range(0, len(entries), 100))
        )
        objects[10] = stream(
            b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /G def"
            b" 1 begincodespacerange <0000> <FFFF> endcodespacerange %s"
            b"endcmap CMapName currentdict /CMap defineresource pop end end" % blocks.encode()
        )
    return raw_pdf(objects)


def truetype_program(glyphs: int, *, cmap: bool = False, post: bool = False) -> bytes:
    """A TrueType font program of `glyphs` glyphs, each a rectangle (glyphs 0 and 3, the
    .notdef and the space, empty), with the tables a reader needs (head, hhea, maxp, hmtx,
    loca, glyf) and, if asked, a cmap (Unicode to glyph, an empty map) and a post table
    (version 3, no glyph names): either one is a Unicode source of its own (#442)."""
    rectangle = simple_glyph([[(50, 0), (450, 0), (450, 600), (50, 600)]])
    outlines = [b"" if glyph in (0, 3) else rectangle for glyph in range(glyphs)]
    return font_program(outlines, [500] * glyphs, cmap=cmap, post=post)


Point = tuple[int, int] | tuple[int, int, bool]  # x, y in font units; on the curve unless False


def simple_glyph(contours: list[list[Point]]) -> bytes:
    """A simple TrueType glyph of the contours, every coordinate a 16-bit delta, no hinting
    instructions (#618)."""
    points = [(p[0], p[1], p[2] if len(p) == 3 else True) for c in contours for p in c]
    ends, total = [], 0
    for contour in contours:
        total += len(contour)
        ends.append(total - 1)
    xs = [p[0] for p in points] or [0]
    ys = [p[1] for p in points] or [0]
    data = struct.pack(">hhhhh", len(contours), min(xs), min(ys), max(xs), max(ys))
    data += struct.pack(f">{len(ends)}H", *ends) + struct.pack(">H", 0)
    data += bytes(1 if on else 0 for _, _, on in points)
    for axis in (0, 1):
        last = 0
        for point in points:
            data += struct.pack(">h", point[axis] - last)
            last = point[axis]
    return data


Component = tuple[int, int, int] | tuple[int, int, int, tuple[float, float, float, float]]


def composite_glyph(components: list[Component]) -> bytes:
    """A composite glyph: each component is (glyph, dx, dy) or (glyph, dx, dy, (a, b, c, d)),
    the offsets as 16-bit words, the matrix as four 2.14 numbers (#618)."""
    data = struct.pack(">hhhhh", -1, 0, 0, 0, 0)
    for k, component in enumerate(components):
        glyph, dx, dy = component[:3]
        flags = 0x0001 | 0x0002 | (0x0020 if k < len(components) - 1 else 0)
        matrix = b""
        if len(component) == 4:
            flags |= 0x0080
            matrix = struct.pack(">4h", *(round(v * 16384) for v in component[3]))
        data += struct.pack(">HHhh", flags, glyph, dx, dy) + matrix
    return data


def font_program(
    outlines: list[bytes],
    advances: list[int],
    *,
    units: int = 1000,
    metrics: int | None = None,
    hmtx: bytes | None = None,
    short_loca: bool = False,
    cmap: bool = False,
    post: bool = False,
    tables: dict[bytes, bytes] | None = None,
) -> bytes:
    """A TrueType program of the glyph `outlines` (bytes of `simple_glyph` or
    `composite_glyph`, empty for no ink) and their advances. `metrics` is hhea's
    numberOfHMetrics (all glyphs unless given: fewer leaves the later glyphs only a left
    side bearing); `hmtx` replaces the table's bytes as written (to cut it short); `tables`
    adds or replaces tables (#618)."""
    count = len(outlines)
    metrics = count if metrics is None else metrics
    glyf, loca = b"", []
    for outline in outlines:
        loca.append(len(glyf))
        glyf += outline + b"\0" * (-len(outline) % 4)
    loca.append(len(glyf))
    if hmtx is None:
        hmtx = b"".join(struct.pack(">Hh", advances[g], 0) for g in range(min(metrics, count)))
        hmtx += b"".join(struct.pack(">h", 0) for _ in range(metrics, count))
    head = struct.pack(
        ">IIIIHHqqhhhhHHhhh",
        0x10000, 0, 0, 0x5F0F3CF5, 0, units, 0, 0, 0, -200, 1000, 800, 0, 3, 2,
        1 if not short_loca else 0, 0,
    )  # fmt: skip
    hhea = struct.pack(
        ">IhhhHhhhhhhhhhhhH", 0x10000, 800, -200, 0, 1000, 0, 0, 1000, 1, 0, 0, 0, 0, 0, 0, 0,
        metrics,
    )  # fmt: skip
    found = {
        b"head": head,
        b"hhea": hhea,
        b"maxp": struct.pack(">IH13H", 0x10000, count, 4, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0),
        b"hmtx": hmtx,
        b"loca": (
            struct.pack(f">{len(loca)}H", *(o // 2 for o in loca))
            if short_loca
            else struct.pack(f">{len(loca)}I", *loca)
        ),
        b"glyf": glyf,
    }
    if cmap:  # format 4 with only the closing segment: maps nothing, but is there
        found[b"cmap"] = (
            struct.pack(">HHHHI", 0, 1, 3, 1, 12)
            + struct.pack(">8H", 4, 24, 0, 2, 2, 0, 0, 0xFFFF)
            + struct.pack(">4H", 0, 0xFFFF, 1, 0)
        )
    if post:
        found[b"post"] = struct.pack(">IIhhIIIII", 0x30000, 0, 0, 0, 0, 0, 0, 0, 0)
    found.update(tables or {})
    return sfnt(found)


def sfnt(tables: dict[bytes, bytes], version: bytes = b"\x00\x01\x00\x00") -> bytes:
    """A font program holding `tables` in tag order, each padded to four bytes."""
    header = version + struct.pack(">HHHH", len(tables), 0, 0, 0)
    offset, directory, body = 12 + 16 * len(tables), b"", b""
    for tag in sorted(tables):
        data = tables[tag]
        directory += struct.pack(">4sIII", tag, 0, offset + len(body), len(data))
        body += data + b"\0" * (-len(data) % 4)
    return header + directory + body


def joined_pdf(*parts: bytes) -> bytes:
    """One PDF holding every page of `parts`, in order, each with its own fonts (pypdfium2's
    page import copies a page's resources): a glyph-number page beside plain pages (#442)."""
    joined = pdfium.PdfDocument.new()
    for data in parts:
        part = pdfium.PdfDocument(data)
        joined.import_pages(part)
        part.close()
    buffer = io.BytesIO()
    joined.save(buffer)
    joined.close()
    return buffer.getvalue()


# ---- twins of Office fonts with no Unicode source (#618) ------------------------------------

FONTS = Path(__file__).resolve().parents[1] / "fixtures" / "fonts"
TWINS = {
    "times": "tinos-regular-subset.ttf",
    "arial": "arimo-regular-subset.ttf",
    "courier": "cousine-regular-subset.ttf",
}
# Where the standard Macintosh glyph order (the first 258 glyphs of the usual TrueType
# fonts, Times New Roman's among them) puts these characters: printable ASCII at its code
# point minus 29, so digits and , . - / : ( ) land on control codes, and ü and ß past 127.
MAC_ORDER = {chr(c): c - 29 for c in range(0x20, 0x7F)} | {
    "Ä": 98, "Ö": 103, "Ü": 104, "ä": 108, "ö": 124, "ü": 129,
    "ß": 137,
}  # fmt: skip


@dataclass(frozen=True)
class Twin:
    """A subset font program taken apart: its glyphs' bytes, advances and letters."""

    units: int
    glyphs: list[bytes]
    advances: list[int]
    letters: dict[str, int]  # character to glyph

    @staticmethod
    def load(name: str) -> Twin:
        program = (FONTS / TWINS[name]).read_bytes()
        (count,) = struct.unpack_from(">H", program, 4)
        tables = {}
        for k in range(count):
            tag, _, offset, length = struct.unpack_from(">4sIII", program, 12 + 16 * k)
            tables[tag] = program[offset : offset + length]
        units = struct.unpack_from(">H", tables[b"head"], 18)[0]
        wide = struct.unpack_from(">h", tables[b"head"], 50)[0] == 1
        glyphs = struct.unpack_from(">H", tables[b"maxp"], 4)[0]
        loca = struct.unpack_from(f">{glyphs + 1}{'I' if wide else 'H'}", tables[b"loca"])
        loca = loca if wide else tuple(2 * o for o in loca)
        data = [tables[b"glyf"][loca[g] : loca[g + 1]] for g in range(glyphs)]
        metrics = struct.unpack_from(">H", tables[b"hhea"], 34)[0]
        advances = [
            struct.unpack_from(">H", tables[b"hmtx"], 4 * min(g, metrics - 1))[0]
            for g in range(glyphs)
        ]
        return Twin(units, data, advances, _cmap(tables[b"cmap"]))

    def program(self, order: list[int], *, metrics: int | None = None) -> bytes:
        """The font with its glyphs in `order` (new glyph k is old glyph order[k]), composite
        components renumbered to match, without cmap and post; `metrics` cuts hmtx."""
        new = {old: k for k, old in enumerate(order)}
        outlines = [_renumbered(self.glyphs[old], new) for old in order]
        advances = [self.advances[old] for old in order]
        return font_program(outlines, advances, units=self.units, metrics=metrics)


def _cmap(table: bytes) -> dict[str, int]:
    """Character to glyph from a cmap's Windows Unicode format 4 subtable."""
    (subtables,) = struct.unpack_from(">H", table, 2)
    for k in range(subtables):
        platform, encoding, offset = struct.unpack_from(">HHI", table, 4 + 8 * k)
        if (platform, encoding) != (3, 1):
            continue
        segments = struct.unpack_from(">H", table, offset + 6)[0] // 2
        ends = struct.unpack_from(f">{segments}H", table, offset + 14)
        starts = struct.unpack_from(f">{segments}H", table, offset + 16 + 2 * segments)
        deltas = struct.unpack_from(f">{segments}h", table, offset + 16 + 4 * segments)
        at = offset + 16 + 6 * segments
        ranges = struct.unpack_from(f">{segments}H", table, at)
        found = {}
        for s in range(segments):
            for code in range(starts[s], min(ends[s], 0xFFFE) + 1):
                if ranges[s]:
                    where = at + 2 * s + ranges[s] + 2 * (code - starts[s])
                    glyph = struct.unpack_from(">H", table, where)[0]
                    glyph = (glyph + deltas[s]) & 0xFFFF if glyph else 0
                else:
                    glyph = (code + deltas[s]) & 0xFFFF
                if glyph:
                    found[chr(code)] = glyph
        return found
    raise ValueError("no Windows Unicode cmap")


def _renumbered(glyph: bytes, new: dict[int, int]) -> bytes:
    """A glyph with its components' glyph numbers changed by `new` (a simple glyph as it
    is)."""
    if len(glyph) < 10 or struct.unpack_from(">h", glyph)[0] >= 0:
        return glyph
    data, at = bytearray(glyph), 10
    while True:
        flags, old = struct.unpack_from(">HH", data, at)
        struct.pack_into(">H", data, at + 2, new[old])
        at += 4 + (4 if flags & 0x0001 else 2)
        at += 2 if flags & 0x0008 else 4 if flags & 0x0040 else 8 if flags & 0x0080 else 0
        if not flags & 0x0020:
            return bytes(data)


def twin_pdf(
    lines: list[str],
    twin: str = "times",
    *,
    order: str = "shuffled",
    seed: int = 618,
    metrics: str = "truncated",
    same: tuple[str, str] | None = None,
    cid_map: bool = False,
    spread: int = 0,
    damage: tuple[tuple[int, int], ...] = (),
    rectangles: tuple[str, ...] = (),
) -> bytes:
    """One page whose `lines` are set as Acrobat Distiller writes a subset of an Office
    font after a PDF organiser dropped its maps (#442, #618): a CID font, Identity-H, each
    code its glyph number, no ToUnicode, the program without cmap and post, /W from the true
    advances. The font is an Apache-2.0 subset of Tinos ("times"), Arimo ("arial") or
    Cousine ("courier") from `tests/fixtures/fonts/`.

    `order`: "shuffled" (seeded), or "mac", the usual TrueType order. `metrics`:
    "truncated" gives only the first half of the glyphs an advance of their own in hmtx,
    "full" all. `same=("c", "e")` draws the second letter's glyph as the first's.
    `cid_map` writes the codes through a /CIDToGIDMap stream that shuffles them (seeded), so
    they are not glyph numbers. `spread` scatters the shuffled glyphs over that many glyph
    numbers, the rest empty: codes as high as an Office font's whole glyph set has.
    `damage` sets bytes of the program: (where, value), where taken modulo its length.
    `rectangles` adds lines in
    the rectangle font of `glyph_number_pdf` (no letter shapes), shifted by 29."""
    font = Twin.load(twin)
    others = list(range(1, len(font.glyphs)))
    rng = random.Random(seed)  # noqa: S311 (a test order, no secret)
    if order == "shuffled" and spread:
        new_order = [0] * spread
        for glyph, at in zip(others, rng.sample(range(1, spread), len(others)), strict=False):
            new_order[at] = glyph
    elif order == "shuffled":
        rng.shuffle(others)
        new_order = [0, *others]
    else:
        wanted = {MAC_ORDER[c]: g for c, g in font.letters.items() if c in MAC_ORDER}
        rest = iter(g for g in others if g not in wanted.values())
        new_order = [0] + [wanted.get(k) or next(rest, 0) for k in range(1, 258)]
        new_order += list(rest)
        while not new_order[-1]:
            new_order.pop()
    if same is not None:
        glyphs = list(font.glyphs)
        glyphs[font.letters[same[1]]] = glyphs[font.letters[same[0]]]
        font = replace(font, glyphs=glyphs)
    count = len(new_order)
    program = font.program(new_order, metrics=count // 2 if metrics == "truncated" else None)
    if damage:
        changed = bytearray(program)
        for where, value in damage:
            changed[where % len(changed)] = value
        program = bytes(changed)
    code_of = {old: k for k, old in enumerate(new_order) if old}
    widths = [round(1000 * font.advances[old] / font.units) for old in new_order]
    # the code of glyph k: itself, or with `cid_map` a shuffled one the map undoes
    cid = list(range(count))
    if cid_map:
        tail = cid[1:]
        random.Random(seed + 1).shuffle(tail)  # noqa: S311 (a test order, no secret)
        cid = [0, *tail]
    content = b""
    for k, line in enumerate(lines):
        hexed = "".join(f"{cid[code_of[font.letters[c]]]:04X}" for c in line).encode()
        content += b"BT /F1 10 Tf 72 %d Td <%s> Tj ET\n" % (720 - 20 * k, hexed)
    for k, line in enumerate(rectangles, len(lines)):
        hexed = "".join(f"{ord(c) - 29:04X}" for c in line).encode()
        content += b"BT /F3 10 Tf 72 %d Td <%s> Tj ET\n" % (720 - 20 * k, hexed)
    cid_widths, glyph_of = [0] * count, [0] * count
    for glyph in range(count):
        cid_widths[cid[glyph]] = widths[glyph]
        glyph_of[cid[glyph]] = glyph
    gid_map = b"/Identity"
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: _PAGE % (b"[0 0 612 792]", b"<< /Font << /F1 6 0 R /F3 11 0 R >> >>", b""),
        4: stream(content),
        6: b"<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+TimesNewRoman"
        b" /Encoding /Identity-H /DescendantFonts [7 0 R] >>",
        8: b"<< /Type /FontDescriptor /FontName /ABCDEF+TimesNewRoman /Flags 6"
        b" /FontBBox [-600 -300 2000 1000] /ItalicAngle 0 /Ascent 891 /Descent -216"
        b" /CapHeight 662 /StemV 80 /FontFile2 9 0 R >>",
        9: stream(program, b"/Length1 %d" % len(program)),
    }
    if cid_map:
        objects[10] = stream(b"".join(struct.pack(">H", g) for g in glyph_of))
        gid_map = b"10 0 R"
    objects[7] = (
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+TimesNewRoman"
        b" /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
        b" /FontDescriptor 8 0 R /CIDToGIDMap %s /W [0 [%s]] >>"
        % (gid_map, " ".join(map(str, cid_widths)).encode())
    )
    shapes = truetype_program(128)
    objects[11] = (
        b"<< /Type /Font /Subtype /Type0 /BaseFont /GHIJKL+Rectangles /Encoding /Identity-H"
        b" /DescendantFonts [12 0 R] >>"
    )
    objects[12] = (
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /GHIJKL+Rectangles"
        b" /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
        b" /FontDescriptor 13 0 R /CIDToGIDMap /Identity /DW 500 >>"
    )
    objects[13] = (
        b"<< /Type /FontDescriptor /FontName /GHIJKL+Rectangles /Flags 6"
        b" /FontBBox [0 -200 1000 800] /ItalicAngle 0 /Ascent 800 /Descent -200"
        b" /CapHeight 700 /StemV 80 /FontFile2 14 0 R >>"
    )
    objects[14] = stream(shapes, b"/Length1 %d" % len(shapes))
    return raw_pdf(objects)


def heavy_glyph_pdf(count: int, points: int = 8191, widths: tuple[int, ...] = (600,)) -> bytes:
    """One page of `count` different glyphs of a font with no Unicode source, each a
    composite holding the same simple glyph of `points` points (#618 review): within every
    limit a glyph has, but each one costs the reader the work of `points` points. The codes
    start at U+4E00, so PDFium reads each as a glyph number with a map error. The glyphs'
    advances (1/1000 em) take `widths` in turn: one width is a monospaced font, Times New
    Roman's widths pass every check made before a glyph is drawn."""
    flags, ys = bytearray(), bytearray()
    for k in range(points):
        flags.append(0x01 | 0x02 | (0x10 if k % 2 == 0 else 0))
        ys += struct.pack(">h", (1000 if k % 2 == 0 else -1000) if k else 0)
    heavy = struct.pack(">hhhhh", 1, 0, 0, 300, 1000) + struct.pack(">HH", points - 1, 0)
    heavy += bytes(flags) + bytes([200]) * points + bytes(ys)
    base = 0x4E00
    outlines = [b"", heavy] + [b""] * (base - 2) + [composite_glyph([(1, 0, 0)])] * count
    advances = [600] * base + [widths[k % len(widths)] for k in range(count)]
    program = font_program(outlines, advances)
    content = b""
    for row in range(0, count, 40):
        hexed = "".join(f"{c:04X}" for c in range(base + row, base + min(row + 40, count)))
        content += b"BT /F1 4 Tf 20 %d Td <%s> Tj ET\n" % (
            780 - 6 * (row // 40) % 760,
            hexed.encode(),
        )
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: _PAGE % (b"[0 0 612 792]", b"<< /Font << /F1 6 0 R >> >>", b""),
        4: stream(content),
        6: b"<< /Type /Font /Subtype /Type0 /BaseFont /ABCDEF+Heavy /Encoding /Identity-H"
        b" /DescendantFonts [7 0 R] >>",
        7: b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+Heavy"
        b" /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >>"
        b" /FontDescriptor 8 0 R /CIDToGIDMap /Identity /DW 600 /W [%d [%s]] >>"
        % (base, " ".join(str(w) for w in advances[base:]).encode()),
        8: b"<< /Type /FontDescriptor /FontName /ABCDEF+Heavy /Flags 6"
        b" /FontBBox [0 -300 9000 1000] /ItalicAngle 0 /Ascent 900 /Descent -200"
        b" /CapHeight 700 /StemV 80 /FontFile2 9 0 R >>",
        9: stream(program, b"/Length1 %d" % len(program)),
    }
    return raw_pdf(objects)
