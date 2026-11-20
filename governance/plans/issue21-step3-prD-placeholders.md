# Issue #21 step 3, PR D: tables, figures, algorithms and formulas (plan for approval)

This follows D-81, D-86 and the coordinator's conditions. It is critical because it changes the layout golden file. No code or tests are written until this plan is approved.

## Where we stand

All drawings and pictures are grouped into FIGURE blocks when they touch, and the text inside a figure or table is read as paragraphs. On the corpus this gives about 230 FIGURE blocks, against 15 truth figures:

- **Thin lines (125):** footnote rules (#51), table rules, boxes around algorithms and framed text, fraction and root bars, and page-foot rules (JOSS).
- **Small marks (25):** icons and the pieces of nowak's derivation trees.
- **Logos:** the JOSS logo repeated on every page.
- **Real figures:** split into pieces. hardt's 8 figures come out as 16 picture blocks in identical pairs, and their axis text is read as paragraphs ("-10", "Extrinsic").

## Proposed split: two PRs (open choice 1)

- **D1 (graphics):** figures, tables and algorithms as placeholders; `describes` (D-86); #38; #51. Truth: 15 figures, 10 tables, 5 algorithms.
- **D2 (formulas):** display formulas as FORMULA placeholders with their printed numbers; #34. Truth: 45 numbered and 6 unnumbered formulas.

Formulas are a different problem: finding math set apart from text, and numbers at the right edge. They also need their own golden review. D2 gets its own plan after D1 merges.

## D1 design

A new module, `layout/graphics.py`, runs after captions and before lists and headings.

### 1. Graphic groups and what they are

Each group of touching drawings and pictures (the existing grouping) is one of the following:

- **Rule:** a thin line (at most `rule_height` thick) standing alone.
  - A footnote rule joins the first footnote below it (#51).
  - A rule inside a table or algorithm region joins that block.
  - Any other rule joins the block read just before it (open choice 3). Its part starts at the end of that block's text, so the text is unchanged.
- **Repeated graphic:** the same box on at least `repeat_pages` pages (the JOSS logo). It becomes FURNITURE with role RUNNING_HEAD, as a repeated line would (open choice 4).
- **Figure:** any other group. Groups that overlap or nearly touch merge (hardt's picture pairs, nowak's tree pieces). The text lines inside the figure's box (axis labels, legends, tree labels) join the FIGURE block as parts. Their text is kept as found, one printed row per line.

### 2. Tables

A "Table N" caption names a table above or below it, in the caption's columns. The table's region:
- is bounded by the horizontal rules next to the caption (the top and bottom rules, booktabs style);
- or, if there are no rules, by the rows of smaller or cell-split lines up to the white before the next paragraph.

The text lines and rules in the region become one TABLE block. Its text is one line per printed row, with cells joined by a space (#38).

### 3. Algorithms

An "Algorithm N" caption and the numbered lines below it ("1: …" up to the last numbered line, with its "▷" comments), together with the box rules around them, become one FIGURE block. Each code line is one line of text, with its number first (#38). The caption stays a CAPTION block and describes this block.

**nowak Figure 1** holds Algorithms 1 and 2 side by side (open choice 2):
- **(a), recommended:** one FIGURE block for Figure 1 with both listings, each read line by line, left listing first. Three captions describe it: Algorithm 1, Algorithm 2 and Figure 1. A placeholder can then announce "Figure 1, with Algorithms 1 and 2", and a reference to any of the three finds the same block. `describes` stays a single index per caption; several captions may point at one block, which core allows.
- **(b):** two FIGURE blocks, one per algorithm. Figure 1's caption describes the first one, so the figure's second half is not named.

### 4. describes

Each caption describes the nearest placeholder of its kind on its page that has no caption yet, next to it in reading order (just before or just after it):
- Table to TABLE;
- Figure, Fig. or Algorithm to FIGURE.

A caption that finds nothing keeps `describes` None, and the corpus test names it.

### 5. #38 and the reading of placeholders

Placeholders are not read in v1.0 (D-55): a text step proposes the spoken notice. Keeping their text as rows and code lines meets #38's criteria in the golden file, so D1 closes #38.

## Tests (D1)

**Corpus truth:**
- TABLE blocks per page match the truth tables (10).
- FIGURE blocks per page match the truth figures plus the algorithms not inside a figure: 15 + 3 = 18, with nowak Figure 1 holding Algorithms 1 and 2.
- Every non-empty truth caption label has a caption that describes a block of the right kind on its page.
- No FIGURE block is a lone rule.
- Footnotes, headings, captions and list items are unchanged.

**Unit tests:**
- A footnote rule joins its note.
- A table between rules, read row by row.
- A table without rules.
- An algorithm with line numbers and comments.
- Two algorithms in one figure.
- A chart with axis text.
- A repeated logo.
- A rule between paragraphs.
- A caption above and a caption below its block.
- "Figure 1 gives …" describes nothing.

**Hypothesis:**
- On any content, every caption's `describes` names a placeholder (the Document already checks this).
- Generated pages with a table between rules and a caption are read as one TABLE that the caption describes.

**Golden file:** every changed line is explained, as before.

**Settings:** `rule_height`, a table's row gap, and a figure's text reach. Every new threshold goes in `LayoutSettings`.

## Open choices for the coordinator

1. Split PR D into D1 (graphics) and D2 (formulas). I recommend the split.
2. nowak Figure 1: (a) one FIGURE block that three captions describe, or (b) one block per algorithm. I recommend (a).
3. A lone rule with no table, algorithm or footnote around it joins the block read just before it. The alternatives are a FIGURE of its own, which would not match the truth, or a new furniture role, which is a core change. I recommend joining.
4. A graphic repeated on every page (a logo) becomes FURNITURE / RUNNING_HEAD. The alternative is a new role, which is a core change. I recommend RUNNING_HEAD.

## Size (D1)

About 400 lines of code and 400 of tests. The golden diff is large: about 230 figure blocks become about 30 placeholders, and the table and figure text moves into them.
