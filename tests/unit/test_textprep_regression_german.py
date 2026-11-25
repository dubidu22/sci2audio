"""The German regression cases (v1.1, D-474 to D-482): each case's script is what it was.

Same loader and check as the English cases (`test_textprep_regression.py`). A failing case
prints the before/after diff. A rule PR changes `expected` of the cases its rule touches
before it changes the rule (`.claude/rules/tests.md`).
"""

from pathlib import Path

import pytest

from sci2audio.testing.regression import (
    Case,
    cut_twice,
    diff,
    load_cases,
    read_twice,
    render,
    run_case,
    said,
)

CASES_FILE = Path(__file__).resolve().parents[1] / "regression" / "german.toml"
CASES = load_cases(CASES_FILE)

# cases that do not read the same on a second run, each with the reason (D-577)
SECOND_RUN_EXCEPTIONS: dict[str, str] = {
    "de-a-maths-italic-letter-after-a-number-is-no-unit": (
        "an italic maths letter after a number is a variable, so the first run leaves it; the "
        "characters step makes it a plain letter, which a second run reads as a unit (as on "
        "main; the owner decides, #1082)"
    ),
}

# cases whose utterances a second run cuts differently, each with the reason (#482). The
# script is the same (above); only where a sentence ends moves.
_REMOVED_END = (
    "a removed citation or link ended the printed sentence after an abbreviation ('et al.', "
    "'Fig.'), which ends it on a first run (D-719); on a second run the removed text is gone, "
    "so the abbreviation ends no sentence there"
)
SECOND_RUN_CUT_EXCEPTIONS: dict[str, str] = {
    "de-links-no-two-full-stops-after-an-abbreviation": _REMOVED_END,
    "de-et-al-whose-citation-ended-the-sentence-still-ends-it": _REMOVED_END,
}


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_the_script_is_the_expected_one(case: Case) -> None:
    run = run_case(case)
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


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            case,
            marks=pytest.mark.xfail(strict=True, reason=SECOND_RUN_CUT_EXCEPTIONS[case.id])
            if case.id in SECOND_RUN_CUT_EXCEPTIONS
            else (),
        )
        for case in CASES
        if case.utterances is not None
    ],
    ids=[case.id for case in CASES if case.utterances is not None],
)
def test_the_utterances_are_cut_the_same_on_a_second_run(case: Case) -> None:
    """#482: a second run over the first run's script cuts it into the same utterances, so a
    long sentence is not cut inside a reading once its words are plain text. A listed
    exception must still fail (strict), so a fix shows and the entry goes."""
    first, second = cut_twice(case)
    assert first == second, f"second-run cuts of {case.id} differ:\n{diff(first, second)}"


def test_every_second_run_cut_exception_names_a_case_with_utterances() -> None:
    assert set(SECOND_RUN_CUT_EXCEPTIONS) <= {c.id for c in CASES if c.utterances is not None}
