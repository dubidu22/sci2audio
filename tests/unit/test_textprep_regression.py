"""The English regression cases (#4, PE-03): each case's script is what it was.

A failing case prints the before/after diff. A rule PR changes `expected` of the cases its
rule touches before it changes the rule (`.claude/rules/tests.md`).
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
from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category

CASES_FILE = Path(__file__).resolve().parents[1] / "regression" / "english.toml"
CASES = load_cases(CASES_FILE)

# cases that do not read the same on a second run, each with the reason (D-577)
SECOND_RUN_EXCEPTIONS: dict[str, str] = {
    "maths-italic-letter-after-a-number-is-no-unit": (
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
    "citations-after-a-read-abbreviation-keep-the-sentence-end": _REMOVED_END,
    "links-no-two-full-stops-after-an-abbreviation": _REMOVED_END,
    "sentence-after-a-narrative-citation": _REMOVED_END,
    "linked-endnote-on-another-page": (
        "a note read at its mark (#213) comes back as a block of its own where it is printed, "
        "so a second run reads it there, after the paragraph that holds its mark"
    ),
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


def test_a_case_may_switch_categories_off_besides_the_defaults(tmp_path: Path) -> None:
    good = tmp_path / "good.toml"
    good.write_text(
        '[[case]]\nid = "one"\naudit = 0\nissue = 463\ngoal = "g"\n'
        'switched_off = ["tables-and-figures"]\n'
        'blocks = [{ kind = "table", text = "A 1" }]\nexpected = []\n'
    )
    (case,) = load_cases(good)
    assert case.switched_off == DEFAULT_SWITCHED_OFF | {Category.TABLES_AND_FIGURES}
    assert render(run_case(case)) == ["A 1"]
    good.write_text('[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\n'
                    'blocks = [{ kind = "table", text = "A 1" }]\nexpected = []\n')  # fmt: skip
    (case,) = load_cases(good)
    assert case.switched_off == DEFAULT_SWITCHED_OFF
    assert render(run_case(case)) == ["A table is skipped."]
    for value, message in (('["tables"]', "is not a valid Category"), ('"code"', "must be a list")):
        good.write_text('[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\n'
                        f'switched_off = {value}\nblocks = []\nexpected = []\n')  # fmt: skip
        with pytest.raises(ValueError, match=message):
            load_cases(good)


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


def test_a_run_may_carry_several_tags_and_a_block_a_later_page(tmp_path: Path) -> None:
    good = tmp_path / "good.toml"
    good.write_text(
        '[[case]]\nid = "one"\naudit = 0\nissue = 189\ngoal = "g"\n'
        'blocks = [{ kind = "paragraph", runs = ["Noise", '
        '{ text = "1", tags = ["a", "epub:noteref", "link:b2l0"] }, " here."] },\n'
        '          { kind = "paragraph", text = "Between.", page = 2 },\n'
        '          { kind = "footnote", text = "A note.", page = 4 }]\n'
        "expected = []\n"
    )
    (case,) = load_cases(good)
    pages = case.document.content.pages
    assert [page.number for page in pages] == [1, 2, 3, 4]
    ids = [[line.id for line in page.lines] for page in pages]
    assert ids == [["b0l0"], ["b1l0"], [], ["b2l0"]]
    assert [(run.text, run.tags) for run in pages[0].lines[0].runs] == [
        ("Noise", ()),
        ("1", ("a", "epub:noteref", "link:b2l0")),
        (" here.", ()),
    ]


@pytest.mark.parametrize(
    ("block", "problem"),
    [
        ('{ kind = "paragraph", text = "a", runs = ["a"] }', "a block gives either text or runs"),
        ('{ kind = "paragraph" }', "a block gives either text or runs"),
        ('{ kind = "paragraph", runs = [{ sub = "1" }] }', "a run is a string or"),
        ('{ kind = "paragraph", runs = [3] }', "a run is a string or"),
        ('{ kind = "paragraph", runs = [{ text = "1", tags = [] }] }', "a run is a string or"),
        ('{ kind = "paragraph", runs = [{ text = "", tags = ["a"] }] }', "a run is a string or"),
        ('{ kind = "paragraph", runs = [{ text = "1", tags = "a" }] }', "a run is a string or"),
        ('{ kind = "paragraph", runs = [{ text = "1", tags = [""] }] }', "a run is a string or"),
        ('{ kind = "paragraph", text = "a", page = 0 }', "page must be a whole number"),
        ('{ kind = "paragraph", text = "a", page = "2" }', "page must be a whole number"),
        ('{ kind = "paragraph", text = "a", page = true }', "page must be a whole number"),
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


def test_pages_never_go_back(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        '[[case]]\nid = "one"\naudit = 0\nissue = 1\ngoal = "g"\n'
        'blocks = [{ kind = "paragraph", text = "a", page = 2 },\n'
        '          { kind = "paragraph", text = "b" }]\n'
        "expected = []\n"
    )
    with pytest.raises(ValueError, match="case one: block 1 is on page 1, after page 2"):
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
