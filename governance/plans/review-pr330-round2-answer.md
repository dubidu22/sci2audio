# PR #330, answer to review round 2

Head ece9296: fix commit a810803, then main 795c2d2 merged in (it brings #332 and #333; the only conflicts were appended CHANGELOG lines and regression cases, both sides kept). Decision: D-599.

## R2-1 (blocker): a lead word nest with year tails

**(a) Decided inner first in one look.** New `_years_after_inner_names`: an inner bracket of years that no rule decided counts as read where it is printed, when the text before it, with the inner edits before it made, ends in a name. So "(see (Smith, 2019) (2019))" is judged as "(see Smith (2019))", as a second run judges it, and the nest goes whole in one look at any depth. Each bracket of years reads back at most 16 edits and 300 characters, so this costs constant time per bracket.

Citations step alone, CPU time, depth 800:

| shape | PR round 1 | now | main 795c2d2 |
|---|---|---|---|
| en `see` | about 88 s | 0.40 s | 0.16 s |
| en `cf.` with a link | about 88 s | 0.60 s | 0.15 s |
| de `vgl.` | 82 s | 0.71 s | 0.15 s |
| de `vgl.` with a link | | 0.75 s | 0.15 s |

Main does not resolve these nests at all (it reads "(see (see … Smith (2019)) …)"). From 100 to 800 levels the PR's time grows 5 to 10 times, which is linear.

**(b) Work budget (D-599).** All looks at one block may read at most `_LOOK_WORK` = 8 times `len(text) + 300` characters. If a look still changes something once that is spent, `_unsettled_as_printed` drops every edit in each outermost bracket where the two last looks differ, so that nest stays as printed, and the rest keeps its edits. The bound stays tied to the input (D-588), and no shape costs more than a fixed number of passes. Measured spend: the fast suite and the 13 corpus documents use at most 1.0 passes past the first look (most blocks 0).

**(c) Tests.**
- The four shapes (en `see`, en `cf.` with a link, de `vgl.`, de `vgl.` with a link) are added to `test_a_deep_citation_nest_takes_linear_time` at 800 levels. Each takes `assert_linear` (100 vs 800 levels, the ratio of linear_time.py), checks the result (the whole nest goes; with a link, only the links step's ", https://x.org" is left), and checks that the nest is decided in at most 3 looks (the deciding look, one for an identifier or link, one that changes nothing).
- Regression rows at depth 4: en `see`, `see` with a link, `cf.`, `cf.` with a link in `citations-a-nest-of-any-depth`; de `vgl.` and `vgl.` with a link in `de-citations-a-nest-of-any-depth`. Before (main 795c2d2): "It holds (see (see (see (see Smith (2019)) (2019)) (2019)) (2019)) more." and so on; after: "It holds more." / "Es gilt mehr.", the same on the second run.

**(d) Budget test.** `test_the_looks_stop_at_a_budget_and_leave_an_unsettled_nest_as_printed`: a stand-in turns off the inner-first reading (monkeypatched `_cited_once_inner_citations_go`), so a comma nest needs one look per level. At 4 levels it still goes; from 100 to 800 levels the time is linear, and at 800 levels the nest stays as printed. Removing the budget makes the suite run 3.5 minutes on this one test before it fails.

## R2-2: the six mutants

| mutant | now |
|---|---|
| `shells-pair` | killed: row `Text ( [12] ] more.` → `Text ( ] more.` in `test_the_edge_rules_read_the_same_on_a_second_run` |
| `shells-balanced` | **code removed.** A removal that keeps names ("(" of "(Smith, 2019)" read "Smith") always stands next to them, so it never meets an empty bracket; 50,000 random texts gave identical edits and look counts with and without the check. The docstring says why |
| `sep-behind` | killed: new deep-nest row `It holds (Lee, 2020; (Smith, 2019))` at 3200 levels. Over the bracket cap only the inner-first reading decides it, and without the end blank the nest is left as printed |
| `toolong-none` | killed: the deep-nest test now counts looks (the mutant needs about 11 at 3200 levels) and checks the result |
| `read-cap` | killed: new `test_a_bracket_longer_than_the_cap_is_no_citation_once_its_inner_ones_go` (a 4400-character bracket of "Lee, 2020; " parts: only the inner citation goes, on both runs; the mutant removes the whole bracket) |
| `read-longer` | **code removed.** `_Read` keeps each piece's own place, so a reading longer than its span shifts no mapping; 50,000 random texts gave identical edits without it. The docstring and comment say so |

My own mutants of the new code, also killed: the budget check (removed: the stand-in test runs past linear) and the year rule (`if child.open in years` off: the `see`/`vgl.` rows fail).

## Checks on ece9296

- ruff, ruff format, lint-imports, deptry: clean.
- Fast suite, ci profile: 5177 passed, 1 skipped, 6 xfailed (#320, #321, #324), 76 snapshots unchanged.
- Corpus, 13 documents through `run_script_job`: byte-identical to main 795c2d2 (39 files).
- Second run of every regression case (159 en, 114 de): only the six known exceptions.
- Nightly profile, seeds 555 and 8080, over citations, German citations, links and both regression files: 1033 passed, 6 xfailed each.
