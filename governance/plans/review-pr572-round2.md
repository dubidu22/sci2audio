# Review of PR #572, round 2 (final-round checks)

Reviewer: B2 review thread (critical, Opus high). Reviewed head **de21173** (merge of main 675d1c6
into d81d24c; d81d24c is the round-1 fix commit on 38e56e0).
Result: **CHANGES REQUESTED, 1 must-fix (tests only, two cases).** Push one commit with exactly
F3; no change to `src/`.

## Round-1 fixes

- F1 fixed as asked: `_mass_numbers` keeps the magnitude edit when `start > 0 and
  text[start - 1].isalnum()`; test `test_a_raised_run_glued_after_a_letter_or_digit_is_no_mass_number`
  with both cases. Probes re-run on d81d24c: "10⁴K", "10³K … 10⁶M", "2⁴⁰K" read as main and are
  stable; every mass-number shape of round 1 is unchanged; "3x⁴⁰K" reads "3 times 40 thousand"
  (as main).
- F2 fixed: one CHANGELOG Unreleased / Fixed line naming #445 and #449.
- Merge of main (CHANGELOG conflict with #575): the PR diff against main equals the d81d24c diff
  against 1797ceb, apart from the CHANGELOG context lines (checked with `diff` of both diffs).

## Final-round checks

- **Three-system CI on de21173:** run 44417155064 (workflow_dispatch, head_sha de21173), tests
  ubuntu, macos, windows all success, both Chromium shards success, `CI passed` success. Linux PR
  run 44416294005 green.
- **Mutation** (`mut3.py` copy with this venv, ROOT = worktree at d81d24c, tests
  `tests/unit/test_textprep_{regression,hidden,affiliation,units,numbers,footnote,statistic,abbrev}*.py`,
  `-m "not slow and not benchmark"`, `HYPOTHESIS_PROFILE=ci`, baseline PASS before each batch).
  Ran the author's mutants 0 to 5 and 19 to 23 (18 no longer applies after F1's reflow; my 23
  replaces it) and five of my own (23 to 27):

  | # | mutant | result |
  |---|---|---|
  | 0, 1 | `removed_span` white-space-after branch dropped / `== ' '` | killed |
  | 2, 3 | `_around` not used / every piece keeps the replacement | killed |
  | 4 | `skip_end <= candidate.end` → `<` | survived, **equivalent** (round 1: 200k random, 0 diffs) |
  | 5 | `at <= skip_start` → `<` | killed |
  | 19, 20 | no superscript translate / wrong `ends` key | killed |
  | 21 | F1 condition dropped | killed |
  | 22 | F1 `isalnum` → `isdigit` | survived: differs only after "<digit>x" ("3x"+sup"40"+"K"); accepted, as the author said |
  | 23 | magnitude-letter check dropped | killed |
  | **24** | `start > 0 and` dropped (index -1 reads the block's **last** character) | **survived** → F3a |
  | **25** | `start > 0` → `start > 1` | **survived** → F3b |
  | 26 | `_LETTER_POWER` caret exception `(?<!\^)` dropped | survived, **pre-existing on main** (same mutant on main 675d1c6 survives) → filed **#578** |
  | 27 | `removed_span` `while` → `if` (one white-space char only) | killed |

  The author's other mutants (6 to 17) were run by the author on 38e56e0 with the same script
  (`plans/b2-mutation/mut_pr1_first.txt`); F1 does not touch their code.
- **Nightly seeds:** own seed 2024 (round 1, same code as F1's patch: 3,985 passed) and seed 4242
  on d81d24c (`HYPOTHESIS_PROFILE=nightly`, `tests/unit/test_textprep_*.py`: 3,987 passed); the
  author's 1, 31337, 555.
- Corpus snapshots: unchanged (CI fast suite green on three systems with the corpus tests).

## Must fix

**F3. Two boundary cases of F1's condition are untested (mutants 24 and 25 survive).** Tests only:

- **F3a** (kills 24): a raised mass number that starts its block, in a block whose text ends in a
  letter or digit, is still a mass number. Real shape: a heading "⁴⁰K in rocks 5". With mutant
  24 it reads "40 thousand in rocks 5"; with the PR "⁴⁰K in rocks 5". Add to
  `tests/unit/test_textprep_units_abbreviations.py` one test (or a case of
  `test_a_magnitude_after_a_raised_mass_number_is_no_thousand`): a heading block with runs
  sup `"40"` + `"K in rocks 5"`, followed by a paragraph `"Text."`: UnitStep gives one edit
  whose reason starts `raised "40"`, and `read_twice` gives `["⁴⁰K in rocks 5", "Text."]` on
  both runs.
- **F3b** (kills 25): add the case `"1"` + sup `"4"` + `"K and more"` (a raised run at offset 1,
  after a digit at the block's start) to
  `test_a_raised_run_glued_after_a_letter_or_digit_is_no_mass_number`: no edit whose reason
  starts `raised "`. (With mutant 25 the PR reads "1⁴K and more"; with the PR "14 thousand and
  more", as main.)

State in your reply that mutants 24 and 25 (`or text[start - 1].isalnum()` and `start > 1`) are
killed by these tests, with the failing test names. No `src/` change; no other test change.

## After F3

Message me the new head once its Linux CI is green. I start the three-system run of that head
myself (D-580 needs it on the merged head), then merge pinned to it and poll main's CI.

## Filed

- **#578** (lane:textprep, risk:low): no test pins the caret exception of the letter-power guard
  ("x^2 x⁶"), pre-existing.
