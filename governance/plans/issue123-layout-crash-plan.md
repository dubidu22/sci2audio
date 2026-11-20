# Plan: #123 layout crash, a drawing claimed twice by an algorithm caption

Thread: "Fix layout crash and text-layout follow-up" (layout lane). Main f5ec33f. Not critical (no layer contract, core dataclass, KB or golden file change), so work starts after this plan is posted.

## Cause (measured)

Reproduced on f5ec33f with the issue's example. Tracing each layout step: `find_captions` makes the bold "Algorithm 0" line a CAPTION; `find_graphics` then returns one FIGURE block whose parts are `['d', 'd']`. `Document` rejects that ("items in more than one block").

In `graphics._read_float`, an algorithm caption reads its float as `_walk(box, down=True, …) + _box_top(box, …)`: the lines below the caption, plus the line just above it (the top of the algorithm's box). Both use `_beyond`, which counts an item as "below" when `item.y0 >= box.y1` and as "above" when `item.y1 <= box.y0`. With a caption box and a drawing that are both zero height at the same y, the drawing is both below and above, so both walks take it and the float lists it twice. Tables and figures don't hit this: `_side` keeps only one of its two walks. A plain "Algorithm 0 0" line is no caption (the label must be bold), so the drawing just joins the paragraph.

## Change

1. `layout/graphics.py`, `_box_top`: skip an item the walk below already took. Concretely, `_read_float` passes the walk's items and `_box_top` returns nothing if `above[0]` is among them (as it already does for an item a float took earlier, `state.taken`). This is the narrowest fix: the walk and the box top stay as they are for every real page, and an item can no longer enter a float twice.
2. As a guard for the invariant, `_read_float` also drops repeated items from `found` (keeping the first), so no later combination of walks can list an item twice. Tell me if you'd rather keep only one of the two; I recommend both, since the guard costs one line and the cause sits in shared geometry (`_beyond`) that other walks use.

I considered changing `_beyond` to make "below" and "above" exclusive for zero-height boxes (strict `>`/`<` on a touching edge). Rejected: real pages have lines that touch exactly (a rule drawn on a caption's baseline), and changing what counts as "below" moves the walk on corpus pages, which risks golden changes for a degenerate case.

## Tests

- The issue's case as an explicit `@example` on `test_layout_headings.py::test_sections_start_at_headings_and_carry_their_text` (acceptance criterion 2), written first and seen failing.
- A unit test in `tests/unit/test_layout_graphics.py`: the same page lays out, the drawing is in exactly one block, and that block is the algorithm's FIGURE (the caption names it).
- Mutation check: remove each of the two changes in turn; the unit test fails only when both are gone (so the guard is tested by a second case where `_box_top` is bypassed, or I state that the guard is defence only).
- Corpus goldens (`test_layout_corpus.ambr`, `test_layout_tagged_corpus.ambr`) must stay byte-identical; I check by sha256 before and after.
- Full fast suite plus the layout property tests under the nightly Hypothesis profile (2000 examples), which is how #123 was found. A nightly run on main is going now to see whether other crashes of this kind exist; any other crash it finds gets its own issue unless it has the same cause.

## Size

About 10 lines of code, 30 lines of tests. One PR, `layout: a drawing on an algorithm caption's line is in one block (#123)`, labels lane:layout, bug, P1; Closes #123.

## Decisions to log

- Q1 (#123): fix the double claim in `_box_top` (skip what the walk below took) plus a de-duplication guard in `_read_float`; leave `_beyond`'s geometry unchanged. Decided (Claude).
