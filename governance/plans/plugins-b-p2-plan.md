# Plan: batch B-P2, a time limit for loading a text-step plugin (#684)

Thread: plugins-b-p2, the textprep/core lane's implementation thread on Opus 5.5 high. It is the same thread that wrote B-P1 and passed the fitness check. Written 20 Nov 2026.

**Critical (CRIT-01):** this is a bug in a safety mechanism of the text-step plugin interface, so the PR is labelled `risk:high`. No code is written before the coordinator approves this plan.

Read first: #684, audit finding F1 (`plans/audit-batch-2026-11-20.md`), `src/sci2audio/textprep/plugins.py` at `origin/main` caecf7a, D-836 and D-844.

## 1. The cause

`_step()` runs the plugin's load-time code in the caller's thread with no time limit:

- `point.load()`, which imports the plugin's module;
- the factory `made()`;
- the attribute reads in `_GuardedStep.__init__`.

`JobRunner()` calls `installed_steps()` while it is being built, and every CLI command (`CliEnv.runner`) and the server build one at start-up. So a plugin whose import, factory or attributes hang stops every command before it prints anything. Only `find` runs behind the worker-thread guard.

## 2. The change (`src/sci2audio/textprep/plugins.py` only)

- **The whole of `_step`'s plugin part runs in a daemon worker thread:** the import, the factory, the `isinstance` and version checks, and building the guard. The loader waits for it with `join(load_timeout)`. This is the same thread-and-`join` pattern as `find`, written once as a small private helper `_in_worker(call, timeout) -> result`. `_GuardedStep.find` uses the helper too, so there is one implementation of the guard.
- **What the outcome becomes:**
  - The thread is still running at the limit: `PluginProblem("took longer than 30 s to load; left out")`. The thread is abandoned, as with `find`, and the next entry point loads.
  - `_Rejected`, or any `BaseException` except `KeyboardInterrupt`: a `PluginProblem`, as today.
  - `KeyboardInterrupt` in the worker is re-raised in the caller's thread, so Ctrl+C still stops start-up. A real Ctrl+C reaches the main thread while it waits in `join`, so it stops start-up anyway.
- **What stays in the caller's thread:** the checks that read only the guard's copied attributes (`step_problems`, the name and id checks) and `_distribution`, which reads only the metadata files. None of them runs plugin code.
- **Entry points load one after another, each with its own limit.** If one hangs, start-up waits `load_timeout` once for it, and every other plugin still loads.
  - Not chosen: loading all entry points in parallel under one shared deadline. That loads faster but in a non-deterministic order, and two imports of a shared module would contend for its import lock.
  - Not chosen: one deadline for all of them, so the plugins after a hanging one would get no time.
- **Public surface:** `sci2audio.textprep.api` is unchanged (#684 criterion 3). `load_plugin_steps` keeps its signature and uses the module constant. The non-public `installed_steps` gets a keyword `load_timeout: float | None = None`; `None` reads `PLUGIN_LOAD_TIMEOUT` when the function is called, so a test can set the constant for the `JobRunner()` that the CLI builds.
- **One behaviour change to name:** a plugin's import and factory now run off the main thread. A plugin that calls `signal.signal` at import fails with `ValueError` and is rejected with that message. `find` already runs off the main thread, so a plugin cannot rely on the main thread anyway. `docs/plugins.md` says so.

## 3. Open choice: the limit

- **Recommended: a separate `PLUGIN_LOAD_TIMEOUT = 30.0`** (seconds, per entry point; a module constant in `textprep/plugins.py`, not a user setting).
- Loading sits on the start-up path of every command, so a hanging plugin delays every command by the full limit. That argues for a shorter limit than `find`'s 60 s, which is a budget per document of a whole job.
- Still, the limit must leave room for a plugin that imports a heavy library on a cold disk. A torch or spaCy import takes a few seconds on an M4, and longer on a slow Windows machine with a virus scan. 30 s covers that.
- The alternative is the same 60 s as `find`: one number to explain, but a minute of silence at every start while a broken plugin stays installed.

## 4. Tests written first (they fail on caecf7a)

The fake plugins block on a `threading.Event` with a 5 s wait, so a test fails in about 5 s rather than hanging. Each test sets the event when it ends. The new fixtures go into the existing `tests/unit/broken_text_plugins.py`, plus a module `tests/unit/hanging_on_import.py` whose import blocks.

- T1: a plugin whose import blocks is left out with "took longer than 0.2 s to load", the plugin after it still loads, and `installed_steps` returns in under 3 s. Node ID: `tests/unit/test_textprep_plugins.py::test_a_plugin_whose_import_hangs_is_left_out_and_the_others_still_load`
- T2: a factory that blocks is left out in the same way. Node ID: `tests/unit/test_textprep_plugins.py::test_a_plugin_whose_factory_hangs_is_left_out`
- T3: an attribute (a property) that blocks is left out in the same way. Node ID: `tests/unit/test_textprep_plugins.py::test_a_plugin_whose_attributes_hang_is_left_out`
- T4: `KeyboardInterrupt` raised by a plugin's import in the worker reaches the caller. Node ID: `tests/unit/test_textprep_plugins.py::test_ctrl_c_while_a_plugin_loads_is_not_swallowed`
- T5: `load_plugin_steps()` keeps its signature (`inspect.signature` pinned) and `api.__all__` is unchanged (#684 criterion 3). Node ID: `tests/unit/test_textprep_plugins.py::test_the_public_loader_is_unchanged`
- T6: with a real dist-info whose entry point hangs and `PLUGIN_LOAD_TIMEOUT` set to 0.2, `JobRunner()` returns in under 3 s and its `steps.problems` names the plugin (#684 criterion 2). Node ID: `tests/unit/test_app_plugins.py::test_a_runner_is_made_well_before_a_hanging_plugin_would_load`
- T7: the same setup through the CLI: `sci2audio script` exits 0 and prints the plugin's "plugin not loaded: took longer than … to load" warning, and the report's problems name it. Node ID: `tests/unit/test_app_plugins.py::test_the_command_line_names_a_plugin_that_hung_while_loading`

All existing plugin, app, docs and conformance tests must stay green unchanged. This includes the parametrised rejection test, the M1 and S1 tests of #676 and the guard tests of `find`; they show that moving the guard into `_in_worker` changes no outcome.

## 5. Docs and CHANGELOG

- `docs/plugins.md`, "Not loaded": a new bullet, "loading it (import, factory, attributes) takes longer than 30 seconds". A sentence says that a plugin's code runs off the main thread.
- CHANGELOG, Unreleased, a **Fixed** line: "A text-step plugin whose import or set-up hangs no longer stops sci2audio from starting: loading gives up after 30 s and lists the plugin as a problem (#684)."
- Both are lane:docs files, which any lane may update (LANE-03). Nothing else outside `src/sci2audio/textprep` and its tests changes: no app, cli or web file, and no core file.

## 6. Checks, size, labels

- `lint-imports` and `deptry` stay green, because only the standard library (`threading`) is used, which is already imported. No new dependency, so the licence note is "none".
- The local runs use `-k "not espeak"`, one `uv run` at a time.
- Size: about 40 lines in `plugins.py` (the helper, and `_step` split into a worker part and a checking part), about 150 lines of tests and fixtures, and 4 lines of docs and CHANGELOG.
- Labels: `lane:textprep`, `lane:docs`, `risk:high`.
- Branch `claude/plugins-b-p2`, taken from `origin/main` caecf7a in its own worktree, so the shared checkout `~/Projekte/sci2audio` is not switched.

## 7. Order after approval

1. Write T1 to T7 and show that they fail on caecf7a.
2. Make the change in `plugins.py`.
3. Update the docs and the CHANGELOG.
4. Run the fast checks.
5. Open the PR (title `textprep: a hanging text-step plugin no longer stops sci2audio from starting (#684)`) and add `governance/ledger/prs/pr-<N>.yaml`.
6. Once Linux CI is green, merge main into the branch with a merge commit, add `ci:full`, and report when all three systems are green. Then remove the label.

Handoff (THR-07): goal: #684 in one critical PR. Done: plan written. Next: the coordinator decides Q (30 s or 60 s), then tests first.
