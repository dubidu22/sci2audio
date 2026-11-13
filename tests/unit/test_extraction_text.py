"""Plain-text extraction and the decoding shared with Markdown (#74, the text part of #5).

A text file becomes one page; each printed line that is not blank is a text line, the first
of a paragraph tagged ``p`` and each following one ``p``, ``br`` (D-344). The encoding is the
byte order mark's, else UTF-8, else Windows-1252 as WHATWG decodes it, marked as guessed
(D-345, D-346). Empty, binary and too large files fail with a clear message (D-347).
"""

from __future__ import annotations

import codecs
import time
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

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


def test_a_large_file_is_read_in_reasonable_time() -> None:
    data = ("A line of an ordinary plain-text file, about sixty chars.\n" * 100_000).encode()
    start = time.perf_counter()
    content = read(data)
    assert len(content.pages[0].lines) == 100_000
    assert time.perf_counter() - start < 10


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


@given(paragraphs, st.sampled_from(["utf-8", "utf-8-sig", "utf-16", "utf-32"]))
def test_paragraphs_come_back_line_for_line_in_every_declared_encoding(
    written: list[list[str]], codec: str
) -> None:
    data = "\n\n".join("\n".join(paragraph) for paragraph in written).encode(codec)
    expected = [
        (" ".join(line.split(" ")).strip(" "), ("p",) if index == 0 else ("p", "br"))
        for paragraph in written
        for index, line in enumerate(paragraph)
    ]
    expected = [(" ".join(t for t in text.split(" ") if t), tags) for text, tags in expected]
    content = read(data)
    assert lines(content) == expected
    assert not content.source.encoding_guessed
