"""Layout: the extracted `Content` in reading order as a `Document` (D-63, Issue #21).

Pipeline stage between extraction and text preparation; may import only ``sci2audio.core``.
Layout decides what extraction only records: page furniture, columns and reading order (and,
in later steps, paragraphs, headings, footnotes, captions and the section tree).
"""

from sci2audio.layout.build import build_document
from sci2audio.layout.settings import LayoutSettings

__all__ = ["LayoutSettings", "build_document"]
