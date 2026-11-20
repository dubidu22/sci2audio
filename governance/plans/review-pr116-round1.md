# Review of PR #116, round 1 (#68 units and abbreviations)

Reviewed head: ec0d1aa (main merged up to #71). Main has since moved to d30e6e7 (#103), so the
PR is in conflict. Date: 13 Nov 2026.

## What was run

| Check | Where | Result |
|---|---|---|
| fast suite | PR head | 1330 passed |
| ruff check, ruff format --check, lint-imports, deptry | PR head | all green, 2 contracts kept |
| nightly Hypothesis profile (new test file + conformance) | PR head | 131 passed; 2000 examples per property, 30k fuzz |
| slow ASR (`test_units_are_heard_as_words` and the existing round trip) | PR head, real Kokoro + faster-whisper small | 2 passed |
| fast suite with main (#103) merged in locally | local merge | 12 failed: 10 snapshots (expected), 2 #66 regression cases (see M4) |
| corpus listing of every `units` and `abbreviations` edit | 7 papers | all readings right in context |
| hand probes, about 70 texts | PR head and local merge | M1 to M3, S1 below |

Decisions checked one by one against the code: D-227 to D-243 (plan section 4 A to Q). The code
follows them, apart from the three gaps below where a rule as coded reads something wrong.
Registry order (D-150, D-190), whole-block claims (D-128: furniture and placeholders skipped),
the layer contract and "cli/web never import testing" all hold.

## Must fix

**M1. A glued "x" in algebra is read "times" and the variable is lost (D-242).**
`_times_x` reads a glued x as "times" whenever a boundary follows it, so:
- "We set y = 2x + 1" reads "y = 2 times + 1"
- "The term 3x^2 dominates" reads "3 times ^2"
- "Let f(x) = 4x." reads "4 times."

The voice then never says the variable. That is a change of meaning, not a reading (D-57). Fix:
no edit when an operator stands next to the number-and-x, that is when `= + - − × · / ^ ( < >
≤ ≥` comes right before the number or right after the x (spaces allowed between). "10x speedup",
"3.5x faster", "2× faster" and "3 x 4" keep reading as they do now. Add regression cases for the
three texts above.

**M2. Sub-figure and panel labels are read as billions (D-236, D-241).**
The label check looks only at the word right before the number. Plural label words are not in
`labels`, and the second label of a list has "and" or "," before it:
- "Figures 2B and 3B" reads "Figures 2 billion and 3 billion"
- "See Figs. 2A and 3B" reads "See Figures 2A and 3 billion"
- "In panels 2A and 4B", "Tables 1A and 1B", "Types 1A and 2B": the B reads "billion"
- "See Figure 1, panels A and 3B": the same

"Fig. 3B" alone is right. Fix both parts: (a) add the plurals (figures, tables, sections,
panels, experiments, studies, groups, conditions, types, phases, chapters, appendices, lemmas,
theorems, equations, lines, rows, steps, cases, parts, items, pages, classes, levels, stages,
versions, trials, waves, sets); (b) let a label word carry over a list of labels joined by
",", "and", "or", "&" or a dash ("2A and 3B", "1A, 1B, 2C", "3B–D"). Cases for each text above.
"Our 7B model" and "the 175B model" must still read "billion".

**M3. A glued magnitude at the very end of a block is never read (D-241).**
Also found by the KB PR #34 review. `units.py:248`: at the end of the text the slice is "",
and `"" in _UNIT_JOINTS` is True. So "trained on 15M", "300K" and "It was 2bn" as the last
characters stay as printed, while "300K." works. Fix the check (for example
`text[e:e + 1] not in tuple(_UNIT_JOINTS)` or an explicit end test) and add the case.

**M4. Merge main (#103 landed as d30e6e7).**
Conflicts: `textprep/__init__.py`, `textprep/registry.py`, `tests/regression/english.toml`, both
snapshots. Registry order after the merge: links, citations, footnote marks, units,
abbreviations. Two #66 regression cases change by this PR's rules and need their `expected`
updated, which is the decided reading (D-230):
- `author-year-nested`: "We use language models (for example, BERT) as a baseline."
- `numeric-citation-after-an-abbreviation`: "This was shown before, compare reference 4, and
  Eq. [3] holds." (or "Equation [3]" with S1)

Then regenerate both snapshots and explain the diff. I did this merge locally: the per-category
snapshot then shows `abbreviations: set-aside: 1` in Nowak (an abbreviation inside a citation
#66 removes), which is right and belongs in the PR body.

## Should fix

**S1. "Eq. [3]" keeps "Eq." (D-230).** #66 now reads a bracket after "Eq." as its number
(D-171, its case above), but `_LABEL` takes only a digit, "(" or a lone capital, so "Eq."
before "[" is left as "eq". Let `_LABEL` also take "[" followed by a digit.

**S2. No test that the wheel ships the two TOML files.** Plan section 3 promised one; the PR
body says it was checked once by hand with `uv build`. Add a test, for example from hatchling's
own file list (`WheelBuilder(root).recurse_included_files()`), or a `slow` test that builds the
wheel and lists it.

**S3. PR body is out of date.** It says one `units` edit is set aside in Waskom (the X of a
DOI). Neither the PR's snapshot nor the merged one has a `units` row for Waskom. Correct it
after the merge.

## Nits (no change needed)

- N1. "We used 3 N samples" reads "3 newtons samples", and "The 2 V curve" reads "2 volts
  curve". Both are the accepted D-236/D-237 behaviour; giving N the `not_before_word` flag
  like A would fix the first, if you want.

## Not findings (checked and right)

- Every corpus edit: 33 "e.g.", 11 "i.e.", Eq./eq. 32 (Arsiwalla's glued "eq.(1)"
  included), Alg. 12; 9 kilograms, 441/64/130/351 thousand, 332/15 million, 12 gigabytes,
  millielectronvolts, picoseconds, angstroms in both printed forms, μB, "d times d".
- Left as printed as decided: Dr., vs., et al., %, "X ~ N(0, 1)", 1990s, 2D, 5 pm, 0x1F,
  x86, "1 A note", "Step 3 A", "GPT-3", "COVID-19".
- #66 interplay on the merge: "Ref. [12]" and "Refs. [3, 5]" read "reference 12",
  "references 3 and 5"; "(e.g., [3])" removed whole, the e.g. edit set aside.
- 100k-character block runs in well under the limit; the ASR check tells the old and new
  scripts apart.

## Note for round 2

#105 (cutter fix) merged into main as 3f0149d after this round. Round 2 checks that the branch
includes both d30e6e7 (#103) and 3f0149d (#105).
#65 (Unicode and hyphens, PR #98) merged into main as a0d363a after 3f0149d. Round 2 checks
a0d363a too, and that the character and hyphen steps stay last in the registry (D-150), after
units and abbreviations. #98 composes "˚A" to "Å", so check that the angstrom edits still apply
and do not overlap.
