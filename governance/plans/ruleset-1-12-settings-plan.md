# Ruleset 1.12.0: autonomy until Colin says stop, told only what needs him (#738)

Thread: ruleset-max-autonomy (settings session, critical work, Opus 5.5 high). Lanes: infra, docs. Critical: yes (META-01, CRIT-01: ruleset, its extracts, config, project instructions).
Colin's request (coordinator chat, 22 Nov 2026): "change the autonomy setting to maximum autonomy". In the settings thread he chose, one question at a time: "Until I say stop", "Only what needs me", "Keep round 4", "Milestones to Claude", and answered "Yes, with CLAUDE.md" to the preview.

## Preview Colin approved

- AUTO-01 horizon: "until milestone v1.6 Study layer is complete or Colin asks to stop" (D-879) becomes "until Colin asks to stop". The testing and review gates stay; AUTO-02 is unchanged (generator-fixed text).
- Notify triggers: "a release is tagged and shipped" and "something waits for Colin: a decision AUTO-02 reserves for him, a critical PR stopped at its last review round, or an owner hand step". Dropped: "a critical decision or a critical merge (one line)" and the v1.6 end-of-grant trigger.
- ROLE-02: "milestone creation or renaming that only Claude asked for" leaves the owner hand steps; "repository settings and rulesets" stays (ROLE-14).
- `token_cfg.critical_max_review_rounds` stays 4; the stop cannot be switched off.
- The notify triggers live only in `governance-config.json` and in `project-state.yaml`; what threads read is CLAUDE.md workflow item 1, so its sentence "Colin is told only when he asks about progress or when a decision is critical; a critical merge gets one line" changes to match.
- The generator rewords PLAN-01 ("by its test ID ... does not exist"); restored by exact replace.
- Version 1.11.0 -> 1.12.0: the ruleset, the 7 extracts, `governance-config.json`, `project_instructions.md` (horizon line) and CLAUDE.md change.

## Plan

1. Regenerate with `generate_project_rules.py --from-json governance/governance-config.json --out-dir governance` and
   `--set 'autonomy_horizon=until Colin asks to stop'`,
   `--set 'notify_triggers=["a release is tagged and shipped","something waits for Colin: a decision AUTO-02 reserves for him, a critical PR stopped at its last review round, or an owner hand step"]'`,
   `--set 'owner_hand_steps=[...the first three unchanged..., "repository settings and rulesets"]'`,
   then `scaffold_workspace.py --refresh`.
2. Restore PLAN-01 by exact replace (assert one occurrence, line count unchanged) in `claude-project-rules.yaml` and `rules/implementation.yaml`.
3. CLAUDE.md workflow item 1: one sentence replaced, as in the preview.
4. No test changes; the existing ruleset tests guard the regeneration and the restore.
5. After the merge, the coordinator logs the D-entry, sets `active_now.autonomy_horizon` to "until Colin asks to stop", replaces the notify triggers in `project-state.yaml`, and drops the D-738 note that a Claude-asked milestone rename is Colin's hand step.

Not in scope: the generator's PLAN-01 upstream (D-849 follow-up, Colin's call); `project-state.yaml` and the decision log (the coordinator's and the KB thread's files); app or repository settings (ROLE-14).

## Tests promised in the plan

- `tests/unit/test_ruleset.py::test_plan_01_carries_the_promised_tests_wording`
- `tests/unit/test_ruleset.py::test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset`
- `tests/unit/test_ruleset.py::test_the_profile_holds_the_paths_of_the_config`

## Handoff

Goal: ruleset 1.12.0 merged into main for #738, critical merge go from the coordinator.
Done: regenerated and committed on `claude/ruleset-max-autonomy-9cab47` (f9c4d5a).
Next: PR #741 open with `ledger/prs/pr-741.yaml`; author ci:full, then the critical review in a separate thread.
