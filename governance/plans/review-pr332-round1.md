# Review of PR #332, round 1

PR: textprep: numbers read the same on a second run (#304), https://github.com/dubidu22/sci2audio/pull/332
Head 0776978, base main e3610f4 (same textprep code as 334e5a8). Critical (regression cases), D-577 PR B.
Verdict: **changes needed** (R1-1 to R1-4). The approach is sound and the main claims hold. The fuzz grid found one new second-run break that the PR adds (R1-1), in the #318 range rule.

## What I checked, and what held

| claim | result |
|---|---|
| fast suite green | yes: 4729 passed, 1 skipped, 76 snapshots passed (ci profile, -n 4) |
| ruff, format, lint-imports, deptry | all clean |
| corpus byte-identical to main | yes: all 13 corpus documents through `sci2audio script` (output folder set, main through PYTHONPATH), 39 files, `diff -r` empty |
| regression cases twice | my rebuild harness (`regr2.py`) gives 15 differing cases on both PR and main, with identical text; none of the four new cases differs. So the PR adds no second-run difference among the cases |
| #331 pre-existing | yes: `310^250 000 000` reads the same, unstable way on main and PR (probe and seed 7). But it duplicates #210 (R1-3) |
| nightly seeds | mine (11, 4242, 90210, 123, fresh database) on the numbers, statistics, units and both regression files: 1073 passed on each seed |
| #304 rows | `−1/2`, `3–33–3 −3/3`, `0:~-↵0` and 60 more sign shapes read the same on both runs |
| #310 | grid of 18,900 texts (lead word × yearless date × spacing × 18 fraction shapes × tails): main has 1080 second-run breaks, PR has 0, none new |
| timing | `_dates` stays linear on n…8n copies of each new shape (fraction, range, chained range); at most 1.5× main |
| CI on head | Linux green; macOS/Windows run at merge time (`ci:full`) |

## Fix list (all required)

**R1-1. New second-run break: a full date, a hyphen, a yearless date, then a date or a "1/x" fraction.** `_YEARLESS_END` refuses a yearless end followed by `\s*\d`, but the yearless date itself is read before what `_DATE_AHEAD` allows (a full date, or `1/x` read "ein …"). Once the next number is read as words, the second run sees a letter and reads the range. Main reads none of these, on both runs.

| printed | run 1 | run 2 |
|---|---|---|
| `Vom 3.4.2019-5.4. 1/2 Tag.` | `Vom 3.4.2019-5.4. ein halb Tag.` | `Vom dritten April 2019 bis fünften April ein halb Tag.` |
| `Vom 3.4.2019-5.4. 12.03.2019 an.` | `Vom 3.4.2019-5.4. zwölfter März 2019 an.` | `Vom dritten April 2019 bis fünften April zwölfter März 2019 an.` |
| `Vom 3.4.2019-31.4. 1/3.` | `Vom 3.4.2019-31.4. ein Drittel.` | `Vom dritten April 2019-31.4. ein Drittel.` |
| `Seit 3.4.2019-5.4.2019-7.4. 1/2 Tag.` (third date) | unread | range read |

My grid `fuzz2.py` (lead × first date × dash × second date × optional third date × tail, 31,500 texts) finds 93 such breaks on the PR and none on main. The list is in `plans/review-pr332-probes/fuzz2-pr-breaks.txt`. Wanted: the year-and-hyphen test decides the same way on both runs. For example, `_YEARLESS_END` could accept what the yearless date accepts after it (`_DATE_AHEAD`), with `_dates` then reading the end only when its `1/x` is read "ein …", as #310 does. The design is yours. Add a German regression case with the three shapes (full date + `-5.4.` + `1/2`, + `12.03.2019`, + `1/12` as the keep) and the invalid-day row. Then show that `fuzz2.py` and `fuzz3.py` give no break the main run lacks.

**R1-2. Align the fraction's minus look-behind with N1's.** `_FRACTION` refuses a fraction after `[\w.,/:]−`, but `_MINUS` reads "−" as "minus" whenever no `[\w.,]` stands before it. So after "/" and ":" the first run still reads `minus 1/2` and the second run `minus 1 half`: `It is /−1/2 here.`, `ratio 1:−1/2`, `12:−3/4`, `x/−1/2`. These shapes are the same on main, but they are the #304 class the PR closes, and the PR's comment says "only where N1 reads it 'minus'". Change the look-behind to `(?<![\w.,]−)` (I patched it in a probe: all four read the same on both runs, and the five test files pass with it). Add these four shapes to `test_a_second_run_reads_the_same_after_a_sign`.

**R1-3. #331 duplicates #210.** #210 (v1.0.1, D-461) is the same shape (`10^250 000 000`) in the same test. Close #331 as a duplicate of #210 with a comment that adds the seed-7 example `t(3)=310^250 000 000` to #210. Change the PR body's out-of-scope line to #210.

**R1-4. Code that no test needs (hand mutants).** I made 19 one-line mutants of the PR's changed lines and ran the numbers, German numbers/statistics, units and both regression test files on each. Thirteen were killed. Of the six survivors, one is R1-2's change and three are equivalent (below). These two need a test:
- `startswith("ein ")` → `True`: no test keeps a date before a `1/x` read with digits. Add `("Am 3.4. 1/12 Liter.", "Am 3.4. 1 von 12 Liter.")` to the #310 rows (unit test and regression case).
- `_YEARLESS_END` without `|\s*\d`: no test has a yearless end followed by a number. R1-1 changes this line anyway. Its new cases must fail if that part is dropped, and `("Vom 3.4.2019-5.4. 3 Tage.", …)` must pin the plain-number keep.

Equivalent, no action: `not paired and` before `_DASH_BEFORE` (a paired dash always stands after a date's "." or year, so `_RANGE_DASH_BEFORE` matches anyway); `(?!\d)` in `_DATE_AHEAD`'s `1/\d{1,2}` and `_FRACTION_AHEAD` `1/` → `\d/` (both gated by the "ein" check).

## Deferred: issues filed (v1.2, textprep), same on main, link them under "Out of scope"

- #334 German date ranges with a spaced or em dash read only the first date (`Vom 3.4.2019 – 5.4.` → `… 2019 bis 5.4.`)
- #335 a unit power after a fraction is read only on a second run (`3/4 s⁻¹`)
- #336 a minus sign at a line end is read only on a second run (`−↵5`)

## No action

- `Die 3.4.-5.4.-Woche` now reads `Die dritte April bis fünften April-Woche`; main read `Die dritte April-5.4.-Woche`. Both readings are awkward, and the new one is no worse; it is stable.
- German `−1/2` stays fully as printed (`Es ist −1/2 hier.`), the same on both runs, as on main.

## Probes

`/mnt/project-files/plans/review-pr332-probes/`: `probe.py` (lang|text shapes, whole chain twice), `fuzz1.py` (every character before `−1/2`), `fuzz2.py` (#318 range grid), `fuzz3.py` (#310 grid), `regr2.py` (regression cases rebuilt and read again). Run each under the PR and under main (`PYTHONPATH=<main worktree>/src`) and compare.
