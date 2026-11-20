# Review of sci2audio PR #140, round 1 (13 Nov 2026)

PR: core: content without positions keeps item order, image refs and outline anchors (#73, part 1)
Head reviewed: 34b3ae08b46b52c6c5a3f1383e844d961b51014d (base main 1064e18, up to date)
Decisions checked against: D-309, D-310, D-311 (plans/issue73-epub-plan.md q6–q8), D-265.

## Verdict

Changes requested, all small. The design matches D-309 to D-311 exactly: three fields at the end
of their dataclasses (no positional call breaks), empty by default, so `to_data` leaves them out
and every PDF golden file and every saved job stays the same. Only the made-up EPUB example in
`test_core_content.ambr` changes, as the PR says.

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports` (3 contracts kept), `deptry src`: clean.
- Fast suite: 2110 passed, 19 subtests, 54 snapshots passed.
- Nightly Hypothesis profile on every test using the shared `contents()` strategy
  (`test_core_content.py`, `test_layout.py`, `test_layout_headings.py`): 86 passed.
- Strategy density probe (500 examples, dev profile): an outline item set in 137, `order` set in
  173, `order` set on a page with both lines and pictures in 93. Good coverage.
- CI on the head: Linux, macOS, Windows tests, lint and layers, browser, security, licences,
  CodeQL all green.

## Findings

1. **Fix: the outline item check is quadratic.** `_check_outline` rebuilds the set of a page's
   item ids for every entry that has an `item`. Measured on this head: 500 anchors into one
   20,000-line spine document take 0.79 s; 2,000 anchors into a 50,000-line document take 7.7 s
   (0.015 s without items). One large XHTML file with a long anchored table of contents is
   exactly the case D-311 is for (several chapters in one file), and the check runs on every
   `Content` construction, including `from_data`. Build each page's id set once (for example a
   dict filled on first use) and reuse it.
2. **Fix: the strategy never points an outline entry at a drawing.** `outlines()` draws `item` from
   the page's lines and pictures only, while `Content` accepts any item id, drawings included.
   Draw from all of the page's items (`_items`-style `(*lines, *pictures, *drawings)`), so the
   property tests cover what `Content` accepts, or say in the docstring why drawings are left out.
3. **Fix (small): the error for an item without a page.** `OutlineEntry("Methods", 1, item="l1")`
   raises "... which is not on its page (None)". Say that the entry points at no page, so the
   message names the real problem.
4. **Fix (docs): `Picture.ref` is the file's own text.** It is copied from the EPUB as stored, so
   it may hold `..`, an absolute path or anything else. Say so in its comment ("as stored; never
   trusted as a path to write to"), so PR 2 and any later export of figures check it before
   using it to name or write a file.

No other findings. Read in full: `core/content.py`, `core/export.py` (round trip and default
omission), the strategy, the new tests and the golden diff.

## Round 2 (13 Nov 2026, ~13:25 UTC)

Author's fix 45a2585 (new commit, no force-push):
1. Fixed: `_check_outline` builds each page's id set once (dict by page number). New test
   `test_many_anchors_into_one_long_page_are_checked_quickly` (2,000 anchors, 50,000 lines,
   `timeout(10)`); author measured 7.15 s → 0.02 s.
2. Fixed: `outlines()` draws the item from lines, pictures and drawings.
3. Fixed: an item without a page raises "points at item 'l1' but at no page"; new test.
4. Fixed: the `Picture.ref` comment says it is the file's text as stored, never trusted as a path.

Main had moved (#128, 5bf1264). Merged locally and checked: ruff, format, lint-imports (3 kept),
deptry clean; fast suite 2148 passed, 54 snapshots; nightly Hypothesis on the three `contents()`
files 88 passed. Branch updated with main through update-branch (merge commit 5964727, same tree
as the local merge). Approved; merge after CI is green on 5964727.
Merged: squash-merged pinned to 5964727 after CI green on all jobs (Linux, macOS, Windows, browser, lint and layers, security, licences, CodeQL); main c0e24fb (13 Nov ~13:40 UTC).
