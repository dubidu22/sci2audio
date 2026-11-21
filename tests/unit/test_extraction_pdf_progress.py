"""Page progress while a PDF is read (#343) and a cancel that ends the reader (#344).

The reader child reports each step it starts (D-581); the parent hands each one on to
`on_step`, and `extract_pdf` hands each page on as `pages(number, total)`. A cancel ends the
child at once, frees its reader slot and raises ReadCancelled, which is not an
ExtractionError: nothing is wrong with the file.

The children's work lives in `reader_targets`, a small module that imports nothing heavy, so
a child starts quickly on every system (#345).
"""

from __future__ import annotations

import logging
import multiprocessing
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import pytest
import reader_targets as targets

from sci2audio.extraction import ExtractionError, ReadCancelled, extract_pdf, isolate, pdf

pytestmark = [pytest.mark.timeout(120), pytest.mark.every_pdf_read]

PAPER = Path(__file__).resolve().parents[1] / "corpus" / "papers" / "acl2023-hardt-ellipsis.pdf"
GiB = 1024**3


def in_thread(work: Callable[[], Any]) -> tuple[threading.Thread, dict[str, Any]]:
    """Run `work` in a thread; its result (or error) and when it ended land in the dict."""
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["result"] = work()
        except BaseException as error:
            outcome["error"] = error
        outcome["ended"] = time.monotonic()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def wait_for(path: Path, thread: threading.Thread) -> None:
    deadline = time.monotonic() + 60
    while not path.exists():
        assert thread.is_alive(), "the read ended before the child's work started"
        assert time.monotonic() < deadline, "the child's work did not start"
        time.sleep(0.02)


# ---- steps reach the parent (#343) ----------------------------------------------------------


def test_each_step_reaches_on_step_in_order() -> None:
    seen: list[str] = []
    result = isolate.run(
        targets.pages_then_rest,
        (3, 0.05, 0.0),
        memory=GiB,
        step_seconds=60,
        readers=isolate.Readers(1),
        on_step=seen.append,
    )
    assert result == 3
    assert seen == ["opening", "page 1 of 3", "page 2 of 3", "page 3 of 3"]  # "opening": D-616


def test_an_on_step_that_raises_does_not_stop_the_read(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[str] = []

    def broken(step: str) -> None:
        calls.append(step)
        raise RuntimeError("the screen is gone")

    with caplog.at_level(logging.ERROR, logger="sci2audio.extraction.isolate"):
        result = isolate.run(
            targets.pages_then_rest,
            (2, 0.0, 0.0),
            memory=GiB,
            step_seconds=60,
            readers=isolate.Readers(1),
            on_step=broken,
        )
    assert result == 2
    assert calls == ["opening", "page 1 of 2", "page 2 of 2"]
    logged = [
        (record.getMessage(), str(record.exc_info[1]))
        for record in caplog.records
        if record.exc_info
    ]
    assert logged == [
        (f"the progress of step {step!r} could not be handed on", "the screen is gone")
        for step in calls
    ]


def test_a_pdf_read_hands_on_every_page_with_the_page_count() -> None:
    """The acceptance test of #343: a multi-page paper, read in a real child."""
    document = pdfium.PdfDocument(PAPER)
    total = len(document)
    document.close()
    assert total > 1
    seen: list[tuple[int, int]] = []
    extract_pdf(PAPER, pages=lambda number, count: seen.append((number, count)))
    assert seen == [(number, total) for number in range(1, total + 1)]


# ---- the time limit holds with a cancel to watch (#344, D-623) -----------------------------


def test_with_a_cancel_to_watch_a_step_is_stopped_at_its_own_time_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The parent looks at the cancel every 0.1 s; the time limit stays one step time from
    the step's start, neither shorter nor stretched by the slices. Timed from the page
    step's arrival to the moment the parent decides, before the child is joined (#366):
    a slow runner's join does not count."""
    started: dict[str, float] = {}
    decided: list[float] = []
    real_wait = isolate._wait

    def timed_wait(*args: Any) -> Any:
        try:
            return real_wait(*args)
        finally:
            decided.append(time.monotonic())

    monkeypatch.setattr(isolate, "_wait", timed_wait)
    stopped = isolate.run(
        targets.page_then_hang,
        (str(tmp_path), 30),
        memory=GiB,
        step_seconds=1.0,
        readers=isolate.Readers(1),
        on_step=lambda step: started.setdefault(step, time.monotonic()),
        cancel=threading.Event(),
    )
    assert stopped == isolate.Stopped("time", "page 1 of 1")
    took = decided[0] - started["page 1 of 1"]  # from the page step's start to the decision
    assert 1.0 <= took < 1.5


def test_with_a_cancel_to_watch_each_step_still_starts_its_time_anew() -> None:
    """Four steps of 0.4 s at a 1 s limit: 1.6 s in all, so only a deadline that each step
    starts anew lets the read finish."""
    result = isolate.run(
        targets.pages_then_rest,
        (4, 0.4, 0.0),
        memory=GiB,
        step_seconds=1.0,
        readers=isolate.Readers(1),
        cancel=threading.Event(),
    )
    assert result == 4


def test_the_cancel_is_looked_at_every_tenth_of_a_second() -> None:
    assert isolate._CANCEL_SECONDS == 0.1


# ---- a cancel ends the child at once (#344) -------------------------------------------------


def test_a_cancel_during_a_long_step_ends_the_child_and_frees_its_slot(tmp_path: Path) -> None:
    readers = isolate.Readers(1)
    cancel = threading.Event()
    thread, outcome = in_thread(
        lambda: isolate.run(
            targets.page_then_hang,
            (str(tmp_path), 30),
            memory=GiB,
            step_seconds=60,
            readers=readers,
            cancel=cancel,
        )
    )
    wait_for(tmp_path / "started", thread)
    cancelled = time.monotonic()
    cancel.set()
    thread.join(10)
    assert outcome["result"] == isolate.Stopped("cancelled", "page 1 of 1")
    assert outcome["ended"] - cancelled < 1.0
    assert multiprocessing.active_children() == []
    assert readers.alive == 0
    began = time.monotonic()
    assert (
        isolate.run(
            targets.pages_then_rest, (1, 0.0, 0.0), memory=GiB, step_seconds=60, readers=readers
        )
        == 1
    )
    assert time.monotonic() - began < 30  # it did not wait for the cancelled read's 30 s
    assert not (tmp_path / "finished").exists()


def test_a_cancel_while_waiting_for_a_slot_starts_no_child(tmp_path: Path) -> None:
    readers = isolate.Readers(1)
    assert readers.take(None)  # the one slot is busy
    cancel = threading.Event()
    try:
        thread, outcome = in_thread(
            lambda: isolate.run(
                targets.page_then_hang,
                (str(tmp_path), 30),
                memory=GiB,
                step_seconds=60,
                readers=readers,
                cancel=cancel,
            )
        )
        time.sleep(0.3)
        assert thread.is_alive()  # waiting for the slot
        cancelled = time.monotonic()
        cancel.set()
        thread.join(10)
        assert outcome["result"] == isolate.Stopped("cancelled")
        assert outcome["ended"] - cancelled < 1.0
        assert readers.alive == 1
        assert multiprocessing.active_children() == []
        assert not (tmp_path / "started").exists()
    finally:
        readers.give()
    assert readers.alive == 0


def test_a_cancel_set_before_the_read_starts_no_child() -> None:
    cancel = threading.Event()
    cancel.set()
    readers = isolate.Readers(1)
    stopped = isolate.run(
        targets.pages_then_rest,
        (1, 0.0, 0.0),
        memory=GiB,
        step_seconds=60,
        readers=readers,
        cancel=cancel,
    )
    assert stopped == isolate.Stopped("cancelled")
    assert readers.most == 0


def test_a_cancelled_pdf_read_is_not_a_damaged_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance test of #344 for extraction: ReadCancelled, never an ExtractionError."""
    monkeypatch.setattr(pdf, "_read_file", targets.hanging_read)
    readers = isolate.Readers(2)
    monkeypatch.setattr(pdf, "_READERS", readers)
    path = tmp_path / "book.pdf"
    path.write_bytes(PAPER.read_bytes())
    cancel = threading.Event()
    thread, outcome = in_thread(lambda: extract_pdf(path, cancel=cancel))
    wait_for(tmp_path / "started", thread)
    cancel.set()
    thread.join(10)
    error = outcome["error"]
    assert type(error) is ReadCancelled
    assert not isinstance(error, ExtractionError)
    assert str(error) == "book.pdf: the read was cancelled"
    assert multiprocessing.active_children() == []
    assert readers.alive == 0


def test_a_pdf_read_with_its_cancel_set_raises_at_once() -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ReadCancelled):
        extract_pdf(PAPER, cancel=cancel)


# ---- Ctrl-C on a terminal reaches the child too (#344, PR #366, D-628) -------------------


posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="a console's Ctrl-C cannot be sent to one child on Windows"
)


@posix_only
@pytest.mark.parametrize("from_the_start", [True, False], ids=["while-starting", "on-a-page"])
def test_a_sigint_to_the_child_leaves_the_cancel_to_the_parent(
    tmp_path: Path, from_the_start: bool
) -> None:
    """The child ignores SIGINT: only the parent's cancel ends it, so the read ends as
    cancelled, never as a reader that could not start or a damaged file. On 766d56a a
    SIGINT while starting gave Stopped("ended", "starting"), and one on a page raised
    KeyboardInterrupt here."""
    readers = isolate.Readers(1)
    cancel = threading.Event()
    stop = threading.Event()
    started = tmp_path / "started"
    if from_the_start:
        targets.sigint_children(stop)  # from before the child exists to the cancel
    thread, outcome = in_thread(
        lambda: isolate.run(
            targets.page_then_hang,
            (str(tmp_path), 30),
            memory=GiB,
            step_seconds=60,
            readers=readers,
            cancel=cancel,
        )
    )
    try:
        wait_for(started, thread)
        if not from_the_start:
            targets.sigint_children(stop)
        time.sleep(0.3)  # signals land on the page step too
        assert thread.is_alive(), outcome  # no SIGINT ended the read
        cancel.set()
        thread.join(10)
    finally:
        stop.set()
    assert outcome.get("result") == isolate.Stopped("cancelled", "page 1 of 1"), outcome
    assert multiprocessing.active_children() == []
    assert readers.alive == 0
