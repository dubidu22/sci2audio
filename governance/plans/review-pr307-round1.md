# Review PR #307, round 1 (#213 PR A: move edits)

Reviewed head bcc101e (on main 1cbed9b) against plans/issue213-footnotes-plan.md (D-558, Q1–Q10).
Verdict: **changes requested, two fixes in the player.** Core, runner, conformance suite, app and report are correct as far as I could test them.

## What I checked

- Fast suite locally: 4556 passed, 1 skipped. CI on bcc101e: all green (3 systems, browser, ZAP, CodeQL).
- No golden file changed (no .ambr or regression TOML in the diff). `TEXT_STEP_API` stays 1.
- **Core differential probe** (own Hypothesis test, 3000 examples on `small_documents`, about 1000 valid sets mixing removes, replacements, pauses, asks and up to N moves, several to one position): `apply_edits` equals an independent reference (apply the plain edits, then split each target block's pieces at `to` and insert the moved blocks' pieces in block order), and is order-independent. Every Q2 rule has a test in `test_core_moves.py`.
- **Runner differential probe** (block step, inline step, two move steps; 3000 examples): a move is accepted exactly when neither its block nor its target block is claimed by an accepted block edit and `check_edits(accepted so far + move)` passes. Set-aside winners seen: remove, pause and move (chains across the two move steps). `run.script()` never raised.
- **Spot mutations** (13, on top of the author's 27): 11 killed. Survivors: `break` in `check_registry` (equivalent: only avoids a second message) and the heading guard in `build_view` (N1).
- Plan items: Q1 Edit/`to`/export defaults; Q2 rules; Q3 stage order, move-only steps, set-aside cases incl. "Footnote texts" on and the ends of a claimed target block; Q6 `read_at` in `prepare_script` and report chapter/spoken; Q8 player order and page markers; Q9 JSON `to`, Markdown and check-table wording (en, de); Q10 paragraph pauses and the script file. All present and tested.

## Required fixes

**R1-1. The player picks a chapter by the printed block of its first chunk.** `build_view` calls `_chapter_of(chapters, readalong.chunks[times.first_chunk].span.block)`. When a chapter's first chunk is a moved block (a move to position 0 of the chapter's first block, which `check_edits` allows), it resolves to the chapter the note is printed in, and the real chapter is never shown. Probe: heading "1 One", footnote (moved to `Span(2, 0, 0)`), heading "2 Two", paragraph "More."; read-along chapters One (chunk 0) and Two (chunk 1). Result: `[[b.index for b in c.blocks] for c in view.chapters] == [[], []]`: "2 Two" and "More." are not shown at all. Fix: `_chapter_of(chapters, run.read_at(block))`, with a test.

**R1-2. The player places moved notes by re-running today's steps, not by how the audiobook was read.** `build_view` gets the moves from a fresh `run_steps(..., BUILT_IN_STEPS)`. Once PR B ships, every audiobook made before it (v1.0 to v1.1, notes read where printed) is shown with its notes after their marks: the view and the voice disagree, and for 21 of the 69 corpus notes the note sits in another chapter's section than the one playing, so the highlight leaves the chapter. `joined_hyphens` has the same re-run design, but there it only changes how a word looks. Fix (author's choice, say which): either use a move only when the read-along agrees (the moved block's first chunk comes right after a chunk of its target block), or write the accepted moves into `audio.json` and use only those (old records have none, so they show as printed). Test: an old-style read-along where the note is read where printed while a move step would move it; the view must show it where printed and in its printed chapter.

## Nits (optional, no issue needed)

- **N1.** `levels.get(shown_here, 0) if shown_here == number else 0` survives mutation: no test moves a heading block. One assertion with a moved heading, or leave it.
- **N2.** The conformance suite's idempotence check compares each block's text, so it cannot see where a move lands on the second run. Fine for A (a move changes no text). PR B's second-run check therefore has to run the whole chain twice (as the nightly runs do) and compare the rendered script order, not only per-block text.

## For PR B (noted now)

Golden diffs only in the files of plan section 4 and explained; all 69 PDF and 3 tagged notes move or are listed with a set-aside reason; whole-chain second-run check; German corpus changes only where a note moves; the highlight browser test; a line on chains in the body.
