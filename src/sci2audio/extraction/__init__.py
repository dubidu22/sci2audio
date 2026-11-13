"""Extraction: record what a PDF, EPUB, Markdown or text file holds as `core.Content` (D-63).

Pipeline stage; may import only ``sci2audio.core``. Extraction decides nothing: reading order,
headings and page furniture are the layout stage's work. A book's cover image is offered
apart from the content, per format (D-313).
"""

from sci2audio.extraction.cover import Cover
from sci2audio.extraction.epub import extract_epub, extract_epub_cover, read_epub
from sci2audio.extraction.errors import ExtractionError
from sci2audio.extraction.pdf import extract_pdf, extract_pdf_cover, read_pdf

__all__ = [
    "Cover",
    "ExtractionError",
    "extract_epub",
    "extract_epub_cover",
    "extract_pdf",
    "extract_pdf_cover",
    "read_epub",
    "read_pdf",
]
