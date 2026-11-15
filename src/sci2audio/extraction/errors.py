"""The errors extraction raises: for a file it cannot read, and for a read that was cancelled."""

from __future__ import annotations


class ExtractionError(Exception):
    """A file that cannot be read, with a message a user can act on."""


class ReadCancelled(Exception):
    """The read was cancelled before it ended (#344). Not an `ExtractionError`: nothing is
    wrong with the file."""
