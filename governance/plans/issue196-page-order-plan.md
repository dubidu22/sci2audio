# Plan: #196 blocks going back a page after a paragraph is cut

Layout lane. Order decided by the coordinator (D-432): #195, #196, then #163. **Critical**: the fix changes one block's place in the corpus golden (`test_layout_corpus.ambr`, nowak), so this plan waits for approval.

## Cause (measured on main 14513b2)

`paragraphs` lets a paragraph run on across a page break and makes what it meets meanwhile wait: figures, furniture, footnotes and lines without a position follow the paragraph, so it is never cut by them. Later steps cut paragraphs again (`find_formulas`, also lists, captions, graphics). The waiting blocks stay after the last piece, so once the piece that starts on the next page is a block of its own, a block of the earlier page follows a block of the later page.

- Hypothesis case (#196): i1 (p1) and i2 (p2) are one paragraph; i0 (p1, no position) waits after it; `find_formulas` cuts i2 out as a FORMULA. Pages of the blocks: 1, 2, 1, 2.
- **It also happens in the corpus**: nowak p9's page number "65" (FURNITURE) waited for the paragraph "Definition 13 … defined as:" + formula (24), which ran on to p10's "Definition 14 …". After the formula cut, "65" stands after the p10 paragraph: blocks 185 FORMULA (p9), 186 PARAGRAPH (p10), 187 FURNITURE "65" (p9). This is the only backward step in the 7 papers (checked before `find_headings` on each).

## Change

One pass in `layout/build.py`, after `find_lists` and before `find_headings` (no step after it cuts blocks; `find_headings` builds index-based sections, and `link_captions` links by items, so indices stay right):

- `_in_page_order(blocks, content)`: walk the blocks; a block whose first item is on an earlier page than the block before it moves back to just after the nearest earlier block whose first item is on its page or before. Blocks already in page order don't move, so the pass is a no-op wherever the property holds today.

Read as a rule: what waited for a paragraph follows the piece of it that starts on its own page. In nowak, "65" moves to just after formula (24), the end of p9. In the Hypothesis case, i0 follows i1.

### Alternatives considered

- **A. Lines without a position end the open paragraph** (like a formula does): fixes only the Hypothesis case, not nowak, and changes how such pages read. Rejected.
- **B. Each cutting step re-seats what followed the block it cut**: the same rule written four times (formulas, lists, captions, graphics), and a future cutting step would have to remember it. Rejected in favour of one pass that holds the invariant for all of them.
- **C. Restate the property** (allow a waiting block after a later page): it would bless "65" being read after p10's text. Rejected.

## Tests

- The Hypothesis case as an `@example` on `test_layout.py::test_layout_never_fails_and_keeps_every_line` (seen failing first).
- Unit test on made-up pages: a figure at the foot of page 1 waits for a paragraph that runs on to page 2 and holds a numbered formula on page 2; the figure follows the piece that starts on page 1, and blocks are in page order.
- A unit test that blocks already in page order are left as they are (identity).
- Golden: `test_layout_corpus.ambr` changes by exactly that one move in nowak (block "65" from after the p10 paragraph to after formula (24)); `test_layout_tagged_corpus.ambr` unchanged. Spoken-script diff on the 7 papers (`sci2audio script … --chapters all --ignore-settings`), main against the PR; I expect no change since furniture is not read, and will report what it shows.
- Layout tests under the nightly Hypothesis profile.

## Size

About 25 lines of code, 50 lines of tests, one golden hunk. PR `layout: blocks stay in page order after a paragraph is cut (#196)`, risk:high (golden), lane:layout; Closes #196.

## Decisions to log

- Q1 (#196): enforce page order with one pass before `find_headings`: a block that waited for a paragraph moves back to just after the nearest earlier block on its page or before. Recommended over A, B and C above.
- Q2 (#196): accept the nowak golden change ("65", p9's page number, read at the end of p9 instead of after p10's first paragraph).
