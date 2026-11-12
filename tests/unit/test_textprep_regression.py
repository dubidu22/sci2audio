"""The English regression cases (#4, PE-03): each case's script is what it was.

A failing case prints the before/after diff. A rule PR changes `expected` of the cases its
rule touches before it changes the rule (`.claude/rules/tests.md`).
"""

from pathlib import Path

import pytest

from sci2audio.testing.regression import Case, diff, load_cases, render
from sci2audio.textprep import StepContext, run_steps

CASES_FILE = Path(__file__).resolve().parents[1] / "regression" / "english.toml"
CASES = load_cases(CASES_FILE)


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_the_script_is_the_expected_one(case: Case) -> None:
    run = run_steps(case.document, StepContext(case.document.language), strict=True)
    got = render(run)
    assert list(case.expected) == got, f"script of {case.id} changed:\n{diff(case.expected, got)}"


def test_the_14_audit_rows_are_all_there() -> None:
    assert sorted(case.audit for case in CASES if case.audit) == list(range(1, 15))
    assert all(case.issue > 0 and case.goal for case in CASES)


def test_a_bad_case_file_names_the_case(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        '[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\n'
        'blocks = [{ kind = "poem", text = "x" }]\nexpected = []\n'
    )
    with pytest.raises(ValueError, match="case one: 'poem' is not a valid BlockKind"):
        load_cases(bad)
    bad.write_text('[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\nblocks = []\n'
                   'expected = []\nextra = 1\n')  # fmt: skip
    with pytest.raises(ValueError, match="unknown keys"):
        load_cases(bad)


def test_the_diff_shows_before_and_after() -> None:
    shown = diff(["Keep.", "Old line."], ["Keep.", "New line."])
    assert "-Old line." in shown
    assert "+New line." in shown
