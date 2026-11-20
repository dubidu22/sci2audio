# Review PR #611, round 1 (head 8c4a894, base ff7bf8d)

PR: web: the player shows a PDF's code with its printed indent (#282). Non-critical, web lane (B12 PR 2, plan §4).
Verdict: **approved, no fix list.** Merge waits for green CI on 8c4a894 and a green main (main CI red on Windows since ff7bf8d, web lane fixing under MRG-04).

## Checked
- View only: `Block.text`, the script, read-along and audio are untouched; `indented()` runs only where `_block_view` already set `view.code` (placeholder with its notice). No golden, snapshot, regression or sentence change; no player.js or template change (`listen.html` already renders `block.code` in a `<pre>`; markers and read-along do not use offsets inside the code view).
- `indented`: rows keyed by part start = row start (split on "\n", `zip(strict=True)`), so a row's indent never lands on another row; parts that do not start a row only feed the per-page left edge (min, harmless). Width = median box width / characters, 0 → text unchanged; indent never negative (left is the min), capped at 40. Leading spaces of the first row survive (`strip("\n")` only).
- Tagged documents (no boxes) keep their own spaces; tested.
- AC-282.1 (indent, no invented block text) and AC-282.2 (seaborn p.2 argument lines four spaces in, from the corpus PDF) are tested; browser test checks `textContent`.
- `tests/unit/test_web_player.py`: 59 passed locally. CHANGELOG Unreleased line present (D-768). No closing keyword in the commit message.
- CI at review time: PR #611 workflow green, ZAP green, CodeQL green; the main CI run is on attempt 2 (re-run of the reported-only WebKit leg, which failed in the untouched `tests/browser/test_remove.py::test_the_removal_reflows_at_320_pixels[webkit-de]`). That leg is reported-only; if it fails again without a code cause it is a flaky-test quarantine for the web lane (D-374), not this PR's.

## Deferred (issue filed)
- #612 (web): a listing's later-page part made only of indented lines is drawn flush, because the left edge is per page.
