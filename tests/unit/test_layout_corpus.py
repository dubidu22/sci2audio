"""Layout on the corpus papers, checked against the hand-made ground truth (Issue #21, D-60).

Step 1 of #21 (D-67): furniture, columns and reading order; a verbatim sentence reads in
order. Step 2: paragraphs; a verbatim sentence comes out word for word inside one block,
across column and page breaks, footnotes and floats, and each heading is a block of its own.
Step 3: the headings are the truth headings, with their levels and printed numbers, and the
section tree follows them; the footnotes are the truth footnotes, with their marks; the
captions are the truth's table, figure and algorithm captions, with their labels; the
tables, figures and algorithms are placeholder blocks that their captions name; each display
formula is a FORMULA block with its printed number, if it has one (PR D2, D-93).

The golden files list every block with its kind, label, the block a caption names, page and
text (line breaks shown as \\n), then the section tree.
Accept a wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import re
import tomllib
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Block, BlockKind, Document, FurnitureRole, Section, TextLine
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.layout.build import columns_per_page

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
IDS = [paper.stem for paper in PAPERS]
MAX_GAPS = 2  # times a sentence may be interrupted: a float, a footnote, a page's top
MAX_SKIPPED_LINES = 10  # lines in one gap (2 at most in the corpus since #34)
# Sentences not yet inside one block, each with the Issue that brings it there.
NOT_YET_ONE_BLOCK: dict[tuple[str, int, str], int] = {
    # A space before a superscript or a full stop that the page does not print.
    (
        "acl2023-nowak-prefix-probabilities",
        3,
        "where the entry at the ith row and the jth column corresponds to",
    ): 36,
    (
        "arxiv2024-arsiwalla-qualia-meaning",
        3,
        "These are certainly useful to quantify computational processes or identify states of"
        " complexity, but that is still rather far from capturing the very phenomenal character"
        " of qualia1.",
    ): 36,
}
MIN_START = 8  # letters a sentence's start must have at a line's end to be found there
# Truth headings not yet found, each with the Issue that brings it there.
NOT_YET_HEADINGS = {
    # Bold at body size, like the numbered subsections and the table headers on its pages.
    ("acl2023-chi-plue", "ACL 2023 Responsible NLP Checklist"): 48,
    ("acl2023-hardt-ellipsis", "ACL 2023 Responsible NLP Checklist"): 48,
}
# Algorithms printed inside a figure, by page: the figure, and the algorithms it holds,
# whose FIGURE block is the figure's (D-89).
ALGORITHMS_IN_FIGURES = {
    ("acl2023-nowak-prefix-probabilities", 3): ("Figure 1", ("Algorithm 1", "Algorithm 2")),
}
# Truth figures printed with an equation number: the FORMULA with that number holds them (D-93).
NUMBERED_AS_FORMULAS = {("arxiv2024-arsiwalla-qualia-meaning", 16): "4"}
LINE_WIDTH = 10.0  # points: a drawing this thin is a line (`line_width` em at 10 point)
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
def test_each_outline_entry_naming_a_truth_heading_is_its_heading_block(paper: Path) -> None:
    """#24: an outline entry whose title is a truth heading (its printed number taken off)
    falls on that HEADING block on its page; the other entries (the liu paper's title and
    its two bookmarks for unprinted headings) add no heading, so the truth stays met."""
    doc = document(paper)
    names = {
        " ".join(PRINTED_NUMBER.sub("", heading["text"], count=1).split()): heading["text"]
        for heading in truth(paper)["headings"]
    }
    pages = {item: page.number for item, (page, _) in doc.content.items().items()}
    on_pages = {
        (pages[block.parts[0].item], block.text.replace("\n", " "))
        for block in doc.blocks
        if block.kind is BlockKind.HEADING
    }
    missed = [
        entry
        for entry in doc.content.outline
        if (name := " ".join(entry.title.split())) in names
        and (entry.page, names[name]) not in on_pages
    ]
    assert missed == []


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


def placeholders(doc: Document, kind: BlockKind) -> dict[int, int]:
    """How many blocks of the kind each page holds."""
    found: dict[int, int] = {}
    for block in doc.blocks:
        if block.kind is kind:
            found[page_of(doc, block)] = found.get(page_of(doc, block), 0) + 1
    return found


def truth_count(paper: Path, key: str) -> dict[int, int]:
    return {entry["page"]: len(entry["labels"]) for entry in truth(paper).get(key, [])}


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_tables_are_the_truth_tables(paper: Path) -> None:
    """Each truth table is one TABLE block on its page (step 3, PR D1)."""
    assert placeholders(document(paper), BlockKind.TABLE) == truth_count(paper, "tables")


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_figures_are_the_truth_figures_and_algorithms(paper: Path) -> None:
    """Each truth figure is one FIGURE block on its page, and so is each algorithm, unless
    it is printed inside a figure (nowak's Figure 1 holds Algorithms 1 and 2, D-89)."""
    expected = truth_count(paper, "figures")
    for page, count in truth_count(paper, "algorithms").items():
        _, inside = ALGORITHMS_IN_FIGURES.get((paper.stem, page), ("", ()))
        expected[page] = expected.get(page, 0) + count - len(inside)
    for stem, page in NUMBERED_AS_FORMULAS:
        if stem == paper.stem:
            expected[page] -= 1
    assert placeholders(document(paper), BlockKind.FIGURE) == {
        k: n for k, n in expected.items() if n
    }


def test_algorithms_inside_figures_share_the_figure_block() -> None:
    """The captions of an algorithm printed inside a figure name the figure's block."""
    for (stem, page), (figure, algorithms) in ALGORITHMS_IN_FIGURES.items():
        doc = document(CORPUS / "papers" / f"{stem}.pdf")
        named = {
            block.label: block.describes
            for block in doc.blocks
            if block.kind is BlockKind.CAPTION and page_of(doc, block) == page
        }
        assert named[figure] is not None
        assert [named[label] for label in algorithms] == [named[figure]] * len(algorithms)


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_each_truth_caption_names_a_block_of_its_kind(paper: Path) -> None:
    """Every caption label in the truth's tables, figures and algorithms names (`describes`)
    a TABLE (for a table) or FIGURE block on its page (step 3, PR D1, D-86)."""
    doc = document(paper)
    named = {}
    for block in doc.blocks:
        if block.kind is BlockKind.CAPTION and block.describes is not None:
            target = doc.blocks[block.describes]
            named[(page_of(doc, block), block.label)] = (page_of(doc, target), target.kind)
    wrong = []
    for key in ("tables", "figures", "algorithms"):
        for entry in truth(paper).get(key, []):
            kind = BlockKind.TABLE if key == "tables" else BlockKind.FIGURE
            for label in filter(None, entry["labels"]):
                if named.get((entry["page"], label)) != (entry["page"], kind):
                    wrong.append((entry["page"], label))
    assert wrong == []


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_no_figure_is_only_lines(paper: Path) -> None:
    """A rule, a frame or an arrow alone is not a figure (#51): each FIGURE block holds a
    picture, a drawing thicker than a line, or text."""
    doc = document(paper)
    items = doc.content.items()
    for block in doc.blocks:
        if block.kind is BlockKind.FIGURE:
            boxes = [items[part.item][1].box for part in block.parts]
            thick = [b for b in boxes if b and min(b.x1 - b.x0, b.y1 - b.y0) > LINE_WIDTH]
            pictures = [p for p in block.parts if p.item in pictures_of(doc)]
            assert block.text or thick or pictures, block.parts


def pictures_of(doc: Document) -> set[str]:
    return {picture.id for page in doc.content.pages for picture in page.pictures}


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_formula_numbers_are_the_truth_numbers(paper: Path) -> None:
    """Each numbered display formula is one FORMULA block labelled with its number as
    printed, in reading order, page by page (step 3, PR D2, D-93)."""
    expected = {
        e["page"]: e["numbers"] for e in truth(paper).get("formula_numbers", []) if e["numbers"]
    }
    doc = document(paper)
    found: dict[int, list[str]] = {}
    for block in doc.blocks:
        if block.kind is BlockKind.FORMULA and block.label:
            found.setdefault(page_of(doc, block), []).append(block.label)
    assert found == expected


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_unnumbered_formulas_are_the_truth_formulas(paper: Path) -> None:
    """Each display formula printed without a number is one FORMULA block without a label."""
    expected = {e["page"]: e["count"] for e in truth(paper).get("unnumbered_formulas", [])}
    doc = document(paper)
    found: dict[int, int] = {}
    for block in doc.blocks:
        if block.kind is BlockKind.FORMULA and not block.label:
            found[page_of(doc, block)] = found.get(page_of(doc, block), 0) + 1
    assert found == expected


def test_a_figure_numbered_as_a_formula_is_held_by_that_formula() -> None:
    """The truth figure printed with an equation number is in the FORMULA with that number."""
    for (stem, page), number in NUMBERED_AS_FORMULAS.items():
        doc = document(CORPUS / "papers" / f"{stem}.pdf")
        formula = next(
            block
            for block in doc.blocks
            if block.kind is BlockKind.FORMULA
            and block.label == number
            and page_of(doc, block) == page
        )
        assert [p for p in formula.parts if p.item in pictures_of(doc)]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_each_line_stands_in_its_block_as_found(paper: Path) -> None:
    """Every printed line's text stands at its part's place in its block's text, as found:
    no letter dropped or added when blocks are cut and kept (D-57)."""
    doc = document(paper)
    items = doc.content.items()
    wrong = []
    for block in doc.blocks:
        for part in block.parts:
            item = items[part.item][1]
            if isinstance(item, TextLine):
                found = block.text[part.start : part.start + len(item.text)]
                if found != item.text:
                    wrong.append((part.item, item.text, found))
    assert wrong == []


# Formulas whose every printed piece the review of PR #61 checked, by the items they hold:
# nowak's Eq. (14), two rows each with its limits; arsiwalla's Eq. (2), a diagram of six
# terms joined by eight arrows.
WHOLE_FORMULAS = {
    ("acl2023-nowak-prefix-probabilities", "14"): {f"p4-l{k}" for k in range(16, 26)},
    ("arxiv2024-arsiwalla-qualia-meaning", "2"): (
        {f"p13-l{k}" for k in range(14, 23)} | {f"p13-d{k}" for k in range(1, 9)}
    ),
}


@pytest.mark.parametrize(("paper", "label"), sorted(WHOLE_FORMULAS), ids=str)
def test_a_formula_holds_all_its_pieces(paper: str, label: str) -> None:
    doc = document(CORPUS / "papers" / f"{paper}.pdf")
    found = [b for b in doc.blocks if b.kind is BlockKind.FORMULA and b.label == label]
    assert len(found) == 1
    assert {part.item for part in found[0].parts} == WHOLE_FORMULAS[paper, label]


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
        kind += f" -> {block.describes}" if block.describes is not None else ""
        out.append(f"{index}  p{page_of(doc, block)}  {kind}  [{items}]  {text}")
    out.append("sections")
    for section in flattened(doc.sections):
        indent = "  " * section.level
        out.append(
            f"{indent}{section.level}  blocks {section.start}-{section.end}  {section.title}"
        )
    assert "\n".join(out) + "\n" == snapshot
