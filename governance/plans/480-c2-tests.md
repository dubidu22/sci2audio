# #480 PR C2 (web): tests written down before the branch exists

Status: prepared 17 Nov 2026 while C1 (#495) is in review. Read against the #490 branch `web-v13-pr-b` at c0c21ba (review round 1), the markers PR. C2 branches from main once #495 and #490 are both merged, and these tests are written first there. Non-critical (D-730), Linux CI, browser job.

## Code points C2 touches (as read on c0c21ba)

- `web/player.py` `_block_view`: today one `Piece` per chunk with a span (`element = f"s{n}"`, `chunk = n`). C2: a chunk whose read-along entry has `joins` and whose chunk before it (`n - 1`) is the last element of the same block extends that element. The piece is redrawn from the first piece's start to this chunk's end, so the text between the pieces is included. `element_of[n]` is the same id and `data-chunk` stays the first piece. `_piece` gets the merged range, so the marks (`_parts`) and the joined hyphens work over the whole range.
- `PlayerView.chunks`: unchanged shape `(start, end, chapter, element)`. Joined chunks repeat the element id.
- `static/player.js`:
  - `#next-sentence` and `#previous-sentence` step by element (the first chunk of the next or previous element). Previous restarts the current element from its first chunk when more than `RESTART_AFTER` has been played since that first chunk's start, not since the piece's start.
  - `markerTarget()` (`MARK_BACK`): it measures from the start of the element's first chunk. As written today, M in the first 1.2 s of piece 2 would walk back over the same id and land on the sentence before. That is a C2 bug to pin.
  - `order` is already deduplicated by element.
- `web/api.py`:
  - `_Book.on_sentence(chunk, markers)` compares `p.chunk == chunk`. C2 compares the sentence: the first chunk of the joined group of `p.chunk` against that of `chunk`. Otherwise M on a joined sentence would not find an old marker placed on piece 2, and would set a second one.
  - `set_marker`: the anchor span runs from the group's first chunk to its last (same block). A request naming a later piece anchors the whole sentence too.
- `web/markers.py` `place()`: unchanged. The overlap rule shows a marker on the chunk it overlaps most, and that chunk's element is the joined sentence.

## Unit tests (tests/unit, TestClient where the API is involved)

Characterisation first (they pass on main and must still pass):

1. A read-along without `joins` (an audiobook made before C1): `_block_view` gives one element per piece, the same pieces, ids and `data-chunk` as today. Plus a golden check: the existing player snapshots are unchanged.
2. `position.json` saved on any chunk, including a later piece of a cut sentence, still resolves (`Bounds.fits`, `Bounds.continues`, `read_position`), with and without `joins`.

New behaviour:

3. A block with one sentence cut into three pieces (`joins` F, T, T) and a sentence before and after it:
   - one `Piece` for the cut sentence, whose text is the block text from the first piece's start to the last piece's end, including the space or the removed text between the pieces;
   - `element_of` is the same id for all three chunks;
   - `chunk` is the first piece;
   - the sentences before and after keep their own elements.
4. `joins` on a chunk whose chunk before it lies in another block (a broken or hand-made file) starts a new element. The same holds for a chunk whose chunk before it has an empty span, or is a notice box.
5. Marks: a cut or replaced stretch that lies across the join is drawn in the merged piece. The parts' texts join up to `shown(text, start, end, joined)`, which is the existing invariant, now over the merged range. A hyphen joined at a line end between two pieces is shown joined.
6. `PlayerView.data()["chunks"]`: the joined chunks carry the same element id, and their times are the read-along's own.
7. Markers through the API:
   - (a) An old marker anchored to piece 2's span shows on the joined sentence: `MarkerOut.chunk` is piece 2, and the page's element for it is the sentence's id.
   - (b) M on that sentence (POST with the first chunk) answers 200 with that marker, and does not set a second one.
   - (c) A new marker on a joined sentence anchors the whole sentence: block, `start` of piece 1, `end` of piece 3, and the whole sentence as the anchor text.
   - (d) A POST that names piece 3 anchors the same whole sentence.
   - (e) The not-found and not-read states of #490 are unchanged for a joined sentence.
8. Made again without cuts (the same text, no `joins`): a marker anchored to the whole sentence shows on the chunk that overlaps it most. This is the #490 overlap rule, pinned for the new anchor.

## Browser tests (tests/browser, Chromium; axe in light and dark)

9. The mark and the margin bar stay on one element while the audio passes through all three pieces. At a time inside each piece the highlighted element is the sentence's id, and the bar spans the sentence's lines. This is checked in normal Listen and in Focus listening.
10. Next sentence from piece 1 goes to the sentence after the cut one, not to piece 2. Previous while paused in piece 3 goes to the first piece of the sentence before. Previous while playing more than `RESTART_AFTER` into piece 2 restarts piece 1. The arrow keys behave the same as the buttons.
11. A click on the joined sentence plays from piece 1.
12. M in the first 1.2 s of piece 2 marks the joined sentence, not the sentence before. M in the first 1.2 s of piece 1 still marks the sentence before, as #397 decided.
13. The timeline tick of a marker on a joined sentence sits at the sentence's first piece, so the marker list and the tick agree. Small decision for the plan line: tick at `chunks[first][0]` of the marker's element.
14. An old audiobook (no `joins`) looks and steps exactly as today. This is one browser check on the existing fixture.

## Mutants to kill (by hand, as for C1)

- `_block_view` ignores `joins`.
- The merge ignores the block check (test 4).
- Next and previous step by chunk instead of by element.
- Previous measures `RESTART_AFTER` from the piece's start.
- `markerTarget` measures from the piece's start.
- `on_sentence` compares chunks instead of sentences.
- `set_marker` anchors the named piece instead of the whole sentence.
- The tick uses the marker's own chunk instead of its element's first chunk.

## Test-harness changes expected (D-718)

- A read-along helper in `tests/unit/web_helpers.py` that writes `joins` on chosen chunks.
- The fake voice's player fixture with one long sentence cut at a comma (`max_chars`). It is a new fixture builder, and the existing fixtures are unchanged.
