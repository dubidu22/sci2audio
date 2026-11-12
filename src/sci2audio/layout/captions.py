"""Captions: the text that names a table, figure or algorithm (Issue #21 step 3, D-85).

A caption is a text block that opens with "Figure", "Fig.", "Table" or "Algorithm" and a
number ("3", "A.2", "S1"), and then either a colon or a full stop ("Table 2: …",
"Figure 1. …"), or the label set in bold and the rest of its line not ("Algorithm 1 CKY").
Running text that opens the same way ("Figure 1 gives the accuracy …") is neither and
stays a paragraph. The caption's label is "Table 2", "Figure 1" or "Algorithm 3", as
printed. An algorithm's caption ends where its numbered lines ("1: …") start; those stay
a paragraph for now (the pseudocode is #38). A table's or figure's caption is never cut.
Which block a caption names (`describes`) is set with the placeholders in PR D (D-86).
"""

from __future__ import annotations

import re
from dataclasses import replace

from sci2audio.core import Block, BlockKind, Content, Part, TextLine
from sci2audio.layout.split import line_starts, split_at

_NAMES = "Figure|Fig\\.|Table|Algorithm|FIGURE|FIG\\.|TABLE|ALGORITHM"
# the label, then what follows it: a colon or full stop before white, or anything else
_LABEL = re.compile(rf"(?P<label>(?:{_NAMES})\s(?:[A-Z]\.?)?\d{{1,3}}(?:\.\d{{1,2}})*)(?P<rest>.*)")
_PUNCT = re.compile(r"[:.](?:\s|$)")
# a numbered line of pseudocode: "1:", "12:"
_CODE_LINE = re.compile(r"\d{1,3}:(?:\s|$)")
_ALGORITHM = ("Algorithm", "ALGORITHM")


def find_captions(blocks: list[Block], content: Content) -> list[Block]:
    """The blocks with each caption marked (kind CAPTION, its label), an algorithm's
    numbered lines cut off into a paragraph of their own."""
    lines = {line.id: line for page in content.pages for line in page.lines}
    out: list[Block] = []
    for block in blocks:
        label = _label(block, lines) if block.kind is BlockKind.PARAGRAPH else None
        if label is None:
            out.append(block)
            continue
        starts = line_starts(block)[1:] if label.startswith(_ALGORITHM) else []
        cuts = [k for k in starts if _CODE_LINE.match(block.text, k)]
        caption, *code = split_at(block, cuts[:1])
        out += [replace(caption, kind=BlockKind.CAPTION, label=label), *code]
    return out


def _label(block: Block, lines: dict[str, TextLine]) -> str | None:
    """The caption label the block opens with, or None if it is not a caption."""
    found = _LABEL.match(block.text)
    if found is None:
        return None
    label, rest = found["label"], found["rest"]
    if _PUNCT.match(rest) or (rest[:1].isspace() and _bold_label(block, lines, label)):
        return label
    return None


def opens_caption(line: TextLine) -> bool:
    """True if the line opens as a caption does ("Table 2: …", "Algorithm 3 CKY" with the
    label in bold): a paragraph never runs on into it."""
    block = Block(BlockKind.PARAGRAPH, line.text, (Part(line.id),))
    return _label(block, {line.id: line}) is not None


def _bold_label(block: Block, lines: dict[str, TextLine], label: str) -> bool:
    """True if the first line sets the label in bold and some of the rest of it not."""
    first = lines.get(block.parts[0].item) if block.parts else None
    if first is None:
        return False
    done, bold, plain = 0, True, False
    for run in first.runs:
        if done < len(label):
            bold = bold and (run.bold or not run.text.strip())
        elif run.text.strip():
            plain = plain or not run.bold
        done += len(run.text)
    return bold and plain
