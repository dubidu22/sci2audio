# v1.1.0 checklist runs on release/1.1 (08d5965)

Written 15 Nov 2026, about 23:30 UTC, by the thread "Release v1.1".

| Run | Result |
|---|---|
| ZAP baseline scan 43770962498 | **Passed** |
| CI push 43770945377 | **Passed** on all three systems |
| Nightly 43770960312 | **Failed**, five jobs, four causes (below). Benchmarks, Chromium and WebKit on Linux passed. |
| Mutation 43770964278 | **Failed** after 2 minutes, before any mutant ran (cause 5) |

## Causes

1. **EPUB cover test, slow tests on all three systems** (`test_convert_reads_an_epub_and_keeps_its_cover`, `assert reused == 1`).
   - The cut Time Machine book has Titlepage, Imprint and Epilogue. Since #190 (PR #373), Imprint is a publisher's page and is not chosen by default, so its logo's "A figure is skipped." is gone, and nothing is reused.
   - The product is doing what was intended; the test is out of date.
   - Fix: the test passes `--chapters all`. Checked with `sci2audio script` on the cut book: one figure notice by default, two with `--chapters all`.
2. **Firefox, position test** (`test_the_next_run_offers_to_continue_where_the_person_stopped`, error at teardown: two requests "outside the server").
   - Both requests are the first run's page saving its position (`keepalive` POST to its own `/position`) on its way out. Firefox sends them after the test has routed everything to the second server.
   - The product behaves correctly, and the save goes to its own server.
   - Fix: the second route also lets requests to the first server through. Requests to anywhere else still count as outside.
3. **Firefox, speed test** (`test_the_speed_select_sets_the_rate_and_keeps_the_pitch`, "Page crashed").
   - This reproduces locally on every run. A Playwright locator on `<option>` elements (`all_inner_texts`, also `evaluate_all`) crashes Firefox's page, while `page.evaluate` on the same elements works.
   - This is a Playwright/Firefox fault, not ours.
   - Fix: read the option texts with `page.evaluate`. It passes locally in Firefox and Chromium.
4. **WebKit on macOS, speed by keyboard** (`test_the_speed_by_keyboard`: value stays "1" after ArrowDown). It passed in WebKit on Linux.
   - On macOS the arrow keys on a closed select open its native menu instead of moving the value, and Playwright cannot drive that menu.
   - **Not fixed: needs a decision**, see below.
5. **Mutation**: `tests/unit/test_ci_workflows.py` (added by #364) reads `.github/workflows/ci.yml`, but mutmut copies only `src/`, `tests/`, `scripts/` and `README.md` into `mutants/`, so the stats run stopped at collection.
   - Fix: `also_copy` gains `".github/"` in `pyproject.toml`. That is the only root path the tests read that was missing (grep of the tests' root paths).
6. **Property test, many examples** (`test_the_built_in_steps_never_fail_and_are_idempotent`, a German document).
   - A table inside a "LITERATUR" section is removed with the reference list on the first run. The rebuilt table is empty, so the reference-list step skips it on the second run, and the table notice is read: "Eine Tabelle wird übersprungen."
   - The same happens in English, and **on v1.0.0 too**: I checked it with a written test on the v1.0.0 tag. So this is old, and only now found by the random examples.
   - What a listener hears (the first run) is right: nothing from the reference list.
   - **Not fixed: needs a decision**, see below.

## Fix branch

`release-fix/1.1.0-nightly` at 5131ba1 (from `release/1.1` 08d5965) carries fixes 1, 2, 3 and 5: tests and the mutmut config only. To prove them, nightly 43774244578 and mutation 43774246928 run on it. No PR is open yet, because the mutmut config counts as CI (critical).

## Decisions for the coordinator

- **A. WebKit on macOS, arrow keys on the Speed select.**
  - Options: (a) the test asserts the macOS behaviour (the select is reached and focused) and leaves the value change to the other engines and to Colin's VoiceOver step 3, which tries the Speed choice by keyboard on his Mac; (b) the test opens and drives the menu some other way, which would need a CI probe on macOS first; (c) ship 1.1.0 with this one nightly job red and file an issue.
  - I recommend (a), as a platform expectation with its reason written down, not a skip to get green. I have not done it, because it narrows a test.
- **B. Reference list with a table, second run.**
  - Options: (a) file an issue for the v1.2 textprep lane and accept for 1.1.0, since it was in 1.0.0 and the first run is right; (b) fix it now in the notice step (no notice for a placeholder inside a reference-list section unless References is switched off). That is a textprep change with regression cases, so critical.
  - I recommend (a).
