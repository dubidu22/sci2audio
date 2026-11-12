"""Extraction: record what a PDF, EPUB, Markdown or text file holds as `core.Content` (D-63).

Pipeline stage; may import only ``sci2audio.core``. Extraction decides nothing: reading order,
headings and page furniture are the layout stage's work.
"""

from sci2audio.extraction.pdf import ExtractionError, extract_pdf, read_pdf

__all__ = ["ExtractionError", "extract_pdf", "read_pdf"]
