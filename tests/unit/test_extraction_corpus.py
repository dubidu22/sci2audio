"""PDF extraction on the corpus papers: the ground truth and golden files (Issue #23, D-60).

Extraction decides nothing, so the truth files (#16) are checked only for what must be
*recorded*: the page count, the title, every verbatim sentence and every piece of furniture on
its page. Order, headings and furniture removal are checked in the layout tests.

The golden files show each line's text and style, page by page. Accept a wanted change with
`uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import re
import tomllib
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Content, Page, TextLine
from sci2audio.extraction import extract_pdf

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAPERS = sorted((CORPUS / "papers").glob("*.pdf"))
IDS = [paper.stem for paper in PAPERS]


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
    assert describe(content(paper)) == snapshot


def describe(content: Content) -> str:
    """Each line with its box and the style of each run; pictures with boxes; drawings counted."""
    meta = content.metadata
    out = [f"{content.source.name}  sha256 {content.source.sha256[:16]}"]
    out.append(f"metadata: title={meta.title!r} authors={list(meta.authors)} date={meta.date!r}")
    for page in content.pages:
        out.append(
            f"== page {page.number}  {page.width:.0f} x {page.height:.0f}  "
            f"lines {len(page.lines)}  pictures {len(page.pictures)}  "
            f"drawings {len(page.drawings)}"
        )
        out.extend(f"{line.id}  {_box(line.box)}  {_runs(line)}" for line in page.lines)
        out.extend(f"{picture.id}  {_box(picture.box)}  picture" for picture in page.pictures)
    return "\n".join(out) + "\n"


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
