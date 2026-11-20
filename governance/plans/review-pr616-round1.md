# PR #616 review, round 1 (head a1f030b)

Reviewer: textprep B6 review thread, 19 Nov 2026 ~05:20Z. Critical (Opus high). Plan `textprep-batch-b6-plan.md`, D-780.
Verdict: **changes requested**, one fix commit: F1 (must-fix), F2 (should-fix), T1 (tests), N1 optional.
Probes and logs: `plans/b6-review/` (run from the PR worktree; main numbers with `PYTHONPATH=<main>/src`).

## What I checked and found right

- Scope: 9 files, all textprep lane (`textprep/`, `testing/`), its tests, CHANGELOG. No snapshot, golden script or corpus truth file moves.
- Rows first: at b3e1daf (src = main b32612d plus the harness helper) the three new rows fail `test_the_script_is_the_expected_one` (utterances), the two #482 rows fail the new second-run cut check, and `test_the_errors_are_the_known_ones[stress-de]` fails. On a1f030b all pass (1,292 passed, 6 xfailed in the four files).
- #479 `_label_again`: a strict subset of the numbers step's same-word rule (the cut needs the full stop to be printed, and a capital after it), so it changes no reading. Probes (`fp.py`): "Kap. 2. Kap. 3", "Rn. 12. Rn. 13", "Az. 3. Az. 4", "Abs.2. Abs. 3", a line break between, all cut and the same on run 2; "der 3. der Saison", "die 2. die", "absatz 2. Absatz", "(Absatz 2. Absatz 3)" (#615) not cut. Matches the plan.
- Harness: `second_run` is `read_twice`'s old body unchanged (same context, same placeholder list, strict); `read_twice` returns the same. The D-577 script check is not weakened. The six `SECOND_RUN_CUT_EXCEPTIONS` each carry a reason, are strict xfail, and fail on main too.
- #533: the seven tests use the literal 40 and name their rule; the author's hand-mutant log (27/27) is valid (clean worktree, baseline first, first failing test named).
- Corpus: I re-ran `corpus_utts.py` on main and on the branch, both runs, three settings. Default: identical. Only `acl2023-chi-plue` with "Tables and figures" off (with or without "Formulas") differs, 9 lines per run, the same on run 1 and run 2; the joined text is identical and no part is over the limit. This confirms the PR body.
- fuzz2 seed 3 × 400: 0 differ (body: 0 of 2,700).
- Gate floors hold (the gate test passes; `known-errors.toml` untouched).

## Ruling on the reported deviation (chi-plue tables read as text)

**Accepted.** It is outside the default setting, the text read is the same, both runs agree (main did too), every part is under the limit, and main's table-1 cut split the range reading "1,350 | to 400". The cost is less even parts in number-dense text, because every space beside a digit ranks 5. That is the price of finding number readings from the text alone; a narrower digit rule would need the numbers step's tables and is not asked for here. #482's third criterion ("corpus utterances unchanged") holds for the default settings, which is what the issue measured. After the F1 fix, re-run the corpus diff and state the result again.

## F1 (must-fix): several of the steps' multi-word readings are not ranked 5 (#482 criterion 1)

Criterion 1 asks that a space between the words of a known multi-word reading of the abbreviation, unit and number steps ranks below every other space. `cover.py` lists every multi-word replacement that the regression rows and the 13 corpus sources make (default settings) and checks each inner space against `_joined`: 193 of 710 have an unranked inner space. Leaving out the placeholder notices (whole sentences, not a reading), the classes are:

| class | examples (printed → read) | from |
|---|---|---|
| fractions and ratios | "12/20" → "12 out of 20", "1/2" → "ein halb", "1/3" → "ein Drittel" | `numbers.py` (" out of "), `numbers_de.py` (N-de-7) |
| compound units without "per" | "N m" → "newton metres", "eV Å" → "electronvolt angstroms" | `units.py` (unit names joined by a space) |
| statistics symbols | "CI" → "confidence interval(s)" (7× in the corpus), "OR" → "odds ratio", "ηp²" → "partielles Eta-Quadrat" | `statistics.py`, `statistics_de.py` symbol readings |

They do move on a second run, the same way #482 describes (`gaps.py`, the shape of `test_a_long_sentence_is_cut_outside_a_reading_on_both_runs`, 30 positions each):

| printed | branch differs | main differs |
|---|---|---|
| en "95% CI" | 2/30 ("95% \| confidence" on run 1, "confidence \| interval" on run 2) | 2/30 |
| en "5 N m" | 2/30 | 2/30 |
| en "3 eV Å" | 2/30 | 2/30 |
| en "12/20" | **2/30** | **0/30** |
| de "1/2 der", "1/3 der" | 1/30 each | 1/30 each |
| de "ηp²" | 2/30 | 2/30 |

"12/20" is new with this PR: "12 | out" and "of | 20" now rank 5 (digit), so the only rank-4 place left is "out | of", inside the replacement, and the cut is drawn into it. A partly covered reading attracts the cut.
`fuzz4.py` = `fuzz3.py` with these shapes added to the pool, seed 1 × 150 per language: branch **83 of 300**, main 168 of 300 (fuzz3 alone: 9 %).

**Fix:** rank 5 for these from their own tables, as the plan does for the others: the fraction and ratio readings of `numbers.py` and `numbers_de.py` (the words between the numbers, and the fraction names after "ein"), the space between two unit names of `units.toml` (singular or plural), and the symbol readings with a space of `statistics.py` and `statistics_de.py`. Add "95% CI", "5 N m", "12/20", "1/2 der" and "ηp²" to the parametrized long-sentence test (each fails without its part of the fix), and give the fuzz4 numbers (seeds 1 and 2) beside fuzz2 and fuzz3 in the PR body, plus the corpus diff again. If one class cannot be found from the text, say why in the PR body and put it in #613 with its fuzz4 share, not silently.

## F2 (should-fix): the readings pattern is slow on punctuation-dense text

The alternatives that start with `\S+` ("X per Y", "X squared", "X cubed", "word Month") are tried at every place after a non-word character, and `\S+` runs to the end of the window and backs off, so one window costs O(window²). One window of 800 characters: "-a-a-a…" 9.24 ms, "word word …" 0.10 ms (`perf2.py`). Whole cutter on 160,000 characters (`perf.py`): "-a" 1.30 s, ".a" 1.44 s on the branch against 0.07 s on main (about 18×); plain words 0.31 s against 0.21 s. Still linear, so the linear-time tests pass, but a 4 MB input of such text costs about half a minute in the cutter alone.

**Fix:** let those alternatives start at the white space (for example `(?<=\S)\s+per\s+(?=\S)` and taking the places from the match), or bound the word (`\S{1,32}`), and give the before/after numbers of `perf.py` for "-a", ".a" and plain words in the PR body. No timing test asked.

## T1 (tests): seven more surviving mutants of the new code

`hand_extra.py` (same method as the author's `hand.py`: clean worktree of a1f030b, the cutter file, both regression files and the gate, `-x`, baseline green first). Killed: E2 (word-before window 32→8), E5, E7, E10 (alternatives unsorted), E11 (operators swapped). Survived, each needs a test that names its rule:

| # | mutant | a test that kills it |
|---|---|---|
| E3 | no `(?<!\w)` left bound | "darin Verbindung mit": "darin \| Verbindung" is no reading space |
| E4 | no `(?!\w)` right bound | "that isotope": "that \| isotope" is no reading space |
| E12 | `before_year` readings left out | German "und andere" ("u. a." before a year) |
| E14 | only the plural unit name | "degree Celsius" (singular only) |
| E15 | only "squared", no "cubed" | "x cubed" |
| E16 | only "square", no "cubic" | "cubic metres" |
| E17 | "to the power of" without the plain form | "10 to the power of 6" |

E13 (`after_paragraph` readings left out) is equivalent today: no list entry has an `after_paragraph` reading with a space. Say so in the PR body (it holds the next entry). E1 below is equivalent too.
Re-run the author's 27 and these 8 on the fix head and list them all in the PR body.

## N1 (nit, optional): `rank == 4 and` in `_cut_point` is always true for a place in `joined`

Every place in `joined` follows white space, and `_rank` returns 4 for every such place, so the guard never decides (mutant E1, guard removed, survives and is equivalent). Drop it, or keep it with a comment that says so.

## Round 2 (final)

One fix commit for F1, F2, T1 (N1 optional); Linux CI green; then I run `ci:full` (three systems), the mutation workflow on `utterances.py`, nightly seeds, re-check F1 to T1 with the probes above, and merge pinned to the reviewed head (MRG-03).
