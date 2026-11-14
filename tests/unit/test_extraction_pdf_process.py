"""PDFs read in a child process with memory and time limits (#185, #28, D-581).

PDFium decodes a stream or loads a page before our limits can count anything, so a file of
1 MB could take this process to 3.3 GB. `extract_pdf` and `extract_pdf_cover` read in a child
(`extraction.isolate`) that is stopped above 1 GB or after 60 s on one step; a crash inside
PDFium ends only the child; two reads no longer wait for each other's lock; and at most two
children run at once. Drawings and pictures are counted like characters (D-394), so what
comes back from the child stays small too.
"""

from __future__ import annotations

import operator
import os
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pdf_maker import dense_pdf, flate_bomb, one_page_pdf, raw_pdf, stream

from sci2audio.extraction import (
    ExtractionError,
    extract_pdf,
    extract_pdf_cover,
    isolate,
    pdf,
    read_pdf,
)

pytestmark = [pytest.mark.timeout(120), pytest.mark.every_pdf_read]

CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "papers"
PAPER = CORPUS / "acl2023-hardt-ellipsis.pdf"
TOO_LARGE = r"^{}: the PDF is too large or damaged \({}\)$"


def written(tmp_path: Path, data: bytes, name: str = "file.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def allocate(size: int, hold: float) -> int:
    """A child's work for the watch tests: write `size` bytes, hold them, give back little."""
    data = b"x" * size
    time.sleep(hold)
    return len(data)


# ---- memory (#185) -------------------------------------------------------------------------


def test_a_flate_bomb_is_stopped_at_the_memory_limit_and_this_process_stays_small(
    tmp_path: Path,
) -> None:
    """1.1 GB of spaces in a 1.1 MB file took 3.3 GB and 13 s in one process (#185). The
    read runs in a fresh interpreter here, so its own peak shows what reading cost it."""
    path = written(tmp_path, flate_bomb(1100 << 20))
    script = textwrap.dedent(
        f"""
        from pathlib import Path
        from sci2audio.extraction import ExtractionError, extract_pdf, isolate
        before = isolate.peak_memory()
        try:
            extract_pdf(Path({str(path)!r}))
        except ExtractionError as error:
            print(error)
        print(isolate.peak_memory() - before)
        """
    )
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True, timeout=110
    )
    message, grown = done.stdout.strip().splitlines()
    assert message == (
        "file.pdf: the PDF is too large or damaged (reading it needs more than 1 GB of memory)"
    )
    assert int(grown) < 50 * 1024 * 1024


def test_the_memory_message_names_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf, "MAX_MEMORY", 300 * 1024 * 1024)
    path = written(tmp_path, flate_bomb(600 << 20))
    detail = "reading it needs more than 300 MB of memory"
    with pytest.raises(ExtractionError, match=TOO_LARGE.format(r"file\.pdf", detail)):
        extract_pdf(path)


def test_the_watch_stops_a_child_that_grows_past_the_limit() -> None:
    stopped = isolate.run(
        allocate,
        (300 * 1024 * 1024, 0.3),
        memory=100 * 1024 * 1024,
        step_seconds=60,
        readers=isolate.Readers(1),
    )
    assert stopped == isolate.Stopped("memory", "opening")


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS has no hard memory limit")
def test_the_hard_limit_stops_an_allocation_faster_than_the_watch() -> None:
    """Three times the limit at once, given back at once: only the system's own limit (at
    twice the limit) can stop it before the watch looks."""
    stopped = isolate.run(
        allocate,
        (300 * 1024 * 1024, 0.0),
        memory=100 * 1024 * 1024,
        step_seconds=60,
        readers=isolate.Readers(1),
    )
    assert stopped == isolate.Stopped("memory", "opening")


def test_a_child_within_the_limit_gives_its_result() -> None:
    result = isolate.run(
        operator.add, (2, 3), memory=1024**3, step_seconds=60, readers=isolate.Readers(1)
    )
    assert result == 5


def test_an_error_in_the_child_is_raised_here() -> None:
    with pytest.raises(ZeroDivisionError):
        isolate.run(
            operator.truediv, (1, 0), memory=1024**3, step_seconds=60, readers=isolate.Readers(1)
        )


# ---- time and crashes ----------------------------------------------------------------------


def test_a_page_that_takes_longer_than_a_step_may_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The densest page the limits allow (90,000 characters) takes about 2 s."""
    monkeypatch.setattr(pdf, "STEP_SECONDS", 0.5)
    path = written(tmp_path, dense_pdf(1, 90_000))
    detail = "reading page 1 took more than 0.5 seconds"
    with pytest.raises(ExtractionError, match=TOO_LARGE.format(r"file\.pdf", detail)):
        extract_pdf(path)


def test_a_child_that_ends_without_a_result_is_named() -> None:
    stopped = isolate.run(os.abort, (), memory=1024**3, step_seconds=60, readers=isolate.Readers(1))
    assert stopped == isolate.Stopped("ended", "opening")
    assert str(pdf._stopped("a.pdf", stopped)) == (
        "a.pdf: the PDF is damaged (the PDF reader stopped unexpectedly)"
    )


def test_a_stopped_child_gives_no_cover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "MAX_MEMORY", 300 * 1024 * 1024)
    assert extract_pdf_cover(written(tmp_path, flate_bomb(600 << 20))) is None
    assert extract_pdf_cover(PAPER) is not None


# ---- drawings and pictures (#185 review comment) -------------------------------------------


def rectangles(count: int) -> bytes:
    content = b"".join(b"%d %d 1 1 re f\n" % (i % 600, (i // 600) % 790) for i in range(count))
    return one_page_pdf(content + b"BT /F1 12 Tf 72 720 Td (Hello) Tj ET", compress=True)


def picture_uses(count: int) -> bytes:
    image = stream(
        b"\x80" * 4,
        b"/Type /XObject /Subtype /Image /Width 2 /Height 2"
        b" /ColorSpace /DeviceGray /BitsPerComponent 8",
    )
    content = b"".join(b"q 2 0 0 2 %d %d cm /Im1 Do Q\n" % (i % 600, i % 790) for i in range(count))
    return one_page_pdf(
        content + b"BT /F1 12 Tf 72 720 Td (Hello) Tj ET",
        compress=True,
        resources=b"<< /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >>",
        extra={6: image},
    )


def nested_drawings(levels: int) -> bytes:
    """Forms drawing the next form ten times, `levels` deep, the last a rectangle: 10 **
    levels rectangles from a few KB (#185 review comment: 7 levels took 1.96 GB)."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Resources << /XObject << /X 100 0 R >> /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        4: stream(b"/X Do BT /F1 12 Tf 72 720 Td (Hello) Tj ET"),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for level in range(levels):
        if level == levels - 1:
            body, resources = b"0 0 1 1 re f", b"<< >>"
        else:
            body = b" ".join([b"/X Do"] * 10)
            resources = b"<< /XObject << /X %d 0 R >> >>" % (101 + level)
        objects[100 + level] = stream(
            body, b"/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources " + resources
        )
    return raw_pdf(objects)


PAGE_GRAPHICS = "page 1 holds more than 100,000 drawings and pictures"


@pytest.mark.parametrize("make", [rectangles, picture_uses], ids=["drawings", "picture-uses"])
def test_a_page_of_too_many_drawings_or_pictures_is_refused(
    tmp_path: Path, make: Callable[[int], bytes]
) -> None:
    with pytest.raises(ExtractionError, match=TOO_LARGE.format(r"file\.pdf", PAGE_GRAPHICS)):
        extract_pdf(written(tmp_path, make(100_001)))


def test_forms_nested_seven_deep_are_refused(tmp_path: Path) -> None:
    """PDFium loads the page into well over 1 GB, or our walk counts past the limit first."""
    with pytest.raises(ExtractionError, match=r"^file\.pdf: the PDF is too large or damaged"):
        extract_pdf(written(tmp_path, nested_drawings(7)))


def test_drawings_and_pictures_count_together_on_a_page_and_in_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf, "MAX_PAGE_GRAPHICS", 5)
    monkeypatch.setattr(pdf, "MAX_GRAPHICS", 8)
    assert len(read_pdf(rectangles(5), "a.pdf").pages[0].drawings) == 5
    with pytest.raises(ExtractionError, match="page 1 holds more than 5 drawings and pictures"):
        read_pdf(picture_uses(6), "a.pdf")
    assert len(read_pdf(two_pages_of_rectangles(4), "a.pdf").pages) == 2  # 8 in all
    with pytest.raises(ExtractionError, match=r"\(more than 8 drawings and pictures\)$"):
        read_pdf(two_pages_of_rectangles(5), "a.pdf")


def two_pages_of_rectangles(per_page: int) -> bytes:
    """Two pages sharing one stream of `per_page` rectangles and a word."""
    content = b"".join(b"%d 10 1 1 re f\n" % i for i in range(per_page))
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [10 0 R 11 0 R] /Count 2 >>",
        4: stream(content + b"BT /F1 12 Tf 72 720 Td (Hello) Tj ET"),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for number in (10, 11):
        objects[number] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        )
    return raw_pdf(objects)


def test_the_limits_are_the_decided_ones() -> None:
    assert (pdf.MAX_PAGE_GRAPHICS, pdf.MAX_GRAPHICS) == (100_000, 500_000)
    assert (pdf.MAX_MEMORY, pdf.STEP_SECONDS, pdf.MAX_PDF_READERS) == (1024**3, 60, 2)


# ---- reads at once (#28) ---------------------------------------------------------------------


def test_a_short_read_does_not_wait_for_a_long_one(tmp_path: Path) -> None:
    """On main, a 400-page book held the PDFium lock for 21 s and every other read waited."""
    long = written(tmp_path, dense_pdf(1, 90_000), "long.pdf")  # about 2 s
    ended: dict[str, float] = {}

    def read(path: Path) -> None:
        extract_pdf(path)
        ended[path.name] = time.perf_counter()

    reading = threading.Thread(target=read, args=(long,))
    reading.start()
    time.sleep(0.3)  # the long read is under way
    read(PAPER)
    reading.join()
    assert ended[PAPER.name] < ended["long.pdf"]


def test_a_third_read_waits_for_a_free_reader_and_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readers = isolate.Readers(2)
    monkeypatch.setattr(pdf, "_READERS", readers)
    path = written(tmp_path, dense_pdf(1, 30_000))
    expected = read_pdf(path.read_bytes(), path.name)
    results: list[object] = []
    threads = [threading.Thread(target=lambda: results.append(extract_pdf(path))) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [expected] * 3
    assert readers.most == 2


# ---- the child stays small (D-581) -----------------------------------------------------------


def test_the_child_imports_only_extraction_and_core(tmp_path: Path) -> None:
    """The program's main module imports every layer (the `sci2audio` command); a child
    that imported it too would spend seconds on each read."""
    main = tmp_path / "main.py"
    main.write_text(
        textwrap.dedent(
            """
            import sci2audio.app, sci2audio.cli, sci2audio.voices, sci2audio.web
            from sci2audio.extraction import isolate
            if __name__ == "__main__":
                print(*isolate.run(
                    isolate.loaded, ("sci2audio",), memory=1024**3, step_seconds=60,
                    readers=isolate.Readers(1),
                ))
            """
        )
    )
    done = subprocess.run(
        [sys.executable, str(main)], capture_output=True, text=True, check=True, timeout=110
    )
    modules = done.stdout.split()
    assert "sci2audio.extraction.isolate" in modules
    others = [
        name
        for name in modules
        if name != "sci2audio" and not name.startswith(("sci2audio.core", "sci2audio.extraction"))
    ]
    assert others == []


# ---- the corpus reads the same ---------------------------------------------------------------


def test_a_paper_read_in_the_child_is_the_paper_read_here() -> None:
    assert extract_pdf(PAPER) == read_pdf(PAPER.read_bytes(), PAPER.name)
