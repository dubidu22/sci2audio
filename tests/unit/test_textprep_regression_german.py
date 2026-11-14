"""The German regression cases (v1.1, D-474 to D-482): each case's script is what it was.

Same loader and check as the English cases (`test_textprep_regression.py`). A failing case
prints the before/after diff. A rule PR changes `expected` of the cases its rule touches
before it changes the rule (`.claude/rules/tests.md`).
"""

from pathlib import Path

import pytest

from sci2audio.testing.regression import Case, diff, load_cases, render, said
from sci2audio.textprep import StepContext, run_steps

CASES_FILE = Path(__file__).resolve().parents[1] / "regression" / "german.toml"
CASES = load_cases(CASES_FILE)


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_the_script_is_the_expected_one(case: Case) -> None:
    run = run_steps(case.document, StepContext(case.document.language), strict=True)
    got = render(run)
    assert list(case.expected) == got, f"script of {case.id} changed:\n{diff(case.expected, got)}"
    if case.utterances is not None:
        cut = said(run)
        assert list(case.utterances) == cut, (
            f"utterances of {case.id} changed:\n{diff(case.utterances, cut)}"
        )


def test_every_case_is_german_and_owned_by_an_issue() -> None:
    assert CASES
    assert all(case.document.language.split("-")[0] == "de" for case in CASES)
    assert all(case.audit == 0 and case.issue > 0 and case.goal for case in CASES)
    assert all(case.id.startswith("de-") for case in CASES)
