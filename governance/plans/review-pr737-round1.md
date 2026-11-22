# Review PR #737, round 1 (ruleset 1.11.0, #736)

Thread: review-737 (Opus 5.5 high). Head reviewed: f9ef4275f0618d358bb697709695e968ae38fa4e. Base: `main` at 880b170 (the PR is up to date with it). Date: 2026-11-22.
**Critical: yes** (META-01, CRIT-01: the ruleset, all 7 extracts, `governance-config.json` and `project_instructions.md`, all in `project_profile.critical_paths`; `risk:high`, `lane:infra`). Author: the settings session `ruleset-maximum-autonomy`. The owner's yes is "Yes, apply" (22 Nov 2026), on the preview in the settings thread. This review does not quote that message itself; the PR body and #736 report it.

**Verdict: changes requested** (2 must-fix, 2 should-fix, 4 notes). None of the four needs a commit. B1 is a PR-body edit. M1 needs two files on branch `governance` and one line from the coordinator. S1 and S2 are answered in the PR body's after-merge list. So round 2 can review the same head, f9ef427.

## Verified

- **The regeneration is reproducible.** I ran the skill's `generate_project_rules.py --from-json governance/governance-config.json` (the PR's config) into a scratch folder.
  - Its summary is "ruleset version 1.11.0".
  - The normalised `governance-config.json` and 6 of the 7 extracts match the PR byte for byte.
  - `claude-project-rules.yaml` and `rules/implementation.yaml` differ from the generator output in one line each: PLAN-01. The PR has the D-849 text ("as a pytest node ID ... does not collect"). The generator writes "by its test ID ... does not exist". The PR's PLAN-01 equals `main`'s, so this is the restore the body names, and there is no other hand edit.
  - `test_plan_01_carries_the_promised_tests_wording` guards the restore.
- **The extracts match the full ruleset.** For each role, I compared the rules whose `applies_to` is `all` or names that role with the extract's `rules`. All 7 match by id and text: assist 17, audit 19, coordinator 33, dispatcher 23, implementation 41, kb 17, review 29. All 7 carry version 1.11.0.
- **Nothing else changed.** `git diff origin/main...f9ef427` touches 10 files and 14 lines:
  - 9 version lines;
  - AUTO-01 in the ruleset and in `rules/coordinator.yaml`;
  - `autonomy_horizon` and one added `notify_triggers` entry in the config;
  - the "Autonomy horizon" line of `project_instructions.md`.
  - No other rule, path list, model or lane changes. `claude-md-snippet.md`, `dispatcher_instructions.md`, CLAUDE.md, `.github/` and `src/` are untouched.
- **AUTO-02, ROLE-01 and ROLE-02 are unchanged.** Product scope, external contracts, the roadmap and the milestones stay with Colin, and so do milestone creation and renaming. So does the round-4 stop (REV-01).
- **No contradiction with the decision log.**
  - D-80 (until v1.0), D-462 (through v1.1) and D-702 a ("until v1.3 finished") were milestone horizons. The new horizon returns to that form.
  - It replaces the open horizon of D-740, which the coordinator's D-entry must say it amends.
  - The testing and review gates of D-80 stay word for word in AUTO-01 ("keeping all testing and review gates intact").
  - AUTO-03 (work beyond the active milestone) still works under the new horizon.
- **`project-state.yaml`.** On branch `governance` (8da722c), the copy that counts for state (THR-13), it already says `9: "v1.6 Study layer"` and has v1.5 Listen while generating before it in `roadmap_order`. The PR body's claim that the state file "still says v1.5 Study layer" holds only for the stale copy on `main` (VER-02). `active_now.autonomy_horizon` still holds the D-740 value, and the coordinator updates it after the merge (THR-04).
- **Tests.**
  - Locally, `uv run pytest -q tests/unit/test_ruleset.py tests/unit/test_lanes.py tests/unit/test_promised_tests.py` gives 86 passed.
  - The skill's `audit_rules.py` on the PR's ruleset gives 0 errors and 2 warnings. A14 (the files differ from `main`) is expected before the merge. A08 (41 rules bind the implementation thread) is also on `main` and is not new.
- **CI on f9ef427.**
  - Green: `CI passed`, `tests (ubuntu-latest)`, both Chromium shards, lint and layers, licences, security, web paths and CodeQL.
  - **`governance pr checks` is red** (B1).
  - `ci:full` has not run. `tests (macos-latest)` and `tests (windows-latest)` are skipped (see "Before the final round").
- **Form.**
  - The title follows `<area>: <outcome> (#N)`.
  - The body has `Closes #736`, risk, licence and after-merge sections.
  - The commit message has no closing keyword.
  - The first three acceptance criteria of #736 are met by the diff. The fourth (test_ruleset passes, audit 0 errors) holds locally.

## Findings

### Must-fix

- **B1 (kind: promised-tests-format).** The required check `governance pr checks` fails on f9ef427 in all three runs (45055691178, 45055692518, 45055692138). The output is "FAIL promised tests: the section lists no node ID; name each test as `tests/...py::test_name`". The body's "## Tests promised in the plan" lists three file paths only. MRG-01 needs required CI green. The same kind sent #735 back today, and the check caught it both times, so the check works (VER-02) and no new check is needed (REV-05).
  - **Fix wanted:** edit the PR body only. Under "## Tests promised in the plan", list at least the node IDs that prove this change, each in backticks: `tests/unit/test_ruleset.py::test_plan_01_carries_the_promised_tests_wording`, `tests/unit/test_ruleset.py::test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset`, and the file paths as before. The `edited` event re-runs the check. Confirm it is green on f9ef427.
- **M1 (kind: missing-plan).** The PR has no plan in `governance/plans/` and no ledger entry `governance/ledger/prs/pr-737.yaml` on branch `governance`. For #730 there were `plans/ruleset-1-10-settings-plan.md` and `prs/pr-730.yaml`. The body's heading "Tests promised in the plan" points at a plan that does not exist. CRIT-02 needs the coordinator's plan approval, and CRIT-03 stops a critical PR without one for the coordinator. Colin's "Yes, apply" approves the setting (META-01). It does not replace the record of the plan and its approval, which `ledger_tool.py` and the next thread read.
  - **Fix wanted:** the author commits `plans/ruleset-1-11-settings-plan.md` on branch `governance`. It holds the preview Colin approved, the restore and the promised tests. The author also commits `ledger/prs/pr-737.yaml` with `plan:` set and `critical: yes`. The coordinator then records its approval of that plan in one line (batch or decision notes), before its merge go.

### Should-fix

- **S1 (kind: untestable-condition).** "until milestone v1.6 Study layer is complete" names the milestone by a title that was renamed recently, from v1.5 to v1.6 (`kb/pending-decisions.md:133`). "Complete" can be read two ways:
  - all Issues in the milestone are closed;
  - the milestone is closed. INV-13 closes it after R3, that is after the v1.6 release.
  - The two readings differ on whether the v1.6 release runs under the grant.
  - The ruleset wording is what Colin approved, so it should not change in this PR. Under META-02 the runtime test belongs in `project-state.yaml` anyway.
  - **Fix wanted:** in the body's after-merge list, ask the coordinator to pin the test in the D-entry and in the comment on `active_now.autonomy_horizon`. My reading of INV-13: the grant ends when GitHub milestone 9 (now "v1.6 Study layer") is closed after R3 of the v1.6 release, or when Colin asks to stop. The D-entry should also say that moving Issues into or out of milestone 9 is a roadmap change, which stays with Colin under AUTO-02 and ROLE-01. That way the coordinator cannot move its own end date. If the author or the coordinator means the other reading, the D-entry says so instead.
- **S2 (kind: dead-setting).** The new notify trigger "milestone v1.6 Study layer complete: the autonomy period ends" lives only in `governance-config.json`. No rule or extract carries it. `project_instructions.md:110` sends the coordinator to "the notification triggers in `project-state.yaml`". The live state file has no trigger list, only `notifications_pending: []`, and the generator kept the state file (no `--reset-state`). So as merged, nothing tells the coordinator to post the end of the grant.
  - **Fix wanted:** add to the body's after-merge list that the coordinator writes the trigger into `project-state.yaml`, next to `autonomy_horizon`. On firing, the coordinator posts in chat and waits (project_instructions.md:110), and from then on critical plans and merges go to Colin.

### Notes

- **N1.** This is the fourth regeneration (after D-855, D-871 and D-877) where the generator's PLAN-01 had to be restored by hand. The test guards it (META-03). The upstream generator change stays the owner's call (D-849 follow-up). The D-entry should say once more that it is still open.
- **N2.** The old clause "or no open issues are left to work on" is dropped. Suppose v1.6 waits on the owner item "Study-layer scope before ADR #395" and nothing else is open. Then the grant stays on with nothing to do. That is harmless, and Colin's "asks to stop" still ends it.
- **N3.** The `milestones` and `roadmap_order` lines in `main`'s copy of `project-state.yaml` are stale. That is the copy on `main` that THR-13 does not count. `governance` is current. No change is needed in this PR.
- **N4.** Colin still has to paste the changed "Autonomy horizon" line into the coordinator's project instructions (ROLE-14). The body lists this step.

## Before the final round

- The author adds `ci:full` once B1 is fixed, waits for `tests (macos-latest)` and `tests (windows-latest)` green on f9ef427, then removes the label (D-698, D-580). A label event creates no new commit, so the head stays f9ef427.
- Round 2 checks: `governance pr checks` green on f9ef427; plan and `prs/pr-737.yaml` on `governance`; the coordinator's plan approval line; the body's after-merge list carries S1 and S2; the `ci:full` run is green on all three systems.

Answer each finding in the round-2 hand-off as fixed (with proof), deferred (Issue) or declined (reason) (REV-02).
