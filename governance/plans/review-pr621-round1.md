# Review of PR #621, round 1 (textprep B9: #414, #415, #402)

Reviewer: B9 review thread (Opus high, critical). Reviewed head **efae3c7**, base main b6355cc. 19 Nov 2026.
Verdict: **changes requested.** Four must-fix items (three readings the PR makes worse than main, one merge conflict), two nits. One fix commit, on this list only.

## What I checked and found sound

- **Regression rows fail on main.** PR's `english.toml` and `german.toml` run against main b6355cc src: 7 cases fail (the 6 new ones, 3 en and 3 de, and the changed D-668 case); all pass on the head.
- **D-668 row line 4.** Only line 4 ("It was shown in reference 1 and reference 3." to "It was shown in references 1 and 3.") and the goal text change, as decision A says.
- **Pinned tests.** The three decision B tests change as the plan says; the two further changed rows ("(cf. (Smith, 2020) (Lee, 2019) 2020) is cited.", "(e.g. (Smith, 2019); Jones, 2020) is cited.") follow plan 2.2 and 2.3 and are listed in the PR body with their old readings. Accepted.
- **efae3c7 work bound.** `test_a_deep_nest_of_lead_words_and_years_reads_each_level_once_in_linear_time`: characters parsed per character of text at 400 / 1,600 / 3,200 levels are 119.3 / 31.3 / 16.6 (en) and 103.2 / 27.3 / 14.6 (de), identical on the head and on main; the bound is 100 at 1,600 levels, against about 1,600 for the quadratic version (mutant 415-u killed in `hand-r4.log`). The ratio falls with depth because the D-599 budget caps the work, so the bound only holds at the test's depth; that is fine as written.
- **12,000-text equivalence** of b357ac2 and efae3c7 (`plans/b9-probes/diff_items.py`, seeds 1 to 3 × 4,000): 0 of 12,000 read differently. Holds.
- **Corpus.** B6's `corpus_utts.py` (13 sources; default, figures off, figures and formulas off; both runs): 23,381 lines, byte-identical main vs head.
- **#402.** 30 hand probes en/de: list joins go, clause joins stay, sentence-first word keeps, German noun limit as pinned, "z. B. Müller und https://x.org hier" reads "zum Beispiel Müller hier". No finding.
- **#414 core rows, #415 issue rows, decision B rows**: all as the plan says, en and de, both runs.
- **CI at efae3c7**: tests on ubuntu, macOS and Windows green, CI passed green.

## Must fix

**M1. A lead-word nest with a two-name inner bracket and a "," before a flat part reads unbalanced and speaks the year.** Found by the PR's own `test_a_nest_reads_balanced_and_the_same_on_a_second_run` (`test_textprep_citations.py`): it fails on every run with `--hypothesis-seed=5` (dev profile).

| printed | main b6355cc | head efae3c7 |
|---|---|---|
| `(see (Smith, 2019; Lee, 2020), Lee, 2020) found it.` | `Smith and Lee, Lee found it.` | `Smith and Lee, Lee, 2020) found it.` |
| `(see (Smith, 2019; Lee, 2020), Jones, 2020) is cited.` | `Smith and Lee, Jones is cited.` | `Smith and Lee, Jones, 2020) is cited.` |
| `(vgl. (Müller, 2019; Lee, 2020), Jones, 2020) wird zitiert.` | `Müller und Lee, Jones wird zitiert.` | `Müller und Lee, Jones, 2020) wird zitiert.` |

Cause: the new lead-words condition in `_listed_inner_names` (`behind = ... or self._only_lead_left(before)`) lists the inner bracket after "see", and the rest's flat part is then read without its year removal. Required: these three rows read as on main (the readings in the middle column), both runs. Tests: the three rows in a parametrized unit test (both runs), and the seed-5 text as an `@example` on the property test.

**M2. "; and" / "; und" after a lead-word nest item drops the later name** (main kept it as printed). The PR makes "; and" a separator ("(Smith, 2019; and Jones, 2020)" and "((Smith, 2019); and Jones, 2020)" both read "Smith and Jones is cited."), and #415's criterion is "reads its names as the flat form does"; the flat forms below read "Smith and Jones is cited." on the head.

| printed | main b6355cc | head efae3c7 | required |
|---|---|---|---|
| `(e.g. (Smith, 2019); and Jones, 2020) is cited.` | `(for example and Jones, 2020) is cited.` | `is cited.` | `Smith and Jones is cited.` |
| `(e.g. (Smith, 2019; Lee, 2020); and Jones, 2020) is cited.` | `(for example and Jones, 2020) is cited.` | `is cited.` | `Smith, Lee and Jones is cited.` |
| `(see (Smith, 2019); and Jones, 2020) is cited.` | `(see Smith; and Jones, 2020) is cited.` | `(see Smith) is cited.` | `Smith and Jones is cited.` |
| `(see (Smith, 2019; Lee, 2020); and Jones, 2020) is cited.` | `(see Smith and Lee; and Jones, 2020) is cited.` | `(see Smith and Lee) is cited.` | `Smith, Lee and Jones is cited.` |
| `(z. B. (Müller, 2019); und Jones, 2020) wird zitiert.` | `(zum Beispiel und Jones, 2020) wird zitiert.` | `wird zitiert.` | `Müller und Jones wird zitiert.` |
| `(vgl. (Müller, 2019); und Jones, 2020) wird zitiert.` | `(vergleiche Müller; und Jones, 2020) wird zitiert.` | `(vergleiche Müller) wird zitiert.` | `Müller und Jones wird zitiert.` |

The "see"/"vgl." rows without "and" ("(see (Smith, 2019); Jones, 2020)" reads "(see Smith)" on main and head) are older and go to #626 (comment below). If the two "see"/"vgl." rows above can only reach the required reading by changing that older "see" rule, read them as on main instead (the main column) and say so in the answer; the four "e.g."/"z. B." rows must read as required. Tests: the six rows, parametrized, both runs.

**M3. A run whose first bracket is no citation loses a number that main read.** `_bracket_lists`' docstring says whether the brackets are citations "is decided at the first one", but when the first is no citation (`_numeric` returns `None` before `_list` takes the later ones), the later brackets are decided one by one: the middle ones go as asides and only the last is read.

| printed | main b6355cc | head efae3c7 |
|---|---|---|
| `Table [1], [2] and [3] show it.` | `Table [1], references 2 and 3 show it.` | `Table [1], and reference 3 show it.` |
| `Table [1], [2], [3] and [4] show it.` | `Table [1], references 3 and 4 show it.` | `Table [1], and reference 4 show it.` |
| `The values x = [1], [2] and [3] hold.` | `The values x equals [1], references 2 and 3 hold.` | `The values x equals [1], and reference 3 hold.` |
| `x = [1], [2], [3] and [4] hold.` | `x equals [1], references 3 and 4 hold.` | `x equals [1], and reference 4 hold.` |
| `Eq. [1], [2] and [3] hold.` | `Equation [1], references 2 and 3 hold.` | `Equation [1], and reference 3 hold.` |
| `It holds[1], [2] and [3] here.` | `It holds[1], references 2 and 3 here.` | `It holds[1], and reference 3 here.` |
| `Siehe Tabelle [1], [2] und [3].` | `Siehe Tabelle [1], Quellen 2 und 3.` | `Siehe Tabelle [1], und Quelle 3.` |
| `Es gilt x = [1], [2] und [3] hier.` | `Es gilt x gleich [1], Quellen 2 und 3 hier.` | `Es gilt x gleich [1], und Quelle 3 hier.` |

This is also a counterexample to the r1 claim that mutant 414-h (the per-item citation check) is equivalent: `search_414h.py`'s texts put no label word, sign or glued word before a run's first bracket.
Required: all eight rows read as on main (middle column), both runs; "CI [1, 3] and [12] show it." keeps "confidence interval 1 to 3 and reference 12 show it." (#151). What such a run should read is a ruling question, filed as **#634** (v2); the unit test names #634. Tests: the eight rows and the CI row, parametrized, both runs. Correct the `_bracket_lists` docstring sentence and the PR body's 414-h row.
(Note from my prototypes: re-starting the run at its second bracket when the first is no citation restores the 3-bracket rows but reads the 4-bracket ones "Table [1], show it.", so it does not meet this item; keeping later brackets as printed breaks the CI row and its second run.)

**M4. Merge main.** The PR is in conflict (`mergeable_state: dirty`): main moved to 805da4e (#609, CHANGELOG lines) after 12f85a7 (#630). Merge main into the branch (never rebase), keep both CHANGELOG entries, in the same fix commit or as its merge parent. Then Linux CI, and `ci:full` on the final head (critical: three systems before merge).

## Nits (fix in the same commit)

- N1. PR body: "seven new cases" is six new cases (3 en, 3 de) plus one changed line.
- N2. With M3: the `_bracket_lists` docstring sentence on label words and signs, and the 414-h row of the mutant table.

## Deferred (filed, milestone v2)

- **#634** (new): what a run of brackets after a label word or a sign reads (M3's question).
- **#626** (comment): "see"/"vgl." lead-word nests with a flat part ("(see (Smith, 2019); Jones, 2020)" reads "(see Smith)"), and inner brackets joined by "&", "and", "or". Same on main and head. https://github.com/dubidu22/sci2audio/issues/626#issuecomment-7003435380
- **#622** (comment): two mixed "or"/"and" lists whose reading changes from one wrong reading to another ("It holds [1], [2] and [3] or [4] here."; "It holds [1] or [2], [3] and [4] here."). Pure "or" lists read as before, so #414's second criterion holds for them; the mixed rows go with the "or" ruling rather than into this PR. https://github.com/dubidu22/sci2audio/issues/622#issuecomment-7003435712

## For the final round

After the fix commit: I rerun every probe file of this round on the new head against main, the property tests with seeds 0 to 15 (dev profile), my own hand mutants of the new lead-word and run-head code, read the three-system `ci:full` run and the nightly seeds, and repeat the corpus diff.

Probe files (this container only): `/home/user/probe/{en,en_nest,de,mx,flat,flatde,s2}.txt`.
