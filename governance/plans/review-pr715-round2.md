# Review PR #715, round 2 (batch B-P3, #693 and #694)

Thread: review-plugins-b-p2 (Opus 5.5). Heads reviewed: c79069d (the fix commit on bafda4d), then 0710344 (one test-only commit, addendum below). Date: 2026-11-21.
**Critical: yes** (CRIT-01, a safety mechanism of the text-step plugin interface). Answer read: `plans/answer-pr715-round1.md` (03c41d0).

**Verdict: approved** (0 must-fix, 1 should-fix, 1 note). S1 is a one-line test change. It can go in a commit before the `ci:full` run; round 3 then checks only that diff and the three systems. Or it can be deferred to an Issue (REV-01). Before merge: the main merge (9ad6d11) and a green three-system run on that head (CRIT-02, D-580).

## Round 1 findings

- **S1 fixed, both (a) and (b).**
  - (a) `_in_worker.work()` runs `gc.collect()` after the call has returned or failed, so the call's frames, copies, results and exceptions are already gone. It covers both `find` and loading.
  - Test: `test_an_object_in_a_reference_cycle_is_freed_in_the_worker[CyclicPlantStep|CyclicErrorStep]`, listed under "Tests promised in the plan".
  - Without the collect (I replaced that line with `pass` in the review worktree), both parameters fail with `('__del__', 'MainThread')`; with it they pass. This is my round-1 probe as a test.
  - The remaining race is microseconds wide: another thread would have to trigger a collection between the end of the call and the worker's collect. The answer names it; I accept it.
  - (b) The module docstring and `docs/plugins.md:99` now name the limit that is left: what outlives a call (the step object, what the plugin keeps on it or in its globals) is freed wherever it is dropped.
  - `docs/baseline.md`: the guard row goes from 23.9 ms to 36.4 ms per plugin and document, with about 14 ms for the collection, plus a sentence saying what the guard now does. Acceptable against the 60 s budget; see N1 for larger heaps.
- **N1:** first tightened to 0.8 s at c79069d, which Linux CI then broke (0.83 s). 0710344 replaces it; see the addendum and S1 below.
- **N2:** now named in the PR body's behaviour-change paragraph.
- **N3:** no change, per D-861.

## Verified at c79069d

- Diff bafda4d..c79069d: `plugins.py` (the `gc` import, the collect, the docstrings), `docs/plugins.md`, `docs/baseline.md`, the two cycle fixtures in `broken_text_plugins.py`, the new test, and the T6 bound. Nothing else.
- Local run (macOS M4, fresh worktree): ruff check and format clean (389 files), lint-imports 3 kept, deptry clean. Fast suite `-k "not espeak"`: 8720 passed, 6 skipped, 6 xfailed.

## Addendum: 0710344

- Diff c79069d..0710344 touches only `tests/unit/test_textprep_plugins.py::test_entry_points_of_one_hanging_module_wait_one_limit_not_one_each`.
- The test now checks the structure of the outcome:
  - the second entry point's full "left out: 'hanging-import' of the same package 'hanging_on_import' took longer than 1 s to load" text;
  - that no "loading text step hanging-too" worker started, using the set of `Thread` objects, so a same-named worker from an earlier test cannot hide one;
  - that the "hanging-import" worker is still alive.
  - The limit is now 1.0 s, and `elapsed < 1.6` stays as a safety net.
  - These checks prove one wait instead of two, without the clock.
- Local: the plugin, isolation and app-plugin files give 127 passed; T6 takes 1.05 s with a small heap.

## Findings

### S1 (should-fix): T6's remaining clock bound is still close to what CI measures (kind brittle-test)
`tests/unit/test_textprep_plugins.py`, `assert elapsed < 1.6`. `elapsed` includes the load of `AMPERSAND`, and since c79069d each load ends with a full `gc.collect()` in its worker. That collection scales with the heap of the test process:
- in my serial full-suite run, the isolation fixture's own `gc.collect()` took 0.19 s (its setup time);
- Linux CI at c79069d measured 0.33 s over the 0.5 s limit (0.83 s).

With the 1.0 s limit, Linux then lands near 1.33 s against 1.6, and Windows runners are slower. The structural checks already prove the claim, and two waits would take at least 2.0 s.

Fix: drop the `elapsed` assertion. If a clock check is wanted, use `< 1.9`, which is still below two waits. One line.

### N1 (note): the collection's cost grows with the heap
The answer measured 13.9 ms with about 105,000 objects. In a large process (the full test suite above) one collection takes about 0.2 s. The server holds more objects than the CLI after many jobs, so the guard's cost per plugin and document grows there too. That is still far inside 60 s, and the step runs in the job's thread anyway. The collection also runs finalizers of unrelated garbage in the worker, which is harmless. If it ever matters, `docs/baseline.md` could state the heap size its row was measured with. No change asked.

Handoff (THR-07): goal: PR #715 to merge. Done: round 2 approved with S1 (T6's clock bound). Next: the author drops or loosens the bound (or defers it), merges main 9ad6d11 in and runs `ci:full`. Round 3 checks that diff and the three systems; the merge follows on the coordinator's go.
