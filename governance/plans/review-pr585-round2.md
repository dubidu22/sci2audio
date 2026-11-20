# Review of PR #585, round 2 (final round)

Reviewer: B2 review thread (critical, Opus high). Reviewed head **8aeb592** (one fix commit on
8ef9ae4). Result: **APPROVED**, merged pinned to 8aeb592.

- F1 fixed exactly as the prototype (`_after_name` drops one comma glued before the mark); the two
  rows, the unit test (three cases) and the mutant are the ones named. `src/` diff 8ef9ae4..8aeb592:
  `footnotes.py`, 4 lines. Probes re-run on 8aeb592: the three F1 rows remove every author and
  affiliation mark; "Mapping ¹²CO,¹³CO" and "Mapping ¹²CO, ¹³CO" keep their mass numbers.
- Three-system CI on 8aeb592: run 44432265252 (workflow_dispatch), tests ubuntu, macos, windows
  success, both Chromium shards success, `CI passed` success. Linux PR run 44430791789 green.
- Mutation (reviewer's own, `mut3s.py`, ROOT = worktree at 8aeb592, textprep test subset
  incl. both regression files, baseline PASS): 7 mutants on the new code, 6 killed (author flag
  start value, end-of-block carry, same-block footnote check, `authors and` dropped, comma check
  off, after-name filter of `noted`), 1 survived: `before[:-1]` → `before.rstrip(",")`, which
  differs only for two or more commas glued before a mark ("Roe,,¹"); accepted, no real shape.
  The author's 14 of 14 killed (`plans/b2-mutation/mutants_pr2.py`).
- Nightly seeds: own seed 8080 (`HYPOTHESIS_PROFILE=nightly`, `tests/unit/test_textprep_*.py`):
  4,018 passed.
- Main moved to ee02e56 (#577) after 8ef9ae4: `CHANGELOG.md` under "Added" only; PR's line is
  under "Fixed"; GitHub reports the PR clean. No branch update (MRG-03).

Totals: 2 rounds, 1 must-fix (F1 REVTeX comma-before-mark regression), fixed; filed #586.

Merge note: #583 (9333ce0) conflicted in CHANGELOG after approval; the author merged main
(138e9ca, both lines kept). PR diff outside CHANGELOG checked identical to 8aeb592's; three-system
run 44434831159 on 138e9ca green. Merged ad6b94f, squash pinned to 138e9ca.
