"""Extraction: record what a PDF, EPUB, Markdown or text file holds as `core.Content` (D-63).

Pipeline stage; may import only ``sci2audio.core``. Extraction decides nothing: reading order,
headings and page furniture are the layout stage's work. A book's cover image is offered
apart from the content, per format (D-313). `legibility` measures how readable each page's
text is, for the app to decide on (#442).
"""

from sci2audio.extraction.cover import Cover
from sci2audio.extraction.epub import extract_epub, extract_epub_cover, read_epub
from sci2audio.extraction.errors import ExtractionError, ReadCancelled
from sci2audio.extraction.legibility import PageLegibility, legibility
from sci2audio.extraction.markdown import extract_markdown, read_markdown
from sci2audio.extraction.pdf import extract_pdf, extract_pdf_cover, read_pdf
from sci2audio.extraction.text import extract_text, read_text

__all__ = [
    "Cover",
    "ExtractionError",
    "PageLegibility",
    "ReadCancelled",
    "extract_epub",
    "extract_epub_cover",
    "extract_markdown",
    "extract_pdf",
    "extract_pdf_cover",
    "extract_text",
    "legibility",
    "read_epub",
    "read_markdown",
    "read_pdf",
    "read_text",
]
