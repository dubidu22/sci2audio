"""Record what an EPUB holds as `Content`, deciding nothing (D-63, D-304 to D-317).

Each spine document becomes a page without positions. Each block element (a paragraph, a
heading, a list item, a table cell, ...) becomes a text line made of styled runs, and each run
keeps its markup as tags (D-306, D-307): the element names from below ``<body>`` down to the
run, each followed by its ``#id``, ``epub:`` and ``role:`` tokens, ``lang:``, ``hidden``,
``aria-hidden``, and a ``link:<item id>`` or ``href:<as stored>`` for a link. Pictures keep
their alternative text and where the file stores them (`Picture.ref`), and `Page.order` keeps
where they stand between the lines. The navigation document (or, failing that, the NCX) fills
`Content.outline`; the package file fills `Metadata`.

Only the standard library is used (D-305): `zipfile`, `xml.etree` for the container, the
package file and the NCX, which are refused when they declare an entity, and `html.parser`
for XHTML, which recovers from malformed markup and never expands custom entities. A file
that cannot be read raises `ExtractionError` with a message a person can act on (D-315).
"""

from __future__ import annotations

import codecs
import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.parsers import expat

from sci2audio.core import (
    Content,
    Metadata,
    OutlineEntry,
    Page,
    Picture,
    Source,
    SourceFormat,
)
from sci2audio.extraction.cover import Cover, media_type
from sci2audio.extraction.errors import ExtractionError
from sci2audio.extraction.markup import (
    Anchors,
    PageReader,
    clean_path,
    fold,
    resolve,
    resolve_links,
)

MAX_MEMBER = 64 * 1024 * 1024  # bytes one file in the zip may unpack to
MAX_TOTAL = 512 * 1024 * 1024  # bytes all files read from one EPUB may unpack to
MAX_SPINE = 10_000  # documents in the reading order
MAX_COVER = 20 * 1024 * 1024  # bytes of a cover image
MAX_OUTLINE_LEVEL = 15  # as for PDF bookmarks (D-267)

CONTAINER = "META-INF/container.xml"
_DRM_FILES = ("META-INF/rights.xml", "META-INF/sinf.xml", "META-INF/license.lcpl")
# Font obfuscation (IDPF and Adobe) hides fonts only; it is not DRM and no text is encrypted.
_FONT_OBFUSCATION = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}

_XHTML_TYPES = {"application/xhtml+xml", "text/html", "image/svg+xml"}
_ENCODING = re.compile(rb"""^\s*<\?xml[^>]*?encoding\s*=\s*["']([A-Za-z0-9._-]+)["']""")
_DATE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")


def extract_epub(path: Path) -> Content:
    """Read the EPUB at `path` into `Content`; raise ExtractionError if it can't be read."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ExtractionError(f"{path.name}: cannot be opened ({error.strerror})") from error
    return read_epub(data, path.name)


def read_epub(data: bytes, name: str) -> Content:
    """Read EPUB bytes into `Content`; `name` is the bare file name the source keeps."""
    book = _open(data, name)
    try:
        package = book.package()
        pages, anchors = book.pages(package)
        pages = resolve_links(pages, anchors)
        outline = book.outline(package, anchors)
        metadata = _metadata(package)
    finally:
        book.close()
    source = Source(name, SourceFormat.EPUB, sha256=hashlib.sha256(data).hexdigest())
    return Content(source=source, pages=pages, metadata=metadata, outline=outline)


def extract_epub_cover(path: Path) -> Cover | None:
    """The cover the EPUB declares, if it is a JPEG or PNG of at most `MAX_COVER` bytes;
    None otherwise or if the file can't be read (a missing cover never stops a job)."""
    try:
        data = path.read_bytes()
        book = _open(data, path.name)
    except (OSError, ExtractionError):
        return None
    try:
        package = book.package()
        item = package.cover()
        if item is None:
            return None
        image = book.read(item.path, limit=MAX_COVER, missing_ok=True)
    except ExtractionError:
        return None
    finally:
        book.close()
    kind = media_type(image) if image else None
    return Cover(image, kind) if image and kind else None


# ---- the zip -------------------------------------------------------------------------


def _open(data: bytes, name: str) -> _Book:
    if not data:
        raise ExtractionError(f"{name}: the file is empty")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        NotImplementedError,  # a zip version it does not know
        OSError,
        ValueError,
        EOFError,
    ) as error:
        raise ExtractionError(f"{name}: not an EPUB, or the file is damaged") from error
    book = _Book(name, archive)
    try:
        book.check_protection()
    except ExtractionError:
        book.close()
        raise
    return book


@dataclass
class _Book:
    name: str
    archive: zipfile.ZipFile
    total: int = 0  # bytes unpacked so far
    members: dict[str, zipfile.ZipInfo] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.members = {info.filename: info for info in self.archive.infolist()}

    def close(self) -> None:
        self.archive.close()

    def damaged(self) -> ExtractionError:
        return ExtractionError(f"{self.name}: not an EPUB, or the file is damaged")

    def read(self, path: str, limit: int | None = None, missing_ok: bool = False) -> bytes:
        """The unpacked bytes of `path` in the zip; b"" if it is missing and `missing_ok`."""
        info = self.members.get(path)
        if info is None:
            if missing_ok:
                return b""
            raise ExtractionError(f"{self.name}: the EPUB is damaged: {path} is missing")
        if info.flag_bits & 0x1:
            raise ExtractionError(
                f"{self.name}: the EPUB is password-protected; remove the password and try again"
            )
        limit = MAX_MEMBER if limit is None else limit
        chunks, size = [], 0
        try:
            with self.archive.open(info) as stream:
                while chunk := stream.read(1 << 20):
                    size += len(chunk)
                    self.total += len(chunk)
                    if size > limit or self.total > MAX_TOTAL:
                        raise ExtractionError(f"{self.name}: the EPUB is too large or damaged")
                    chunks.append(chunk)
        except ExtractionError:
            raise
        except NotImplementedError as error:  # a compression zipfile doesn't know
            raise self.damaged() from error
        except RuntimeError as error:  # encrypted (WinZip AES) without the flag zipfile checks
            raise ExtractionError(
                f"{self.name}: the EPUB is password-protected; remove the password and try again"
            ) from error
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError) as error:
            raise self.damaged() from error
        return b"".join(chunks)

    def check_protection(self) -> None:
        """Refuse an EPUB under DRM; obfuscated fonts alone are fine (D-315)."""
        drm = ExtractionError(
            f"{self.name}: the EPUB is protected by DRM; sci2audio can read only EPUBs without DRM"
        )
        if any(path in self.members for path in _DRM_FILES):
            raise drm
        if "META-INF/encryption.xml" not in self.members:
            return
        root = _xml(self.read("META-INF/encryption.xml"), self, "encryption file")
        for element in root.iter():
            method = _local(element.tag) == "EncryptionMethod"
            if method and element.get("Algorithm", "") not in _FONT_OBFUSCATION:
                raise drm

    def package(self) -> _Package:
        if CONTAINER not in self.members:
            raise ExtractionError(f"{self.name}: the EPUB has no container file ({CONTAINER})")
        container = _xml(self.read(CONTAINER), self, "container file")
        roots = [e for e in container.iter() if _local(e.tag) == "rootfile" and e.get("full-path")]
        if not roots:
            raise ExtractionError(f"{self.name}: the EPUB's container file names no package file")
        preferred = [e for e in roots if e.get("media-type", "") == "application/oebps-package+xml"]
        path = clean_path((preferred or roots)[0].get("full-path", ""))
        if path is None or path not in self.members:
            shown = (preferred or roots)[0].get("full-path", "")
            raise ExtractionError(f"{self.name}: the EPUB's package file {shown} is missing")
        return _Package.parse(path, _xml(self.read(path), self, "package file"))

    def pages(self, package: _Package) -> tuple[tuple[Page, ...], Anchors]:
        if not package.spine:
            raise ExtractionError(f"{self.name}: the EPUB has no chapters")
        if len(package.spine) > MAX_SPINE:
            raise ExtractionError(f"{self.name}: the EPUB is too large or damaged")
        anchors = Anchors()
        pages = []
        for number, idref in enumerate(package.spine, 1):
            item = package.manifest.get(idref)
            if item is None:
                raise ExtractionError(
                    f"{self.name}: the EPUB is damaged: its reading order names {idref!r},"
                    " which it does not list"
                )
            pages.append(self._page(number, package.readable(item), anchors))
        return tuple(pages), anchors

    def _page(self, number: int, item: _Item, anchors: Anchors) -> Page:
        anchors.pages.setdefault(item.path, number)
        data = self.read(item.path)
        if item.media_type in _XHTML_TYPES:
            reader = PageReader(number, item.path, anchors)
            try:
                reader.read(_decode(data))
            except (AssertionError, ValueError) as error:  # html.parser gave up
                raise ExtractionError(
                    f"{self.name}: the EPUB is damaged: {item.path} cannot be read"
                ) from error
            return reader.page()
        if item.media_type.startswith("image/"):  # an image in the reading order
            picture = Picture(f"p{number}-i1", ref=item.path)
            return Page(number, pictures=(picture,), order=(picture.id,))
        return Page(number)

    def outline(self, package: _Package, anchors: Anchors) -> tuple[OutlineEntry, ...]:
        """The table of contents as the file stores it; a damaged one gives what could be
        read, never an error (D-311)."""
        try:
            if package.nav is not None:
                data = self.read(package.nav.path, missing_ok=True)
                if data:
                    found = _NavReader.entries(_decode(data), package.nav.path)
                    if found:
                        return _outline(found, anchors)
            if package.ncx is not None:
                data = self.read(package.ncx.path, missing_ok=True)
                if data:
                    return _outline(
                        _ncx_entries(_xml(data, self, "NCX"), package.ncx.path), anchors
                    )
        except (ExtractionError, ValueError, AssertionError):  # AssertionError: html.parser
            return ()
        return ()


def _xml(data: bytes, book: _Book, what: str) -> ET.Element:
    """A small XML file of the package, refused when it declares an entity (D-305)."""

    def refuse(*_: object) -> None:
        raise ValueError("entity declared")

    checker = expat.ParserCreate()
    checker.EntityDeclHandler = refuse
    checker.UnparsedEntityDeclHandler = refuse
    try:
        checker.Parse(data, True)
        # Safe here: the checker above refused any entity declaration, and ElementTree
        # never loads an external DTD or entity.
        return ET.fromstring(data)  # noqa: S314
    except (expat.ExpatError, ET.ParseError, ValueError, LookupError) as error:
        raise ExtractionError(f"{book.name}: the EPUB's {what} is damaged") from error


def _local(tag: object) -> str:
    """An element or attribute name without its namespace."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _decode(data: bytes) -> str:
    """XHTML bytes as text: a byte-order mark first, then the XML declaration, else UTF-8;
    bytes that don't decode become U+FFFD (D-315)."""
    for bom, codec in (
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    ):
        if data.startswith(bom):
            return data[len(bom) :].decode(codec, errors="replace")
    codec = "utf-8"
    if found := _ENCODING.match(data[:200]):
        try:
            codec = codecs.lookup(found.group(1).decode("ascii")).name
        except LookupError:
            codec = "utf-8"
        if codec.startswith("utf-16") or codec.startswith("utf-32"):
            codec = "utf-8"  # declared but written without a byte-order mark: not readable
    try:
        return data.decode(codec, errors="replace")
    except (LookupError, ValueError):  # not a text codec (hex, base64) or one that can't
        return data.decode("utf-8", errors="replace")  # replace (idna, punycode)


# ---- the package file ------------------------------------------------------------------


@dataclass(frozen=True)
class _Item:
    id: str
    path: str  # inside the zip
    media_type: str
    properties: frozenset[str] = frozenset()
    fallback: str = ""


@dataclass
class _Package:
    path: str
    manifest: dict[str, _Item]
    spine: list[str]  # manifest ids in reading order
    nav: _Item | None
    ncx: _Item | None
    metadata: ET.Element | None
    unique_id: str
    cover_id: str  # from <meta name="cover"> (EPUB 2)

    @classmethod
    def parse(cls, path: str, root: ET.Element) -> _Package:
        manifest: dict[str, _Item] = {}
        spine: list[str] = []
        toc = ""
        metadata = None
        cover_id = ""
        for element in root:
            kind = _local(element.tag)
            if kind == "metadata":
                metadata = element
                for meta in element.iter():
                    if _local(meta.tag) == "meta" and meta.get("name") == "cover":
                        cover_id = cover_id or meta.get("content", "")
            elif kind == "manifest":
                for entry in element:
                    if _local(entry.tag) != "item" or not entry.get("id") or not entry.get("href"):
                        continue
                    target, _ = resolve(path, entry.get("href", ""))
                    if target is None:
                        continue
                    manifest.setdefault(
                        entry.get("id", ""),
                        _Item(
                            entry.get("id", ""),
                            target,
                            entry.get("media-type", "").strip().lower(),
                            frozenset(entry.get("properties", "").split()),
                            entry.get("fallback", ""),
                        ),
                    )
            elif kind == "spine":
                toc = element.get("toc", "")
                spine = [
                    ref.get("idref", "")
                    for ref in element
                    if _local(ref.tag) == "itemref" and ref.get("idref")
                ]
        nav = next((i for i in manifest.values() if "nav" in i.properties), None)
        ncx = manifest.get(toc) or next(
            (i for i in manifest.values() if i.media_type == "application/x-dtbncx+xml"), None
        )
        return cls(
            path, manifest, spine, nav, ncx, metadata, root.get("unique-identifier", ""), cover_id
        )

    def readable(self, item: _Item) -> _Item:
        """The item itself if it is XHTML, SVG or an image, else the first readable item in
        its fallback chain, else the item (an empty page)."""
        seen = {item.id}
        current = item
        while current.media_type not in _XHTML_TYPES and current.fallback:
            following = self.manifest.get(current.fallback)
            if following is None or following.id in seen:
                break
            seen.add(following.id)
            current = following
        if current.media_type in _XHTML_TYPES:
            return current
        return item

    def cover(self) -> _Item | None:
        """The cover image the package declares (D-313): EPUB 3, else EPUB 2."""
        for item in self.manifest.values():
            if "cover-image" in item.properties:
                return item
        return self.manifest.get(self.cover_id) if self.cover_id else None


def _metadata(package: _Package) -> Metadata:
    """Title, authors, date, identifier and language as the package states them (D-312)."""
    if package.metadata is None:
        return Metadata()
    elements = list(package.metadata.iter())

    def dc(name: str) -> list[ET.Element]:
        return [e for e in elements if _local(e.tag) == name and "purl.org/dc" in str(e.tag)]

    roles: dict[str, list[str]] = {}
    for meta in elements:
        if _local(meta.tag) == "meta" and meta.get("property") == "role":
            target = meta.get("refines", "").lstrip("#")
            roles.setdefault(target, []).append((meta.text or "").strip().lower())
    authors = []
    for creator in dc("creator"):
        own = [v.strip().lower() for k, v in creator.attrib.items() if _local(k) == "role"]
        given = own + roles.get(creator.get("id", ""), [])
        text = fold("".join(creator.itertext()))
        if text and (not given or "aut" in given):
            authors.append(text)
    titles = [t for t in (fold("".join(e.itertext())) for e in dc("title")) if t]
    dates = [d for d in (fold("".join(e.itertext())) for e in dc("date")) if d]
    date = ""
    if dates and (found := _DATE.match(dates[0])):
        date = "-".join(part for part in found.groups() if part)
    identifiers = dc("identifier")
    chosen = next(
        (e for e in identifiers if package.unique_id and e.get("id") == package.unique_id), None
    )
    languages = [t for t in (fold("".join(e.itertext())) for e in dc("language")) if t]
    return Metadata(
        title=titles[0] if titles else "",
        authors=tuple(authors),
        date=date,
        identifier=fold("".join(chosen.itertext())) if chosen is not None else "",
        language=languages[0] if languages else "",
    )


# ---- the outline ---------------------------------------------------------------------------


@dataclass
class _Entry:
    title: str
    level: int
    path: str | None = None
    fragment: str = ""


class _NavReader(HTMLParser):
    """The entries of the navigation document's `nav epub:type="toc"`, in order (D-311)."""

    def __init__(self, path: str) -> None:
        super().__init__(convert_charrefs=True)
        self.path = path
        self.found: list[_Entry] = []
        self.nav = 0  # depth inside the toc nav (0: outside)
        self.lists = 0  # <ol>/<ul> depth inside it
        self.label: list[str] | None = None  # text of the label being read
        self.label_tag = ""
        self.labelled: list[bool] = []  # per open <li>: label read already
        self.done = False

    @classmethod
    def entries(cls, text: str, path: str) -> list[_Entry]:
        reader = cls(path)
        reader.feed(text)
        reader.close()
        return reader.found

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if self.done:
            return
        if tag == "nav":
            if self.nav:
                self.nav += 1
            elif "toc" in (values.get("epub:type") or "").split():
                self.nav = 1
            return
        if not self.nav:
            return
        if tag in ("ol", "ul"):
            self.lists += 1
        elif tag == "li":
            self.labelled.append(False)
            self.found.append(_Entry("", self.lists))
        elif (
            tag in ("a", "span") and self.labelled and not self.labelled[-1] and self.label is None
        ):
            self.label, self.label_tag = [], tag
            if tag == "a" and (href := values.get("href")):
                path, fragment = resolve(self.path, href)
                self.found[-1].path, self.found[-1].fragment = path, fragment

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag in ("a", "span", "li", "ol", "ul", "nav"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.nav or self.done:
            return
        if tag == "nav":
            self.nav -= 1
            self.done = self.nav == 0
        elif tag in ("ol", "ul"):
            self.lists = max(0, self.lists - 1)
        elif tag == "li" and self.labelled:
            self.labelled.pop()
        elif tag == self.label_tag and self.label is not None:
            self.found[-1].title = fold("".join(self.label))
            self.label, self.label_tag = None, ""
            if self.labelled:  # its <li> may have closed first in damaged markup
                self.labelled[-1] = True

    def handle_data(self, data: str) -> None:
        if self.label is not None:
            self.label.append(data)


def _ncx_entries(root: ET.Element, path: str) -> list[_Entry]:
    found: list[_Entry] = []

    def walk(parent: ET.Element, level: int) -> None:
        if level > MAX_OUTLINE_LEVEL:
            return
        for point in parent:
            if _local(point.tag) != "navPoint":
                continue
            title = ""
            source = None
            for child in point:
                if _local(child.tag) == "navLabel":
                    texts = [t for t in child if _local(t.tag) == "text"]
                    title = fold("".join(texts[0].itertext())) if texts else ""
                elif _local(child.tag) == "content" and source is None:
                    source = child.get("src")
            entry = _Entry(title, level)
            if source:
                entry.path, entry.fragment = resolve(path, source)
            found.append(entry)
            walk(point, level + 1)

    for element in root:
        if _local(element.tag) == "navMap":
            walk(element, 1)
    return found


def _outline(entries: list[_Entry], anchors: Anchors) -> tuple[OutlineEntry, ...]:
    out: list[OutlineEntry] = []
    for entry in entries:
        level = min(max(entry.level, 1), out[-1].level + 1 if out else 1)
        if level > MAX_OUTLINE_LEVEL:
            continue
        page = anchors.pages.get(entry.path) if entry.path else None
        item = ""
        if page is not None and entry.path and entry.fragment:
            target = anchors.items.get((entry.path, entry.fragment), "")
            item = "" if target == f"p{page}" else target
        out.append(OutlineEntry(entry.title, level, page, item))
    return tuple(out)
