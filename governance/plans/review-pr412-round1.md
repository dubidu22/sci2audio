# Review of PR #412 (v1.1.0 checklist-run fixes), round 1

Reviewed head **8f98a62** (3 commits on `release/1.1` 08d5965). Critical (CI config: mutmut), Opus high. 16 Nov 2026 ~01:15 UTC. Plan: `plans/release-v11-checklist-runs.md`, decisions D-678 (A: WebKit/macOS focus only; B: #410 accepted as a known issue).

**Verdict: changes needed (two small items).** No product code; the mutmut fix is right; four of the five test changes keep or strengthen what they test. One test change lets more through than it needs to, and the known-issues line describes something users cannot do. The mutation run is still running (see the end).

## What was checked

| Change | Finding |
|---|---|
| Files | `CHANGELOG.md`, `pyproject.toml` (mutmut `also_copy`), `tests/browser/test_player_position.py`, `tests/browser/test_player_speed.py`, `tests/integration/test_cli_end_to_end.py`. No `src/` change. |
| 1. EPUB cover slow test `--chapters all` | Correct: Imprint is a publisher's page since #190, so the default run loses the repeated logo notice. The cover assertions are unchanged; the default chapter choice of an EPUB stays covered by #190's own tests. Not narrowed. Green on slow tests on all three systems (nightly 43776765113). |
| 2. Firefox position test, route | **P1.** The new route lets every request to the first server through, from the second run's page too. The only request that needs to pass is the first page's exit save: `POST {live.url}/api/v1/documents/{document}/position` (`player.js:192-206`, `keepalive`). As written, a second-run page that fetched audio, data or the position from the first server would no longer be reported as outside. |
| 3. Firefox speed test, options via `page.evaluate` | Same assertion on the same six labels (`o.text`); not narrowed. Firefox green in the nightly. |
| 7. Chromium position test, `wait_until_saved` | Replaces a 300 ms sleep by a wait for `position.json` to hold the stopped time (±0.05 s, up to 5 s): waits on state, stronger than before. |
| A. WebKit on macOS, speed by keyboard | Early return after the select is reached and focused, only for WebKit on darwin, reason written in the test, as D-678 decided. Accepted. WebKit/macOS green in the nightly. |
| mutmut `also_copy` + `.github/` | Correct and sufficient: the tests' root reads are `README.md`, `scripts/`, `.github/workflows` (test_ci_workflows.py) and `pyproject.toml` (test_package_data.py via WheelBuilder; mutmut copies pyproject.toml itself). Nothing else under the repository root is read. |
| B. Known issues (#410) | Verified on 8f98a62 with the issue's `make_document` repro for TABLE, FIGURE, FORMULA and CODE in English and German: all eight give nothing on the first run and the notice on the second. **K1** on the wording. |
| Nightly 43776765113 on 8f98a62 | All jobs green except "property-based tests, many examples": the one failure is the #410 shape (LITERATUR section, "Eine Tabelle wird übersprungen." on the second run), accepted by D-678. |
| PR CI | Linux run 43783044883 running; `ci:full` added by this review for the three-system run. |

## Fix list (exact)

**P1. `tests/browser/test_player_position.py`, the second route:** replace `or inside(route.request.url, live.url)` with a pass for exactly the first page's exit save: `route.request.method == "POST"` and `route.request.url == f"{live.url}/api/v1/documents/{document}/position"`. Every other request to the first server still goes to `live.outside` and is aborted. Keep the comment. Run the test in Firefox and Chromium locally (or nightly browser jobs on the new head).

**K1. `CHANGELOG.md`, "Known issues":** the line says "if the listening script is read a second time", which a user cannot do: only the second-run check (`sci2audio.testing.rebuilt_from_script`, for plugin authors) reads it again. And code blocks are new in 1.1, so "already in 1.0.0" holds for tables, figures and formulas only. Replace the line with:

> - For plugin authors: a table, figure, formula or code block printed inside the reference list is left out with the list, as it should be, but a second run over `sci2audio.testing.rebuilt_from_script` gives it its short notice, so the second-run check reports a difference (#410). Tables, figures and formulas did the same in 1.0.0. The audiobook and the listening script are not affected.

## Mutation run

43774246928 (on 5131ba1, the same mutmut config) was still running at review time; it got past the stats stage that failed before (cause 5). Its result goes into round 2 and the R2 body; per D-531 a partial result does not hold the tag.
