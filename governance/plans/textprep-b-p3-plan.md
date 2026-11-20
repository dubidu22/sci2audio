# Plan: batch B-P3, no plugin code runs outside the guard (#693, #694)

Thread: textprep-b-p3, the textprep lane's implementation thread on Opus 5.5 high. Written 20 Nov 2026, on main b00002d.

**Critical (CRIT-01):** a safety mechanism of the text-step plugin interface. One PR, `lane:textprep`, `risk:high`, for #693 and #694. Both change only `textprep/plugins.py` and its tests, and #694 is about 20 lines, so they are reviewed together. No code before the coordinator approves this plan.

Read: #693 (with its audit paragraph), #694, `textprep/plugins.py`, `textprep/runner.py`, `app/report.py`, the B-P2 plan and the #690 reviews and answer, audit 2026-11-20b F1 and its META-03 proposal, D-836, D-844, D-845, D-852, D-858.

## 1. The cause

`_in_worker` hands plugin objects back to the job's thread, and the guard and the runner then use them there:

- `_GuardedStep.find` makes the copy `given` in the job's thread, compares it there (`given != document`, `plugins.py:360`) and drops it there (`__del__` of a planted object).
- It re-raises the plugin's own `Exception` (`:353-354`); the runner formats it with `{error}` (`runner.py:151-152`). The `SystemExit` and `BaseException` branches format with `error.code!r` and `_said` in the job's thread (`:356`, `:358`).
- The runner checks the returned list and its edits in the job's thread (`runner.py:_proposed`): `isinstance`, iteration of a list subclass, `edit.step != step.id`, `check_edits` on int and str subclasses.
- Not in #693 but the same kind: the guard passes the job's own `StepContext` to the plugin. A plugin can plant an object in it with `object.__setattr__`; the runner then compares `context.language` in `handles` for every later step, in the job's thread. And `step_problems` checks `category` and `stage` with `isinstance`, which an object whose `__class__` is a property passes; the runner then hashes it (`step.category in switched_off`).
- On the load side, `_made` raises `_Rejected(...) from error`. The `_Rejected` crosses to the job's thread with the plugin's exception as its cause and the worker's frames (with the factory's result in their locals) in its traceback.

## 2. The change

One rule: **what `_in_worker` returns is built-in values or a plain failure message; it never re-raises an exception object from the worker.** All in `src/sci2audio/textprep/plugins.py` unless named.

1. `_in_worker(call, timeout, name)` keeps its signature. The worker catches `KeyboardInterrupt` and sets a flag; the caller raises a fresh `KeyboardInterrupt()`. Any other `BaseException` that reaches `work()` becomes a `_Failure` message built there with `_said` (a bug of ours or a path missed; the run still goes on). `_TimedOut` carries the worker thread (for #694).
2. A small frozen `_Failure(message: str, raised: bool)`: `raised` is True when the plugin's `find` raised an `Exception`, so the runner shows its text as today ("ValueError: boom", pinned by `test_a_failing_plugin_keeps_its_own_error_in_the_problem`).
3. **Run time.** `_GuardedStep.find` runs one worker function, `_run(step, document, context)`, which inside the worker:
   - deep-copies the document and the context (the context is new: one copy per call, like D-844's document copy);
   - calls `find`; an `Exception` becomes `_Failure(_said(error), raised=True)`, `SystemExit` `"called SystemExit(<code>)"`, another `BaseException` `"raised …"` (today's texts), each built in the worker;
   - compares the copy with the document and drops it there;
   - rebuilds the edits from plain values: the list must be a `list` (subclass allowed, as today), each item an `Edit` (as today, same message "find must return a list of Edit, got …"); `block`, `start`, `end` must be ints (`issubclass(type(x), int)`) and are copied with `int.__index__`, which calls no override; `reason`, `step`, `replacement` must be strs and are copied with `str.__str__`; `kind` must be an `EditKind` member exactly; `to` is `None` or rebuilt the same way. A value of another type is a readable failure ("find returned an edit whose start is not a whole number, got float"). `Edit(...)` re-checks the rebuilt edit (core's own code on plain values).
   - The job's thread gets a `list[Edit]` of plain `Edit`/`Span`/`int`/`str`/`EditKind` objects or a `_Failure`. It raises `PluginError(message)` for `raised=True`, else `StepError(message)`, outside any `except` block, so neither carries a cause or context.
   - The time limit covers `find`, the comparison and the rebuild together: a planted `__eq__` or an exception `__str__` that blocks is "took longer than 60 s; its edits are left out", as a slow `find` is today (#693 criterion 1 "or under the same time limit").
4. `PluginError(StepError)`: a step error whose message is what the plugin raised. Defined in `plugins.py`, **not** in `sci2audio.textprep.api`. The runner (`textprep/runner.py`, 3 lines) records `str(error)` for a `PluginError` and `"{type}: {error}"` for everything else, as today. The runner's checks in `_proposed` stay where they are; they now read only plain values.
5. **Load time.** `_made` stays as it is (it raises `_Rejected` with a plain message); a wrapper in the worker turns `_Rejected` into a `_Failure`, so the exception, its cause and its frames die in the worker. `_step` raises a fresh `_Rejected(message)` in the job's thread.
6. `keep_plain_copies` also requires `type(category) is Category` and `type(stage) is Stage` and each language to be a `str`; otherwise a readable `_Rejected` with `step_problems`' wording: "languages must be a non-empty tuple of primary tags like 'en' or '*', got a Obj" (#690 round 2 N1). `step_problems` itself (the text-step interface's check, also used by `check_text_step`) is unchanged.
7. **#694.** `_load` remembers, for an entry point whose load timed out, its distribution and top-level package with the worker thread. A later entry point of the same distribution and top-level package, while that worker is still alive, is rejected at once: "left out: 'hanging-import' of the same package 'hanging_on_import' took longer than 30 s to load". Keyed on the distribution as well, so a plugin of another distribution that shares a namespace package is still tried. If the worker has finished meanwhile, the later entry point loads normally. The cause it removes: the hung worker holds the module's import lock, so the later import can only wait (REV-06).
8. Unchanged: `sci2audio.textprep.api`, `load_plugin_steps` (signature pinned), `installed_steps`' signature, `PLUGIN_TIMEOUT`, `PLUGIN_LOAD_TIMEOUT`, every problem text the #676 and #690 tests pin.

Known limit, written in `docs/plugins.md`: the step object itself lives as long as the job's steps (the `JobRunner`), so its `__del__` runs where they are dropped, at the end of the program. The isolation test does not trace `__del__` on the step object for that reason; it traces it on every object a run hands over.

Behaviour changes to name: a guarded **built-in** step that raised would now raise `PluginError` instead of its own type. No built-in step raises on any document (the textprep property tests), so `test_the_guard_changes_no_edit` keeps passing unchanged. A plugin edit whose `kind` is a plain `"remove"` string instead of `EditKind.REMOVE` is now a problem; the contract says `EditKind`.

## 3. Tests, written first (each fails or hangs on b00002d unless marked)

Tracer in `tests/unit/broken_text_plugins.py` (about 70 lines): `traced(base)` builds a subclass of `str`, `int`, `tuple`, `list`, `Exception`, `SystemExit`, `BaseException`, `Edit` or `object` whose dunders `__str__`, `__repr__`, `__format__`, `__eq__`, `__ne__`, `__hash__`, `__lt__`, `__bool__`, `__len__`, `__iter__`, `__index__`, `__int__`, `__getattr__`, `__del__` record `threading.current_thread().name` in `CALLS` and then answer as the base does. One hostile step class per case, made in its factory (so the traced objects are made in the loading worker or in `find`).

- T1 `tests/unit/test_textprep_plugin_isolation.py::test_no_plugin_object_is_touched_outside_a_guard_worker`, parametrised over the case (id, languages, the factory's result, category, stage, `Exception`, `SystemExit` with a traced code, `BaseException`, the returned list, an `Edit` subclass, the span offsets, the replacement text, an object planted in the document copy, one planted in the context) and the path (`run_steps` non-strict, `run_steps` strict with the error formatted by `traceback.format_exception`, and `JobRunner.run_script` writing the JSON and Markdown report). Every recorded thread name starts with `loading text step ` or `text step `; no exception but the strict run's `StepError` leaves; a case meant to fail ends with a problem for that step. The id, languages and factory-result cases already pass on b00002d (#690); the others fail.
- T2 `tests/unit/test_textprep_plugin_isolation.py::test_a_planted_object_whose_comparison_blocks_is_given_up` (#693 criterion 3): the run returns in under 3 s with "took longer than 0.2 s".
- T3 `tests/unit/test_textprep_plugin_isolation.py::test_an_offset_whose_index_raises_is_read_as_a_plain_int` (#693 criterion 3): the edit is accepted with plain int offsets, and `__index__` never ran in the job's thread.
- T4 `tests/unit/test_textprep_plugin_isolation.py::test_a_plugin_error_whose_str_blocks_is_given_up` (audit F1): an exception from `find` whose `__str__` blocks is a "took longer than" problem, and the run goes on.
- T5 `tests/unit/test_textprep_plugins.py::test_a_language_that_is_not_a_str_is_a_readable_problem` (#690 round 2 N1): an object whose `__str__` is `"en"` gives "languages must be a non-empty tuple of primary tags …", no "TypeError" or "descriptor". On b00002d the message is the raw TypeError.
- T6 `tests/unit/test_textprep_plugins.py::test_entry_points_of_one_hanging_module_wait_one_limit_not_one_each` (#694): two entry points in `hanging_on_import`, limit 0.5 s; loading takes under 0.9 s, the second problem names the first entry point, and the other plugin loads.
- T7 `tests/unit/test_textprep_plugins.py::test_a_hanging_package_does_not_hold_up_another_distribution` (#694): the same module under two distributions (lookalike entry points with a `dist`), so the second is tried, not rejected at once.

All existing tests in `test_textprep_plugins.py`, `test_app_plugins.py`, `test_docs_plugins.py` and the conformance suite stay unchanged and green; the new ones are additions only. Cost in the fast suite: about 2 s.

## 4. Docs and CHANGELOG

- `docs/plugins.md:99`: what runs in the worker exactly: the import, the factory, every attribute read, `find`, the comparison of the copy and the reading of the returned edits; what the job gets back is plain text and plain edits. The context is a copy too. A plugin that shares a package with one whose import hung is left out at once. The step object's own lifetime (the known limit above).
- CHANGELOG, Unreleased, **Fixed**: "A text-step plugin can no longer stop or hang a job through what its `find` returns or raises: the edits, the error and the document copy are read inside the guard, under its time limit (#693)." And: "Several text-step plugins in one package whose import hangs wait the load limit once, not once each (#694)."

## 5. Checks, size, labels

- Fast checks as CLAUDE.md item 5 with `-k "not espeak"`, one `uv run` at a time. Standard library only; licence note "none".
- Size: about 110 lines in `plugins.py`, 3 in `runner.py`, 70 of tracer, 220 of tests, 10 of docs and CHANGELOG.
- Labels `lane:textprep`, `lane:docs`, `risk:high`. Branch `claude/textprep-b-p3-ad2bb3` from main b00002d (its own worktree).
- `fixes_kinds: [unguarded-plugin-code]` in the ledger entry: T1 is the META-03 check for that kind.

## 6. Order after approval

1. Tracer and T1 to T7; show they fail on b00002d (T2 and T4 by their time bound).
2. The change in `plugins.py` and `runner.py`.
3. Docs and CHANGELOG, fast checks.
4. Open the PR `textprep: no plugin code runs outside the guard (#693)` with `Closes #693`, `Closes #694` and `## Tests promised in the plan` (T1 to T7 as above); ledger `ledger/prs/pr-<N>.yaml`.
5. One line to the coordinator at PR open, at green Linux CI, and with the head after `ci:full`.

Handoff (THR-07): goal: #693 and #694 in one critical PR. Done: plan written. Next: coordinator approval, then tests first.
