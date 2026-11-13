"""Layout for documents without positions: EPUB, Markdown and plain text (#75, D-405 to D-418).

A document none of whose items has a box is read from its tags (D-405); the PDF rules,
which read positions and fonts, never see it. Extraction gives one text line per block
element, a line after a ``<br>`` (or a wrapped line of a text file) tagged ``br``, runs that
carry their markup as tags, and `Page.order` for where pictures stand (D-306 to D-311,
D-340 to D-344). Layout reads each page in that order:

- A line tagged ``br`` continues the element of the line just before it; any other line,
  or a line after a picture, starts a new element. An element's lines are joined by line
  breaks, as a PDF paragraph's are. Its kind comes from its first line's **context**: the
  tags all its runs share, so an emphasis or inline maths inside a paragraph does not
  change it.
- Kinds, the first that applies: a line tagged ``hidden`` or ``aria-hidden`` is furniture
  without a role, a ``nav`` table of contents is furniture ``contents``, a whole-line page
  break marker is ``page-number`` (D-411); a note (``doc-endnote``, ``epub:footnote``, ... or
  an ``li`` inside a notes list) is a FOOTNOTE, one block per note (D-414: it stays where the
  file puts it); table lines are one TABLE per run of them, a ``caption`` inside cut out as
  a CAPTION before it (D-412); SVG text is a FIGURE; then the innermost of ``h1``-``h6``
  (HEADING), ``figcaption`` (CAPTION), maths (FORMULA) and ``li`` (LIST_ITEM, D-415);
  everything else, code blocks too (D-410), is a PARAGRAPH. Each picture is a FIGURE of its
  own with text "" (D-413), unless it stands between two lines of one table, note or SVG.
- A caption describes the placeholder next to it: a ``figcaption`` the one before it, else
  the one after it; a table's caption the one after it, else the one before it.
- Labels are printed in the text, as core asks: a heading's number as in PDF ("1.1"), a
  caption's label ("Table 2"), a display formula's number in brackets at its end, a note's
  mark only where its text starts with the mark its noteref links to (D-406). A list marker
  that HTML numbering adds is not text, so list items carry none.
- Heading levels are counted per page, an EPUB spine document or a whole Markdown file
  (D-407): the page's highest rank (``h1`` before ``h2``) gets the page's base level and each
  lower rank one more, gaps closed. The base level is the level of the first outline entry
  that points at the page (after the outline rules of #24), else the base of the page
  before, else 1; a heading an outline entry points at by its item takes that entry's level.
- Where a page has no heading, each outline entry pointing at it starts a section (D-408):
  at the block holding its item, or the page's first block. That block becomes the heading
  when its text is the entry's title (compared as in #24); otherwise the section is titled
  as the entry and starts at the block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    FurnitureRole,
    Item,
    OutlineEntry,
    Page,
    Part,
    Section,
    TextLine,
)
from sci2audio.layout.captions import caption_label
from sci2audio.layout.headings import (
    outline_entries,
    printed_number,
    section_tree,
    title,
    title_key,
)
from sci2audio.layout.settings import LayoutSettings

# tags that are not element names: attribute tokens (D-307) and flags
_TOKENS = ("#", "epub:", "role:", "lang:", "link:", "href:")
_FLAGS = frozenset({"br", "hidden", "aria-hidden"})
_HIDDEN = frozenset({"hidden", "aria-hidden"})
_NOTE = frozenset(
    {
        *("role:doc-endnote", "role:doc-footnote", "epub:endnote", "epub:footnote"),
        *("epub:rearnote", "epub:note"),
    }
)
_NOTES = frozenset({"role:doc-endnotes", "epub:endnotes", "epub:footnotes", "epub:rearnotes"})
_NOTE_REF = frozenset({"role:doc-noteref", "epub:noteref"})
_TOC = frozenset({"epub:toc", "role:doc-toc"})
_PAGE_BREAK = frozenset({"epub:pagebreak", "role:doc-pagebreak"})
_RANKS = {f"h{rank}": rank for rank in range(1, 7)}
_MATHS = frozenset({"math", "role:math"})
# a display formula's number in brackets at its end: "(1)", "(2.3)", "(A1)"
_FORMULA_NUMBER = re.compile(r"\((?P<label>[0-9A-Za-z]{1,6}(?:\.[0-9A-Za-z]{1,4})?)\)\s*\Z")

# kinds whose element may hold a picture: one standing between two of their lines joins them
_HOLD_PICTURES = frozenset({BlockKind.TABLE, BlockKind.FOOTNOTE, BlockKind.FIGURE})
_BEFORE, _AFTER = -1, 1  # where a caption looks first for what it describes


def positioned(content: Content) -> bool:
    """True if any item of the content has a box: then layout reads positions."""
    return any(
        item.box is not None
        for page in content.pages
        for item in (*page.lines, *page.pictures, *page.drawings)
    )


def build_tagged(content: Content, settings: LayoutSettings) -> Document:
    """The document of content without positions, read from its tags."""
    items = content.items()
    units = [unit for page in content.pages for unit in _merged(_units(page, items))]
    lines = {line.id: line for page in content.pages for line in page.lines}
    blocks = [_block(unit, lines) for unit in units]
    blocks = _described(blocks, units)
    blocks = _marked(blocks, lines)
    blocks, sections = _Sections(blocks, units, content, settings).build()
    return Document(
        content=content,
        language=settings.language or content.metadata.language or "en",
        blocks=tuple(blocks),
        sections=sections,
        page_labels=tuple("" for _ in content.pages),
    )


# ---- elements --------------------------------------------------------------------------


@dataclass
class _Unit:
    """An element of the page (or a picture), with the kind its tags give."""

    kind: BlockKind
    page: int
    items: list[Item] = field(default_factory=list)
    key: tuple[str, ...] | None = None  # units in a row with one key are one block
    role: FurnitureRole | None = None
    rank: int = 0  # a heading's rank: 1 for h1
    looks: int = _BEFORE  # a caption: where it looks first for what it describes


def _units(page: Page, items: dict[str, tuple[Page, Item]]) -> list[_Unit]:
    order = page.order or tuple(item.id for item in (*page.lines, *page.pictures, *page.drawings))
    units: list[_Unit] = []
    after_line = False
    for item_id in order:
        item = items[item_id][1]
        if isinstance(item, TextLine):
            if after_line and "br" in item.runs[0].tags:
                units[-1].items.append(item)
            else:
                units.append(_classified(item, page.number))
            after_line = True
        else:
            units.append(_Unit(BlockKind.FIGURE, page.number, [item]))
            after_line = False
    return units


def _merged(units: list[_Unit]) -> list[_Unit]:
    """Units in a row with one key as one; pictures between two of them join them."""
    out: list[_Unit] = []
    k = 0
    while k < len(units):
        unit = units[k]
        last = out[-1] if out else None
        if last is not None and last.key is not None and unit.key == last.key:
            last.items += unit.items
        elif last is not None and last.key and last.kind in _HOLD_PICTURES and _picture(unit):
            j = k
            while j < len(units) and _picture(units[j]):
                j += 1
            if j < len(units) and units[j].key == last.key:
                for picture in units[k:j]:
                    last.items += picture.items
                k = j
                continue
            out.append(unit)
        else:
            out.append(unit)
        k += 1
    return out


def _picture(unit: _Unit) -> bool:
    return unit.kind is BlockKind.FIGURE and unit.key is None


def _classified(line: TextLine, page: int) -> _Unit:
    context = _context(line)
    names = [tag for tag in context if _is_name(tag)]
    tags = set(context)
    unit = _Unit(BlockKind.PARAGRAPH, page, [line])
    if tags & _HIDDEN:
        unit.kind = BlockKind.FURNITURE
    elif "nav" in names and tags & _TOC:
        unit.kind, unit.role, unit.key = BlockKind.FURNITURE, FurnitureRole.CONTENTS, ("nav",)
    elif tags & _PAGE_BREAK:
        unit.kind, unit.role = BlockKind.FURNITURE, FurnitureRole.PAGE_NUMBER
    elif (note := _note_key(context)) is not None:
        unit.kind, unit.key = BlockKind.FOOTNOTE, note
    elif "table" in names:
        if "caption" in names[names.index("table") :]:
            unit.kind, unit.key, unit.looks = BlockKind.CAPTION, ("caption",), _AFTER
        else:
            unit.kind, unit.key = BlockKind.TABLE, ("table",)
    elif "svg" in names:
        unit.kind, unit.key = BlockKind.FIGURE, ("svg",)
    else:
        for tag in reversed(context):
            if tag in _MATHS:
                unit.kind = BlockKind.FORMULA
            elif tag in _RANKS:
                unit.kind, unit.rank = BlockKind.HEADING, _RANKS[tag]
            elif tag == "figcaption":
                unit.kind, unit.key = BlockKind.CAPTION, ("figcaption",)
            elif tag == "li":
                unit.kind = BlockKind.LIST_ITEM
            else:
                continue
            break
    return unit


def _context(line: TextLine) -> tuple[str, ...]:
    """The tags all the line's runs share, outermost first, without a closing ``br``."""
    first, *rest = (run.tags for run in line.runs)
    size = len(first)
    for tags in rest:
        size = min(size, len(tags))
        size = next((k for k in range(size) if tags[k] != first[k]), size)
    shared = first[:size]
    while shared and shared[-1] == "br":
        shared = shared[:-1]
    return shared


def _is_name(tag: str) -> bool:
    return tag not in _FLAGS and not tag.startswith(_TOKENS)


def _note_key(context: tuple[str, ...]) -> tuple[str, ...] | None:
    """The tags up to the note element's own, if the context is inside a note: an element
    with a note token, or an ``li`` inside a notes list."""
    in_notes = False
    names = [k for k, tag in enumerate(context) if _is_name(tag)]
    for n, k in enumerate(names):
        end = names[n + 1] if n + 1 < len(names) else len(context)
        own = set(context[k + 1 : end])
        if own & _NOTE or (in_notes and context[k] == "li"):
            return context[:end]
        in_notes = in_notes or bool(own & _NOTES)
    return None


# ---- blocks ----------------------------------------------------------------------------


def _block(unit: _Unit, lines: dict[str, TextLine]) -> Block:
    text, parts, with_line = "", [], False
    for item in unit.items:
        if isinstance(item, TextLine):
            if with_line:
                text += "\n"
            parts.append(Part(item.id, len(text)))
            text += item.text
            with_line = True
        else:
            parts.append(Part(item.id, len(text)))
    kind = unit.kind
    if kind is BlockKind.HEADING and not text.strip():
        kind = BlockKind.PARAGRAPH
    block = Block(kind, text, tuple(parts), role=unit.role)
    label = ""
    if kind is BlockKind.CAPTION:
        label = caption_label(block, lines) or ""
    elif kind is BlockKind.FORMULA and (found := _FORMULA_NUMBER.search(text)):
        label = found["label"]
    return Block(kind, text, tuple(parts), role=unit.role, label=label) if label else block


def _described(blocks: list[Block], units: list[_Unit]) -> list[Block]:
    """Each caption pointed at the placeholder next to it, if there is one."""
    out = list(blocks)
    for index, (block, unit) in enumerate(zip(blocks, units, strict=True)):
        if block.kind is not BlockKind.CAPTION:
            continue
        for step in (unit.looks, -unit.looks):
            other = index + step
            if 0 <= other < len(blocks) and blocks[other].is_placeholder:
                out[index] = replace(block, describes=other)
                break
    return out


def _marked(blocks: list[Block], lines: dict[str, TextLine]) -> list[Block]:
    """Each note labelled with the mark its noteref links to, where its text starts with it."""
    marks: dict[str, str] = {}
    for line in lines.values():
        for run in line.runs:
            if not _NOTE_REF & set(run.tags):
                continue
            for tag in run.tags:
                if tag.startswith("link:") and run.text.strip():
                    marks.setdefault(tag[len("link:") :], run.text.strip())
    out = []
    for block in blocks:
        if block.kind is BlockKind.FOOTNOTE:
            mark = next((marks[p.item] for p in block.parts if p.item in marks), "")
            if mark and "\n" not in mark and block.text.lstrip().startswith(mark):
                block = replace(block, label=mark)
        out.append(block)
    return out


# ---- headings and sections -------------------------------------------------------------


class _Sections:
    """Heading levels and the section tree (D-407, D-408)."""

    def __init__(
        self,
        blocks: list[Block],
        units: list[_Unit],
        content: Content,
        settings: LayoutSettings,
    ) -> None:
        self.blocks = list(blocks)
        self.units = units
        self.content = content
        self.entries = [e for e in outline_entries(content) if e.page is not None]
        letters = {
            label
            for block in blocks
            if block.kind is BlockKind.HEADING
            and (label := printed_number(title(block.text), lettered=True)[0])[:1].isalpha()
        }
        self.lettered = len(letters) >= settings.heading_repeats

    def build(self) -> tuple[list[Block], tuple[Section, ...]]:
        heads: dict[int, tuple[int, str]] = {}  # block index → level, title
        base = 1
        firsts = {e.page: e.level for e in reversed(self.entries)}
        by_item = {e.item: e.level for e in reversed(self.entries) if e.item}
        on_page: dict[int, list[int]] = {}
        for k, unit in enumerate(self.units):
            on_page.setdefault(unit.page, []).append(k)
        entries: dict[int, list[OutlineEntry]] = {}
        for entry in self.entries:
            entries.setdefault(entry.page or 0, []).append(entry)
        for page in self.content.pages:
            base = firsts.get(page.number, base)
            indexes = on_page.get(page.number, [])
            headings = [k for k in indexes if self.blocks[k].kind is BlockKind.HEADING]
            if headings:
                ranks = sorted({self.units[k].rank for k in headings})
                for k in headings:
                    level = base + ranks.index(self.units[k].rank)
                    level = next(
                        (by_item[p.item] for p in self.blocks[k].parts if p.item in by_item),
                        level,
                    )
                    heads[k] = (level, self._labelled(k))
            elif indexes:
                holding = {p.item: k for k in indexes for p in self.blocks[k].parts}
                for entry in entries.get(page.number, []):
                    k = holding.get(entry.item) if entry.item else indexes[0]
                    if k is not None and k not in heads:
                        self._from_entry(entry, k, heads)
        found = [(k, level, name) for k, (level, name) in sorted(heads.items())]
        return self.blocks, section_tree(found, len(self.blocks))

    def _labelled(self, k: int) -> str:
        """Give heading `k` its printed number as label; its section title."""
        block = self.blocks[k]
        name = title(block.text)
        label = printed_number(name, self.lettered)[0]
        if label and label in block.text:
            self.blocks[k] = replace(block, label=label)
        return name

    def _from_entry(self, entry: OutlineEntry, k: int, heads: dict[int, tuple[int, str]]) -> None:
        """The section an outline entry starts at block `k`, on a page without headings."""
        block = self.blocks[k]
        if block.kind is BlockKind.PARAGRAPH and block.text.strip() and self._names(entry, k):
            self.blocks[k] = replace(block, kind=BlockKind.HEADING)
            heads[k] = (entry.level, self._labelled(k))
        else:
            heads[k] = (entry.level, " ".join(entry.title.split()))

    def _names(self, entry: OutlineEntry, k: int) -> bool:
        """True if the block's text is the entry's title (#24: a printed number may be taken
        off the front of either)."""
        text = title(self.blocks[k].text)
        mine = {title_key(text), title_key(printed_number(text, self.lettered)[1])}
        theirs = {
            title_key(entry.title),
            title_key(printed_number(entry.title.strip(), self.lettered)[1]),
        }
        return bool(mine & theirs)
