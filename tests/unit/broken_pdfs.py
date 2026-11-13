"""The PDFs extraction refuses since #5, each with its exact message, for the extraction
tests and the web tests (D-393 to D-398). `{name}` stands for the file's name."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pdf_maker import (
    Rect,
    dense_pdf,
    image_only_pdf,
    make_pdf,
    one_page_pdf,
    owner_locked_pdf,
    page_tree_bomb,
    protected_pdf,
)

CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "papers"
LIU = CORPUS / "arxiv2024-liu-orbital-hall.pdf"  # its xref is at the end: PDFium rebuilds it
HARDT = CORPUS / "acl2023-hardt-ellipsis.pdf"  # PDFium can't open it once cut

ALL = 0xFFFFFFFC  # every permission (bits 1 and 2 are reserved as 0)
COPY, ACCESSIBILITY = 1 << 4, 1 << 9

NO_TEXT = (
    "{name}: the PDF holds no text; a scanned PDF needs text recognition,"
    " which sci2audio can't do yet"
)
CUT_SHORT = "{name}: the PDF is cut short (an unfinished download?); download it again"
PROTECTED = (
    "{name}: the PDF is protected by DRM or a certificate; sci2audio can read only PDFs without it"
)
OWNER = (
    "{name}: the PDF's owner does not allow its text to be read out;"
    " ask for a copy without this restriction"
)
TOO_LARGE = "{name}: the PDF is too large or damaged ({detail})"


def cut(path: Path, share: float) -> bytes:
    data = path.read_bytes()
    return data[: int(len(data) * share)]


def unloadable_second_page() -> bytes:
    """Two pages, the second of which is the page tree itself: PDFium can't load it."""
    pdf = one_page_pdf()
    return pdf.replace(b"/Kids [3 0 R] /Count 1", b"/Kids [3 0 R 2 0 R] /Count 2")


@dataclass(frozen=True)
class Refused:
    id: str
    make: Callable[[], bytes]
    message: str  # with {name}

    def expected(self, name: str) -> str:
        return self.message.format(name=name)


REFUSED = (
    Refused("scan-without-text", image_only_pdf, NO_TEXT),
    Refused("blank-pages", lambda: make_pdf([], []), NO_TEXT),
    Refused("only-drawings", lambda: make_pdf([Rect(50, 50, 300, 300)]), NO_TEXT),
    Refused(
        "page-tree-bomb",
        lambda: page_tree_bomb(14),  # 16,384 pages from 2 KB
        TOO_LARGE.replace("{detail}", "more than 10,000 pages"),
    ),
    Refused(
        "page-of-too-many-characters",
        lambda: dense_pdf(1, 100_001),  # 1 KB
        TOO_LARGE.replace("{detail}", "page 1 holds more than 100,000 characters"),
    ),
    Refused("cut-short-rebuilt-by-pdfium", lambda: cut(LIU, 0.9), CUT_SHORT),
    Refused("cut-short-by-one-thousandth", lambda: cut(LIU, 0.999), CUT_SHORT),
    Refused("cut-short-pdfium-cannot-open", lambda: cut(HARDT, 0.75), CUT_SHORT),
    Refused("drm-plug-in", lambda: protected_pdf(b"/FOPN_foweb /V 2 /Length 40"), PROTECTED),
    Refused(
        "certificate",
        lambda: protected_pdf(b"/Adobe.PubSec /SubFilter /adbe.pkcs7.s4 /V 4 /Recipients [<00>]"),
        PROTECTED,
    ),
    Refused(
        "owner-forbids-copying-and-accessibility",
        lambda: owner_locked_pdf("A made-up paper", ALL & ~COPY & ~ACCESSIBILITY),
        OWNER,
    ),
    Refused(
        "owner-forbids-copying-revision-2",  # revision 2 has no accessibility bit
        lambda: owner_locked_pdf("A made-up paper", ALL & ~COPY, revision=2),
        OWNER,
    ),
    Refused(
        "unloadable-page",
        unloadable_second_page,
        "{name}: the PDF is damaged (page 2 cannot be read)",
    ),
)
