# Plan: layout PR D2, display formulas as placeholders (Issue #21 step 3, #34)

Author: layout thread "Build PDF extraction and layout stage", 12 Nov 2026, after D1 (#57) merged as 84dc299.
Status: **waiting for the coordinator's approval** (critical: it changes a golden file). No code or tests before approval.

## Goal

Display formulas become FORMULA placeholder blocks, and each numbered formula carries its number as printed in `Block.label` ("1", "16a", "A.2", without the brackets). D-81 set this, and D-88 split it into D2. D2 also fixes #34: Eq. (16a–f) on nowak p5 spans both columns, and today it is read as pieces of the left and right columns.

## Truth targets

Every target is checked by a corpus truth test.

- **45 numbered formulas.** On each page, the FORMULA labels read in order equal the truth `formula_numbers`:
  - nowak 33: p2 1–9; p3 10, 11; p4 12–15; p5 16a–16f; p8 10, 11 again (restated) and 17–20; p9 21–24; p10 25, 26;
  - arsiwalla 4: p12 1, p13 2, p14 3, p16 4;
  - liu 8: p2 1–4, p3 5–8.
- **6 unnumbered formulas**, per page as in `unnumbered_formulas`: nowak p4 1 (Eq. (9) shown again); arsiwalla p13 3, p15 1, p16 1.
- **No false formulas:**
  - chi, hardt, seaborn and pymedphys have no FORMULA block;
  - hardt's numbered language examples (1)–(4) on p1 stay text.
- **#34:** the nowak sentence "Pre-computing γ and δ in lines 10–14 takes" comes out inside one block, and `NOT_YET_ONE_BLOCK` is empty. Verbatim sentences go from 27 of 28 to 28 of 28.
- **Unchanged:**
  - 10 TABLE blocks;
  - 29 of 29 captions naming a block of their kind;
  - footnotes 41 of 41, headings 73 of 75, list items 69;
  - furniture tests in both directions.
  - FIGURE blocks go from 18 to 17 if choice 2 below is approved, otherwise they stay 18.

## Design

**Module.** A new module `layout/formulas.py`, `find_formulas(blocks, content, body, settings)`, runs after `find_graphics` and before `find_lists`. By then captions have taken their figures' and tables' text, so axis labels and table cells cannot be mistaken for formulas.

**An equation number** is a line whose whole text is `(N)`, where N is a number as printed: `\d{1,3}[a-z]?`, also `A.2` and `S1`, as for captions. It ends within `number_reach` of its column's right edge. Extraction splits a line at a wide gap (#27), so a number standing apart is a line of its own. A number at the end of a longer line ("ξ(X′ | X) · p(X′→Y Z) (9)", nowak p2; one liu line) counts only when that line starts at least `formula_indent` in from the column's left edge. This rules out running text that happens to end with "(3)" at the right margin.

**A display line** is a line in a PARAGRAPH block that:
- starts at least `formula_indent` in from its column's left edge; and
- does not fill the column (`fill_slack`), apart from a number at its end.

Running text starts at the column edge, or one paragraph indent in.

**A display group** is display lines and number lines chained within `float_gap` of each other, between running text above and below. It also takes:
- the sub- and superscript lines set smaller (`k−1`, `Y,Z∈N`);
- the graphics joined to blocks that stand inside the group's box grown by `float_gap`: liu's fraction and root bars, arsiwalla's arrows of Eq. (2), nowak's underbraces in its formulas. In D1 these joined the paragraph before them.

**Formulas in a group.**
- Each number in the group makes one formula. Each row of the group goes to the number row nearest it by vertical centre, so aligned equations with a number per line (16a–f) are six formulas. A two-row formula under one number, like (14), is one formula.
- A group without a number is an **unnumbered formula** only if at least `math_share` of its letters are set in a math font or are math symbols (Unicode category Sm). This keeps a centred quotation or title out. The math font names are a setting, `math_fonts`: CMMI, CMSY, CMEX, CMBSY, MSAM, MSBM, EUFM, RSFS, STIX math, Symbol, Cambria Math. They are a list of names, like `section_names`.

**Block.** Kind FORMULA, and label = the number as printed, without brackets ("" when unnumbered). The text is its lines read row by row, each line as found and the number included, the same as D1's placeholders (D-57). Its graphics are parts where they are read.

**Where it stands (choice 1).** The formula stands where it is printed. A paragraph that holds it is cut there:
- the lines before it stay that paragraph;
- then the FORMULA;
- then the lines after it are a new PARAGRAPH, with each line's text unchanged.

**#34, the cross-column formula (choice 4).** This is fixed in the reading-order step (`order.py`), before columns are found:
- A number standing at the text area's right edge gathers, as above, the math lines on its rows and the rows chained to them within `float_gap`, on a page whose bands have two columns.
- If the gathered box is wider than `wide` of the text area, it becomes one Element made of those lines. It cuts the page into bands, as a full-width figure does.
- `build.units` turns it into a held FORMULA block (a `Held` unit, like a figure). An open paragraph passes over it and goes on, as it does over a float at a page's top, so the p4 to p5 sentence joins up.
- `find_formulas` then cuts it into one formula per number (16a–f).

**Settings.** All new settings live in `LayoutSettings`, with these defaults:
- `formula_indent` = 2 em: a display line starts at least this far in from its column's left edge.
- `number_reach` = 0.5 em: an equation number ends this close to its column's right edge.
- `math_share` = 0.5: an unnumbered display group has at least this share of math letters.
- `math_fonts` = the tuple above.
- Reused: `float_gap`, `wide`, `fill_slack`, `size_change`, `row_overlap`.
- The defaults are set from the truth, and I state any later tuning in the PR body.

## Open choices, each with my recommendation

1. **Where a formula stands, and what happens to the paragraph around it.**
   - **Recommended: in place.** The paragraph is cut, with the text before the formula, then the formula, then the text after it as a new paragraph. This is faithful to the page, and it follows D1, where a placeholder stands where its first line was read. A later version that reads formulas will find each one where it is referenced.
   - Alternative: hold the formula until its paragraph ends, as figures are. The sentence around the formula then stays in one block, but the formula moves after text that follows it on the page.
   - Cost of the recommendation: a sentence that runs through a display formula ("is defined as: [formula] where …") is in two blocks. Textprep can handle this later. If a truth verbatim sentence runs through a display formula, I name it in the PR and file an issue; I don't expect any.
2. **arsiwalla Eq. (4) on p16 is a picture with an equation number.** The truth counts it under both `figures` (label "") and `formula_numbers`. One block cannot be both.
   - **Recommended:** a FORMULA labelled "4" that holds the picture, because the text refers to it as Eq. (4). The corpus figure test gets a one-line exception, `NUMBERED_AS_FORMULAS = {(arsiwalla, 16): "4"}`, like D1's `ALGORITHMS_IN_FIGURES`, and FIGURE blocks become 17. The truth file is unchanged.
   - Alternatives: keep the FIGURE and make "(4)" a FORMULA of its own with only the number in it (an empty formula, and the picture loses its number); or give FIGURE a label (a core change).
3. **Aligned equations with several numbers** (16a–f, and nowak (10) and (11)).
   - **Recommended:** one FORMULA per number, with rows going to the nearest number row. Each block then carries its own printed number, so "Eq. (16c)" can point to one block, and `label` stays a single value.
   - Alternative: one block for the whole display, which needs several labels (a core change).
4. **How #34 is fixed.**
   - **Recommended:** in the reading order, anchored on the equation number, as above. The number makes the rule specific; without it, any cluster of small pieces could become a band.
   - Alternative: a general rule that lets narrow pieces crossing a gutter merge into one element. That rule is broader, and it risks merging table cells or a figure's labels.
5. **Unnumbered formulas, and how wide to cast the net.**
   - **Recommended: conservative.** Only display groups in PARAGRAPH blocks, after captions took their floats, with `math_share` ≥ 0.5.
   - A missed unnumbered formula stays a paragraph with its text unchanged. A false one would turn text into a placeholder that is not read aloud (D-55), and that is the worse failure. So the test is exact on the truth counts (6), and any miss is named in the PR with an Issue.
   - Display math inside footnotes and list items is left as it is. The truth has none numbered there, and nowak's footnote formula stays as it is (#58).

## Core and contracts

- **No core change.** `BlockKind.FORMULA` exists, `label` is already allowed on formulas (D-81), and `describes` may already point at a FORMULA.
- **No layer-contract change.** The changes are inside `layout/`: `formulas.py` (new), `order.py` (wide formula element), `build.py` (held formula unit, pipeline order) and `settings.py`.
- The PR is critical only because of the golden file (D-69), so it is `risk:high`.

## Golden impact (estimate; the PR body gives exact counts by cause)

I measured today's corpus with a script:
- **About 120 paragraphs made only of formula pieces become FORMULA blocks:** nowak about 80, liu about 26, arsiwalla about 13.
- **About 55 paragraphs holding running text and formula lines are cut at the formula:** nowak 34, liu 19, arsiwalla 3. Their text before and after is unchanged, now in two blocks.
- **Graphics move from paragraphs into formulas:** liu's 23 fraction and root bars, arsiwalla's 4 arrows of Eq. (2), and nowak's 2 underbraces in display formulas (not the footnote's).
- **arsiwalla p16:** FIGURE becomes FORMULA "4" (choice 2).
- **nowak p5:** the reading order changes (#34). The formula comes once as 16a–f, and the paragraph from p4 now joins across the page.
- hardt has 4 lines that look like numbers ((1)–(4), at the left); they are unchanged.
- No other paper changes. Captions, tables, footnotes, headings, list items and section titles are unchanged; a test and the PR body check this.

## Tests

- **Corpus** (`test_layout_corpus.py`):
  - formula labels per page equal the truth numbers, in order;
  - unnumbered FORMULA blocks per page equal the truth counts;
  - no FORMULA in the four papers without formulas;
  - the figure test gets the choice 2 exception;
  - `NOT_YET_ONE_BLOCK` is empty;
  - all D1 counts are unchanged.
- **Unit** (`test_layout_formulas.py`, about 14 tests, each on a made-up page):
  - a one-line formula with its number standing apart;
  - a number at the end of an indented line;
  - a formula with a sum's sub- and superscript rows;
  - two rows under one number;
  - aligned rows with a number each;
  - a paragraph cut at a formula, with both texts unchanged;
  - running text ending "(3)" at the right edge is no formula;
  - numbered examples at the left edge are no formulas (hardt);
  - a centred math line with no number is an unnumbered formula;
  - a centred quotation is not;
  - a fraction bar inside a formula is its part;
  - a picture with an equation number is that formula;
  - #34's case from the Issue: a two-column page with a full-width numbered formula between the columns reads both columns in order and the formula once, and a paragraph runs on across it.
- **Property:** any one- to three-row formula with numbers in a column, between paragraphs, gives one FORMULA per number with the label as printed, and the paragraphs' text is unchanged. The existing never-fails property (every item in exactly one block, text as found) keeps running, under the nightly profile as well, before the PR opens.

## Size and risk

- About 350 lines in `formulas.py`, about 60 in `order.py` and `build.py`, and about 500 lines of tests.
- Risks:
  - Display detection on other papers (single-column papers, papers set in other fonts). The rules are geometric, anchored on numbers, and math fonts are only a setting for unnumbered formulas.
  - The order change on two-column pages. It applies only to number-anchored groups wider than `wide`.

## Out of scope

- Reading formulas aloud (D-55, v1.1).
- Display math in footnotes and list items.
- #58, #59 and #60 from D1.
- Inline maths, which stays running text.
