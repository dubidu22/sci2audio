"""The one error extraction raises for a file it cannot read."""

from __future__ import annotations


class ExtractionError(Exception):
    """A file that cannot be read, with a message a user can act on."""
