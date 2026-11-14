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
- After headings are found, a run of PARAGRAPH blocks next to each other in reading
  order, each made only of monospace lines, is one CODE block: its parts in order, its text
  the blocks' texts joined by line breaks. Headings, captions, notes, list items and
  furniture are never taken, a paragraph that mixes a monospace word into prose stays,
  and a run never spans the start of a section.
- A run that is only links stays a paragraph: its lines put together are one URL, e-mail
  address or DOI (nowak's GitHub address under the authors, broken over two lines), or
  every word of it is one ("alice@uni-x.de" and "bob@uni-y.org" on two lines, ACL's
  "{alice,bob}@cs.uni-x.edu"). The links step reads them.

A listing broken by a page break is two CODE blocks (#283). Its indentation is not
rebuilt: a PDF line holds no leading white space, and layout adds no text (#282).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import replace

from sci2audio.core import Block, BlockKind, Content, Part, Section, TextLine, TextRun

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
_LARGER = 1.1  # a run more than this times the body size is larger than the body text


def monospace(font: str) -> bool:
    """True if the font, by its name, is a typewriter font."""
    return bool(_MONOSPACE.search(font))


def find_code(
    blocks: list[Block], sections: tuple[Section, ...], content: Content, size: float
) -> tuple[list[Block], tuple[Section, ...]]:
    """The blocks with each run of paragraphs made only of monospace lines joined into one
    CODE block, and the sections and caption links moved to the new block numbers; `size`
    is the body text's font size (0 if unknown)."""
    lines = {item.id: item for _, item in content.items().values() if isinstance(item, TextLine)}
    if _typewritten(lines.values()):
        return blocks, sections
    starts = {section.start for section in _all(sections)}
    groups: list[tuple[list[int], bool]] = []  # old block numbers of each new block; code?
    for number, block in enumerate(blocks):
        code = _code_paragraph(block, lines, size)
        if code and groups and groups[-1][1] and number not in starts:
            groups[-1][0].append(number)
        else:
            groups.append(([number], code))
    kept: list[tuple[list[int], bool]] = []
    for members, code in groups:
        run = [blocks[k] for k in members]
        if code and (_links("\n".join(b.text for b in run)) or _all_bold(run, lines)):
            kept += [([k], False) for k in members]  # only links or only bold: as printed
        else:
            kept.append((members, code))
    new_of = {old: new for new, (members, _) in enumerate(kept) for old in members}
    out = [
        _joined([blocks[k] for k in members]) if code else blocks[members[0]]
        for members, code in kept
    ]
    out = [
        replace(block, describes=new_of[block.describes]) if block.describes is not None else block
        for block in out
    ]
    return out, tuple(_moved(section, new_of, len(out)) for section in sections)


def _typewritten(lines: Iterable[TextLine]) -> bool:
    """True if most letters of the document are in a typewriter font."""
    letters: Counter[bool] = Counter()
    for line in lines:
        for run in line.runs:
            letters[monospace(run.font)] += sum(c.isalpha() for c in run.text)
    return letters[True] > letters[False]


def _code_paragraph(block: Block, lines: dict[str, TextLine], size: float) -> bool:
    if block.kind is not BlockKind.PARAGRAPH or not block.parts:
        return False
    return all(
        part.item in lines and _monospace_line(lines[part.item], size) for part in block.parts
    )


def _monospace_line(line: TextLine, size: float) -> bool:
    shown = [run for run in line.runs if run.text.strip()]
    return bool(shown) and all(
        monospace(run.font) and not (size and run.size > _LARGER * size) for run in shown
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


def _links(text: str) -> bool:
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
