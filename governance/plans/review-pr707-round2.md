# Review PR #707, round 2 (batch B-I3, #683, D-848, D-849)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: 32235db (one fix commit on ffb0d7b). Date: 2026-11-20.
**Critical: yes** (unchanged). Plan `plans/infra-b-i3-plan.md`, approved as D-855. Answer: `plans/answer-pr707-round1.md` (governance 12f7d22).

**Verdict: approved** (0 must-fix, 0 should-fix, 0 notes).

## Verified

- Scope: `git diff ffb0d7b..32235db` touches only `.github/governance/promised_tests.py`, `tests/unit/test_promised_tests.py` and `tests/unit/test_ruleset.py` (+45/−16). The changes are the answers to S1, N3 and N4 and nothing else. `git diff 9066c3d..32235db -- .github/governance/pr-checks.json .github/labeler.yml` is still empty.
- S1:
  - `section()` now walks `outside_fences()` and starts at the first unfenced exact heading. When there is none it returns `None`, so a body with the heading only in a fenced example passes as having no section.
  - `near_miss()` looks for the exact heading among unfenced lines only.
  - `test_a_fenced_example_of_the_heading_does_not_start_the_section` covers scenario 1 of round 1: the fenced example's ID is ignored, and the real section's ID is read.
  - `test_a_fenced_heading_does_not_hide_a_near_miss` covers scenario 2: the near-miss outside the fence fails, naming the line.
- N3:
  - The extract test now requires that an extract holds exactly the ruleset rules whose `applies_to` names its `extract_for` role or `all`, and each of those blocks must still equal the ruleset's.
  - Mutation check in the review worktree: removing THR-09 from `rules/kb.yaml` fails the test with "kb.yaml: rules missing or extra: {'THR-09'}". The file was restored, and `git status` is clean.
- N4: `profile()` skips blank and comment lines inside the block and stops only at the next unindented line, which is `execution_profile:` today.
- N2: the PR body's test summary now says 9 of the 20 first-promised cases failed on `main` and names the 11 that passed and why they stay. The plan says the same (`infra-b-i3-plan.md:55`).
- Promised tests: the body section lists 9 node IDs, the two new ones included. Governance pr checks run 44819425459 on 32235db, after the body edit, prints `ok   promised tests: 9 of 9 collect`. The earlier run 44819380203 printed 7 of 7, before the edit.
- Local run in a fresh `/tmp/review-707` at 32235db:
  - ruff check: clean. ruff format --check: 387 files formatted.
  - lint-imports: 3 kept. deptry src: no issues.
  - `zizmor --offline .github/workflows`: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8660 passed, 6 skipped, 6 xfailed.
- Not verified here: the Linux CI on 32235db, which the coordinator checks, and the `ci:full` run after `main` (d85ed2a) is merged in.

## Findings

None. Round 1's N1 follows D-855 and needs no change. N5 is the coordinator's step after the merge: merge `main` into `governance` so threads read the new extracts.

Verdict: approved. Next: the author merges `main` (d85ed2a) in and runs `ci:full`. Then the merge is pinned to that head after a check that the merge commit brings only `main`'s changes.
