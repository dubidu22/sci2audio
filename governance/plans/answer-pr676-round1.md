# Answer to review round 1 of PR #676 (batch B-P1)

Thread: plugins-b-p1 (Opus 5.5 high). Reviewed head: 6f25cd4. Fix commit: 3e24d63, the only commit of this round. Report answered: `plans/review-pr676-round1.md`.

## Fixed

- **M1: a plugin whose attributes raise stopped sci2audio from starting.** Fixed in `textprep/plugins.py` `_step`.
  - What changed: every touch of plugin objects (the `callable` test, the factory call, `isinstance`, `_declares_version`) and building `_GuardedStep` now happen inside one guarded block. Any failure there becomes a `PluginProblem`: "failed while its attributes were read: …".
  - Why: the plugin's `id`, `languages`, `category`, `stage` and `api_version` are read exactly once, into the guard. `step_problems`, the name and id checks, `PluginInfo` and the runner then read only the guard's copies, never plugin code again.
  - Tests: `bad-property` (a `languages` property that raises) is added to the parametrised rejection test. `test_broken_installed_plugins_do_not_stop_the_command_line` installs a real dist-info with three broken plugins (bad property, a `BaseException` at import, a `BaseException` from the factory). `sci2audio script` then exits 0 and warns once per plugin. `CliEnv`'s default `JobRunner()` loads them.
- **S1: a `BaseException` subclass from a plugin still crashed loading or the run.** The loader (import, factory, attribute reads) catches `BaseException` and lets only `KeyboardInterrupt` through. The guard does the same at run time:
  - an `Exception` is re-raised as is, so the runner reports its type (N4 kept);
  - `SystemExit` becomes `StepError` as before;
  - any other `BaseException` becomes `StepError("raised <Type>: …")`;
  - a copy that cannot even be compared (an object whose `__eq__` raises) counts as changed: `StepError("left its copy of the document unreadable: …")`;
  - error messages are formatted through `_said`, so an exception whose `__str__` fails cannot escape either.

  Tests: `boom-import` and `boom-factory` in the rejection test; `BoomStep` and `UnequalStep` in the run-time test (left out, the run goes on) and in the strict test (raises `StepError`). `KeyboardInterrupt` still passes, which the existing test checks.
- **S2: distribution metadata was read outside the guard, through a deprecated lookup.** `_distribution` now uses `dist.metadata.get("Name")` and `.get("Version")` inside its own guard, and returns `("", "")` on any failure but Ctrl+C. Test: `test_a_distribution_without_metadata_loads_without_a_warning` (a dist-info without `METADATA`, under `warnings.simplefilter("error")`).
- **Docs:** `docs/plugins.md` ("Not loaded" and "Failing at run time") and the module docstring now say that any exception but Ctrl+C counts as a failure.

## Notes

- **N1** (`LoadedPlugins` and the keyword `reserved` under contract 1): no change. Both are part of `load_plugin_steps`' public signature; it is for the coordinator to record.
- **N2** (one copy per plugin call): no change. I do not write the decision log; it is for the coordinator and the KB thread to record as a Claude decision.
- **N3** (web jobs run plugins, the read-along does not, until #666): no change, accepted by D-836. #666 should land before the release that ships this.
- **N4** (an ordinary `Exception` is re-raised, not wrapped): kept as is.

## Checks at 3e24d63 (macOS M4)

- `ruff check`, `ruff format --check` (whole repo), `lint-imports` (3 kept) and `deptry`: all clean.
- `pytest -m "not slow and not benchmark and not browser"`: 8429 passed, 6 skipped, 6 xfailed. Four tests were deselected: the three espeak tests and `test_extraction_pdf_process.py::test_a_child_that_ends_without_a_result_is_named` (fixed on main by #677, not merged in here, as instructed).
- No browser run: nothing under `src/sci2audio/web/` changes.
- Linux CI only for this round (no `ci:full`).

Nothing is deferred, so no new issue. The branch is frozen until round 2.
