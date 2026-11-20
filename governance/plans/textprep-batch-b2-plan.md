# Textprep batch B2: #445, #449, #448 (marks and hidden runs)

Status: **PROPOSED, waits for the coordinator's approval** (every PR is critical: regression rows).
Author: textprep lane thread "Fix marks and hidden runs in textprep", 18 Nov 2026. Base: main 1797ceb.
Read first: `next-batches-2026-11-18.md` (B2, AC-445.x, AC-448.x, AC-449.x, condition C2),
rules 1.4.6, D-744, `textprep-batch-3-plan.md` (format), review lessons in
`memory/MEMORY-archive-2026-11-18.md`, the three issues and their comments, and the code they name.
Measured on a local scratch branch (nothing pushed): all three changes prototyped
(`plans/b2-fuzz/proto.diff`), the fast suite and the corpus run against them, and a fuzz built
for AC-445.2 (`plans/b2-fuzz/`).

## 0. Summary and PR split

| PR | issues | files | why critical |
|---|---|---|---|
| **PR 1** | #445, #449 | `textprep/furniture.py` (`removed_span`), `textprep/notation.py` (`through_unread`), `textprep/numbers.py` (one guard), `textprep/footnotes.py` (new `raised_numbers`), `textprep/units.py` (magnitude after a raised number) | new en + de regression rows; risk:high |
| **PR 2** | #448 | `textprep/footnotes.py` (`AffiliationMarkStep` only) | new rows; **edits 3 existing rows** (§3.3) |

Order: PR 1 first; PR 2 is written while PR 1 is in review and opened after PR 1 merges (both
edit `footnotes.py`, different functions). One review thread for the batch (Opus high).

**C2 (corpus snapshots): no change.** With all three prototypes applied, `test_app_corpus.py`
(scripts and reports of every golden paper) passes unchanged, and so does every corpus test in
the fast suite. AC-445.3 and AC-448.4 hold as measured; the PRs re-run them.

Two findings change the issues' assumptions (lesson #502: a guessed cause is re-checked):
- **#445's cause is not the one the issue names.** In all three rows the unit edit covers only
  "m²"; no match spans the hidden run. The real cause: removing the run leaves two white-space
  characters ("5 ␣␣m²", "p < .05 ␣\nm²"), and the numbers step's letter-power guard ("not after
  a number and *one space*") misses them, so it reads "²" as " squared"/" Quadrat" and the unit
  edit is set aside. The run-2 text has one space, so it reads the unit. The issue's mechanism
  (a match spanning a hidden run, set aside against the removal) is real too: the fuzz finds it
  for statistics ("x < [run] 5") and abbreviations ("e.[run]g."). PR 1 fixes both.
- **The English row of #445 is unstable on main even without the run**: `p < .05\nm² here`
  reads "m squared" on run 1, "metres squared" on run 2 (the English guard sees only a space,
  not a line break, after a number). Since AC-445.1 wants the row stable, PR 1 fixes this too
  (a line break between a number and its unit is common in PDFs).
- **#449's "K" rule is in `units.py`**, not `numbers.py` (magnitudes, D-241). German has no
  magnitudes, so AC-449.3 holds by construction (pinned by a row anyway).

## 1. PR 1, #445: hidden runs inside number, unit, statistic and abbreviation matches

**P1.1 Tests first** (rows before code): the issue's three rows as regression cases
- en `hidden-run-between-a-number-and-its-unit-on-a-new-line` (`p < .05 [Jane]\nm² here` → "p less than .05 square metres here");
- de `de-hidden-run-between-a-number-and-its-unit` (`Es sind 5 [Jane] m² hier` → "Es sind 5 Quadratmeter hier") and `de-hidden-run-before-a-unit-on-a-new-line` (`p < .05 [Jane]\nm² hier` → "p kleiner als 0 Komma 0 5 Quadratmeter hier");
- plus one en row each for the split mechanism: a hidden run inside a statistic ("x < [13] 5"), an
  abbreviation ("e.[13]g." with a page-break marker) and a unit compound ("5 [13] mg/kg"), and an
  en row without any run pinning `5\nm²` and `p < .05\nm²` (the main bug above).
Every row is checked twice by the harness (read_twice), so AC-445.1 "on run 1 and on run 2" is
the harness's own check.

**P1.2 `removed_span` (furniture.py)**: a removal with white space on **both** sides also takes
the white space before it, as it already does before closing punctuation. So "5 [run] m²" leaves
"5 m²", the printed text without the run, which is what a second run reads. Used by
`HiddenRunStep` and `AffiliationMarkStep` (an affiliation mark " 2 " between spaces). Report
spans move by the white space; the spoken text does not (render already joins white space).

**P1.3 `through_unread` (notation.py)**: a candidate mapped back over an unread span (a hidden
run, a footnote or affiliation mark that an earlier step removes) is split into the pieces beside
those spans: the first piece keeps the replacement, the others are removed with the same reason,
as `furniture.edits_around` does for links and citations (#434). Today such a candidate overlaps
the accepted removal and is set aside on run 1 only. `edits_through_unread` (units,
abbreviations) gets it through `through_unread`; its replace-only check stays for the rules' own
edits. Characters the Unicode step removes (soft hyphen, invisible) are not split around: no
earlier step removes them, so covering them stays right (D-150).

**P1.4 numbers.py `_LETTER_POWER`**: the guard "not after a number and a space" / "not after
'.' or ',' and a space" accepts any one white-space character (`\s`), as German's twin already
does (`numbers_de._LETTER_POWER`) and as the units step's gap allows. One regex line.

**P1.5 Unit tests** (`test_textprep_hidden_runs.py`, `test_notation*.py` or the numbers tests):
`removed_span` cases (both-sides white space, a line break on one side, the run at a line start);
`through_unread` splitting (two runs inside one candidate, a run at the candidate's edge is not
split, soft hyphen not split); the en guard with "\n" and "\t".

**P1.6 Existing tests that change (test-harness and pins, named):** 25 cases in
`tests/unit/test_textprep_hidden_runs.py` pin today's removal spans (`test_removed_span` rows
"a xy b" and "a  xy  b", the side-by-side, every-kind, reason and placeholder tests): their
expected spans gain the white space before the run; the spoken text they check is unchanged. One
case in `test_textprep_affiliation_marks.py` (`test_digits_commas_and_note_symbols_make_a_mark[ 2 ]`)
expects the removed text "2" and now gets " 2". No regression row's `expected` changes in PR 1.
No test-harness code changes.

**P1.7 AC-445.2 measurement.** `fuzz5.py FAMILY=hidden` compares run 1 with run 2 only, and on
main most of its differences come from shapes that read differently on run 2 *without* any hidden
run (citations then units "[3] m²", "2019 x", footnote intros): 49 of 2,580 texts at seed 41 are
unstable with the runs taken out. So I measure with `plans/b2-fuzz/fuzz445.py` (fuzz5's
generator, more number/unit/statistic/abbreviation tokens, only texts that have a hidden run),
which reads each text twice and also the same text with its hidden runs taken out, and counts:
(a) second-run differences where the run-free text is stable, (b) texts whose accepted
replacements from the statistics, numbers, units and abbreviations steps differ from the run-free
text's. Measured, seeds 41 to 44, about 10,100 texts:

| | main 1797ceb | prototype |
|---|---|---|
| (a) hidden-only second-run differences | seed 41: 21, 42: 24 | **0, 0, 0, 0** |
| (b) four-step replacements differ from the run-free text | seed 41: 39, 42: 44 | **0, 1, 0, 0** |

The one left (seed 42): `= , < [Jane]\n[e.]https://x.org`: the statistics match " <\n" is split
around the run into " <" and "\n"; the links step already removed that "\n", so the second piece
is set aside and the first is read ("less than"), where the run-free text sets the whole match
aside ("<"). Both are stable on run 2. It needs "<" glued to a removed link across a hidden run.
I propose to accept it and file it as a follow-up issue (lane:textprep, low), because making the
pieces all-or-nothing would need the runner to settle edits in groups (a text-step interface
change, critical on its own). **Open choice for the coordinator:** accept (recommended), or ask
for the runner change in this batch.
The PR states the counts from the exact commands; AC-445.2 is read as "(a) = 0 and (b) = 0 apart
from the named residual". fuzz5.py itself is also run and its differences listed as pre-existing
(each one reproduces with the runs taken out).

**P1.8 Pre-existing classes seen, not fixed here** (the run-free text is unstable on main): I
check each against #405 and open issues and file what is new (one issue per class): "[3] m²"
(citation then unit), "2019 x" → "2019 times" → "2,019 times", a footnote whose text starts with a
hidden run before punctuation ("Footnote 2.."). None is in B2's acceptance criteria.

## 2. PR 1, #449: a raised mass number before "K"

**P2.1 Tests first:** en rows `raised-mass-number-before-k-is-not-thousand` (`We use [40]K and [87]Rb atoms.` with sup runs), `plain-k-after-a-number-reads-thousand` (`We use 40K and 87Rb atoms.`, `441K apps`), de row `de-raised-mass-number-before-k` (`Wir nutzen [40]K-Atome und 40K-Atome.`, unchanged). A unit test for the PDF shape: a run of digits set small and raised (size and box, no tag) before "K".

**P2.2 The reading.** "Reads as printed" cannot mean the script keeps "40K": a second run sees
plain "40K" (run tags are not carried, D-577) and AC-449.2 keeps that as "40 thousand". So the
units step writes the raised digits as **superscript digits** ("⁴⁰K"): that is how it is printed,
it is what a Unicode-encoded source already reads today (main reads "⁴⁰K" as printed on both
runs), no step reads it as a number, and the English voice says it exactly like "40K" (checked
with misaki's G2P: "forty K" for both). The magnitude edit is dropped. Reason in the report:
`raised "40" before "K" kept as printed, not "thousand"`.

**P2.3 Code.** `footnotes.raised_numbers(document)`: per block, runs of 1 to 3 ASCII digits set
small and raised by the rules the affiliation marks use (`_set_small` and `_superscript`: a
`sup` tag, or smaller than the block's main size and RISE em above a main-size run). Mass
numbers have at most three digits, so a longer raised number keeps today's reading. In
`UnitStep.find`, only where the language has magnitudes (en): a magnitude edit whose letter
starts where such a run ends becomes a replace edit of the digits with superscript digits. This
is the one units edit that covers the number; it cannot overlap the numbers step there (no
numbers rule reads a lone 1 to 3 digit number before a letter); the module docstring says so.

## 3. PR 2, #448: affiliation marks only after the author line

**P3.1 Tests first:** en rows for both title shapes of the issue (`[13]CO and C[18]O
observations of the Taurus cloud` at the block start; `Mapping [12]CO, [13]CO and [15]NH3 in\n[13]CH4-rich regions`), each followed by an author line and affiliation lines whose marks still go; the reverse-case row (`¹Ca' Foscari University`, `²Co-design Lab`, `³In Silico Institute` after an author line: marks read, AC-448.2); a row with authors and affiliations in one block (marks go); de row `[13]CO-Beobachtungen der Taurus-Wolke` with an author and an affiliation line.

**P3.2 The cue (structural, AC-448.3).** "Before an affiliation" counts only after the author
line: once a mark after a name has been seen earlier in the title block (an earlier block, or
earlier in the same block). A footnote mark after a name (taken by the footnotes step, such as
"Arden∗") counts as that evidence too, so an author line with only a corresponding-author mark
still opens the affiliations. The "after a name" shape is unchanged. `_affiliation_shape` is
split into `_after_name` and `_before_affiliation`; no word list grows.

**P3.3 Existing rows that change (critical, named):** three rows test a mark before an
affiliation in a title block that has no author line, so with the cue they would read "1AI Lab":
`affiliation-marks-not-isotope-numbers` (en), `affiliation-marks-not-before-element-symbols`
(en), `de-affiliation-marks-not-isotope-numbers` (de). Each gets an author line block
(`Jane Roe¹`, `Jana Rot¹`) before its affiliation block; their `expected` gains that line; the
readings they protect (mass numbers read, affiliation mark removed) are unchanged. Also 11
parametrised cases of `test_marks_after_a_name_or_before_an_affiliation_are_removed` and
`test_a_mark_at_a_line_start_comes_before_an_affiliation` in `test_textprep_affiliation_marks.py`
build a lone affiliation block; they get an author block first. Trade-off named: a paper whose
author line has no mark at all but whose affiliations are numbered (rare) keeps those numbers
read, which is the safe way to fail (D-57).

**P3.4 Corpus:** chi, arsiwalla, liu and biggs read as now (measured with the prototype; the
corpus scripts and reports are unchanged).

## 4. Common to both PRs

- Branches `textprep/hidden-runs-mass-numbers` (PR 1) and `textprep/affiliation-author-line`
  (PR 2) from main; merge main, never rebase; no "fixes #N" in commits; `Closes #445, #449` and
  `Closes #448` in the PR bodies.
- Mutation: I write the mutants for the new code (removed_span both-sides branch, the split, the
  guard, raised_numbers, the magnitude swap, the author-line flag) and state killed/total in the
  PR; nightly seeds (Hypothesis `nightly` profile on the textprep property tests) before hand-off.
- Before hand-off: the CLAUDE.md checks, Linux CI green, my own `ci:full` green, label removed.
- Ledger line per PR in `ledger/implementation.md`. Size: PR 1 about 80 lines of code and 120
  of tests and rows; PR 2 about 30 lines of code and 60 of tests and rows.

## 5. Questions for the coordinator

1. Approve the PR split and the reading of AC-445.2 in P1.7 (accept the one named residual and
   file it), or require the runner change.
2. Approve P2.2 (superscript digits as the run-1 reading of a raised mass number before "K").
3. Approve the three existing row edits of P3.3.
