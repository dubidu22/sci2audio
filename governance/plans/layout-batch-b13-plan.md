# Layout batch B13: page edges, columns, fractions, figure speed (#156, #238, #322, #354)

Status: posted 19 Nov 2026 ~06:25Z by the B13 layout thread, **waits for the coordinator's approval** (critical batch, PLAN-04).
Base: main b6355cc (#616 merged; B12 #600/#611 merged). Batch plan: plans/next-batches-2026-11-19.md (D-776), rows 156/238/322/354, §3, §4.
Every claim below was measured on b6355cc with throw-away prototypes (scratch probes, nothing pushed). Item numbers are fixed (PLAN-03).

## 0. Summary and recommendation

| PR | issues | goldens / shared files that move | critical | review | may start |
|---|---|---|---|---|---|
| **PR 1** `layout/issue156-238-edges-columns` | #156, #238 | none: furniture identical on all 8 papers, `NOT_YET_COLUMNS` loses its one entry | yes (batch plan; furniture rule + corpus truth exception list) | Opus high | on approval |
| **PR 2** `layout/issue322-line-end-fractions` | #322 | liu layout golden (2 sites); textprep test files by block index only (`test_textprep_citations_links_corpus.ambr` liu rows renumbered, `test_textprep_rules_corpus.py` liu indices 52/132/133 → 50/130/131 or by search) | yes (golden) | Opus high | **after B9 merges** (B9 #414/#415/#402 rewrites the same citations golden; LANE-02) |
| **PR 3** `layout/issue354-figure-speed` | #354 | none (same figure groups, proven on 8 families + corpus) | no (perf only, goldens unchanged) | Opus medium | after PR 1; **not** waiting for B15 (§4.4) |

Recommendation: approve the split into three PRs. Changes to the batch plan: (a) #354 leaves PR 2 for its own PR 3 and does not wait for B15's limit decision; (b) PR 2 waits for B9 instead (shared golden); (c) B13 touches no sentence-set file at all (none of the four changes moves a corpus line that `tests/sentences/` reads), so B11 PR 2 (#468) no longer waits for B13 (§4 point 4 of the batch plan).

## 1. #156 smaller edge lines need stronger evidence (PR 1)

**Cause.** `furniture._Page.furniture`: an edge line set below `small` (0.95) of the body is a RUNNING_HEAD when its *shape* (numbers → `#`) stands at its height on `repeat_pages` (2) pages (D-326, D-328). Nothing else: no white, no coverage, no exact text. The issue's two cases (a `\small` continued table header with its first row 2 pt below on 2 of 6 pages; "Algorithm 1"/"Algorithm 2" at 0.9 at the top of two pages) are taken.

**Corpus today (measured).** Smaller heads taken by the shape rule: JOSS seaborn and pymedphys footers and their numbers (0.80, apart on 4/4 pages), PrivacyScore heads "N Max Maaß, Anne Laubach, Dominik Herrmann" / "PrivacyScore N" (0.90, 12 of 13 pages, apart on 11 of the 12; one odd page not apart).

**Change** (`furniture.py`, one new function `_small_heads` beside `_body_heads`; the shape rule in `_Page.furniture` is replaced by membership in that set):
156.1 A smaller edge line whose shape repeats at its height on `repeat_pages` pages (unchanged precondition) is a running head when **either**
- (A) *coverage*: such smaller lines **that are apart from the body** stand at that height (within `head_drift`) in that band, whatever their text, on at least `max(head_pages, head_share × pages)` pages (the D-322 pooling, per height as after review M1 of #149). The line itself need not be apart (the PrivacyScore page whose head has no white under it), but only apart lines lend pages; or
- (B) *short documents*: the line is apart from the body and its exact text (numbers too, D-323) repeats at its height on `repeat_pages` pages **and** on `head_share` of the pages. This is "exact text for short pages" from the AC: a 2-page paper with small heads keeps them (the existing test `test_a_body_size_head_needs_head_pages_but_a_smaller_one_does_not` stays green), "Algorithm 1"/"Algorithm 2" never pass (texts differ). The #458 page-number offset (`_texts`) is **not** used in (B), so "Algorithm 1" on page 3 and "Algorithm 2" on page 4 (same offset) do not pass either.
156.2 A smaller edge line that starts with a caption label ("Algorithm 1", "Table 3 (continued)", "Abb. 2"; the label pattern of `captions._LABEL`, exposed as `captions.starts_with_label(text)`) is never a running head by 156.1. Covers the residual "Algorithm 1/2/3 apart at the top of 3 of 4 pages". No import cycle: `captions` imports `code`, `split`; neither imports `furniture`.
156.3 No new threshold: (A) and (B) reuse `head_pages`, `head_share`, `apart`, `head_drift`, `repeat_pages`; the comments in `LayoutSettings` say that they now apply to smaller heads too. The module docstring's "Smaller lines keep the shape rule in v1.0 … (D-328, #156)" paragraph is rewritten.
156.4 Unchanged on purpose: the FOOTER rule (bottom `footer_band`, smaller or apart) and `_counted` page numbers. The first-row top band (#235, D-502, the issue's comment) is covered by the same rule because it goes through `Edges.band`.

**Measured:** a prototype of 156.1 gives the same furniture, line by line, as main on all 8 papers (the 156.2 guard can only remove heads; no corpus head starts with a label).

**Tests first** (`tests/unit/test_layout.py`, beside the #33 tests): the issue's two cases at 0.9 of the body (table header 2 pt above its first row on 2 of 6 pages; "Algorithm 1"/"Algorithm 2" at the top of pages 3 and 5, and of pages 3 and 4 for the offset); a small head on 6 of 7 pages stays furniture; alternating small author/title heads (PrivacyScore shape) stay furniture with one page not apart; a small head on 2 of 2 pages apart stays furniture (B), the same not apart is text; a small continued table header *with* 1 em white on 2 of 6 pages is text (B needs `head_share`); "Algorithm 1/2/3" apart on pages 2–4 of 4 is text (156.2); the first-row band case (small type area, D-502) with a continued table header is text. One test per stated condition so mutation can reach each: apart-only lending, per-height pooling, `head_share` in B, exact text without offset in B, the label guard.

## 2. #238 text inside a captioned figure is not counted as columns (PR 1)

**Cause.** `build.columns_per_page` counts columns from `reading_order(...).columns`, before captions and figures are known; on PrivacyScore p3 the diagram's labels stand in three columns inside the 12-drawing frame p3-d2 (127,153)–(485,314) above "Abb. 1: …" and the band between the frame's edges counts 3.

**Finding that limits the risk:** `Reading.columns` feeds `columns_per_page` only (grep over src), which only the corpus truth test calls. The reading order itself does not use the count, so no golden, snapshot or sentence moves.

**Change.**
238.1 `columns_per_page` builds the document first and collects the lines inside FIGURE blocks that a caption describes (`describes`); `_Layout.read` (or `reading_order`, via a new keyword `uncounted: frozenset[str]`) still finds gutters and reads with every line, but leaves those lines out of the two counting measures (`_text` share against the page's counted text, and `_filled`). Removing the lines altogether was tried and fails: on Nowak p5 the algorithm frame's lines are one side of the gutter, without them no gutter is found and the page drops to 1 column (truth 2).
238.2 Docstrings of `columns_per_page` and `reading_order` say what is counted.
238.3 `NOT_YET_COLUMNS` loses its entry (the dict stays, empty, with its comment, as `NOT_YET_ONE_BLOCK` does).

**Measured:** the prototype gives the truth's column count on every page of all 8 papers, PrivacyScore p3 included.

**Tests:** `tests/unit/test_layout.py`: a made-up page with a framed, captioned diagram whose labels stand in three columns above two-column body text counts 2; the same labels without a caption under the frame still count (the rule needs the caption); a page whose body is one column under such a figure counts 1. Corpus: `test_columns_per_page` with the exception removed.

## 3. #322 a line-end inline fraction is read in its line (PR 2)

**Cause (traced on liu p2).** Extraction gives the printed line "is within the energy gap σintOH = −(egsgν/12π)(me/m∗). Physically," as five pieces: l48 "is within … σint", l49 "OH = −egsgν" (numerator), l50 "12π" (denominator), l51 "me" (numerator, raised), l52 "m∗ . Physically," (denominator glued to the rest of the line). `order.by_rows` and `paragraphs.rows_of` compare a piece with the **last** piece of the printed line only: l50 sits under the bar, overlaps neither the bar nor "me" by half, so it starts a printed line of its own (block 17 "12π") and then a paragraph break cuts the sentence (block 18 starts "the dominance …"). Sorted by left edge, l52 (231.2) comes before l51 (231.4), so "me" is read after "Physically,".

**AC correction (please confirm):** the rendered page (pdftoppm crop, checked) prints −(e gs gν / 12π)(**me / m∗**): me is the numerator. AC-322.1's example "−egsgν 12π m∗ me" was read off the golden's order. The faithful reading, numerator before denominator as #202 reads every other fraction, is **"−egsgν 12π me m∗ . Physically,"**. I will pin that and say so in the issue.

**Change** (`paragraphs.py`, `build.py` passes the page's `Bars` to `rows_of`):
322.1 A text piece read after an open printed line joins it when it is the denominator of a piece already in the line: `geometry.fraction_bar` (the #202 predicate, unchanged) holds for one of the line's bars, a numerator piece in the line and this piece, **and** this piece's first letters lie inside the bar's width (within 0.1 em). The last condition keeps Nowak p10's underbrace ("| {z }" glyphs under two short brace rules p10-d1/d2, measured: without it the brace text moves into the sentence and Nowak's golden changes).
322.2 Inside a printed line, a piece whose first letters stand under a bar is read right after the piece standing over that bar, even when it starts further left (me before m∗).
322.3 The same two rules make liu p4's "U3 1 / 2πniU4 0 · mev2F∆2 / (q2Fv2F+∆2)" read numerator, denominator, numerator, denominator ("U3 1 2πniU4 0 mev2F∆2 (q2Fv2F+∆2), which dominates as the ballistic limit …"); the lone "2πniU4 0" paragraph goes. Not reached by this change: the paragraph break between "conductance ∝" (the p3→p4 paragraph's last piece) and the fraction; I will try the printed-line grouping of 322.1 against the whole row in the PR and, if it needs a rule beyond fraction bars, file it as a follow-up rather than widen the join.

**Measured (prototype of 322.1 + 322.2):** layout golden: only liu changes, at exactly these two sites (p2 blocks 16–18 → one paragraph "… σintOH = −egsgν 12π me m∗ . Physically,\nthe dominance …"; p4 blocks 46–48 → one); liu goes from 133 to 129 blocks, all later liu block numbers shift by 2 or 4. Fast suite: 3 failures, all liu by block number: the layout golden, `test_textprep_citations_links_corpus.ambr` (liu rows renumbered, edits unchanged), and `test_liu_s_list_without_a_heading_is_not_read_and_its_body_is` (hard-coded indices 52/132/133). No app, CLI, sentence-set or regression change. The two textprep test files are a test-only cross-lane touch (D-756 note, as B12 did); I will make the liu test find the list by its first entry "[1] " instead of fixed numbers, so the next layout change does not break it again.
322.4 LANE-02: B9 (textprep, implementing, critical) changes the citations golden that PR 2 renumbers. PR 2 starts after B9's PR merges, then regenerates from main (never hand-resolve). If B14 moves a corpus snapshot meanwhile: merge main and regenerate.

**Tests first:** `tests/unit/test_layout_paragraphs.py` (beside the #202 fraction-bar tests there): a made-up line ending in two inline fractions, the second numerator raised and its denominator glued to the rest of the line (liu's shape); a denominator starting left of its numerator; an underbrace (glyph text under two short rules) stays where it is; a fraction whose denominator is wider than the bar is not joined (the 0.1 em reach); the property test "every item in exactly one block" untouched. Golden: liu, two sites, each explained in the PR.

## 4. #354 grouping figures in linear time (PR 3)

**Measured on b6355cc** (one page, n drawings, `build_document`, CPU seconds): 100,000 rectangles at one spot cost 54 s at only 20,000 (quadratic: 0.86 s at 2,500); stacked full-width rules 18 s at 20,000; a staircase 14 s; a grid 0.9 s. cProfile: `order.figures` is 98 % of it. Cause: drawings are sorted by left edge and each is compared with every later one whose left edge is within reach of its right edge, so a pile of overlapping drawings compares every pair.

**Change.**
354.1 `order.figures` gives **the same groups** with a sweep along x: drawings in order of their left edge; those whose right edge is still within `figure_reach` of the sweep ("open") all touch each other across, so a new drawing joins exactly the groups of the open drawings whose heights reach its own. Open drawings sit in buckets by height (each bucket keeps its drawings by group), a drawing leaves when the sweep passes its right edge; a bucket that the new drawing's height covers wholly joins every group in it without looking at its drawings, the two end buckets check drawings group by group until one touches. Union-find as today; `Element` order and contents as today (groups in first-member order, graphics in input order, checked by a test).
354.2 Prototype result (same groups as `figures` checked on 8 families at 2,500 and 20,000 drawings: one spot, grid, spaced grid, stacked wide rules, stacked tall rules, staircase, random, glyph-like outlines): at 100,000 drawings the grouping takes 0.2 to 0.7 s, stacked page-tall rules 2.7 s; `build_document` of one page at 100,000 drawings then takes 1.7 to 5.1 s.
354.3 The rest of layout at 100,000 drawings: after 354.1 the growth from 12,500 to 100,000 drawings is 9× to 17× for seven families and 26× for glyph-like outlines (1,112 figures); cProfile names `core.document.Block.__post_init__` and `graphics._place`. In the PR I find the step that grows faster than linear; a layout step gets fixed in PR 3, a core one (`Block.__post_init__`, core lane, single-threaded) becomes an issue. The `assert_linear` test (below) must pass with its existing limit 32 in either case.
354.4 **Why PR 3 need not wait for B15.** The fix is exact and limit-independent: it makes layout linear in drawings whatever `MAX_PAGE_GRAPHICS` is, and today's limits (5 × 100,000) lay out in seconds (AC-354.2, measured in the PR on the real 0.2 MB file built with `pdf_maker`, number reported in the PR and on #355). B15 can then decide #355 on parent memory alone (option 1 or 2), and a lower limit only makes the test's sizes conservative. If the coordinator prefers the batch plan's order, PR 3 simply waits for B15 PR 1; nothing else changes.

**Tests:** `tests/unit/test_layout_figure_speed.py` (new): `assert_linear` on `build_document` of a one-page `Content` with n drawings (base n/8, n = 16,000 so the fast suite stays fast; CPU clock as `linear_time.py`), parametrized over one spot, stacked rules, staircase, glyph-like grid; a Hypothesis property test that the new `figures` gives the same partition as a plain all-pairs reference on random boxes (≤ 60 boxes, reach 0 to 4, touching edges included), which pins "exact, not approximate". A `benchmark`-marked test at 5 × 100,000 plus a `docs/baseline.md` row (a long pipeline step, tests.md table).

## 5. Files, size, CHANGELOG, process

- **PR 1:** `src/sci2audio/layout/furniture.py`, `captions.py` (one public helper), `build.py`, `order.py` (count keyword), `settings.py` (comments only); `tests/unit/test_layout.py`, `tests/unit/test_layout_corpus.py`; `CHANGELOG.md`. About 70 lines of code, 200 of tests.
- **PR 2:** `src/sci2audio/layout/paragraphs.py`, `build.py`; `tests/unit/test_layout_paragraphs.py`, `tests/unit/__snapshots__/test_layout_corpus.ambr`, test-only textprep files named in §3; `CHANGELOG.md`. About 50 lines of code, 120 of tests.
- **PR 3:** `src/sci2audio/layout/order.py` (+ any layout step found in 354.3), `tests/unit/test_layout_figure_speed.py`, `docs/baseline.md`; `CHANGELOG.md`. About 80 lines of code, 120 of tests.
- **CHANGELOG Unreleased (D-768):**
  PR 1: "Small lines at the top or bottom of a page are read unless they really are running heads (#156): a continued table header or an "Algorithm 1" caption set smaller than the text at the top of a page is no longer dropped from the listening script; small running heads and footers on most pages are still left out."
  #238 has no user-visible effect (the column count feeds no reading) and gets no line.
  PR 2: "A fraction at the end of a line is read in its place (#322): its denominator no longer becomes a paragraph of its own, and the sentence goes on after it."
  PR 3: "Pages with very many drawings lay out quickly (#354): grouping drawings into figures now takes about as long as reading them, instead of minutes for a page of 100,000 drawings."
- **Process:** tests written first and failing on main; fast suite + ruff + lint-imports + deptry before each PR; critical PRs (1, 2) get my own `ci:full` run green before review, label removed afterwards; one fix commit per review round; merge main, never rebase; ledger line per PR in `ledger/implementation.md`.

## 6. Not folded in (open layout follow-ups stay as they are)

#599, #603, #604, #612 untouched. The B12 audit's A2 note (code.py docstring mentions the player indent) rides with the next layout PR that touches `code.py`; none of B13's PRs does, so it stays with #603.
