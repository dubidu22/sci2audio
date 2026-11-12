"""Layout on the corpus papers, checked against the hand-made ground truth (Issue #21, D-60).

Step 1 of #21 (D-67): furniture, columns and reading order; a verbatim sentence reads in
order. Step 2: paragraphs; a verbatim sentence comes out word for word inside one block,
across column and page breaks, footnotes and floats, and each heading is a block of its own.

The golden files list every block with its kind, page and text (line breaks shown as \\n).
Accept a wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import re
import tomllib
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Block, BlockKind, Document
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.layout.build import columns_per_page

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
IDS = [paper.stem for paper in PAPERS]
MAX_GAPS = 2  # times a sentence may be interrupted: a float, a footnote, a page's top
MAX_SKIPPED_LINES = 100  # lines in one gap (nowak p4 needs 81 until #34)
# Sentences not yet inside one block, each with the Issue that brings it there.
NOT_YET_ONE_BLOCK = {
    # Eq. (16) across both columns of page 5 is read as part of the columns.
    (
        "acl2023-nowak-prefix-probabilities",
        4,
        "Pre-computing \u03b3 and \u03b4 in lines 10\u201314 takes",
    ): 34,
}
MIN_START = 8  # letters a sentence's start must have at a line's end to be found there


@cache
def document(paper: Path) -> Document:
    return build_document(extract_pdf(paper))


def truth(paper: Path) -> dict:
    return tomllib.loads((CORPUS / "truth" / f"{paper.stem}.toml").read_text(encoding="utf-8"))


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text)


def letters(text: str) -> str:
    """Only letters and digits, lower case: hyphens and spaces at line ends don't matter."""
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def page_of(doc: Document, block: Block) -> int:
    items = doc.content.items()
    return items[block.parts[0].item][0].number


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_columns_per_page(paper: Path) -> None:
    assert columns_per_page(document(paper).content) == truth(paper)["columns"]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_furniture_is_only_in_furniture_blocks(paper: Path) -> None:
    doc = document(paper)
    on_page: dict[tuple[int, bool], list[str]] = {}
    for block in doc.blocks:
        if block.parts and block.text:
            key = (page_of(doc, block), block.kind is BlockKind.FURNITURE)
            on_page.setdefault(key, []).append(block.text)
    wrong = []
    for item in truth(paper)["furniture"]:
        text = squeezed(item["text"])
        for number in item["pages"]:
            furniture = [squeezed(t) for t in on_page.get((number, True), [])]
            read = [squeezed(t) for t in on_page.get((number, False), [])]
            if not _made_of(text, furniture):
                wrong.append(("not furniture", number, item["text"]))
            elif len(text) >= 4 and any(text in t for t in read):  # "12" may be read elsewhere
                wrong.append(("also read", number, item["text"]))
    assert wrong == []


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_furniture_blocks_hold_only_furniture(paper: Path) -> None:
    """The other direction: no body text is taken for furniture (and dropped from the script)."""
    doc = document(paper)
    known: dict[int, list[str]] = {}
    for item in truth(paper)["furniture"]:
        for number in item["pages"]:
            known.setdefault(number, []).append(letters(item["text"]))
    wrong = [
        (page_of(doc, block), block.text)
        for block in doc.blocks
        if block.kind is BlockKind.FURNITURE
        and letters(block.text)
        and not any(letters(block.text) in text for text in known.get(page_of(doc, block), []))
    ]
    assert wrong == []


def _made_of(text: str, pieces: list[str]) -> bool:
    """True if the text is made up of whole pieces (a furniture text may span several lines)."""
    if any(text in piece for piece in pieces):
        return True
    for piece in sorted(pieces, key=len, reverse=True):
        if piece and piece in text:
            text = text.replace(piece, "", 1)
    return not text


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_verbatim_sentences_read_in_order(paper: Path) -> None:
    doc = document(paper)
    lines = [
        (number, letters(text))
        for b in doc.blocks
        if b.kind is not BlockKind.FURNITURE and b.text
        for number, text in printed_lines(doc, b)
    ]
    missing = [
        (item["page"], item["text"])
        for item in truth(paper)["verbatim"]
        if not _reads_in_order(letters(item["text"]), item["page"], lines)
    ]
    assert missing == []


def printed_lines(doc: Document, block: Block) -> list[tuple[int, str]]:
    """The block's lines (its text between line breaks), each with the page it stands on."""
    items = doc.content.items()
    found = []
    for k, part in enumerate(block.parts):
        if k == 0 or block.text[part.start - 1] == "\n":
            found.append((items[part.item][0].number, part.start))
    ends = [start - 1 for _, start in found[1:]] + [len(block.text)]
    return [
        (number, block.text[start:end]) for (number, start), end in zip(found, ends, strict=True)
    ]


def _reads_in_order(target: str, page: int, lines: list[tuple[int, str]]) -> bool:
    """The sentence starts at the end of (or inside) a line on its page and goes on line by
    line in reading order. It may be interrupted at most `MAX_GAPS` times (a float, a
    footnote or the next page's top), each time by at most `MAX_SKIPPED_LINES` lines; two
    columns read in turn, line by line, interrupt it far more often."""
    for start, (number, text) in enumerate(lines):
        if number != page or not text:
            continue
        if target in text:
            return True
        cut = next((k for k in range(len(target), 0, -1) if text.endswith(target[:k])), 0)
        if cut and _goes_on(target[cut:], lines[start + 1 :], strict=cut < MIN_START):
            return True
    return False


def _goes_on(rest: str, lines: list[tuple[int, str]], strict: bool) -> bool:
    """The rest of a sentence follows in these lines. `strict`: its start was too short to be
    sure of, so the very next line must go on with it."""
    skipped, gaps = 0, 0
    for _, text in lines:
        if not text:
            continue
        if text.startswith(rest):
            return True
        if rest.startswith(text):
            rest, skipped, strict = rest[len(text) :], 0, False
            if not rest:
                return True
            continue
        if strict:
            return False
        if skipped == 0:
            gaps += 1
        skipped += 1
        if gaps > MAX_GAPS or skipped > MAX_SKIPPED_LINES:
            return False
    return False


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_verbatim_sentences_are_inside_one_block(paper: Path) -> None:
    """Word for word in one paragraph (spaces may be line breaks, and a word may be split
    by a hyphen at a line's end): not cut by a column or page break, a footnote, a
    figure or a table, nor by a wide gap that split one of its lines (#27)."""
    blocks = [b.text for b in doc_blocks(paper)]
    cut = {
        (paper.stem, item["page"], item["text"])
        for item in truth(paper)["verbatim"]
        if not any(word_for_word(item["text"]).search(text) for text in blocks)
    }
    assert cut == {key for key in NOT_YET_ONE_BLOCK if key[0] == paper.stem}


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_each_heading_is_a_block_of_its_own(paper: Path) -> None:
    """No heading is joined with the text before or after it, nor split (step 3 of #21
    gives these blocks their kind)."""
    blocks = [b.text.strip() for b in doc_blocks(paper)]
    joined_or_split = [
        heading["text"]
        for heading in truth(paper)["headings"]
        if not any(word_for_word(heading["text"]).fullmatch(text) for text in blocks)
    ]
    assert joined_or_split == []


def word_for_word(sentence: str) -> re.Pattern[str]:
    """The sentence as a block may hold it: any white space where it has a space, and a
    line break after a hyphen, or after a letter that a hyphen and a line break may follow
    (the truth drops a hyphen that only splits a word)."""
    pattern = []
    for ch in sentence:
        if ch.isspace():
            pattern.append(r"\s+")
        elif ch == "-":
            pattern.append(r"-\n?")
        else:
            pattern.append(re.escape(ch) + (r"(?:-\n)?" if ch.isalpha() else ""))
    return re.compile("".join(pattern))


def doc_blocks(paper: Path) -> list[Block]:
    return [b for b in document(paper).blocks if b.kind is not BlockKind.FURNITURE]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_golden_file(paper: Path, snapshot: SnapshotAssertion) -> None:
    doc = document(paper)
    out = [f"{paper.name}  language {doc.language}  blocks {len(doc.blocks)}"]
    for index, block in enumerate(doc.blocks):
        first, last = block.parts[0].item, block.parts[-1].item
        items = first if first == last else f"{first}..{last} ({len(block.parts)})"
        text = block.text.replace("\n", "\\n")  # one block per line of the golden file
        out.append(f"{index}  p{page_of(doc, block)}  {block.kind.value}  [{items}]  {text}")
    assert "\n".join(out) + "\n" == snapshot
