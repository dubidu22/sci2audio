"""Whether a PDF's text can be read aloud: the app's decision on extraction's measures
(#442 part B, #187; policy D-762, docs/unreadable-pdf-text.md).

A PDF whose fonts lost every Unicode source gives the fonts' glyph numbers as text ("Das
Buch" reads "'DV %XFK"), and voicing it is minutes of nonsense. `extraction.legibility`
measures each page and says which are unreadable; this module decides what the jobs do:

- when the unreadable pages hold more than half of the document's characters (white space
  not counted), the audio job stops before the voice and writes nothing (`stops`);
- otherwise every unreadable page is named in a warning of the report.

PDF only (D-772): a page is a printed page only there; an EPUB's "page" is one of its files
and a text file is one page, and their text comes from the file's own letters, not from a
font.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sci2audio.core import Content, SourceFormat
from sci2audio.extraction import legibility


@dataclass(frozen=True)
class Unreadable:
    """The pages whose text can't be read, and whether the document stops for them."""

    pages: tuple[int, ...]  # `Page.number`: 1 = the first page, as a PDF viewer counts
    stops: bool  # they hold more than half of the document's characters

    def __post_init__(self) -> None:
        if not self.pages:
            raise ValueError("an Unreadable names at least one page")


def unreadable(content: Content) -> Unreadable | None:
    """The unreadable pages of a PDF, or None when there are none (or it is no PDF)."""
    if content.source.format is not SourceFormat.PDF:
        return None
    measured = legibility(content)
    pages = tuple(page.number for page in measured if page.unreadable)
    if not pages:
        return None
    total = sum(page.characters for page in measured)
    bad = sum(page.characters for page in measured if page.unreadable)
    return Unreadable(pages, stops=2 * bad > total)


def pages_named(pages: Iterable[int]) -> str:
    """For the app's English messages: "page 4", or "pages " and the ranges."""
    numbers = set(pages)
    return f"{'page' if len(numbers) == 1 else 'pages'} {page_ranges(numbers)}"


def stop_message(name: str, found: Unreadable) -> str:
    """Why the audio job stops (UnreadableTextError), naming the pages."""
    return (
        f"{name}: the text of {pages_named(found.pages)} cannot be read: the PDF's fonts "
        "give glyph numbers or wrong letters there, so the voice would read nonsense; "
        "no audiobook is made from it"
    )


def warning(found: Unreadable) -> str:
    """The report's warning (#187), naming the pages."""
    where = pages_named(found.pages)
    if found.stops:
        return (
            f"The text of {where} cannot be read: the PDF's fonts give glyph "
            "numbers or wrong letters there. That is most of the document, so no audiobook is "
            "made from it."
        )
    return (
        f"The text of {where} cannot be read: the PDF's fonts give glyph numbers "
        "or wrong letters there, so the voice would read nonsense. Leave the chapters on "
        "those pages out."
    )


def page_ranges(pages: Iterable[int]) -> str:
    """Page numbers as people write them, "1-3, 7" with an en dash: a run of three or more
    as a range, a run of two as "4, 5"."""
    numbers = sorted(set(pages))
    parts: list[str] = []
    start = 0
    for i in range(1, len(numbers) + 1):
        if i == len(numbers) or numbers[i] != numbers[i - 1] + 1:
            run = numbers[start:i]
            if len(run) >= 3:
                parts.append(f"{run[0]}\N{EN DASH}{run[-1]}")
            else:
                parts.extend(str(n) for n in run)
            start = i
    return ", ".join(parts)
