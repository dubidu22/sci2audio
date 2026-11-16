"""Citation pairs and page brackets, a join word or full stop after a removed link, and
subject nests and year shells around several citations: the second textprep batch of v1.2,
PR 3 (#257, #258, #372, #375; D-668). Every row is read by the whole chain, and a second run
reads it the same."""

import re

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text


def read_all(text: str, language: str = "en") -> str:
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    script = run_steps(document, StepContext(language), strict=True).script()
    again = rebuilt_from_script(document, script)
    second = run_steps(again, StepContext(language), strict=True).script()
    first = spoken_text(script, show_pauses=True)
    assert spoken_text(second, show_pauses=True) == first, (text, first)
    return first


# ---- #257 a bracket that would go, joined to one the sentence needs ------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "Between [1] and [3] it lies.", "Between references 1 and 3 it lies."),
        ("en", "Between [1] and [3].", "Between references 1 and 3."),
        ("en", "noise [12] and [13] here.", "noise references 12 and 13 here."),
        ("en", "Between [1] and [3, 4] it lies.", "Between references 1, 3 and 4 it lies."),
        ("en", "Between [1, 2] and [3] it lies.", "Between references 1, 2 and 3 it lies."),
        ("en", "Between [1] and [3\u20135] it lies.", "Between references 1 and 3 to 5 it lies."),
        ("de", "Zwischen [1] und [3] liegt es.", "Zwischen Quellen 1 und 3 liegt es."),
        # only "and" / "und" join a pair; two brackets the sentence needs read as before
        ("en", "It holds [1] or [3] here.", "It holds or reference 3 here."),
        ("de", "Zwischen [1] oder [3] liegt es.", "Zwischen oder Quelle 3 liegt es."),
        ("en", "It was shown in [1] and [3].", "It was shown in reference 1 and reference 3."),
        ("en", "[1] and [3] show it.", "Reference 1 and reference 3 show it."),
        # a partner that is no citation, a number glued on, a German decimal interval
        ("en", "Between [1] and [x] it lies.", "Between and [x] it lies."),
        ("en", "Between [1] and [MH17] it lies.", "Between and [MH17] it lies."),
        ("en", "Between [1] and [0.5, 1.5] it lies.", "Between and [0.5, 1.5] it lies."),
        ("en", "Between [1] and [3]2 it lies.", "Between and [3]2 it lies."),
        (
            "de",
            "Zwischen [1] und [1,5; 2,5] liegt es.",
            "Zwischen und [1 Komma 5; 2 Komma 5] liegt es.",
        ),
    ],
)
def test_a_pair_of_citations_reads_as_one(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Between [MH17] and [Fa14] it lies.", "Between references MH17 and Fa14 it lies."),
        # a key and a number are no pair
        ("Between [MH17] and [3] it lies.", "Between and reference 3 it lies."),
    ],
)
def test_a_pair_of_listed_keys_reads_as_one(printed: str, said: str) -> None:
    document = make_document(
        [
            (BlockKind.PARAGRAPH, printed),
            (BlockKind.HEADING, "References"),
            (BlockKind.PARAGRAPH, "[MH17] M. Maass and D. Herrmann. A tool. 2017."),
            (BlockKind.PARAGRAPH, "[Fa14] S. Fahl. Causes. 2014."),
        ]
    )
    script = run_steps(document, StepContext("en"), strict=True).script()
    assert spoken_text([piece for piece in script if piece.span.block == 0]) == said


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "In [12, p. 3] it is.", "In reference 12, page 3 it is."),
        ("en", "In [12, page 3] it is.", "In reference 12, page 3 it is."),
        ("en", "In [12, pp. 3-5] it is.", "In reference 12, pages 3 to 5 it is."),
        ("en", "This holds [12, pp. 3\u20135].", "This holds."),
        ("de", "In [12, S. 3] steht es.", "In Quelle 12, Seite 3 steht es."),
        ("de", "Wie in [12, Seite 3] steht es.", "Wie in Quelle 12, Seite 3 steht es."),
        ("de", "Das gilt [12, S. 3].", "Das gilt."),
        # several sources, a page that is no number, or a key the document does not list
        ("en", "This holds [12, p. 3; 14] here.", "This holds [12, p. 3; 14] here."),
        ("en", "In [12, p. 3a] it is.", "In [12, p. 3a] it is."),
        ("en", "In [MH17, p. 3] it is.", "In [MH17, p. 3] it is."),
    ],
)
def test_a_numeric_citation_with_a_page(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


# ---- #257 a join word after a link that went ----------------------------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "We thank https://x.org and Smith (2019).", "We thank Smith."),
        ("en", "We thank https://x.org or Smith.", "We thank Smith."),
        ("en", "We thank and https://x.org and Smith.", "We thank and Smith."),
        ("de", "Wir danken https://x.org und Müller (2019).", "Wir danken Müller."),
        ("de", "Wir danken https://x.org oder Müller.", "Wir danken Müller."),
        # only after a word and before a capital word, and only for a link that went alone
        ("en", "We use https://x.org and then run it.", "We use and then run it."),
        ("en", "We thank https://x.org and the authors.", "We thank and the authors."),
        ("en", "We thank, https://x.org and Smith.", "We thank, and Smith."),
        ("en", "We thank https://x.org and 3 others.", "We thank and 3 others."),
        ("en", "We downloaded it from https://x.org and ran it.", "We downloaded it and ran it."),
        ("en", "We downloaded it from https://x.org and Smith.", "We downloaded it and Smith."),
        # a join word before the link is #402's
        ("en", "We thank Smith and https://x.org here.", "We thank Smith and here."),
    ],
)
def test_a_join_word_after_a_removed_link(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


# ---- #258 the link's full stop after an abbreviation's ------------------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "Smith et al. https://x.org. Then more.", "Smith et al. Then more."),
        ("en", "Smith et al. https://x.org.", "Smith et al."),
        ("en", "Smith et al. https://x.org. then more.", "Smith et al. then more."),
        ("en", "The answer is in Fig. https://x.org. Then.", "The answer is in Fig. Then."),
        ("en", "See Smith et al. (https://x.org). Then more.", "See Smith et al. Then more."),
        (
            "de",
            "Wir zeigen das in Abb. https://x.org. Dann mehr.",
            "Wir zeigen das in Abb. Dann mehr.",
        ),
        # an abbreviation read with its full stop keeps the link's as the sentence end
        ("en", "We use e.g. https://x.org. Then more.", "We use for example. Then more."),
        (
            "de",
            "Daten finden sich u. a. unter https://x.org. Dann mehr.",
            "Daten finden sich unter anderem. Dann mehr.",
        ),
        ("en", "Smith et al. https://x.org.) Then more.", "Smith et al.) Then more."),
        ("en", "Fig. https://x.org. 3 shows it.", "Figure 3 shows it."),
        # read with its full stop ("Figure"), or right before the next link: as before
        ("en", "Fig. (https://x.org). Then more.", "Figure. Then more."),
        ("en", "Fig. https://x.org. https://x.org 3 shows it.", "Fig.. 3 shows it."),
        # no abbreviation: the link's full stop ends the sentence, as before
        ("en", "We use https://x.org. Then more.", "We use. Then more."),
    ],
)  # fmt: skip
def test_no_two_full_stops_after_an_abbreviation(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


# ---- the second run over all of them -------------------------------------------------------

_PIECES = st.sampled_from(
    [
        "[1]", "[3]", "[12, p. 3]", "[12, S. 3]", "[12, pp. 3\u20135]", "[3, 4]", "and", "und",
        "or", "https://x.org", "https://x.org.", "et al.", "Fig.", "Abb.", "u. a.", "e.g.", "Smith",
        "Müller", "(Smith, 2019)", "((Smith, 2019); (Lee, 2018); Jones, 2020)",
        "((Smith, 2019); (Lee, 2020) 2021)", "(Jones, 2020; (Smith, 2019))", "in", "from",
        "We", "thank", "Between", "Then", "Dann", "the", "it", "is cited", "here", ",", ";",
    ]
)  # fmt: skip


@given(st.lists(_PIECES, min_size=1, max_size=10), st.sampled_from(["en", "de"]))
def test_the_new_shapes_read_the_same_on_a_second_run(pieces: list[str], language: str) -> None:
    text = " ".join(pieces) + "."
    # an abbreviation right before a citation that goes reads differently on a second run
    # on main already ("Fig. ((Smith, 2019); Jones, 2020) Müller", #405)
    assume(not re.search(r"(?:al|Fig|Abb|a|e\.g)\.\s+[(\[]", text))
    read_all(text, language)
