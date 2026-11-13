"""PDF extraction on the corpus papers: the ground truth and golden files (Issue #23, D-60).

Extraction decides nothing, so the truth files (#16) are checked only for what must be
*recorded*: the page count, the title, every verbatim sentence and every piece of furniture on
its page. Order, headings and furniture removal are checked in the layout tests.

The outline (PDF bookmarks, #24) is checked entry by entry as stored, and against the truth
headings: every entry names a truth heading once its printed number is taken off, except the
entries listed in `NOT_TRUTH_HEADINGS` with their reason (D-269).

The golden files show the outline, then each line's text and style, page by page. Accept a
wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.

A font the PDF doesn't embed (the arXiv stamp's Times-Roman) is drawn with a substitute font
that differs between Linux, macOS and Windows, and so do the boxes of its text; the golden files
leave those boxes out, so they match on every system. The text and style are still checked.
"""

import ctypes
import re
import tomllib
from functools import cache
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw
import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Content, OutlineEntry, Page, TextLine
from sci2audio.extraction import extract_pdf

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
IDS = [paper.stem for paper in PAPERS]


# Each corpus paper's bookmarks as stored (titles with their spaces, level, page), matched
# against the truth headings by the test below. The ACL papers have none.
OUTLINES: dict[str, tuple[OutlineEntry, ...]] = {
    "acl2023-chi-plue": (),
    "acl2023-hardt-ellipsis": (),
    "acl2023-nowak-prefix-probabilities": (),
    "arxiv2024-arsiwalla-qualia-meaning": (
        OutlineEntry("Introduction", 1, 2),
        OutlineEntry("Subjective Meaning in Phenomenology of Experience", 1, 4),
        OutlineEntry("Do Raw Feels Have Subjective Meaning? ", 1, 9),
        OutlineEntry("The Formal Structure of Meaning", 1, 11),
        OutlineEntry("Discussion ", 1, 18),
    ),
    "arxiv2024-liu-orbital-hall": (
        OutlineEntry(
            "Dominance of extrinsic scattering mechanisms in the orbital Hall effect: graphene,"
            " transition metal dichalcogenides and topological antiferromagnets",
            1,
            1,
        ),
        OutlineEntry("Abstract", 2, 1),
        OutlineEntry("References", 2, 4),
    ),
    "joss2021-waskom-seaborn": (
        OutlineEntry("Summary", 1, 1),
        OutlineEntry("Statement of need", 1, 1),
        OutlineEntry("Example", 1, 1),
        OutlineEntry("Overview", 1, 2),
        OutlineEntry("Acknowledgements", 1, 4),
        OutlineEntry("References", 1, 4),
    ),
    "joss2022-biggs-pymedphys": (
        OutlineEntry("Summary", 1, 1),
        OutlineEntry("Statement of need", 1, 1),
        OutlineEntry("Acknowledgements", 1, 2),
        OutlineEntry("References", 1, 2),
    ),
}
# Outline entries that are not truth headings, with the reason (D-269). The liu paper is set in
# PRL style: its truth has no headings at all.
NOT_TRUTH_HEADINGS = {
    # the paper's title, as the single top entry over the rest (a "title root")
    ("arxiv2024-liu-orbital-hall", 1): "title",
    # bookmarks for headings the page does not print
    ("arxiv2024-liu-orbital-hall", 2): "not printed",
    ("arxiv2024-liu-orbital-hall", 3): "not printed",
}
PRINTED_NUMBER = re.compile(r"^(?:\d+|[A-Z])(?:\.\d+)* ")  # "2.1 ", "A ": at the start only


@cache
def content(paper: Path) -> Content:
    return extract_pdf(paper)


def truth(paper: Path) -> dict:
    return tomllib.loads((CORPUS / "truth" / f"{paper.stem}.toml").read_text(encoding="utf-8"))


def squeezed(text: str) -> str:
    """The text without any white space, so spacing differences don't matter."""
    return re.sub(r"\s+", "", text)


def letters(text: str) -> str:
    """Only letters and digits, lower case: hyphens and spaces at line ends don't matter."""
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def page_text(page: Page) -> str:
    return " ".join(line.text for line in page.lines)


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_every_page_is_recorded(paper: Path) -> None:
    assert len(content(paper).pages) == truth(paper)["pages"]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_title_is_on_page_one(paper: Path) -> None:
    title = truth(paper)["title"]
    assert squeezed(title) in squeezed(page_text(content(paper).pages[0]))


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_furniture_is_recorded_on_its_pages(paper: Path) -> None:
    # Recorded, not yet marked: layout makes these furniture blocks.
    pages = content(paper).pages
    missing = [
        (item["text"], number)
        for item in truth(paper)["furniture"]
        for number in item["pages"]
        if squeezed(item["text"]) not in squeezed(page_text(pages[number - 1]))
    ]
    assert missing == []


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_every_word_of_the_verbatim_sentences_is_recorded(paper: Path) -> None:
    pages = content(paper).pages
    missing = []
    for item in truth(paper)["verbatim"]:
        start = item["page"] - 1
        lines = [line for page in pages[start : start + 2] for line in page.lines]
        stream = letters(" ".join(line.text for line in lines))
        for word in filter(None, map(letters, item["text"].split())):
            if word not in stream and not _split_across_lines(word, lines):
                missing.append((item["page"], word))
    assert missing == []


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_the_outline_is_recorded_as_stored(paper: Path) -> None:
    assert content(paper).outline == OUTLINES[paper.stem]


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_each_outline_entry_names_a_truth_heading(paper: Path) -> None:
    """Allowing for the printed number the outline leaves out, and white space; the entries
    that are not headings are named with their reason."""
    headings = [
        " ".join(PRINTED_NUMBER.sub("", heading["text"], count=1).split())
        for heading in truth(paper)["headings"]
    ]
    unmatched = [
        (k, entry.title)
        for k, entry in enumerate(content(paper).outline, 1)
        if " ".join(entry.title.split()) not in headings
    ]
    assert unmatched == [
        (k, entry.title)
        for k, entry in enumerate(content(paper).outline, 1)
        if (paper.stem, k) in NOT_TRUTH_HEADINGS
    ]


def test_a_printed_number_is_taken_off_the_front_only() -> None:
    """Review of #133: nothing in the middle of a heading looks like a number to strip."""
    assert PRINTED_NUMBER.sub("", "2.1 Setup", count=1) == "Setup"
    assert PRINTED_NUMBER.sub("", "A Proofs", count=1) == "Proofs"
    checklist = "ACL 2023 Responsible NLP Checklist"
    assert PRINTED_NUMBER.sub("", checklist, count=1) == checklist


def test_outlines_named_here_are_the_corpus_papers() -> None:
    assert sorted(OUTLINES) == IDS
    assert all(stem in IDS for stem, _ in NOT_TRUTH_HEADINGS)


def _split_across_lines(word: str, lines: list[TextLine]) -> bool:
    """A word hyphenated at the end of one line or page and finished on another."""
    ends = [letters(line.text) for line in lines]
    return any(
        any(end.endswith(word[:cut]) for end in ends)
        and any(end.startswith(word[cut:]) for end in ends)
        for cut in range(1, len(word))
    )


@pytest.mark.parametrize("paper", PAPERS, ids=IDS)
def test_golden_file(paper: Path, snapshot: SnapshotAssertion) -> None:
    assert describe(content(paper), not_embedded(paper)) == snapshot


def not_embedded(paper: Path) -> frozenset[str]:
    """Names of the fonts the PDF uses without embedding them."""
    names: set[str] = set()

    def walk(handles: list) -> None:
        for handle in handles:
            kind = raw.FPDFPageObj_GetType(handle)
            if kind == raw.FPDF_PAGEOBJ_TEXT:
                font = raw.FPDFTextObj_GetFont(handle)
                if not raw.FPDFFont_GetIsEmbedded(font):
                    size = raw.FPDFFont_GetBaseFontName(font, None, 0)
                    buffer = ctypes.create_string_buffer(size)
                    raw.FPDFFont_GetBaseFontName(font, buffer, size)
                    names.add(re.sub(r"^[A-Z]{6}\+", "", buffer.value.decode()))
            elif kind == raw.FPDF_PAGEOBJ_FORM:
                count = raw.FPDFFormObj_CountObjects(handle)
                walk([raw.FPDFFormObj_GetObject(handle, i) for i in range(count)])

    document = pdfium.PdfDocument(paper)
    for page in document:
        walk(
            [
                raw.FPDFPage_GetObject(page.raw, i)
                for i in range(raw.FPDFPage_CountObjects(page.raw))
            ]
        )
        page.close()
    document.close()
    return frozenset(names)


def describe(content: Content, not_embedded: frozenset[str] = frozenset()) -> str:
    """The outline entries; each line with its box and the style of each run; pictures with
    boxes; drawings counted."""
    meta = content.metadata
    out = [f"{content.source.name}  sha256 {content.source.sha256[:16]}"]
    out.append(f"metadata: title={meta.title!r} authors={list(meta.authors)} date={meta.date!r}")
    out.extend(
        f"outline: level {entry.level}  page {entry.page}  {entry.title!r}"
        for entry in content.outline
    )
    for page in content.pages:
        out.append(
            f"== page {page.number}  {page.width:.0f} x {page.height:.0f}  "
            f"lines {len(page.lines)}  pictures {len(page.pictures)}  "
            f"drawings {len(page.drawings)}"
        )
        out.extend(
            f"{line.id}  "
            f"{'[box varies: font not embedded]' if _uses(line, not_embedded) else _box(line.box)}"
            f"  {_runs(line)}"
            for line in page.lines
        )
        out.extend(f"{picture.id}  {_box(picture.box)}  picture" for picture in page.pictures)
    return "\n".join(out) + "\n"


def _uses(line: TextLine, fonts: frozenset[str]) -> bool:
    return any(run.font in fonts for run in line.runs)


def _box(box: object) -> str:
    if box is None:
        return "[no box]"
    return "[" + " ".join(f"{getattr(box, name):.0f}" for name in ("x0", "y0", "x1", "y1")) + "]"


def _runs(line: TextLine) -> str:
    parts = []
    for run in line.runs:
        style = (
            f"{run.font} {run.size:g}" + (" b" if run.bold else "") + (" i" if run.italic else "")
        )
        parts.append(f"{{{style}}}{run.text}")
    return "".join(parts)
