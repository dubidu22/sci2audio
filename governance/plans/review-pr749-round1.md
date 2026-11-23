# Review PR #749, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/749 (#746, D-874; plan `plans/docs-b-d2-plan.md`, approved D-883, amended D-884)
- Head: `bdc8247c3da2a008990d05bad6662c98033b74c8` (up to date with main `5213b4a`)
- Thread: review-b004-e (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03): adds a CI step under `.github/` and a check script (safety mechanism, CI workflow), carries `risk:high`. Plan approved before the code (D-883).
- **Verdict: approved.** Must-fix 0, should-fix 0, notes 3.

## Verified checks

- CI run 45124653781 (pull_request) on bdc8247: all jobs green; the `lint and layers` log prints `no working files on this branch`.
- Three-system run 45124663555 (workflow_dispatch, `ci:full`) on bdc8247: `tests (ubuntu|macos|windows-latest)` all success, `CI passed` success (D-580).
- `governance pr checks` on bdc8247: red only because no approving round existed for the head (`approved` step). Its two WARNs were judged: `unowned: tests/unit/test_working_files.py` is accepted in the approved plan §5; the two deleted probe files under `plans/` were never collected (`testpaths = ["tests"]`) and still exist on branch governance (TST-02: not removed to turn CI green).
- Deletions (AC 1, 2): 772 deleted paths, every one a working file by the script's own rule, every working file on main is in the list, every one exists on `origin/governance`. The four that differ between the branches (`pending-decisions.md`, both ledger tables, `project-state.yaml`) were last changed on main by #657 only, so no main-only content is lost. The three generator files are byte-equal on main, the PR and governance.
- The check fails on a known-wrong case (VER-02): run on a checkout of `origin/main` and on the governance worktree it exits 1 with the hit lines and the pointer; on the PR head it exits 0.
- Tests: the 9 promised tests are in the file (31 cases) and pass locally (`pytest --noconftest`; `uv` could not fetch Python 3.12.16 here, so the full fast suite is taken from CI). Hand mutations of the script are caught: dropping `ledger/` from `WORKING_DIRS` (4 fail), not printing the pointer (1 fails), ignoring `KEPT` (5 fail). Removing the CI step is caught by `test_ci_runs_the_check_in_the_lint_job`. `mutmut` covers `src/sci2audio/` only, and this PR changes no `src/`, so no mutation run applies; no Hypothesis test changed, so no nightly seeds apply (D-626).
- Readers (AC 6): no file outside the deletions reads the deleted paths; the remaining mentions in `pr-checks.json` (both copies), `lanes.yml`, `governance-pr-checks.yml` (reads `origin/governance`) and tests are path globs or strings. No generator file changed.
- After-merge procedure (AC 7) simulated on a scratch clone of governance merged with the PR head: the merge stops on conflicts as the body says; after `git checkout HEAD -- <working paths>` the `git diff --cached --stat "$old"` line prints nothing, the tree equals the PR head outside the working paths, and the kept generator files equal main's.
- `CLAUDE.md`: the six state-file mentions name branch `governance`; no `rules/project-state.yaml` remains.
- PR-05/PR-06: comments say why; no unplanned feature, file or dependency.

## Findings

- **N1** (note). The script docstring and the test say CI never runs on branch governance, but `ci.yml` also has `workflow_dispatch`, which can be started on any ref (`ci-full-label.yml` starts it on a PR's head branch). A run by hand on `governance` would go red in `lint and layers`. No one does that today and no PR ever targeted governance (0 PRs with base `governance`), so this is accepted as is; whoever starts CI by hand on governance should expect the red.
- **N2** (note, for the dispatcher's one-time merge). `git checkout HEAD -- governance/ledger governance/plans` also resets the three generator files to governance's copy. Today they are byte-equal to main, so nothing is lost; if a ruleset PR changes one of them on main before the one-time merge, that change would be silently dropped on governance and the `$old` diff would not show it. Add `git diff --cached --stat origin/main -- governance/plans/README.md governance/ledger/README.md governance/ledger/deferred/since.txt` (must print nothing) before the commit.
- **N3** (note). The pointer file lives in `governance/kb/00-index/` (D-884); the KB README's file count ("53 Markdown files in 7 folders") is a dated status line and was not updated. No action.

## Handoff (THR-07)

- Goal: critical review round 1 of #749 at bdc8247.
- Done: approved, 0 must-fix; ledger `rounds/pr749-round1.yaml` written.
- Next: the coordinator's go `ledger/gos/pr-749.yaml`, then `ledger_tool.py gate 749`, the re-run of `governance pr checks` on bdc8247 (MRG-01, risk:high), the pinned squash merge, `merged:` here, and the main CI run on all three systems.
