"""The English regression cases (#4, PE-03): each case's script is what it was.

A failing case prints the before/after diff. A rule PR changes `expected` of the cases its
rule touches before it changes the rule (`.claude/rules/tests.md`).
"""

from pathlib import Path

import pytest

from sci2audio.testing.regression import Case, diff, load_cases, render, said
from sci2audio.textprep import StepContext, run_steps

CASES_FILE = Path(__file__).resolve().parents[1] / "regression" / "english.toml"
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
    bad.write_text('[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = 3\nblocks = []\n'
                   'expected = []\n')  # fmt: skip
    with pytest.raises(ValueError, match="case one: goal must say"):
        load_cases(bad)


def test_the_diff_shows_before_and_after() -> None:
    shown = diff(["Keep.", "Old line."], ["Keep.", "New line."])
    assert "-Old line." in shown
    assert "+New line." in shown


def test_runs_give_superscripts_and_sections_are_read(tmp_path: Path) -> None:
    good = tmp_path / "good.toml"
    good.write_text(
        '[[case]]\nid = "one"\naudit = 0\nissue = 64\ngoal = "g"\n'
        'blocks = [{ kind = "heading", text = "References" },\n'
        '          { kind = "paragraph", runs = ["Noise", { sup = "1" }, " here."] }]\n'
        'sections = [{ title = "References", level = 1, start = 0, end = 2 }]\n'
        "expected = []\n"
    )
    (case,) = load_cases(good)
    assert case.document.blocks[1].text == "Noise1 here."
    line = case.document.content.pages[0].lines[1]
    assert [(run.text, run.tags) for run in line.runs] == [
        ("Noise", ()),
        ("1", ("sup",)),
        (" here.", ()),
    ]
    assert [(s.title, s.start, s.end) for s in case.document.sections] == [("References", 0, 2)]


@pytest.mark.parametrize(
    ("block", "problem"),
    [
        ('{ kind = "paragraph", text = "a", runs = ["a"] }', "a block gives either text or runs"),
        ('{ kind = "paragraph" }', "a block gives either text or runs"),
        ('{ kind = "paragraph", runs = [{ sub = "1" }] }', "a run is a string or"),
        ('{ kind = "paragraph", runs = [3] }', "a run is a string or"),
    ],
)
def test_a_bad_run_names_the_case(tmp_path: Path, block: str, problem: str) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        f'[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\nblocks = [{block}]\n'
        "expected = []\n"
    )
    with pytest.raises(ValueError, match=f"case one: {problem}"):
        load_cases(bad)


def test_a_bad_section_names_the_case(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        '[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\nblocks = []\n'
        'sections = [{ title = "R", level = 1, start = 0, end = 0, children = [] }]\n'
        "expected = []\n"
    )
    with pytest.raises(ValueError, match="case one: unknown section keys"):
        load_cases(bad)
