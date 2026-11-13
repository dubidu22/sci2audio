"""Shared data objects: the contract between the pipeline stages (D-46, D-63).

How a file flows through them: extraction records `Content` (pages with text lines, styled
runs, pictures and drawings, each with its position, and the file's own outline) and decides
nothing; the layout stage builds a `Document` of `Block`s in reading order, each pointing back
at the items it is made of; text steps return `Edit`s on `Span`s and never change the text
(D-57); the app applies the accepted edits with `apply_edits` to get the listening script as
`ScriptPiece`s; the voice returns `AudioChunk`s that point back at their spans, which output
uses for chapters and read-along timing (OU-02).

Lowest layer: standard library only, imports nothing else from sci2audio.
"""

from sci2audio.core.audio import AudioChunk
from sci2audio.core.content import (
    Box,
    Content,
    Drawing,
    Item,
    Metadata,
    OutlineEntry,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.core.document import (
    LABELLED_KINDS,
    Block,
    BlockKind,
    Document,
    FurnitureRole,
    Part,
    Section,
    Span,
    SpanError,
)
from sci2audio.core.edits import (
    Edit,
    EditKind,
    OverlappingEditsError,
    ScriptPiece,
    apply_edits,
    check_edits,
)
from sci2audio.core.export import from_data, to_data

__all__ = [
    "LABELLED_KINDS",
    "AudioChunk",
    "Block",
    "BlockKind",
    "Box",
    "Content",
    "Document",
    "Drawing",
    "Edit",
    "EditKind",
    "FurnitureRole",
    "Item",
    "Metadata",
    "OutlineEntry",
    "OverlappingEditsError",
    "Page",
    "Part",
    "Picture",
    "ScriptPiece",
    "Section",
    "Source",
    "SourceFormat",
    "Span",
    "SpanError",
    "TextLine",
    "TextRun",
    "apply_edits",
    "check_edits",
    "from_data",
    "to_data",
]
