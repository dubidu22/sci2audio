# PR #689, answer to review round 1 (head 13ec9c2 → d4b2111)

Author: B-W2 web/app implementation thread, Opus 5.5. 20 Nov 2026. One fix commit: d4b2111.

## Should fix

- **S1 fixed in this PR, at the root.** `CliEnv.runner` is now `JobRunner | None = None`, and `CliEnv.job_runner(settings)` makes the runner when a job starts. With `settings.plugins` false it makes `JobRunner(BUILT_IN_STEPS)`, which never touches the entry points. Otherwise it makes `JobRunner()` once and keeps it. An injected runner (tests) is used as given. All three job call sites in `cli.py` (`script`, `convert`, `convert --with-script`) go through it. As a side effect, a command that runs no job (`voices`, `clean`, `listen`, `ui`) no longer imports plugins at start-up either; the server keeps its own runner.
  - `tests/unit/test_cli_script.py::test_no_plugins_never_imports_a_plugin`: a counting entry point is loaded 0 times under `--no-plugins` and once without the flag (the script then reads "Salt and pepper").
  - `tests/unit/test_cli_script.py::test_a_command_that_runs_no_job_imports_no_plugin` (`voices`).
- **S2 fixed.** The `KEPT` comment in `app/config.py` now names both the chosen chapters and the plugin switch as not kept.

## Notes

- **N1 accepted as is** (the `docs/plugins.md` bullet).
- **N2 filtered.** `JobRunner.steps_for(settings, steps)` now drops plugin steps from the steps given too, not only from the runner's own. So a job with plugins off never runs a plugin, and the report and record can't say "off" beside a plugin's edits; `run_script` and `run_audio` both use it. Steps a caller passes that no plugin added (test fakes) are kept. Test: `tests/unit/test_app_job.py::test_plugins_off_also_filters_steps_given_to_the_job`.
- **N3 accepted** (no `convert` plugin line, pre-existing; the choice is in `audio.json`).
- **N4 noted.** Firefox's `test_resume_of_a_paused_replace_never_asks_to_replace_again` is a first occurrence, not quarantined. D-374 applies if it fails again.
- **N5 noted.** After round-2 approval: merge main (c4c2de8 or later) with a merge commit, then the final `ci:full`.

## Local checks (macOS, `-k "not espeak"`)

- ruff, format, lint-imports (3 kept) and deptry: clean.
- Fast suite: 8599 passed. One failure: `tests/unit/test_textprep_plugins.py::test_the_guard_changes_no_edit` hit Hypothesis `DeadlineExceeded`, 342 ms against 200 ms, under `-n auto`. The test and its code are untouched by this PR, and it passed 3 of 3 runs alone. It is a timing flake under load, reported here and not changed.

## Handoff (THR-07)

- Goal: PR #689 to merge, then PR A.
- Done: round 1 answered in d4b2111.
- Next: review round 2; after approval, merge main, run `ci:full`, merge; then PR A from main.
