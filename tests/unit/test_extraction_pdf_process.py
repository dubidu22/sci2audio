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
from dataclasses import dataclass
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


MB = 1024 * 1024


def grow(chunks: int, size: int, pause: float) -> int:
    """A child's work for the watch test: grow by `size` bytes `chunks` times, slowly enough
    for the watch to look in between; give back how many were held."""
    held = [b"x" * size]
    for _ in range(chunks - 1):
        time.sleep(pause)
        held.append(b"x" * size)
    time.sleep(0.3)
    return len(held)


def allocate_unwatched(size: int) -> int:
    """A child's work for the hard-limit test: park the watch first, then ask for `size`
    bytes at once, so only the system's own limit can stop the child."""
    isolate._WATCH_SECONDS = 3600
    time.sleep(0.1)  # the watch takes its last look and sleeps
    return len(b"x" * size)


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
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=110
    )
    assert done.returncode == 0, (  # #485: say why the reading process failed
        f"exit status {done.returncode}\nstdout:\n{done.stdout}\nstderr:\n{done.stderr}"
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
    """Up to 1.25 times the limit in 10 MB steps: still under the hard limit at twice the
    limit (with the child's own address space), so only the watch can stop it (#345 B1)."""
    stopped = isolate.run(
        grow, (50, 10 * MB, 0.01), memory=400 * MB, step_seconds=60, readers=isolate.Readers(1)
    )
    assert stopped == isolate.Stopped("memory", "opening")


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS has no hard memory limit")
def test_the_hard_limit_stops_an_allocation_the_watch_does_not_see() -> None:
    """Three times the limit at once with the watch parked: only the system's own limit (the
    address space on Linux, the job object on Windows, at twice the limit) refuses it."""
    stopped = isolate.run(
        allocate_unwatched,
        (300 * MB,),
        memory=100 * MB,
        step_seconds=60,
        readers=isolate.Readers(1),
    )
    assert stopped == isolate.Stopped("memory", "opening")


def report_and_end(step: str) -> None:
    """A child's work for the closed-pipe test: report a step, then end at once as the
    memory watch ends a child."""
    isolate.report(step)
    os._exit(isolate.MEMORY_EXIT)


def test_a_child_that_ended_while_this_process_was_busy_is_named() -> None:
    """The parent is still handing on the child's last step when the child ends, so it next
    looks at a pipe that is empty and closed. On Windows that look raised BrokenPipeError,
    which left `extract_pdf` as an unexplained error (#485: the flate-bomb test failed
    under load there)."""
    stopped = isolate.run(
        report_and_end,
        ("page 1 of 1",),
        memory=1024**3,
        step_seconds=60,
        readers=isolate.Readers(1),
        on_step=lambda step: time.sleep(0.5),
    )
    assert stopped == isolate.Stopped("memory", "page 1 of 1")


class ClosedPipe:
    """The parent's end of a pipe whose child has ended, as Windows reports it: looking
    for words raises (PeekNamedPipe, WinError 109)."""

    def poll(self, timeout: float | None = None) -> bool:
        raise BrokenPipeError(32, "The pipe has been ended")

    def recv(self) -> object:
        raise AssertionError("nothing to receive")


@dataclass
class EndedChild:
    exitcode: int

    def join(self) -> None:
        pass

    def kill(self) -> None:
        raise AssertionError("the child has already ended")


@pytest.mark.parametrize(
    ("exitcode", "reason"),
    [(isolate.MEMORY_EXIT, "memory"), (isolate.TIME_EXIT, "time"), (1, "ended")],
)
def test_a_closed_pipe_is_read_as_the_child_having_ended(exitcode: int, reason: str) -> None:
    """On every system: an error from looking at the pipe means the child has ended, and
    its exit status says why (#485)."""
    stopped = isolate._wait(EndedChild(exitcode), ClosedPipe(), 60, None, None)  # type: ignore[arg-type]
    assert stopped == isolate.Stopped(reason, "starting")


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


class TwoPartError(Exception):
    """Pickles, but cannot be rebuilt from its pickle (its arguments are not its `args`)."""

    def __init__(self, first: str, second: str) -> None:
        super().__init__(f"{first}/{second}")


def raise_two_part() -> None:
    raise TwoPartError("a", "b")


def test_an_error_that_cannot_cross_to_this_process_arrives_named() -> None:
    """Without the check in the child it arrived as an unrelated TypeError (#345 S1)."""
    with pytest.raises(RuntimeError, match=r"^TwoPartError: a/b$"):
        isolate.run(raise_two_part, (), memory=1024**3, step_seconds=60, readers=isolate.Readers(1))


def raise_permission(path: str, limits: dict[str, object]) -> None:
    raise PermissionError(13, "not allowed", path)


def test_an_os_error_in_the_child_is_not_a_failed_start() -> None:
    """Only a child that could not be started gets the start message (#345 S5)."""
    with pytest.raises(PermissionError, match="not allowed"):
        pdf._isolated(raise_permission, "a.pdf")


def test_a_child_that_cannot_start_is_named_and_leaves_no_pipe_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import multiprocessing.context

    def refuse(self: object) -> None:
        raise OSError(24, "Too many open files")

    pipes: list[tuple[object, object]] = []
    context = multiprocessing.get_context("spawn")
    real_pipe = context.Pipe

    def pipe(duplex: bool = True) -> tuple[object, object]:
        ends = real_pipe(duplex)
        pipes.append(ends)
        return ends

    monkeypatch.setattr(multiprocessing.context.SpawnProcess, "start", refuse)
    monkeypatch.setattr(context, "Pipe", pipe)
    with pytest.raises(ExtractionError) as raised:
        extract_pdf(PAPER)
    assert str(raised.value) == (
        "acl2023-hardt-ellipsis.pdf: cannot be read: sci2audio could not start its PDF reader"
        " ([Errno 24] Too many open files)"
    )
    assert [(end.closed, other.closed) for end, other in pipes] == [(True, True)]  # type: ignore[attr-defined]
    assert pdf._READERS.alive == 0


MARKS = """
import os, time
from pathlib import Path

def sleep_with_marks(folder, seconds):
    Path(folder, "started").write_text(str(os.getpid()))
    time.sleep(seconds)
    Path(folder, "finished").write_text("")
"""


def test_a_child_whose_parent_is_gone_ends_after_twice_its_step_time(tmp_path: Path) -> None:
    """The parent ends a slow step; when the parent itself was killed, the child's watch ends
    it after twice the step time, so it does not read on alone (#345 S2, plan Q9). The child's
    work lives in a module of its own that imports nothing heavy, so that the child starts
    within one step time on every system (Windows CI took longer than 0.25 s to import pytest
    in the child)."""
    code = tmp_path / "code"
    code.mkdir()
    (code / "marks.py").write_text(MARKS)
    script = textwrap.dedent(
        f"""
        import os, sys, threading, time
        sys.path.insert(0, {str(code)!r})
        from pathlib import Path
        from sci2audio.extraction import isolate
        from marks import sleep_with_marks
        folder = {str(tmp_path)!r}
        reading = threading.Thread(
            target=isolate.run, args=(sleep_with_marks, (folder, 3.0)),
            kwargs=dict(memory=1024**3, step_seconds=0.5, readers=isolate.Readers(1)),
            daemon=True,
        )
        reading.start()
        while not Path(folder, "started").exists():
            if not reading.is_alive():
                sys.exit("the child was stopped before its work started")
            time.sleep(0.02)
        os._exit(0)  # gone at once, as if killed: nothing ends the child from here
        """
    )
    subprocess.run([sys.executable, "-c", script], check=True, timeout=60)
    assert (tmp_path / "started").exists()
    time.sleep(3.5)  # the child would have finished after 3 s; its watch ends it after 1 s
    assert not (tmp_path / "finished").exists()


STEPS = """
import time
from sci2audio.extraction import isolate

def steady_steps(count, pause):
    for number in range(1, count + 1):
        isolate.report(f"page {number}")
        time.sleep(pause)
    return count
"""


def test_each_reported_step_starts_the_childs_own_clock_anew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eight steps of 0.2 s at a 0.5 s step limit: 1.6 s in all, past the child's own limit
    of twice a step, so only a clock that each report restarts lets the read finish; a long
    book (about 1,800 pages in 120 s) would otherwise be stopped (#345 R2-1). The child's
    work lives in a small module of its own, so the child starts quickly on every system."""
    (tmp_path / "steady_steps.py").write_text(STEPS)
    monkeypatch.syspath_prepend(str(tmp_path))
    import steady_steps  # type: ignore[import-not-found]

    result = isolate.run(
        steady_steps.steady_steps,
        (8, 0.2),
        memory=1024**3,
        step_seconds=0.5,
        readers=isolate.Readers(1),
    )
    assert result == 8


SLOW_START = """
import time
time.sleep(1.0)  # a busy machine: the child's imports take a second

def quick(value):
    return value
"""


def slow_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[object], object]:
    """A target whose module takes a second to import, in the child as here."""
    (tmp_path / "slow_start.py").write_text(SLOW_START)
    monkeypatch.syspath_prepend(str(tmp_path))
    import slow_start  # type: ignore[import-not-found]

    return slow_start.quick  # type: ignore[no-any-return]


def test_a_slow_start_is_not_counted_as_a_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first step starts when the child runs: macOS CI took longer than a 0.5 s step to
    start a child, and the read was stopped at "opening" before it began (D-616)."""
    quick = slow_start(tmp_path, monkeypatch)
    result = isolate.run(quick, (7,), memory=1024**3, step_seconds=0.3, readers=isolate.Readers(1))
    assert result == 7


def test_a_child_that_does_not_start_in_time_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quick = slow_start(tmp_path, monkeypatch)
    monkeypatch.setattr(isolate, "START_SECONDS", 0.3)  # below the step: only it can stop
    stopped = isolate.run(quick, (7,), memory=1024**3, step_seconds=5, readers=isolate.Readers(1))
    assert stopped == isolate.Stopped("time", "starting")
    assert str(pdf._stopped("a.pdf", stopped)) == (
        "a.pdf: cannot be read: sci2audio could not start its PDF reader"
        " (it did not start within 0.3 seconds)"
    )
    assert str(pdf._stopped("a.pdf", isolate.Stopped("ended", "starting"))) == (
        "a.pdf: cannot be read: sci2audio could not start its PDF reader (it ended while starting)"
    )


def test_a_child_ended_by_its_own_watch_for_time_is_named() -> None:
    """The parent normally ends a slow step first; when the child's watch is first, its exit
    reads as a step that took too long."""
    stopped = isolate.run(
        os._exit, (isolate.TIME_EXIT,), memory=1024**3, step_seconds=60, readers=isolate.Readers(1)
    )
    assert stopped == isolate.Stopped("time", "opening")


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


def test_a_read_reports_each_page_and_then_the_outline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each report starts a step's time anew; the outline is a step of its own (#345 S3).
    A page step names the page count too, for the job's progress (#343)."""
    steps: list[str] = []
    monkeypatch.setattr(isolate, "_report", steps.append)
    read_pdf(two_pages_of_rectangles(1), "a.pdf")
    assert steps == ["page 1 of 2", "page 2 of 2", "outline"]


@pytest.mark.parametrize(
    ("step", "detail"),
    [
        ("opening", "opening it took more than 60 seconds"),
        ("page 7", "reading page 7 took more than 60 seconds"),
        ("page 7 of 400", "reading page 7 took more than 60 seconds"),
        ("outline", "reading its outline took more than 60 seconds"),
    ],
)
def test_the_time_message_names_the_step(step: str, detail: str) -> None:
    message = str(pdf._stopped("a.pdf", isolate.Stopped("time", step)))
    assert message == f"a.pdf: the PDF is too large or damaged ({detail})"


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
    assert pdf._READERS.limit == pdf.MAX_PDF_READERS  # the cap reads use (#345 S4)
    assert isolate.START_SECONDS == 30  # a reader's start, before its first step (D-616)


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
