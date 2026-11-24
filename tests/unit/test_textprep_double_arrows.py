"""A long double arrow printed as "=" and an arrow (#590): one arrow in both languages, on
both runs. The voices read "=⇒" as "equals" ("gleich"), which flips the meaning."""

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
    ("language", "printed", "said"),
    [
        ("en", "So A =⇒ B, and C⇐=D iff P ⇐=⇒ Q.", "So A ⇒ B, and C⇐D iff P ⇔ Q."),
        ("en", "Then X=⇒Y and Y ⇐⇒ Z.", "Then X⇒Y and Y ⇔ Z."),
        ("de", "Also gilt A =⇒ B und C⇐=D.", "Also gilt A ⇒ B und C⇐D."),
        ("de", "Dann gilt P ⇐=⇒ Q und X=⇒Y.", "Dann gilt P ⇔ Q und X⇒Y."),
        ("de", "Für x =⇒ 3 gilt y ⇐= 5.", "Für x ⇒ 3 gilt y ⇐ 5."),
    ],
)
def test_a_pieced_double_arrow_is_one_arrow_on_both_runs(
    language: str, printed: str, said: str
) -> None:
    first, second = first_and_second_run(printed, language)
    assert first == said
    assert second == first
