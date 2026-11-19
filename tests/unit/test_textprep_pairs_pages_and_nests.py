"""Citation pairs and page brackets, a join word or full stop after a removed link, and
subject nests and year shells around several citations: the second textprep batch of v1.2,
PR 3 (#257, #258, #372, #375; D-668); lists of citation brackets, every name of a subject
nest and a join word before a removed link: batch B9 (#414, #415, #402; D-791). Every row is
read by the whole chain, and a second run reads it the same."""

import re

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text
from sci2audio.textprep.citations import CitationStep
from sci2audio.textprep.links import LinkStep


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
        # only "and" / "und" join a pair
        ("en", "It holds [1] or [3] here.", "It holds or reference 3 here."),
        ("de", "Zwischen [1] oder [3] liegt es.", "Zwischen oder Quelle 3 liegt es."),
        # two brackets the sentence needs read once over both, as a needed list does (#414,
        # D-791; read "reference 1 and reference 3" before)
        ("en", "It was shown in [1] and [3].", "It was shown in references 1 and 3."),
        ("en", "[1] and [3] show it.", "References 1 and 3 show it."),
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
        # a join word before the link goes too when the link ends a list (#402, D-791; read
        # "We thank Smith and here." before)
        ("en", "We thank Smith and https://x.org here.", "We thank Smith here."),
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


# ---- #414 a list of citation brackets is one citation (B9, D-791) -------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # an aside list goes whole, as one bracket of a range does
        ("en", "It holds [1], [2] and [3] here.", "It holds here."),
        ("en", "It holds [1], [2], [3] and [4] here.", "It holds here."),
        ("en", "It holds [1], [2], and [3] here.", "It holds here."),
        ("en", "It holds [1, 2], [3] and [4] here.", "It holds here."),
        ("en", "It holds [2\u20136], [8] and [9].", "It holds."),
        ("en", "It holds [1], [2] and [3]. Then", "It holds. Then"),
        ("en", "It holds [1], [2], here.", "It holds, here."),
        ("de", "Es gilt [1], [2] und [3] hier.", "Es gilt hier."),
        # "and" anywhere in the list, or none
        ("en", "It holds [1] and [2], [3] here.", "It holds here."),
        (
            "en",
            "As shown in [1] and [2], [3], it holds.",
            "As shown in references 1, 2 and 3, it holds.",
        ),
        ("en", "It holds [1] and [2] and [3] here.", "It holds here."),
        ("en", "It holds [1], [2] here.", "It holds here."),
        ("en", "It holds [1],[2],[3] here.", "It holds here."),
        # a needed list is read once over all its brackets
        (
            "en",
            "As shown in [1], [2] and [3], it holds.",
            "As shown in references 1, 2 and 3, it holds.",
        ),
        (
            "en",
            "As shown in [1], [2], [3], it holds.",
            "As shown in references 1, 2 and 3, it holds.",
        ),
        (
            "en",
            "As shown in [1], [2], and [3], it holds.",
            "As shown in references 1, 2 and 3, it holds.",
        ),
        ("en", "As shown in [1] and [3], it holds.", "As shown in references 1 and 3, it holds."),
        (
            "en",
            "As shown in [1, 2], [3\u20135] and [9].",
            "As shown in references 1, 2, 3 to 5 and 9.",
        ),
        ("en", "[1], [2] and [3] show it.", "References 1, 2 and 3 show it."),
        ("en", "It holds. [1], [2] and [3] show it.", "It holds. References 1, 2 and 3 show it."),
        ("en", "Refs. [1], [2] and [3] show it.", "References 1, 2 and 3 show it."),
        ("en", "See Refs. [1], [2] and [3].", "See references 1, 2 and 3."),
        # the reading takes the place of "Refs." and the list goes, past a removal between
        (
            "en",
            "Refs. (see https://x.org) [1], [2] and [3] show it.",
            "References 1, 2 and 3 show it.",
        ),
        (
            "de",
            "Wie in [1], [2] und [3] gezeigt, gilt es.",
            "Wie in Quellen 1, 2 und 3 gezeigt, gilt es.",
        ),
        ("de", "[1], [2] und [3] zeigen es.", "Quellen 1, 2 und 3 zeigen es."),
        # "or" joins no list: as before (#414's second criterion; follow-up F1)
        ("en", "Between [1], [2] or [3] it lies.", "Between, or reference 3 it lies."),
        ("de", "Es gilt [1], [2] oder [3] hier.", "Es gilt, oder Quelle 3 hier."),
        # what is no item: a page, a bracket glued to a word, a number glued after, maths
        ("en", "It holds [12, p. 3], [4] and [5] here.", "It holds, references 4 and 5 here."),
        # a letter glued after the list stays glued, as after one bracket ("[3]x"); on main
        # the pair read "3x" on run 1 and "3 times" on run 2
        ("en", "It holds [1], [2] and [3]x here.", "It holdsx here."),
        ("en", "x \u2208 [0, 1], [2] and [3] here.", "x \u2208 [0, 1], references 2 and 3 here."),
        (
            "en",
            "CIs [1, 3], [2, 4] and [5, 6] hold.",
            "confidence intervals 1 to 3, 2 to 4 and 5 to 6 hold.",
        ),
        (
            "de",
            "Es gilt [1,2; 3,4], [5] und [6] hier.",
            "Es gilt [1 Komma 2; 3 Komma 4], Quellen 5 und 6 hier.",
        ),
    ],
)
def test_a_list_of_citation_brackets_is_one_citation(
    language: str, printed: str, said: str
) -> None:
    assert read_all(printed, language) == said


@pytest.mark.parametrize(
    ("printed", "named"),
    [
        ("It holds [1], [2] and [3] here.", 'list of numeric citations "[1], [2] and [3]"'),
        ("As shown in [1], [2] and [3], it holds.", 'citation "[1], [2] and [3]" is part of'),
        ("Between [1] and [3] it lies.", 'citations "[1] and [3]" are part of'),
    ],
)
def test_a_list_is_named_whole_in_its_reason(printed: str, named: str) -> None:
    (edit,) = CitationStep().find(
        make_document([(BlockKind.PARAGRAPH, printed)]), StepContext("en")
    )
    assert named in edit.reason


def test_an_or_list_is_not_read_as_one_citation() -> None:
    """#414 keeps "or" lists as they read before; this pins only that they are not joined into
    one citation, not today's reading of them (follow-up F1)."""
    said = read_all("It holds [1], [2] or [3] here.")
    assert "references 1" not in said
    assert said != "It holds here."
    assert " or " in said


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        (
            "It was found in [MH17], [Fa14] and [Ka20].",
            "It was found in references MH17, Fa14 and Ka20.",
        ),
        ("It holds [MH17], [Fa14] and [Ka20] here.", "It holds here."),
    ],
)
def test_a_list_of_listed_keys_is_one_citation(printed: str, said: str) -> None:
    assert _with_keys(printed) == said


def test_keys_and_numbers_make_no_one_list() -> None:
    """A key and a number are no list: the keys' list is decided apart from the number."""
    said = _with_keys("It holds [MH17], [Fa14] and [3] here.")
    assert "MH17" not in said
    assert "reference 3" in said


def _with_keys(printed: str) -> str:
    document = make_document(
        [
            (BlockKind.PARAGRAPH, printed),
            (BlockKind.HEADING, "References"),
            (BlockKind.PARAGRAPH, "[MH17] M. Maass and D. Herrmann. A tool. 2017."),
            (BlockKind.PARAGRAPH, "[Fa14] S. Fahl. Causes. 2014."),
            (BlockKind.PARAGRAPH, "[Ka20] K. Kam. A survey. 2020."),
        ]
    )
    script = run_steps(document, StepContext("en"), strict=True).script()
    return spoken_text([piece for piece in script if piece.span.block == 0])


# ---- #415 subject nests keep every name (B9, D-791) ---------------------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "((Smith, 2019) 2021) is cited.", "Smith is cited."),
        ("en", "(see (Smith, 2019); (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "((Smith, 2019) (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "((Smith, 2019) (Lee, 2018) (Kim, 2017)) is cited.", "Smith, Lee and Kim is cited."),
        ("en", "((Smith, 2019); and (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "((Smith, 2019), & (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "(Jones, 2020; ; (Smith, 2019)) is cited.", "Jones and Smith is cited."),
        ("en", "((Smith, 2019); (Lee, 2018) 2021) is cited.", "Smith and Lee is cited."),
        # lead words, a join word or an empty part, and a year shell, together
        ("en", "(see (Smith, 2019); and (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "(see (Smith, 2019); ; (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "((Smith, 2019); ; (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "((Smith, 2019); and (Lee, 2018) 2021) is cited.", "Smith and Lee is cited."),
        (
            "de",
            "(vgl. (Müller, 2019); und (Lee, 2018)) wird zitiert.",
            "Müller und Lee wird zitiert.",
        ),
        ("en", "((Smith, 2019)) is cited.", "Smith is cited."),
        ("en", "(see (Smith, 2019)) is cited.", "Smith is cited."),
        ("en", "Shown by ((Smith, 2019) (Lee, 2018)).", "Shown by Smith and Lee."),
        # the flat forms read the same
        ("en", "(Smith, 2019; and Lee, 2018) is cited.", "Smith and Lee is cited."),
        ("en", "(Jones, 2020; ; Smith, 2019) is cited.", "Jones and Smith is cited."),
        # a join word joins a part to the one before it: after one that is no citation, it
        # opens none (#621 review round 1, M2)
        ("en", "(RNNGs; and Dyer et al., 2016) help.", "(RNNGs; and Dyer et al., 2016) help."),
        ("en", "(RNNGs; Dyer et al., 2016; and Kim, 2019) help.", "(RNNGs) help."),
        # as an aside the nest still goes whole
        ("en", "It holds ((Smith, 2019) (Lee, 2018)) here.", "It holds here."),
        ("en", "It holds ((Smith, 2019) 2021) here.", "It holds here."),
        ("en", "It holds ((Smith, 2019)) here.", "It holds here."),
        # other text in the nest: as before
        ("en", "((Smith, 2019) Jones, 2020) is cited.", "Jones is cited."),
        ("en", "(foo (Smith, 2019); Jones, 2020) is cited.", "(foo) is cited."),
        ("de", "((Müller, 2019) 2021) wird zitiert.", "Müller wird zitiert."),
        ("de", "(vgl. (Müller, 2019); (Lee, 2018)) wird zitiert.", "Müller und Lee wird zitiert."),
        ("de", "((Müller, 2019) (Lee, 2018)) wird zitiert.", "Müller und Lee wird zitiert."),
        ("de", "((Müller, 2019); und (Lee, 2018)) wird zitiert.", "Müller und Lee wird zitiert."),
        ("de", "(Jones, 2020; ; (Müller, 2019)) wird zitiert.", "Jones und Müller wird zitiert."),
        ("de", "(Müller, 2019; und Lee, 2018) wird zitiert.", "Müller und Lee wird zitiert."),
    ],
)
def test_a_subject_nest_keeps_every_name(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # M1: an inner bracket read with its names after lead words stays in the rest, whose
        # parts name it already: read as on main
        (
            "en",
            "(see (Smith, 2019; Lee, 2020), Lee, 2020) found it.",
            "Smith and Lee, Lee found it.",
        ),
        (
            "en",
            "(see (Smith, 2019; Lee, 2020), Jones, 2020) is cited.",
            "Smith and Lee, Jones is cited.",
        ),
        (
            "de",
            "(vgl. (Müller, 2019; Lee, 2020), Jones, 2020) wird zitiert.",
            "Müller und Lee, Jones wird zitiert.",
        ),
        # M2: "; and" after an inner citation that lead words open reads as the flat form ...
        ("en", "(e.g. (Smith, 2019); and Jones, 2020) is cited.", "Smith and Jones is cited."),
        (
            "en",
            "(e.g. (Smith, 2019; Lee, 2020); and Jones, 2020) is cited.",
            "Smith, Lee and Jones is cited.",
        ),
        (
            "de",
            "(z. B. (Müller, 2019); und Jones, 2020) wird zitiert.",
            "Müller und Jones wird zitiert.",
        ),
        # ... and after "see"/"vgl.", whose inner citation stays read, as on main (#626)
        (
            "en",
            "(see (Smith, 2019); and Jones, 2020) is cited.",
            "(see Smith; and Jones, 2020) is cited.",
        ),
        (
            "en",
            "(see (Smith, 2019; Lee, 2020); and Jones, 2020) is cited.",
            "(see Smith and Lee; and Jones, 2020) is cited.",
        ),
        (
            "de",
            "(vgl. (Müller, 2019); und Jones, 2020) wird zitiert.",
            "(vergleiche Müller; und Jones, 2020) wird zitiert.",
        ),
    ],
)
def test_a_lead_word_nest_with_a_flat_part_reads_its_names_once(
    language: str, printed: str, said: str
) -> None:
    """#621 review round 1, M1 and M2."""
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "Table [1], [2] and [3] show it.", "Table [1], references 2 and 3 show it."),
        ("en", "Table [1], [2], [3] and [4] show it.", "Table [1], references 3 and 4 show it."),
        (
            "en",
            "The values x = [1], [2] and [3] hold.",
            "The values x equals [1], references 2 and 3 hold.",
        ),
        ("en", "x = [1], [2], [3] and [4] hold.", "x equals [1], references 3 and 4 hold."),
        ("en", "Eq. [1], [2] and [3] hold.", "Equation [1], references 2 and 3 hold."),
        ("en", "It holds[1], [2] and [3] here.", "It holds[1], references 2 and 3 here."),
        ("de", "Siehe Tabelle [1], [2] und [3].", "Siehe Tabelle [1], Quellen 2 und 3."),
        ("de", "Es gilt x = [1], [2] und [3] hier.", "Es gilt x gleich [1], Quellen 2 und 3 hier."),
        # only "and" alone makes a pair, as before
        ("en", "Table [1], [2], and [3] show it.", "Table [1], and reference 3 show it."),
        # a run that "or" ends is no list either: its pairs read as before (#622)
        (
            "en",
            "It holds [1] and [2] or [3] here.",
            "It holds references 1 and 2 or reference 3 here.",
        ),
        (
            "en",
            "It holds [1], [2] and [3] or [4] here.",
            "It holds, references 2 and 3 or reference 4 here.",
        ),
        # an interval first: the bracket after it reads as before (#151)
        (
            "en",
            "CI [1, 3] and [12] show it.",
            "confidence interval 1 to 3 and reference 12 show it.",
        ),
    ],
)
def test_a_run_whose_first_bracket_is_no_citation_reads_as_before(
    language: str, printed: str, said: str
) -> None:
    """#621 review round 1, M3: after a label word, a sign or a glued word the later brackets
    read one by one as before #414, an aside joined by "and" to the next as a D-668 pair.
    What such a run should read is the ruling question #634; this pins only that B9 changes
    nothing here."""
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once


# ---- #402 a join word before a removed last link (B9, D-791) ------------------------------


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        ("en", "We thank Smith and https://x.org here.", "We thank Smith here."),
        ("en", "We thank Smith, Lee, and https://x.org here.", "We thank Smith, Lee here."),
        ("en", "We thank Smith, Lee and https://x.org for help.", "We thank Smith, Lee for help."),
        ("en", "We thank Smith or https://x.org here.", "We thank Smith here."),
        ("en", "We thank Smith and www.x.org here.", "We thank Smith here."),
        ("de", "Wir danken Müller und https://x.org hier.", "Wir danken Müller hier."),
        ("de", "Wir danken Müller oder https://x.org hier.", "Wir danken Müller hier."),
        # it stays where it joins clauses: no name before it
        ("en", "It rains and https://x.org shows it.", "It rains and shows it."),
        ("en", "We ran it, and https://x.org shows it.", "We ran it, and shows it."),
        ("de", "Es regnet und https://x.org zeigt es.", "Es regnet und zeigt es."),
        # the sentence's first word is no list's name
        ("en", "Smith and https://x.org agree.", "Smith and agree."),
        ("en", "It holds. Smith and https://x.org agree.", "It holds. Smith and agree."),
        # ... nor one that opens a bracket or a quotation
        ("en", "(Smith and https://x.org agree.)", "(Smith and agree.)"),
        ("en", '"Smith and https://x.org agree."', '"Smith and agree."'),
        ("de", "(Müller und https://x.org zeigen es.)", "(Müller und zeigen es.)"),
        # one "and" stays where one goes after the link already
        ("en", "We thank Smith and https://x.org and Lee here.", "We thank Smith and Lee here."),
        # a word that went with the link keeps the join word before it
        ("en", "Data from Smith and from https://x.org here.", "Data from Smith and here."),
        # nothing after the link: `_dangling_join` as before
        ("en", "We thank Smith and https://x.org.", "We thank Smith."),
        # an abbreviation, a citation before the join word
        ("en", "We thank Dr. Smith and https://x.org here.", "We thank Dr. Smith here."),
        (
            "de",
            "Wir danken z. B. Müller und https://x.org hier.",
            "Wir danken zum Beispiel Müller hier.",
        ),
        ("en", "We thank [1] and https://x.org here.", "We thank and here."),
        # what the other steps judge on the link's removal (they read `link_removals`): a
        # citation after the link is then an aside of "Smith"; a German statistic after it
        # reads as before
        ("en", "We thank Smith and https://x.org [3] here.", "We thank Smith here."),
        ("en", "As in Smith and https://x.org (Lee, 2019) here.", "As in Smith here."),
        (
            "de",
            "Die Werte von Müller und https://x.org zeigen \u03c7\u00b2 = 3,2 hier.",
            "Die Werte von Müller zeigen Chi-Quadrat gleich 3 Komma 2 hier.",
        ),
        (
            "de",
            "Es gilt p < 0,05 und https://x.org hier.",
            "Es gilt p kleiner als 0 Komma 0 5 und hier.",
        ),
        # the known German limit: a noun has a capital too (the removed link was the clause's
        # subject, so neither reading mends it)
        (
            "de",
            "Wir messen die Daten und https://x.org zeigt sie.",
            "Wir messen die Daten zeigt sie.",
        ),
    ],
)
def test_a_join_word_before_a_removed_last_link(language: str, printed: str, said: str) -> None:
    assert read_all(printed, language) == said


def test_a_name_glued_after_a_removed_link_still_takes_the_join_word() -> None:
    """A name right after an earlier removal counts from where that removal ended, as every
    repair of the link step does, so its "and" goes with the next link (the glued "TextSmith"
    is a separate fault of the bracket removal)."""
    printed = "Text <https://a.org>Smith and https://x.org here."
    edits = LinkStep().find(make_document([(BlockKind.PARAGRAPH, printed)]), StepContext("en"))
    assert [edit.reason.endswith('"and" before it goes too (TP-07)') for edit in edits] == [
        False,
        True,
    ]


@pytest.mark.parametrize("printed", ["Text ( (Smith, 2019)) more.", "Text ([1]) more."])
def test_a_removed_nest_of_one_citation_is_named_a_bracket_of_lead_words(printed: str) -> None:
    """Where the inner citation's removal takes the whole bracket, the reason names the
    bracket as before #415, not the inner citation."""
    (edit,) = CitationStep().find(
        make_document([(BlockKind.PARAGRAPH, printed)]), StepContext("en")
    )
    assert edit.reason.startswith("bracket of lead words")


# ---- the second run over all of them -------------------------------------------------------

_PIECES = st.sampled_from(
    [
        "[1]", "[3]", "[12, p. 3]", "[12, S. 3]", "[12, pp. 3\u20135]", "[3, 4]", "and", "und",
        "or", "https://x.org", "https://x.org.", "et al.", "Fig.", "Abb.", "u. a.", "e.g.", "Smith",
        "Müller", "(Smith, 2019)", "((Smith, 2019); (Lee, 2018); Jones, 2020)",
        "((Smith, 2019); (Lee, 2020) 2021)", "(Jones, 2020; (Smith, 2019))", "in", "from",
        "We", "thank", "Between", "Then", "Dann", "the", "it", "is cited", "here", ",", ";",
        # B9 (#414, #415, #402)
        "[1], [2] and [3]", "[1], [2]", "[1], [2] or [3]", "((Smith, 2019) (Lee, 2018))",
        "((Smith, 2019) 2021)", "(see (Smith, 2019); and (Lee, 2018))",
        "(Jones, 2020; ; Lee, 2018)", "Smith and https://x.org", "Lee, and",
    ]
)  # fmt: skip


@given(st.lists(_PIECES, min_size=1, max_size=10), st.sampled_from(["en", "de"]))
def test_the_new_shapes_read_the_same_on_a_second_run(pieces: list[str], language: str) -> None:
    text = " ".join(pieces) + "."
    # an abbreviation right before a citation that goes reads differently on a second run
    # on main already ("Fig. ((Smith, 2019); Jones, 2020) Müller", #405)
    assume(not re.search(r"(?:al|Fig|Abb|a|e\.g)\.\s+[(\[]", text))
    read_all(text, language)
