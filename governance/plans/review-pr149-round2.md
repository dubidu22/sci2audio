# Review of PR #149, round 2

Reviewed head: 4fa2072 (fixes ef57ab5, then main a0bb69f merged). Answer: `plans/review-pr149-round1-answer.md`.

**Verdict: approved.** Every round-1 item is closed.

| Item | Status | Checked how |
|---|---|---|
| M1 pooled count per height | fixed | new test; my "drop height in pooled" mutant is now killed |
| M2 pooled count counts pages | fixed | new test; my "count lines" mutant is now killed |
| S1 smaller lines lend no pages | fixed | code keeps only `small` to `head_size`; new test; my "drop small floor" mutant is killed |
| N1 one-page section heads | fixed | named in the module docstring |
| N2 185 edge lines | answered | PR body corrected |
| N3 `repeat_pages` comment | fixed | |
| F1 smaller lines (D-328) | Issue #156 (v1.1, lane:layout) | KB #44 has a D-328 row |

My checks on 4fa2072:
- Fast suite with `--snapshot-update`: 2199 passed, 19 subtests, 54 snapshots passed, working tree clean (no golden file changed).
- Nightly Hypothesis profile on `tests/unit/test_layout*.py`: 332 passed, 7 snapshots.
- ruff, format, lint-imports (3 contracts kept), deptry: clean.
- Mutations (15): all killed except the band guard in the pooled count, which the PR names.
- Corpus, main a0bb69f against the PR: 185 edge-band lines and every block (kind, role, text) of the 7 papers identical.
- CI on 4fa2072: all jobs green on ubuntu, macOS, Windows, browser, lint and layers, licences, CodeQL.

Merge: main moved to 9657262, so the branch is updated by a merge commit (no force-push), then merged once CI is green on the new head.
