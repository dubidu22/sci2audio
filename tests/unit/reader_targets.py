"""Work for the PDF reader child in the progress and cancel tests (#343, #344).

The child imports this module by name, so it imports nothing heavy (not pytest, not the test
modules): a child then starts quickly on every system (#345). `sigint_children` runs in the
test process.
"""

from __future__ import annotations

import contextlib
import importlib
import multiprocessing
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


ENDS_WHILE_STARTING = """
import multiprocessing, os
from pathlib import Path

# in the reader child, importing this module is part of its start (the target is unpickled
# before the child runs any of isolate's code): it ends there, as a Ctrl-C would end it
if multiprocessing.current_process().name == "sci2audio-reader":
    Path(__file__).with_name("ended").write_text("")
    os._exit(1)


def never_runs(*args):
    raise AssertionError("the child ended while starting")
"""


def ends_while_starting(folder: Path) -> Callable[..., Any]:
    """A target whose child ends during its start, before its first word, and marks that
    in `folder` ("ended"). The caller removes `folder` from `sys.path` and the module from
    `sys.modules` (`forget_ends_while_starting`)."""
    (folder / "ends_while_starting.py").write_text(ENDS_WHILE_STARTING)
    sys.path.insert(0, str(folder))
    sys.modules.pop("ends_while_starting", None)
    importlib.invalidate_caches()
    return importlib.import_module("ends_while_starting").never_runs  # type: ignore[no-any-return]


def forget_ends_while_starting(folder: Path) -> None:
    sys.modules.pop("ends_while_starting", None)
    with contextlib.suppress(ValueError):
        sys.path.remove(str(folder))


def cancel_once_ended(folder: Path, cancel: threading.Event) -> threading.Thread:
    """Set `cancel` once the child marked its end in `folder`: a Ctrl-C that ended the child
    while starting and reaches the parent's cancel a moment later."""

    def watch() -> None:
        deadline = time.monotonic() + 60
        while not Path(folder, "ended").exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        cancel.set()

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread
