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
import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Iterator
from multiprocessing import resource_tracker
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
        # clock-bound: the wait loop's way out after 60 s; what it waits for is far quicker
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
    # With the parent's limit broken, the child's own watch still stops the step at 2 x 1.0 s
    # with the same result, so a bound at or above 2 s would hide that bug.
    # clock-bound: 1.5 s must stay below the child's 2 s watch; timed before the join (#366)
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
    # clock-bound: a cancel that is not watched waits out the 30 s hang; the watch takes 0.1 s
    assert outcome["ended"] - cancelled < 5.0
    assert multiprocessing.active_children() == []
    assert readers.alive == 0
    began = time.monotonic()
    assert (
        isolate.run(
            targets.pages_then_rest, (1, 0.0, 0.0), memory=GiB, step_seconds=60, readers=readers
        )
        == 1
    )
    # clock-bound: it did not wait for the cancelled read's 30 s
    assert time.monotonic() - began < 30
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
        # clock-bound: an unwatched cancel waits for the slot until it frees; the watch takes 0.1 s
        assert outcome["ended"] - cancelled < 5.0
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


@posix_only
def test_a_sigint_sent_while_the_child_starts_waits_held_back_and_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The child's first line of our code finds SIGINT held back and the SIGINT sent during
    its start waiting there; `_child` drops it and the read gives its result (#803). No
    timing: the child waits for the SIGINT before it goes on."""
    monkeypatch.setattr(isolate, "_child", targets.first_line)
    stop = threading.Event()
    targets.sigint_children(stop)  # from before the child exists to its end
    try:
        result = isolate.run(
            targets.both,
            (targets.WAIT_FOR_A_SIGINT,),
            memory=GiB,
            step_seconds=60,
            readers=isolate.Readers(1),
        )
    finally:
        stop.set()
    assert result == (True, True)  # held back, waiting, and the child lived on


class _TrackerOf3128:
    """`signal` as the resource tracker of Python 3.12.0 to 3.12.8 used it: after starting
    its process it unblocked SIGINT in the calling thread instead of restoring that thread's
    mask (fixed in 3.12.9 by gh-127586)."""

    def __getattr__(self, name: str) -> Any:
        return getattr(signal, name)

    @staticmethod
    def pthread_sigmask(how: int, mask: Any) -> set[signal.Signals]:
        if how == signal.SIG_SETMASK:  # 3.12.8: SIG_UNBLOCK of SIGINT and SIGTERM
            return signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT, signal.SIGTERM})
        return signal.pthread_sigmask(how, mask)


@posix_only
def test_a_resource_tracker_started_with_the_first_child_keeps_sigint_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#803: the first reader child of a program also starts multiprocessing's resource
    tracker, inside `child.start()`. On Python 3.12.0 to 3.12.8 that start unblocked SIGINT
    in the starting thread, so the child was spawned without SIGINT held back, and a SIGINT
    in its first moments (before Python sets its own handler) ended it at once, silently:
    the "ended" in 1 of 20 tries that #803 is about. The tracker now starts before SIGINT is
    held.
    No timing: the child reports its mask at its first line."""
    tracker = resource_tracker.ResourceTracker()  # not yet started, as in a fresh program
    monkeypatch.setattr(resource_tracker, "signal", _TrackerOf3128())
    monkeypatch.setattr(resource_tracker, "ensure_running", tracker.ensure_running)
    monkeypatch.setattr(resource_tracker, "getfd", tracker.getfd)
    monkeypatch.setattr(isolate, "_child", targets.first_line)
    try:
        result = isolate.run(
            targets.both, (), memory=GiB, step_seconds=60, readers=isolate.Readers(1)
        )
    finally:
        tracker._stop()  # type: ignore[attr-defined]
    assert result == (True, False)  # SIGINT held back at the child's first line


# ---- another thread takes the child's end (#440) --------------------------------------------


@posix_only
@pytest.mark.parametrize("cancelled", [True, False], ids=["cancelled", "finished"])
def test_a_child_whose_end_another_thread_took_is_not_closed_as_running(
    monkeypatch: pytest.MonkeyPatch, cancelled: bool
) -> None:
    """multiprocessing reaps each child it finds ended (`os.waitpid`) in
    `active_children()`, as `sigint_children` calls it, and in every `Process.start()`, as a
    second read starts its child; it notes the exit code only a moment later. A read ending
    in that moment found no child left to wait for: `join()` returned with no exit code and
    `close()` took the ended child for a running one, so the read raised "Cannot close a
    process while it is still running" in place of its result (#440, twice on Linux CI). No
    timing: the end is taken between the read's last word and its clean-up."""
    wait = isolate._wait
    cancel = threading.Event()
    taken: dict[str, Any] = {}
    signalled: list[str] = []

    def end_taken_by_another_thread(child: Any, *rest: Any) -> Any:
        if cancelled:
            cancel.set()
        result = wait(child, *rest)
        # what the other thread does before it notes the code
        _, status = os.waitpid(child.pid, 0)
        taken.update(child=child, code=os.waitstatus_to_exitcode(status))
        monkeypatch.setattr(child, "kill", lambda: signalled.append("kill"))
        return result

    monkeypatch.setattr(isolate, "_wait", end_taken_by_another_thread)
    readers = isolate.Readers(1)
    try:
        result = isolate.run(
            targets.pages_then_rest,
            (1, 0.0, 0.0),
            memory=GiB,
            step_seconds=60,
            readers=readers,
            cancel=cancel,
        )
    finally:
        if "child" in taken and taken["child"]._popen is not None:
            taken["child"]._popen.returncode = taken["code"]  # ... and then notes it
    assert result == (isolate.Stopped("cancelled", "starting") if cancelled else 1)
    assert signalled == []  # its pid is free: a signal could reach another process
    assert readers.alive == 0
    assert multiprocessing.active_children() == []


# ---- a child that ends while starting, as a Ctrl-C ends it (#367) ---------------------------


@pytest.fixture
def ends_while_starting(tmp_path: Path) -> Iterator[Callable[..., Any]]:
    yield targets.ends_while_starting(tmp_path)
    targets.forget_ends_while_starting(tmp_path)


def test_a_child_ended_while_starting_by_a_cancelled_read_is_cancelled(
    tmp_path: Path, ends_while_starting: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl-C can end the child during its start (on Windows, which has no signal mask, or
    on POSIX wherever the hold fails, as it did on Python 3.12.0 to 3.12.8, #803) and
    reach the parent's cancel only a moment later: the read is cancelled, not a reader that
    could not start. Before #367 it ended as Stopped("ended", "starting"). Runs on every
    system."""
    monkeypatch.setattr(isolate, "_CANCEL_GRACE_SECONDS", 30.0)  # a busy machine is slow
    cancel = threading.Event()
    targets.cancel_once_ended(tmp_path, cancel)
    readers = isolate.Readers(1)
    stopped = isolate.run(
        ends_while_starting, (), memory=GiB, step_seconds=60, readers=readers, cancel=cancel
    )
    assert (tmp_path / "ended").exists()
    assert stopped == isolate.Stopped("cancelled", "starting")
    assert readers.alive == 0


def test_a_child_ended_while_starting_with_no_cancel_still_ended(
    ends_while_starting: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grace for a cancel is a short wait, not a guess: no cancel, no cancelled read."""
    monkeypatch.setattr(isolate, "_CANCEL_GRACE_SECONDS", 0.05)
    stopped = isolate.run(
        ends_while_starting,
        (),
        memory=GiB,
        step_seconds=60,
        readers=isolate.Readers(1),
        cancel=threading.Event(),
    )
    assert stopped == isolate.Stopped("ended", "starting")
