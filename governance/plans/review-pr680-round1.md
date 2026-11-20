# Review PR #680, round 1 (batch B-I1, #664 and #665)

Thread: review-infra-b-i1 (Opus 5.5). Head reviewed: c6322ae. Date: 2026-11-20.
**Critical: yes** (CRIT-01: a CI workflow, the governance PR check and the labeler under `.github/**`; `risk:high` set). Plan `plans/infra-b-i1-plan.md`, approved as D-839.

**Verdict: changes requested** (0 must-fix, 4 should-fix, 5 notes).

## Verified

- (a) Workflow security, `.github/workflows/codeql.yml`: top-level `permissions: {}`; the job has only `contents: read` and `security-events: write`. All three `uses:` are SHA-pinned to real releases: `actions/checkout@3d3c42e…` is tag v7.0.1 (lightweight tag, commit 3d3c42e, released 2026-07-20); `github/codeql-action@1bd86f2…` is tag v4.39.4 (annotated tag e046217 dereferences to commit 1bd86f2). The checkout step has `persist-credentials: false`. There is no `pull_request_target` and no `run:` step, so no `${{ }}` can be injected into a script; the only expressions are `matrix.language` in the job name and in `with:`. `uv run zizmor --offline .github/workflows` reports no findings at c6322ae.
- (b) CodeQL config: `paths-ignore` is exactly `docs/design/prototype/**` and `governance/**`. None of the tracked files under `src/` or `.github/` matches either glob, and `.github/governance/pr_checks.py` stays scanned. The categories are `/language:actions`, `/language:javascript-typescript` and `/language:python`, the same names as the default-setup analyses on `main` (20f9575), so the alert history carries over. The PR's own analyses (43fac1c) use those categories. Alerts 8, 9 and 10 are still dismissed, and there is no open code-scanning alert.
- (c) Lanes: every one of the 878 tracked files under `governance/` and `docs/design/` (`git ls-files`) matches exactly one lane. I checked this by hand with `pr_checks.matches` against `pr-checks.json` as well as through the PR's test. `lanes.yml` and `label_paths` agree lane for lane, and the `risk:high` globs in `labeler.yml` equal `critical_paths` in the same order.
- (d) `governance_paths` narrowing, reasoned through `run_checks` and confirmed with dry runs:
  - A PR of working files only (plans, ledger, state, memory, release, `workflow-export.md`, kb) is governance-only: `scope ok`, with no title, lane or ownership check, as before.
  - The daily decision-log PR (`governance/kb/decision-log.md`, no lane label, a title without `(#N)`) still passes: commits ok, scope ok, new docs ok.
  - A ruleset PR (`claude-project-rules.yaml` and `rules/**`, even with a kb file) now needs the title format, `lane:infra` and `risk:high`. Without them it fails title, lane label, ownership and critical. With them everything passes. This is what D-839 asked for.
  - A PR that changes only `governance/tools/**` now needs the title and `lane:infra`, but not `risk:high` (S2).
- (e) Tests fail without the change, judged by reading:
  - The CodeQL tests need the new files.
  - `test_the_governance_check_reads_the_same_lanes_as_lanes_yml` and the labeler-equals-critical test fail on the old config.
  - The infra-ownership tests fail on the old config because `governance/**` was skipped, so `lane:docs` passed.
  - The working-files tests are characterisation tests and pass on both configs, as intended.
- (f) The title passes `TITLE_RE`. The body has `Closes #664`, `Closes #665`, a licence note (none) and the risk. There is no unrelated change: 8 files, all named in the plan.
- Local run in a worktree at c6322ae (macOS M4):
  - zizmor clean.
  - `tests/unit/test_ci_workflows.py tests/unit/test_lanes.py`: 48 passed.
  - Fast suite `-k "not espeak"`: 8469 passed, 6 skipped, 6 xfailed.
- CI at c6322ae: Linux `tests`, `CI passed`, `governance pr checks`, `security` and the three CodeQL legs are green. The `ci:full` dispatch run is green on all three systems: `tests` passed on ubuntu, macOS and Windows.

## Findings

### S1 (should-fix): the checkout pin test breaks on every Dependabot bump
`tests/unit/test_ci_workflows.py:368` finds the checkout step by the literal text `# v7.0.1`. `.github/dependabot.yml:3` updates github-actions weekly and rewrites that version comment, so the first checkout bump fails this test on a correct PR. Fix: find the step by `actions/checkout@` or match `# v\d[\d.]*`, and keep the `persist-credentials: false` assertion.

### S2 (should-fix): the merge-gate tool is not a critical path
`.github/governance/pr-checks.json:75-88` and `.github/labeler.yml`: `governance/tools/**` holds `ledger_tool.py`, the `gate` that MRG-01 runs before every merge. That is a safety mechanism under CRIT-01. The PR makes the path lane:infra (`pr-checks.json:54`) but not critical, so a PR that changes the gate passes without `risk:high`. Dry run: `governance/tools/ledger_tool.py` with `lane:infra` alone passes every check. Fix: add `governance/tools/**` to `critical_paths` and to `labeler.yml`, with a sample in `test_a_rules_change_needs_risk_high`. D-839 named only the four rules paths, so if the coordinator keeps the plan as approved, it records why and this is declined. `governance/github-setup/**` is the unrun template copy and can stay non-critical.

### S3 (should-fix): the generator's source still holds the old lanes
`governance/governance-config.json:92` (`critical_paths`) and `:125` (`label_paths`), and `governance/claude-project-rules.yaml:38-39` (`project_profile.critical_paths`, `label_paths`), still list the pre-#665 globs and have no `governance_paths`. The header of `pr_checks.py` says `pr-checks.json` "is written by scaffold_workspace.py --github from governance-config.json", so the next re-scaffold silently reverts #665. CRIT-03 also points at `project_profile.critical_paths`, which now differs from the check. Changing the ruleset and its config is owner-gated (META-01, THR-14) and outside this PR's plan, so the fix is an Issue: a ruleset PR that brings the config and `project_profile` in line with `pr-checks.json`, milestone v1.4, `lane:infra` and `risk:high`. Name that Issue in the PR body.

### S4 (should-fix): the PR body does not name the follow-up Issue
The PR body's "Out of scope" section says "linked in a comment"; #681 appears only in a PR comment. Name #681 (and S3's Issue) in the body so the record holds it.

### Notes
- N1: `.github/lanes.yml:33` `docs/design/**` is already covered by `docs/**`. Keeping it is fine, because #665 asks for it by name, and the exactly-one-lane test counts lanes, not globs.
- N2: since `governance/github-setup/**` and `governance/tools/**` left `governance_paths`, a new markdown file there other than `README.md` now fails the PR-05 new-docs check (dry run: `A governance/github-setup/NOTES.md` gives `new docs FAIL`). This is consistent with PR-05; keep it in mind for the next skill-template update.
- N3: the header sentence of `.github/governance/pr_checks.py:52` ("governance files (the workspace folder)") now describes `governance_paths` loosely. It is the template's text, so leave it.
- N4: `load_pr_checks` and `tracked_files` are duplicated in `tests/unit/test_ci_workflows.py:315-336` and `tests/unit/test_lanes.py:21-67`. A shared helper would do; this is not worth a round on its own.
- N5: zizmor's pedantic persona also notes that `codeql.yml` has no `concurrency` group; `ci.yml` and four other workflows have one. That is optional. `github/codeql-action` v4.39.4 was released on 2026-11-20, the day it was pinned: GitHub's own action, so acceptable.

Verdict: changes requested. No must-fix; S1 and S2 need one fix commit, and S3 and S4 need an Issue and a body edit.
