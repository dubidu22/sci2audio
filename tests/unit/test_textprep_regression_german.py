"""The German regression cases (v1.1, D-474 to D-482): each case's script is what it was.

Same loader and check as the English cases (`test_textprep_regression.py`). A failing case
prints the before/after diff. A rule PR changes `expected` of the cases its rule touches
before it changes the rule (`.claude/rules/tests.md`).
"""

from pathlib import Path

import pytest

from sci2audio.testing.regression import Case, diff, load_cases, read_twice, render, said
from sci2audio.textprep import StepContext, run_steps

CASES_FILE = Path(__file__).resolve().parents[1] / "regression" / "german.toml"
CASES = load_cases(CASES_FILE)

# cases that do not read the same on a second run, each with the reason (D-577)
SECOND_RUN_EXCEPTIONS = {
    # `rebuilt_from_script` keeps a label only where the text prints it, so the rebuilt notice
    # has none and is read "Eine Abbildung wird übersprungen": the rebuild, not a step
    "de-notice-table-named-by-its-caption": "the rebuilt notice block loses its label",
    "de-notice-figure-short-label": "the rebuilt notice block loses its label",
    "de-units-german-label-joins": "#321: '1 bzw. 2 V' reads '2 Volt' on a second run",
}


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


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case,
            marks=pytest.mark.xfail(strict=True, reason=SECOND_RUN_EXCEPTIONS[case.id])
            if case.id in SECOND_RUN_EXCEPTIONS
            else (),
        )
        for case in CASES
    ],
    ids=[case.id for case in CASES],
)
def test_the_script_reads_the_same_on_a_second_run(case: Case) -> None:
    """D-577: the steps change nothing more on a second run over the first run's script. A
    listed exception must still fail (strict), so a fix shows and the entry goes."""
    first, second = read_twice(case)
    assert first == second, f"second run of {case.id} differs:\n{diff(first, second)}"


def test_every_second_run_exception_names_a_case() -> None:
    assert set(SECOND_RUN_EXCEPTIONS) <= {case.id for case in CASES}
