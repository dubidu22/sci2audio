"""Inline code in a PDF: a typewriter word inside prose is tagged `code` (#879).

Markdown and EPUB mark inline code themselves (backticks, `<code>`), and the text steps
read a run tagged `code` as printed (#854): "x => x + 1" keeps its arrow and operators
while the prose around it is read. A PDF has no markup; its sign is the font. Layout tags
the runs, as it knows the typewriter fonts (`code.monospace`) and whether the whole
document is typed (`BodyText.typed`, the one judgement `build_document` makes for
`paragraphs` and `find_code`, #794).

- In a document that is not typed, a run with visible text set in a typewriter font gets
  the tag `code` when it stands in a read text block (not a placeholder, not furniture)
  that also holds a run with letters in a proportional font. A listing is a CODE block of
  its own and is not tagged; a block set wholly in a typewriter font (a link on its own
  line) holds no prose and is not tagged either.
- A link is not code: LaTeX sets `\\url` and e-mail addresses in a typewriter font, and the
  links step reads them or leaves them out with its reason. A stretch of typewriter runs
  side by side, across a line break or across runs of only braces, commas, semicolons and
  white space (nowak's "{franz.nowak, ryan.cotterell}@inf.ethz.ch") is not tagged when its
  text, put together, holds a link or an "@" (arsiwalla's DOIs broken over two lines).
- Only the tags change: the content keeps its ids, texts and boxes, and the blocks do not
  change. A run already tagged `code` is not tagged again, so building twice is the same.
"""

from __future__ import annotations

import re
from dataclasses import replace

from sci2audio.core import Block, BlockKind, Content, TextLine, TextRun
from sci2audio.layout.code import BodyText, monospace

CODE_TAG = "code"  # the source tag the text steps read as inline code (#854)
# a link's mark, as `code._LINK` finds links: a scheme, "www.", a DOI or an e-mail's "@"
_LINK = re.compile(r"@|(?:https?|ftp)://|\bwww\.|\bdoi:|\b10\.\d{4,9}/", re.IGNORECASE)
_JOINING = re.compile(r"[\s{},;]*")  # runs that keep a stretch of typewriter runs going

_Place = tuple[str, int]  # a run: its line's id and its number in the line


def tag_inline_code(blocks: list[Block], content: Content, body: BodyText) -> Content:
    """The content with each typewriter run inside read prose tagged `code`; `body` is the
    document's judgement of code, nothing is tagged where it is typed."""
    if body.typed:
        return content
    lines = {line.id: line for page in content.pages for line in page.lines}
    marked: set[_Place] = set()
    for block in blocks:
        if block.is_placeholder or block.kind is BlockKind.FURNITURE:
            continue
        runs = [
            ((part.item, k), run)
            for part in block.parts
            if part.item in lines
            for k, run in enumerate(lines[part.item].runs)
        ]
        if any(_prose(run) for _, run in runs):
            marked |= _inline_code(runs)
    if not marked:
        return content
    return replace(
        content,
        pages=tuple(
            replace(page, lines=tuple(_tagged(line, marked) for line in page.lines))
            for page in content.pages
        ),
    )


def _prose(run: TextRun) -> bool:
    return not monospace(run.font) and any(c.isalpha() for c in run.text)


def _typewriter(run: TextRun) -> bool:
    return monospace(run.font) and bool(run.text.strip())


def _inline_code(runs: list[tuple[_Place, TextRun]]) -> set[_Place]:
    """The places of the typewriter runs of one block's runs (in reading order) whose
    stretch holds no link."""
    found: set[_Place] = set()
    stretch: list[_Place] = []
    text: list[str] = []
    for place, run in [*runs, (("", -1), TextRun("."))]:  # a full stop ends the last one
        if _typewriter(run):
            stretch.append(place)
            text.append(run.text)
        elif stretch and _JOINING.fullmatch(run.text):
            text.append(run.text)
        else:
            if stretch and not _LINK.search("".join(text)):
                found.update(stretch)
            stretch, text = [], []
    return found


def _tagged(line: TextLine, marked: set[_Place]) -> TextLine:
    if not any((line.id, k) in marked for k in range(len(line.runs))):
        return line
    return replace(
        line,
        runs=tuple(
            replace(run, tags=(*run.tags, CODE_TAG))
            if (line.id, k) in marked and CODE_TAG not in run.tags
            else run
            for k, run in enumerate(line.runs)
        ),
    )
