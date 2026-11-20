# Issue #58: a loose rule or mark joins the wrong block (plan)

Thread "Fix loose rule joining the wrong block", 13 Nov 2026. Layout lane, after #33 (PR #149,
f3dba5a), before #48. Critical (a golden file changes), so this plan waits for the
coordinator's approval. Measured on main f3dba5a with a local prototype (not pushed).

## 1. Today's rule (D-90, D-92, #51)

`graphics._loose` decides per group of graphics no caption took (each group is still a FIGURE
block of its own at that point): lines only or a mark at most `mark_height` tall "join", the
rest become figures. `graphics._place` then puts each joining group into the footnote just
after it in reading order, else the block before it (at the end of its text), else the block
after it. Nothing looks at where the graphic is printed. So in nowak p1 the underbrace of
"n times" (`p1-d7`, `p1-d8`, y ≈ 713), drawn inside footnote 1's line `p1-l48` ("| {z }"),
is read after footnote 2 and joins its end.

## 2. What the corpus shows (main f3dba5a)

- 158 graphics join a neighbour across the 7 papers. 13 of them lie wholly inside the box of
  one text line on their page: nowak `p1-d7`, `p1-d8` (in `p1-l48`), nowak `p10-d1`, `p10-d2`
  (in `p10-l34`, the same underbrace in the appendix), liu `p1-d97`, `p2-d115`, `p2-d121`,
  `p2-d128`, `p2-d133`, `p2-d135`, `p3-d200` (inline fraction bars), biggs `p1-d5`, `p1-d6`
  (an ORCID icon in the author line `p1-l6`).
- About 30 more (liu's fraction bars) lie 0.2 to 2.5 pt outside a line box: a bar printed
  between a numerator line and a denominator line touches both and is inside neither.
- The union of a block's lines on one page is a poor test: a paragraph that runs from the
  foot of the left column to the top of the right one covers most of the page. On main,
  liu p2 paragraph 61's union holds 20 loose graphics that belong to other blocks, and the
  footnote rules of chi p5 and p9 lie inside the union of the paragraph above them.

Prototype of the proposal below, compared with main on all 7 papers:

| graphic | main | proposal |
|---|---|---|
| nowak `p1-d7`, `p1-d8` | end of footnote 2, after `p1-l55` | footnote 1, just after `p1-l48` |
| liu `p1-d97` | paragraph 10, after `p1-l97` | same paragraph, just after `p1-l96` |
| biggs `p1-d5`, `p1-d6` | paragraph 2, after `p1-l7` | same paragraph, just after `p1-l6` |

Every block's kind, label and text are unchanged on all 7 papers, so the spoken scripts are
unchanged (checked again on the PR with the script diff from the layout review checks). The
other 8 graphics inside a line already stand just after it, or a formula takes them later.
The invariant "every block is what `kept(block, block.parts)` makes of it" (each graphic
stands where the text read before it ends) holds on main and on the prototype for every
block of the corpus, and in 1,500 Hypothesis examples.

## 3. Proposal

Before today's rule, a joining group whose whole box lies inside the box of one text line on
its page **stands in that line**: it joins the block that holds the line (after floats are
assembled, so a line taken into a table joins with it), read just after that line and after
any graphic already read there, with its start where the line's text ends. The block's text
is unchanged. A group inside no line keeps today's rule (footnote just after it, else the
block before, else the block after). If several lines hold it, the one with the smallest box
counts; on a tie, the one read first.

Where the line meets the next one with no separator (pieces of one printed line set close
together, #36), the graphic's start equals the next line's start; parts stay in reading
order, so `kept` and the formula cut (`formulas._flush`) keep it with its line.

## 4. Code shape

- `layout/graphics.py`: new `_hosts(items, state, actions)` (per page: joining group → the
  line it stands in); `_assemble` takes the hosted groups out of `_place` and a new `_stand`
  puts them after `_place`, using `split.part_ends`. Module docstring updated (D-90 now says
  "the line it stands in, else the footnote below, else the block before").
- `layout/split.py`: only if question 7 is answered (b).
- No new settings, no core change, no change to other stages.

## 5. Tests (written first, failing on main where they should)

1. Issue's case: a footnote whose second line holds a drawn underbrace (two thin drawings),
   followed by a second footnote: both drawings are parts of footnote 1 just after that line,
   at its end; both footnotes' texts unchanged (fails on main).
2. No-separator join: the underbrace stands in the first of two pieces set close on one row
   (no space between them): it stands between them, at the second piece's start, and
   `kept(block, block.parts)` returns the block unchanged; dropping the first piece (as a
   formula cut does) keeps the graphic with nothing before it (fails on main).
3. A group of two drawings (an icon) inside a line joins as a group; a group only partly
   inside keeps today's rule.
4. A rule touching a line box but not inside it (a fraction bar 0.4 pt below) keeps today's
   rule; a footnote rule above its footnote still joins that footnote.
5. Two lines whose boxes both hold the graphic: the smaller one wins.
6. Property (Hypothesis, `test_layout_never_fails_and_keeps_every_line`): every block equals
   `kept(block, block.parts, lengths)`, plus a strategy that draws thin drawings inside random
   line boxes, so the new path is exercised.
7. Corpus: golden file updated (see question 6); a direct corpus test that nowak `p1-d7` and
   `p1-d8` are parts of footnote 1, just after `p1-l48`.
8. Mutations: drop the host step; drop the "smallest box" choice; place at the line's start;
   each must fail a test.

Run before the PR: ruff, format, lint-imports, deptry, the fast suite, the nightly Hypothesis
profile on the layout tests, and the review checks (text at offset, reading order, spoken
script diff on the 7 papers).

## 6. Questions (numbered, with my recommendation)

1. **What "inside the box of a block's lines" means.** (A) inside the box of one of the
   block's lines; (B) inside the union of the block's lines on that page; (C) inside the
   union of two lines read one after the other in the same column. **Recommend A**: it is the
   only reading that names "the line it stands in", which the issue asks for; B claims rules
   of other blocks (section 2); C would take fraction bars between a numerator and a
   denominator line, where the line it stands in is ambiguous.
2. **Slack.** **Recommend none** (wholly inside, no new setting). A slack of 0.05 em would
   pull in about 30 liu fraction bars that touch two lines; nearly all go into formulas
   anyway, and the others already stand next to their line. Option stays open for v1.1.
3. **Unit.** (A) per joining group (the graphics drawn close together, read as one);
   (B) per graphic. **Recommend A**: an icon drawn in three pieces (waskom, biggs) stays one
   thing; nowak's two underbrace halves are separate groups and both land right.
4. **Position.** (A) just after the line, where its text ends; (B) just before it, at its
   start. **Recommend A**: it is what `kept` makes of a graphic ("where the text read before
   it ends"), so every block stays equal to `kept(block, block.parts)` and later cuts
   (formulas, lists) keep the graphic with its line. B would move the graphic to the end of
   the line before whenever `kept` runs.
5. **Which blocks.** **Recommend any block that holds the line**, whatever its kind
   (paragraph, footnote, caption, heading, list item, placeholder, furniture): it is the
   block the graphic stands in. Footnote rules and rules between blocks are inside no line,
   so they keep today's rule.
6. **Golden file.** Today a golden line shows `[first..last (count)]`, so the move shows only
   as footnote 1 `(6)` → `(8)` and footnote 2 `[p1-l51..p1-d8 (7)]` → `[p1-l51..p1-l55 (5)]`.
   (A) keep the format and add the direct corpus test; (B) also list each graphic part with
   its offset on its block's line (e.g. `graphics p1-d6@0 p1-d7@119 p1-d8@119`), in a
   separate format-only commit, so this and any later misplacement shows in the golden diff.
   **Recommend B**: the issue asks for the golden to show the move, and graphics are what
   D-90/D-92 keep referenceable. The format commit changes no behaviour; the review can check
   that stripping the new field gives today's file byte for byte.
7. **`split_at` at a no-separator cut.** No caller cuts there today (lists and algorithm
   captions cut only after a line break), but a cut at the start of a line glued to the one
   before would put a graphic standing in that earlier line into the next piece, since both
   start at the same place. (a) leave `split_at` and pin today's callers with a test;
   (b) make `split_at` keep parts in reading order, so a graphic before the cut line's part
   stays in the earlier piece. **Recommend (b)**, a few lines with a unit test; no corpus
   change (checked on the PR). If you prefer to keep this PR narrow, (a) plus a v1.1 issue.
8. **Scope.** `formulas._flush` keeps its own D-90 rule (a segment of graphics alone joins the
   block before it); with this change no corpus graphic reaches that path differently. No
   follow-up issues expected; anything found on the way gets one.

## 7. KB

After the code PR: one KB PR with the coordinator's D-numbers, newest first, "Decided
(Claude)", marking D-90 as refined ("a graphic inside a line's box stands in that line").
It merges after the queued KB PRs #38 to #44, keeping numeric order.

## 8. Size

About 60 lines in `graphics.py` (plus about 10 in `split.py` for 7b), about 200 lines of
tests, a golden update. Half a day including review checks.

## 9. Decisions (coordinator, 13 Nov 2026 14:15 UTC, under D-80)

- **D-329** (q1): a loose group stands in a line when its whole box lies inside the box of one
  text line on its page.
- **D-330** (q2): no slack, no new setting.
- **D-331** (q3): decided per joining group, not per graphic.
- **D-332** (q4): the group is read right after the line, where the line's text ends.
- **D-333** (q5): any block kind that holds the line.
- **D-334** (q6): the golden file lists each graphic part with its offset; the format change is
  its own commit.
- **D-335** (q7): `split_at` keeps parts in reading order at a cut with no separator.
- **D-336** (q8): no follow-up issues; `formulas._flush` keeps its D-90 rule.

Colin informed in the project chat: 2026-11-13 14:15:16 UTC.
