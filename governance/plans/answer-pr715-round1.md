# Answer to review PR #715, round 1

Thread: textprep-b-p3. Review read: `plans/review-pr715-round1.md` (6ca361d). One fix commit, c79069d, on bafda4d. Decisions per the coordinator's message: S1 both (a) and (b); N1 0.8 s if safe; N2 in the PR body; N3 no change (D-861).

## S1, fixed by (a) and (b)

- **(a)** `src/sci2audio/textprep/plugins.py`, `_in_worker.work()`: after the call returns or fails, the worker runs `gc.collect()`. The call's frames, copies, results and exceptions are gone by then, so whatever they left in reference cycles is freed in the worker, under the time limit. The collection sits in `_in_worker`, so it covers both `find` and loading (`_loaded`): a factory can leave cycles too. The `_in_worker` docstring says so.
  - Cost, measured on the M4 with the largest corpus paper and the app and web modules imported (about 105,000 tracked objects): 13.9 ms per collection, once per plugin per document. The guard's benchmark goes from 23.9 ms to 36.4 ms per plugin and document. `docs/baseline.md` gets a row and a sentence saying what the guard now does. That is far inside the 60 s budget.
  - Remaining race, not closed: the cycle becomes garbage when the call's frame ends, and the worker's `gc.collect()` follows at once. An automatic collection triggered by another thread in that gap would free it there. The job's thread is blocked in `join` and allocates nothing, so only an unrelated thread (the server's) could, in a window of microseconds.
  - Test (new, failing on bafda4d with `('__del__', 'MainThread')` for both parameters): `tests/unit/test_textprep_plugin_isolation.py::test_an_object_in_a_reference_cycle_is_freed_in_the_worker`, parametrised over `CyclicPlantStep` (a self-referencing traced object planted in the copy) and `CyclicErrorStep` (an exception that refers to itself). The test runs the plugin, calls `gc.collect()` itself, and asserts that `__del__` was recorded and that every record is in a worker.
- **(b)** The module docstring and `docs/plugins.md:99` now state exactly what is not covered: what outlives a call. The step object lives as long as the job's steps, and whatever the plugin keeps on it or in its module's globals is freed wherever that is dropped, so a `__del__` there may run in the job's thread. The docs tell plugin authors to keep finalizers out of what they hold on to.

## N1, tightened

`tests/unit/test_textprep_plugins.py::test_entry_points_of_one_hanging_module_wait_one_limit_not_one_each`: the bound is now 0.8 s, with a comment that two waits would be 1.0 s. Measured locally over 10 runs: 0.506 to 0.534 s, so the 0.3 s margin is more than ten times the overhead. If a CI system ever comes close, the reviewer's alternative (limit 1.0 s, bound 1.8 s) keeps the same boundary.

## N2, named

The PR body's behaviour-change paragraph now says that a strict run's error text includes the plugin's error type ("text step 'raising' failed: ValueError: boom", was "… failed: boom"). Strict runs are for tests, and no test pins the old text.

## N1, second fix commit 0710344

Tightening to 0.8 s failed on Linux CI (0.83 s on c79069d). By the coordinator's decision the test is now structural: the second entry point's exact problem text ("left out: 'hanging-import' of the same package 'hanging_on_import' took longer than 1 s to load") and the absence of a "loading text step hanging-too" worker among the threads started during the call prove that it never waited, while the first entry point's worker is still alive. The time bound remains as a safety net only: the limit is 1.0 s, the bound 1.6 s, and two waits would be 2 s. Five runs of the plugin test files in random order pass locally. My 0.8 s bound was the mistake: ten local runs say nothing about a loaded CI runner.

## N3

No change: the top-level-package key is D-861's choice.

## Promised tests

The PR body's `## Tests promised in the plan` adds `tests/unit/test_textprep_plugin_isolation.py::test_an_object_in_a_reference_cycle_is_freed_in_the_worker`.

## Checks at c79069d

ruff check and format clean, lint-imports 3 kept, deptry clean; fast suite `-k "not espeak"` (macOS M4): 8720 passed, 6 skipped, 6 xfailed. Benchmark `test_benchmark_the_guard_on_the_largest_paper`: mean 36.4 ms.

Handoff (THR-07): goal: PR #715 to merge. Done: round 1 answered with one fix commit. Next: round 2 on 0710344 (Linux CI), then the coordinator's go for the main merge and the final three-system run.
