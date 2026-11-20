# Review of PR #332, round 2

PR: textprep: numbers read the same on a second run (#304), https://github.com/dubidu22/sci2audio/pull/332
Head 887edae (fix 250fe9b plus a merge of main fbc6de8). Round 1: review-pr332-round1.md.
Verdict: **approve**. Every round-1 item is fixed and verified, and no new finding needs a change. Merge once `ci:full` (added) is green on Linux, macOS and Windows for 887edae.

## Round-1 items

| item | status | how I checked |
|---|---|---|
| R1-1 range with a yearless end before a date or 1/x | fixed: `_YEARLESS_END` accepts what a yearless date may stand before (`_DATE_AHEAD`), and `_dates` skips the range when the `1/x` after it is not read in words | `fuzz2.py` (31,500 texts): 0 breaks on the PR, 0 on main (round 1: 93 on the PR). New grid `fuzz4.py` (range × spacing × 17 tails incl. 1/10, 1/11, 1/12, 1/2-mal, "1 von 2", "ein halb", 48,960 texts): 48 breaks on both PR and main, the same texts, none PR-only (they are #349, below). New regression case and unit rows |
| R1-2 minus look-behind as N1's | fixed: `(?<![\w.,]−)` | `fuzz1.py` (every character before `−1/2`): 0 breaks (main 317). Mutant back to `[\w.,/:]` fails 4 new tests |
| R1-3 #331 duplicate of #210 | done: #331 closed as duplicate, comment on #210, PR body updated | GitHub |
| R1-4 tests for surviving mutants | done: the `1/12` keep row (unit and german.toml) and the `3 Tage` keep row | mutants below |

## Rechecked on the new head

- ruff, format, lint-imports (3 contracts kept), deptry: clean.
- Fast suite: 4814 passed, 1 skipped, 76 snapshots passed (ci profile).
- Corpus: all 13 documents through `sci2audio script`, PR vs main fbc6de8: `diff -r` empty.
- Regression cases rebuilt and read again (`regr2.py`): output identical to main's, no new case differs.
- `fuzz3.py` (#310 grid, 18,900 texts): 0 breaks (main 1080).
- Nightly profile, fresh database, seeds 777 and 2026, on the numbers, German numbers/statistics, units and both regression files: 1084 passed each.
- Hand mutants of the round-2 lines: 6 of 7 killed. The survivor is the dropped `startswith("ein ")` filter in `_read_as_ein`, now equivalent: for 1/0 to 1/99 after a date, every fraction `_fractions` reads starts with "ein " (checked), as the docstring says.

## New issue filed (v1.2, same on main, not caused by this PR)

- #349 German dotted section numbers read their last part as an ordinal on a second run (`Kapitel 1.2.3. Tag.` → `… 2 Punkt 3. Tag.`, then `… 2 Punkt dritter Tag.`). Found by `fuzz4.py`. The author may add it under Out of scope; this is not a merge condition.

## Merge conditions

1. `tests (macos-latest)` and `tests (windows-latest)` succeed on 887edae: DONE, run 43642749424 green on all jobs (Linux, macOS, Windows, browser, lint, licences, security).
2. If PR #330 merges first, this branch merges main again, and the review thread reruns the fast suite, the corpus diff and `regr2.py` before merging.
