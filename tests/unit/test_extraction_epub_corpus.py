"""EPUB extraction on the corpus EPUB: the ground truth and the golden file (#73, D-317).

Extraction decides nothing, so the truth file (#16) is checked only for what must be
*recorded*: every chapter title as an `h2` line on its page, the one endnote in a run tagged
as an endnote, and the link from its mark. Headings, sections and footnote blocks are the
layout stage's work (#75). The outline, metadata and cover are written out here as the file
stores them (section 1 of `plans/issue73-epub-plan.md`).

The golden file shows each page's items in stored order: every line in full with its runs'
tags and style, every picture with its path and alternative text. Accept a wanted change
with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import hashlib
import tomllib
import zipfile
from functools import cache
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Content, Metadata, OutlineEntry, Picture, TextLine
from sci2audio.extraction import extract_epub, extract_epub_cover

pytestmark = pytest.mark.timeout(60)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
SAMPLE = CORPUS / "epub" / "wells-the-time-machine.epub"
SPINE = [
    "Titlepage", "Imprint", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "Epilogue", "Endnotes", "Colophon", "Uncopyright",
]  # fmt: skip


@cache
def content() -> Content:
    return extract_epub(SAMPLE)


def truth() -> dict:
    path = CORPUS / "truth" / f"{SAMPLE.stem}.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_every_spine_document_is_a_page() -> None:
    assert len(content().pages) == 18


def test_metadata_as_the_package_states_it() -> None:
    assert content().metadata == Metadata(
        title=truth()["title"],
        authors=("H. G. Wells",),
        date="2014-05-25",  # the ebook's date, as the file gives it
        identifier="https://standardebooks.org/ebooks/h-g-wells/the-time-machine",
        language="en-GB",
    )


def test_the_outline_is_the_table_of_contents() -> None:
    outline = content().outline
    assert outline == tuple(OutlineEntry(title, 1, page) for page, title in enumerate(SPINE, 1))
    # entries 3 to 15 are the story's chapters, as the truth file lists them
    assert [entry.title for entry in outline[2:15]] == truth()["chapters"]


def test_every_chapter_title_is_an_h2_line_on_its_page() -> None:
    pages = content().pages
    for entry in content().outline[2:15]:
        first = pages[entry.page - 1].lines[0]  # type: ignore[index]
        assert first.text == entry.title
        assert all("h2" in run.tags and run.bold for run in first.runs)


def test_the_endnote_and_its_mark_are_recorded_with_their_link() -> None:
    (note,) = truth()["endnotes"]
    endnotes = content().pages[15]
    line = endnotes.lines[1]
    text = line.text.replace("﻿", "").removesuffix(" ↩︎")
    assert text == note["text"]
    assert all("epub:endnote" in run.tags and "#note-1" in run.tags for run in line.runs)
    chapter = content().pages[SPINE.index(note["chapter"])]
    marks = [run for item in chapter.lines for run in item.runs if "epub:noteref" in run.tags]
    assert [(run.text, run.tags[-1]) for run in marks] == [("1", f"link:{line.id}")]


def test_pictures_keep_their_paths_and_alternative_text() -> None:
    pictures = [picture for page in content().pages for picture in page.pictures]
    assert pictures == [
        Picture("p1-i1", ref="epub/images/titlepage.png"),
        Picture("p2-i1", alt="The Standard Ebooks logo.", ref="epub/images/logo.png"),
        Picture("p17-i1", alt="The Standard Ebooks logo.", ref="epub/images/logo.png"),
    ]


def test_the_cover_is_the_declared_jpeg() -> None:
    cover = extract_epub_cover(SAMPLE)
    assert cover is not None
    assert cover.media_type == "image/jpeg"
    with zipfile.ZipFile(SAMPLE) as archive:
        stored = archive.read("epub/images/cover.jpg")
    assert hashlib.sha256(cover.data).digest() == hashlib.sha256(stored).digest()


def test_golden_file(snapshot: SnapshotAssertion) -> None:
    assert describe(content()) == snapshot


def describe(content: Content) -> str:
    """Source, metadata and outline, then each page's items in stored order."""
    meta = content.metadata
    out = [f"{content.source.name}  sha256 {content.source.sha256[:16]}"]
    out.append(
        f"metadata: title={meta.title!r} authors={list(meta.authors)} date={meta.date!r}"
        f" identifier={meta.identifier!r} language={meta.language!r}"
    )
    out.append("outline:")
    out.extend(
        f"  {entry.level} p{entry.page} {entry.item or '-'} {entry.title!r}"
        for entry in content.outline
    )
    for page in content.pages:
        out.append(f"== page {page.number}  lines {len(page.lines)}  pictures {len(page.pictures)}")
        items = {item.id: item for item in (*page.lines, *page.pictures)}
        for item_id in page.order:
            item = items[item_id]
            if isinstance(item, TextLine):
                out.append(f"{item.id}  {_runs(item)}")
            else:
                out.append(f"{item.id}  picture ref={item.ref!r} alt={item.alt!r}")
    return "\n".join(out) + "\n"


def _runs(line: TextLine) -> str:
    parts = []
    for run in line.runs:
        style = " ".join(run.tags) + ("; b" if run.bold else "") + ("; i" if run.italic else "")
        parts.append(f"{{{style}}}{run.text}")
    return "".join(parts)
