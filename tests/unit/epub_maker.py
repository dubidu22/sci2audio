"""Make small EPUBs for extraction tests with zipfile, so each case shows one thing (D-316).

`make_epub` builds a whole book from chapter bodies; the lower-level helpers build the
pieces, so a broken-file test can leave one out or damage it. Everything here is our own
work, made for the tests: no third-party text enters the repository.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

XHTML_NS = 'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
OPF_NS = "http://www.idpf.org/2007/opf"
CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
METADATA = """<dc:identifier id="uid">urn:uuid:00000000-0000-4000-8000-000000000000</dc:identifier>
    <dc:title>A Made-Up Book</dc:title>
    <dc:language>en</dc:language>"""


def xhtml(body: str, head: str = "<title>Chapter</title>", declaration: bool = True) -> str:
    """An XHTML content document with `body` inside <body>."""
    start = '<?xml version="1.0" encoding="utf-8"?>\n' if declaration else ""
    return f"{start}<html {XHTML_NS}><head>{head}</head><body>{body}</body></html>"


def nav(entries: str) -> str:
    """An EPUB 3 navigation document whose toc holds `entries` (the <li>s of its <ol>)."""
    return xhtml(f'<nav epub:type="toc"><h1>Contents</h1><ol>{entries}</ol></nav>')


@dataclass
class Item:
    id: str
    href: str  # relative to OEBPS/
    media_type: str = "application/xhtml+xml"
    properties: str = ""
    content: str | bytes | None = None  # None: the item is listed but not in the zip
    in_spine: bool = True
    extra: str = ""  # more attributes for the manifest entry, e.g. 'fallback="x"'


@dataclass
class Book:
    """The parts of an EPUB; `bytes()` packs them."""

    items: list[Item] = field(default_factory=list)
    metadata: str = METADATA
    version: str = "3.0"
    spine_toc: str = ""
    extra_files: dict[str, str | bytes] = field(default_factory=dict)  # path in the zip → data
    container: str | None = CONTAINER
    opf: str | None = None  # the whole package file, in place of the built one

    def package(self) -> str:
        manifest = "\n    ".join(
            f'<item id="{i.id}" href="{i.href}" media-type="{i.media_type}"'
            + (f' properties="{i.properties}"' if i.properties else "")
            + (f" {i.extra}" if i.extra else "")
            + "/>"
            for i in self.items
        )
        spine = "\n    ".join(f'<itemref idref="{i.id}"/>' for i in self.items if i.in_spine)
        toc = f' toc="{self.spine_toc}"' if self.spine_toc else ""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="{OPF_NS}" version="{self.version}" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="{OPF_NS}">
    {self.metadata}
  </metadata>
  <manifest>
    {manifest}
  </manifest>
  <spine{toc}>
    {spine}
  </spine>
</package>
"""

    def files(self) -> dict[str, str | bytes]:
        out: dict[str, str | bytes] = {}
        if self.container is not None:
            out["META-INF/container.xml"] = self.container
        out["OEBPS/content.opf"] = self.opf if self.opf is not None else self.package()
        for item in self.items:
            if item.content is not None:
                out[f"OEBPS/{item.href}"] = item.content
        out.update(self.extra_files)
        return out

    def bytes(self) -> bytes:
        return pack(self.files())


def pack(files: dict[str, str | bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """A zip with the EPUB's `mimetype` first and stored, then `files` in order."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for path, data in files.items():
            archive.writestr(path, data, compress_type=compression)
    return buffer.getvalue()


def make_epub(
    *bodies: str,
    nav_entries: str | None = None,
    metadata: str = METADATA,
    items: list[Item] | None = None,
    extra_files: dict[str, str | bytes] | None = None,
) -> bytes:
    """A book whose spine is one chapter per body (c1.xhtml, c2.xhtml, ...), with a
    navigation document (not in the spine) when `nav_entries` is given."""
    book = Book(metadata=metadata, extra_files=dict(extra_files or {}))
    book.items = [
        Item(f"c{n}", f"c{n}.xhtml", content=xhtml(body)) for n, body in enumerate(bodies, 1)
    ]
    if nav_entries is not None:
        book.items.append(
            Item("nav", "nav.xhtml", properties="nav", content=nav(nav_entries), in_spine=False)
        )
    book.items += items or []
    return book.bytes()


def set_flag(data: bytes, member: str, bit: int) -> bytes:
    """`data` with a general-purpose flag bit set on `member` in both zip headers
    (bit 0 = encrypted), as zipfile cannot write an encrypted entry itself."""
    out = bytearray(data)
    name = member.encode()
    local = out.find(b"PK\x03\x04")
    while local != -1:
        size = int.from_bytes(out[local + 26 : local + 28], "little")
        if out[local + 30 : local + 30 + size] == name:
            out[local + 6] |= 1 << bit
        local = out.find(b"PK\x03\x04", local + 4)
    central = out.find(b"PK\x01\x02")
    while central != -1:
        size = int.from_bytes(out[central + 28 : central + 30], "little")
        if out[central + 46 : central + 46 + size] == name:
            out[central + 8] |= 1 << bit
        central = out.find(b"PK\x01\x02", central + 4)
    return bytes(out)


def set_method(data: bytes, member: str, method: int) -> bytes:
    """`data` with `member`'s compression method changed in both zip headers."""
    out = bytearray(data)
    name = member.encode()
    for signature, method_at, name_size_at, name_at in (
        (b"PK\x03\x04", 8, 26, 30),
        (b"PK\x01\x02", 10, 28, 46),
    ):
        start = out.find(signature)
        while start != -1:
            size = int.from_bytes(out[start + name_size_at : start + name_size_at + 2], "little")
            if out[start + name_at : start + name_at + size] == name:
                out[start + method_at : start + method_at + 2] = method.to_bytes(2, "little")
            start = out.find(signature, start + 4)
    return bytes(out)
