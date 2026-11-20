# Review of PR #357, round 2: SRT and WebVTT subtitles (#214, D-606)

Head reviewed: `5cf1378` (a40e18e tests, f2deb0f merge of main 6c91465 = PR #345, 5cf1378 N1).
No force-push. Main's tip is 6c91465, so the branch is up to date.

**Verdict: approved at `5cf1378`.** Waiting for the coordinator's merge go.

## Round 1 items

- **S1, fixed.** `test_a_line_holds_42_characters` pins 42 and 2 with literal numbers, both sides
  of 42. The `LINE = 43` and `len(whole) < LINE` mutants now fail.
- **S2, fixed.** `test_a_semicolon_wins_over_a_later_comma_in_the_same_cue` pins the cut exactly,
  and `test_a_clause_mark_counts_from_a_half_full_cue` pins 42 against 41. The merged-marks
  mutant and the `// 3` mutant now fail.
- **S3, fixed.** `test_a_chunks_time_is_shared_out_by_characters` pins the inner boundaries of
  two chunks exactly; the `done - 1` mutant fails.
- **S4a, fixed, guard kept.** `test_a_subtitle_file_replaced_by_someone_else_during_the_run_is_left_alone`
  fails with the inode check removed (re-run here).
- **S4b, fixed.** The file test checks `read_bytes()` for `\r`; the `newline="\r\n"` mutant fails.
- **N1, done.** The unreachable fallback is now a `cast` with its reason; ruff S101 forbids
  `assert` in `src`, so that is the right form. No change in behaviour.
- **N2.** No action, as agreed.

## Checks on 5cf1378

- Fast suite: 5245 passed, 1 skipped, 6 xfailed (main's #324 cases). Browser suite: 56 passed.
  `ruff check`, `ruff format --check`, `lint-imports`, `deptry src`: clean.
- Mutations: of the round 1 survivors, all except one were re-run and are now killed. The one
  left is the even-lines tie taken the other way, which is equivalent: both lines are equally
  even, so no fix is needed.
- Commit messages: no `fixes`, `closes` or `resolves #N` in a40e18e, f2deb0f or 5cf1378.
  `Closes #214` is in the PR description only.
- CI on 5cf1378, with the `ci:full` label: `tests (ubuntu-latest)`, `tests (macos-latest)`
  (09:01:14Z) and `tests (windows-latest)` (08:59:55Z) all succeeded. Browser, lint and layers,
  security, licences, CodeQL, ZAP and `CI passed` also succeeded.

## Merge

Squash-merge pinned to `sha=5cf1378`, with an explicit commit message that names #214 only. Then
check that #214 closed.
