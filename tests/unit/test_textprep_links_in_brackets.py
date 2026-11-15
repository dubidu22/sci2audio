"""Links inside brackets read the same on a second run (#326, #337, D-605, D-630)."""

import pytest

from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, spoken_text
from sci2audio.textprep.links import find_links


def read_all(text: str, language: str = "en") -> str:
    """The whole chain of built-in steps."""
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    return spoken_text(run_steps(document, StepContext(language), strict=True).script())


@pytest.mark.parametrize(
    ("text", "found"),
    [
        # #326: the address ends at the bracket it closes when another bracket is glued on
        ("(see https://example.org)(Smith, 2019) it holds.", "https://example.org"),
        ("(see https://example.org)[12] it holds.", "https://example.org"),
        ("[see https://example.org][12] it holds.", "https://example.org"),
        ("(Smith, 2019, https://example.org)(Smith, 2019)", "https://example.org"),
        # a bracket the address opens itself stays in it
        (
            "(see https://en.wikipedia.org/wiki/Foo_(bar))(Smith, 2019)",
            "https://en.wikipedia.org/wiki/Foo_(bar)",
        ),
        # no bracket open before it: the address runs on as before
        ("See https://example.org)(Smith, 2019) here.", "https://example.org)(Smith"),
    ],
)
def test_an_address_ends_at_the_bracket_it_closes_before_a_glued_bracket(
    text: str, found: str
) -> None:
    assert [text[link.start : link.end] for link in find_links(text)] == [found]


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # #326
        ("en", "(Smith, 2019, https://example.org)(Smith, 2019) it holds.", "Smith it holds."),
        ("en", "(see https://example.org)(Smith, 2019) it holds.", "it holds."),
        ("en", "Text (see https://example.org)(Smith, 2019) more.", "Text more."),
        ("de", "(siehe https://example.org)(Müller, 2019) es gilt.", "es gilt."),
        # #337: a join word or separator the link leaves at the bracket's edge goes with it
        ("en", "It holds (see https://example.org and Lee, 2019) here.", "It holds here."),
        ("en", "It holds (https://example.org, Lee, 2019) here.", "It holds here."),
        ("en", "It holds (see https://example.org; Lee, 2019) here.", "It holds here."),
        ("en", "It holds (https://example.org or the code) here.", "It holds (the code) here."),
        ("de", "Es gilt (siehe https://example.org und Lee, 2019) hier.", "Es gilt hier."),
        ("de", "Es gilt (https://example.org, Müller, 2019) hier.", "Es gilt hier."),
        ("de", "Es gilt (siehe https://example.org; Lee, 2019) hier.", "Es gilt hier."),
        # a join word inside the bracket, not at its edge, stays
        ("en", "It holds (the code and https://example.org) here.", "It holds (the code) here."),
    ],
)
def test_links_in_brackets_read_the_same_on_a_second_run(
    language: str, printed: str, said: str
) -> None:
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once


@pytest.mark.parametrize(
    ("language", "printed", "said"),
    [
        # #338: a numeric bracket glued after a removed citation or link bracket is judged
        # where the removal stood, after its space, as the spaced form is
        ("en", "As said by Lee (Smith, 2019)[12] it holds.", "As said by Lee it holds."),
        ("en", "As said by Lee (Smith, 2019)[12][13] it holds.", "As said by Lee it holds."),
        ("de", "Wie Weber (Müller, 2019)[12] zeigt.", "Wie Weber zeigt."),
        ("en", "It holds and (Smith, 2019)[12] more.", "It holds and reference 12 more."),
        ("en", "It holds and (Smith, 2019) [12] more.", "It holds and reference 12 more."),
        ("en", "Text (see https://example.org)[12] more.", "Text more."),
        (
            "en",
            "As shown in (see https://example.org)[12] it holds.",
            "As shown in reference 12 it holds.",
        ),
        (
            "en",
            "As shown in (see https://example.org) [12] it holds.",
            "As shown in reference 12 it holds.",
        ),
        ("de", "Wie in (siehe https://example.org)[12] gezeigt.", "Wie in Quelle 12 gezeigt."),
        # after its reference word with a removal between, it is read in the word's place
        ("en", "Ref. (see https://example.org) [3, 4] more.", "References 3 and 4 more."),
        ("en", "It is in Ref. (see https://example.org) [3] here.", "It is in reference 3 here."),
        ("de", "Ref. https://x.org [3, 4] mehr.", "Quellen 3 und 4 mehr."),
        ("en", "Ref. (Smith, 2019) [12] shows it.", "Reference 12 shows it."),
        # glued to the word itself, it stays as before
        ("en", "As said by Lee(Smith, 2019)[12] it holds.", "As said by Lee[12] it holds."),
        # #339: year shells around a citation that goes go with it, however deep
        ("en", "Text ((Smith, 2019) 2020) more.", "Text more."),
        ("en", "Text (((Smith, 2019) 2020) 2021) more.", "Text more."),
        ("en", "Text ((((Smith, 2019) 2020) 2021) 2022) more.", "Text more."),
        ("en", "the method (((Smith, 2019) 2020) 2021) works.", "the method works."),
        ("en", "((Smith, 2019) 2020) is cited.", "is cited."),
        ("de", "Text ((Müller, 2019) 2020) mehr.", "Text mehr."),
        ("de", "Text ((((Müller, 2019) 2020) 2021) 2022) mehr.", "Text mehr."),
        # a shell with more than a year stays
        ("en", "Text ((Smith, 2019) the 2020 data) more.", "Text (Smith the 2020 data) more."),
        # #278: an inner citation that opens the list keeps its names, as in the flat form
        ("en", "((Smith, 2019); Jones, 2020) is cited.", "Smith and Jones is cited."),
        ("en", "((Smith, 2019), Jones, 2020) is cited.", "Smith and Jones is cited."),
        (
            "en",
            "((Smith, 2019; Lee, 2018); Jones, 2020) is cited.",
            "Smith, Lee and Jones is cited.",
        ),
        ("de", "((Müller, 2019); Weber, 2020) wird zitiert.", "Müller und Weber wird zitiert."),
        ("en", "Text ((Smith, 2019); Jones, 2020) here.", "Text here."),
        # other nest shapes read as before
        ("en", "((Smith, 2019) Jones, 2020) is cited.", "Jones is cited."),
        ("en", "(Jones, 2020; (Smith, 2019)) is cited.", "Jones is cited."),
        ("en", "((Smith, 2019)) is cited.", "is cited."),
    ],
)
def test_citation_nests_read_the_same_on_a_second_run(
    language: str, printed: str, said: str
) -> None:
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once
