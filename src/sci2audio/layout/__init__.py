"""Layout: the extracted `Content` in reading order as a `Document` (D-63, Issue #21).

Pipeline stage between extraction and text preparation; may import only ``sci2audio.core``.
Layout decides what extraction only records: page furniture, columns, reading order and
paragraphs, with lines that extraction split at a wide gap joined again, headings,
footnotes, captions, placeholders and the section tree. Documents without positions (EPUB,
Markdown, text) are read from their tags (`tagged`, #75). The document's language is the
job's setting, the file's own, or a guess from the text (`language`, #219).
"""

from sci2audio.layout.build import build_document
from sci2audio.layout.language import COMMON_WORDS, guess_language
from sci2audio.layout.settings import LayoutSettings

__all__ = ["COMMON_WORDS", "LayoutSettings", "build_document", "guess_language"]
