"""What the programs print of Python's logging (#143, #1258).

With no handler set up, Python's last-resort handler prints every library's warning to
stderr, between sci2audio's own lines (pypdfium2 on a looped outline, for one). Each
entry point therefore decides once, at start-up: sci2audio's own warnings and errors, and
every library's errors, are printed as that handler printed them, the message alone; a
library's warnings are not. The pipeline stages never set this up; the reader's child
process hands what it logs to this process's logging (`extraction.isolate`), so the same
choice holds for it.
"""

from __future__ import annotations

import logging
import sys

OWN = "sci2audio"


class _OwnWarnings(logging.Handler):
    """sci2audio's records from a warning up and any other logger's from an error up, on
    the stderr of the moment, as Python's last-resort handler wrote them."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)

    def filter(self, record: logging.LogRecord) -> bool:
        ours = record.name == OWN or record.name.startswith(f"{OWN}.")
        # a library's warning is noise between our lines (#143); its error may be why a
        # job failed, so it stays the person's to see (#1258)
        shown = ours or record.levelno >= logging.ERROR
        return shown and bool(super().filter(record))

    def emit(self, record: logging.LogRecord) -> None:
        stream = sys.stderr  # looked up each time: a windowed build replaces it (#215)
        if stream is None:
            return
        try:
            stream.write(f"{self.format(record)}\n")
            stream.flush()
        except Exception:
            self.handleError(record)


def own_warnings_only() -> None:
    """Print sci2audio's own warnings and errors, and a library's errors but never its
    warnings. Once is enough; a second call changes nothing."""
    root = logging.getLogger()
    if not any(isinstance(handler, _OwnWarnings) for handler in root.handlers):
        root.addHandler(_OwnWarnings())
