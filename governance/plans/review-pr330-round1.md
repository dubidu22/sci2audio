# Review of PR #330, round 1

PR: textprep: citations read the same on a second run after a removal (#305), https://github.com/dubidu22/sci2audio/pull/330
Head e8354a7, base main 334e5a8 (main has not moved). Critical (regression cases), D-577 PR A.
Verdict: **changes needed** (R1-1 to R1-6). The approach is sound, and every claim I could check holds except the nightly seeds: two of my three seeds fail, and one of those failures is a new second-run break.

## What I checked, and what held

| claim | result |
|---|---|
| fast suite green | yes: 4979 passed, 1 skipped, 6 xfailed, 76 snapshots passed (ci profile, -n 8) |
| ruff, format, lint-imports, deptry | all clean (3 contracts kept) |
| corpus byte-identical to main | yes: all 13 corpus documents through `run_script_job` (with `output_folder`), main through PYTHONPATH, 39 files (script, report, text), `diff -r` empty |
| timing ratios | linear: citations shapes 7.7 to 8.6 against limit 32 (main 8.3 to 8.7), German blocks 7.4 to 8.4. Deep German nests `assert_near` went from 5.9 and 6.0 on main to 2.8 and 2.9 here, against limit 16. Worst shapes I made (row of years, "e.g." nests, separators, links) are linear at 8× (7.2 to 8.4), at most 2.3× main |
| fuzz | 8000 seeded token texts (en and de, whole chain twice): 26 second-run breaks here against 114 on main, and none of the 26 is PR-only |
| issue rows | every row of #305, #306, #308, #309, #291, #278 row 1, #272 and #259 reads the same on both runs |
| nightly seeds | **not held**: seeds 41, 555 and 8080 fail (R1-1, R1-2) |
| CI on head | green on Linux, macOS and Windows (run before the lean CI change) |

## Fix list (all required)

**R1-1. New second-run break in comma nests four deep.** With the nightly profile, seeds 555 and 8080 fail `test_a_nest_reads_balanced_and_the_same_on_a_second_run`, and seed 555 also fails `test_identifier_brackets_add_no_second_run_change`. Main passes all three.

| lang | printed | run 1 | run 2 | main |
|---|---|---|---|---|
| en | `It holds ((((Smith, 2019), Lee, 2020), Lee, 2020), Lee, 2020) found it.` | `It holds (Lee, 2020) found it.` | `It holds found it.` | `(((, Lee, 2020), …)`, stable |
| en | `It holds (((527794, (Smith, 2019)) (Smith, 2019), Lee, 2020), Lee, 2020) found it.` | `It holds (Lee, 2020) found it.` | `It holds found it.` | stable |
| de | `Es gilt ((((Müller, 2019), Weber, 2020), Weber, 2020), Weber, 2020) hier.` | `Es gilt (Weber, 2020) hier.` | `Es gilt hier.` | stable |
| en | `Text (e.g., (e.g., (e.g., (Smith, 2019), Lee, 2020), Kim, 2021), Park, 2022) more.` | `Text (for example, Park, 2022) more.` | `Text more.` | also breaks |

Each look peels one level, so a nest one level deeper than the looks allow breaks. Because the nightly workflow runs these properties, merging as is would turn the nightly run red. Wanted: decide such nests independently of depth, judging inner levels first as `_lead_around_gone` already does for lead-word nests. Add English and German regression cases for these rows. Then show that seeds 555 and 8080 pass, along with your four seeds. The property tests must not be narrowed. If a depth-independent rule turns out not to be feasible, say why in your reply before changing anything else, and the coordinator decides.

**R1-2. Seed 41, the reproducer named in #259, still fails.** `test_no_citation_is_left_and_no_word_is_lost` fails on `( [12]. see (see also [48, 135]))`, which now reads `` (the whole bracket goes) where main read `(. see)`. The new reading is right, because the bracket holds only citations and lead words. The test's own pattern for leftover brackets, though, does not allow the ".". Add "." to that pattern, with a comment. Add this shape (en, inside a sentence: `It holds ( [12]. see (see also [48, 135])) here.` → `It holds here.`) to the #272/#259 regression case. Then show that seed 41 passes, since "Closes #259" rests on it.

**R1-3. Track the four notice exceptions with #324.** `figure-abbreviated-label`, `figure-label-in-capitals`, `de-notice-table-named-by-its-caption` and `de-notice-figure-short-label` fail because `rebuilt_from_script` drops a label that a step rewrote. That is exactly #324 (D-578). Change the four reasons to name it, for example `"#324: the rebuilt notice block loses a label a step rewrote"`. Add an acceptance criterion to #324: "remove the four notice cases from SECOND_RUN_EXCEPTIONS in both regression test files". After that, each of the six exceptions is tracked by an issue (#320, #321, #324).

**R1-4. Code that no test needs (hand mutants).** I made 13 one-line mutants of `citations.py` and ran the citations, links, statistics and both regression test files on each. Seven were killed. These six survived:
- `glue-abbrev`: dropping the abbreviation exception in `_would_glue`. It can be killed by the docstring's own example, so add tests: de `Es gilt vgl.(527794)2019 hier.` → `Es gilt vergleiche 2019 hier.` and en `See e.g.(527794)2019 here.` → `See for example 2019 here.`, each the same on a second run. Without the exception, both keep `(527794)` and then break on run 2.
- `closing-pair`: replacing `pairs.get(closing.end() - 1, len(text)) < first` with True. It can be killed by the docstring's example: add `It holds and (see [12])) here.`, which must keep its "and" (`It holds and) here.`).
- `looks2`: `_LOOKS = 2` passes every test, so no test needs the third look. After R1-1, add a test that fails with one look fewer than the cap, whatever the cap ends up being.
- `numeric-at`: `at = node.open` in `_numeric`, ignoring the moved position.
- `pairs-check`: `if lead:` in place of `if lead and pairs.get(lead.start(), -1) >= past[number]:`.
- `merge-crossing`: `if True:` in place of the crossing check in `_merged`.

For each of the last three, add a test that fails without it, or remove the code if it cannot be reached. Say which in your reply.

**R1-5. Missing regression cases named by the issues' criteria.**
- #291 requires English and German cases for both shapes. German row 1 is missing: `Es gilt ((Müller, 2019) Weber, 2020; siehe Tabelle 2) hier.` → `Es gilt ( siehe Tabelle 2) hier.`
- #272 row 3 is missing: `Das gilt ( (Müller, 2019) [1,2; 3,4], [12]).` → `Das gilt ( [1 Komma 2; 3 Komma 4]).`

**R1-6. File follow-up issues (v1.2, textprep) for shapes I found that read the same way on main.** They were not caused by this PR, but they sit next to its rules. Link them under "Out of scope":
- a. A link's removal leaves a hanging join word, because the #305 rule covers only the citations step's own removals: `It holds (see https://example.org and Lee, 2019) here.` → `It holds ( and Lee, 2019) here.`
- b. A numeric bracket glued after a removed citation stays glued to the name before it: `As said by Lee (Smith, 2019)[12] it holds.` → `As said by Lee[12] it holds.` (de: `Wie Weber (Müller, 2019)[12] zeigt.` → `Wie Weber[12] zeigt.`)
- c. A nest of year brackets keeps empty shells: `Text ((((Smith, 2019) 2020) 2021) 2022) more.` → `Text ((( 2020) 2021) 2022) more.`

## No action
- `It holds ( see Table 2) here.` keeps the space after "(". It is not heard, and it reads the same on both runs.
- Cost: an identifier look comes on top of the three general looks, so a block can take four passes. The PR body says so. That stays within D-577's intent, and it is linear.

## For the coordinator (not a fix item)
- **#259 milestone.** The PR closes #259, which is on milestone v1.0.1. The fix lands on main, which becomes v1.2, and it needs the whole look and separator machinery, so a backport to release/1.0 does not make sense. Recommendation: keep "Closes #259" (once R1-2 holds) and move #259 to milestone v1.2. This is a decision for the coordinator.
- Decision text for the KB once merged: PR A of D-577 merged; #259 moved from v1.0.1 to v1.2 (if decided); the second-run check over all regression cases is in force, with exceptions tracked by #320, #321 and #324.

## Probes (container-local)
`/home/user/probe/`: probe.py (whole chain twice, `lang|text`), shapes1-6.txt, fuzz.py (seed 4242, 8000 texts), corpus.py, timing.py, ratio_plugin.py, mutate.py.
