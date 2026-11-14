"""The language a file states, normalised by extraction (#237, D-513 to D-515).

A PDF's /Lang, an EPUB's dc:language and Markdown's `lang` reach `Metadata.language` as one
BCP 47 tag or "": "_" becomes "-", white space goes, "und", "zxx", "mul", "mis" and values
that are not tags state nothing, and "eng", "deu", "ger" become "en" and "de". So layout's
guess and its English/German override (#219, D-496) see every stated tag.
"""

from __future__ import annotations

import re

import pytest
from epub_maker import make_epub
from hypothesis import given
from hypothesis import strategies as st
from pdf_maker import raw_pdf, stream

from sci2audio.app import language_warning
from sci2audio.core import LanguageSource
from sci2audio.extraction import read_epub, read_markdown, read_pdf
from sci2audio.extraction.language import stated_language
from sci2audio.layout import build_document

pytestmark = pytest.mark.timeout(60)


@pytest.mark.parametrize(
    ("raw", "stated"),
    [
        ("en-GB", "en-GB"),
        ("de", "de"),
        ("EN", "EN"),  # letter case is kept as written
        ("en_US", "en-US"),
        ("de_DE", "de-DE"),
        ("  de-AT \n", "de-AT"),
        ("zh-Hant-TW", "zh-Hant-TW"),
        ("und", ""),
        ("UND", ""),
        ("und-DE", ""),
        ("zxx", ""),
        ("mul", ""),
        ("mis", ""),
        ("x-default", ""),
        ("i-klingon", ""),
        ("German", ""),
        ("en-", ""),
        ("en--US", ""),
        ("en US", ""),
        ("", ""),
        ("eng", "en"),
        ("deu", "de"),
        ("ger", "de"),
        ("GER-DE", "de-DE"),
        ("fra", "fra"),  # other three-letter codes are left as written
    ],
)
def test_a_stated_tag_is_normalised(raw: str, stated: str) -> None:
    assert stated_language(raw) == stated


SHAPED = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{1,8})*")


@given(st.text())
def test_any_value_gives_a_tag_or_nothing_and_is_stable(raw: str) -> None:
    stated = stated_language(raw)
    assert stated == "" or SHAPED.fullmatch(stated)
    assert stated_language(stated) == stated
    assert stated.split("-")[0].lower() not in {"und", "zxx", "mul", "mis", "eng", "deu", "ger"}


# German running text without umlauts, so a Type 1 font with the standard encoding prints it:
# 26 German common words, no English one.
GERMAN = (
    "Die Studie zeigt, dass die Ergebnisse mit der Zeit nicht schlechter werden.",
    "Wir haben die Daten von zwei Gruppen in einer Tabelle gesammelt und sie dann",
    "mit den Werten aus dem letzten Jahr verglichen. Dabei ist zu sehen, dass sich",
    "die Zahlen kaum bewegen, auch wenn die Gruppen nicht gleich gross sind.",
)


def german_pdf(lang: bytes) -> bytes:
    """One page of German prose whose catalog states `/Lang (lang)`."""
    lines = b" ".join(b"(" + line.encode("ascii") + b") Tj 0 -14 Td" for line in GERMAN)
    return raw_pdf(
        {
            1: b"<< /Type /Catalog /Pages 2 0 R /Lang (" + lang + b") >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400]"
            b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            4: stream(b"BT /F1 10 Tf 40 340 Td " + lines + b" ET"),
            5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def test_a_german_pdf_tagged_en_us_with_an_underscore_is_read_in_german() -> None:
    """Issue #237: "en_US" was taken as a language of its own and the file won."""
    content = read_pdf(german_pdf(b"en_US"), "studie.pdf")
    assert content.metadata.language == "en-US"
    document = build_document(content)
    assert (document.language, document.language_source) == ("de", LanguageSource.TEXT)
    warning = language_warning(document)
    assert warning is not None
    assert warning.startswith("The file says its language is en-US, but its text is German")


def test_a_german_pdf_tagged_und_is_guessed_german_without_a_warning() -> None:
    content = read_pdf(german_pdf(b"und"), "studie.pdf")
    assert content.metadata.language == ""
    document = build_document(content)
    assert (document.language, document.language_source) == ("de", LanguageSource.TEXT)
    assert language_warning(document) is None


def test_a_german_pdf_tagged_ger_states_german() -> None:
    document = build_document(read_pdf(german_pdf(b"ger"), "studie.pdf"))
    assert (document.language, document.language_source) == ("de", LanguageSource.FILE)


@pytest.mark.parametrize(("lang", "stated"), [("en_GB", "en-GB"), ("und", ""), ("deu", "de")])
def test_markdown_front_matter_states_a_normalised_tag(lang: str, stated: str) -> None:
    content = read_markdown(f"---\ntitle: T\nlang: {lang}\n---\n\nText.\n".encode(), "n.md")
    assert content.metadata.language == stated


def test_an_epub_states_its_first_language_that_names_one() -> None:
    """dc:language "und" states nothing, so the next one counts."""
    metadata = (
        "<dc:title>T</dc:title><dc:language>und</dc:language><dc:language>de_CH</dc:language>"
    )
    content = read_epub(make_epub("<p>x</p>", metadata=metadata), "b.epub")
    assert content.metadata.language == "de-CH"
    nothing = "<dc:title>T</dc:title><dc:language>x-default</dc:language>"
    assert read_epub(make_epub("<p>x</p>", metadata=nothing), "b.epub").metadata.language == ""
