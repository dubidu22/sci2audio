"""Shared data objects: the contract between the pipeline stages (D-46, D-63).

How a file flows through them: extraction records `Content` (pages with text lines, styled
runs, pictures and drawings, each with its position) and decides nothing; the layout stage
builds the reading document from it; text steps propose marked edits (D-57); the voice and
output point back at the original text for chapters and read-along (OU-02).

Lowest layer: standard library only, imports nothing else from sci2audio.
"""

from sci2audio.core.content import (
    Box,
    Content,
    Drawing,
    Item,
    Metadata,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.core.export import from_data, to_data

__all__ = [
    "Box",
    "Content",
    "Drawing",
    "Item",
    "Metadata",
    "Page",
    "Picture",
    "Source",
    "SourceFormat",
    "TextLine",
    "TextRun",
    "from_data",
    "to_data",
]
