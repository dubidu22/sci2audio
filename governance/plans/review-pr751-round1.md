# Review PR #751, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/751 (#750, D-888; ruleset 1.13.0 → 1.14.0, claude.ai Project setup)
- Head: `f168cbf3e7c48e4d3a2280f4f3a806e786fbc9a3`, base `5213b4a`; main is at `1cbfbd2` (#749), so the PR is behind main by one commit
- Thread: review-pr751-1 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03): changes `governance/claude-project-rules.yaml`, all seven extracts, the instruction files and `.github/` path lists (all in `critical_paths`); carries `risk:high`.
- **Verdict: changes_requested, not reviewed.** The coordinator's precondition for round 1 is not met: no three-system run exists on the head, and the PR predates #749. The diff was not reviewed; this round does not count toward REV-01's round limit for content findings.

## Verified checks

- CI run 45136209676 (pull_request) on f168cbf: `tests (ubuntu-latest)`, `lint and layers`, `licences`, `security`, both Chromium browser shards, `web paths` and `CI passed` all success. CodeQL success.
- Three-system run: **missing.** `start CI on all three systems` was skipped (the PR has no `ci:full` label); no `tests (macos-latest)` or `tests (windows-latest)` check exists on f168cbf (D-580, CRIT-02, CLAUDE.md workflow 7).
- `governance pr checks` on f168cbf: red only with `no review round is recorded` (the `approved` step), as expected before a round exists.
- Behind main: #749 (squash `1cbfbd2`) landed after the base `5213b4a` and added the working-files check in `lint and layers`. A trial merge of main into f168cbf (scratch worktree, not pushed) is clean, and `.github/scripts/working_files.py` on the merged tree prints `no working files on this branch` (exit 0). The PR's CI has still never run with #749's check.

## Findings

- **B1** (must-fix, kind `ci-full-missing`). No green three-system run on the head. Recommended: merge main into the branch first (B2), then add `ci:full`, wait for `tests (ubuntu|macos|windows-latest)` green on the new head, then remove `ci:full`.
- **B2** (must-fix, kind `behind-main`). The head predates #749 and its working-files check. Recommended: `git merge origin/main` into `claude/ruleset-cloud-project-ef7ce5` (merge commit, no force-push), push, and let Linux CI run on the new head before B1's `ci:full` run.

## Handoff (THR-07)

- Goal: critical review round 1 of #751.
- Done: CI and freshness checked at f168cbf; two preconditions missing; diff not reviewed.
- Next: once the author's head carries main and a green three-system run, a review thread runs round 1 again (`review-pr751-round2.md`) on that head, starting from the diff. Ruled out: none of the content was judged yet.
