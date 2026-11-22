# Ruleset 1.10.0: dispatcher on Opus, promised-tests setting (#729, D-877)

Thread: settings-1-10 (critical work, Opus 5.5 high). Lane: infra. Critical: yes (META-01, CRIT-01: ruleset, its extracts, governance tools).
Colin's yes to the preview: "Yes, with restore" (22 Nov 2026, in the settings thread).

## Plan

1. Regenerate with the updated `project-governance-init` skill (init.md, "Changing settings") from `governance/governance-config.json` with
   `--set 'dispatcher_model=Opus 5.5 high' --set 'promised_tests_check=the governance check'`, then `scaffold_workspace.py --refresh`.
2. Take what the newer generator brings, unedited: THR-16 gains `fixed (the commit)`; `governance/tools/ledger_tool.py` gains the deferred
   decision `fixed` (commit of 7 to 40 hex characters; triage lists it as settled); `governance/ledger/README.md` gains the `commit:` field;
   `governance/dispatcher_instructions.md` names Opus 5.5 high and the starter-block fallback; the config gains `dispatcher_model`,
   `promised_tests_check`, `advisor: false`, `advisor_model: ""` (key order changes).
3. Restores by exact replace: PLAN-01 only. The generator now writes "by its test ID ... does not exist"; the D-849 sentence
   ("as a pytest node ID ... does not collect") goes back in `claude-project-rules.yaml` and `rules/implementation.yaml`, because
   `.github/governance/promised_tests.py` reads backticked pytest node IDs. `governance_paths` is now kept by the generator: no restore.
4. `tests/unit/test_ruleset.py`: docstring corrected (the generator keeps `governance_paths` now). No assertion changes.
5. New `tests/unit/test_ledger_tool.py` for the `fixed` decision; both tests fail against the 1.9.0 `ledger_tool.py`.

Not in scope: the skill's newer `pr_checks.py` (self-test, ~108 lines) is not copied, since `--refresh` without `--github` leaves it;
switching PREF-01's advisor to the generator's `advisor` setting; recording #715's S1 as `fixed` (the coordinator's deferred entry).

## Tests promised in the plan

- `tests/unit/test_ruleset.py`
- `tests/unit/test_ledger_tool.py::test_fixed_needs_a_commit`
- `tests/unit/test_ledger_tool.py::test_triage_lists_fixed_as_settled`
- `tests/unit/test_lanes.py`
- `tests/unit/test_promised_tests.py`

## Handoff

Goal: ruleset 1.10.0 merged into main through the PR for #729, critical merge go from the coordinator.
Done: PR #730 at head 4ec26e4; author ci:full green on Linux, macOS and Windows, then ci:full removed; review-730 round 1 approved
(0 must-fix, 2 should-fix, plans/review-pr730-round1.md); S1 filed as #731, S2 as #732 and #733, linked in the PR body; gate 730 passes.
Next: the coordinator's critical merge go for #730 pinned to 4ec26e4; after the merge, the Opus dispatcher replaces dispatcher-b004 (D-877).
