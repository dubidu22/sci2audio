# Ruleset 1.11.0: autonomy until milestone v1.6 Study layer is complete (#736)

Thread: ruleset-maximum-autonomy (settings session, critical work, Opus 5.5 high). Lane: infra. Critical: yes (META-01, CRIT-01: ruleset, its extracts, config, project instructions).
Colin's request: "change the autonomy setting to allow maximum autonomy until a milestone is reached". He picked "v1.6 Study layer" and answered "Yes, apply" to the preview (22 Nov 2026, in the settings thread).

## Preview Colin approved

- AUTO-01 horizon: "until Colin asks to stop or no open issues are left to work on" (D-740) becomes "until milestone v1.6 Study layer is complete or Colin asks to stop". The testing and review gates stay; AUTO-02 (scope, roadmap) and the owner's hand steps are unchanged.
- New notify trigger: "milestone v1.6 Study layer complete: the autonomy period ends".
- The generator rewords PLAN-01 ("by its test ID ... does not exist").
- Version 1.10.0 -> 1.11.0: the ruleset, the 7 extracts and `governance-config.json` change.
- v1.6 depends on Colin's open item "Study-layer scope before ADR #395"; work that needs it waits for him.

## Plan

1. Regenerate with the `project-governance-init` skill (init.md, "Changing settings") from `governance/governance-config.json` with
   `--set 'autonomy_horizon=until milestone v1.6 Study layer is complete or Colin asks to stop'` and
   `--set 'notify_triggers=["a release is tagged and shipped","a critical decision or a critical merge (one line)","milestone v1.6 Study layer complete: the autonomy period ends"]'`,
   then `scaffold_workspace.py --refresh` (changes only the "Autonomy horizon" line of `project_instructions.md`).
2. Restore by exact replace: PLAN-01 only, back to the D-849 sentence ("as a pytest node ID ... does not collect") in
   `claude-project-rules.yaml` and `rules/implementation.yaml`, because `.github/governance/promised_tests.py` reads backticked pytest node IDs.
3. No test changes; the existing ruleset tests guard the regeneration and the restore.
4. After the merge, the coordinator logs the D-entry, sets `active_now.autonomy_horizon` with the pinned end test (review-737 S1) and the end-of-grant trigger (S2) in `project-state.yaml`.

Not in scope: changing the generator's PLAN-01 upstream (D-849 follow-up, Colin's call); the state file (the coordinator's file).

## Tests promised in the plan

- `tests/unit/test_ruleset.py::test_plan_01_carries_the_promised_tests_wording`
- `tests/unit/test_ruleset.py::test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset`
- `tests/unit/test_ruleset.py`
- `tests/unit/test_lanes.py`
- `tests/unit/test_promised_tests.py`

## Handoff

Goal: ruleset 1.11.0 merged into main through PR #737 for #736, critical merge go from the coordinator.
Done: PR #737 at head f9ef427; review-737 round 1 changes requested (plans/review-pr737-round1.md); B1, S1, S2 answered in the PR body; this plan and `ledger/prs/pr-737.yaml` added (M1).
Next: author ci:full on f9ef427, then label removed; the coordinator records its approval of this plan; review-737 round 2 on f9ef427.
