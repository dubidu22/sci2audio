# Review PR #307, round 3 (#213 PR A)

Reviewed head 070980b (a plain push on 50abb72). Fix list: PR comment 6880301626.

- **R2-1 fixed.** `_heard_moves` now groups the read-along into runs, one per block. A stretch of moved blocks that share one target counts when it sits right after a run of the target, or right before the target's first run. My round-2 probe now gives `[[1, 3, 4], [5]]`, so both notes show in chapter One. I also checked an old-style read-along for the same document: it gives `[[1], [3, 4, 5]]`, so both notes stay where they are printed. The author added tests for 2 and 3 notes, mid-block and at the start of a block, plus an old-style case.
- Fast suite run locally on 070980b: 4563 passed, 1 skipped. Main is still 1cbed9b, so the branch is up to date.

Verdict: **approved.** Merge by squash, pinned to 070980b, once CI on that head is green.
