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
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import Counter
from dataclasses import dataclass, field, replace
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.parsers import expat

from sci2audio.core import (
    Content,
    Metadata,
    OutlineEntry,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.extraction.cover import Cover, media_type
from sci2audio.extraction.errors import ExtractionError

MAX_MEMBER = 64 * 1024 * 1024  # bytes one file in the zip may unpack to
MAX_TOTAL = 512 * 1024 * 1024  # bytes all files read from one EPUB may unpack to
MAX_SPINE = 10_000  # documents in the reading order
MAX_COVER = 20 * 1024 * 1024  # bytes of a cover image
MAX_TAGGED = 100  # nested elements that add tags; deeper ones add none
MAX_TAGS = 200  # tags one element carries, its ancestors' included; more are left out
MAX_OUTLINE_LEVEL = 15  # as for PDF bookmarks (D-267)

CONTAINER = "META-INF/container.xml"
_DRM_FILES = ("META-INF/rights.xml", "META-INF/sinf.xml", "META-INF/license.lcpl")
# Font obfuscation (IDPF and Adobe) hides fonts only; it is not DRM and no text is encrypted.
_FONT_OBFUSCATION = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}

_XHTML_TYPES = {"application/xhtml+xml", "text/html", "image/svg+xml"}
# HTML block elements (and SVG text): each one ends the line before it and starts a new one.
_BLOCKS = frozenset(
    {
        *("address", "article", "aside", "blockquote", "body", "caption", "center", "dd"),
        *("details", "dialog", "dir", "div", "dl", "dt", "fieldset", "figcaption", "figure"),
        *("footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr"),
        *("html", "legend", "li", "main", "menu", "nav", "ol", "p", "pre", "search"),
        *("section", "summary", "table", "tbody", "td", "text", "tfoot", "th", "thead"),
        *("tr", "ul"),
    }
)
_VOID = frozenset(
    {
        *("area", "base", "br", "col", "embed", "hr", "img", "input", "image", "link"),
        *("meta", "param", "source", "track", "wbr"),
    }
)
_SKIPPED = frozenset({"head", "script", "style", "template"})
_BOLD = frozenset({"b", "strong", "th", "h1", "h2", "h3", "h4", "h5", "h6"})
_ITALIC = frozenset({"i", "em", "cite", "dfn", "var", "address"})
_WHITE = re.compile(r"[ \t\n\r\f]+")  # HTML's ASCII white space; a no-break space is text
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
        pages = _resolve_links(pages, anchors)
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
        path = _clean((preferred or roots)[0].get("full-path", ""))
        if path is None or path not in self.members:
            shown = (preferred or roots)[0].get("full-path", "")
            raise ExtractionError(f"{self.name}: the EPUB's package file {shown} is missing")
        return _Package.parse(path, _xml(self.read(path), self, "package file"))

    def pages(self, package: _Package) -> tuple[tuple[Page, ...], _Anchors]:
        if not package.spine:
            raise ExtractionError(f"{self.name}: the EPUB has no chapters")
        if len(package.spine) > MAX_SPINE:
            raise ExtractionError(f"{self.name}: the EPUB is too large or damaged")
        anchors = _Anchors()
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

    def _page(self, number: int, item: _Item, anchors: _Anchors) -> Page:
        anchors.pages.setdefault(item.path, number)
        data = self.read(item.path)
        if item.media_type in _XHTML_TYPES:
            reader = _Reader(number, item.path, anchors)
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

    def outline(self, package: _Package, anchors: _Anchors) -> tuple[OutlineEntry, ...]:
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


def _clean(path: str) -> str | None:
    """A path inside the zip, normalised; None if it leaves the zip's root."""
    path = posixpath.normpath(path.lstrip("/"))
    if path in (".", "") or path.startswith("../") or path == "..":
        return None
    return path


def _resolve(base: str, href: str) -> tuple[str | None, str]:
    """The zip path and fragment an `href` in the file at `base` points at; the path is None
    when the link leaves the book (a web address, mail, or a path outside the zip) and for
    an address that cannot be parsed at all (e.g. "http://[x")."""
    try:
        parts = urlsplit(href)
    except ValueError:
        return None, ""
    fragment = unquote(parts.fragment)
    if parts.scheme or parts.netloc:
        return None, fragment
    if not parts.path:
        return base, fragment
    return _clean(posixpath.join(posixpath.dirname(base), unquote(parts.path))), fragment


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


def _fold(text: str) -> str:
    return _WHITE.sub(" ", text).strip(" ")


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
                    target, _ = _resolve(path, entry.get("href", ""))
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
        text = _fold("".join(creator.itertext()))
        if text and (not given or "aut" in given):
            authors.append(text)
    titles = [t for t in (_fold("".join(e.itertext())) for e in dc("title")) if t]
    dates = [d for d in (_fold("".join(e.itertext())) for e in dc("date")) if d]
    date = ""
    if dates and (found := _DATE.match(dates[0])):
        date = "-".join(part for part in found.groups() if part)
    identifiers = dc("identifier")
    chosen = next(
        (e for e in identifiers if package.unique_id and e.get("id") == package.unique_id), None
    )
    languages = [t for t in (_fold("".join(e.itertext())) for e in dc("language")) if t]
    return Metadata(
        title=titles[0] if titles else "",
        authors=tuple(authors),
        date=date,
        identifier=_fold("".join(chosen.itertext())) if chosen is not None else "",
        language=languages[0] if languages else "",
    )


# ---- the text of a spine document --------------------------------------------------------


@dataclass
class _Anchors:
    """Where each anchor of the book lands, for links and the outline, filled while reading."""

    pages: dict[str, int] = field(default_factory=dict)  # zip path → page number
    items: dict[tuple[str, str], str] = field(default_factory=dict)  # (path, id) → item id
    links: list[tuple[str, str | None, str]] = field(default_factory=list)  # base, path, frag

    def target(self, path: str | None, fragment: str) -> str | None:
        """`link:` target for a place in the book: an item id, or "p<n>" for a whole page."""
        if path is None or path not in self.pages:
            return None
        if fragment:
            return self.items.get((path, fragment))
        return f"p{self.pages[path]}"


@dataclass
class _Element:
    name: str
    tags: tuple[str, ...]  # its own tags and its ancestors', outermost first
    bold: bool
    italic: bool
    tagged: int  # elements on the way down that added tags, this one included


_LINK = "\x00link:"  # a placeholder tag, replaced once every page is read


class _Reader(HTMLParser):
    """One spine document into lines and pictures, in the order the file stores them.

    Work per element and per piece of text does not grow with the nesting depth, so a
    deeply nested hostile file is read in linear time.
    """

    def __init__(self, number: int, path: str, anchors: _Anchors) -> None:
        super().__init__(convert_charrefs=True)
        self.number, self.path, self.anchors = number, path, anchors
        self.stack: list[_Element] = []
        self.open: Counter[str] = Counter()  # open elements by name
        self.svgs: list[tuple[list[str], list[int]]] = []  # per open <svg>: title, pictures
        self.segments: list[tuple[str, tuple[str, ...], bool, bool]] = []
        self.lines: list[TextLine] = []
        self.pictures: list[Picture] = []
        self.order: list[str] = []
        self.waiting: list[Picture] = []  # pictures inside the line being read
        self.pending: list[str] = []  # anchors waiting for the next item
        self.continues = False  # the next line continues an element after a <br>

    def read(self, text: str) -> None:
        self.feed(text)
        self.close()
        self.flush()

    def page(self) -> Page:
        for anchor in self.pending:  # anchors after the last item point at the whole page
            self.anchors.items.setdefault((self.path, anchor), f"p{self.number}")
        return Page(
            self.number,
            lines=tuple(self.lines),
            pictures=tuple(self.pictures),
            order=tuple(self.order),
        )

    @property
    def skipping(self) -> bool:
        return any(self.open[name] for name in _SKIPPED)

    # -- parser callbacks

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start(tag, dict(attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start(tag, dict(attrs))
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.open[tag]:
            return
        if tag in _BLOCKS and not self.skipping:
            self.flush()
            self.continues = False
        while self.stack:
            element = self.stack.pop()
            self.closed(element)
            if element.name == tag:
                return

    def unknown_decl(self, data: str) -> None:
        if data.startswith("CDATA["):  # XHTML may wrap text in a CDATA section
            self.handle_data(data[len("CDATA[") :])

    def handle_data(self, data: str) -> None:
        if self.skipping:
            return
        if self.open["title"] and self.svgs:
            self.svgs[-1][0].append(data)  # an SVG's title is its pictures' alternative text
            return
        if self.open["pre"]:  # (a line feed right after <pre> gives an empty line: none)
            first, *rest = data.split("\n")
            self.add(first)
            for piece in rest:
                self.flush(continued=True)
                self.add(piece)
            return
        self.add(data)

    # -- building

    def start(self, tag: str, attrs: dict[str, str | None]) -> None:
        parent = self.stack[-1] if self.stack else None
        if self.skipping or tag in _SKIPPED:
            if tag not in _VOID:
                self.push(_Element(tag, parent.tags if parent else (), False, False, 0))
            return
        if tag in _BLOCKS or tag == "br":
            self.flush(continued=tag == "br")
            if tag != "br":
                self.continues = False
        if anchor := attrs.get("id"):
            self.pending.append(anchor)
        if tag in ("img", "image"):
            self.picture(attrs)
        if tag in _VOID:
            return
        tagged = parent.tagged if parent else 0
        own: tuple[str, ...] = ()
        inherited = parent.tags if parent else ()
        if tag not in ("html", "body") and tagged < MAX_TAGGED:
            own, tagged = self.tags(tag, attrs)[: MAX_TAGS - len(inherited)], tagged + 1
        self.push(
            _Element(
                tag,
                inherited + own,
                tag in _BOLD or bool(parent and parent.bold),
                tag in _ITALIC or bool(parent and parent.italic),
                tagged,
            )
        )
        if tag == "svg":
            self.svgs.append(([], []))

    def push(self, element: _Element) -> None:
        self.stack.append(element)
        self.open[element.name] += 1

    def closed(self, element: _Element) -> None:
        self.open[element.name] -= 1
        if element.name == "svg" and self.svgs and not self.skipping:
            title, indexes = self.svgs.pop()
            alt = _fold("".join(title))
            for index in indexes:
                self.pictures[index] = replace(self.pictures[index], alt=alt)

    def tags(self, tag: str, attrs: dict[str, str | None]) -> tuple[str, ...]:
        found = [tag]
        if anchor := attrs.get("id"):
            found.append(f"#{anchor}")
        found += [f"epub:{token}" for token in (attrs.get("epub:type") or "").split()]
        found += [f"role:{token}" for token in (attrs.get("role") or "").split()]
        if language := (attrs.get("lang") or attrs.get("xml:lang") or "").strip():
            found.append(f"lang:{language}")
        if "hidden" in attrs:
            found.append("hidden")
        if (attrs.get("aria-hidden") or "").strip().lower() == "true":
            found.append("aria-hidden")
        if tag == "a" and (href := attrs.get("href")) is not None:
            path, fragment = _resolve(self.path, href)
            self.anchors.links.append((href, path, fragment))
            found.append(f"{_LINK}{len(self.anchors.links) - 1}")
        return tuple(found)

    def picture(self, attrs: dict[str, str | None]) -> None:
        source = attrs.get("src") or attrs.get("xlink:href") or attrs.get("href") or ""
        ref = ""
        if source and not source.startswith("data:"):
            path, _ = _resolve(self.path, source)
            ref = path if path is not None else source
        number = len(self.pictures) + 1
        picture = Picture(f"p{self.number}-i{number}", alt=attrs.get("alt") or "", ref=ref)
        if self.svgs:
            self.svgs[-1][1].append(len(self.pictures))
        self.pictures.append(picture)
        if self.segments:  # inside a line: placed after that line
            self.waiting.append(picture)
        else:
            self.place(picture.id)

    def add(self, text: str) -> None:
        if not text:
            return
        top = self.stack[-1] if self.stack else None
        tags = top.tags if top else ()
        self.segments.append((text, tags, bool(top and top.bold), bool(top and top.italic)))

    def flush(self, continued: bool = False) -> None:
        """End the line being read; `continued` when a <br> or a line feed in <pre> ends it."""
        runs = _runs(self.segments, keep_white=self.open["pre"] > 0)
        self.segments = []
        if runs:
            if self.continues:
                runs = [replace(run, tags=(*run.tags, "br")) for run in runs]
            line = TextLine(f"p{self.number}-l{len(self.lines) + 1}", tuple(runs))
            self.lines.append(line)
            self.place(line.id)
            self.continues = continued
        elif not continued:
            self.continues = False
        for picture in self.waiting:
            self.place(picture.id)
        self.waiting = []

    def place(self, item: str) -> None:
        self.order.append(item)
        for anchor in self.pending:
            self.anchors.items.setdefault((self.path, anchor), item)
        self.pending = []


def _runs(
    segments: list[tuple[str, tuple[str, ...], bool, bool]], keep_white: bool
) -> list[TextRun]:
    """Runs from the pieces of one line, white space folded as a browser shows it (D-306)."""
    pieces: list[list] = []
    for text, tags, bold, italic in segments:
        if not keep_white:
            text = _WHITE.sub(" ", text)
            if text.startswith(" ") and (not pieces or pieces[-1][0].endswith(" ")):
                text = text[1:]
        if text:
            pieces.append([text, tags, bold, italic])
    if not keep_white:
        while pieces and not pieces[0][0].strip(" "):
            pieces.pop(0)
        while pieces and not pieces[-1][0].strip(" "):
            pieces.pop()
        if pieces:
            pieces[0][0] = pieces[0][0].lstrip(" ")
            pieces[-1][0] = pieces[-1][0].rstrip(" ")
    elif not "".join(piece[0] for piece in pieces).strip():
        return []
    runs: list[TextRun] = []
    for text, tags, bold, italic in pieces:
        if not text:
            continue
        if runs and (runs[-1].tags, runs[-1].bold, runs[-1].italic) == (tags, bold, italic):
            runs[-1] = replace(runs[-1], text=runs[-1].text + text)
        else:
            runs.append(TextRun(text, bold=bold, italic=italic, tags=tags))
    return runs


def _resolve_links(pages: tuple[Page, ...], anchors: _Anchors) -> tuple[Page, ...]:
    """Each link placeholder becomes `link:<item id>` (or `link:p<n>`) for a place in the
    book that was read, else `href:<as stored>` (D-307)."""
    if not anchors.links:
        return pages
    names = []
    for href, path, fragment in anchors.links:
        target = anchors.target(path, fragment)
        names.append(f"link:{target}" if target else f"href:{href}")

    def tag(value: str) -> str:
        return names[int(value[len(_LINK) :])] if value.startswith(_LINK) else value

    def resolved(run: TextRun) -> TextRun:
        if not any(value.startswith(_LINK) for value in run.tags):
            return run
        return replace(run, tags=tuple(map(tag, run.tags)))

    out = []
    for page in pages:
        lines = tuple(replace(line, runs=tuple(map(resolved, line.runs))) for line in page.lines)
        out.append(replace(page, lines=lines))
    return tuple(out)


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
                path, fragment = _resolve(self.path, href)
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
            self.found[-1].title = _fold("".join(self.label))
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
                    title = _fold("".join(texts[0].itertext())) if texts else ""
                elif _local(child.tag) == "content" and source is None:
                    source = child.get("src")
            entry = _Entry(title, level)
            if source:
                entry.path, entry.fragment = _resolve(path, source)
            found.append(entry)
            walk(point, level + 1)

    for element in root:
        if _local(element.tag) == "navMap":
            walk(element, 1)
    return found


def _outline(entries: list[_Entry], anchors: _Anchors) -> tuple[OutlineEntry, ...]:
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
