"""Small documents with sections and a title, for the app tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from sci2audio.core import Document, Metadata, Section
from sci2audio.testing import make_document
from sci2audio.testing.documents import BlockLike


def document_with(
    blocks: Iterable[BlockLike],
    sections: tuple[Section, ...] = (),
    *,
    title: str = "",
    name: str = "paper.pdf",
    language: str = "en",
) -> Document:
    """A one-page document of these blocks, with this section tree and metadata title."""
    made = make_document(blocks, language, name)
    content = replace(made.content, metadata=Metadata(title=title))
    return Document(content=content, language=language, blocks=made.blocks, sections=sections)
