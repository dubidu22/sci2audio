"""Work for the PDF reader child in the progress and cancel tests (#343, #344).

The child imports this module by name, so it imports nothing heavy (not pytest, not the test
modules): a child then starts quickly on every system (#345). `sigint_children` runs in the
test process.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import signal
import threading
import time
from pathlib import Path

from sci2audio.extraction import isolate


def pages_then_rest(count: int, pause: float, rest: float) -> int:
    """Report `count` pages, `pause` seconds each, then wait `rest` seconds."""
    for number in range(1, count + 1):
        isolate.report(f"page {number} of {count}")
        time.sleep(pause)
    time.sleep(rest)
    return count


def page_then_hang(folder: str, seconds: float) -> str:
    """Report one page, mark the start in `folder`, then hang for `seconds`."""
    isolate.report("page 1 of 1")
    Path(folder, "started").write_text(str(os.getpid()))
    time.sleep(seconds)
    Path(folder, "finished").write_text("")
    return "finished"


def hanging_read(path: str, limits: dict[str, int]) -> str:
    """In place of `pdf._read_file`: a read that hangs on its first page, marked next to
    the file."""
    return page_then_hang(str(Path(path).parent), 30)


def sigint_children(stop: threading.Event) -> threading.Thread:
    """Send a real SIGINT to each reader child every 10 ms until `stop` is set, as a
    terminal's Ctrl-C reaches every process of its group."""

    def press() -> None:
        while not stop.is_set():
            for child in multiprocessing.active_children():
                if child.pid is not None:
                    with contextlib.suppress(OSError):  # it just ended
                        os.kill(child.pid, signal.SIGINT)
            time.sleep(0.01)

    thread = threading.Thread(target=press, daemon=True)
    thread.start()
    return thread
