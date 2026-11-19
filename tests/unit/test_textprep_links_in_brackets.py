"""Links inside brackets read the same on a second run (#326, #337, D-605, D-630)."""

import pytest

from sci2audio.core import BlockKind, ScriptPiece, Span
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
        # a "/" with white space on both sides goes too (#371 review round 2, N2)
        ("en", "It holds (see https://example.org / Lee, 2019) here.", "It holds here."),
        ("en", "It holds (https://example.org / the code) here.", "It holds (the code) here."),
        ("de", "Es gilt (siehe https://example.org / Müller, 2019) hier.", "Es gilt hier."),
        # a bracket that stays, glued after the link's, keeps the space before (round 1, S1)
        ("en", "Text (see https://example.org)(more) here.", "Text (more) here."),
        ("en", "Text, (see https://example.org)(more) here.", "Text, (more) here."),
        # the address ends at the ")" before the glued bracket, not at an earlier stray one,
        # and a bracket it opens itself counts (round 2, N1)
        ("en", "Text (see https://example.org/a)b)(more) here.", "Text (more) here."),
        ("en", "Lee (see https://x.org/a(b)(Smith, 2019).", "Lee."),
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
        # one citation in a year shell as the subject keeps its names (#415, D-791; read "is
        # cited." before)
        ("en", "((Smith, 2019) 2020) is cited.", "Smith is cited."),
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
        # an inner citation after lead words is an item too, as in the flat form (#415, D-791;
        # read "Jones is cited." before); other text before it is no lead (round 2, N1)
        ("en", "(e.g. (Smith, 2019); Jones, 2020) is cited.", "Smith and Jones is cited."),
        ("en", "(foo (Smith, 2019); Jones, 2020) is cited.", "(foo) is cited."),
        # #372: every inner citation that is an item of the list keeps its names
        ("en", "(Jones, 2020; (Smith, 2019)) is cited.", "Jones and Smith is cited."),
        (
            "en",
            "(Jones, 2020; (Smith, 2019); (Lee, 2018)) is cited.",
            "Jones, Smith and Lee is cited.",
        ),
        (
            "en",
            "((Smith, 2019); (Lee, 2018); Jones, 2020) is cited.",
            "Smith, Lee and Jones is cited.",
        ),
        ("en", "((Smith, 2019); (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "((Smith, 2019), (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        (
            "en",
            "(Jones, 2020; (Smith, 2019); Kim, 2017) is cited.",
            "Jones, Smith and Kim is cited.",
        ),
        (
            "de",
            "((Müller, 2019); (Lee, 2018); Schmidt, 2020) wird zitiert.",
            "Müller, Lee und Schmidt wird zitiert.",
        ),
        ("en", "Text ((Smith, 2019); (Lee, 2018); Jones, 2020) here.", "Text here."),
        # #375: a year shell around several citations goes whole; as the subject, it names them
        ("en", "Data ((Smith, 2019); (Lee, 2020) 2021) here.", "Data here."),
        ("en", "Data ((Smith, 2019), (Lee, 2020); (Kim, 2017) 2021) here.", "Data here."),
        ("en", "((Smith, 2019); (Lee, 2020) 2021) is cited.", "Smith and Lee is cited."),
        ("de", "Daten ((Müller, 2019); (Lee, 2020) 2021) hier.", "Daten hier."),
        # other nest shapes read as before
        ("en", "((Smith, 2019) Jones, 2020) is cited.", "Jones is cited."),
        # a nest of one citation, and one after lead words, keep their names as the flat form
        # does (#415, D-791; read "is cited." and "(see Smith) is cited." before)
        ("en", "((Smith, 2019)) is cited.", "Smith is cited."),
        ("en", "(see (Smith, 2019); (Lee, 2018)) is cited.", "Smith and Lee is cited."),
        ("en", "Data ((Smith, 2019); foo (Lee, 2020) 2021) here.", "Data (foo 2021) here."),
    ],
)
def test_citation_nests_read_the_same_on_a_second_run(
    language: str, printed: str, said: str
) -> None:
    once = read_all(printed, language)
    assert once == said
    assert read_all(once, language) == once


@pytest.mark.parametrize(
    "printed", ["Text (see https://example.org)", "Text [see https://example.org]"]
)
def test_a_link_bracket_that_ends_its_block_takes_the_space_before_it(printed: str) -> None:
    """The script piece itself, which the spoken text would hide: no trailing space, so its
    span and chunk key stay as before (#371 review round 2, S1)."""
    document = make_document([(BlockKind.PARAGRAPH, printed)], "en")
    script = run_steps(document, StepContext("en"), strict=True).script()
    assert tuple(script) == (ScriptPiece("Text", Span(0, 0, 4)),)
