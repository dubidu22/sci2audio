"""Layout on the corpus documents without positions, against their ground truth (#75).

The EPUB, the Markdown note and the plain-text note are read from their tags (D-405). Their
headings, sections, notes, tables, figures and formulas are checked against the hand-made
truth files, and every block is kept in a golden file in the format of the papers' golden
(`test_layout_corpus.golden_text`): kind, label, the block a caption names, page, pictures
where they stand in its text and its text, then the section tree (D-417).
Accept a wanted change with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import tomllib
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion
from test_layout_corpus import flattened, golden_text, printed_numbers, word_for_word

from sci2audio.core import BlockKind, Document, Picture, TextLine
from sci2audio.extraction import extract_epub, extract_markdown, extract_text
from sci2audio.layout import build_document

pytestmark = pytest.mark.timeout(120)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
EPUB = CORPUS / "epub" / "wells-the-time-machine.epub"
MARKDOWN = CORPUS / "markdown" / "sci2audio-sample-note.md"
TEXT = CORPUS / "text" / "sci2audio-sample-plain.txt"
GERMAN_MARKDOWN = CORPUS / "markdown" / "sci2audio-beispiel-notiz.md"  # German samples (#219)
GERMAN_TEXT = CORPUS / "text" / "sci2audio-beispiel-text.txt"
SAMPLES = [EPUB, MARKDOWN, TEXT, GERMAN_MARKDOWN, GERMAN_TEXT]
READERS = {".epub": extract_epub, ".md": extract_markdown, ".txt": extract_text}
# The Standard Ebooks front and back matter around the story's chapters: headed sections of
# their own, read as ordinary chapters (D-409); the truth lists only the story's chapters.
FRONT = ["The Time Machine", "Imprint"]
BACK = ["Endnotes", "Colophon", "Uncopyright"]
BACK_LINK = {"role:doc-backlink", "epub:backlink"}
NOTE_REF = {"role:doc-noteref", "epub:noteref"}


@cache
def document(sample: Path) -> Document:
    return build_document(READERS[sample.suffix](sample))


def truth(sample: Path) -> dict:
    return tomllib.loads((CORPUS / "truth" / f"{sample.stem}.toml").read_text(encoding="utf-8"))


def of_kind(doc: Document, kind: BlockKind) -> list[int]:
    return [k for k, block in enumerate(doc.blocks) if block.kind is kind]


def note_refs(doc: Document) -> list[tuple[str, str, int]]:
    """Each noteref in reading order: its mark, the item it links to, the block it is in."""
    found = []
    for index, block in enumerate(doc.blocks):
        for part in block.parts:
            item = doc.content.items()[part.item][1]
            if not isinstance(item, TextLine):
                continue
            for run in item.runs:
                if NOTE_REF & set(run.tags):
                    links = [t[len("link:") :] for t in run.tags if t.startswith("link:")]
                    found += [(run.text, link, index) for link in links]
    return found


def block_of(doc: Document, item: str) -> int:
    return next(k for k, b in enumerate(doc.blocks) if any(p.item == item for p in b.parts))


def text_without_back_links(doc: Document, index: int) -> str:
    """A note's text as the truth writes it: no back-link arrow, no invisible U+FEFF."""
    pieces = []
    for part in doc.blocks[index].parts:
        item = doc.content.items()[part.item][1]
        if isinstance(item, TextLine):
            pieces += [run.text for run in item.runs if not BACK_LINK & set(run.tags)]
    return " ".join("".join(pieces).replace("﻿", "").split())


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.stem for s in SAMPLES])
def test_golden_file(sample: Path, snapshot: SnapshotAssertion) -> None:
    assert golden_text(sample.name, document(sample)) == snapshot


@pytest.mark.parametrize("sample", SAMPLES, ids=[s.stem for s in SAMPLES])
def test_each_section_starts_at_its_heading(sample: Path) -> None:
    doc = document(sample)
    assert [s.start for s in flattened(doc.sections)] == of_kind(doc, BlockKind.HEADING)


# ---- the EPUB -------------------------------------------------------------------------


def test_the_epub_chapters_are_level_1_sections_in_order() -> None:
    """The truth's 13 chapters, each a level-1 section, between the front and back matter;
    the title page's h1 does not hold the chapters (D-407)."""
    found = [(s.title, s.level) for s in flattened(document(EPUB).sections)]
    expected = [*FRONT, *truth(EPUB)["chapters"], *BACK]
    assert found == [(name, 1) for name in expected]


def test_the_epub_endnote_is_its_one_footnote_where_the_file_puts_it() -> None:
    doc = document(EPUB)
    (note,) = of_kind(doc, BlockKind.FOOTNOTE)
    (expected,) = truth(EPUB)["endnotes"]
    assert text_without_back_links(doc, note) == expected["text"]
    endnotes = next(s for s in doc.sections if s.title == "Endnotes")
    assert endnotes.start < note < endnotes.end  # not moved next to its mark (D-414)
    assert doc.blocks[note].label == ""  # the mark is not printed in the note (D-406)


def test_the_epub_noteref_links_into_its_endnote_from_its_chapter() -> None:
    doc = document(EPUB)
    ((mark, item, citing),) = note_refs(doc)
    (note,) = of_kind(doc, BlockKind.FOOTNOTE)
    assert mark == "1"
    assert block_of(doc, item) == note
    chapter = next(s for s in doc.sections if s.title == truth(EPUB)["endnotes"][0]["chapter"])
    assert chapter.start < citing < chapter.end


def test_the_epub_pictures_are_figures_in_place() -> None:
    doc = document(EPUB)
    figures = of_kind(doc, BlockKind.FIGURE)
    assert len(figures) == 3
    for k in figures:
        (part,) = doc.blocks[k].parts
        assert isinstance(doc.content.items()[part.item][1], Picture)
        assert doc.blocks[k].text == ""


# ---- the Markdown note ----------------------------------------------------------------


def test_the_markdown_sections_are_the_truth_headings() -> None:
    doc = document(MARKDOWN)
    expected = [(h["text"], h["level"]) for h in truth(MARKDOWN)["headings"]]
    assert [(s.title, s.level) for s in flattened(doc.sections)] == expected
    labels = [doc.blocks[k].label for k in of_kind(doc, BlockKind.HEADING)]
    assert labels == printed_numbers([text for text, _ in expected])


def test_the_markdown_notes_are_footnotes_their_marks_link_to() -> None:
    doc = document(MARKDOWN)
    notes = of_kind(doc, BlockKind.FOOTNOTE)
    expected = truth(MARKDOWN)["footnotes"]
    assert [text_without_back_links(doc, k) for k in notes] == [n["text"] for n in expected]
    marks = {(mark, block_of(doc, item)) for mark, item, _ in note_refs(doc)}
    assert marks == {(n["mark"], k) for n, k in zip(expected, notes, strict=True)}
    assert all(doc.blocks[k].label == "" for k in notes)  # marks not printed (D-406)


def test_the_markdown_table_is_one_table_block() -> None:
    doc = document(MARKDOWN)
    tables = of_kind(doc, BlockKind.TABLE)
    assert len(tables) == truth(MARKDOWN)["tables"]
    assert doc.blocks[tables[0]].text.split("\n") == [
        *("Group", "Listeners", "Minutes", "A", "12", "41", "B", "9", "38")
    ]


def test_the_markdown_figures_are_its_pictures_in_order() -> None:
    doc = document(MARKDOWN)
    alts = []
    for k in of_kind(doc, BlockKind.FIGURE):
        (part,) = doc.blocks[k].parts
        picture = doc.content.items()[part.item][1]
        assert isinstance(picture, Picture)
        alts.append(picture.alt)
    assert alts == truth(MARKDOWN)["figures"]


def test_display_maths_is_a_formula_and_inline_maths_stays_in_its_sentence() -> None:
    doc = document(MARKDOWN)
    formulas = [doc.blocks[k].text for k in of_kind(doc, BlockKind.FORMULA)]
    expected = truth(MARKDOWN)["formulas"]
    assert formulas == [f["text"] for f in expected if f["display"]]
    for formula in (f["text"] for f in expected if not f["display"]):
        holders = [b for b in doc.blocks if formula in b.text]
        assert [b.kind for b in holders] == [BlockKind.LIST_ITEM]


def test_the_markdown_lists_are_list_items_without_labels() -> None:
    doc = document(MARKDOWN)
    items = [doc.blocks[k] for k in of_kind(doc, BlockKind.LIST_ITEM)]
    assert [b.text for b in items] == [
        "How fast can a listener follow a formula such as E = mc^2?",
        "Do footnotes2 help or hurt?",
        "when read in place",
        "when read at the end",
    ]
    assert {b.label for b in items} == {""}  # HTML numbering is not text (D-415)


def test_a_code_block_is_one_paragraph_keeping_its_lines() -> None:
    doc = document(MARKDOWN)
    code = "def words_per_minute(words, seconds):\n    return 60 * words / seconds"
    (block,) = [b for b in doc.blocks if b.text == code]
    assert block.kind is BlockKind.PARAGRAPH  # D-410


# ---- all three ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample",
    [MARKDOWN, TEXT, GERMAN_MARKDOWN, GERMAN_TEXT],
    ids=["markdown", "text", "german-markdown", "german-text"],
)
def test_verbatim_sentences_are_inside_one_block(sample: Path) -> None:
    blocks = [b.text for b in document(sample).blocks]
    cut = [
        item["text"]
        for item in truth(sample)["verbatim"]
        if not any(word_for_word(item["text"]).search(text) for text in blocks)
    ]
    assert cut == []


def test_plain_text_is_paragraphs_only() -> None:
    """A text file marks no structure (D-416): its truth has no headings."""
    doc = document(TEXT)
    assert truth(TEXT)["headings"] == []
    assert doc.sections == ()
    assert {b.kind for b in doc.blocks} == {BlockKind.PARAGRAPH}
    assert len(doc.blocks) == 8  # its eight runs of non-blank lines


# ---- the German samples (#219) --------------------------------------------------------


def test_the_german_markdown_sections_and_notes_are_its_truth() -> None:
    doc = document(GERMAN_MARKDOWN)
    expected = truth(GERMAN_MARKDOWN)
    headings = [(h["text"], h["level"]) for h in expected["headings"]]
    assert [(s.title, s.level) for s in flattened(doc.sections)] == headings
    notes = of_kind(doc, BlockKind.FOOTNOTE)
    assert [text_without_back_links(doc, k) for k in notes] == [
        n["text"] for n in expected["footnotes"]
    ]
    assert len(of_kind(doc, BlockKind.TABLE)) == expected["tables"]
    assert len(of_kind(doc, BlockKind.FIGURE)) == len(expected["figures"])
    formulas = [doc.blocks[k].text for k in of_kind(doc, BlockKind.FORMULA)]
    assert formulas == [f["text"] for f in expected["formulas"] if f["display"]]


def test_the_german_samples_are_read_as_german() -> None:
    """The Markdown note states "de"; the text file states nothing and is guessed (D-495)."""
    assert (document(GERMAN_MARKDOWN).language, document(GERMAN_MARKDOWN).language_source) == (
        "de",
        "file",
    )
    assert (document(GERMAN_TEXT).language, document(GERMAN_TEXT).language_source) == (
        "de",
        "text",
    )
