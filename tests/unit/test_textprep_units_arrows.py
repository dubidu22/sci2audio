# ruff: noqa: RUF001, RUF002  (the multiplication sign is meant)
"""#843: "3x" beside a logic arrow is a variable, whether the arrow is printed ("3x=>A",
"3x ⇒ A") or already read by the statistics step ("3x implies A"), so a second run reads it
as the first did. "3x faster" and "3 × 4" still read "times"."""

import pytest

from sci2audio.core import BlockKind
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.textprep import StepContext, run_steps, spoken_text


def first_and_second_run(text: str, language: str) -> tuple[str, str]:
    document = make_document([(BlockKind.PARAGRAPH, text)], language)
    context = StepContext(language)
    first = run_steps(document, context, strict=True)
    assert not first.problems
    second = run_steps(rebuilt_from_script(document, first.script()), context, strict=True)
    return spoken_text(first.script()), spoken_text(second.script())


@pytest.mark.parametrize(
    ("language", "printed"),
    [
        ("en", "So 3x=>A holds."),
        ("en", "So 3x ⇒ A holds."),
        ("en", "So A ⇐ 3x, as said."),
        ("en", "So 3x<=>A holds."),
        ("en", "So 3x ⇔ A holds."),
        ("de", "Also gilt 3x=>A."),
        ("de", "Also gilt 3x ⇒ A."),
        ("de", "Also gilt A ⇐ 3x."),
        ("de", "Also gilt 3x ⇔ A."),
    ],
)
def test_x_beside_a_printed_arrow_is_a_variable_on_both_runs(language: str, printed: str) -> None:
    first, second = first_and_second_run(printed, language)
    assert "3x" in first
    assert second == first


@pytest.mark.parametrize(
    ("language", "said"),
    [
        ("en", "So 3x implies A."),
        ("en", "So A is implied by 3x."),
        ("en", "So 3x if and only if A."),
        ("de", "Also 3x daraus folgt A."),
        ("de", "Also A folgt aus 3x."),
        ("de", "Also 3x genau dann, wenn A."),
    ],
)
def test_x_beside_a_read_arrow_is_a_variable(language: str, said: str) -> None:
    first, second = first_and_second_run(said, language)
    assert first == said
    assert second == first


@pytest.mark.parametrize(
    ("language", "printed", "expected"),
    [
        ("en", "It runs 3x faster.", "It runs 3 times faster."),
        ("en", "So 3 × 4 is 12.", "So 3 times 4 is 12."),
        ("de", "Es läuft 3x schneller.", "Es läuft 3 mal schneller."),
        ("de", "Also 3 × 4 ist 12.", "Also 3 mal 4 ist 12."),
    ],
)
def test_times_reads_as_before(language: str, printed: str, expected: str) -> None:
    assert first_and_second_run(printed, language) == (expected, expected)


@pytest.mark.parametrize(
    ("language", "printed", "expected"),
    [
        ("en", "So A ⇐ 3x more data.", "So A is implied by 3 times more data."),
        ("de", "Also A ⇐ 3x so viele Daten.", "Also A folgt aus 3 mal so viele Daten."),
    ],
)
def test_x_after_an_arrow_before_a_prose_word_is_times(
    language: str, printed: str, expected: str
) -> None:
    assert first_and_second_run(printed, language) == (expected, expected)
