# ruff: noqa: RUF001, RUF002
# (the times sign is what these texts are about)
"""N3 before a sign (#844): a four-digit number before "=", "×" or an "x" read as "times"
reads the same on a first run and on a second run, which sees "equals" and "times"."""

import pytest

from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, run_steps, spoken_text


def _read_all(text: str, language: str) -> str:
    """The whole chain of built-in steps, as a job in `language` runs it."""
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    return spoken_text(run_steps(document, StepContext(language), strict=True).script())


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("We set 1234 = A.", "We set 1,234 equals A."),
        ("So 1234=A holds.", "So 1,234 equals A holds."),
        ("It grew 1234× over the year.", "It grew 1,234 times over the year."),
        ("It grew 1234 × 5.", "It grew 1,234 times 5."),
        ("It was 1234x larger.", "It was 1,234 times larger."),
        ("It grew 9999 × 5.", "It grew 9,999 times 5."),
        ("It grew 1499× here.", "It grew 1,499 times here."),
        ("It grew 2101× here.", "It grew 2,101 times here."),
        # the words a second run sees, printed so
        ("We set 1234 equals A.", "We set 1,234 equals A."),
        ("We had 1234 times the cost.", "We had 1,234 times the cost."),
        # a year-like number is left as printed before "=" and before its word
        ("We set 2019 = A.", "We set 2019 equals A."),
        ("We set 2019 equals A.", "We set 2019 equals A."),
        # ... and before the times sign or "times" with a number after it (a product, a
        # size), while before the sign or "times" alone it is a count (#871)
        ("It grew 1501 × 5.", "It grew 1501 times 5."),
        ("It grew 2019× here.", "It grew 2,019 times here."),
        ("We had 2099 times the cost.", "We had 2,099 times the cost."),
        # a sign before the number reads it as a number, as before
        ("x = 2019 = A", "x equals 2,019 equals A"),
        # the plural rule is unchanged: a year word before, or none
        ("We enrolled 2019 participants.", "We enrolled 2,019 participants."),
        ("In 2019 studies differ.", "In 2019 studies differ."),
        # an "x" that is no "times" leaves the number alone
        ("We used 1234xy here.", "We used 1234xy here."),
    ],
)
def test_english_reads_a_number_before_a_sign_the_same_on_both_runs(
    printed: str, said: str
) -> None:
    first = _read_all(printed, "en")
    assert first == said
    assert _read_all(first, "en") == first


@pytest.mark.parametrize(
    ("printed", "said"),
    [
        ("Wir setzen 1234 = A.", "Wir setzen 1234 gleich A."),
        ("Es wuchs 1234× im Jahr.", "Es wuchs 1234 mal im Jahr."),
        ("Wir setzen 2019 = A.", "Wir setzen 2019 gleich A."),
        ("Es wuchs 2019× im Jahr.", "Es wuchs 2019 mal im Jahr."),
    ],
)
def test_german_reads_a_number_before_a_sign_the_same_on_both_runs(printed: str, said: str) -> None:
    first = _read_all(printed, "de")
    assert first == said
    assert _read_all(first, "de") == first
