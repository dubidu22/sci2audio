# Review PR #680, round 2 (batch B-I1, #664 and #665)

Thread: review-infra-b-i1 (Opus 5.5). Head reviewed: dc94e5f (one fix commit on top of c6322ae). Date: 2026-11-20.
**Critical: yes** (unchanged from round 1). Answer: `plans/answer-pr680-round1.md`.

**Verdict: approved** (0 must-fix, 0 should-fix, 1 note).

## Round-1 findings

- **S1, fixed.** `tests/unit/test_ci_workflows.py:365-370` no longer contains a literal version. Every `uses:` line must have the form `<action>@<40-hex> # v<N>[.<N>…]`, and the checkout step is found by its `actions/checkout@` prefix. A Dependabot bump that rewrites the comment still passes, and an unpinned or comment-less `uses:` still fails. The added comment says why, so PR-05 is met.
- **S2, fixed.** `governance/tools/**` is now in `critical_paths` (`.github/governance/pr-checks.json:88`) and among the `risk:high` globs in `.github/labeler.yml:17`. The labeler still equals `critical_paths`, so `test_the_labeler_marks_the_paths_the_check_holds_critical` holds. `test_a_rules_change_needs_risk_high` now covers `governance/tools/ledger_tool.py`. Red check: with round 1's `pr-checks.json` put back at dc94e5f, `tests/unit/test_lanes.py` fails 2 tests (that new case and the labeler-equality test).
- **S3, deferred to #683.** #683 is open, in milestone v1.4, labelled `lane:infra` and `risk:high`. It states the exact edits to `governance/governance-config.json` and to `project_profile` in `governance/claude-project-rules.yaml`:
  - `critical_paths`: the five governance globs, which match today's `pr-checks.json`.
  - `label_paths`: all 14 new `lane=glob` entries.
  - The new `governance_paths`: the seven docs-lane working-file globs.
  - Regeneration of the extracts.
  - Its acceptance criteria include a regeneration dry run that must equal today's `pr-checks.json`, and the owner's approval (META-01).
- **S4, fixed.** The "Out of scope" section of the PR body names #681 and #683.

## Verified

- The fix diff touches only `pr-checks.json`, `labeler.yml` and the two test files. There is no other change.
- In a temporary worktree at dc94e5f:
  - `uv run zizmor --offline .github/workflows`: no findings.
  - `tests/unit/test_ci_workflows.py tests/unit/test_lanes.py`: 49 passed.
- `gh pr checks 680` on dc94e5f, at the time of review:
  - `lint and layers`, `security`, `governance pr checks` and `Analyze (actions)` pass.
  - `tests (ubuntu-latest)`, `Analyze (python)` and `Analyze (javascript-typescript)` are pending, so the Linux run is not yet complete and `CI passed` is not yet green.

### N1 (note): merge preconditions not yet met at dc94e5f
Before the merge (MRG-01, D-580), dc94e5f needs a green Linux run (`CI passed`). Because the PR is critical, it also needs a green three-system run on this head. The `ci:full` run at c6322ae does not cover dc94e5f. Check `tests (macos-latest)` and `tests (windows-latest)` on dc94e5f itself.

Verdict: approved; merge on the coordinator's go once `CI passed` and the three-system run are green on dc94e5f.
