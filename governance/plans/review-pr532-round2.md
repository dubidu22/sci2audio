# Review PR #532, round 2 (final round, critical)

Reviewed: fix commit **40a161e** (R1 to R11 of round 1), then main (94a4353) merged in by me: head **4877887**, PR diff byte-identical before and after the merge (only the strings TOML shared files with main; merged cleanly).
Verdict: **approved**. All 11 round-1 items fixed with a test each. One leftover test gap filed as #544 (no data risk). Merge once the three-system run on 4877887 is green (macOS job re-run: the first attempt got no hosted runner, "not acquired … capacity constraints", no test ran).

## Round-1 items

| Item | Result |
|---|---|
| R1 merge loop | Fixed: `_free` raises on any lstat error but "not found", `_through_folders` refuses a file or link on the way, numbering bounded (`MAX_EARLIER`). My round-1 reproduction (file named `from-earlier-version`) now returns; three tests with a 30 s timeout. |
| R2 lock window | Fixed: `FolderLock` held through copy, commit, removal of originals and merge; across the rename on Linux/macOS; on Windows released only before the rename and re-taken after `EXDEV`; `job.lock` neither copied nor read; pruned after release. Tests for copy, merge, rename (POSIX). |
| R3 to R5, R10, R11 | Tests added; each kills its mutant (table below). |
| R6 MT2 | Exhaustive: per case the uncut run's operations are counted (fast 1, across 31, merge 28, merge-across 71) and every cut point is run, with the new-folder-unchanged and equal-digest checks. Matches my round-1 probe. |
| R7 | Windows-only test with a file held open; it ran on windows-latest (not in the job's skip list). |
| R8 | Both terminal lines, tests with caplog. |
| R9 | PR body has the per-item table and the corrected mutant table (b, i, r marked equivalent, which I agree with). |

## Final-round checks

- **Mutation:** 29 hand mutants from a clean baseline (the 6 test files pass unmutated: 97 passed, 3 skipped), run against test_app_projects, test_web_projects, test_cli_project_folders, test_web_remove, test_app_chunks. 25 killed, each by a test that hits the mutant; b, i, r equivalent (as in round 1); **n12** survives: the `_through_folders` check for `from-earlier-version/` itself. Without it, a linked `from-earlier-version` holding an identical file lets the old copy be removed through the link; nothing is lost (the same bytes are where the link points) → test filed as **#544** (lane:app, v1.2).
  Killed: a, c, d, e, f, h, k, o, q, v, x, z2, m2, g2 (lock never busy), n1 (`_free` true on error), n2 (unbounded numbering), n3 (`_through_folders` always true), n4 (lock released before the rename on POSIX), n7 (no staging discard in the merge path), n9/n9b (terminal lines), n11 (lock only probed), y2 (preview `is_dir`).
  `mutmut run "sci2audio.app.projects*"` could not be used: its stats run over the whole suite in mutmut's copy fails on a test unrelated to this PR (`test_web_design.py::test_every_font_is_the_licence_tables_file_byte_for_byte`, a file mutmut does not copy). The hosted mutation workflow mutates all of `src/` and dies after about 5 h (#246), so the targeted hand mutants are the mutation evidence here.
- **Nightly seeds:** not applicable; the PR has no Hypothesis test any more (MT2 is exhaustive).
- **Three-system run:** 40a161e green on ubuntu, macOS, Windows (run 44331809854). On the merge head 4877887: ubuntu, macOS (re-run after the runner was never acquired) and Windows green (run 44343665565). Merge held for the coordinator's merge slot (D-758); main moves again first (#524, #528), so main is merged once more before the squash-merge.
- **Plan §7:** `web/api.py` and `web/pages.py` still untouched.

## Notes (no action)

- N2 and N3 of round 1 stand as accepted.
- On Windows the folder rename runs with the lock let go for one call (plan M5); the migration lock keeps other new-version moves out and `project_folder` keeps reading the old folder until the rename is done.
