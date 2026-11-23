# Audit: batch 004 (critical_only)

Audit thread audit-batch-004 (Opus 5.5 medium), 2026-11-23 (08:40 to 08:50Z). Read-only on product
code; this file and `ledger/audits/batch-004.md` are the only writes. Started from
`ledger_tool.py flags` (ROLE-15), then the merged diffs of the critical PRs.

- Scope: #737 (1bebb96), #741 (3fb4d1b), #742 (f85a633), #740 (b5a40a0), #745 (3bf852f),
  #749 (1cbfbd2). #735, #739 and #748 (non-critical) were read only where a critical PR touched them.
- **Verdict: pass. 0 blocking, 3 should-fix, 7 notes.**

## What was checked, and held

- **Pinned heads.** For every PR, `git merge-tree --write-tree <squash>^ <head>` equals the squash's
  tree: #737 f9ef427, #741 f9c4d5a, #742 85dd312, #740 e24fa58, #745 095cb2a, #749 bdc8247. Each is the
  approved round head (#740, #742, #745, #749) or the override head (#737, #741).
- **Three systems on the final head (D-580).** #740 run 45066994414, #742 ci:full on 85dd312, #745 run
  45075077530 (ubuntu, macos, windows success), #749 run 45124663555. #741: green before the merge.
  #737: macOS and Windows still running at the merge, green after (in the override, D-879).
- **Main after #749.** CI 45139630420 on 1cbfbd2: Linux, Windows, browsers, lint green; macOS still
  running at 08:44Z. Check it before the batch report.
- **D-883 governance merge.** Tag `governance-before-d874` = f12fe96 on origin. `git diff f12fe96
  6409f52` over the four working paths is empty; outside them 6409f52 equals 1cbfbd2.
- **Hard rules.** No critical PR touched `src/`, `pyproject.toml`, `uv.lock`, licences, corpus or
  snapshots. No network call, no binding change, no text rule change. The only golden change is #742's
  goal strings (declared, critical; per its first commit the new test was red on main: 24 English, 39 German).
- **Copies.** `.github/workflows/governance-pr-checks.yml`, `labeler.yml` and `labeler-workflow.yml`
  are byte-equal to their `github-setup/` copies on main, after both #740 and #745 edited them.
- **Deferred fixes.** pr715-1's 266f10f is in #715's merged head 022db85; pr737-1/2's 013069d is on
  governance (the state-file fix). #744 (v1.5) and #747 (v1.6) have milestone, lane and risk labels.
- **VER-02.** #740's clock-bound check has 7 self-tests that feed it known-bad sources; #742's goal test
  was red on main; #745's `approved` gate was red on #745 and #749 until their rounds landed.

## Should-fix

- **F1. The ledger does not know two merged PRs.** `ledger_tool.py status` lists #741 as "in work, no
  review round yet" and #721 as "round 1 approved, gate stops"; both are merged (#741 3fb4d1b on main,
  #721 into release/1.4 on 2026-11-21). Their PR entries have `merged: ""`, which the README says the
  recorder of a by-hand merge fills in. So `stats` says 29 merged, and the revert share and THR-02
  counts are taken over the wrong set. Two PRs, same cause (a merge by hand that nobody recorded).
  Data fix: fill `merged:` in `prs/pr-741.yaml` and `prs/pr-721.yaml` (writer: the coordinator, who
  recorded both overrides and decisions). **Verdict: check.** `ledger_tool.py check` could list PR
  entries without a merge record whose number appears as `(#N)` at the end of a squash subject on
  `main` or `release/*` (`git log --format=%s`), and fail on them.
- **F2. A deferral made in the approving round leaves no trace in the ledger.** #745 round 1 S4 was
  deferred to #747 in round 2; round 2 records `should_fix: 0`, and there is no `deferred/pr745-*.yaml`.
  `triage` checks the last round's `should_fix` against `deferred/`, so it reports "nothing is waiting"
  while #747 holds a risk:high gap (release branches run no gate). **Verdict: check.** A round entry
  field such as `deferred: 1` (findings of earlier rounds set aside in this round), and `check` fails
  when the count of `deferred/pr<N>-*.yaml` is below it. Data fix: the coordinator writes
  `deferred/pr745-1.yaml` (S4, planned in #747).
- **F3. Milestone v1.4 is not closed.** The batch goal was to close it; 56 closed, 1 open: #731 (the
  coordinator's advisor start, PREF-01 against the model-start rule), which the batch file left to the
  coordinator. With coordination moving into the claude.ai Project (#751, ruleset 1.14.0, open), #731
  may be moot or need rewording. **Verdict: owner** if #731 moves milestone (ROLE-01: milestones are
  Colin's); otherwise the coordinator closes it as superseded by #751 or plans it into the next batch.

## Notes

- **N1. Two owner overrides in one day, both ruleset PRs** (#737 D-879, #741 D-880). The reasons
  differ (process findings only; "correct previous setup"), so the flags do not yet show a wrong rule.
  Both came from Colin's own settings sessions, after his explicit yes, and the ruleset tests passed.
  Since #745 a risk:high PR without an approving round is red on `governance pr checks`, so the next
  such hand merge needs an `overrides/` entry first. **Verdict: owner**, only if this repeats: whether a
  generated ruleset change Colin already approved word for word gets a shorter review path.
- **N2. The gate's bootstrap fallback is live once more for #747.** `governance-pr-checks.yml` copies
  the PR's own `ledger_tool.py` when the base has no `def approved(`. On main that is dead (review-745
  N8), but the release/1.0, 1.1 and 1.4 bases have no `approved`, so #747's port would let the port PR
  judge itself with its own tool. **Verdict: check** in #747's plan: port the tool first, or drop the
  fallback and fail closed when the base has no `approved`.
- **N3. Review tags outside the scanned roots.** `governance/tools/ledger_tool.py:242` cites
  "(review-745 S1)" in a docstring; `tests/unit/test_review_tags.py` reads only `src/` and `tests/`.
  The kind `narrating-comment` is already flagged as regressed (#712, then #739). **Verdict: check.**
  Add `governance/tools` and `.github` to the scan roots (lane:infra, with the next tool PR).
- **N4. Lane config still names the working paths.** `.github/lanes.yml` (docs lane) and both
  `pr-checks.json` copies (`lane:docs`, `governance_paths`) list `governance/plans/**`,
  `governance/ledger/**`, `governance/project-state.yaml`, which `.github/scripts/working_files.py` now
  forbids on main apart from the three kept files. Harmless (the kept files still need an owner lane),
  but the two configs read opposite. **Verdict: leave** until the next ruleset regeneration; a config
  edit needs Colin (META-01).
- **N5. Clock-bound allowances.** main carries 25 `# clock-bound:` reasons in 14 files. The others are
  wait-loop exits or bounds that catch a hang many times longer than the step; `test_extraction_pdf_progress.py:151` keeps 1.5 s under a 2 s watch
  (its reason was fixed in round 1, S1). `brittle-test` is holding. **Verdict: leave**: the margin is
  the behaviour under test, and the reason says so.
- **N6. Ledger detail.** `rounds/pr745-round2.yaml` has no `critical:` (only round 1 must, CRIT-03);
  `prs/pr-745.yaml` and `prs/pr-749.yaml` have `merged: ""` although their rounds record it (allowed:
  "only when no round records the merge"); `gos/pr-749.yaml` names D-889 (the hosting) while the go is
  D-890. **Verdict: leave**; the KB thread should cite D-890 for the go.
- **N7. Batch file settings are stale.** `plans/batch-004.md` "Settings" says ruleset 1.12.0; main is
  1.13.0 since #745, and #751 (1.14.0) is open. **Verdict: leave**: the batch is ending.

## Process numbers

- Critical PRs 6: reviewed 4 (rounds: #740 2, #742 1, #745 2, #749 1), overridden 2 (#737 after
  round 1, #741 with none). Reverts 0.
- Repeated kinds from `flags` touched by this batch: `weak-guard` (#740 S2, #745 S1; with #675) and
  `missing-test` (#745 S2, S3; with #671, #675). Both are guard-code findings in governance tooling and
  tests, found and fixed in review; neither has a check yet. META-03 proposal (for the coordinator):
  for `weak-guard`, every new check in `.github/` or `governance/tools/` lands with a case that must
  fail and a near-miss that must pass (as #740's `test_clock_bounds.py` already does); `pr_checks.py`
  could warn when a PR adds a file under those paths and no test file changes.
