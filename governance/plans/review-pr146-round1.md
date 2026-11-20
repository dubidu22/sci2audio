# Review of PR #146, round 1: the outline adds headings the font rules miss (#24, part 3)

Reviewed head 973b2ba (main with #133 merged in; layout files identical to 5b3cab7), against
plan `issue24-outline-plan.md` section 5 and D-262 to D-273. Reviewer thread: "Review outline
headings layout PR 146", 13 Nov 2026.

## What I checked

- Whole diff (4 files) against plan section 5, rules 1 to 6 and the test list. The code matches
  the plan: only PARAGRAPH blocks are candidates, the match is on the entry's page only (D-272),
  a block the font rules found is never re-levelled or re-labelled (`index not in found`,
  D-270/D-271), title root and file title skipped, entries without letters ignored (D-266).
- `ruff check`, `ruff format --check`, `lint-imports` (3 kept, 0 broken), `deptry src`: clean.
- Fast suite, ci profile, without browser: 2191 passed, 19 subtests, 54 snapshots passed. The
  7 corpus layout golden files are unchanged, so the spoken text of every corpus paper is unchanged.
- Nightly Hypothesis profile, fresh example database, `test_layout.py`,
  `test_layout_headings.py`, `test_layout_corpus.py`: 216 passed.
- CI on 973b2ba: all jobs green on Linux, macOS, Windows, browser, lint, security, licences.
- The new property test does exercise additions: over 2000 drawn contents, 567 of the outline
  runs added at least one heading (28 %).
- Mutation test: 19 hand-made mutants of the new code, run against the three layout test files.
  16 killed, 3 survived (M1, S2 and N1 below).

## Findings

### M1 (must fix): the "font rules' level stands" guard (D-271) is not tested

Removing `index not in found` from `_from_outline`, or passing `{}` as `found` so the outline
re-levels every heading it names, passes all 216 layout tests, also the nightly property test with
a fresh database. `test_the_font_rules_level_stands_when_the_outline_disagrees` uses numbered
headings, where the outline would give the same level as the font rules anyway ("1.1 Setup"
gets depth 2 either way), so it cannot see the guard. This is the core guarantee of the PR.

Fix: a disagreement test on unnumbered font headings. This one kills both mutants:

```python
page = Page().heading("Summary", 14.0).body().heading("Details", 12.0).body()
page.heading("Statement of need", 14.0).body().heading("More", 12.0).body()
doc = page.build(OutlineEntry("Summary", 1, 1), OutlineEntry("Details", 1, 1))
assert tree(doc.sections) == tree(page.build().sections)  # Details stays at level 2
```

Keep or replace the numbered test as you see fit.

### S1 (should fix): an added numbered heading ignores the font rules' appendix shift

The font rules give a numbered heading `_depth(label) + shift`, with shift 1 after a common title
over the appendices. An added heading gets plain `_depth(label)`, so it nests wrongly:

```python
page = Page().heading("1 Introduction").body().heading("2 Method").body()
page.heading("Appendices", 16.0).body().heading("A Proofs").body()
page.heading("A.1 First").body()
plain(page, "A.2 Second").body()
page.heading("B More").body().heading("B.1 Third").body()
page.build(OutlineEntry("Second", 1, 1))
# font rules alone: Appendices 1 > A Proofs 2 > A.1 First 3; B More 2 > B.1 Third 3
# with the outline: "A.2 Second" lands at level 2, a sibling of "A Proofs", not under it
```

Plan rule 4 says the level comes from the number "as for the font rules", and the level decides
the section tree and the heading pause. Fix: apply the same shift to an added numbered heading that
comes after the common title (for example `_Headings` keeps the block index where the shift
starts), with this case as a test.

### S2 (should fix): the NFKC test passes without NFKC

`str.casefold()` already folds "ﬁ" to "fi", so `test_titles_are_compared_after_nfkc_case_and_spaces`
passes with `unicodedata.normalize` removed from `_key`. Use a character only NFKC folds, for
example full-width letters in the entry, `OutlineEntry("Ｆｉｎａｌ Definitions", 1, 1)` against
the printed "Final Definitions" (kills the mutant), and keep the ligature case too if you like.

### N1 (nit): two entries naming the same block

When two entries match one block, the first one's level wins (`index not in added`); switching to
last-wins survives every test. One line in the docstring or a small test, your choice.

### Note (no change asked)

The outline can make a block a heading that the font rules' "stands over body text" rule would
refuse, for example the paper's title when the outline lists it among several top entries and the
file's metadata title differs. Plan section 6 accepted this risk (rule 3 covers the single-root and
metadata cases); no corpus paper has it. Recorded here only.

## Verdict

Changes requested: M1, S1, S2 (N1 optional). The code otherwise does what the plan and D-270 to
D-272 say, and it changes nothing on the corpus.
