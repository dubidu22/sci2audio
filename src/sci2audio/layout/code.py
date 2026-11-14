"""Code listings in a PDF: one CODE placeholder block each (#280, D-542, D-543).

A program listing is set in a typewriter font, and layout reads its short lines as one
paragraph each (the seaborn paper's Python example was ten). Read aloud, code is noise
("g equals sns.relplot open bracket"), so it becomes a placeholder like a figure: a text
step reads a short notice instead, and the player shows the code.

- A line is **monospace** when every run with visible text is in a typewriter font, known
  by its name (`monospace`), and none is larger than the body text (a package name set as
  a title is not code).
- A run of PARAGRAPH blocks next to each other in reading order, each made only of
  monospace lines, is one CODE block: its parts in order, its text the blocks' texts
  joined by line breaks. Headings, captions, footnotes, list items and furniture are never
  taken, and a paragraph that mixes a monospace word into proportional text stays.
- A run whose lines, put together, are one URL, e-mail address or DOI stays a paragraph:
  it is a link set in a typewriter font (nowak's GitHub address under the authors), which
  the links step reads.

A listing broken by a page break is two CODE blocks (#283). Its indentation is not
rebuilt: a PDF line holds no leading white space, and layout adds no text (#282).
"""

from __future__ import annotations

import re

from sci2audio.core import Block, BlockKind, Content, Part, TextLine

# typewriter fonts by name: "LMMono10-Regular", "Courier", "Inconsolatazi4", "NimbusMonL",
# "SourceCodePro", and TeX's typewriter families ("CMTT10", "SFTT1000", "txtt")
_MONOSPACE = re.compile(
    r"mono(?!type)|courier|typewriter|consol|menlo|monaco|inconsolata|cousine|nimbusmon"
    r"|code|^(?:cm|sf|ec|tc|tx|lc|lm|pcr)tt",
    re.IGNORECASE,
)
_LINK = re.compile(
    r"(?:https?://|ftp://|www\.|doi:\s*|10\.\d{4,9}/)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    re.IGNORECASE,
)
_LARGER = 1.1  # a run more than this times the body size is larger than the body text


def monospace(font: str) -> bool:
    """True if the font, by its name, is a typewriter font."""
    return bool(_MONOSPACE.search(font))


def find_code(blocks: list[Block], content: Content, size: float) -> list[Block]:
    """The blocks with each run of paragraphs made only of monospace lines joined into one
    CODE block; `size` is the body text's font size (0 if unknown)."""
    lines = {item.id: item for _, item in content.items().values() if isinstance(item, TextLine)}
    out: list[Block] = []
    run: list[Block] = []

    def close() -> None:
        if run and not _link("".join(block.text for block in run)):
            out.append(_joined(run))
        else:
            out.extend(run)
        run.clear()

    for block in blocks:
        if _code_paragraph(block, lines, size):
            run.append(block)
        else:
            close()
            out.append(block)
    close()
    return out


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


def _link(text: str) -> bool:
    return bool(_LINK.fullmatch("".join(text.split())))


def _joined(run: list[Block]) -> Block:
    parts: list[Part] = []
    texts: list[str] = []
    start = 0
    for block in run:
        parts += [Part(part.item, start + part.start) for part in block.parts]
        texts.append(block.text)
        start += len(block.text) + 1
    return Block(BlockKind.CODE, "\n".join(texts), tuple(parts))
