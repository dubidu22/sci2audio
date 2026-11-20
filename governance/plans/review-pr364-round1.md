# Review PR #364, round 1 (#360: labels start no CI run; ci:full dispatches one)

Head reviewed: c3f9728 (base main 87c6503). Main is now 82d9e0d; no `.github`, CONTRIBUTING, CLAUDE.md or test-file change on main since the base, and `git merge-tree` merges cleanly. The PR is behind main, so the merge needs `update-branch` first.

Plan: plans/issue360-ci-passed-plan.md (D-620, option A). Critical (CI workflow).

**Verdict: not approvable yet. No blocker, one should-fix (S1). Nothing deferred.**

## What I checked

- **Change against the plan:** `ci.yml` drops `labeled` (types `[opened, synchronize, reopened]`); concurrency, matrix, `CI passed` and the other triggers are unchanged. New `ci-full-label.yml`: `pull_request: types: [labeled]`, top-level `permissions: {}`, one job with `actions: write` only, gated on `label.name == 'ci:full'` and `head.repo.full_name == github.repository`, no checkout, branch passed through `env` and quoted, `gh workflow run ci.yml --ref "$BRANCH"`. CONTRIBUTING and CHANGELOG match. CLAUDE.md step 8 stays correct as written.
- **Permissions:** nothing in `ci.yml` widened (`contents: read`). `actions: write` is the least scope `workflow_dispatch` needs. `ci.yml` uses no secrets, so a dispatched run gets nothing a same-repo PR run does not already get.
- **Fork PRs:** the trigger is `pull_request`, not `pull_request_target`, so a fork's run gets a read-only token whatever the YAML asks for, and the job is skipped by the same-repo gate anyway. A same-repo author who edits the workflow already has push access, so it opens nothing new.
- **Other workflows:** `zap.yml` uses `pull_request` with paths and the default types (no `labeled`); nightly, mutation and release start on no PR event. So no label except `ci:full` starts any run.
- **YAML:** both files parse; `zizmor --offline .github/workflows`: no findings. `tests/unit/test_ci_workflows.py`: 5 passed.
- **The PR body's run ids, checked on the API:**
  - 43698112582 CI `pull_request`, success, Linux jobs only. It is the only `pull_request` CI run on c3f9728.
  - 43698113338 and 43698113460 "CI on all three systems", skipped (labels `risk:high`, `lane:app`).
  - 43698160369 CI `workflow_dispatch` by hand, cancelled: tests on all three systems and browser cancelled, `CI passed` **failure** (not skipped).
  - 43698267053 label run, success; 43698274438 CI `workflow_dispatch` by `github-actions[bot]`, success, with `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, browser, lint, licences, security and `CI passed` all green.
  - Check runs on c3f9728: three `CI passed` (failure 09:14:07, success 09:15:44, success 09:20:38). The newest is green, and the dispatched checks sit on the PR head as the plan says.
- **Mutation probes on the new test:** each of these fails at least one test: `labeled` put back in `ci.yml`; `skipped` dropped from `CI passed`; the fork gate dropped; `contents: write` added to the job; `permissions: write-all`; the branch put inline as `${{ }}`; `cancel-in-progress: true`; `pull_request_target`. One survives (S1).

## Fix list

### Should-fix

**S1. The test does not pin the job-level `if: always()` of "CI passed".** `test_ci_passed_fails_on_any_job_that_did_not_succeed` checks `"    if: always()" in job`, and that substring also matches the step "Which systems ran the tests" (`        if: always()`). With the job's line changed to `if: ${{ !cancelled() }}`, all 5 tests pass. That mutant is option B, which D-620 rejected: a cancelled run would leave `CI passed` skipped, and the ruleset counts skipped as passing. Fix: anchor the check to the job's own indent, for example `assert re.search(r"^    if: always\(\)$", job, re.M), job`. Confirm by hand that the `!cancelled()` mutant now fails and the current file passes.

### Notes (no change needed)

- **N1.** A dispatched run tests the branch head, not `refs/pull/N/merge` as a `pull_request` run does. The ruleset's strict up-to-date rule means the head already contains main at merge time, and the `update-branch` push starts a full `pull_request` run anyway, since the label is on. No change.
- **N2.** Adding `ci:full` to a closed PR whose branch was deleted makes the label job fail on that closed PR. It is harmless and rare. No change.
- **N3.** If an `opened` payload already carries `ci:full`, that run is full and the dispatch is a second full run. It costs minutes only, and review threads add the label later. No change.

## For the merge go

After S1: `update-branch` (merge commit), then check that `tests (macos-latest)`, `tests (windows-latest)` and `CI passed` are green on the new head, which the `synchronize` run tests on all three systems because the label is on.

---

# Round 2 (approving), head 356cc10 (7a63955 = main 82d9e0d merged in, then the S1 fix)

- `git diff 82d9e0d 356cc10` touches only the PR's 5 files; `.github` and CONTRIBUTING are byte-equal to c3f9728.
- S1 fixed: `re.search(r"^    if: always\(\)$", job, re.M)`. With the job's line changed to `if: ${{ !cancelled() }}`, 1 test fails; the real file passes 5.
- Branch commit messages carry no closing keywords.
- CI run 43732681379 (`pull_request`, full matrix because the label is on): lint, licences, security, browser, `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` and `CI passed` all green on 356cc10.

**Verdict: approved at 356cc10. Squash-merged pinned to 356cc10 → main 3d66b93. #360 closed (completed).**
