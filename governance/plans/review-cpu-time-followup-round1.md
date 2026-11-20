# Review of PR #297 (issue #294, D-551), round 1: CPU-time timing follow-up to PR #277

Reviewed first on the author's commits fb447bb and bb815ff, cherry-picked onto main 4cfff38. PR #297 (head 7b109da, one commit on 4cfff38) differs from that only in one docstring line ("#277 review" became "#294"), so every result below holds for it.

## Change

- `tests/unit/linear_time.py`: `best_seconds` times with `time.process_time()` (process CPU time) instead of `time.perf_counter()`. `FLOOR` is `4 / 64` s (four 15.6 ms ticks) on win32 and stays 2 ms elsewhere.
- `tests/unit/test_linear_time.py`: the fake clock patches `process_time`.
- `tests/unit/test_textprep_footnotes_linked.py`: its own `seconds()` uses `process_time` too.
- Not converted, and not needed: the #274 `_abbreviations_seconds` link look-ahead timing test still uses `perf_counter`. Its counted twin is the real guard.

## Does CPU time still catch each slow version? (Linux, 4 cores)

| slow version | test | result |
|---|---|---|
| cutter counts the whole rest each cut | utterances linear_time | fails, 64.2 (0.107 s → 6.877 s) |
| footnotes: each note scans every block's marks | footnotes linear_time | fails (4.78 s vs 40 × 0.065 s) |
| citations `_MAX_BRACKET = 8000` | deep German nest (`assert_near`) | fails, 21.9 |
| numbers look-back `WINDOW = 10**9` | numbers is_quick + pathological | fails, 60.9 and 63.1 |

The steps are pure CPU, so process time measures the same work as the wall clock, without the time other processes take.

## Can the Windows floor mask a quadratic case?

With the floor at 62.5 ms, a slow version passes only if its large run stays under 32 × 62.5 ms = 2 s. With the floor forced on Linux (`FLOOR = 4 / 64`): the cutter slow version still fails (69.3) and so does the numbers look-back (62.3). A quadratic slow version also slows its own base run (0.105 s and 0.218 s here, both over the floor). Every converted case passes on today's code with the forced floor (35 passed).

Masking is possible only for a quadratic slow version whose 100,000-character run stays under 2 s, and only on Windows. Linux and macOS run the same tests with the 2 ms floor on every PR. Acceptable.

## Overload run

Two fast suites at once, each `-n 24` with `HYPOTHESIS_PROFILE=ci`, on 4 cores (48 workers, 12 times overloaded), on main + the two commits:

- both runs: 4304 passed, 2 failed, 1 skipped (334 s and 332 s);
- every textprep timing test passed in both runs;
- the 2 failures were the same in both runs, both extraction tests with wall-clock limits in seconds that this change does not touch: `test_extraction_text.py::test_a_large_file_is_read_in_reasonable_time` (< 10 s) and `test_extraction_markdown.py::test_pathological_inputs_are_read_in_linear_time[table rows]` (< 30 s). They fail only under this artificial overload. Reported to the coordinator as an observation.

## Findings

None. A nit, no action: the footnotes test keeps its own 1 ms floor rather than `FLOOR`. Its base run (about 65 ms) is above the Windows tick anyway.

## Branch history note

The author's push of 14:02:40 to the #277 branch was a plain push, not a force-push. GitHub had deleted the head branch when #277 merged, so the push re-created it from the author's local history.

## CI on 7b109da: F1 (must-fix)

The `tests (windows-latest)` job failed in `test_linear_time.py::test_a_text_far_slower_than_its_reference_fails` with DID NOT RAISE. The fake reference run (0.01 s) is replaced by the Windows FLOOR (0.0625 s), which gives 0.2 / 0.0625 = 3.2, under the limit of 16. Fix: fake times above the floor, or patch FLOOR in the fixture. The other fake-clock tests pass on both floors.

Side issue filed for D-556: #298 (v1.2), moving the extraction text reader and Markdown table-row timing tests onto the ratio helper.

## Round 2 and merge

F1 was fixed in 9e1a6d2. All the fake runs now lie above the Windows floor (the far case is 2.0 s against 0.1 s), and a new test pins FLOOR per platform. With the 62.5 ms floor forced on Linux, the five behaviour tests pass. CI was green on all three systems. Squash-merged at 2026-11-14 14:30:11 UTC as 918f6ce.
