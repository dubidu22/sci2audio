# ruff: noqa: RUF001  (the sentences are as papers print them)
"""Writing captures as Markdown (Obsidian), RIS (Zotero) and CSV (#399, ADR-008 2.1 item 7,
2.2 A and C): each format pinned as exact text, quotes and notes verbatim (D-57), a CSV
cell that cannot run as a formula, RIS line breaks that never read as a tag, the reference
holding only what the document states, never overwriting a file without being asked, no
network, and writes under faults (tests.md: file writing)."""

from __future__ import annotations

import csv
import errno
import io
import re
import shutil
import socket
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.app import capture_export as module
from sci2audio.app import files
from sci2audio.app.capture_export import (
    ENGLISH,
    ExportedCapture,
    ExportedDocument,
    ExportFormat,
    ExportLabels,
    PageFinder,
    Reference,
    csv_text,
    export_captures,
    file_stem,
    markdown_text,
    reference_of,
    ris_text,
)
from sci2audio.core import (
    Anchor,
    Block,
    BlockKind,
    Capture,
    CaptureType,
    Content,
    Document,
    Metadata,
    Page,
    Part,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.testing import NetworkUsedError, no_network

TIME = "2026-11-20T19:04:00Z"
QUOTE_SENTENCE = "Sleep loss lowered recall by 12 % (p < .01)."
NOTE_SENTENCE = "Runs on\nto page two."
MARK_SENTENCE = "=SUM(A1:A3) is not a formula here."
NOTE = 'Compare with "Ode 2021", p. 3'


def capture(number: int, kind: CaptureType, sentence: str, text: str = "") -> Capture:
    anchor = Anchor(number, 0, len(sentence), sentence)
    return Capture(f"{number:016x}", kind, TIME, TIME, anchor, text)


SLEEP = ExportedDocument(
    Reference("Sleep and memory", ("Ana Ruiz", "Ben Ode"), "2024", "10.1234/sleep.5"),
    (
        ExportedCapture(capture(1, CaptureType.QUOTE, QUOTE_SENTENCE), 4),
        ExportedCapture(capture(2, CaptureType.NOTE, NOTE_SENTENCE, NOTE), 5),
        ExportedCapture(capture(3, CaptureType.MARK, MARK_SENTENCE)),
    ),
)
BOOK = ExportedDocument(
    Reference("Ein Buch"),
    (ExportedCapture(capture(4, CaptureType.QUOTE, "Größe: α ≥ 0,5.")),),
)


# ---- the three formats, pinned ----------------------------------------------------------------


def test_the_csv_is_the_plain_table_of_adr_008() -> None:
    assert csv_text([SLEEP, BOOK]) == (
        "document,type,page,sentence,text\r\n"
        "Sleep and memory,quote,4,Sleep loss lowered recall by 12 % (p < .01).,\r\n"
        'Sleep and memory,note,5,"Runs on\nto page two.","Compare with ""Ode 2021"", p. 3"\r\n'
        "Sleep and memory,mark,,'=SUM(A1:A3) is not a formula here.,\r\n"
        'Ein Buch,quote,,"Größe: α ≥ 0,5.",\r\n'
    )


def test_the_ris_file_is_one_new_item_per_document_with_a_note_per_capture() -> None:
    assert ris_text([SLEEP, BOOK]) == (
        "TY  - GEN\r\n"
        "TI  - Sleep and memory\r\n"
        "AU  - Ana Ruiz\r\n"
        "AU  - Ben Ode\r\n"
        "PY  - 2024\r\n"
        "DO  - 10.1234/sleep.5\r\n"
        "N1  - Quote · p. 4\r\n"
        " Sleep loss lowered recall by 12 % (p < .01).\r\n"
        "N1  - Note · p. 5\r\n"
        " Runs on\r\n"
        " to page two.\r\n"
        " \r\n"
        ' Compare with "Ode 2021", p. 3\r\n'
        "N1  - Mark\r\n"
        " =SUM(A1:A3) is not a formula here.\r\n"
        "ER  - \r\n"
        "\r\n"
        "TY  - GEN\r\n"
        "TI  - Ein Buch\r\n"
        "N1  - Quote\r\n"
        " Größe: α ≥ 0,5.\r\n"
        "ER  - \r\n"
    )


def test_the_markdown_file_has_a_section_per_document_and_per_capture() -> None:
    assert markdown_text([SLEEP, BOOK]) == (
        "# Sleep and memory\n"
        "\n"
        "## Quote · p. 4\n"
        "\n"
        "> Sleep loss lowered recall by 12 % (p < .01).\n"
        "\n"
        "## Note · p. 5\n"
        "\n"
        "> Runs on\n"
        "> to page two.\n"
        "\n"
        'Compare with "Ode 2021", p. 3\n'
        "\n"
        "## Mark\n"
        "\n"
        "> =SUM(A1:A3) is not a formula here.\n"
        "\n"
        "# Ein Buch\n"
        "\n"
        "## Quote\n"
        "\n"
        "> Größe: α ≥ 0,5.\n"
    )


def test_the_words_of_the_labels_are_the_callers() -> None:
    german = ExportLabels(mark="Markierung", note="Notiz", quote="Zitat", page="S. {page}")
    assert "## Zitat · S. 4\n" in markdown_text([SLEEP], german)
    assert "N1  - Notiz · S. 5\r\n" in ris_text([SLEEP], german)
    assert ",quote,4," in csv_text([SLEEP])  # the CSV's type is data, never translated


def test_a_ris_file_with_no_document_is_empty_and_a_csv_has_its_header() -> None:
    assert ris_text([]) == ""
    assert markdown_text([]) == ""
    assert csv_text([]) == "document,type,page,sentence,text\r\n"


# ---- CSV: formulas ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cell", "written"),
    [
        ("=1+1", "'=1+1"),
        ("+49 30 1234", "'+49 30 1234"),
        ("-0.3 in the first trial", "'-0.3 in the first trial"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tTabbed", "'\tTabbed"),
        ("\rReturn", '"\'\rReturn"'),
        ('-"x", y', '"\'-""x"", y"'),
        ("a = b", "a = b"),
        ("'quoted'", "'quoted'"),
    ],
)
def test_a_cell_that_could_run_as_a_formula_gets_one_apostrophe_in_front(
    cell: str, written: str
) -> None:
    document = ExportedDocument(
        Reference(cell), (ExportedCapture(capture(1, CaptureType.NOTE, cell, cell)),)
    )
    row = csv_text([document]).split("\r\n", 1)[1]
    assert row == f"{written},note,,{written},{written}\r\n"


@given(st.text(min_size=1, max_size=40).filter(lambda t: "\x00" not in t))
def test_every_csv_cell_reads_back_verbatim_after_its_guard(text: str) -> None:
    document = ExportedDocument(
        Reference(text), (ExportedCapture(capture(1, CaptureType.NOTE, text, text), 7),)
    )
    rows = list(csv.reader(io.StringIO(csv_text([document]), newline="")))
    assert rows[0] == ["document", "type", "page", "sentence", "text"]
    cells = rows[1]
    assert cells[1:3] == ["note", "7"]
    for cell in (cells[0], cells[3], cells[4]):
        assert not cell.startswith(("=", "+", "-", "@", "\t", "\r"))
        guarded = text.startswith(("=", "+", "-", "@", "\t", "\r"))
        assert cell == ("'" + text if guarded else text)


# ---- RIS: line breaks ------------------------------------------------------------------------

TAG = re.compile(r"[A-Z][A-Z0-9] {1,2}-")  # as Zotero reads a tag line; stricter readers want two


def test_a_line_inside_a_note_that_looks_like_a_tag_does_not_start_a_line() -> None:
    note = "ER  - not the end\nTY  - GEN\r\nAU - Someone\rKW  - x"
    document = ExportedDocument(
        Reference("T"), (ExportedCapture(capture(1, CaptureType.NOTE, "S.", note)),)
    )
    assert ris_text([document]) == (
        "TY  - GEN\r\n"
        "TI  - T\r\n"
        "N1  - Note\r\n"
        " S.\r\n"
        " \r\n"
        " ER  - not the end\r\n"
        " TY  - GEN\r\n"
        " AU - Someone\r\n"
        " KW  - x\r\n"
        "ER  - \r\n"
    )


def test_a_title_or_author_with_a_line_break_is_continued_the_same_way() -> None:
    document = ExportedDocument(Reference("Part one\nPart two", ("A\nB",)))
    assert ris_text([document]) == (
        "TY  - GEN\r\nTI  - Part one\r\n Part two\r\nAU  - A\r\n B\r\nER  - \r\n"
    )


def _read_ris(text: str) -> list[tuple[str, str]]:
    """The tag lines of a RIS text with their values, continuation lines joined by "\\n"."""
    fields: list[tuple[str, str]] = []
    for line in text.split("\r\n"):
        if TAG.match(line):
            fields.append((line[:2], line[6:]))
        elif line.startswith(" "):
            tag, value = fields[-1]
            fields[-1] = (tag, value + "\n" + line[1:])
        else:
            assert line == ""
    return fields


BREAKS = re.compile(r"\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]")


@given(
    st.text(min_size=1, max_size=60),
    st.text(max_size=60).filter(lambda t: "\x00" not in t),
)
def test_no_line_of_any_note_or_sentence_reads_as_a_tag(sentence: str, note: str) -> None:
    kind = CaptureType.NOTE if note else CaptureType.QUOTE
    document = ExportedDocument(
        Reference(sentence), (ExportedCapture(capture(1, kind, sentence, note)),)
    )
    text = ris_text([document])
    fields = _read_ris(text)
    assert [tag for tag, _ in fields] == ["TY", "TI", "N1", "ER"]
    assert fields[1][1] == BREAKS.sub("\n", sentence)
    label = "Note" if note else "Quote"
    body = BREAKS.sub("\n", sentence) + ("\n\n" + BREAKS.sub("\n", note) if note else "")
    assert fields[2][1] == f"{label}\n{body}"


def test_the_type_is_gen_since_extraction_records_no_type() -> None:
    assert ris_text([SLEEP]).startswith("TY  - GEN\r\n")
    assert ris_text([SLEEP]).count("TY  - ") == 1


# ---- verbatim (D-57) -------------------------------------------------------------------------


@pytest.mark.parametrize("form", list(ExportFormat))
def test_sentences_and_notes_are_written_verbatim(tmp_path: Path, form: ExportFormat) -> None:
    sentence = "*p* < .05, [Fig. 2] & `x_1` — #tag {α} \\ ü"
    note = "My # note with <b>tags</b> and $x$"
    document = ExportedDocument(
        Reference("R"), (ExportedCapture(capture(1, CaptureType.NOTE, sentence, note), 2),)
    )
    path = export_captures(tmp_path, "out", form, [document])
    text = path.read_bytes().decode("utf-8-sig")
    assert sentence in text
    assert note in text


# ---- the reference: only what the document states --------------------------------------------


def content(kind: SourceFormat, metadata: Metadata, name: str = "paper", pages: int = 1) -> Content:
    suffix = {"pdf": "pdf", "epub": "epub", "markdown": "md", "text": "txt"}[kind.value]
    return Content(
        Source(f"{name}.{suffix}", kind), tuple(Page(n) for n in range(1, pages + 1)), metadata
    )


def test_the_reference_holds_authors_year_and_doi_as_extraction_found_them() -> None:
    metadata = Metadata("File title", ("Ana Ruiz",), "2024-03-01", "doi:10.1234/x.5")
    found = reference_of("Library title", content(SourceFormat.EPUB, metadata))
    assert found == Reference("Library title", ("Ana Ruiz",), "2024", "10.1234/x.5")


@pytest.mark.parametrize(
    ("identifier", "doi"),
    [
        ("10.1234/x.5", "10.1234/x.5"),
        ("https://doi.org/10.1234/x.5", "10.1234/x.5"),
        ("DOI: 10.1234/x.5", "10.1234/x.5"),
        ("978-3-16-148410-0", ""),
        ("arXiv:2101.00001", ""),
        ("urn:uuid:1234", ""),
        ("", ""),
    ],
)
def test_only_a_doi_is_written_as_the_doi(identifier: str, doi: str) -> None:
    found = reference_of("T", content(SourceFormat.MARKDOWN, Metadata(identifier=identifier)))
    assert found.doi == doi


def test_a_pdf_states_no_year_since_its_date_is_when_the_file_was_made() -> None:
    metadata = Metadata("T", ("Ana Ruiz",), "2015-06-01")
    assert reference_of("T", content(SourceFormat.PDF, metadata)).year == ""


@pytest.mark.parametrize(("date", "year"), [("2024", "2024"), ("1987-05", "1987"), ("May", "")])
def test_the_year_is_the_dates_first_four_digits(date: str, year: str) -> None:
    assert reference_of("T", content(SourceFormat.EPUB, Metadata(date=date))).year == year


def test_nothing_the_document_does_not_state_is_written() -> None:
    document = ExportedDocument(reference_of("Bare", content(SourceFormat.TEXT, Metadata())))
    assert ris_text([document]) == "TY  - GEN\r\nTI  - Bare\r\nER  - \r\n"


def test_a_reference_needs_a_title_and_no_empty_author() -> None:
    with pytest.raises(ValueError, match="title"):
        Reference("")
    with pytest.raises(ValueError, match="author"):
        Reference("T", ("",))
    with pytest.raises(ValueError, match="page"):
        ExportedCapture(capture(1, CaptureType.MARK, "S."), 0)


# ---- the page on which the sentence starts ----------------------------------------------------


def two_pages(kind: SourceFormat = SourceFormat.PDF) -> Document:
    lines = (
        TextLine("a", (TextRun("Intro"),)),
        TextLine("b", (TextRun("Runs on"),)),
        TextLine("c", (TextRun("to page two."),)),
    )
    pages = (Page(1, lines[:2]), Page(2, lines[2:]))
    if kind is not SourceFormat.PDF:
        pages = (Page(1, lines, order=("a", "b", "c")),)
    source = Source("two.pdf" if kind is SourceFormat.PDF else "two.epub", kind)
    blocks = (
        Block(BlockKind.PARAGRAPH, "Intro", (Part("a"),)),
        Block(BlockKind.PARAGRAPH, "Runs on\nto page two.", (Part("b"), Part("c", 8))),
    )
    return Document(Content(source, pages), "en", blocks)


def test_the_page_is_the_pdf_page_on_which_the_sentence_starts() -> None:
    pages = PageFinder(two_pages())
    assert pages.page(0, 0) == 1
    assert pages.page(1, 0) == 1  # the sentence runs on to page 2 but starts on page 1
    assert pages.page(1, 8) == 2
    assert pages.page(9, 0) is None  # not found in this document


def test_an_epub_markdown_or_text_has_no_page() -> None:
    assert PageFinder(two_pages(SourceFormat.EPUB)).page(1, 8) is None


# ---- the file: name, folder, never overwriting ------------------------------------------------


def test_each_format_is_written_to_the_given_folder_under_its_extension(tmp_path: Path) -> None:
    written = {form: export_captures(tmp_path, "Sleep", form, [SLEEP]) for form in ExportFormat}
    assert {path.name for path in written.values()} == {"Sleep.md", "Sleep.ris", "Sleep.csv"}
    assert written[ExportFormat.CSV].read_bytes() == b"\xef\xbb\xbf" + csv_text([SLEEP]).encode()
    assert written[ExportFormat.RIS].read_bytes() == ris_text([SLEEP]).encode()
    assert written[ExportFormat.MARKDOWN].read_bytes() == markdown_text([SLEEP]).encode()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Sleep.csv", "Sleep.md", "Sleep.ris"]


def test_the_labels_reach_the_file(tmp_path: Path) -> None:
    german = ExportLabels(mark="Markierung", note="Notiz", quote="Zitat", page="S. {page}")
    path = export_captures(tmp_path, "x", ExportFormat.MARKDOWN, [SLEEP], labels=german)
    assert "## Zitat · S. 4" in path.read_text(encoding="utf-8")
    assert ENGLISH.quote == "Quote"


def test_an_existing_file_is_never_overwritten_without_being_asked(tmp_path: Path) -> None:
    target = tmp_path / "Sleep.ris"
    target.write_bytes(b"the person's own file")
    with pytest.raises(FileExistsError) as refused:
        export_captures(tmp_path, "Sleep", ExportFormat.RIS, [SLEEP])
    assert refused.value.filename == str(target)
    assert target.read_bytes() == b"the person's own file"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Sleep.ris"]


def test_a_file_that_appears_during_the_write_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "Sleep.csv"
    real = files._write_partial

    def racing(partial: Path, content: str | bytes) -> None:
        real(partial, content)
        target.write_bytes(b"another program's file")

    monkeypatch.setattr(files, "_write_partial", racing)
    with pytest.raises(FileExistsError):
        export_captures(tmp_path, "Sleep", ExportFormat.CSV, [SLEEP])
    assert target.read_bytes() == b"another program's file"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Sleep.csv"]


def test_an_existing_file_is_replaced_when_the_person_said_so(tmp_path: Path) -> None:
    target = tmp_path / "Sleep.md"
    target.write_bytes(b"old")
    assert export_captures(tmp_path, "Sleep", ExportFormat.MARKDOWN, [SLEEP], overwrite=True)
    assert target.read_text(encoding="utf-8") == markdown_text([SLEEP])


def test_a_folder_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        export_captures(tmp_path / "gone", "x", ExportFormat.CSV, [SLEEP])
    (tmp_path / "file").write_bytes(b"")
    with pytest.raises(NotADirectoryError):
        export_captures(tmp_path / "file", "x", ExportFormat.CSV, [SLEEP])


@pytest.mark.parametrize("stem", ["", "a/b", "..", "a\\b", "CON", " x", "x.", "a\nb", "a:b"])
def test_a_name_that_is_not_a_safe_file_name_is_refused(tmp_path: Path, stem: str) -> None:
    with pytest.raises(ValueError, match="file name"):
        export_captures(tmp_path, stem, ExportFormat.CSV, [SLEEP])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("title", "stem"),
    [
        ("Sleep and memory", "Sleep and memory"),
        ('A/B: "C" <d>?*|\\', "A B C d"),
        ("Line\nbreak\ttab", "Line break tab"),
        ("..hidden.", "hidden"),
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("com1", "_com1"),
        ("Console", "Console"),
        ("", "captures"),
        ("???", "captures"),
        ("Größe α", "Größe α"),
    ],
)
def test_a_title_becomes_a_safe_file_name(title: str, stem: str) -> None:
    assert file_stem(title) == stem
    assert file_stem(stem) == stem


def test_a_long_title_is_cut_to_fit_any_file_system() -> None:
    stem = file_stem("ü" * 300)
    assert len(stem.encode("utf-8")) <= module.STEM_BYTES
    assert file_stem(stem) == stem


# ---- no network --------------------------------------------------------------------------------


def test_no_export_makes_a_network_call(tmp_path: Path) -> None:
    with no_network() as attempts:
        for form in ExportFormat:
            export_captures(tmp_path, "Sleep", form, [SLEEP, BOOK])
    assert attempts == []
    with no_network(), pytest.raises(NetworkUsedError):  # the guard itself works
        socket.getaddrinfo("example.org", 443)


# ---- faults (tests.md: file writing) ------------------------------------------------------------


def test_a_full_disk_leaves_no_file_and_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(partial: Path, content: str | bytes) -> None:
        assert isinstance(content, bytes)
        partial.write_bytes(content[: len(content) // 2])
        raise OSError(errno.ENOSPC, "No space left on device", str(partial))

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space"):
        export_captures(tmp_path, "Sleep", ExportFormat.RIS, [SLEEP])
    assert list(tmp_path.iterdir()) == []


def test_a_full_disk_keeps_the_old_file_when_replacing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "Sleep.csv"
    target.write_bytes(b"old")

    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device", str(partial))

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space"):
        export_captures(tmp_path, "Sleep", ExportFormat.CSV, [SLEEP], overwrite=True)
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Sleep.csv"]


def test_a_folder_removed_during_the_write_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "export"
    folder.mkdir()
    real = files._write_partial

    def removed(partial: Path, content: str | bytes) -> None:
        real(partial, content)
        shutil.rmtree(folder)

    monkeypatch.setattr(files, "_write_partial", removed)
    with pytest.raises(FileNotFoundError):
        export_captures(folder, "Sleep", ExportFormat.MARKDOWN, [SLEEP])
    assert list(tmp_path.iterdir()) == []


def test_a_crash_before_the_rename_leaves_the_old_file_and_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "Sleep.md"
    target.write_bytes(b"old")

    def killed(*args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(files, "_commit", killed)
    with pytest.raises(KeyboardInterrupt):
        export_captures(tmp_path, "Sleep", ExportFormat.MARKDOWN, [SLEEP], overwrite=True)
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Sleep.md"]
