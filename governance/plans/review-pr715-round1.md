# Review PR #715, round 1 (batch B-P3, #693 and #694)

Thread: review-plugins-b-p2 (Opus 5.5), the reviewer of #676 and #690. Head reviewed: bafda4d (base b00002d). Date: 2026-11-20.
**Critical: yes** (CRIT-01: the safety mechanism of the text-step plugin interface; `risk:high` set). Plan `plans/textprep-b-p3-plan.md`, approved as D-861.

**Verdict: approved** (0 must-fix, 1 should-fix, 3 notes). S1 is fixed in one fix commit, which round 2 checks, or deferred to an Issue (REV-01). The three-system `ci:full` run 44829824327 is green on bafda4d.

## Verified

- (1) Scope: `src/sci2audio/textprep/plugins.py`, `src/sci2audio/textprep/runner.py` (the `PluginError` import and the three-line `said`), `tests/unit/broken_text_plugins.py`, the new `tests/unit/test_textprep_plugin_isolation.py`, `tests/unit/test_textprep_plugins.py`, `docs/plugins.md` and `CHANGELOG.md`. Nothing else changed. `sci2audio.textprep.api` is untouched, and `PluginError` lives in `plugins.py` only. Labels `risk:high`, `lane:textprep`, `lane:docs`. No licence item.
- (2) T1 covers what the coordinator listed. It has 14 cases (id, languages, the factory's result, category and stage through a `__class__` liar, `Exception`, `SystemExit` with a traced code, `BaseException`, the returned list, an `Edit` subclass, traced offsets, traced texts, an object planted in the document copy, one planted in the context). It runs each case on 3 paths (non-strict, strict with `traceback.format_exception`, and `JobRunner.run_script` with both reports). It asserts that every recorded thread name starts with `loading text step ` or `text step `. `test_the_tracer_records_the_worker_threads` makes sure the tracer records anything at all.
  - Base check: with `src` checked out at b00002d, the new tests give 39 failed and 10 passed. The 10 are the 9 id, languages and factory-result cases, which #690 already guards, and T7, which guards against rejecting too much. This matches the PR body.
- My own hostile probes at bafda4d (`timeout=0.3`):
  - an `Exception` whose `__str__`, `__repr__` and `__format__` block: "took longer than 0.3 s" after 0.34 s, nothing outside a worker;
  - `SystemExit` with a code whose `__repr__` blocks: the same, 0.31 s;
  - a list subclass whose `__iter__` and `__del__` record their thread: both ran in "text step rec-list";
  - an object that fakes `isinstance(x, Edit)` through `__class__`: rebuilt from plain values, and its `__del__` ran in the worker;
  - an `Exception` whose `__str__` returns a str subclass: the problem message is an exact `str`.
  - The one gap is S1.
- (3) The job's thread gets only plain values:
  - `_run` copies the document and the context, calls `find`, turns `Exception`, `SystemExit` and `BaseException` into `_Failure` text built in the worker, compares with `bool(...)` in the worker, and rebuilds the edits. `_plain_edits`, `_plain_span`, `_whole` (`int.__index__`) and `_plain_text` (`str.__str__`) require an exact `EditKind`, so `Edit(...)` checks plain values. Edit's fields are complete (span, kind, reason, step, replacement, to).
  - `find` raises a fresh `PluginError`/`StepError` outside any `except`; the timeout's `StepError ... from None` carries only `_TimedOut` (our thread object) as its suppressed context.
  - `_in_worker` turns Ctrl+C into a flag and raises a fresh `KeyboardInterrupt`.
  - `_loaded` lets the `_Rejected`, its cause and its frames die in the worker.
  - The runner's `_proposed` reads only the rebuilt values.
  - The step object's own lifetime is the documented limit.
- (4) T2 to T7 exist under the node IDs in the plan and in the PR body's "Tests promised in the plan". T6 and T7 cover #694; the key is the distribution plus the top-level package (`plugins.py:145`). Its worker is checked with `is_alive()`, so a later entry point loads normally once the hung import has finished.
- (5) The #676 and #690 tests are unchanged: the diffs of `test_textprep_plugins.py` and `broken_text_plugins.py` are additions only, and `test_app_plugins.py`, the conformance tests and `test_the_public_loader_is_unchanged` (which pins `load_plugin_steps` and `api.__all__`) are not touched. All of them pass.
- (6) `docs/plugins.md` (:99, the "Not loaded" and "Failing at run time" lists, the context copy) and the two CHANGELOG Fixed lines (#693, #694) describe the code, except the overclaim in S1. The PR body names both behaviour changes accepted in D-861.
- (7) Local, macOS M4, fresh worktree at bafda4d: ruff check clean, ruff format --check clean (389 files), lint-imports 3 kept, deptry clean, fast suite `-k "not espeak"`: 8718 passed, 6 skipped, 6 xfailed.
- Comments give the reason. No narrating comment and no review tag.

## Findings

### S1 (should-fix): a planted object in a reference cycle is dropped in the job's thread (kind unguarded-plugin-code)
Code: `src/sci2audio/textprep/plugins.py:424-455` (`_run`). Claims: `docs/plugins.md:99` ("Every object your plugin hands over stays in that thread") and the module docstring at `plugins.py:21` ("No object of the plugin's leaves a worker"). The copies and the plugin's results are dropped in the worker by reference counting. An object in a reference cycle, though, is freed only by the cyclic garbage collector, and that runs in whichever thread triggers it, usually the job's.
- Probe: `find` plants `Cyclic()` (with `self.me = self` and a `__del__` that records its thread) in `document.blocks[0].text`. Its `__eq__` ran in "text step cyclic", but its `__del__` ran in MainThread at the next `gc.collect()`.
- A `__del__` that blocks or raises there runs outside the time limit and outside any `try`; an exception in `__del__` is only printed, but a block hangs the job.
- T1 does not catch this: its traced objects have no cycles, and the fixture's `gc.collect()` runs before `CALLS.clear()`.
- The same holds for an exception object that the plugin put in a cycle.

Fix, either of:
- (a) in `_run`, drop the copies and the plugin's results and then call `gc.collect()` in the worker before returning. That frees the cycles there, under the limit; the cost is one collection per plugin per document, to be measured against the 60 s budget. Add a T1 case or a test that plants a self-referencing traced object, runs, calls `gc.collect()` in the test and asserts that `__del__` was recorded in a worker;
- (b) if (a) costs too much, name the limit in `docs/plugins.md:99` and the module docstring next to the step-object limit: an object in a reference cycle is freed wherever Python's collector runs.

(a) removes the gap; (b) only states it.

### N1 (note): T6's timing margin
`tests/unit/test_textprep_plugins.py:283`: the budget is 0.9 s against a 0.5 s limit, so a slow machine has 0.4 s for its overhead. The message assertion ("'hanging-import'" in the second problem) already proves that the second entry point did not wait. A limit of 1.0 s with a budget of 1.8 s would keep the "one wait, not two" boundary with more room. It passed on three systems; no change asked.

### N2 (note): a strict run shows a plugin's error with its type now
`runner.py:151`: in a strict run, `{error}` of a `PluginError` is "ValueError: boom", where it used to be "boom". Strict runs are for tests only, and no test pins the old text. The PR body does not name it among the behaviour changes; worth a word in the KB entry.

### N3 (note): #694 is keyed on the top-level package
While `pkg.a`'s import hangs, an entry point in `pkg.b` of the same distribution is left out at once, even if `pkg/__init__.py` imports fine and `pkg.b` would load. D-861 chose this, and the message names the first entry point. `docs/plugins.md:123` says "the same top-level module", which matches.

Handoff (THR-07): goal: PR #715 to merge. Done: round 1 approved with S1 (cyclic garbage freed in the job's thread). Next: the author fixes S1 (a or b) in one commit or defers it to an Issue. Round 2 checks that diff and Linux CI, and the final head needs a green three-system run before merge.
