# Answer to review round 1 of PR #690 (batch B-P2, #684)

Thread: plugins-b-p2 (Opus 5.5 high). Reviewed head: f7d8898. Fix commit: 0c78cc1, the only commit of this round. Report answered: `plans/review-pr690-round1.md` (044b6a4).

## Fixed

- **M1: the checks left in the caller's thread ran plugin code, unguarded and with no time limit** (kind unguarded-plugin-code). The fix is in `src/sci2audio/textprep/plugins.py`:
  - **The checks move into the worker.** `step_problems`, the entry-point-name check and the built-in-id check now run inside `_made`, in the loading worker and inside its `try`. An id whose `repr` raises becomes `_Rejected` ("failed while its attributes were read: RuntimeError: no repr"). An `api_version` whose `!=` blocks meets the load limit ("took longer than 0.2 s to load; left out"). `taken` is only read in the worker. The messages are unchanged, and `_step` is now only the worker call with its time limit.

    This departs from the plan text, which put those checks in the caller's thread ("they run no plugin code", which was wrong). It stays within D-845, which put the attribute reads under the same worker-thread guard.
  - **The root of this kind (its second time, after #676 M1):** once the checks pass, the guard replaces the plugin's values with plain built-in copies (`keep_plain_copies`). `id` becomes a `str`, `languages` a `tuple` of `str`, and `api_version` becomes `TEXT_STEP_API`, which `step_problems` just found equal.

    So after loading, the caller and the runner hash, sort, show and compare only plain values; no plugin method runs on the start-up path. Before the fix, the caller's `sorted(found)` and `found.setdefault(step.id, …)` would run a str subclass's `__lt__` and `__hash__` at start-up. It also removes most of N1 (`handles`, the thread name and the registry now see plain values); the rest of N1 is #693.
  - **Tests**, each failing on f7d8898:
    - `test_a_broken_plugin_is_a_problem_and_the_others_still_load[entry13-RuntimeError: no repr]` (a non-str id with a raising `repr`);
    - `test_a_plugin_whose_version_check_hangs_is_left_out` (`__ne__` blocks on `HANG`; the plugin is left out in under 3 s);
    - `test_a_plugin_s_id_and_languages_are_kept_as_plain_copies` (a str subclass whose `__hash__` and `__lt__` raise; it loads, and its `id`, `languages` and `PluginInfo.step` are plain `str`).

## Notes

- **N1** (copied values still reach plugin code at run time): filed as **#693** (v1.4, lane:textprep, risk:high). It covers what is left after the plain copies of M1: comparing a copy in which the plugin planted an object, and the edits `find` returns, both checked in the job's thread.
- **N2** (several entry points in one hanging module each wait the full limit): filed as **#694** (v1.4, lane:textprep, risk:low).
- **N3** (a Fixed line for a feature that has not been released): no change. The coordinator asked for the Fixed line (B-P2 brief, step 3); folding it into the Added line ("takes longer than 30 s to load or 60 s per document") is a release-time edit.
- **N4** (Ctrl+C on Windows during a hanging load): no change. It is the same as `find`'s 60 s guard. The docs do not describe Ctrl+C; if they ever do, they should say this.

## Checks at 0c78cc1 (macOS M4)

- `ruff check`, `ruff format --check`, `lint-imports` (3 kept) and `deptry`: all clean.
- The plugin, app and docs tests: 80 passed.
- Fast suite `-m "not slow and not benchmark and not browser" -k "not espeak"`: 8593 passed and 2 failed, `tests/unit/test_core_properties.py::test_edits_and_chunks_round_trip` and `::test_a_document_that_loses_an_item_is_refused`.
  - Both failed on Hypothesis's `too_slow` health check ("only generated 5 valid inputs after 1.48 seconds") while the machine was loaded: the run took 12.9 min against 10.3 min for the same suite earlier today.
  - Both passed when run alone (2 passed in 1.1 s).
  - This PR does not touch `core`, `core_strategies.py` or those tests, and CI on Linux is the check that counts.
  - It is their first failure seen, so no quarantine (D-374: twice, with no code cause).

Linux CI only this round; the main merge (c4c2de8, #691) and the final `ci:full` run come after round 2 is approved. The branch is frozen.
