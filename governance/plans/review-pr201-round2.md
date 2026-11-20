# Review PR #201, round 2 (issue #199)

Head 110bcc2. Verdict: **clean. S1 is fixed; merge once CI is green.**

## S1: fixed as asked

The diff from ea70558 is exactly the two changes listed, both in `tests/unit/test_layout_headings.py`:
1. The branch for content without positions asserts one level shift per page (with the outline minus without, grouped by the page of each section start's first item). A comment cites D-407 and notes that `outlined()` never sets `item`.
2. A new `@example`: h1 "Part", h2 "Chapter" and "Text." on one EPUB page, with the outline ("0",1,1), ("0",1,1), ("Part",2,1).

Nothing else changed.

## Checks (in a worktree, mutating `layout/tagged.py` only when an outline is present)

| Code | Profile | Result |
|---|---|---|
| PR as is | nightly | passes |
| drop (first heading per page becomes a PARAGRAPH) | ci | fails |
| relabel (label + "x") | nightly | fails |
| rank (headings on an outlined page all get the base level) | ci | fails (round 1: survived) |

- **Fast suite:** 3109 passed, 1 skipped.
- **Nightly:** `test_layout_headings.py` gives 49 passed.
- **CI:** green at merge (checked before merging).

## Merge

Main moved twice during the review, first to #194 and then to #200 (layout). I merged it into the branch with update-branch both times. On cf5d267 I re-ran `test_layout_headings.py` under nightly (49 passed) and the fast suite (3168 passed, 1 skipped), and CI was all green. I squash-merged at 2026-11-13 21:38:13 UTC as 486e18b, and #199 is closed.
