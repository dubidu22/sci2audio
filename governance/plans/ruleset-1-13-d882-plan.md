# Ruleset 1.13.0: the dispatcher changes of D-882

Thread: ruleset-d882 (settings thread, critical work, Opus 5.5 high). Lane: infra. Critical: yes (META-01, CRIT-01: ruleset, extracts, `governance/tools/**`, a CI workflow).
Owner's yes to the preview below: "Yes, apply" (Colin, 22 Nov 2026, in the settings thread; META-01). Issue #743, PR #745.
Source: D-882 in `kb/pending-decisions.md` (Colin: "Yes, start it", 22 Nov 2026) and the read-only audit of 22 Nov (session "Audit: do we need the dispatcher?"), whose wording is used below where it fits.

## Why by hand

`generate_project_rules.py --dry-run` against the 1.12.0 config reproduces every rule except PLAN-01: none of the six changes is a setting the generator has. So, as #730, #737 and #741 did for PLAN-01: the generator runs once (it bumps the version to 1.13.0 and rewords PLAN-01), `scaffold_workspace.py --refresh` runs, then every change is an exact replace asserted to match once, and a test pins each new text so a later regeneration that drops it fails (META-03). The refresh rewrites `dispatcher_instructions.md`, `ledger/README.md` and `tools/ledger_tool.py` from the skill's copies, so the hand changes there are guarded by tests too. The upstream generator change is Colin's call (as the D-849 follow-up).

## Rules changed (exact replace in `claude-project-rules.yaml` and every extract that carries the rule)

1. **THR-10** (coordinator, dispatcher). New first sentence: "Starting a thread: the dispatcher starts implementation and review threads as background subagents of its own session (Agent tool, with the slot's model and effort from execution_profile.model_routing, and `isolation: worktree` when the thread writes files); it writes a starter block only if it has no such tool." The rest stays, starting "Otherwise, if you have a tool that opens a thread or session, ...".
2. **MRG-01** (review). The go clause becomes "(dispatcher for PRs confirmed non-critical; for critical ones the coordinator, whose go is the file ./governance/ledger/gos/pr-<N>.yaml with the head SHA, the coordinator and the time, written by the coordinator and required by ledger_tool.py gate <N>)". Two additions: "For a risk:high PR, re-run `governance pr checks` on that head after the approving round entry is pushed." And, in the behind-main sentence: "..., re-verify diff and CI, record the new SHA as `updated_head` in the latest round entry, and merge on the new SHA."
3. **ROLE-11** (dispatcher). Appended: "It also watches CI and merges for PRs outside the batch that the coordinator names, and records them in the batch file."
4. **THR-05** (dispatcher). "..., at the next hand-off, and never while one of its subagents is running."
5. **ROLE-17** (coordinator). Appended: "A dispatcher event reaches you as one line starting with `COORDINATOR:`; its content is in ./governance/plans/batch-<NNN>.md, read it there." **THR-04** (all). Appended: "The dispatcher sends the coordinator one line per event, starting with `COORDINATOR:`; the content goes in the batch file."
6. **PLAN-01**: the D-849 wording is restored again (sixth time).

`dispatcher_instructions.md` gets the same changes in its THR-10 bullet, its THR-05 sentence and its reporting paragraph (one `COORDINATOR:` line per event, content in the batch file; it also watches the PRs outside the batch the coordinator names). `project_instructions.md` is unchanged: the coordinator's own way of starting threads and reading events is covered by its extract.

## Tool: `governance/tools/ledger_tool.py`

- **Go files.** New folder `ledger/gos/`, one file per critical PR, writer the coordinator:
  ```yaml
  pr: 12
  head: 3f9c2ab                  # the reviewed head the go is for
  by: "coordinator (session ...)"
  time: 2026-11-22T19:00Z
  ```
  `gate` passes a PR whose round 1 says `critical: yes` only when `gos/pr-<N>.yaml` exists, names the coordinator in `by`, and its `head` is the latest round's `head` or `updated_head`. A non-critical PR needs no go file (the dispatcher's go stays a message). `check` reports malformed go files. `status` then shows an approved critical PR without a go as "gate stops [next: coordinator]".
- **`updated_head`** (optional, round entries): the head after MRG-01's update from main; `gate` and `approved` accept it beside `head`.
- **New command `approved <N> --head <sha>`**: exit 0 only if the latest round entry approves exactly that head (`verdict: approved`, `must_fix: 0`, `head` or `updated_head` equal) or an owner override for that head is recorded (MRG-02). This is what CI calls.
- **The #737 stats bug is a tool bug.** The tool knew a merge only from a round entry's `merged`. A PR merged with no round recording it (#737: Colin merged after a changes-requested round, by owner override) stayed "not merged" in `stats` and "open" in `status`, although 13 PR entries carry `merged:`, a field the README never named. Fix: the README names `merged` in `prs/pr-<N>.yaml` ("the merge commit SHA, when no round records the merge"), and one helper reads a merge from the round first, then from the PR entry when it starts with a commit SHA. `stats`, `status`, `table`, `gate` ("already merged"), `flags` and `fix_claims` use it. `triage` still counts only round merges, so it does not newly demand deferred entries for #737's two should-fix findings; whether they need entries is the coordinator's call.
- `ledger/README.md`: the gos format and writer row, `merged` in the PR format, `updated_head`, the `approved` command.

## CI: the required job `governance pr checks` (change 6)

A new last step in the existing job (so the required check name stays), `if: ${{ !cancelled() }}`:
- PRs without the `risk:high` label pass the step at once.
- **How CI reads the ledger:** `git fetch` of `refs/heads/governance` (public repository, no credentials; `persist-credentials: false` stays), then `git archive origin/governance governance/ledger | tar -x` into `$RUNNER_TEMP`. The ledger never comes from the PR branch.
- **Which code judges:** `ledger_tool.py` as it is on the PR's base commit (`git show "$PR_BASE:governance/tools/ledger_tool.py"`), so a PR cannot change the check that judges it. Only when the base copy has no `approved` command yet (this PR, the bootstrap) does it use the PR's copy.
- **Permissions:** unchanged, `contents: read` and `pull-requests: read`, trigger `pull_request` (never `pull_request_target`). PR code runs only without write rights, and nothing from the PR reaches a script except through environment variables (number, labels, base and head SHA).
- **Timing:** the round entry lands on `governance` after CI ran, and nothing re-triggers the check on a push to `governance` (that would need write rights). So the step fails on a risk:high PR until review approves its head, and the review thread re-runs it (`gh run rerun --failed <run>`) after pushing its approving round entry. This is in MRG-01 (change 2). The failure message says so.
- **Not covered:** a PR that edits `governance-pr-checks.yml` itself runs its own version of the workflow and could drop the step. Such a PR is critical by `critical_paths` and the diff shows it; closing that would need a second, base-side workflow made required, which is a repository setting (Colin, ROLE-14). The same hand step D-882 names: set the main ruleset so no one can bypass the required checks.

## Files

`governance/claude-project-rules.yaml`, `governance/rules/*.yaml` (all 7: version; THR-04 is in every extract), `governance/governance-config.json` (version), `governance/dispatcher_instructions.md`, `governance/ledger/README.md`, `governance/tools/ledger_tool.py`, `.github/workflows/governance-pr-checks.yml`, `tests/unit/test_ruleset.py`, `tests/unit/test_ledger_tool.py`, `tests/unit/test_ci_workflows.py`. Rough size: about 150 lines of tool and test code, plus the rule texts. No change in `src/`.

## Tests promised in the plan

- `tests/unit/test_ruleset.py::test_plan_01_carries_the_promised_tests_wording`
- `tests/unit/test_ruleset.py::test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset`
- `tests/unit/test_ruleset.py::test_the_profile_holds_the_paths_of_the_config`
- `tests/unit/test_ruleset.py::test_a_d882_rule_keeps_its_wording`
- `tests/unit/test_ruleset.py::test_the_dispatcher_instructions_carry_the_d882_changes`
- `tests/unit/test_ledger_tool.py::test_gate_stops_a_critical_pr_without_a_go_file`
- `tests/unit/test_ledger_tool.py::test_gate_passes_a_critical_pr_with_a_go_for_its_head`
- `tests/unit/test_ledger_tool.py::test_gate_stops_a_go_for_another_head`
- `tests/unit/test_ledger_tool.py::test_gate_needs_no_go_file_for_a_non_critical_pr`
- `tests/unit/test_ledger_tool.py::test_gate_and_approved_take_the_updated_head`
- `tests/unit/test_ledger_tool.py::test_approved_passes_only_the_head_the_latest_round_approved`
- `tests/unit/test_ledger_tool.py::test_approved_takes_an_owner_override_for_this_head`
- `tests/unit/test_ledger_tool.py::test_check_reports_a_malformed_go_file`
- `tests/unit/test_ledger_tool.py::test_a_merge_recorded_only_in_the_pr_entry_counts_as_merged`
- `tests/unit/test_ci_workflows.py::test_the_governance_check_gates_a_risk_high_pr_on_the_ledger_of_branch_governance`
- `tests/unit/test_ci_workflows.py::test_the_governance_check_runs_pr_code_only_without_write_access` (existing, must stay green)

Parametrized ones (`test_a_d882_rule_keeps_its_wording`) collect as one node per rule ID.

## After the merge (not in this PR)

- Coordinator: log ruleset 1.13.0 with the next D-number, quoting Colin's yes; re-read the extract; from now on write `ledger/gos/pr-<N>.yaml` for each critical go. Record #741's merge (`3fb4d1b`) in `prs/pr-741.yaml`, whose `merged` is still empty.
- Dispatcher (next start): re-read `dispatcher_instructions.md`; merge `main` into `governance` (THR-14).
- Colin (ROLE-14, hand step): set the main ruleset so no one can bypass the required checks.

## Handoff

Goal: ruleset 1.13.0 merged into main with the six D-882 changes and the stats fix; critical merge go from the coordinator.
Done: plan written; Colin's yes ("Yes, apply"); Issue #743; PR #745 rebased onto #740 (4473133), `governance/github-setup/pr-checks-workflow.yml` byte-equal to the live workflow; `prs/pr-745.yaml`.
Next: ci:full green on three systems, then the critical review subagent.
