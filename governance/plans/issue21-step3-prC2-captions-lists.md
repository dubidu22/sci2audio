# Issue #21 step 3, PR C2: captions and list items (plan for approval)

This follows the PR C plan approved on 12 Nov at 18:40 UTC (D-85, D-86), and its C2 section is unchanged except for the refinements listed below. The PR is critical because it changes the layout golden file.

Note: I built C2 on a local branch while C1 was in review. Nothing is pushed or opened. If you change the plan, I will change or drop that code.

## Modules (lane:layout)

- `layout/captions.py`: `find_captions(blocks, content)`.
- `layout/lists.py`: `find_lists(blocks, content)`.
- `layout/split.py`: `split_at(block, cuts)` cuts a block before some of its lines. Each piece keeps the parts that start in it, and the text stays exactly as found.

`build_document` runs paragraphs, then footnotes, then captions, then lists, then headings. Captions and lists run before headings because they can cut blocks, and the section tree holds block indices. Headings only look at PARAGRAPH blocks, so they are unchanged: 73 of 75, with the same tree.

## Captions (as in the plan)

A PARAGRAPH block is a caption when it opens with Figure, Fig., Table or Algorithm (or FIGURE, FIG., TABLE, ALGORITHM), then a number such as "1", "A.2", "S3" or "2.1". After the number comes either ":" or "." followed by white, or a bold label whose line is not all bold ("Algorithm 1 CKY"). The label is the name and number as printed, such as "Table 2".

"Figure 1 gives …" at the start of a block, and "see Table 2." inside a paragraph, stay paragraphs. Both are tested.

- **Refinement 1:** an algorithm caption ends where its numbered pseudocode lines ("1: …") start. Those lines stay a PARAGRAPH until PR D handles them (#38). Nowak's Algorithm 3 caption held "1: P′ ←− …".
- `describes` is not set. It moves to PR D (D-86).

## List items (as in the plan)

A list is two or more text blocks in a row, opening with markers of one style in sequence. The styles are:
- the same bullet: • ◦ ▪ ‣ or en dash;
- `1.`, `(1)`, `1)`;
- `(a)`, `a)`;
- `(i)`, `i)` (a "(i)" that comes after "(h)" is read as a letter).

A list starts at its first marker. Furniture, figures, captions and footnotes between two items do not end it, so a list can run across a page break or a float. A heading or an unmarked block ends it. A nested list of another style does not end the outer one. A block with one item per line is cut into one block per item. The label is the marker as printed.

- **Refinement 2 (set alike):** all items of one list have the marker standing apart from the text (its own piece, with a gap) or none do. Without this, hardt p1's numbered examples, which stand apart ("(1)", gap, "William went running."), would make a list with the paragraph after them, "(1) is understood as …", which has an inline marker.
- **Refinement 3:** the marker must be followed by text on the same line. This keeps nowak p2's formula numbers, read as "(1)\nX −→ a", out of lists. They belong to PR D.

## Results on the corpus

- Captions: 29 of 29 truth caption labels (10 tables, 14 figures, 5 algorithms) on the right pages, and no others.
- List items: 69 in total.
  - chi p9: 1–10 and 1–30, cut from 14 blocks into 40 items.
  - nowak: p2 bullets (5); p9 (i)–(iv), and (i)–(iv) with 2 nested bullets.
  - arsiwalla: p8 1–10; (i)/(ii) across the p2/p3 page break; p16 (i)/(ii).
- Not list items: hardt's examples (1)–(4), nowak p3 "(a) ξ (b) ξ", and liu "(a) (b)".
- Headings: unchanged.

## Tests

- **Corpus:** `test_the_captions_are_the_truth_captions` (per page, sorted labels), and footnotes, captions and list items all open with their label.
- **Unit tests (20):**
  - colon or full-stop labels; printed label forms;
  - bold label; plain label is running text;
  - "Figure 1 gives" and mid-paragraph "see Table 2." stay paragraphs;
  - algorithm caption cut; two-line caption;
  - bullets; a numbered block cut into items; a multi-line item;
  - letters and roman numerals; (i) after (h); a nested list;
  - one line is not a list; a list must start at 1; text between items ends the list;
  - named example vs. set-apart examples; a formula number on its own line.
- **Hypothesis:**
  - any list of 2 to 6 items in 5 styles, one block per item or all in one block;
  - any caption label with or without punctuation;
  - in the never-fails property on any content, labelled blocks open with their label.

## Size

About 230 lines of code and 330 lines of tests. 447 tests pass.
