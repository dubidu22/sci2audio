"""Work for the PDF reader child in the progress and cancel tests (#343, #344).

The child imports this module by name, so it imports nothing heavy (not pytest, not the test
modules): a child then starts quickly on every system (#345).
"""

from __future__ import annotations

import os
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
