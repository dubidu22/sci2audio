# Review PR #600, round 2 (head 72577a5, final)

Verdict: **approved, merged** (pinned squash on 72577a5).

- M1 fixed: `_white` returns inf for a neighbour whose nearest line does not overlap the caption's edge line across. The round 1 probe (`plans/review-pr600-twocol-probe.py`) now pairs Listing 1 → "import a", Listing 2 → "import b". New test `test_a_listing_caption_names_the_code_in_its_own_column`.
- S1 fixed: `test_listings_captions_and_furniture_over_pages_keep_every_item_once`, Hypothesis over 2–4 pages with running heads, page numbers, code, listing captions and prose; asserts as listed in round 1. Author reports it kills the one-caption-per-block and duplicated-furniture mutants under ci, dev and nightly.
- Fix commit touches only `layout/code.py` (5 lines) and `tests/unit/test_layout_code.py`. No golden, snapshot, regression or sentence change: still non-critical.
- CI on 72577a5: `CI passed` green (tests ubuntu, lint and layers, both Chromium shards, CodeQL, licences, security).
- Local: the four touched test files, 415 passed (3 runs). One local run under the dev profile failed once in the pre-existing `test_layout_tagged.py::test_any_tagged_content_gives_a_document_keeping_every_item_once` (file touched by this PR only by a new example test); not reproduced in 9 further runs on the PR head nor 3 on 678fe3c, and the PR's code does not touch the tagged path's item bookkeeping. Treated as a one-off cold-start (no failure output captured); not a quarantine case (D-374 needs two failures without a code cause). If it shows up again in CI, the next review files it.
- Main moved by uv.lock only (#513, #515): no conflict, no shared file, merged without a branch update (MRG-03).
- Deferred: #603 (layout), #604 (textprep, AC-281.2 row + docstring).
