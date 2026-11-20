# Review PR #676, round 2 (batch B-P1, #216 and #203)

Thread: review-plugins-b-p1 (Opus 5.5). Head reviewed: 3e24d63 (one fix commit on 6f25cd4). Date: 2026-11-20.
**Critical: yes** (CRIT-01, text-step interface). Answer read: `plans/answer-pr676-round1.md`.

**Verdict: approved** (0 must-fix, 1 should-fix). Before merge: a green three-system `ci:full` run on the head to be merged (CRIT-02, D-580). This round ran on Linux only.

## Round 1 findings

- **M1 fixed.** `textprep/plugins.py` `_step`: `callable`, the factory call, `isinstance`, `_declares_version` and building `_GuardedStep` (which reads `id`, `languages`, `category`, `stage` and `api_version` once) now sit in one block. Any failure there except Ctrl+C becomes `_Rejected("failed while its attributes were read: …")`. `step_problems`, the name and id checks, `PluginInfo` and the runner then read only the guard's copies. Tests: `bad-property` in the parametrised rejection test, and `test_broken_installed_plugins_do_not_stop_the_command_line`. That test puts a real dist-info with three broken plugins on the path; `sci2audio script` builds the default `JobRunner()`, exits 0 and warns once per plugin. The server builds its runner through the same `JobRunner()` → `installed_steps()` path. My round-1 probe (a raising `languages` property) now gives a `PluginProblem`.
- **S1 fixed.** The loader catches `BaseException` and lets only `KeyboardInterrupt` through. At run time the guard re-raises `KeyboardInterrupt` and `Exception` as they are (N4 kept); it turns `SystemExit` and any other `BaseException` into `StepError`. A copy whose comparison raises counts as changed. `_said` makes sure an exception whose `__str__` fails cannot escape either. Tests: `boom-import` and `boom-factory` in the rejection test; `BoomStep` and `UnequalStep` in the run-goes-on test and the strict test. The existing Ctrl+C test still passes. My probes (a `BaseException` from the factory and from `find`) no longer escape.
- **S2 fixed.** `_distribution` uses `metadata.get("Name")` and `.get("Version")` inside its own guard, and returns `("", "")` on any failure except Ctrl+C. Test: `test_a_distribution_without_metadata_loads_without_a_warning`, with warnings turned into errors. My probe under `-W error::DeprecationWarning` now passes.
- N1 to N4: answered, no change. N1 and N2 are for the coordinator or KB to record; #666 should land before the release that ships this.
- Docs: `docs/plugins.md` now says that any exception except Ctrl+C counts as a failure, at load time and at run time.

## Verified

- The new tests would fail on 6f25cd4 (from reading the code and from my probes).
- Local run at 3e24d63 (macOS M4): fast suite with `-k "not espeak"` and the crash-dialog test deselected: 8426 passed, 6 skipped, 6 xfailed. lint-imports: 3 kept. deptry and ruff (check and format): clean.
- CI on 3e24d63 (Linux only): `tests (ubuntu-latest)`, `lint and layers` and `CI passed` pass. 18 checks pass and 4 are skipped (the three-system jobs, not run). One report-only check, `browser (Linux, webkit, 2/2)`, was still pending.
- No file under `src/sci2audio/web/` changed, and no unrelated change.

## Findings

### S1 (should-fix): review tags in comments and docstrings (PR-05, narrating-comment)
These comments and docstrings name the review that asked for the code. That is "who asked", which PR-05 rules out:
- `src/sci2audio/textprep/plugins.py`, the `_distribution` comment "(review S2 of #676)";
- the `_step` docstring "(review M1, S1 of #676)";
- `tests/unit/boom_on_import.py:1`;
- `tests/unit/broken_text_plugins.py` (`BadPropertyStep` docstring);
- `tests/unit/test_textprep_plugins.py` (the comment in the rejection parameters, and the comment in `test_a_distribution_without_metadata_loads_without_a_warning`);
- `tests/unit/test_app_plugins.py` (the docstring of `test_broken_installed_plugins_do_not_stop_the_command_line`).

The "why" around each tag is fine; only delete the parentheses and the "review … of #676" words. This can go in the same commit as the `ci:full` run. Round 3 then checks only that diff and the three systems.

### N1 (note): two small edges outside the guard
`step_problems` and `point.name != step.id` run on the guard's copies, so they never call plugin methods. A copied value could still be a hostile object, for example a `tuple` subclass whose `__iter__` raises, and `handles()` in `run_steps` then iterates it before the runner's `try`. That would take deliberate effort, not a careless plugin. One cheap way to close it is to move `step_problems` and the id checks into the same guarded block. No change asked in this PR.

Handoff (THR-07): goal: PR #676 to merge. Done: round 2 approved with 1 should-fix. Next: the author removes the review tags (optional) and runs `ci:full`; then round 3 checks that head and its three systems, and the coordinator gives the merge go.
