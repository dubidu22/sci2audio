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
    """Eight times the lines against a base run, on CPU time (#298)."""
    line = "A line of an ordinary plain-text file, about sixty chars.\n"
    # a paragraph of 50 lines: 100,000 lines without a blank one are past MAX_PARAGRAPH (#607)
    paragraph = line * 50 + "\n"
    content = assert_linear(
        lambda text: read(text.encode()), lambda n: paragraph * (n // 50), 100_000
    )
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
