"""Shared data objects (document, spans, edits, audio chunks).

The contract between the pipeline stages (D-46). How a paper flows through them: extraction
builds a `Document` of `Block`s, each with its `Origin` in the source; text steps return
`Edit`s on `Span`s and never change the text (D-57); the app applies the accepted edits with
`apply_edits` to get the listening script as `ScriptPiece`s; the voice returns `AudioChunk`s
that point back at their spans, which output uses for chapters and read-along timing (OU-02).

Lowest layer: standard library only, imports nothing else from sci2audio.
"""

from sci2audio.core.audio import AudioChunk
from sci2audio.core.document import (
    Block,
    BlockKind,
    Document,
    Metadata,
    Origin,
    Region,
    Section,
    Source,
    SourceFormat,
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
    "AudioChunk",
    "Block",
    "BlockKind",
    "Document",
    "Edit",
    "EditKind",
    "Metadata",
    "Origin",
    "OverlappingEditsError",
    "Region",
    "ScriptPiece",
    "Section",
    "Source",
    "SourceFormat",
    "Span",
    "SpanError",
    "apply_edits",
    "check_edits",
    "from_data",
    "to_data",
]
