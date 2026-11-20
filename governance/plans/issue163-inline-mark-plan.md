# Plan: #163 a mark drawn inside a line cuts its paragraph

Layout lane, after #195, #196, #199 (D-432, D-436). **Critical**: the corpus golden changes (liu, biggs), so this plan waits for approval.

## Cause (measured on main a37c18e)

`build._Layout.units` passes the page's reading order to `paragraphs.rows_of`, which joins neighbouring text pieces on one baseline into one printed line (`Row`). A graphic element read between two pieces ends the row being built, and the next piece starts a new `Row`. That second row starts mid-column, so `Paragraphs` ends the paragraph there.

- liu p2: row `[l44, l45]`, then Held FIGURE `d121` (a fraction bar inside `l45`), then row `[l46]` at x 155: "… σintOH = 1 22σtot" | "OH. It is a continuous Fermi sea …".
- liu p2: `[l121, l122]`, then `d133`+`d134` (the bars of "1/ℏ" and "∂Emq/∂q", one group, spanning `l122` and `l123`), then `[l123]`, then `d135` (inside `l123`), then `[l124 … l127]`. One printed line in three rows.
- liu p3: `[l64, l65]`, then `d200` (inside `l65`), then `[l66, l67, l68]`.

A mark read *after* a row ends (between two printed lines) does not cut a paragraph by itself: the Held figure waits for the open paragraph. It does set `Paragraphs.figure`, though. That makes a following line starting with "Figure 3 …" count as a caption after a float, which starts a new paragraph, and it feeds `_pauses` and `_resumes`. That cut would not happen without the mark.

## Change

1. **`paragraphs.rows_of` reads past a mark inside a printed line.** A graphic element read between two text pieces that join into one row (same column, `same_row`, as today) does not end the row when it is *minor* and its box lies inside the union of those two pieces' boxes. The row goes on, and the graphic follows the row as its own element. `rows_of` gets the body size as a new argument.
2. **`Held.inline`**: a minor graphic whose box lies inside the box of a text line on its page is held with `inline=True`. `Paragraphs._hold` lets it wait for the open paragraph without marking a figure (`figure` and `marked` stay as they were), so the paragraph runs on as it would without it. With no open paragraph it is emitted as today.
3. **One "minor" rule**: the test `graphics._minor` applies to a group (lines only, at most `line_width` thick, or no taller than `mark_height`, D-90 and D-92) moves to a shared helper in `layout/geometry.py`. Both `graphics` and `paragraphs` use it, so a graphic that reading order treats as inline is one that `graphics` would join to its host line (#58, D-329 to D-333).

Where the graphic ends up is unchanged: `find_graphics` still places it after its host line by #58's rule. Only the reading-order position it is held at moves, from between two pieces to right after the row.

### Open choices (my recommendation first)

- **Q1: "inside a text line" means inside the union of the two pieces it is read between**, when those pieces are one printed line. The issue's wording is "the box of a text line". liu's `d120` and `d133`+`d134` are fraction bars that span two extraction pieces of one printed line, so they are in no single piece's box, yet they cut exactly like the issue's cases. Alternative: one piece's box only, which leaves two of liu's cuts in place.
- **Q2: include change 2 (`Held.inline`)** although it changes nothing in the corpus. It is what "the paragraph runs on as it would without the graphic" asks for, and it closes the caption-after-a-float cut described above. Alternative: only change 1.
- **Q3: share the minor test** (change 3) rather than copying it. Alternative: a second copy in `paragraphs`, which could drift from `graphics`.

## Measured effect (prototype of 1 and 2, not committed)

Golden `test_layout_corpus.ambr`: chi, hardt, nowak, arsiwalla and waskom unchanged.
- **liu 146 → 134 blocks**, 4 hunks. The three paragraphs from the issue are joined, and so are four more cut the same way by inline fraction bars: "… = −egsgν" | "m∗ . Physically …"; "Lˆ = m0" | "4 (rˆ × vˆ …" | "… µB = eℏ" | "2me . The Berry …"; "… = " | "i∂δ(q−q′)" | "∂q δm,m′ + … velocity operator" | "is …" (the position and velocity operators); "… ∂δ(Eq−Eq′)" | "∂Eq . The Fermi …" | "… ∂Θ(EF−Eq)" | "∂Eq . Then …" (the tilt expansion).
- **biggs 82 → 78 blocks**: the author list, cut into 5 paragraphs by the ORCID icons drawn in its lines, is one paragraph.
- Section starts shift with the block indices; titles and levels unchanged.
- Adding change 2 on top of 1 changes no block in the corpus.

Spoken-script diff (`sci2audio script FILE --chapters all --ignore-settings`, 7 papers, main against the prototype): only liu and biggs change, and every change removes a paragraph pause mid-sentence. Side effect: the pieces of an inline stacked fraction now stand in one row, so `separators` joins them as it joins stacked pieces elsewhere, without a space: "eℏ2me" (was "eℏ" ⏎ "2me"), "∂Emq∂q", "iRmm′q[f(0)". "Em′q Rmm′q" (the join the issue asked to check) reads correctly. I propose a follow-up issue (v1.1, lane:textprep or layout) for reading inline stacked fractions. There is none yet.

## Tests

- Unit (`test_layout_paragraphs.py` or `test_layout_graphics.py`, made-up pages): a paragraph whose second line holds a drawn fraction bar between its two pieces is one paragraph, and the bar is in that block right after its line (acceptance criterion 2).
- A bar spanning two pieces of one printed line (the `d133` shape) keeps the paragraph whole.
- A bar inside a one-piece line, then a line starting "Figure 3 shows …" that goes on with the paragraph: one paragraph (change 2).
- Negative cases: a picture taller than `mark_height`, or a graphic not inside the pieces, still cuts as today. The graphic's block placement is unchanged.
- Mutations: drop each of changes 1 and 2, and check that some test fails.
- Goldens updated and explained per hunk in the PR, with the spoken-script diff on the 7 papers. Layout properties under the nightly profile.

## Size

About 60 lines of code, 100 lines of tests, golden hunks in liu and biggs. PR `layout: a mark drawn inside a line no longer cuts its paragraph (#163)`, risk:high, lane:layout; Closes #163.

## Decisions to log

- Q1, Q2, Q3 above (recommended: union of the two pieces; include `Held.inline`; share the minor test).
- Q4: accept the liu and biggs golden changes listed above, and file the inline stacked-fraction follow-up (v1.1).
