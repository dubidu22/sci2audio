# Project rules

One checkable sentence per rule, with what checks it.

- A PR title reads `<area>: <outcome> (#N)`. Checked by: review.
- A PR that changes the interface (`src/sci2audio/web/**`, its static files and templates) passes `uv run pytest -m browser` before it opens. Checked by: the browser CI job on every PR.
- A critical PR gets a green `ci:full` run on Linux, macOS and Windows before review, and merges only when `tests (macos-latest)` and `tests (windows-latest)` succeeded on the head being merged, since `CI passed` alone can still show an earlier Linux-only run (D-580). Checked by: `.github/workflows/ci-full-label.yml` and the CI matrix.
- A test that fails twice without a code cause is quarantined the same day with a linked Issue, then run alone 40 or more times (per browser for a browser test) with the result recorded in that Issue; a found code cause fixes the test and lifts the quarantine, and the test is fixed before the next release (D-374, D-682, D-739). Checked by: `.github/workflows/isolate.yml`.
- Release: R1 sets version, CHANGELOG and README on `release/X.Y`; R2 is the release-day PR with Colin's hand-step results and the changelog date; R3 forward-merges `release/X.Y` into `main` after the tag, then the milestone closes; the release-checklist runs (ZAP, nightly, mutation) run on the release branch (D-669, D-714). Checked by: `docs/release-checklist.md`.
- A change that can affect output is judged with the corpus comparison on a local merge of `main`: every output file not expected to change stays byte-identical (D-714). Checked by: `scripts/corpus_diff.py` and review.
- A `risk:high` PR gets a review by a reviewer subagent (`/code-review`) before it merges, its findings answered in the PR; other PRs rely on CI (Colin, 28 Nov 2026, #1227). Checked by: the PR body's review section.
- A golden file (corpus truth file, syrupy snapshot, English regression case) changes only in a critical PR that explains the diff (D-69). Checked by: the labeler sets `risk:high` on `tests/corpus/**`, `tests/unit/__snapshots__/**` and `tests/regression/**`.
- Claude does not do the owner's hand steps (the listening test and VoiceOver pass; the speed run with `scripts/speed.py` on the M4 and the Dependabot check; pushing release tags and PyPI publishing; repository settings and rulesets); it prepares them and hands them to Colin. Checked by: review and `docs/release-checklist.md`.
- The label for critical is `risk:high` here, and the labeler (`.github/labeler.yml`) sets it. Checked by: `.github/workflows/labeler.yml`.
