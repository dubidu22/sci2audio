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
