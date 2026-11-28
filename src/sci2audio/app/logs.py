"""What the programs print of Python's logging (#143).

With no handler set up, Python's last-resort handler prints every library's warning to
stderr, between sci2audio's own lines (pypdfium2 on a looped outline, for one). Each
entry point therefore decides once, at start-up: sci2audio's own warnings and errors are
printed as that handler printed them, the message alone, and no other library's are. The
pipeline stages never set this up; a stage's child process prints nothing of its own.
"""

from __future__ import annotations

import logging
import sys

OWN = "sci2audio"


class _OwnWarnings(logging.Handler):
    """sci2audio's records from a warning up, on the stderr of the moment, as Python's
    last-resort handler wrote them; a record of any other logger is dropped."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)

    def filter(self, record: logging.LogRecord) -> bool:
        ours = record.name == OWN or record.name.startswith(f"{OWN}.")
        return ours and bool(super().filter(record))

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
    """Print sci2audio's own warnings and errors, and no library's. Once is enough; a second
    call changes nothing."""
    root = logging.getLogger()
    if not any(isinstance(handler, _OwnWarnings) for handler in root.handlers):
        root.addHandler(_OwnWarnings())
