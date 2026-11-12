"""PDF extraction on small made-up PDFs and broken files (Issue #23, D-63, D-65).

Extraction records what the PDF holds and decides nothing; each test shows one thing it must
record faithfully, or one file it must refuse with a clear message.
"""

import threading
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import HEIGHT, Rect, Text, in_form, make_pdf

from sci2audio.core import Content, SourceFormat
from sci2audio.extraction import ExtractionError, extract_pdf, read_pdf

pytestmark = pytest.mark.timeout(60)

TESTS = Path(__file__).resolve().parents[1]
BROKEN = TESTS / "fixtures" / "broken"
PAPER = TESTS / "corpus" / "papers" / "acl2023-hardt-ellipsis.pdf"
EPUB = TESTS / "corpus" / "epub" / "wells-the-time-machine.epub"


def lines_of(data: bytes) -> list[str]:
    return [line.text for line in read_pdf(data, "made.pdf").pages[0].lines]


def test_two_columns_on_one_baseline_stay_two_lines() -> None:
    data = make_pdf([Text("end of a left line", 50, 100), Text("start of a right", 320, 100)])
    assert lines_of(data) == ["end of a left line", "start of a right"]


def test_lines_keep_the_order_the_file_stores_them_in() -> None:
    data = make_pdf([Text("stored first, lower", 50, 300), Text("stored second, higher", 50, 100)])
    assert lines_of(data) == ["stored first, lower", "stored second, higher"]


def test_runs_record_font_size_bold_and_italic() -> None:
    data = make_pdf(
        [
            Text("Heading", 50, 60, font="Helvetica-Bold", size=14),
            Text("leaning", 50, 100, font="Helvetica-Oblique"),
        ]
    )
    heading, leaning = (line.runs[0] for line in read_pdf(data, "made.pdf").pages[0].lines)
    assert (heading.font, heading.size, heading.bold, heading.italic) == (
        "Helvetica-Bold",
        14.0,
        True,
        False,
    )
    assert (leaning.size, leaning.bold, leaning.italic) == (10.0, False, True)


def test_a_raised_smaller_number_stays_in_its_line_as_its_own_run() -> None:
    data = make_pdf([Text("E = mc", 50, 200), Text("2", 81, 196, size=6)])
    (line,) = read_pdf(data, "made.pdf").pages[0].lines
    assert [(run.text, run.size) for run in line.runs] == [("E = mc", 10.0), ("2", 6.0)]


def test_text_turned_upwards_reads_as_one_line() -> None:
    data = make_pdf([Text("arXiv:1234.5678v1 [cs.CL]", 20, 600, size=20, turned=True)])
    (line,) = read_pdf(data, "made.pdf").pages[0].lines
    assert line.text == "arXiv:1234.5678v1 [cs.CL]"
    assert line.box is not None
    assert line.box.y1 - line.box.y0 > line.box.x1 - line.box.x0  # tall and narrow


def test_boxes_are_measured_from_the_top_left() -> None:
    page = read_pdf(make_pdf([Text("near the top", 50, 40), Rect(50, 300, 250, 301)]), "m.pdf")
    (line,) = page.pages[0].lines
    (rule,) = page.pages[0].drawings
    assert line.box is not None
    assert 25 < line.box.y0 < line.box.y1 < 45
    assert (rule.box.x0, rule.box.y0, rule.box.x1, rule.box.y1) == (50, 300, 250, 301)


def test_drawings_inside_a_form_get_page_positions() -> None:
    # The rectangle sits at x 100..300, y 100..200 on its own page; the form halves it and
    # moves it 10 pt right and 20 pt up (PDF space): 60..160 across, 430..480 down.
    data = in_form(make_pdf([Rect(100, 100, 300, 200)]), scale=0.5, dx=10, dy=20)
    (drawing,) = read_pdf(data, "form.pdf").pages[0].drawings
    box = drawing.box
    assert (box.x0, box.y0, box.x1, box.y1) == (60, 430, 160, 480)


def test_pages_ids_and_source_are_recorded(tmp_path: Path) -> None:
    file = tmp_path / "two pages.pdf"
    file.write_bytes(make_pdf([Text("one", 50, 100)], [Text("two", 50, 100), Rect(1, 2, 3, 4)]))
    content = extract_pdf(file)
    assert content.source.name == "two pages.pdf"
    assert content.source.format is SourceFormat.PDF
    assert len(content.source.sha256) == 64
    assert [(p.number, p.width, p.height) for p in content.pages] == [
        (1, 600, HEIGHT),
        (2, 600, HEIGHT),
    ]
    assert sorted(content.items()) == ["p1-l1", "p2-d1", "p2-l1"]


def test_extraction_is_deterministic() -> None:
    data = make_pdf([Text("same every time", 50, 100), Rect(10, 10, 20, 20)])
    assert read_pdf(data, "a.pdf") == read_pdf(data, "a.pdf")


def test_threads_reading_at_once_do_not_crash() -> None:
    # PDFium is not thread-safe (KB audit "PDFium thread-safety crash"): the lock must hold.
    data = make_pdf([Text(f"line {i}", 50, 20 + 12 * i) for i in range(40)])
    expected = read_pdf(data, "t.pdf")
    results: list[Content] = []

    def work() -> None:
        results.extend(read_pdf(data, "t.pdf") for _ in range(5))

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [expected] * 30


# Broken files: a clear message naming the file, never a traceback or a hang (#5).


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(b"", "the file is empty", id="empty"),
        pytest.param(b"Just some words, no PDF at all.", "not a PDF", id="plain-text"),
        pytest.param(EPUB.read_bytes(), "not a PDF", id="epub-named-pdf"),
        pytest.param(PAPER.read_bytes()[:1000], "damaged", id="truncated-start"),
        pytest.param(PAPER.read_bytes()[: PAPER.stat().st_size // 2], "damaged", id="half"),
        pytest.param(
            (BROKEN / "password-protected.pdf").read_bytes(), "password-protected", id="password"
        ),
        pytest.param(make_pdf(), "damaged", id="no-pages"),  # PDFium refuses to open it
    ],
)
def test_broken_files_fail_with_a_clear_message(data: bytes, message: str) -> None:
    with pytest.raises(ExtractionError, match=message) as error:
        read_pdf(data, "broken.pdf")
    assert str(error.value).startswith("broken.pdf: ")


def test_a_missing_file_fails_with_a_clear_message(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match=r"^gone\.pdf: cannot be opened"):
        extract_pdf(tmp_path / "gone.pdf")


SMALL = make_pdf(
    [Text("A heading", 50, 60, font="Helvetica-Bold", size=14), Text("Body text", 50, 100)],
    [Rect(50, 300, 250, 301), Text("arXiv stamp", 20, 600, turned=True)],
)


def outcome(data: bytes, name: str) -> Content | str:
    """The content, or the message of the ExtractionError (any other exception fails the test)."""
    try:
        return read_pdf(data, name)
    except ExtractionError as error:
        return str(error)


@settings(deadline=None)
@given(st.binary(max_size=2000))
def test_any_bytes_give_content_or_a_clear_error(data: bytes) -> None:
    result = outcome(data, "random.pdf")
    assert isinstance(result, Content) or result.startswith("random.pdf: ")


@settings(deadline=None)
@given(
    st.integers(0, len(SMALL)),
    st.lists(st.tuples(st.integers(0, len(SMALL) - 1), st.integers(0, 255)), max_size=20),
)
def test_a_damaged_pdf_gives_content_or_a_clear_error(
    keep: int, changes: list[tuple[int, int]]
) -> None:
    data = bytearray(SMALL[:keep] if keep < len(SMALL) // 2 else SMALL)
    for position, value in changes:
        if position < len(data):
            data[position] = value
    result = outcome(bytes(data), "damaged.pdf")
    assert (isinstance(result, Content) and result.pages) or result.startswith("damaged.pdf: ")
