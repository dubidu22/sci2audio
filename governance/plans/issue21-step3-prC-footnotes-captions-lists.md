# Issue #21 step 3, PR C: footnotes, captions and list items (plan for review)

This plan follows D-81. It is critical because it changes the golden files and adds new kinds to the output. It waits for the coordinator's approval.

## Proposed split: two PRs

The plan approved under D-81 had one PR C. Each half below can be reviewed and merged on its own, and footnotes alone are a sizeable change, so I propose two PRs.

- **PR C1:** footnotes, which also covers #37 (a narrow footnote split into pieces).
- **PR C2:** captions and list items.

Both are in lane:layout and add the new module `layout/notes.py` (footnotes), then `layout/captions.py` and `layout/lists.py`. Each runs after paragraphs and headings in `build_document`, on the blocks and the content, like `headings.py`.

## C1: footnotes

**Footnote zone.** On each page, for each column, the zone starts at the footnote rule. The rule is a short horizontal drawing: under 1.5 pt high, narrower than half the column, and starting at the column's left edge in the lower half of the page. The zone holds the text of that column below the rule and above the page-foot furniture, set smaller than the body text.

**Notes.** All lines in the zone are joined and then split into notes. A note starts at a line that opens with a mark:
- a run of digits, or one of ∗ * † ‡ § ¶, set smaller or raised compared with the line;
- or a line that opens with the next number in the page's sequence.

A line without a mark continues the note before it. This joins #37's pieces ("1Datasets" / "and associated programs …" / "https://…"). A zone with text but no mark is one note with label "".

Each note becomes `BlockKind.FOOTNOTE`, with `label` = the mark as printed ("1", "∗", "10").

**Where notes go.** Notes stay where they are in the reading order: after the paragraph they interrupted, as step 2 already holds them. Linking an in-text mark to its note is a textprep job and stays out of this PR.

**No rule.** A page with no rule gets no footnotes. Every corpus page with a truth footnote has a rule, which I checked on the first note of each page. Notes found without a rule would be an Issue, not a guess.

**Truth test.** The test compares the per-page list of footnote marks with the truth `footnotes` (41 notes on 30 pages, including chi p13's note with no mark). The PR body states the count met. Each label is checked against the truth marks.

**Other tests.**
- Unit cases: rule plus one note; two notes; a note split into pieces on one baseline (#37); a mark as a smaller run; a note without a mark; no rule means no footnote; a footnote in the right column only; a small-text table at the page foot without a rule is not a footnote.
- Hypothesis: on any content, footnote blocks carry a label that is printed in their text, and every item is still in exactly one block.
- Golden files: the changed lines are FOOTNOTE kinds with labels, and blocks are joined where #37 splits occurred. The PR explains every changed line.

## C2: captions and list items

**Captions.** A text block is a caption if it starts with "Figure", "Fig.", "Table" or "Algorithm", followed by a number (`3`, `A.2`), and then either `:` or `.`, or the label is bold while the rest of the block is not ("Algorithm 1 CKY").

Running text such as "Figure 1 gives the accuracy …" stays a paragraph. The kind is CAPTION, with label "Table 2", "Figure 1" or "Algorithm 3".

**Where `describes` is set.** D-81 put `describes` in PR C. I propose moving it to PR D, because the table, formula and algorithm placeholders it must point at only exist there, and core refuses a caption that points at a non-placeholder. Figures from pictures and drawings exist today, but linking only those would be half the job.

**List items.** A list item is a run of at least 2 consecutive lines or blocks that open with markers of one kind in sequence:
- `•` `◦` `–`,
- `1.` `2.`,
- `(a)` `(b)`,
- `(i)` `(ii)`.

Each item becomes LIST_ITEM with label = the marker as printed. A block holding several items, such as chi A.1 "1. First Party …\n2. Third Party …", is split at the markers. A lone "(1)" in running text ("(1) is understood as …") is not a list item, because it breaks the sequence.

**Tests.**
- Truth: every non-empty caption label in the truth tables, figures and algorithms is a CAPTION block on its page, and there are no other captions. That is 29 labels: 10 tables, 14 figures and 5 algorithms. Figure labels "" have no caption.
- List items have no truth data, so they get unit cases and golden lines only.
- Hypothesis: labels are found in their text, and list items never span two lists.

## Size

- C1: about 250 lines of code and 250 of tests.
- C2: about 250 lines of code and 250 of tests.

## Open choices for the coordinator

1. Split PR C into C1 (footnotes) and C2 (captions and lists), as above, or keep it as one PR. I recommend the split.
2. Move `describes` from PR C to PR D. I recommend the move.
