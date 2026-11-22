# Review PR #740, round 2

Thread: review-b004-a (Opus 5.5 high). Author of the fix: infra-b-i6. Head reviewed: e24fa5864bfa227cbb82da3ec668970ec2dd88f2 (one fix commit on 465b96f). Date: 2026-11-22.
**Critical: yes** (as round 1: CI workflow and a safety check, `risk:high`, `lane:infra`).

**Verdict: approved** (0 must-fix, 0 should-fix). The merge waits for the three-system `ci:full` run on e24fa58 (MRG-01, D-580): when this report was written, `governance pr checks` was green and `tests (ubuntu-latest)` was still running.

## Round 1 findings

- **S1 (vague-reason): fixed.** `tests/unit/test_extraction_pdf_progress.py:149-151`: a why-comment now says that with the parent's limit broken, the child's own watch still stops the step at 2 x 1.0 s with the same result. The allowance alone on the line above the assert reads `# clock-bound: 1.5 s must stay below the child's 2 s watch; timed before the join (#366)`. It names both numbers, and the bound is unchanged at `1.0 <= took < 1.5`. The allowance is on the line just above the assert, so the check counts it (test green).
- **S2 (weak-guard): fixed.** `tests/unit/test_clock_bounds.py:102-118`: `is_mark` looks at the decorator itself (or at its call's `func`), and `is_unmarked` looks at it or at the elements of a list or tuple (`pytestmark`). This is the fix wanted in round 1, word for word. The new case in `test_slow_benchmark_and_browser_tests_are_not_read` (`:273-278`) is the one round 1 named. In round 1's scratch trial, that same case failed on the old `is_unmarked` (`0 == 1`). On the head it passes, and so do the existing marked cases (function, called `benchmark(...)`, class, `pytestmark` list).
- **N1 to N3:** no change asked; none made.

## Verified

- The diff of 465b96f..e24fa58 touches only `tests/unit/test_clock_bounds.py` and `tests/unit/test_extraction_pdf_progress.py`, which are lane-free tests. No other file changed, and the workflow, `promised_tests.py` and the scaffold copies are as reviewed in round 1.
- Locally on e24fa58, `pytest tests/unit/test_clock_bounds.py test_extraction_pdf_progress.py test_promised_tests.py test_ci_workflows.py test_lanes.py` gives 149 passed. That includes the full-repository scan `test_no_fast_test_asserts_an_upper_wall_clock_bound`, which shows 0 hits with the stricter mark rule. `ruff check` and `ruff format --check` are clean.
- PR body: a "Round 1 answer" section lists S1 and S2 as fixed (coordinator's relay; the fix matches it). Labels: `risk:high`, `lane:infra`, `ci:full`.

## Merge

Gate: no open B/M finding. Before the coordinator's go, check that the run on e24fa58 shows `CI passed`, `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)` green. If the branch is updated to main first (merge commit), re-check the diff and CI on the new head.
