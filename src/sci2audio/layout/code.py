"""Code listings in a PDF: one CODE placeholder block each (#280, D-542, D-543).

A program listing is set in a typewriter font, and layout reads its short lines as one
paragraph each (the seaborn paper's Python example was ten). Read aloud, code is noise
("g equals sns.relplot open bracket"), so it becomes a placeholder like a figure: a text
step reads a short notice instead, and the player shows the code.

- A line is **monospace** when every run with visible text is in a typewriter font, known
  by its name (`monospace`), and none is larger than the body text (a package name set as
  a title is not code). A run made only of lines set wholly in bold is not code (that is a
  heading's look); a bold keyword line ("end") inside a listing is part of it.
- Code can only be told from text where the text is not itself typewriter type: when most
  of the document's letters are in a typewriter font (a typed memo, an RFC, a text file
  printed to PDF), nothing is code.
- Whether a document is typed and the size its body text is set in are judged once per
  document (`body_text`, #794), from its text lines without the furniture: a running head
  set in Courier says nothing about the body. Paragraphs (which start a listing on a block
  of its own), captions (which cut a listing off) and `find_code` all use that one
  judgement, so no line is cut as code by one and kept as prose by another.
- After headings are found, a run of PARAGRAPH blocks next to each other in reading
  order, each made only of monospace lines, is one CODE block: its parts in order, its text
  the blocks' texts joined by line breaks. Headings, captions, notes, list items and
  furniture are never taken, a paragraph that mixes a monospace word into prose stays,
  and a run never spans the start of a section.
- A run that is only links stays a paragraph: its lines put together are one URL, e-mail
  address or DOI (nowak's GitHub address under the authors, broken over two lines), or
  every word of it is one ("alice@uni-x.de" and "bob@uni-y.org" on two lines, ACL's
  "{alice,bob}@cs.uni-x.edu"). The links step reads them.

- A listing broken by a page break is one CODE block (#283): code paragraphs with only
  furniture between them (the page number at one page's foot, the running head at the
  next one's top), the later one starting on a later page and no section, are one run. The
  furniture is read just after the CODE block, as what met a paragraph running on across
  a page waits until it ends. Anything else between (a footnote, a figure, a caption)
  ends the run, and so does furniture between two code paragraphs on one page.
- A listing's caption ("Listing 3: ...", German "Quelltext 3", #281) names the CODE block
  next to it in reading order, before or after it; when both are code, the nearer on the
  page in its column. A CODE block is named by one such caption at most, and a listing
  caption with no CODE block next to it names nothing.

A listing's indentation is not rebuilt here: a PDF line holds no leading white space, and
layout adds no text. The player draws the indent from the line boxes (`web/player.py`
`indented`, #282).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from sci2audio.core import Block, BlockKind, Box, Content, Part, Section, TextLine, TextRun

# Typewriter fonts by name: "LMMono10-Regular", "Courier", "Inconsolatazi4", "NimbusMonL",
# "Consolas", "SourceCodePro", "FiraCode", TeX Gyre Cursor, and TeX's typewriter families
# ("CMTT10", "SFTT1000", "txtt"). Not a bare "code" (Lucida Sans Unicode, Encode Sans,
# Barcode) nor American Typewriter, which are proportional.
_MONOSPACE = re.compile(
    r"mono(?!type)|courier|(?<!american)typewriter|consol|menlo|monaco|inconsolata|cousine"
    r"|nimbusmon|cursor|sourcecode|firacode|cascadia|codenewroman"
    r"|^(?:cm|sf|ec|tc|tx|lc|lm|pcr)tt",
    re.IGNORECASE,
)
_BOLD = re.compile(r"bold|black|heavy", re.IGNORECASE)
_LINK = re.compile(
    r"(?:https?://|ftp://|www\.|doi:\s*|10\.\d{4,9}/)\S+"
    r"|(?:[\w.+-]+|\{[\w.+-]+(?:,[\w.+-]+)*\})@[\w-]+(?:\.[\w-]+)+",
    re.IGNORECASE,
)
_BRACES = re.compile(r"\{[^{}]*\}")
LISTING = ("Listing", "LISTING", "Quelltext", "QUELLTEXT")  # a listing's caption labels
_LARGER = 1.1  # a run more than this times the body size is larger than the body text


def monospace(font: str) -> bool:
    """True if the font, by its name, is a typewriter font."""
    return bool(_MONOSPACE.search(font))


def monospace_line(line: TextLine, size: float = 0.0) -> bool:
    """True if every run of the line with visible text is in a typewriter font and none is
    larger than the body text (`size`; 0 if unknown, then any size)."""
    shown = [run for run in line.runs if run.text.strip()]
    return bool(shown) and all(
        monospace(run.font) and not (size and run.size > _LARGER * size) for run in shown
    )


@dataclass(frozen=True)
class BodyText:
    """The judgement that tells code from a document's text, made once per document (#794):
    whether most of its letters are typewriter type (`typed`: then nothing is code), and the
    size its body text is set in (`size`; 0 if unknown)."""

    typed: bool
    size: float


def body_text(lines: Iterable[TextLine]) -> BodyText:
    """The judgement over these text lines: the document's own, without its furniture."""
    letters: Counter[bool] = Counter()
    sizes: Counter[float] = Counter()
    for line in lines:
        for run in line.runs:
            letters[monospace(run.font)] += sum(c.isalpha() for c in run.text)
            sizes[run.size] += len(run.text)
    size = sizes.most_common(1)[0][0] if sizes else 0.0
    return BodyText(letters[True] > letters[False], size)


def find_code(
    blocks: list[Block], sections: tuple[Section, ...], content: Content, body: BodyText
) -> tuple[list[Block], tuple[Section, ...]]:
    """The blocks with each run of paragraphs made only of monospace lines joined into one
    CODE block, and the sections and caption links moved to the new block numbers; `body`
    is the document's judgement (`body_text`): in a typed document nothing is code."""
    if body.typed:
        return blocks, sections
    size = body.size
    items = content.items()
    lines = {item.id: item for _, item in items.values() if isinstance(item, TextLine)}
    page_of = {key: page.number for key, (page, _) in items.items()}
    starts = {section.start for section in _all(sections)}
    groups: list[_Group] = []
    held: list[int] = []  # furniture met while a code run is open
    for number, block in enumerate(blocks):
        code = _code_paragraph(block, lines, size)
        run = groups[-1] if groups and groups[-1].code else None
        if code and run and number not in starts:
            last = blocks[run.members[-1]]
            if not held or page_of[block.parts[0].item] > page_of[last.parts[-1].item]:
                run.members.append(number)
                run.carried += held  # read after the joined block (#283)
                held = []
                continue
        if run and block.kind is BlockKind.FURNITURE:
            held.append(number)
            continue
        groups += [_Group([k], False) for k in held]
        held = []
        groups.append(_Group([number], code))
    groups += [_Group([k], False) for k in held]
    kept: list[_Group] = []
    for group in groups:
        run = [blocks[k] for k in group.members]
        if group.code and (only_links("\n".join(b.text for b in run)) or _all_bold(run, lines)):
            # only links or only bold: as printed, in the order read
            kept += [_Group([k], False) for k in sorted(group.members + group.carried)]
        else:
            kept.append(group)
            kept += [_Group([k], False) for k in group.carried]
    new_of = {old: new for new, group in enumerate(kept) for old in group.members}
    out = [
        _joined([blocks[k] for k in group.members]) if group.code else blocks[group.members[0]]
        for group in kept
    ]
    out = [
        replace(block, describes=new_of[block.describes]) if block.describes is not None else block
        for block in out
    ]
    out = _listing_captions(out, lines, page_of)
    return out, tuple(_moved(section, new_of, len(out)) for section in sections)


@dataclass
class _Group:
    """Old block numbers that become one new block (several only for code), and the
    furniture met inside a code run, read after it."""

    members: list[int]
    code: bool
    carried: list[int] = field(default_factory=list)


def _listing_captions(
    blocks: list[Block], lines: dict[str, TextLine], page_of: dict[str, int]
) -> list[Block]:
    """The blocks with each listing caption that names nothing naming the CODE block next to
    it: the nearer one on the page if both neighbours are code (#281)."""
    out = list(blocks)
    named = {block.describes for block in blocks if block.describes is not None}
    for k, block in enumerate(blocks):
        if block.kind is not BlockKind.CAPTION or block.describes is not None:
            continue
        if not block.label.startswith(LISTING):
            continue
        near = [
            (_white(block, blocks[n], n < k, lines, page_of), n)
            for n in (k - 1, k + 1)
            if 0 <= n < len(blocks) and blocks[n].kind is BlockKind.CODE and n not in named
        ]
        if near:
            n = min(near)[1]
            out[k] = replace(block, describes=n)
            named.add(n)
    return out


def _white(
    caption: Block, code: Block, above: bool, lines: dict[str, TextLine], page_of: dict[str, int]
) -> float:
    """The white between a caption and the code block before (`above`) or after it, from
    the caption's lines to the code's nearest line; infinite on another page, in another
    column (the lines do not overlap across) or unknown."""
    own = [part.item for part in caption.parts if part.item in lines]
    other = [part.item for part in code.parts if part.item in lines]
    if not own or not other:
        return math.inf
    edge, near = (own[0], other[-1]) if above else (own[-1], other[0])
    a, b = lines[edge].box, lines[near].box
    if page_of[edge] != page_of[near] or a is None or b is None:
        return math.inf
    if a.x1 <= b.x0 or b.x1 <= a.x0:  # in another column: farther, as on another page
        return math.inf
    return _gap(b, a) if above else _gap(a, b)


def _gap(upper: Box, lower: Box) -> float:
    return lower.y0 - upper.y1


def _code_paragraph(block: Block, lines: dict[str, TextLine], size: float) -> bool:
    if block.kind is not BlockKind.PARAGRAPH or not block.parts:
        return False
    return all(
        part.item in lines and monospace_line(lines[part.item], size) for part in block.parts
    )


def _all_bold(blocks: list[Block], lines: dict[str, TextLine]) -> bool:
    """True if every line of the blocks is set wholly in bold: a heading's look, not a
    listing's, which may set a keyword line ("end") in bold among the others."""
    return all(
        all(_bold(run) for run in lines[part.item].runs if run.text.strip())
        for block in blocks
        for part in block.parts
    )


def _bold(run: TextRun) -> bool:
    return run.bold or bool(_BOLD.search(run.font))


def only_links(text: str) -> bool:
    """True if the text is only links: one when put together, or one per word."""
    if _LINK.fullmatch("".join(text.split())):
        return True
    words = _BRACES.sub(lambda braces: "".join(braces[0].split()), text).split()
    return bool(words) and all(_LINK.fullmatch(word.strip(".,;")) for word in words)


def _joined(run: list[Block]) -> Block:
    parts: list[Part] = []
    texts: list[str] = []
    start = 0
    for block in run:
        parts += [Part(part.item, start + part.start) for part in block.parts]
        texts.append(block.text)
        start += len(block.text) + 1
    return Block(BlockKind.CODE, "\n".join(texts), tuple(parts))


def _all(sections: tuple[Section, ...]) -> list[Section]:
    return [s for section in sections for s in (section, *_all(section.children))]


def _moved(section: Section, new_of: dict[int, int], total: int) -> Section:
    start = new_of.get(section.start, total)
    end = new_of[section.end - 1] + 1 if section.end > section.start else start
    children = tuple(_moved(child, new_of, total) for child in section.children)
    return replace(section, start=start, end=end, children=children)
