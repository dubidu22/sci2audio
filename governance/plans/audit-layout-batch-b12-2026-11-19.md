# Light audit, layout batch B12 (19 Nov 2026)

Scope: the merged diffs of PR #600 (a9dad14, #281 #283, layout) and PR #611 (e658c17, #282, web), read together for cross-PR inconsistencies and contract touches only. #284 is a decision (plan §3, close proposed to Colin via the coordinator), no code.

Result: **0 blocking findings.**

## Contract touches
- None. No change to `sci2audio.core`, the lint-imports layers, the text-step interface, goldens, snapshots, regression cases or sentence sets in either PR. New imports stay inside one layer (`layout.captions` and `layout.graphics` import `layout.code`; `code` imports neither, no cycle). The web PR reads `Document.content` lines and boxes, which the player already had.
- Textprep touched by a test file only (#600, D-756); its docstring and the AC-281.2 regression row are #604.

## Cross-PR consistency
- A1 (consistent, known limit): #600 joins a listing over a page break into one CODE block; #611 measures indent against the leftmost line per page, which is right for different page margins but draws a later-page part made only of indented lines flush. Filed as #612 in the #611 review.
- A2 (note, fold into the next layout PR): the `layout/code.py` module docstring still ends "A listing's indentation is not rebuilt: a PDF line holds no leading white space, and layout adds no text (#282)". Still true for layout, but it should add that the player draws the indent from the line boxes (`web/player.py` `indented`, #282). Add it with #603 or the next layout lane PR; no own issue.
- A3 (note): the caption cut (#600, `captions.py`) calls `monospace_line` without the body size, while `find_code` passes it; a caption line set in a typewriter font larger than the body text is cut off but then is not code (stays a paragraph). Not seen in the corpus or the tests' shapes; recorded with #603 (same rule) rather than a new issue.
- CHANGELOG: two Unreleased lines, #281/#283 and #282, consistent with each other (block text, script and audio unchanged by #282).

## Process
- #600: 2 rounds (M1 cross-column pairing, S1 property test), #611: 1 round. Both merged pinned on green heads; #611 got main merged in first because #610 changed `tests/unit/test_web_player.py` (MRG-03), PR diff confirmed unchanged. Main CI green after #600 on all three systems; after #611 checked as noted in the ledger.
- Follow-ups: #603 (layout), #604 (textprep), #612 (web), #599 (layout, filed by the author).
- Thread length: the review thread stayed short (no compressions); fine for one more batch of the same lane.
