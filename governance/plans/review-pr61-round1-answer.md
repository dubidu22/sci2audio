# PR #61, answer to review round 1

New head: **749ab0f** (it follows bb8bc2f). I fixed or added tests for findings 1 to 5. Finding 6 is deferred as #62.

After this round, every count from round 0 still holds:
- 45 of 45 numbered formulas and 6 of 6 unnumbered formulas.
- FIGURE 17 and TABLE 10.
- Verbatim sentences 28 of 28.
- Captions, footnotes, headings and list items are unchanged.

Checks:
- ruff, ruff format, lint-imports and deptry are clean.
- 547 fast tests pass.
- The nightly profile passes on `tests/unit/test_layout*.py`: 307 tests in 113 s.

## Must-fix

1. **Trimmed text, fixed.**
   - `split.part_ends(block, lines)` now ends a line part at the next *line* part. A graphic part holds no text, so it never ends a line, wherever it stands.
   - The two liu lines are whole again in the golden file: p2-l69 "…ˆρ," and p2-l84 "…satisfies".
   - Tests added:
     - `test_each_line_stands_in_its_block_as_found` (corpus) checks every block: each line part's text equals `block.text[start : start + len(line.text)]`. Without the fix it fails on p2-l69 and p2-l84.
     - `tests/unit/test_layout_split.py` (new) has two unit tests for `kept`, one with a graphic at the text's end and one with a graphic where a line ends.
     - The same file has a property: any block of lines with graphics at line starts, at line ends or at the text's end, and any subset of its parts kept, keeps each kept line's text. Without the fix all three tests fail.

2. **Formula (14), fixed in the rule.** In `_chains`, a piece on a display line's row counts as display if it does not fill the column, as before, or if it starts at least `formula_indent` in, even when it reaches the edge. FORMULA "14" now holds both rows with their limits: p4-l16 to l25, ending "= I + P X P n = I + P P∗ = (I − P) −1\nn=0".
   - Unit test: `test_a_row_piece_reaching_the_edge_is_part_of_its_formula`. It fails without the change.
   - Corpus test: `test_a_formula_holds_all_its_pieces` checks that (14) holds exactly p4-l16 to l25, so no fragment is left as a paragraph.

3. **arsiwalla Eq. (2), fixed.** A new step, `_grown`, runs between `_chains` and `_graphics`. A loose graphic (one not in a FIGURE or TABLE block, within the column) that reaches into a chain's box, grown by `float_gap`, grows the box. Any other chain the grown box reaches joins the group. This repeats until nothing more is reached.
   - FORMULA "2" is now "AP\nObjP RelP\nRObj RRel (2)\nObjM RelM\nAM" and holds all 8 arrows, p13-d1 to d8. The six one-word paragraphs are gone.
   - Corpus test: `test_a_formula_holds_all_its_pieces` checks p13-l14 to l22 and d1 to d8 exactly.
   - Unit test: `test_a_diagram_its_arrows_join_is_one_formula`. It fails without `_grown`.
   - **New guard, found while doing this:** growth first pulled liu p3's inline "σ ext OH = σ sd OH + …" pieces (l102 to l105) into formula (7). Their own chain had been rejected before, but formula (7)'s fraction bars now reached it. A piece on a row of running text is now never a display line: running text is a non-display line starting at the column's edge or one paragraph indent in. With this guard, liu's golden changes only by the two restored letters.
   - Unit test: `test_inline_maths_on_a_row_of_running_text_stays_in_its_paragraph`. It fails without the guard.
   - The PR body's point 5 is corrected.

## Should-fix

4. **Done.** `MAX_SKIPPED_LINES` is 10, with the comment "2 at most in the corpus since #34".
5. **Done.**
   - New tests in `test_layout_paragraphs.py` drive `paragraphs()` directly with rows and a held block:
     - `test_a_caption_after_a_float_is_never_read_into_the_paragraph` covers the rule after a held FORMULA and after a held FIGURE. It fails without rule (a).
     - `test_the_lines_of_a_caption_s_float_do_not_end_the_paragraph_set_aside` uses a code row that fills its column, followed by an indented code row. It fails without rule (b), and also without rule (a).
     - `test_a_caption_after_a_formula_at_a_page_top_is_no_part_of_the_paragraph` is in `test_layout_formulas.py`. It covers the whole nowak p5 case on a made-up two-page document and fails without rule (a).
   - The body now says that rule (a) also applies after figures, with no corpus change.
   - I also tried letting float rows never *resume* the paragraph. That broke the nowak #34 sentence, because the continuation "takes O(N2…" stands under the caption in its column. So I reverted it, and rule (b) is unchanged.
6. **Deferred as #62.** It covers `_chains`' pairwise row-mates, `_graphics`' scan of every graphic per group and the new `_grown` loop. Corpus time is unchanged in practice.

## Golden change in this round (against bb8bc2f)

- **nowak:** 211 → 209 blocks. FORMULA "14" takes p4-l24 and l25, and two PARAGRAPH blocks are gone.
- **arsiwalla:** 324 → 318 blocks. FORMULA "2" takes the six terms and their arrows, and six PARAGRAPH blocks are gone.
- **liu:** 146 blocks, unchanged in number. Two PARAGRAPH texts each regain their last character, and the items are unchanged.
- **chi, hardt, seaborn, pymedphys:** unchanged.
- **Corpus total:** 1,322 (main) → 1,224. The PR body's cause list is updated:
  - 145 paragraphs became FORMULA blocks;
  - 6 paragraphs were cut at a formula;
  - 4 joins;
  - arsiwalla p16;
  - graphics: liu 17, arsiwalla 8.
