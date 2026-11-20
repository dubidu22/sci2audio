# PR #689 review, round 2 (head d4b2111)

Reviewer: review-web-b-w2, Opus. 20 Nov 2026. Plan: plans/web-b-w2-plan.md §2 (D-847). Author's answer: plans/answer-pr689-round1.md (governance d66b24c).
Critical: **yes** (unchanged from round 1).
Verdict: **approved** (0 must-fix, 0 should-fix, 3 notes). Merge still needs the coordinator's go and, as a critical PR, `main` merged in and a green three-system run on the final head (CRIT-02, D-580).

## Round 1 findings

- **S1 fixed at the root.** `CliEnv.runner` is `JobRunner | None = None` (`cli.py:143`); `CliEnv.job_runner(settings)` (`cli.py:151-159`) returns an injected runner as given, `JobRunner(BUILT_IN_STEPS)` when `settings.plugins` is false (never touches the entry points), else makes `JobRunner()` once and keeps it. All three job call sites (`script` `cli.py:715`, `convert --with-script` `:797`, the audio thread `:829`) go through it; no other `env.runner` use is left, and `ui`/`listen` keep the server's own runner. Test `test_cli_script.py::test_no_plugins_never_imports_a_plugin`: the counting point replaces `plugins.entry_points`, the very name `load_plugin_steps` calls (`textprep/plugins.py:25,105`); 0 loads under `--no-plugins`, 1 without, and the on-run's "Salt and pepper" can only come from that point (no plugin is installed), so the fixture really intercepts the load path. `test_a_command_that_runs_no_job_imports_no_plugin` (`voices`, 0 loads). Mutation check: dropping the `--no-plugins` branch of `job_runner` makes the first test fail.
- **S2 fixed.** `app/config.py:27`: "every JobSettings field but the chosen chapters and the plugin switch (#667)".
- **N2 done.** `JobRunner.steps_for(settings, steps)` filters plugin steps from given steps too; `run_script` and `run_audio` both call it; steps no plugin added are kept. Test `test_app_job.py::test_plugins_off_also_filters_steps_given_to_the_job` (built-in reading, no `plugins` in the report); mutation (skip the filter for given steps) makes it fail.
- **N1, N3 accepted as is; N4, N5 noted**: accepted. N4: the Firefox shard 2/2 passed on d4b2111.

## Checks

- **Fix-commit diff 13ec9c2..d4b2111**: 5 files (`app/config.py`, `app/runner.py`, `cli.py`, `tests/unit/test_app_job.py`, `tests/unit/test_cli_script.py`), only the three answers above; nothing else.
- **Goldens**: over the whole PR the only golden diff is still `tests/unit/__snapshots__/test_cli_golden.ambr` (the two `--no-plugins` lines); nothing under `tests/corpus` or `tests/regression`.
- **PR body**: the promised-tests list adds the three round-1 tests by node ID; the "What changes" text names the lazy runner and the N2 filter.
- **Local run** (fresh worktree /tmp/review-689 at d4b2111, macOS): ruff, ruff format (384 files), lint-imports (3 kept, 0 broken), deptry green; `pytest -m "not slow and not benchmark and not browser" -k "not espeak"`: 8600 passed, 6 skipped, 6 xfailed, 0 failed (496 s). The author's `test_the_guard_changes_no_edit` deadline miss under `-n auto` did not occur in this serial run.
- **CI on d4b2111 (Linux, pull_request)**: `CI passed`, `tests (ubuntu-latest)`, lint and layers, licences, security, ZAP, CodeQL, governance pr checks, both Chromium shards green; Firefox and WebKit shards (reported only) green.

## Notes

- **N6.** The new `cli.py:141-142` comment ends "(#667 review S1)" and a test docstring "(#667 review N2)". The sentences say why, so not a narrating-comment finding; "review S1/N2" points at a working file outside the product repo, though, and could be cut to "(#667)" when `main` is merged in. Optional.
- **N7.** For `convert`, the plugins are now loaded on first use inside the audio worker thread, not at start-up in the main thread. A plugin that calls `signal.signal` at import would now be rejected (with a problem in the report) under `convert` but load under `script`. No such plugin is known; mentioned only.
- **N8.** Before merge: merge `main` into the branch (merge commit, no rebase), re-check the diff, then `ci:full` on that head and check `tests (macos-latest)` and `tests (windows-latest)`, then `ledger_tool.py gate 689` (MRG-01).

## Handoff (THR-07)

- Goal: PR #689 (B-W2 PR B) to merge, then PR A.
- Done: round 2 at d4b2111, approved.
- Next: on the coordinator's go, after `main` is merged in and the three-system run is green on that head, gate and squash-merge pinned to it.
