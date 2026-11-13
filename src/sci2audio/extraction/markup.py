"""Read one HTML or XHTML document into the lines and pictures of a page (D-306 to D-310).

Shared by the EPUB reader (one spine document per page) and the Markdown reader, which renders
Markdown to HTML first (D-340), so both give layout the same shape: one text line per block
element, made of styled runs whose tags are the markup around them (D-307), bold and italic
from the HTML default rendering (D-308), pictures with their alternative text and `ref`, and
`Page.order` for where they stand between the lines. `html.parser` recovers from malformed
markup and never expands custom entities or fetches anything.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from sci2audio.core import Page, Picture, TextLine, TextRun

MAX_TAGGED = 100  # nested elements that add tags; deeper ones add none
MAX_TAGS = 200  # tags one element carries, its ancestors' included; more are left out

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


def clean_path(path: str) -> str | None:
    """A path inside the zip, normalised; None if it leaves the zip's root."""
    path = posixpath.normpath(path.lstrip("/"))
    if path in (".", "") or path.startswith("../") or path == "..":
        return None
    return path


def resolve(base: str, href: str) -> tuple[str | None, str]:
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
    return clean_path(posixpath.join(posixpath.dirname(base), unquote(parts.path))), fragment


def fold(text: str) -> str:
    return _WHITE.sub(" ", text).strip(" ")


# ---- the text of one HTML document -------------------------------------------------------


@dataclass
class Anchors:
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


class PageReader(HTMLParser):
    """One spine document into lines and pictures, in the order the file stores them.

    Work per element and per piece of text does not grow with the nesting depth, so a
    deeply nested hostile file is read in linear time.
    """

    def __init__(self, number: int, path: str, anchors: Anchors) -> None:
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
            alt = fold("".join(title))
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
            path, fragment = resolve(self.path, href)
            self.anchors.links.append((href, path, fragment))
            found.append(f"{_LINK}{len(self.anchors.links) - 1}")
        return tuple(found)

    def picture(self, attrs: dict[str, str | None]) -> None:
        source = attrs.get("src") or attrs.get("xlink:href") or attrs.get("href") or ""
        ref = ""
        if source and not source.startswith("data:"):
            path, _ = resolve(self.path, source)
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


def resolve_links(pages: tuple[Page, ...], anchors: Anchors) -> tuple[Page, ...]:
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
