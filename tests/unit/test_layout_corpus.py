"""Layout on the corpus papers, checked against the hand-made ground truth (Issue #21, D-60).

Step 1 of #21 (D-67): furniture, columns and reading order; a verbatim sentence reads in
order. Step 2: paragraphs; a verbatim sentence comes out word for word inside one block,
across column and page breaks, footnotes and floats, and each heading is a block of its own.
Step 3: the headings are the truth headings, with their levels and printed numbers, and the
section tree follows them; the footnotes are the truth footnotes, with their marks; the
captions are the truth's table, figure and algorithm captions, with their labels.

The golden files list every block with its kind, label, page and text (line breaks shown as
\\n), then the section tree.
Accept a wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import re
import tomllib
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Block, BlockKind, Document, FurnitureRole, Section
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
# Truth headings not yet found, each with the Issue that brings it there.
NOT_YET_HEADINGS = {
    # Bold at body size, like the numbered subsections and the table headers on its pages.
    ("acl2023-chi-plue", "ACL 2023 Responsible NLP Checklist"): 48,
    ("acl2023-hardt-ellipsis", "ACL 2023 Responsible NLP Checklist"): 48,
}
PRINTED_NUMBER = re.compile(r"((?:\d+|[A-Z])(?:\.\d+)*) ")  # "2.1 Setup", "A Proofs"


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


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_furniture_blocks_have_the_truth_role(paper: Path) -> None:
    """#31: each truth furniture item has a piece in a block with its role, and a block
    that is a piece of an item has the item's role, unless it is a piece of another item
    of its own role on that page (a page number "2" in a contents line "1 Introduction 2").
    Every truth kind is a `FurnitureRole`, and every furniture block has a role."""
    doc = document(paper)
    blocks = [
        (page_of(doc, block), squeezed(block.text), block.role.value)
        for block in doc.blocks
        if block.role and block.text.strip()
    ]
    items = [
        (number, squeezed(item["text"]), FurnitureRole(item["kind"]).value)
        for item in truth(paper)["furniture"]
        for number in item["pages"]
    ]
    unnamed = [b.text for b in doc.blocks if b.kind is BlockKind.FURNITURE and b.role is None]
    wrong = []
    for number, text, kind in items:
        pieces = [(t, role) for page, t, role in blocks if page == number and _same_piece(t, text)]
        if kind not in {role for _, role in pieces}:
            wrong.append(("no block with its role", number, kind, text))
        for piece, role in pieces:
            other = any(p == number and k == role and piece in t for p, t, k in items)
            if role != kind and not other:
                wrong.append((f"a piece is {role}", number, kind, text))
    assert wrong == []
    assert unnamed == []  # every furniture block says what it is


def _same_piece(block: str, item: str) -> bool:
    """True if the block holds the item or a piece of it (an item may span lines); a short
    text such as a page number must match whole."""
    return (
        block == item or (len(block) >= 4 and block in item) or (len(item) >= 4 and item in block)
    )


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_pages_carry_their_printed_page_numbers(paper: Path) -> None:
    """#31: the page numbers the truth lists are the pages' labels; other pages have none."""
    doc = document(paper)
    printed = {
        number: item["text"]
        for item in truth(paper)["furniture"]
        if item["kind"] == "page-number"
        for number in item["pages"]
    }
    expected = [printed.get(page.number, "") for page in doc.content.pages]
    assert list(doc.page_labels) == expected


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


def flattened(sections: tuple[Section, ...]) -> list[Section]:
    """The sections in reading order, each before its children."""
    return [s for section in sections for s in (section, *flattened(section.children))]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_sections_are_the_truth_headings(paper: Path) -> None:
    """Every truth heading, with its level and nothing else, in reading order (step 3)."""
    expected = [
        (heading["text"], heading["level"])
        for heading in truth(paper)["headings"]
        if (paper.stem, heading["text"]) not in NOT_YET_HEADINGS
    ]
    found = [(section.title, section.level) for section in flattened(document(paper).sections)]
    assert found == expected


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_each_section_starts_at_its_heading_with_its_printed_number(paper: Path) -> None:
    doc = document(paper)
    sections = flattened(doc.sections)
    headings = [i for i, block in enumerate(doc.blocks) if block.kind is BlockKind.HEADING]
    assert [section.start for section in sections] == headings
    expected = [
        heading["text"]
        for heading in truth(paper)["headings"]
        if (paper.stem, heading["text"]) not in NOT_YET_HEADINGS
    ]
    labels = [doc.blocks[section.start].label for section in sections]
    assert labels == printed_numbers(expected)


def printed_numbers(texts: list[str]) -> list[str]:
    """The number each heading prints: digits always, a capital letter only where more
    than one heading is numbered by letters ("A", "A.1"), not a title's one-letter first
    word ("A Note on Ethics")."""
    found = [number[1] if (number := PRINTED_NUMBER.match(text)) else "" for text in texts]
    letters = {number for number in found if number[:1].isalpha()}
    return [n if not n[:1].isalpha() or len(letters) > 1 else "" for n in found]


def test_printed_numbers_follow_the_truth_text() -> None:
    assert printed_numbers(["Abstract", "1 Intro", "2.1 Set", "A Proofs", "A.1 Lemma"]) == [
        "",
        "1",
        "2.1",
        "A",
        "A.1",
    ]
    assert printed_numbers(["1 Intro", "A Note on Ethics"]) == ["1", ""]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_footnotes_are_the_truth_footnotes(paper: Path) -> None:
    """Every note below a footnote rule is a footnote block with its mark as printed, page
    by page in reading order, and nothing else is a footnote (step 3, PR C1)."""
    doc = document(paper)
    found: dict[int, list[str]] = {}
    for block in doc.blocks:
        if block.kind is BlockKind.FOOTNOTE:
            found.setdefault(page_of(doc, block), []).append(block.label)
    expected = {note["page"]: note["marks"] for note in truth(paper)["footnotes"]}
    assert found == expected


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_a_footnote_caption_or_list_item_opens_with_its_label(paper: Path) -> None:
    opening = {BlockKind.FOOTNOTE, BlockKind.CAPTION, BlockKind.LIST_ITEM}
    for block in document(paper).blocks:
        if block.kind in opening:
            assert block.text.lstrip().startswith(block.label)


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_captions_are_the_truth_captions(paper: Path) -> None:
    """Every caption label in the truth's tables, figures and algorithms is a caption block
    on its page, and nothing else is a caption (step 3, PR C2; "" is a figure without a
    caption)."""
    doc = document(paper)
    found: dict[int, list[str]] = {}
    for block in doc.blocks:
        if block.kind is BlockKind.CAPTION:
            found.setdefault(page_of(doc, block), []).append(block.label)
    expected: dict[int, list[str]] = {}
    for key in ("tables", "figures", "algorithms"):
        for entry in truth(paper).get(key, []):
            labels = [label for label in entry["labels"] if label]
            if labels:
                expected.setdefault(entry["page"], []).extend(labels)
    assert {page: sorted(labels) for page, labels in found.items()} == {
        page: sorted(labels) for page, labels in expected.items()
    }


def test_headings_not_yet_found_are_still_in_the_truth() -> None:
    """A known gap names a real truth heading, so the list can't hide a typo."""
    for stem, text in NOT_YET_HEADINGS:
        paper = CORPUS / "papers" / f"{stem}.pdf"
        assert text in [heading["text"] for heading in truth(paper)["headings"]]
        assert text not in [section.title for section in flattened(document(paper).sections)]


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
    out.append("page labels  " + " ".join(label or "-" for label in doc.page_labels))
    for index, block in enumerate(doc.blocks):
        first, last = block.parts[0].item, block.parts[-1].item
        items = first if first == last else f"{first}..{last} ({len(block.parts)})"
        text = block.text.replace("\n", "\\n")  # one block per line of the golden file
        kind = f"{block.kind.value}/{block.role.value}" if block.role else block.kind.value
        kind += f" ({block.label})" if block.label else ""
        out.append(f"{index}  p{page_of(doc, block)}  {kind}  [{items}]  {text}")
    out.append("sections")
    for section in flattened(doc.sections):
        indent = "  " * section.level
        out.append(
            f"{indent}{section.level}  blocks {section.start}-{section.end}  {section.title}"
        )
    assert "\n".join(out) + "\n" == snapshot
