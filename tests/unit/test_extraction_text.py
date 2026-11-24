"""Plain-text extraction and the decoding shared with Markdown (#74, the text part of #5).

A text file becomes one page; each printed line that is not blank is a text line, the first
of a paragraph tagged ``p`` and each following one ``p``, ``br`` (D-344), unless it starts a
list item or follows a title line (#466). The encoding is the
byte order mark's, else UTF-8, else Windows-1252 as WHATWG decodes it, marked as guessed
(D-345, D-346). Empty, binary and too large files fail with a clear message (D-347).
"""

from __future__ import annotations

import codecs
import textwrap
import tracemalloc
import unicodedata
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import Content, SourceFormat
from sci2audio.extraction import ExtractionError, extract_text, read_text
from sci2audio.extraction import text as text_module
from sci2audio.extraction.text import decode_text

pytestmark = pytest.mark.timeout(60)


def read(data: bytes) -> Content:
    return read_text(data, "notes.txt")


def lines(content: Content) -> list[tuple[str, tuple[str, ...]]]:
    return [(line.text, line.runs[0].tags) for line in content.pages[0].lines]


# ---- lines and paragraphs (D-344) --------------------------------------------------------


def test_each_printed_line_is_a_line_and_blank_lines_end_paragraphs() -> None:
    content = read(b"Title\n\nFirst line\nsecond line\n\n\nNext paragraph\n")
    assert lines(content) == [
        ("Title", ("p",)),
        ("First line", ("p",)),
        ("second line", ("p", "br")),
        ("Next paragraph", ("p",)),
    ]
    page = content.pages[0]
    assert [line.id for line in page.lines] == ["p1-l1", "p1-l2", "p1-l3", "p1-l4"]
    assert page.order == ("p1-l1", "p1-l2", "p1-l3", "p1-l4")
    assert (page.number, page.width, page.height, page.pictures) == (1, None, None, ())
    assert all(line.box is None for line in page.lines)


def test_one_page_no_style_no_outline_no_metadata() -> None:
    content = read(b"Only one line")
    assert len(content.pages) == 1
    (run,) = content.pages[0].lines[0].runs
    assert (run.font, run.size, run.bold, run.italic, run.box) == ("", 0.0, False, False, None)
    assert content.outline == ()
    assert content.metadata == type(content.metadata)()


@pytest.mark.parametrize("end", [b"\n", b"\r\n", b"\r"])
def test_every_kind_of_line_end_ends_a_line(end: bytes) -> None:
    data = end.join([b"one", b"two", b"", b"three"]) + end
    assert lines(read(data)) == [("one", ("p",)), ("two", ("p", "br")), ("three", ("p",))]


def test_a_line_of_spaces_tabs_or_form_feeds_is_blank() -> None:
    data = b"one\n \t \n two\n\x0c\nthree"
    assert lines(read(data)) == [("one", ("p",)), ("two", ("p",)), ("three", ("p",))]


def test_white_space_is_folded_as_a_browser_shows_it() -> None:
    """Runs of ASCII spaces, tabs and form feeds become one space, none at either end
    (D-306); a no-break space and other characters are kept as stored."""
    data = "\t  a   b\t\tc  \u00a0d\u2003e  ".encode()
    assert lines(read(data)) == [("a b c \u00a0d\u2003e", ("p",))]


def test_a_line_end_hyphen_is_kept_as_printed() -> None:
    assert [text for text, _ in lines(read(b"an exam-\nple"))] == ["an exam-", "ple"]


def test_the_source_names_the_file_its_hash_and_encoding() -> None:
    data = b"text"
    source = read(data).source
    assert (source.name, source.format) == ("notes.txt", SourceFormat.TEXT)
    assert source.sha256 == "982d9e3eb996f559e633f4d194def3761d909f5a3b647d1a851fead67c32c9d1"
    assert (source.encoding, source.encoding_guessed) == ("utf-8", False)


def test_a_file_is_read_from_its_path(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"Hello")
    assert lines(extract_text(path)) == [("Hello", ("p",))]


def test_a_missing_file_cannot_be_opened(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match=r"^gone\.txt: cannot be opened"):
        extract_text(tmp_path / "gone.txt")


# ---- encoding (D-345, D-346) ---------------------------------------------------------------

WORDS = "Caf\u00e9 \u2013 \u201cquoted\u201d \u00b5s, Z\u00fcrich \u00ff"


@pytest.mark.parametrize(
    ("data", "encoding"),
    [
        (WORDS.encode("utf-8"), "utf-8"),
        (codecs.BOM_UTF8 + WORDS.encode("utf-8"), "utf-8"),
        (codecs.BOM_UTF16_LE + WORDS.encode("utf-16-le"), "utf-16le"),
        (codecs.BOM_UTF16_BE + WORDS.encode("utf-16-be"), "utf-16be"),
        (codecs.BOM_UTF32_LE + WORDS.encode("utf-32-le"), "utf-32le"),
        (codecs.BOM_UTF32_BE + WORDS.encode("utf-32-be"), "utf-32be"),
    ],
)
def test_a_byte_order_mark_or_utf8_is_not_a_guess(data: bytes, encoding: str) -> None:
    decoded = decode_text(data, "notes.txt")
    assert (decoded.text, decoded.encoding, decoded.guessed) == (WORDS, encoding, False)


def test_not_utf8_is_read_as_windows_1252_and_marked_as_guessed() -> None:
    decoded = decode_text(WORDS.encode("cp1252"), "notes.txt")
    assert (decoded.text, decoded.encoding, decoded.guessed) == (WORDS, "windows-1252", True)
    source = read(WORDS.encode("cp1252")).source
    assert (source.encoding, source.encoding_guessed) == ("windows-1252", True)


def test_windows_1252_loses_no_byte() -> None:
    """The five bytes Windows-1252 leaves unassigned become the C1 controls of the same
    number, as WHATWG decodes them; every other byte is its Windows-1252 character."""
    data = bytes(range(1, 256))  # every byte but NUL; not UTF-8
    decoded = decode_text(data, "notes.txt")
    assert decoded.guessed
    assert len(decoded.text) == 255
    for byte, char in zip(data, decoded.text, strict=True):
        if byte in (0x81, 0x8D, 0x8F, 0x90, 0x9D):
            assert char == chr(byte)
        else:
            assert char == bytes([byte]).decode("cp1252")


def test_bad_sequences_after_a_byte_order_mark_become_replacement_characters() -> None:
    decoded = decode_text(codecs.BOM_UTF8 + b"ok \xff ok", "notes.txt")
    assert (decoded.text, decoded.encoding, decoded.guessed) == ("ok � ok", "utf-8", False)
    odd = decode_text(codecs.BOM_UTF16_LE + "ab".encode("utf-16-le") + b"x", "notes.txt")
    assert odd.text == "ab�"


# ---- broken files (D-347) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "the file is empty"),
        (b"  \n\t\n\r\n", "the file holds no text"),
        (codecs.BOM_UTF8, "the file holds no text"),
        (codecs.BOM_UTF16_LE + " \n".encode("utf-16-le"), "the file holds no text"),
        (b"text\x00more", "not a text file"),
        ("a\x00b".encode("utf-16-le"), "not a text file"),  # UTF-16 without a mark
        (codecs.BOM_UTF16_LE + "a\x00b".encode("utf-16-le"), "not a text file"),
        (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", "this is a PDF, not a text file; open it with the .pdf"),
        (b"PK\x03\x04" + b"mimetypeapplication/epub+zip", "not a text file"),
        (b"\x89PNG\r\n\x1a\n" + b"IHDR", "not a text file"),
        (b"\xff\xd8\xff\xe0" + b"JFIF", "not a text file"),
        (b"GIF89a" + b"rest", "not a text file"),
        (b"GIF87a" + b"rest", "not a text file"),
        (b"\x1f\x8b\x08" + b"rest", "not a text file"),
        (b"word " * 800_001, "holds a paragraph longer than 4,000,000 characters"),  # #607
    ],
)
def test_broken_files_fail_with_a_clear_message(data: bytes, message: str) -> None:
    with pytest.raises(ExtractionError, match=message) as error:
        read(data)
    assert str(error.value).startswith("notes.txt: ")


def test_a_too_large_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_module, "MAX_TEXT", 10)
    with pytest.raises(ExtractionError, match="the file is too large"):
        read(b"x" * 11)
    assert lines(read(b"x" * 10)) == [("x" * 10, ("p",))]


def test_the_limit_is_the_decided_one() -> None:
    """D-351; the test above lowers it to keep the file small."""
    assert text_module.MAX_TEXT == 64 * 1024 * 1024


def test_a_large_file_is_read_in_linear_time() -> None:
    """Eight times the lines against a base run, on CPU time (#298). One paragraph of 100,000
    lines, so that a reader quadratic in a paragraph's lines fails; the lines are short (28
    characters) to keep the paragraph, 2.8 million characters, under `MAX_PARAGRAPH` (#607)."""
    line = "A short line of plain text.\n"
    content = assert_linear(lambda text: read(text.encode()), lambda n: line * n, 100_000)
    assert len(content.pages[0].lines) == 100_000


# ---- the line limit (#174, D-579) ----------------------------------------------------------

LINES_MESSAGE = (
    r"^notes\.txt: the file is too large; sci2audio reads text files of up to 500,000 lines$"
)


def test_a_file_of_more_lines_than_the_limit_is_refused_before_it_is_split() -> None:
    """500,001 lines of one letter (1 MB) would hold 500,001 lines in memory; the lines are
    counted on the decoded text, so the refusal costs little more than the file itself."""
    data = b"w\n" * 500_001
    tracemalloc.start()
    try:
        with pytest.raises(ExtractionError, match=LINES_MESSAGE):
            read(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 20 * 1024 * 1024


@pytest.mark.slow
def test_a_file_of_exactly_the_limit_still_reads() -> None:
    assert len(read(b"w\n" * 500_000).pages[0].lines) == 500_000


@pytest.mark.parametrize(
    ("text", "printed"),
    [
        ("a\nb\nc", 3),
        ("a\nb\nc\n", 3),  # a line end after the last line starts no new one
        ("a\r\nb\r\nc\r\n", 3),  # CR LF is one line end
        ("a\rb\rc", 3),
        ("a\n\n\nb", 4),  # blank lines count
        ("\n\n\na", 4),
    ],
)
def test_every_printed_line_counts_blank_ones_too(
    monkeypatch: pytest.MonkeyPatch, text: str, printed: int
) -> None:
    assert text_module.line_count(text) == printed
    monkeypatch.setattr(text_module, "MAX_LINES", printed)
    read(text.encode())
    monkeypatch.setattr(text_module, "MAX_LINES", printed - 1)
    with pytest.raises(ExtractionError, match=f"of up to {printed - 1:,} lines$"):
        read(text.encode())


def test_the_line_limit_is_the_decided_one() -> None:
    assert text_module.MAX_LINES == 500_000  # D-579


# ---- the paragraph limit (#607, D-777) -----------------------------------------------------

PARAGRAPH_MESSAGE = (
    "notes.txt: the file holds a paragraph longer than {:,} characters"
    " (counted between blank lines)"
)


def refused_before_it_is_split(data: bytes, monkeypatch: pytest.MonkeyPatch) -> int:
    """The peak (tracemalloc) of refusing `data`, which must happen before any line is built."""

    def fold(_: str) -> str:
        raise AssertionError("a line was built")

    monkeypatch.setattr(text_module, "fold", fold)
    tracemalloc.start()
    try:
        with pytest.raises(ExtractionError) as error:
            read(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert str(error.value) == PARAGRAPH_MESSAGE.format(4_000_000)
    return peak


def test_one_long_line_past_the_paragraph_limit_is_refused_before_lines_are_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One line of 64 MB took 1 GB to read and handed layout one paragraph of that size."""
    peak = refused_before_it_is_split(b"word " * (8 * 1024 * 1024 // 5), monkeypatch)
    assert peak < 40 * 1024 * 1024


def test_a_paragraph_of_many_lines_past_the_limit_is_refused_before_lines_are_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    peak = refused_before_it_is_split(
        (b"word " * 53 + b"\n") * (8 * 1024 * 1024 // 266), monkeypatch
    )
    assert peak < 40 * 1024 * 1024


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"w" * 4_000_000, id="one line"),
        pytest.param((b"word " * 53 + b"\n") * (4_000_000 // 266), id="short lines"),
    ],
)
def test_a_paragraph_at_the_real_limit_still_reads_in_bounded_memory(data: bytes) -> None:
    """Measured at the limit: one line of "word " peaks at 58 MB under tracemalloc, short lines
    at 19 MB."""
    assert text_module.longest_paragraph(data.decode()) <= 4_000_000
    tracemalloc.start()
    try:
        content = read(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 100 * 1024 * 1024
    assert content.pages[0].lines


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 9 + "\n\n" + "b" * 9, id="paragraphs"),
        pytest.param("a" * 9 + "\n \t\f\n" + "b" * 9, id="a blank line of white space"),
        pytest.param("a" * 8 + "\r\n\r\n" + "b" * 9, id="CR LF"),
        pytest.param("a" * 9 + "\r\r" + "b" * 9, id="CR"),
        pytest.param("a" * 10, id="one line"),
        pytest.param("a" * 4 + "\n" + "b" * 5, id="two lines"),
    ],
)
def test_paragraphs_at_the_limit_read(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """Each paragraph holds at most 10 characters, its line ends included."""
    monkeypatch.setattr(text_module, "MAX_PARAGRAPH", 10)
    assert read(text.encode()).pages[0].lines


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 11, id="one line"),
        pytest.param("a" * 5 + "\n" + "b" * 5, id="two lines"),
        pytest.param("x\n\n" + "a" * 5 + "\r\n" + "b" * 5, id="CR LF inside a paragraph"),
        pytest.param("a\nb\nc\nd\ne\nf", id="many short lines"),
        pytest.param("a" * 6 + "\n\u00a0\n" + "b" * 6, id="a no-break space is no blank line"),
    ],
)
def test_a_paragraph_past_the_limit_fails(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(text_module, "MAX_PARAGRAPH", 10)
    with pytest.raises(ExtractionError) as error:
        read(text.encode())
    assert str(error.value) == PARAGRAPH_MESSAGE.format(10)


@pytest.mark.parametrize(
    ("text", "longest"),
    [
        ("", 0),
        ("\n\n", 0),
        ("abc", 3),
        ("abc\n", 4),
        ("ab\ncd\n\nefghij", 6),
        ("ab\r\ncd\r\n \r\nx", 8),
        ("ab\rcd\r\t\r", 6),
        ("  \t\f  \n", 0),
        (" " * 100 + "x", 101),  # spaces before text make no blank line
        ("a\n\u00a0\nb", 5),  # a no-break space is text, as `fold` has it
    ],
)
def test_the_longest_paragraph_counts_characters_between_blank_lines(
    text: str, longest: int
) -> None:
    assert text_module.longest_paragraph(text) == longest


def test_the_longest_paragraph_is_found_in_linear_time() -> None:
    def sized(size: int) -> str:
        return ("a" * 50 + "\n" + " " * 50 + "\n\n") * (size // 103)

    assert_linear(text_module.longest_paragraph, sized, 4_000_000)


def test_the_paragraph_limit_is_the_decided_one() -> None:
    assert text_module.MAX_PARAGRAPH == 4_000_000  # D-777, as markup.MAX_LINE


# ---- properties --------------------------------------------------------------------------


def outcome(data: bytes) -> Content | str:
    """The content, or the message of the ExtractionError (any other error fails the test)."""
    try:
        return read(data)
    except ExtractionError as error:
        return str(error)


@given(st.binary(max_size=2000))
def test_any_bytes_give_content_or_a_clear_error(data: bytes) -> None:
    content = outcome(data)
    if isinstance(content, str):
        assert content.startswith("notes.txt: ")
        return
    for line in content.pages[0].lines:
        assert line.text == line.text.strip(" ")
        assert "  " not in line.text
        assert not set(line.text) & set("\n\r\t\x0c")


printed = st.text(
    st.characters(exclude_categories=("Cs",), exclude_characters="\x00\n\r"), max_size=40
).map(lambda text: " ".join(text.replace("\x0c", " ").replace("\t", " ").split(" ")))
paragraphs = st.lists(
    st.lists(printed.filter(lambda text: text.strip(" ")), min_size=1, max_size=4),
    min_size=1,
    max_size=5,
)


STARTS = {("p",), ("ul", "li"), ("ol", "li")}  # the tags of a line that starts an element


@given(paragraphs, st.sampled_from(["utf-8", "utf-8-sig", "utf-16", "utf-32"]))
def test_paragraphs_come_back_line_for_line_in_every_declared_encoding(
    written: list[list[str]], codec: str
) -> None:
    """Every printed line comes back once, in order, folded; a paragraph's first line starts
    an element, and every other line starts one or continues the one before (#466)."""
    data = "\n\n".join("\n".join(paragraph) for paragraph in written).encode(codec)
    expected = [
        " ".join(t for t in " ".join(line.split(" ")).strip(" ").split(" ") if t)
        for paragraph in written
        for line in paragraph
    ]
    content = read(data)
    assert [text for text, _ in lines(content)] == expected
    firsts = {sum(map(len, written[:k])) for k in range(len(written))}
    for k, (_, tags) in enumerate(lines(content)):
        assert tags in STARTS if k in firsts else (tags in STARTS or tags[-1] == "br")
    assert not content.source.encoding_guessed


prose = st.lists(
    st.text("abcdefghijklmnopqrstuvwxyzäöüß ,;", min_size=1, max_size=40).filter(str.strip),
    min_size=1,
    max_size=4,
)


@given(st.lists(prose, min_size=1, max_size=5))
def test_prose_lines_of_a_paragraph_are_joined(written: list[list[str]]) -> None:
    """Lines with no list marker and no title line before them keep D-344's tags: ``p``
    for a paragraph's first line, ``p, br`` for each following one."""
    data = "\n\n".join("\n".join(paragraph) for paragraph in written).encode()
    tags = [tags for _, tags in lines(read(data))]
    expected = [
        ("p",) if index == 0 else ("p", "br")
        for paragraph in written
        for index, _ in enumerate(paragraph)
    ]
    assert tags == expected


# ---- structure inside a paragraph (#466) -------------------------------------------------


def tags_of(text: str) -> list[tuple[str, ...]]:
    return [tags for _, tags in lines(read(text.encode()))]


@pytest.mark.parametrize("marker", ["- ", "* ", "\u2022 "])
def test_a_bulleted_line_starts_a_list_item(marker: str) -> None:
    text = f"Our points:\n{marker}first point\n{marker}second point\n"
    assert lines(read(text.encode())) == [
        ("Our points:", ("p",)),
        (f"{marker}first point", ("ul", "li")),
        (f"{marker}second point", ("ul", "li")),
    ]


@pytest.mark.parametrize("style", [".", ")"])
def test_numbered_lines_that_count_up_start_list_items(style: str) -> None:
    text = f"1{style} First point\n2{style} Second point\n3{style} Third point\n"
    assert tags_of(text) == [("ol", "li")] * 3


def test_a_wrapped_list_item_continues_on_its_next_line() -> None:
    text = "- a first point that is long\n  and wraps onto a second line\n- second point\n"
    assert tags_of(text) == [("ul", "li"), ("ul", "li", "br"), ("ul", "li")]


def test_a_lone_numbered_line_or_a_german_date_stays_text() -> None:
    """A number starts a list item only in a run of two that count up: "1. Introduction"
    alone and a paragraph opening with a date ("3. Oktober 1990") are text."""
    assert tags_of("1. Introduction\n") == [("p",)]
    text = "3. Oktober 1990 war ein Feiertag, und die Menschen gingen auf\ndie Straße.\n"
    assert tags_of(text) == [("p",), ("p", "br")]


def test_only_the_run_of_numbers_that_count_up_are_items() -> None:
    """ "1." "2." are items; "4." after them does not follow, and stays a wrapped line."""
    text = "1. First point of a list\n2. Second point of a list\n4. not the third one\n"
    assert tags_of(text) == [("ol", "li"), ("ol", "li"), ("ol", "li", "br")]


def test_a_dash_or_number_inside_a_line_is_no_marker() -> None:
    text = "The result - as expected - was 2. the second\nline goes on here as wrapped prose.\n"
    assert tags_of(text) == [("p",), ("p", "br")]


@pytest.mark.parametrize(
    ("title", "after"),
    [
        ("LISTENING TO PAPERS", "A pilot note written for the sci2audio tests"),
        ("PAPERS HÖREN", "Eine Pilotnotiz für die Tests von sci2audio"),
        ("A Short Title", "This line starts with a capital and runs on for long."),
        ("„Ein Titel“", "»Dieser Satz« beginnt mit einem Großbuchstaben und läuft weiter."),
    ],
)
def test_the_line_after_a_title_line_starts_a_paragraph(title: str, after: str) -> None:
    assert tags_of(f"{title}\n{after}\n") == [("p",), ("p",)]


def test_hard_wrapped_prose_stays_one_paragraph() -> None:
    """A capital at the start of a line is no cut when the line before is not short (German
    nouns), nor when a short line ends in punctuation, a hyphen or a dash."""
    text = (
        "Diese Notiz beschreibt eine erfundene Pilotstudie und keine echten\n"
        "Daten. Jeder Satz darin ist unser eigener, und die Zeilen sind von\n"
        "Hand umbrochen.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]
    for end in (",", ";", "-", "\u2013", ":"):
        text = f"Short line{end}\nThis line starts with a capital and runs on for long.\n"
        assert tags_of(text) == [("p",), ("p", "br")], end


def test_a_short_line_before_a_lower_case_line_stays_joined() -> None:
    text = "a line in a poem\nkeeps where it breaks, and this line is long.\n"
    assert tags_of(text) == [("p",), ("p", "br")]


def test_a_poem_with_capitalised_lines_of_even_length_stays_one_paragraph() -> None:
    text = "Roses are red\nViolets are blue\nSugar is sweet\nAnd so are you.\n"
    assert tags_of(text) == [("p",), *[("p", "br")] * 3]


def test_a_wrapped_text_in_capitals_stays_one_paragraph() -> None:
    """A licence in capitals, wrapped by hand: no line but the last is short."""
    text = (
        "THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY\n"
        "AND FITNESS FOR A PARTICULAR PURPOSE.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


def test_a_title_line_needs_two_letters() -> None:
    """A short number or sign is no title: "2026" before a capital stays joined."""
    assert tags_of("0\nA line of prose that runs on for a while here.\n") == [("p",), ("p", "br")]


def test_a_short_line_in_capitals_is_a_title_line_whatever_it_ends_with() -> None:
    """A line in capitals cuts even where a mixed-case line would run on (its colon)."""
    assert tags_of("ABSTRACT:\nthe text of the abstract runs on for a long line.\n") == [
        ("p",),
        ("p",),
    ]


def test_numbers_of_two_styles_make_no_run() -> None:
    """ "1." then "2)" count up but differ in style: no list, the lines stay joined."""
    text = "1. First point of a list\n2) second point of a list\n"
    assert tags_of(text) == [("p",), ("p", "br")]


# ---- #561: spaced dashes, one long token, the property ---------------------------------


def test_a_spaced_dash_wrapped_to_a_line_s_start_stays_in_its_sentence() -> None:
    """M1: " - " as a dash, put at a line's start by the wrap, opens no list item."""
    text = (
        "Teilnehmer hörten die Texte - meist unterwegs\n"
        "- und beantworteten danach Fragen zum Inhalt\n"
        "der Texte.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


def test_a_list_after_a_colon_or_another_item_opens_items() -> None:
    """A marker line opens an item first in a paragraph, after an item (or its wrapped
    line), or after a line ending in a colon; after other prose it stays a wrapped line."""
    assert tags_of("We found two things:\n- one\n- two\n") == [
        ("p",),
        ("ul", "li"),
        ("ul", "li"),
    ]
    assert tags_of("We found two things that\n- matter here and\n- elsewhere too.\n") == [
        ("p",),
        ("p", "br"),
        ("p", "br"),
    ]


def test_a_numbered_run_after_prose_without_a_colon_stays_in_its_sentence() -> None:
    """The anchor holds for numbered runs too: dates wrapped to two line starts in a row."""
    text = "Die Termine der Studie lagen am\n3. Oktober und am\n4. November, beide im Herbst.\n"
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]
    assert tags_of("Die Termine:\n3. Oktober\n4. November\n") == [
        ("p",),
        ("ol", "li"),
        ("ol", "li"),
    ]


URL = "https://example.org/archiv/daten/2026/pilotstudie/hoeren/rohdaten/version-3/index.html"


def test_one_long_token_does_not_make_the_filled_lines_short() -> None:
    """M2: a URL on a line of its own does not count as the paragraph's width, so a German
    noun at the start of a filled line cuts nothing."""
    prose = (
        "Die Studie wurde von der Deutschen Forschungsgemeinschaft gefördert und lief an"
        f" drei Standorten; die Daten liegen unter {URL} Die Auswertung der Daten folgt im"
        " nächsten Abschnitt, den Ergebnissen der Teilnehmer."
    )
    text = textwrap.fill(prose, 50, break_long_words=False) + "\n"
    assert URL + "\n" in text  # the URL stands on a line of its own
    assert tags_of(text) == [("p",), *[("p", "br")] * (text.count("\n") - 1)]


words = st.from_regex(r"[A-ZÄÖÜ][a-zäöüß]{1,11}|[a-zäöüß]{1,12}|-", fullmatch=True)


@given(
    st.lists(words, min_size=8, max_size=80),
    st.integers(40, 80),
    st.sampled_from([None, URL]),
    st.data(),
)
def test_hard_wrapped_prose_with_capitals_dashes_and_a_long_token_is_one_paragraph(
    found: list[str], width: int, token: str | None, data: st.DataObject
) -> None:
    """S1: words with capitals, spaced dashes and at most one long token, hard-wrapped,
    come back as one element: ``p``, then ``p, br``."""
    if token:
        found.insert(data.draw(st.integers(1, len(found))), token)
    text = textwrap.fill("Am " + " ".join(found) + ".", width, break_long_words=False)
    assert tags_of(text + "\n") == [("p",), *[("p", "br")] * text.count("\n")]


# ---- #561: closers looked through, the two-letter minimum ----------


@pytest.mark.parametrize(
    "line",
    ["She said “yes,”", "Er sagte: »Ja,«", "(see the note above,)"],
)
def test_punctuation_before_closing_quotes_or_brackets_keeps_the_lines_joined(line: str) -> None:
    """A short line ending in a comma inside closing quotes or a bracket runs on: the
    closers are looked through (#561)."""
    text = f"{line}\nThen the second line runs on for quite a long while here.\n"
    assert tags_of(text) == [("p",), ("p", "br")]


def test_a_two_letter_line_can_be_a_title_line() -> None:
    """Two letters are enough: "EU" alone before a capital starts a new paragraph after it
    (#561); "0" has none and stays joined."""
    text = "EU\nThe second line runs on for quite a long while here, as prose does.\n"
    assert tags_of(text) == [("p",), ("p",)]


# ---- #570: a title line between two prose lines ------------------------------------------


@pytest.mark.parametrize("end", [".", "!", "?", "…", ".”", ".)"])
def test_a_title_line_after_the_end_of_a_sentence_starts_an_element_of_its_own(end: str) -> None:
    """A short line in capitals inside a paragraph, after a line that ends a sentence, is cut
    before as well as after: the heading is not read as the end of the prose before it."""
    text = (
        f"The first part of the note ends here, at the end of the first part{end}\n"
        "RESULTS\n"
        "The second part starts on this line and runs on for a while here.\n"
    )
    assert tags_of(text) == [("p",), ("p",), ("p",)]


def test_a_german_title_line_after_a_sentence_starts_an_element_of_its_own() -> None:
    text = (
        "Der erste Teil der Notiz endet hier, am Ende des ersten Teils.\n"
        "ERGEBNISSE DER STUDIE\n"
        "Der zweite Teil beginnt in dieser Zeile und läuft eine Weile weiter.\n"
    )
    assert tags_of(text) == [("p",), ("p",), ("p",)]


@pytest.mark.parametrize("end", ["", ",", ":", ";", "-"])
def test_a_title_line_after_a_line_that_runs_on_stays_joined_to_it(end: str) -> None:
    """Without the end of a sentence before it, the short line in capitals ends the element
    before it, as it did (#466): an acronym wrapped onto a line of its own stays in place."""
    text = (
        f"The first part of the note runs on here and names the agency of the{end}\n"
        "NASA JPL\n"
        "The second part starts on this line and runs on for a while here.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p",)]


def test_a_short_last_line_in_capitals_after_a_sentence_stays_joined() -> None:
    """The last line of a paragraph has no next line to start: a licence in capitals whose
    short last line follows a full stop stays one paragraph."""
    text = (
        "THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING THE WARRANTIES OF MERCHANTABILITY. IN NO EVENT SHALL.\n"
        "THE AUTHORS BE LIABLE.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


@pytest.mark.parametrize(
    ("first", "second", "item"),
    [
        ("- Install the package from the website first.", "- Run the installer now.", "ul"),
        ("1. Install the package from the website first.", "2. Run the installer now.", "ol"),
    ],
)
def test_a_line_in_capitals_between_two_list_items_keeps_the_list(
    first: str, second: str, item: str
) -> None:
    """The heading rule applies after prose only: a short line in capitals after an item
    that ends a sentence continues that item, and the next item stays an item (#570)."""
    assert tags_of(f"{first}\nWINDOWS\n{second}\n") == [
        (item, "li"),
        (item, "li", "br"),
        (item, "li"),
    ]


def test_a_short_mixed_case_line_after_a_sentence_is_not_cut_before() -> None:
    """Only a line in capitals is cut before (`_capitals`): "Results" or a poem's line after
    a full stop stays joined to the line before it."""
    text = (
        "The first part of the note ends here, at the end of the first part.\n"
        "Results\n"
        "the second part starts on this line and runs on for a while here.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


def test_a_long_line_in_capitals_after_a_sentence_is_not_cut_before() -> None:
    """Only a short line is cut before (`_short`): a full line in capitals after a full stop
    is wrapped prose, as in a licence that mixes cases."""
    text = (
        "The first part of the note ends here, at the end of the first part.\n"
        "THE SOFTWARE IS PROVIDED AS IS, WITHOUT ANY WARRANTY OF ANY KIND\n"
        "and the second part starts on this line and runs on for a while.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


# ---- #827: a line ending in an abbreviation does not end a sentence ----------------------


@pytest.mark.parametrize(
    "end",
    ["e.g.", "i.e.", "etc.", "Calif.", "Jan.", "z. B.", "d. h.", "usw.", "(e.g.", "e.g.)"],
)
def test_a_line_ending_in_an_abbreviation_keeps_a_capitals_line_in_its_sentence(
    end: str,
) -> None:
    """An abbreviation's full stop is not the end of a sentence: an acronym wrapped onto a
    line of its own after it stays in the paragraph, as after a line that runs on (#827)."""
    text = (
        f"The tool reads many kinds of input, among them scanned pages and {end}\n"
        "PDF\n"
        "files and plain text, and it runs on for a while here as prose does.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


def test_the_issue_example_after_e_g_stays_one_paragraph() -> None:
    text = (
        "The tool reads many kinds of input, such as text, markdown and scans, e.g.\n"
        "PDF\n"
        "files and plain text, and it runs on for a while here as prose does.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


@pytest.mark.parametrize("end", ["the end of the first part.", "the age of three.", "go."])
def test_a_word_ending_like_an_abbreviation_still_ends_a_sentence(end: str) -> None:
    """Only a listed abbreviation is looked through: an ordinary last word ("part.", "three.",
    "go.") still ends the sentence before a capitals heading (#570)."""
    text = (
        f"The first part of the note ends here, and it ends at {end}\n"
        "RESULTS\n"
        "The second part starts on this line and runs on for a while here.\n"
    )
    assert tags_of(text) == [("p",), ("p",), ("p",)]


def test_a_capitals_line_before_a_lower_case_line_does_not_end_its_paragraph() -> None:
    """A short line in capitals before a line starting in lower case is a wrapped acronym,
    not a title: the sentence runs on through it (#827)."""
    text = (
        "The first part of the note runs on here and names the agency of the\n"
        "NASA JPL\n"
        "and its partners, and it runs on for a while here as prose does.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")]


# ---- #812: a mixed-case heading between two prose lines ----------------------------------

_INTRO = "The first part of the note ends here, at the end of the first part.\n"
_BODY = "The next part starts on this line and runs on for a while here.\n"


def test_two_mixed_case_headings_between_prose_lines_start_elements_of_their_own() -> None:
    """A short capitalised line without a sentence end, between a line that ends a sentence
    and a prose line, is a heading when another line of the document has the same shape."""
    text = f"{_INTRO}Methods\n{_BODY}{_INTRO}Results and discussion\n{_BODY}"
    assert tags_of(text) == [("p",), ("p",), ("p",), ("p", "br"), ("p",), ("p",)]


def test_mixed_case_headings_count_across_paragraphs() -> None:
    text = f"{_INTRO}Methods\n{_BODY}\n{_INTRO}Ergebnisse\n{_BODY}"
    assert tags_of(text) == [("p",), ("p",), ("p",), ("p",), ("p",), ("p",)]


def test_one_stray_mixed_case_line_between_prose_lines_stays_joined() -> None:
    """One such line alone is not cut before: it may be a short wrapped line."""
    text = f"{_INTRO}Methods\n{_BODY}"
    assert tags_of(text) == [("p",), ("p", "br"), ("p",)]


def test_a_mixed_case_heading_shape_needs_the_end_of_a_sentence_before_it() -> None:
    """After a line that runs on, or a line ending in an abbreviation, the short line stays
    in its sentence even when the document shows the heading shape elsewhere."""
    runs_on = "The first part of the note runs on here and names the agency of the\n"
    abbreviation = "The first part of the note runs on here and names, e.g.\n"
    text = (
        f"{_INTRO}Methods\n{_BODY}{_INTRO}Results\n{_BODY}"
        f"{runs_on}Results\n{_BODY}{abbreviation}Results\n{_BODY}"
    )
    br = ("p", "br")
    assert tags_of(text) == [
        *[("p",), ("p",), ("p",), br, ("p",), ("p",)],
        *[br, br, ("p",)],
        *[br, br, ("p",)],
    ]


def test_short_last_lines_and_lines_that_run_on_stay_joined() -> None:
    """A paragraph's short last line, a short line ending in punctuation and a short line
    before a line in lower case stay joined, however often they occur (#812)."""
    br = ("p", "br")
    last = f"{_INTRO}Thank you\n"
    assert tags_of(f"{last}\n{last}") == [("p",), br, ("p",), br]
    punctuated = f"{_INTRO}Results of the study,\n{_BODY}"
    assert tags_of(punctuated * 2) == [("p",), *[br] * 5]
    lower = f"{_INTRO}Results of the\nnext part start on this line and run on for a while.\n"
    assert tags_of(lower * 2) == [("p",), *[br] * 5]


def test_a_short_line_a_hard_wrap_left_before_a_long_word_is_no_mixed_case_heading() -> None:
    """A short line whose next line's first word would not have fit after it is a hard wrap,
    not a heading, however often it occurs (#812)."""
    word = "Rindfleischetikettierungsueberwachungsaufgabenuebertragungsgesetze"
    text = f"{_INTRO}The new\n{word}.\n" * 2
    br = ("p", "br")
    assert tags_of(text) == [("p",), br, ("p",), br, br, ("p",)]


# ---- #827: a capitals title before a lower-case first word still cuts --------------------


@pytest.mark.parametrize(
    "after", ["this paper presents a method", "mRNA vaccines are discussed", "pH values rose"]
)
def test_a_first_line_in_capitals_before_a_lower_case_line_is_a_title_line(after: str) -> None:
    """A heading whose next line starts in lower case ("mRNA", "pH") still ends its element:
    only a capitals line inside a running sentence runs on (#827)."""
    text = f"ABSTRACT\n{after} and runs on for a long line here as prose does.\n"
    assert tags_of(text) == [("p",), ("p",)]


@pytest.mark.parametrize("heading", ["INTRODUCTION", "RESULTS"])
def test_a_capitals_heading_after_a_sentence_before_a_lower_case_line_is_cut(
    heading: str,
) -> None:
    text = (
        "The samples were prepared as before and all of them were checked twice.\n"
        f"{heading}\n"
        "mRNA levels and pH values rose in every sample, and it runs on here.\n"
    )
    assert tags_of(text) == [("p",), ("p",), ("p",)]


def test_a_short_line_in_capitals_without_a_colon_is_a_title_line() -> None:
    """The no-colon variant of the "ABSTRACT:" pin above."""
    assert tags_of("ABSTRACT\nthe text of the abstract runs on for a long line.\n") == [
        ("p",),
        ("p",),
    ]


# ---- #848: a number before a full stop ---------------------------------------------------

_ORDINAL = "Die Konferenz fand in diesem Jahr in Berlin statt, und zwar am 3.\n"
_NUMBER = "The tool reads many kinds of input, and the error rose to approximately 3.\n"
_NEW = "The second part starts on this line and runs on for a while here.\n"


@pytest.mark.parametrize("month", ["OKTOBER", "MAERZ", "MÄRZ", "DEZEMBER", "(JULI"])
def test_a_german_ordinal_before_a_month_in_capitals_stays_in_its_sentence(month: str) -> None:
    """ "am 3." / "OKTOBER" is a date wrapped over two lines, not a sentence end before a
    heading: the month stays in the sentence (#848). (The line after the month is judged by
    the title rule, which this issue leaves alone.)"""
    text = f"{_ORDINAL}{month}\nDie Teilnehmer kamen aus ganz Europa zusammen und blieben da.\n"
    assert tags_of(text)[:2] == [("p",), ("p", "br")]


def test_a_german_ordinal_before_a_month_is_no_sentence_end_for_a_mixed_case_heading() -> None:
    """ "am 3." / "Oktober 2020" twice in a document: the month line is the date's second
    half, not a mixed-case heading after a sentence end (#848)."""
    second = "Die Auswertung lief danach noch eine ganze Weile, und zwar bis zum 7.\n"
    after = "Die Teilnehmer kamen aus ganz Europa zusammen und blieben lange da.\n"
    text = f"{_ORDINAL}Oktober 2020\n{after}{second}März 2021\n{after}"
    br = ("p", "br")
    assert tags_of(text)[:2] == [("p",), br]
    assert tags_of(text)[3:5] == [br, br]


def test_a_german_ordinal_before_a_line_that_goes_on_stays_one_paragraph() -> None:
    text = f"{_ORDINAL}Oktober 2020 in einem grossen Saal mit vielen Teilnehmern aus Europa.\n"
    assert tags_of(text) == [("p",), ("p", "br")]


def test_a_number_before_a_stop_runs_on_into_a_lower_case_line() -> None:
    """ "approximately 3." / "files and ...": a lower-case next line goes on. The title rule
    cuts only before a line starting with a capital or a date (`_title`), so the number's
    stop is not judged for this line (#848, #900)."""
    text = f"{_NUMBER}files and plain text, and it runs on for a while here as prose does.\n"
    assert tags_of(text) == [("p",), ("p", "br")]


@pytest.mark.parametrize("heading", ["RESULTS", "MARCH", "MAY 2020", "JULY", "PDF"])
def test_a_capitals_heading_after_a_number_before_a_stop_is_cut_before_a_new_sentence(
    heading: str,
) -> None:
    """ "approximately 3." / "RESULTS" / "The second ...": the number's stop ends a sentence
    and the heading is cut before and after (#570, #848). An English month is a heading:
    English writes no "3. March"."""
    assert tags_of(f"{_NUMBER}{heading}\n{_NEW}") == [("p",), ("p",), ("p",)]


@pytest.mark.parametrize("heading", ["RESULTS", "PDF"])
def test_a_capitals_heading_after_a_number_before_a_stop_keeps_its_cuts_before_lower_case(
    heading: str,
) -> None:
    """ "approximately 3." / "RESULTS" / "mRNA levels ...": a short capitals line keeps its
    title cuts after a number's stop, as after any sentence end (#827, #848)."""
    after = "mRNA levels and pH values rose in every sample, and it runs on here.\n"
    assert tags_of(f"{_NUMBER}{heading}\n{after}") == [("p",), ("p",), ("p",)]


def test_an_english_month_line_after_a_number_before_a_stop_stays_a_mixed_case_heading() -> None:
    """ "we used 3." / "June 2020" / "The second ..." twice: both month lines are headings,
    cut before and after, as without #848."""
    text = f"The first part of the note ends here, and for it we used 3.\nJune 2020\n{_NEW}" * 2
    assert tags_of(text) == [("p",), ("p",), ("p",), ("p", "br"), ("p",), ("p",)]


def test_a_german_month_in_capitals_after_a_number_before_a_stop_joins_the_sentence() -> None:
    """The trade-off of #848, pinned (#900): "betrug 3." / "MÄRZ 2021" / "Die ..." reads like
    "am 3." / "MÄRZ 2021", so the month heading joins the paragraph before it. Only the
    line's end and the next line's first word are looked at, and nothing there tells a
    number before a heading from an ordinal before its month; a German date wrapped after
    its day is the more common of the two. The line after the month still starts a
    paragraph by the title rule."""
    text = (
        "Der Anteil der Teilnehmer aus dem Ausland betrug am Ende nur 3.\n"
        "MÄRZ 2021\n"
        "Die Teilnehmer kamen aus ganz Europa zusammen und blieben da noch.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p",)]


# ---- #893: a month line inside a running sentence ----------------------------------------

_IM = "Die Konferenz fand in diesem Jahr in Berlin statt, und zwar im\n"
_YEAR = "2020 kamen die Teilnehmer aus ganz Europa zusammen und blieben da.\n"
_DIE = "Die Teilnehmer kamen aus ganz Europa zusammen und blieben da noch.\n"
_DONE = "Die Teilnehmer kamen aus ganz Europa zusammen und blieben lange da.\n"


@pytest.mark.parametrize("before", [_ORDINAL, _IM], ids=["am 3.", "im"])
@pytest.mark.parametrize(
    ("month", "after"),
    [("OKTOBER", _YEAR), ("(DEZEMBER", _YEAR), ("Oktober 2020", _DIE)],
    ids=["OKTOBER", "(DEZEMBER", "Oktober 2020"],
)
def test_a_month_line_inside_a_running_sentence_stays_in_its_paragraph(
    before: str, month: str, after: str
) -> None:
    """ "am 3." / "OKTOBER" / "2020 kamen ..." and "im" / "Oktober 2020" / "Die ...": a month,
    or a month and a year, inside a running sentence is part of a date, not a title; the
    line after it goes on in the same paragraph (#893)."""
    assert tags_of(f"{before}{month}\n{after}") == [("p",), ("p", "br"), ("p", "br")]


def test_a_month_heading_between_two_finished_paragraphs_still_cuts() -> None:
    """ "OKTOBER 2020" after a finished sentence, or alone between blank lines, is a heading
    (#570, #893); so is "Oktober 2020" twice in a document (#812)."""
    assert tags_of(f"{_DONE}OKTOBER 2020\n{_DIE}") == [("p",), ("p",), ("p",)]
    assert tags_of(f"{_DONE}\nOKTOBER 2020\n\n{_DIE}") == [("p",), ("p",), ("p",)]
    twice = f"{_DONE}Oktober 2020\n{_DIE}" * 2
    assert tags_of(twice) == [("p",), ("p",), ("p",), ("p", "br"), ("p",), ("p",)]


def test_a_capitals_line_that_is_no_month_before_a_number_still_cuts() -> None:
    """Only a month line runs on into a line starting with a number: "NASA JPL" / "2020 ..."
    keeps the title cut it had (#827, #893)."""
    text = (
        "The first part of the note runs on here and names the agency of the\n"
        "NASA JPL\n"
        "2020 was the year in which the second part starts and runs on here.\n"
    )
    assert tags_of(text) == [("p",), ("p", "br"), ("p",)]


@pytest.mark.parametrize(
    ("lines", "tags"),
    [
        (["LISTENING TO PAPERS", "April 2020", "A pilot note on reading papers aloud."], "ppp"),
        (["Jahresbericht der Gesellschaft", "Oktober 2020", _DIE.strip()], "ppp"),
        (["Protokoll der Sitzung", "Mai 2021", _DIE.strip()], "ppp"),
        ([_DONE.strip(), "Ergebnisse", "Oktober 2020", _DIE.strip()], "pbpp"),
    ],
    ids=["title-april", "jahresbericht-oktober", "protokoll-mai", "ergebnisse-oktober"],
)
def test_a_month_line_after_a_title_line_keeps_its_cut(lines: list[str], tags: str) -> None:
    """A short title line before a date ends no sentence either, but it is no running
    sentence: the date in a heading block (title, date, body) keeps the cut after it
    (#893). ``p`` is a new paragraph, ``b`` a line joined to the one before."""
    expected = [("p",) if t == "p" else ("p", "br") for t in tags]
    assert tags_of("\n".join(lines) + "\n") == expected


# ---- #903: an English month line inside a running sentence -------------------------------

_PUBLISHED = "The first version of the reading tool was published, as planned, in\n"
_THE = "The second part starts on this line and runs on for a while here.\n"
_ENGLISH_MONTHS = (
    *("January", "February", "March", "April", "May", "June", "July", "August"),
    *("September", "October", "November", "December"),
)


@pytest.mark.parametrize("month", _ENGLISH_MONTHS)
def test_an_english_month_line_inside_a_running_sentence_stays_in_its_paragraph(
    month: str,
) -> None:
    """ "... published in" / "June 2020" / "The ...": every English month behaves alike, the
    ones spelled as in German (April) and the English-only ones (June) (#903)."""
    for line in (month, f"{month} 2020"):
        text = f"{_PUBLISHED}{line}\n{_THE}"
        assert tags_of(text) == [("p",), ("p", "br"), ("p", "br")], line


# ---- #922: a date line after a long title line ---------------------------------------------


@pytest.mark.parametrize(
    ("title", "date", "body"),
    [
        ("Jahresbericht der Deutschen Gesellschaft für Akustik", "Oktober 2020", _DIE),
        ("JAHRESBERICHT DER GESELLSCHAFT FÜR AKUSTIK UND SPRACHE", "Oktober 2020", _DIE),
        ("Max Mustermann und Erika Musterfrau, Institut für Akustik Berlin", "Mai 2021", _DIE),
        ("A Study of Reading Scientific Papers Aloud on Phones", "April 2020", _THE),
    ],
    ids=["jahresbericht", "capitals", "authors", "english"],
)
def test_a_date_line_after_a_long_title_line_is_a_block_of_its_own(
    title: str, date: str, body: str
) -> None:
    """A title or author line longer than `TITLE_SHARE` of the longest line, ending in a
    word that is no preposition, article or ordinal, before a date: title, date and body
    are three blocks (#922)."""
    assert len(title) > 0.6 * len(body.strip())
    assert tags_of(f"{title}\n{date}\n{body}") == [("p",), ("p",), ("p",)]


def test_a_long_word_before_a_date_line_is_read_in_linear_time() -> None:
    """ "AAAA...A." / "June 2020" / "The ...": the last word of the line before a date is
    found in time linear in the line, whatever its end (#922)."""

    def sized(size: int) -> str:
        return f"{'A' * size}.\nJune 2020\n{_THE}"

    assert_linear(lambda text: read(text.encode()), sized, 160_000)


@pytest.mark.parametrize(
    ("lines", "tags"),
    [
        (
            [
                "All the forms for the second round of the study must be sent in no later than",
                "June 2020",
                "and will then be read by the board of the society in the order they came.",
            ],
            "pbb",
        ),
        (
            [
                "All the forms for the second round of the study must be sent in no later than",
                "June 2020.",
                "The board of the society will then read them in the order they came in.",
            ],
            "pbb",
        ),
        (
            [
                "The board has now read the second report of the society, dated",
                "June 2020.",
                "The board of the society will then read them in the order they came in.",
            ],
            "pbb",
        ),
        (
            [
                "Readers who want to take part in the second round can apply starting",
                "June 2020.",
                "Every chapter of the study is then read aloud by two of the voices.",
            ],
            "pbb",
        ),
        (
            [
                "The first version of the reading tool for phones was finally released",
                "April 2020.",
                "The second version followed half a year later with many more voices.",
            ],
            "pbb",
        ),
        (
            [
                "Die Zahlen in der Tabelle dieses Berichts zeigen den letzten Stand",
                "Oktober 2020.",
                "Die Erhebung lief danach noch eine ganze Weile weiter, bis zum Ende.",
            ],
            "pbb",
        ),
        (
            [
                "Die Zahlen in der Tabelle dieses Berichts zeigen den letzten Stand",
                "Mai 2021.",
                "Die Erhebung lief danach noch eine ganze Weile weiter, bis zum Ende.",
            ],
            "pbb",
        ),
        (
            [
                "Der zweite Bericht der Gesellschaft soll vorliegen bis spätestens",
                "Oktober 2020.",
                "Dann liest der Vorstand alle Berichte in der Reihenfolge ihres Eingangs.",
            ],
            "pbb",
        ),
        (
            [
                "Die Zahlen in der Tabelle dieses Berichts geben den Stand",
                "Oktober 2020",
                "wieder und werden im nächsten Jahr durch neue Zahlen ersetzt.",
            ],
            "pbb",
        ),
    ],
    ids=[
        "no-later-than",
        "no-later-than-stop",
        "dated-stop",
        "starting-stop",
        "released-stop",
        "letzten-stand-oktober",
        "letzten-stand-mai",
        "spaetestens-stop",
        "stand-lower-case",
    ],
)
def test_a_date_line_ending_a_sentence_or_before_lower_case_stays_in_it(
    lines: list[str], tags: str
) -> None:
    """A date after a word that leads into no date stays in its sentence when the date line
    ends in a stop or the line after it starts in lower case, as before #922: only a date
    line without a stop before a capital is a block of its own after a title line."""
    expected = [("p",) if t == "p" else ("p", "br") for t in tags]
    assert tags_of("\n".join(lines) + "\n") == expected


def tags_read(tags: str) -> list[tuple[str, ...]]:
    """Tags from letters: ``p`` a new paragraph, ``b`` a line joined to the one before; a
    space between paragraphs is for reading only."""
    return [("p",) if t == "p" else ("p", "br") for t in tags.replace(" ", "")]


# ---- #942: a long title line inside a paragraph, a long date line, NFD text ---------------


@pytest.mark.parametrize(
    "text",
    [
        "The first part of the note ends here, as the data show us all.\n"
        "Results\n"
        "The data show that the readers liked it a lot, and more besides.\n"
        "\n"
        "The second part of the note ends here, as noted before, and that is it.\n"
        "The report was then sent on to the board of the Society\n"
        "June 2020\n"
        "The board read it twice and then sent it back with many notes, as usual.\n",
        "Der erste Teil des Berichts endet hier, wie die Daten uns allen zeigen.\n"
        "Ergebnisse\n"
        "Die Daten zeigen, dass die Leser ihn mochten, und noch mehr als das.\n"
        "\n"
        "Der zweite Teil des Berichts endet hier, wie schon gesagt, und das war es.\n"
        "Der Bericht ging danach an den Vorstand der Gesellschaft\n"
        "Oktober 2020\n"
        "Der Vorstand las ihn zweimal und schickte ihn mit vielen Notizen zurueck.\n",
    ],
    ids=["english", "german"],
)
def test_a_long_title_line_inside_a_paragraph_is_no_mixed_case_heading(text: str) -> None:
    """A long line ending in a plain word before a date, after a sentence end inside a
    paragraph, stays in that paragraph and does not count toward the two mixed-case
    headings a document needs (#812), so the lone "Results" stays a wrapped line; the date
    joins the line before it and the next sentence starts after it (#942)."""
    assert tags_of(text) == tags_read("pbp pbbp")


@pytest.mark.parametrize(
    ("title", "date", "tags"),
    [
        ("Reading Papers Aloud", "September 2020", "pbb"),
        ("Reading Scientific Papers Aloud", "May 2020", "ppp"),
    ],
    ids=["long-date", "short-date"],
)
def test_a_date_line_after_a_title_is_cut_before_only_when_it_is_short(
    title: str, date: str, tags: str
) -> None:
    """In a paragraph whose longest line is its title, a date line as long as a title is
    no date of its own: it is never cut from the title and then joined to the body (#942).
    A short date line is cut before and after (#922)."""
    assert tags_of(f"{title}\n{date}\nThe End\n") == tags_read(tags)


@pytest.mark.parametrize(
    ("lines", "tags"),
    [
        (
            [
                "A Study of Reading Scientific Papers Aloud on Phones and",
                "Tablets in the Train, the Bus, the Car and on Foot at Home",
                "June 2020",
                _THE.strip(),
            ],
            "pbpp",
        ),
        (
            [
                "Jahresbericht der Deutschen Gesellschaft für Akustik und",
                "Sprache sowie für das Hören von Fachtexten unterwegs",
                "Oktober 2020",
                _DIE.strip(),
            ],
            "pbpp",
        ),
        (
            [
                "Reading Papers Aloud",
                "Jane Smith, John Brown and Erika Mustermann of the Society",
                "Institute for Acoustics and Speech, University of Somewhere",
                "June 2020",
                _THE.strip(),
            ],
            "ppbpp",
        ),
        (
            [
                "Vorlesen von Fachtexten",
                "Erika Mustermann, Max Mustermann und Anna Beispiel vom Verein",
                "Institut für Akustik und Sprache, Universität Musterstadt",
                "Oktober 2020",
                _DIE.strip(),
            ],
            "ppbpp",
        ),
        (
            [
                "A Study of Reading Scientific Papers Aloud on Phones",
                "Jane Smith, John Brown and Erika Mustermann, Society",
                "June 2020",
                _THE.strip(),
            ],
            "pbpp",
        ),
        (
            [
                "Jahresbericht der Deutschen Gesellschaft für Akustik",
                "Erika Mustermann und Max Mustermann, Institut Berlin",
                "Oktober 2020",
                _DIE.strip(),
            ],
            "pbpp",
        ),
    ],
    ids=[
        "wrapped-title",
        "wrapped-title-de",
        "title-authors-affiliation",
        "title-authors-affiliation-de",
        "title-authors",
        "title-authors-de",
    ],
)
def test_a_title_block_wrapped_over_long_lines_keeps_the_cut_before_its_date(
    lines: list[str], tags: str
) -> None:
    """A title or author block wrapped over two long lines, none of them ending a sentence,
    is still a title block: its date is cut before and after (#922). Only a long line after
    a sentence end inside a paragraph is prose (#942)."""
    assert all(len(line) > 0.6 * len(lines[-1]) for line in lines[-4:-2])
    assert tags_of("\n".join(lines) + "\n") == tags_read(tags)


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        (
            "Der Bericht der Gesellschaft wurde fertig, wie geplant während\n"
            "Oktober 2020\n"
            "Die Leser haben ihn dann gelesen und an den Vorstand weitergegeben.\n",
            "pbb",
        ),
        (
            "Die Zahlen in der Tabelle dieses Berichts gelten bis zum nächsten\n"
            "März 2021\n"
            "Die Leser haben ihn dann gelesen und an den Vorstand weitergegeben.\n",
            "pbb",
        ),
        (
            "Die Konferenz fand in diesem Jahr in Berlin statt, und zwar am 3.\n"
            "MÄRZ\n"
            "2021 kamen die Teilnehmer aus ganz Europa zusammen und blieben da.\n",
            "pbb",
        ),
        (
            "Gemeint sind Bücher, Aufsätze, Berichte, Vorträge, Hefte o. ä.\n"
            "Überblick\n"
            "Über die Jahre kamen viele Teilnehmer aus ganz Europa zusammen.\n"
            "\n"
            "Gemeint sind Bücher, Aufsätze, Berichte, Vorträge, Hefte u. Ä.\n"
            "Überblick\n"
            "Über die Jahre kamen viele Teilnehmer aus ganz Europa zusammen.\n",
            "pbp pbp",
        ),
    ],
    ids=["waehrend", "naechsten-maerz", "am-3-maerz", "o-ae"],
)
def test_nfd_text_gets_the_tags_of_nfc_text(text: str, tags: str) -> None:
    """Umlauts written as a letter and a combining mark (NFD, as macOS file names and some
    editors write them) read as the composed letters do: "während" and "nächsten" lead into
    a date, "März" and "MÄRZ" are months, "o. ä." is an abbreviation (#942). The text is
    kept as stored."""
    nfd = unicodedata.normalize("NFD", text)
    assert nfd != text
    assert tags_of(text) == tags_read(tags)
    assert tags_of(nfd) == tags_read(tags)
    assert [line for line, _ in lines(read(nfd.encode()))] == [
        line for line in nfd.splitlines() if line
    ]


_VOCABULARY = (
    *("während", "nächsten", "März", "MÄRZ", "Mai", "Oktober", "OKTOBER", "Jänner", "June"),
    *("Übersicht", "Ärger", "ÜBER", "für", "Größe", "o. ä.", "u. Ä.", "am 3.", "2020", "Die"),
    *("the", "in", "of", "Results", "Ergebnisse", "über", "schön", "zurück", "Straße", "."),
)


@given(
    st.lists(
        st.lists(
            st.lists(st.sampled_from(_VOCABULARY), min_size=1, max_size=14).map(" ".join),
            min_size=1,
            max_size=6,
        ),
        min_size=1,
        max_size=4,
    )
)
def test_nfd_and_nfc_text_always_get_the_same_tags(written: list[list[str]]) -> None:
    """Whatever the lines, the composed and the decomposed spelling of a text get the same
    tags (#942)."""
    text = "\n\n".join("\n".join(paragraph) for paragraph in written) + "\n"
    assert tags_of(unicodedata.normalize("NFD", text)) == tags_of(text)


# ---- #930: capitals month lines after a title, dates in references, a lone "May" ----------

_GERMAN_MONTHS = (
    *("JANUAR", "FEBRUAR", "MÄRZ", "APRIL", "MAI", "JUNI", "JULI", "AUGUST"),
    *("SEPTEMBER", "OKTOBER", "NOVEMBER", "DEZEMBER"),
)
_MARKED = "2020 marked a turning point for the society and its many members, as we see.\n"
_WAR = "2020 war ein Wendepunkt für die Gesellschaft und ihre vielen Mitglieder, wie man sieht.\n"


@pytest.mark.parametrize(
    "title",
    ["ANNUAL REPORT", "Annual Report", "A STUDY OF READING SCIENTIFIC PAPERS ALOUD ON PHONES"],
    ids=["capitals", "mixed", "long"],
)
@pytest.mark.parametrize("month", [m.upper() for m in _ENGLISH_MONTHS])
def test_an_english_capitals_month_line_after_a_title_keeps_both_cuts(
    title: str, month: str
) -> None:
    """ "ANNUAL REPORT" / "JUNE" / "2020 marked ...": the month is the title block's date,
    cut from the title and from the body, for every month (#930). Inside a running sentence
    ("am 3." / "OKTOBER" / "2020 kamen ...") it still runs on (#893)."""
    assert tags_of(f"{title}\n{month}\n{_MARKED}") == tags_read("ppp")


@pytest.mark.parametrize(
    "title",
    ["JAHRESBERICHT", "Jahresbericht", "JAHRESBERICHT DER GESELLSCHAFT FÜR AKUSTIK UND SPRACHE"],
    ids=["capitals", "mixed", "long"],
)
@pytest.mark.parametrize("month", _GERMAN_MONTHS)
def test_a_german_capitals_month_line_after_a_title_keeps_both_cuts(title: str, month: str) -> None:
    """ "JAHRESBERICHT" / "OKTOBER" / "2020 war ...": as in English (#930)."""
    assert tags_of(f"{title}\n{month}\n{_WAR}") == tags_read("ppp")


@pytest.mark.parametrize(
    "text",
    [
        "The first version of the reading tool for phones was finally released\n"
        "June 2020\n"
        "The second part of the study followed half a year later with more voices.\n",
        "Der erste Bericht der Gesellschaft wurde im Herbst endlich veröffentlicht\n"
        "Oktober 2020\n"
        "Die zweite Fassung folgte ein halbes Jahr später mit vielen neuen Stimmen.\n",
    ],
    ids=["released", "veroeffentlicht"],
)
def test_a_date_after_a_verb_opening_a_paragraph_is_a_block_of_its_own(text: str) -> None:
    """The trade-off of #922, pinned (#930): a paragraph's long first line ending in a verb
    before a date and a capital reads as a title before its date, three blocks. Nothing in
    the line's last word tells "released" from a title's last noun, and a title and date
    opening a paragraph is the more common of the two. A date that ends its sentence with a
    stop, or goes on in lower case, stays in it (#922)."""
    assert tags_of(text) == tags_read("ppp")


@pytest.mark.parametrize(
    "text",
    [
        "Smith, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics\n"
        "June 2020\n"
        "Brown, B. and Green, G. Another study of listening to papers. Journal of Sound\n",
        "Mustermann, M. und Musterfrau, E. Vorlesen von Aufsätzen. Zeitschrift für Akustik\n"
        "Oktober 2020\n"
        "Beispiel, B. und Muster, M. Hören von Fachtexten unterwegs. Zeitschrift für Klang\n",
    ],
    ids=["english", "german"],
)
def test_a_date_inside_a_wrapped_reference_joins_its_entry(text: str) -> None:
    """A reference entry ("Smith, J. ...") wrapped before its date is no title: the date
    joins the entry, and the next entry starts a block (#930)."""
    assert tags_of(text) == tags_read("pbp")


def test_a_date_inside_a_numbered_reference_joins_its_entry() -> None:
    """ "[1] ..." and "1. Smith, J. ..." entries are no titles either (#930). Numbered
    entries that count up are list items (#466), the date inside the first one."""
    brackets = (
        "[1] J. Smith and K. Jones, A study of reading papers aloud, Journal of Acoustics\n"
        "June 2020\n"
        "The board of the society will then read them in the order they came in.\n"
    )
    assert tags_of(brackets)[:2] == tags_read("pb")
    numbered = (
        "1. Smith, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics\n"
        "June 2020\n"
        "2. Brown, B. and Green, G. Another study of listening to papers. Journal of Sound\n"
    )
    item = ("ol", "li")
    assert tags_of(numbered) == [item, (*item, "br"), item]


def test_dates_in_a_list_of_references_join_their_entries() -> None:
    """Entry after entry, each date stays with the entry before it (#930)."""
    text = (
        "Smith, J. and Jones, K. A study of reading scientific papers aloud on phones and\n"
        "tablets in the train, the bus and the car, in the Journal of Applied Acoustics\n"
        "June 2020\n"
        "Brown, B. and Green, G. Another study of listening to papers. Journal of Sound\n"
        "May 2021\n"
        "White, W. A third study of listening to papers on the way home. Journal of Ears\n"
    )
    assert tags_of(text) == tags_read("pbbpbp")


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        (
            "This chapter is written for all of those who listen on the go\n"
            "May\n"
            "Skip a chapter if you like, and come back to it later on when you can.\n",
            "pbp",
        ),
        (
            "A Study of Reading Scientific Papers Aloud on Phones\n"
            "June\n"
            "The second part starts on this line and runs on for a while here.\n",
            "pbp",
        ),
        (
            "Der Bericht der Gesellschaft erschien nach langer Arbeit dann\n"
            "Mai\n"
            "Die Leser haben ihn dann gelesen und an den Vorstand weitergegeben.\n",
            "pbb",
        ),
    ],
    ids=["may", "june", "mai"],
)
def test_a_lone_month_word_after_a_plain_word_reads_as_before_922(text: str, tags: str) -> None:
    """A month word without a year after a line ending in a word that leads into no date,
    before a capital, reads as before #903 and #922: the modal "May" is no date (#930). A
    lone English month is any short line, cut before the capital after it; a lone German
    month (and April, August, September, November, spelled alike) runs on as in #893."""
    assert tags_of(text) == tags_read(tags)


@pytest.mark.parametrize("month", ["MAY", "JUNE", "MAI", "OKTOBER"])
def test_a_lone_month_in_capitals_after_a_long_title_is_its_date(month: str) -> None:
    """A month in capitals is no modal verb: after a long title before a capital it is the
    title's date, cut before and after, as before a number (#922, #930)."""
    text = f"A Study of Reading Scientific Papers Aloud on Phones\n{month}\n{_THE}"
    assert tags_of(text) == tags_read("ppp")


def test_a_long_reference_or_title_line_before_a_date_is_read_in_linear_time() -> None:
    """ "Smithaaa...a" / "JUNE" / "2020 ...": the reference and title checks on the line
    before a date take time linear in the line (#930)."""

    def sized(size: int) -> str:
        return f"Smith{'a' * size}\nJUNE\n{_MARKED}"

    assert_linear(lambda text: read(text.encode()), sized, 160_000)


# ---- #947: dates in reference lists of every style; #908: a month line after a colon ------

# Two entries of each style, each long enough to be wrapped before its date (#947)
_STYLES = {
    "vancouver": (
        "Smith J, Jones K. A study of reading papers aloud. Journal of Acoustics",
        "Brown B, Green G. Another study of listening to papers. Journal of Sound",
    ),
    "vancouver-initials": (
        "Smith JA, Jones KB. A study of reading papers aloud. Journal of Acoustics",
        "Brown BC, Green G. Another study of listening to papers. Journal of Sound",
    ),
    "chicago": (
        "Smith, John, and Kate Jones. A Study of Reading Papers Aloud. Journal of Acoustics",
        "Brown, Bob, and Gail Green. Another Study of Listening to Papers. Journal of Sound",
    ),
    "chicago-middle": (
        "Smith, John A., and Kate Jones. A Study of Reading Papers Aloud. Journal of Acoustics",
        "Brown, Bob C., and Gail Green. Another Study of Listening. Journal of Sound",
    ),
    "apa": (
        "Smith, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics",
        "Brown, B. and Green, G. Another study of listening to papers. Journal of Sound",
    ),
    "numbered": (
        "[1] J. Smith and K. Jones, A study of reading papers aloud, Journal of Acoustics",
        "[2] B. Brown and G. Green, Another study of listening to papers, Journal of Sound",
    ),
    "von": (
        "von Neumann, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics",
        "von Braun, B. and Green, G. Another study of listening to papers. Journal of Sound",
    ),
    "van-der": (
        "van der Berg, A. and Jones, K. A study of reading papers aloud. Journal of Acoustics",
        "van den Bosch, B. and Green, G. Another study of listening. Journal of Sound",
    ),
    "de": (
        "de Souza, M. and Jones, K. A study of reading papers aloud. Journal of Acoustics",
        "de la Cruz, B. and Green, G. Another study of listening. Journal of Sound",
    ),
    "german": (
        "Mustermann, M. und Musterfrau, E. Vorlesen von Aufsätzen. Zeitschrift für Akustik",
        "Beispiel, B. und Muster, M. Hören von Fachtexten unterwegs. Zeitschrift für Klang",
    ),
}


@pytest.mark.parametrize("style", list(_STYLES))
def test_a_date_in_a_reference_entry_of_any_style_joins_its_entry(style: str) -> None:
    """Vancouver ("Smith J,"), Chicago ("Smith, John,"), APA ("Smith, J."), numbered ("[1]")
    and surnames with a particle ("von Neumann, J.", "van der Berg, A.", "de Souza, M."): an
    entry wrapped before its date is no title, the date stays in its entry, and the next
    entry starts a block (#947)."""
    first, second = _STYLES[style]
    month = "Oktober 2020" if style == "german" else "June 2020"
    for date in (month, month.upper()):
        assert tags_of(f"{first}\n{date}\n{second}\n") == tags_read("pbp"), date
        listed = f"{first}\n{date}\n{second}\n{date}\n{first}\n"
        assert tags_of(listed) == tags_read("pbpbp"), date


@pytest.mark.parametrize("style", ["apa", "numbered", "vancouver", "chicago", "von"])
def test_a_short_wrapped_reference_line_before_its_date_stays_in_its_entry(style: str) -> None:
    """ "... on phones and tablets in the" / "train. Journal of Acoustics" / "June 2020": the
    short last line of an entry is no title before its date; both stay in the entry (#947)."""
    first, second = _STYLES[style]
    authors = first.split(" A s")[0].split(" A S")[0]
    text = (
        f"{authors} A study of reading scientific papers aloud on phones and tablets in the\n"
        "train. Journal of Acoustics\n"
        "June 2020\n"
        f"{second}\n"
    )
    assert tags_of(text) == tags_read("pbbp")


@pytest.mark.parametrize("abbreviation", ["z. B.", "d. h.", "u. a.", "z.B."])
def test_a_german_abbreviation_after_a_comma_starts_no_reference(abbreviation: str) -> None:
    """ "Beispiele, z. B. das ..." is no "Smith, J." entry: an initial is a capital. The
    line is a title before its date, cut before and after as #922 asks (#947)."""
    text = (
        f"Beispiele, {abbreviation} das Vorlesen von Fachtexten auf Telefonen und Tablets\n"
        "Oktober 2020\n"
        "Der Vorstand las ihn zweimal und schickte ihn mit vielen Notizen zurück, wie immer.\n"
    )
    assert tags_of(text) == tags_read("ppp")


_BOARD = "The board read it twice and then sent it back with many notes, as usual here.\n"
_VORSTAND = "Der Vorstand las ihn zweimal und schickte ihn mit vielen Notizen zurück, wie immer.\n"


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        (
            "Guns, Germs, and Steel: The Fates of Human Societies in the Long Run\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (f"Guns, Germs, and Steel\nJune 2020\n{_BOARD}", "ppp"),
        (
            "Reading, Writing, and Listening: A Study of Papers Read Aloud on Phones\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (
            "Kinder, Eltern, Lehrer: Eine Studie über das Vorlesen von Fachtexten\n"
            f"Oktober 2020\n{_VORSTAND}",
            "ppp",
        ),
        (
            "zum Beispiel, Kinder, Eltern und Lehrer: Eine Studie über das Vorlesen\n"
            f"Oktober 2020\n{_VORSTAND}",
            "ppp",
        ),
        (
            "The US, China and Europe: Research on Reading Papers Aloud at Home\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (
            "Die EU, China und die USA: Handel und Forschung im Wandel der Zeit\n"
            f"Oktober 2020\n{_VORSTAND}",
            "ppp",
        ),
        (
            "Guns, Germs, and Steel: The Fates of Human Societies in the\n"
            "Long Run of History, from the First Farmers to the Present Day\n"
            f"June 2020\n{_BOARD}",
            "pbpp",
        ),
        (
            "Reading Papers Aloud\n"
            "Smith, Jane, and John Doe, Department of Acoustics, Example University\n"
            f"June 2020\n{_BOARD}",
            "pppp",
        ),
    ],
    ids=[
        "guns-long",
        "guns-short",
        "reading-writing",
        "kinder-eltern",
        "zum-beispiel",
        "the-us",
        "die-eu",
        "guns-wrapped",
        "title-authors",
    ],
)
def test_a_title_shaped_like_a_chicago_or_vancouver_entry_keeps_its_date_apart(
    text: str, tags: str
) -> None:
    """ "Guns, Germs, and Steel: ..." or "The US, China ...": a line shaped like a Chicago
    ("Smith, John,") or Vancouver ("Smith JA,") entry is a reference only in context: when an
    entry opened an earlier block of the paragraph, or the line after the date starts an
    entry too. Before a date and prose it is a title, read as on main (#922, #947)."""
    assert tags_of(text) == tags_read(tags)


def test_washington_dc_reads_as_a_reference_entry() -> None:
    """A known limit, pinned (#947): "Washington, D.C." has the shape of an author with two
    initials ("Washington, D. C."), so the line is read as a reference entry and its date
    joins it. Nothing in the line tells the city from the author."""
    text = (
        "Washington, D.C. Annual Report of the Society of Acoustics and Speech\n"
        "June 2020\n"
        "The board read it twice and then sent it back with many notes, as usual here.\n"
    )
    assert tags_of(text) == tags_read("pbp")


def test_a_title_wrapped_in_a_bullet_item_keeps_its_date_apart() -> None:
    """ "- A Study ... Phones and" / "  Tablets ..." / "June 2020" / body: a list item heads
    its block as a paragraph's first line does, so the date after its wrapped title is cut
    before and after, as before #946 (#947)."""
    text = (
        "- A Study of Reading Scientific Papers Aloud on Phones and\n"
        "  Tablets in the Train, the Bus, the Car and on Foot at Home\n"
        "June 2020\n"
        "The board read it twice and then sent it back with many notes, as usual here.\n"
    )
    item = ("ul", "li")
    assert tags_of(text) == [item, (*item, "br"), ("p",), ("p",)]


@pytest.mark.parametrize(
    ("line", "month", "after"),
    [
        (
            "Die Termine der Sitzungen des Vorstands im kommenden Jahr waren die folgenden:",
            "Oktober 2020",
            "Die Sitzung fand im grossen Saal statt und dauerte bis spät in die Nacht.",
        ),
        (
            "Die Termine der Sitzungen des Vorstands im kommenden Jahr waren die folgenden:",
            "Oktober",
            "Die Sitzung fand im grossen Saal statt und dauerte bis spät in die Nacht.",
        ),
        (
            "The dates of the meetings of the board in the coming year were these:",
            "June 2020",
            "The board read it twice and then sent it back with many notes, as usual here.",
        ),
    ],
    ids=["oktober-2020", "oktober", "june-2020"],
)
def test_a_month_line_after_a_colon_keeps_its_cut_after_it(
    line: str, month: str, after: str
) -> None:
    """ "... die folgenden:" / "Oktober 2020" / "Die ...": after a colon a month line is a
    list item or a heading, not the rest of a running sentence, so the line after it starts
    a block (#908)."""
    assert tags_of(f"{line}\n{month}\n{after}\n") == tags_read("pbp")


def test_the_reference_checks_take_linear_time() -> None:
    """Particles, a long surname, a long initial and a long bracket number, each on a line
    before or after a date: the reference checks take time linear in the lines (#947)."""

    def sized(size: int) -> str:
        name = "von " * (size // 8) + "Smith" + "a" * (size // 2)
        return (
            f"{name}\nJune 2020\n{name}, J{'a' * size}\nJune 2020\n[{'1' * size}\n"
            f"Smith {'A' * size}\nJune 2020\nSmith, J{'a' * size} J.,\nJune\n"
        )

    assert_linear(lambda text: read(text.encode()), sized, 160_000)


# ---- #981: more reference shapes; titles shaped like entries read as before #947 ----------

# An entry whose last line ends in a comma, a semicolon, a number, a bracket or a lead word
_RUN_ON_ENTRIES = {
    "numbered-comma": (
        "[1] J. Smith and K. Jones, A study of reading papers aloud, J. Acoust., pp. 1-9,",
        "[2] B. Brown and G. Green, Another study of listening to papers, Journal of Sound",
    ),
    "vancouver-semicolon": (
        "Smith J, Jones K. A study of reading papers aloud. J Acoust. 2020;1:1-9;",
        "Brown B, Green G. Another study of listening to papers. Journal of Sound",
    ),
    "apa-number": (
        "Smith, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics, 1",
        "Brown, B. and Green, G. Another study of listening to papers. Journal of Sound",
    ),
    "chicago-bracket": (
        "Smith, John, and Kate Jones. A Study of Reading Papers Aloud. Journal of Acoustics (1)",
        "Brown, Bob, and Gail Green. Another Study of Listening. Journal of Sound",
    ),
    "numbered-lead-word": (
        "[1] J. Smith and K. Jones, A study of reading papers aloud, published in",
        "[2] B. Brown and G. Green, Another study of listening to papers, Journal of Sound",
    ),
}


@pytest.mark.parametrize("style", list(_RUN_ON_ENTRIES))
def test_a_date_ends_its_entry_whatever_the_entry_ends_in(style: str) -> None:
    """ "[1] ... pp. 1-9," / "June 2020" / "[2] ...": the date runs on from the entry's last
    line, and still the next entry starts a block, as after an entry ending in a word (#981)."""
    first, second = _RUN_ON_ENTRIES[style]
    for date in ("June 2020", "JUNE 2020"):
        assert tags_of(f"{first}\n{date}\n{second}\n") == tags_read("pbp"), date
        listed = f"{first}\n{date}\n{second}\n{date}\n{first}\n"
        assert tags_of(listed) == tags_read("pbpbp"), date


@pytest.mark.parametrize("style", ["vancouver", "chicago", "apa", "numbered", "von", "german"])
def test_a_date_with_a_full_stop_ends_its_entry(style: str) -> None:
    """ "... Journal of Acoustics" / "June 2020." / "Brown, B. ...": a date that ends in a
    stop stays in its entry, and the next entry starts a block (#981)."""
    first, second = _STYLES[style]
    month = "Oktober 2020." if style == "german" else "June 2020."
    assert tags_of(f"{first}\n{month}\n{second}\n") == tags_read("pbp")


def test_a_date_with_a_full_stop_in_prose_stays_in_its_sentence() -> None:
    """Outside a reference list a date ending in a stop ends the sentence it is in (#922)."""
    text = f"The board met once more to read the papers that came in during\nJune 2020.\n{_BOARD}"
    assert tags_of(text) == tags_read("pbb")


_MORE_STYLES = {
    "initials-first": (
        "J. Smith and K. Jones, A study of reading papers aloud, Journal of Acoustics",
        "B. Brown and G. Green, Another study of listening to papers, Journal of Sound",
    ),
    "initials-first-three": (
        "J. A. Smith, K. Jones, and L. Li, A study of reading papers aloud, Journal of Acoustics",
        "B. Brown, G. Green, and W. White, Another study of listening, Journal of Sound",
    ),
    "capitalised-particle": (
        "De Souza, M. and Jones, K. A study of reading papers aloud. Journal of Acoustics",
        "Van Gogh, V. and Green, G. Another study of listening to papers. Journal of Sound",
    ),
    "capitalised-particle-vancouver": (
        "De Souza M, Jones K. A study of reading papers aloud. Journal of Acoustics",
        "Van Gogh V, Green G. Another study of listening to papers. Journal of Sound",
    ),
    "vancouver-et-al": (
        "Smith J, Jones K, et al. A study of reading papers aloud. Journal of Acoustics",
        "Brown B, Green G, et al. Another study of listening. Journal of Sound",
    ),
}


@pytest.mark.parametrize("style", list(_MORE_STYLES))
def test_initials_first_and_capitalised_particle_entries_keep_their_dates(style: str) -> None:
    """Initials before the surname ("J. Smith and K. Jones, ...") and a capitalised particle
    ("De Souza, M.", "Van Gogh V,"): the date stays in its entry and the next entry starts a
    block, as in the styles of #947 (#981)."""
    first, second = _MORE_STYLES[style]
    for date in ("June 2020", "JUNE 2020", "June 2020."):
        assert tags_of(f"{first}\n{date}\n{second}\n") == tags_read("pbp"), date
        listed = f"{first}\n{date}\n{second}\n{date}\n{first}\n"
        assert tags_of(listed) == tags_read("pbpbp"), date


@pytest.mark.parametrize(
    "second",
    [
        "Brown, Bob. Another Study of Listening to Papers. Journal of Sound",
        "Brown, Bob K. Another Study of Listening to Papers. Journal of Sound",
        "B. Brown, Another study of listening to papers, Journal of Sound",
    ],
    ids=["chicago", "chicago-middle", "initials-first"],
)
def test_a_single_author_entry_in_a_list_keeps_its_date(second: str) -> None:
    """One Chicago author ("Brown, Bob. ...") or one initials-first author ("B. Brown, ...")
    in a list that an APA entry opened: the date stays in its entry (#981)."""
    first = "Smith, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics"
    text = f"{first}\nJune 2020\n{second}\nJune 2020\n{first}\n"
    assert tags_of(text) == tags_read("pbpbp")


@pytest.mark.parametrize(
    "first",
    [
        "Smith, John. A Study of Reading Papers Aloud on the Train. Journal of Acoustics",
        "J. Smith, A Study of Reading Papers Aloud on the Train, Journal of Acoustics",
    ],
    ids=["chicago", "initials-first"],
)
def test_a_lone_single_author_entry_before_its_date_reads_as_a_title(first: str) -> None:
    """A known limit, pinned (#981): one Chicago or initials-first author has the shape of
    a title ("Yes, Sir. ...", "A. Lincoln, The Man"), so two such entries alone read as a
    title, its date and the text after it, as on main. In a list they are entries."""
    second = "Brown, Bob. Another Study of Listening to Papers. Journal of Sound"
    assert tags_of(f"{first}\nJune 2020\n{second}\n") == tags_read("ppp")


@pytest.mark.parametrize(
    "entry",
    [
        "Smith, J. A study of reading papers aloud on the train and the bus. Journal of",
        "[1] J. Smith, A study of reading papers aloud on the train and the bus, in",
    ],
    ids=["apa", "numbered"],
)
def test_a_capitals_date_ending_an_entry_is_cut_from_a_numbered_line(entry: str) -> None:
    """ "Journal of Sound" / "DECEMBER 2025" / "1. While ...": the date stays in its entry
    (#947), and the numbered line after it starts a block, as before #947 (#981)."""
    text = (
        f"{entry}\nJournal of Sound\nDECEMBER 2025\n"
        "1. While the board read it, nothing changed at all.\n"
    )
    assert tags_of(text) == tags_read("pbbp")


@pytest.mark.parametrize(
    ("month", "after"),
    [("JUNE", "2020, 12(3), 1-9."), ("DECEMBER 2025", "12(3), 1-9.")],
    ids=["month-before-year", "date-before-volume"],
)
def test_a_capitals_month_in_an_entry_runs_on_into_its_year(month: str, after: str) -> None:
    """ "Journal of Sound" / "JUNE" / "2020, 12(3), 1-9.": only a numbered line is cut
    from a capitals date that ends an entry; a year or a volume stays in it, as on main
    (#981)."""
    entry = "Smith, J. A study of reading papers aloud on the train and the bus. Journal of"
    assert tags_of(f"{entry}\nJournal of Sound\n{month}\n{after}\n") == tags_read("pbbb")


_APA_FIRST = "Smith, J. and Jones, K. A study of reading papers aloud. Journal of Acoustics"
_APA_SECOND = "Brown, B. and Green, G. Another study of listening to papers. Journal of Sound"


@pytest.mark.parametrize(
    "text",
    [
        f"{_APA_FIRST}\nJune 2020\n{_APA_SECOND}\nJune 2020.\n"
        "Brown, Bob. Another Study of Listening to Papers. Journal of Sound\n",
        "Smith, John, and Kate Jones. A Study of Reading Papers Aloud. Journal of Acoustics\n"
        "June 2020\n"
        "White, Walt, and Kim Black. A Third Study of Papers. Journal of Speech\n"
        "June 2020.\n"
        "Brown, Bob. Another Study of Listening to Papers. Journal of Sound\n",
        f"{_APA_FIRST}\nJune 2020\n"
        "Brown, Bob. Another Study of Listening to Papers. Journal of Sound, 1-9,\n"
        f"June 2020\n{_APA_SECOND}\n",
        f"{_APA_FIRST}\nJune 2020\n"
        "Brown, B. and Green, G. Another study of listening. Journal of Sound, 1-9,\n"
        "June 2020\nB. Brown, Another study of listening to papers, Journal of Sound\n",
    ],
    ids=["stop-before-chicago", "chicago-list-stop", "chicago-comma", "comma-before-initials"],
)
def test_a_single_author_entry_in_a_list_ends_at_its_date(text: str) -> None:
    """In a list of entries, a date after a stop or an entry ending in a comma ends its
    entry before one Chicago or initials-first author too, and such an entry ends at its
    own date: any entry shape counts on both sides of the date once the paragraph is a list
    (#981)."""
    assert tags_of(text) == tags_read("pbpbp")


@pytest.mark.parametrize(
    "entry",
    [_APA_FIRST, "[1] J. Smith and K. Jones, A study of reading papers aloud, Journal of Sound"],
    ids=["apa", "numbered"],
)
def test_a_title_right_after_an_entry_reads_as_the_entry_s_last_line(entry: str) -> None:
    """A known limit, pinned (#947, #981): a short title line right after an entry, with no
    blank line, has the shape of the entry's wrapped last line ("... Journal of" / "Speech,
    Language, and Hearing" / "June 2020"), so the date joins it. Before #947 it was cut
    (``pbpp``)."""
    text = f"{entry}\nReading Papers Aloud\nJune 2020\n{_BOARD}"
    assert tags_of(text) == tags_read("pbbp")


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        # a title, its date and a sentence that opens like an entry (#981, lead's comment)
        (
            "The US, China and Europe: Research on Reading Papers Aloud at Home\n"
            "June 2020\n"
            "Using AI, we read papers aloud to the board, and the board read them twice.\n",
            "ppp",
        ),
        (
            "Guns, Germs, and Steel: The Fates of Human Societies in the Long Run\n"
            "June 2020\n"
            "Today, Europe, China and the US read papers aloud, as the board noted here.\n",
            "ppp",
        ),
        (
            "Guns, Germs, and Steel\n"
            "June 2020\n"
            "Using AI, we read papers aloud to the board, and the board read them twice.\n",
            "ppp",
        ),
        # a title and its subtitle of the same shape
        (f"The US, China and Europe\nPart II. Trade and Research\nJune 2020\n{_BOARD}", "pppp"),
        (f"Guns, Germs, and Steel\nDiamond, Jared, and Others\nJune 2020\n{_BOARD}", "pppp"),
        (
            f"Kinder, Eltern, Lehrer\nDie EU, China und die USA\nOktober 2020\n{_VORSTAND}",
            "pppp",
        ),
        # a title before its date and an entry
        (
            "Guns, Germs, and Steel\nJune 2020\n"
            "Brown, Bob, and Gail Green. Another Study of Listening. Journal of Sound\n",
            "ppp",
        ),
        (
            "Guns, Germs, and Steel: The Fates of Human Societies in the Long Run\n"
            "June 2020\n"
            "Brown, Bob, and Gail Green. Another Study of Listening. Journal of Sound\n",
            "ppp",
        ),
        (
            "Guns, Germs, and Steel\nJune 2020\n"
            "Brown, B. and Green, G. Another study of listening to papers. Journal of Sound\n",
            "ppp",
        ),
        # headings and sentences shaped like one author
        (
            "Part I. Reading Aloud\nJune 2020\n"
            "Yes, Sir. The board read it twice and then sent it back with many notes.\n",
            "ppp",
        ),
        (
            "Part II. Trade and Research\nJune 2020\n"
            "J. Smith, the chair, read it twice and then sent it back with many notes.\n",
            "ppp",
        ),
        (f"Part I. Reading Aloud\nPart II. Trade and Research\nJune 2020\n{_BOARD}", "pppp"),
        (f"Hello, World. A Study\nParis, France. Annual Report\nJune 2020\n{_BOARD}", "pppp"),
        (
            "Paris, France. Annual Report of the Society\nJune 2020\n"
            "Berlin, Germany. The board read it twice and sent it back with many notes.\n",
            "ppp",
        ),
        (
            "J. Smith and K. Jones, Department of Acoustics\n"
            "B. Brown and G. Green, Department of Speech\n"
            f"June 2020\n{_BOARD}",
            "pppp",
        ),
    ],
    ids=[
        "the-us-using-ai",
        "guns-today",
        "guns-short-using-ai",
        "the-us-part-ii",
        "guns-diamond",
        "kinder-die-eu",
        "guns-short-chicago-entry",
        "guns-long-chicago-entry",
        "guns-short-apa-entry",
        "part-i-yes-sir",
        "part-ii-initials",
        "part-i-part-ii",
        "hello-world-paris",
        "paris-berlin",
        "author-lines",
    ],
)
def test_a_title_shaped_like_an_entry_keeps_its_date_apart_in_context(text: str, tags: str) -> None:
    """A title shaped like a Chicago or Vancouver entry keeps its date apart when the line
    after the date or the line after the title has an entry's shape too, as before #947: only
    a whole author list confirms another ("Smith J, Jones K.", "Smith, John, and Kate
    Jones."), and only after one does the paragraph become a list of entries (#981)."""
    assert tags_of(text) == tags_read(tags)


def test_the_author_list_checks_take_linear_time() -> None:
    """Author lists of every style that never end, before and after a date: the reference
    checks take time linear in the lines (#981)."""

    def sized(size: int) -> str:
        n = size // 10
        return (
            f"{'Smith J, ' * n}\nJune 2020\n{'Smith J, ' * n}\nJune 2020\n"
            f"Smith, John, {'Kate Jones, ' * n}\nJune 2020\n{'J. Smith, ' * n}\n"
            f"June 2020\n{'J. ' * n}Smith and\nJune 2020.\n{'De ' * n}Souza, M.\n"
        )

    assert_linear(lambda text: read(text.encode()), sized, 160_000)


@pytest.mark.parametrize(
    ("text", "tags"),
    [
        (
            "Using AI, Speech and Sound to Read Scientific Papers Aloud at Home\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (f"Using AI, Speech and Sound\nJune 2020\n{_BOARD}", "ppp"),
        (
            f"Part II. Reading Scientific Papers Aloud on Phones and Tablets\nJune 2020\n{_BOARD}",
            "ppp",
        ),
        (f"Part II. Listening\nJune 2020\n{_BOARD}", "ppp"),
        (
            "Appendix A. Reading Scientific Papers Aloud on Phones and Tablets\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (
            "The US, China and Europe: Research on Reading Papers Aloud at Home\n"
            f"JUNE 2020\n{_BOARD}",
            "ppp",
        ),
        (f"Die EU, China und die USA\nOktober 2020\n{_VORSTAND}", "ppp"),
        (
            "Guns, Germs, and Steel\nJune\n"
            "2020 was a year of many notes and the board read them all twice.\n",
            "ppb",
        ),
        (f"Reading Papers Aloud\nSmith, Jane, and John Doe\nJune 2020\n{_BOARD}", "pppp"),
        (
            "Smith J, Jones K. A study of reading papers aloud. Journal of Acoustics\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (
            "Smith, John, and Kate Jones. A Study of Reading Papers Aloud. Journal of Acoustics\n"
            f"June 2020\n{_BOARD}",
            "ppp",
        ),
        (
            "Smith J, Jones K. A study of reading papers aloud on phones and\n"
            f"tablets. Journal of Acoustics\nJune 2020\n{_BOARD}",
            "pbpp",
        ),
    ],
    ids=[
        "using-ai",
        "using-ai-short",
        "part-ii",
        "part-ii-short",
        "appendix-a",
        "the-us-capitals-date",
        "die-eu-short",
        "guns-lone-month",
        "title-and-author-line",
        "one-vancouver-entry-and-prose",
        "one-chicago-entry-and-prose",
        "one-wrapped-vancouver-entry-and-prose",
    ],
)
def test_more_entry_shaped_titles_read_as_before_947(text: str, tags: str) -> None:
    """More titles shaped like an entry, each read as on main before #947: a
    line shaped like an entry before its date and prose is a title, and so is one entry of
    a style that titles share before prose (#981)."""
    assert tags_of(text) == tags_read(tags)


def test_the_date_after_a_chicago_shaped_title_in_a_bullet_item_joins_the_item() -> None:
    """ "- Guns, Germs, and Steel: ..." / "June 2020" / body: the date joins the item as on
    main before #947, and the body starts a block (#981)."""
    text = (
        "- Guns, Germs, and Steel: The Fates of Human Societies in the Long Run\n"
        f"June 2020\n{_BOARD}"
    )
    item = ("ul", "li")
    assert tags_of(text) == [item, (*item, "br"), ("p",)]
