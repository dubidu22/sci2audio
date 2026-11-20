# Review PR #307, round 2 (#213 PR A)

Reviewed head 50abb72 (plain push on bcc101e). Fix list: PR comment 6880229628.

## Round-1 items

- **R1-1 fixed.** `build_view` finds a chapter from where its first piece is read. My probe is now `test_a_chapter_that_starts_with_a_moved_block_is_the_chapter_it_is_read_in`; it passes.
- **R1-2 partly fixed.** `_heard_moves` keeps a move only when the read-along agrees. The old-style read-along test passes. But the neighbour rule misses notes that share a position (R2-1).
- N1, N2 unchanged in A, which is fine (N2 is handled in PR B).

## Required fix

**R2-1. A second note moved to the same position is not "heard".** `_heard_moves` needs the chunk just before the moved block to belong to its target block, or the chunk just after it to be the target's first. When two notes are moved to one position, the voice reads: target text, note 1, note 2, rest of the target. The chunk before note 2 belongs to note 1, not to the target, so note 2 is shown where printed. The same happens for notes moved to a target's start (note 1 is followed by note 2, not by the target).

Probe: "It works.1 It holds." in chapter One, with notes 3 and 4 printed in chapter Two and both moved to `Span(1, 10, 10)`. The read-along reads 1a, 3, 4, 1b. The view gives `[[1, 3], [4, 5]]`: note 4 is shown in chapter Two while the voice reads it in chapter One. The plan measured 6 sentence ends with 2 or 3 marks on the corpus, so PR B hits this.

Suggested fix: walk the read-along in order and accept a run of consecutive moved blocks that share one target, when the run touches a chunk of that target. That means the chunk before the run is the target's, or the chunk after it is the target's first. Test with two and three notes at one position, mid-block and at the target's start, plus an old-style read-along with two notes printed together under a paragraph that does not hold their marks (they must stay where printed).

CI on 50abb72 was still running at review time. The local move, player and app tests passed (97).
