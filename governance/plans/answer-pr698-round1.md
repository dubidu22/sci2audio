# PR #698, answer to review round 1 (head 80f4459 → f7e818a)

Author: B-W2 web/app implementation thread, Opus 5.5. 20 Nov 2026. One fix commit: f7e818a.

## Must fix

- **M1 fixed, as D-851 decided.** `.github/scripts/browser_shard.py` has a new `browser_tests(listing)` that keeps only lines that start with `tests/` and contain `::`. The quarantine banner `  #697 tests/browser/test_flow.py::…` (indented, after the issue number) and pytest's summary line are left out, so the shard file holds test ids only and pytest no longer exits 4. `main()` uses it; `nightly.yml` calls the same script, so the nightly is covered as well.
  - Test: `tests/unit/test_ci_workflows.py::test_the_browser_shard_reads_only_test_ids_not_the_quarantine_banner`. A collect output with the banner and summary lines gives exactly the three test ids. It failed before the fix (the function did not exist).
  - Real run, locally, with the marker in place: `browser_shard.py firefox 1 2` writes 101 lines, all `tests/…`, none with `#697`, and `pytest -m browser --browser firefox --collect-only @shard.txt` exits 0 with 101 tests.

## Labels and body

- Added `lane:infra` and `risk:high`; removed `risk:low`.
- The PR body now has the M1 section, "## Tests promised in the plan" with the new node ID (the local check reads 1 of 1), the tests run, and the new risk.

## Local checks

- ruff, format: clean.
- `tests/unit/test_ci_workflows.py` 28 passed; `tests/unit/test_quarantine.py` 11 passed.
- `zizmor --offline .github/workflows`: no findings.

## Next

Linux CI on f7e818a. Then merge main if it moved, set `ci:full`, and report the head; round 2 reviews the fix and the three-system run.
