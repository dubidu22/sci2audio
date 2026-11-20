# Extraction batch B18 "Letters from glyph shapes": plan (#442 part 3)

**Approved D-789, 19 Nov 05:25Z** (coordinator): q1 to q9 as recommended, Carlito (OFL-1.1) included (drawings are output, not the font; one `THIRD_PARTY_LICENSES.md` row per family, licences confirmed at the source in the PR). Conditions: the close-call step is proven on the c/e fixture (the test fails with the word step patched out); if it does not settle c/e, use the bigram fallback and say so in the PR body. AC-442.13 is a measure, not a merge gate. PR 1 critical (Opus high review), PR 2 non-critical (Opus medium), both after B15 merges. D-402 amendment flagged to Colin.

Thread: "Plan glyph-ID text recovery for unreadable fonts", started 19 Nov 2026 04:53Z (D-788). Planning only: no branch, no PR, no GitHub issue yet. Base read: main e658c17. Runs after B14 (#609) and B15 (#355 #367 #356), because B15 also changes `extraction/pdf.py` and `isolate.py`.

**Recommendation in one paragraph.** Recover the letters of a font with no Unicode source by **the shape of its glyphs**, not by its glyph numbers: read each used glyph's outline from the embedded TrueType program (a small, bounded reader of our own), draw it on a 48 × 48 grid, and compare it with precomputed drawings of the same characters in open fonts that are **metric-compatible** with the common Office fonts (Tinos ≈ Times New Roman, Arimo ≈ Arial, Cousine ≈ Courier New, Carlito ≈ Calibri, Caladea ≈ Cambria). Metric compatibility means every character has the same advance width as in the original, so the width picks the family and narrows each glyph to a few candidates; the shape picks among them; a one-letter-per-glyph rule and a closed list of common English and German words settle the few close calls. The text is accepted per font only when the shapes match closely and every page then passes the existing `legibility` check; otherwise extraction keeps today's glyph numbers and part B still stops. Recovered characters are counted in a new additive field `Page.recovered`, and the report and document page always say "recognised from the letter shapes, may hold mistakes" (PR 2, app lane). A prototype on Colin's file (measure only) read the Calibri title, the Calibri italic and bold lines and the Symbol bullet correctly, and 77 to 78 of the 79 Times New Roman glyphs. The remaining pair, c and e, has the same width and nearly the same shape; the word step is meant to settle it, and the prototype has not yet shown that it does (§3.4 step 5). Glyph-order tables (the issue's own idea) were measured too and rejected: the standard order covers only part of Times New Roman, and Calibri's order exists only in Microsoft's font. This is **critical**: it adds a core field, reverses D-402 ("extraction never guesses") for this one case, ships data derived from third-party fonts, and parses untrusted font programs.

All numbers below were measured in this thread on Colin's file `uploads/hearth/718963ef-…` (3 pages, measure only, never committed or quoted beyond a few words), with pypdfium2 5.x and main e658c17's `read_pdf`, in a scratch venv on CPython 3.12. Prototype scripts: `plans/b18-probes/` (`p1.py` fonts and glyph orders, `p5.py` width check, `p6.py` shape matching, `shape.py` its drawing and distances). They use fontTools for convenience; the plan does not.

## 1. What the file holds, and what today's code does with it

| font (all CID TrueType, Identity-H, no ToUnicode) | glyphs in program | drawn (non-empty) | used | characters |
|---|---|---|---|---|
| TimesNewRoman (body) | 3,414 | 80 | 82 | 8,596 |
| Calibri (title block) | 3,878 | 32 | 33 | 89 |
| Calibri,Italic | 3,948 | 9 | 11 | 15 |
| Calibri,Bold | 3,878 | 8 | 10 | 12 |
| Symbol | 192 | 2 | 2 | 6 |

- The subsets **keep the original glyph numbers** (3,414 slots, 80 drawn), and `/CIDToGIDMap /Identity` holds: the width PDFium gives each character (loose box ÷ font size) equals the program's advance for glyph = code in 7,773 of 7,845 Times characters within 2 % (median 1.000; the rest are italic boxes). So "code = glyph number" can be **checked**, not assumed (§3.2).
- Every program has `glyf`, `loca`, `hmtx`, `head`, `hhea`, `maxp`, no `cmap`, no `post`. **The `hmtx` tables are truncated** (Times: 641 long metrics present, the left side bearings of the other 2,773 glyphs missing). fontTools refuses the font for this (`TTLibError: not enough 'hmtx' table data: expected 8110 bytes, got 2564`), so a strict font library would fail on exactly the files this batch is for.
- **Characters are lost today, not only garbled.** PDFium gives the glyph number as the character, and `_char_text` drops every code that is white space or a control character as a word break, before `_SourcelessFonts` is asked. In Times New Roman's order that is every digit, `,` `.` `-` `/` `:` `(` `)` `&`, `ü` (glyph 129 = U+0081) and `ß` (137 = U+0089): **339 of 6,941 drawn characters (4.9 %)** never reach `Content`, so "u.a." reads as "X D" and "Fülle" as ") OOH". Part A's `Page.unmapped` does not count them either. B18 fixes this as part of recovery (§3.1).

## 2. Approaches measured

| | approach | measured on the file | verdict |
|---|---|---|---|
| A | **standard glyph order** (Apple's 258 standard Macintosh glyph names, the order most Monotype fonts start with) | Times: 75 of 79 right (ASCII, äöüÜß), 4 wrong: from slot 172 on Times New Roman is one slot behind the standard (en dash at 177 not 178, „ at 196 not 197, “ 179, ‘ 181). Calibri: 0 (its order is its own: e = 286, i = 349, n = 374). | rejected as the method: covers only fonts in that order, and gets the punctuation wrong in the one font it fits |
| B | **glyph-order tables per named font** (Times New Roman, Arial, Calibri), the issue's proposal | not buildable here: the tables would be derived from Microsoft's font files, whose licence is not on the allowed list (licence gate rule 3: unclear), and glyph orders change between font versions | rejected |
| C | **shape matching** against metric-compatible open fonts (§3) | Times: 77 or 78 of 79 glyphs right, depending on the distance used; the remaining confusion is c ↔ e (same width, Times' thin bar). Calibri, Calibri Italic, Calibri Bold: every glyph right ("Gemeinwesenarbeit als Arbeitsprinzip: Jaak Boulet, Jürgen Krauss, Dieter Oelschlägel"), once the family is chosen by width and shape together. Symbol: bullet right. `„ “ ‘ –`, umlauts and ß: right (the file holds no ligature glyphs). | **recommended** |
| D | **decipherment by letter statistics** alone (a substitution cipher solved with n-grams) | not prototyped: needs far more text than a 3-page excerpt for 82 symbols, cannot tell case, digits or punctuation | rejected as the method; a closed word list settles close calls in C (§3.4) |
| E | **OCR** of the rendered page (Tesseract or a model) | not tried | out of scope for v1.x (#187): a large external program or model, a new licence, and a second way to read every PDF |
| F | **PDFium draws the glyph** (`FPDFFont_GetGlyphPath`) | not usable: it takes a Unicode value and maps it through the font's own map, which these fonts lack; cropping glyphs from a rendered page mixes in neighbours | rejected (possible later route for CFF programs, §6) |

## 3. Design (decisions q1 to q9)

### 3.1 Where it runs (q1)

In extraction, inside the PDF child process (`isolate.py`, 1 GB watch, 60 s per step), because only extraction sees the font programs (D-63). Nothing changes for a PDF without a font with no Unicode source: the shape data is never loaded (a test pins this), and the corpus reads byte for byte as before.

`pdf.py` changes:
- `_chars` asks `_SourcelessFonts` **before** `_char_text` drops white space and control codes, for every character whose map error is set, so the 339 lost characters are kept as glyph numbers (code, font key) instead of word breaks. The map error is asked for every character today already; the new cost is the call for codes that are white space (measured on the corpus in the PR).
- `_SourcelessFonts` moves from per page to **per document** (a font recurs on every page; recognising it once needs all its glyphs). The first pass keeps, for a document that has such a font, the pages' `_Line`s unbuilt; after the last page the recogniser runs once per font, then the lines are built with the recovered text (`_text_line`, unchanged). Documents without such a font take today's path, unbuilt lines are never held.
- A glyph that draws nothing (empty outline, positive advance) is a space; glyph 0 stays U+FFFD as today.

New module `extraction/glyphs.py` (about 400 lines): the outline reader, the drawing, the matcher, the word step. New data file `extraction/data/glyph-shapes.bin` (about 0.6 to 1 MB compressed, §3.5), built by `scripts/glyph_shapes.py`.

### 3.2 Reading the font program (q2): our own bounded TrueType reader, no new dependency

Reads `head` (units per em, loca format), `maxp` (glyph count), `hhea` + `hmtx` (advances, **tolerating a truncated table**: missing advances take the last one present, as the TrueType spec says, missing side bearings are not needed), `loca` and `glyf`: simple glyphs (on/off-curve points, quadratic curves split into lines) and composite glyphs (offsets and the 2 × 2 transform; accents are composites). Limits, each refusing only that glyph: 64 contours, 4,000 points, composite depth 4, 32 components, offsets inside the table. A damaged program means "not recoverable" for that font, never a failed file (D-402's "never fails" stays). CFF programs (`OTTO`) are not read (§6).

Before recognising, the **identity check**: for at least 90 % of a font's characters, the advance of glyph = code (in the program) times the font size equals PDFium's width of the character within 3 %. A font whose `/CIDToGIDMap` is a stream (code ≠ glyph) fails this and is left as glyph numbers (pypdfium2 does not expose the map).

Alternative: fontTools (MIT) as a runtime dependency. Rejected: it refuses this file's truncated `hmtx` (§1), it is a large parser of untrusted input whose time and memory we do not bound, and it adds a dependency (infra lane). fontTools stays a tool for `scripts/` only, run with `uv run --with fonttools`, not in the lock.

### 3.3 Reference fonts and their licences (q3, licence gate)

| family (styles: regular, bold, italic, bold italic) | metric twin of | licence (to confirm at the source in the PR, rule 1) |
|---|---|---|
| Tinos | Times New Roman | Apache-2.0 (ChromeOS core fonts) |
| Arimo | Arial, Helvetica | Apache-2.0 |
| Cousine | Courier New | Apache-2.0 |
| Caladea | Cambria | Apache-2.0 |
| Carlito | Calibri | OFL-1.1 |

The prototype used Liberation Serif/Sans (Tinos/Arimo-derived, same metrics) and Carlito from the container. The PR ships **no font file**: only `glyph-shapes.bin`, the drawings and advances of about 420 characters per style (Basic Latin, Latin-1, Latin Extended-A, Greek, general punctuation `– — ‘ ’ ‚ “ ” „ • … ‰ ‹ ›`, `€ ™ − ± ≤ ≥ ∞ ≈ ≠`, ligatures `ﬀ ﬁ ﬂ ﬃ ﬄ`), 20 styles, built by `scripts/glyph_shapes.py` from pinned releases checked by SHA-256. A drawing made with a font is output, not the font (OFL FAQ), so rule 2's "OFL fonts unmodified" is not touched; still, `THIRD_PARTY_LICENSES.md` gets a row per family naming the release, licence and copyright, out of caution. **Coordinator's call** (rule 7: when unsure, ask): accept derived drawings from OFL-1.1 Carlito, or drop Carlito and leave Calibri to the no-twin path (§3.4; would lose the title block of this very file unless the no-twin path reads it).

### 3.4 Recognising a font (q4)

For each font with no Unicode source that passed the identity check, over all its used glyphs in the document:

1. **Family:** for every reference style, the share of the font's drawn glyphs whose advance equals some reference character's advance within 0.002 em, then the mean best shape distance among those. The best style with a share ≥ 90 % is the **twin**. Measured: Times → Liberation Serif Regular, Calibri → Carlito Regular, Calibri Italic → Carlito Italic, Calibri Bold → Carlito Bold (share 1.00 each; choosing by width alone picked the wrong style for the italic, so shape is part of the choice).
2. **Candidates:** with a twin, the twin's characters of equal advance (± 0.002 em); without one, every character of every style (shape only, the stricter acceptance in step 6 applies).
3. **Shape distance:** both glyphs drawn on 48 × 48 cells, x over the advance, y from 1.0 em to −0.3 em (keeps position: comma vs apostrophe, en dash vs macron); distance = mean of (a) cells that differ over cells inked in either, on the em grid and on the ink box scaled to 32 × 32, and (b) 1 − correlation of the same two drawings blurred. Plus a small prior: Basic Latin 0, Latin-1 and the punctuation above +0.01, Latin Extended-A +0.03, Greek and the rest +0.05 (measured: without it, Greek capitals and `ŧ` win ties with `T`, `ŧ` with `t`).
4. **One letter per glyph:** within a font, two different glyphs do not get the same character (assignment by increasing distance). Measured: this turned "c → e" into a c/e swap, so it is necessary but not enough.
5. **Close calls:** glyphs whose best two candidates differ by less than 0.05 and have the same advance are settled by a closed list of about 200 short common words, English and German (`der die und ist the of and …`, written for this repository, CC0), matched **case-sensitively** on the font's whole recovered text: the choice (or swap between two such glyphs) with more listed words wins, and only by a margin of 5 words or more. Measured, honestly partial: choosing per close call fixed one glyph of the c/e pair but not its partner (a swap was not tried), and an unrestricted swap search with case-folded words made it worse (every `e` became `E`). So the step is limited to close calls and swaps between equal-width glyphs whose other letter is among their three best shapes, and the PR must show on the fixture and on the file that this settles c/e (§4 "Close calls"). If it does not, the fallback is a bigram table of English and German letters from the CC0 corpus samples; the PR reports which was needed.
6. **Accept or refuse, per font:** accepted when the mean distance of its drawn glyphs is at most `MAX_MEAN` and no glyph is above `MAX_GLYPH` (values pinned in the PR from the fixtures and the file; prototype: twins 0.08 to 0.20 mean, 0.45 worst), with a stricter `MAX_MEAN` for the no-twin path. Then per page: the existing `legibility` measures run on the recovered text; a page that is still unreadable gets its characters back as glyph numbers (today's text), so part B stops or warns exactly as now.

Cost (to be pinned in the PR, `assert_near`): the prototype draws 4,676 reference glyphs in 13 s (hence precomputed data) and matches 150 glyphs in 0.6 to 27 s unvectorised; the PR matches all candidates of a glyph as one array operation. Bound: at most `MAX_RECOVERED = 2,000` distinct glyphs per document (beyond that, the rest stay glyph numbers and the report says so), and the child's step clock covers recognition (`isolate.report("recognising letters")`).

### 3.5 What `Content` records (q5, core: critical)

`core.Page` gets `recovered: int = 0`: how many characters of the page's lines were recognised from their glyph's shape (#442 part 3). Additive with an empty default, left out of exports at 0, so golden files and older exports read the same. On pages extraction makes, `recovered ≤ unmapped ≤ characters` (extraction's tests); `Page` itself refuses only a negative count, as for `unmapped` (the #574 lesson: `replace(page, lines=subset)` in textprep keeps the whole page's count; grep every `replace(` of `Page` in `src/` before adding any check). `unmapped` keeps its meaning (characters from a font with no Unicode source), now including the 339 formerly dropped characters.

`legibility`: the unmapped share becomes `(unmapped − recovered) / characters`; `PageLegibility` gets `recovered`. No run-level flag: nothing downstream needs to know which run was recovered, and splitting runs would move layout.

### 3.6 D-402 amended (q6)

D-402 says extraction reads garbled text as stored and never guesses. Proposed amendment: **for characters from a font with no Unicode source (D-762's rule), extraction may recognise letters from the glyph shapes; it records how many (`Page.recovered`), it refuses when unsure (§3.4 step 6), and the person is always told.** Every other broken encoding stays as D-402 says.

### 3.7 What the person sees (q7, PR 2, app lane)

- Report warning, first among warnings after the unreadable one: EN "Pages 1–3: the letters were recognised from their shapes because the PDF's fonts hold no text. The text may hold mistakes." / DE "Seiten 1–3: Die Buchstaben wurden an ihrer Form erkannt, weil die Schriften des PDFs keinen Text enthalten. Der Text kann Fehler enthalten." Page ranges as part B. JSON: `"recovered": {"pages": [1, 2, 3], "ranges": "1–3"}` at the end, only when a page has recovered characters.
- Document page step 1 notice (`document.recovered_pages`), not blocking.
- `app.readability.unreadable` unchanged in logic (it reads `legibility`, which now subtracts recovered characters).

## 4. Tests

Fixtures: the PR commits generated PDFs (each well under 100 KB) and their generator `scripts/glyph_fixtures.py`: a CID TrueType font, Identity-H, no ToUnicode, `cmap` and `post` stripped, `hmtx` truncated as Distiller does, glyph order **shuffled** (proves nothing depends on an order), from subsets of **Apache-2.0** fonts only (Tinos and Arimo for the twin path; for the no-twin path an Apache-2.0 font outside the reference set, picked in the PR after checking its licence at the source, since some Google families moved from Apache-2.0 to OFL), because rule 2 allows OFL fonts only unmodified and a subset is a modification. Text: the existing `GERMAN` and `ENGLISH` lines of `test_extraction_legibility.py` plus digits, `„…“`, `– ß ü`, `fi`, `(a.a.O. 5).` and a title line in bold and italic. Row in `tests/corpus/LICENSES.md` for each fixture font.

- **Recovery:** each twin fixture reads back its source text exactly (every character, spaces included), `unmapped == recovered == characters`, every page readable by `legibility`. The no-twin fixture: either exact or refused (glyph numbers, `recovered == 0`), never partly wrong text accepted; the PR states which.
- **Lost characters:** digits, `,` `.` `-` `/` `:` `(` `)` `ü` `ß` in a shuffled order that puts them on white-space and control codes are kept; with recovery refused (shape data patched empty) they are counted in `unmapped` (today: dropped).
- **Refusals,** each leaving today's text and `recovered == 0`: code ≠ glyph (`/CIDToGIDMap` stream, the identity check), shapes far from every reference (glyphs drawn as rectangles: the existing `truetype_program`), a program with `cmap` (part A's rule: not sourceless), a page still unreadable after recovery, more than `MAX_RECOVERED` glyphs (limit patched low).
- **Close calls:** a fixture whose c and e have the same advance reads right with the word step, and with the word step patched out the test fails (so the step is proven needed, the review lesson about mutants that survive).
- **Reader safety:** Hypothesis over random and mutated programs (truncated tables, offsets past the end, composite loops, 65,535 points): never raises, never exceeds the limits, `assert_linear` over glyph count; each limit refuses at limit + 1 and reads at the limit; `test_the_limits_are_the_decided_ones` pins every constant (`MAX_MEAN`, `MAX_GLYPH`, `MAX_RECOVERED`, the reader limits, the 0.002 em, 0.05, 5-word margins).
- **Corpus:** no corpus page has `unmapped` or `recovered` above 0; all goldens unchanged; `glyph-shapes.bin` is never opened while reading the corpus (patched to fail if opened); corpus PDF reading time unchanged within the benchmark noise (the extra map-error calls).
- **Data:** `glyph-shapes.bin` is rebuilt by the script from the pinned fonts identically (test compares its SHA-256 to the one the script prints; the slow test downloads nothing, it only checks the stored hash and the file's header: version, styles, characters).
- **Core:** `Page.recovered` refuses negative values, export leaves it out at 0, import of older exports gives 0; `core_strategies` generate it.
- **Colin's file (measure only, never committed):** the PR body reports characters right per page against a hand check of the first 1,000 characters and the title block, legibility per page, time and peak memory.
- PR 2: report and document page in EN and DE, JSON field present only with recovered pages, a recovered PDF is voiced (no stop), browser test of the notice.

Critical-PR extras (REV and CI rules): `ci:full` three systems on the final round, mutation probing of `glyphs.py` (thresholds, assignment, word step, identity check, reader limits).

## 5. Acceptance criteria (proposed for the issue)

- **AC-442.5** A PDF whose fonts have no Unicode source (D-762's rule) and pass the identity check is read with letters recognised from the glyph shapes: on the committed twin fixtures (Times-like and Arial-like, shuffled glyph order, truncated `hmtx`) the text equals the source exactly.
- **AC-442.6** Recognition refuses rather than guesses: a font whose shapes match no reference closely, whose codes are not its glyph numbers, or whose page is still unreadable by `legibility` keeps today's text, and part B stops or warns as now.
- **AC-442.7** Characters that PDFium gives as white space or control codes for such fonts (digits, comma, period, `ü`, `ß` in the usual TrueType order) are no longer dropped: recovered, or counted in `Page.unmapped` when not.
- **AC-442.8** `Page.recovered` counts recovered characters (additive, default 0, `docs/` names it); `legibility` subtracts them from the unmapped share.
- **AC-442.9** The report and the document page say in English and German which pages were recognised from letter shapes and that the text may hold mistakes; such a document is voiced.
- **AC-442.10** No corpus document changes: goldens unchanged, no shape data loaded, reading time unchanged within noise.
- **AC-442.11** The font reader is bounded (contours, points, composite depth, glyph count, offsets) and a damaged program never fails the file; recognition of 2,000 glyphs stays within the child's step clock.
- **AC-442.12** Reference data is generated by a committed script from pinned Apache-2.0 / OFL-1.1 font releases, with `THIRD_PARTY_LICENSES.md` rows; no font file ships.
- **AC-442.13** (measure) Colin's file: at least 99.5 % of characters right on each page, title block included, all pages readable.

## 6. Out of scope (follow-up issues filed when PR 1 opens, milestone proposed: v1.2.x)

- CFF programs (`OTTO`, `FontFile3`), Type 3 fonts, `/CIDToGIDMap` streams: stay glyph numbers (part B handles them). PDFium's glyph path (§2 F) may be a route for CFF.
- CJK and other scripts outside the reference set.
- Fonts with a `cmap` or `post` table but no ToUnicode map (part A's doc: "could be recovered"): a separate, simpler path through the program's own names; not counted as sourceless today, so not in this batch.
- OCR (#187's out-of-scope note stands).

## 7. Files, size, lanes, order

- **PR 1** (extraction + core, critical, `risk:high`, labels `lane:extraction`, `lane:core`, `lane:infra` as the lock per LANE-03): `src/sci2audio/extraction/glyphs.py` (new, about 400 lines), `extraction/data/glyph-shapes.bin` (new; hatchling ships package files as it ships `web/static/fonts`, so no `pyproject.toml` change: to verify with a wheel-contents test), `extraction/pdf.py` (about +80: per-document fonts, lost codes, deferred line building), `extraction/legibility.py` (+5), `core/content.py` (`Page.recovered`, +6), `scripts/glyph_shapes.py`, `scripts/glyph_fixtures.py`, fixtures in `tests/fixtures/` (or `tests/unit/data/`, as the repo does), tests (`test_extraction_glyphs.py` new, `test_extraction_legibility.py`, `test_core_content.py`), `docs/unreadable-pdf-text.md`, `THIRD_PARTY_LICENSES.md`, `tests/corpus/LICENSES.md`, `CHANGELOG.md`. About 900 lines of own code and tests plus data. Goldens touched: none.
- **PR 2** (app/release lane, non-critical, Opus medium review): `app/report.py`, `app/readability.py` (field passthrough), `web/strings/en.toml`, `de.toml`, `web/templates/document.html`, `cli.py` if the report text is printed there, tests. Starts when PR 1 merges and no app/web batch holds those files (LANE-02).
- **Order:** after B15 merges (shared `pdf.py`, `isolate.py`). B14 touches only markup files, so it is not a file conflict, but the extraction lane runs one implementation thread.
- **CHANGELOG Unreleased (D-768), "Added":** "PDFs whose fonts hold no text, only glyph numbers, are now read by recognising each letter's shape; the report says which pages and that the text may hold mistakes (#442)." "Fixed": "Digits and some punctuation in such PDFs were dropped; they are now kept (#442)."
- KB (via the KB thread): q1 to q9 as decisions, D-402 amendment, the measurements in §1 and §2.

## 8. Questions for the coordinator

- **q1** Recovery in extraction, inside the PDF child, per document. Recommended: yes.
- **q2** Own bounded TrueType reader; fontTools only for scripts. Recommended: yes.
- **q3** Reference data derived from Tinos, Arimo, Cousine, Caladea (Apache-2.0) and Carlito (OFL-1.1), drawings only, no font file shipped. Licence-gate call on Carlito. Recommended: accept all five.
- **q4** Shape matching with width-chosen twin, one-letter-per-glyph, word step for close calls, refusal thresholds pinned in the PR. Recommended: yes (approach C; A, B, D, E, F rejected as in §2).
- **q5** Core field `Page.recovered: int = 0` (critical). Recommended: yes.
- **q6** D-402 amended for fonts with no Unicode source only. Recommended: yes. This is a product-behaviour change Colin started ("lets do part 3"); flag it to him in one line.
- **q7** PR 2 in the app lane inside B18 (notice EN/DE, JSON field). Recommended: yes, so recovered text never reaches a release without the notice (no release is planned before both merge, D-721).
- **q8** Fixtures from Apache-2.0 font subsets only (OFL fonts may not be modified under rule 2). Recommended: yes.
- **q9** Scope limits of §6 as follow-up issues. Recommended: yes.

## 9. GitHub issue draft (not created; for a sub-issue of #442)

**Title:** extraction: read PDFs whose fonts hold only glyph numbers by recognising the letters' shapes (#442 part 3)

**Body:**

> Part 3 of #442 (parts A and B merged: extraction flags fonts with no Unicode source, preparing stops when most of a document comes from them). Plan: `plans/extraction-batch-b18-plan.md` (project files), batch B18, after B15.
>
> **Problem.** A PDF whose CID TrueType fonts lost their ToUnicode map, `cmap` and `post` holds only glyph numbers. Today such a document is refused (part B). The glyphs themselves are still in the file, and for the usual Office fonts open metric-compatible twins exist (Tinos, Arimo, Cousine, Carlito, Caladea), so the letters can be recognised from their shapes without OCR. Also, PDFium gives some glyph numbers as white space or control codes, and extraction drops them today: in Times New Roman's order every digit, `,` `.` `-` `/` `:` `(` `)`, `ü` and `ß` (4.9 % of the characters of the reported file).
>
> **Approach.** A bounded TrueType outline reader in `extraction/glyphs.py`; each used glyph drawn and compared with precomputed drawings of the twin fonts (family chosen by advance widths, candidates of equal width, shape distance, one letter per glyph, a closed list of common words for close calls). Accepted per font only when the shapes match closely and each page passes `legibility`; otherwise today's behaviour. New core field `Page.recovered`. The report and document page say which pages were recognised and that the text may hold mistakes. Amends D-402 for this case only.
>
> **Acceptance criteria:** AC-442.5 to AC-442.13 (plan §5).
>
> **Out of scope (own issues):** CFF and Type 3 fonts, `/CIDToGIDMap` streams, CJK, fonts with `cmap`/`post` but no ToUnicode, OCR.
>
> **Critical:** yes (core field, third-party data, parsing untrusted font programs, D-402 change). `risk:high`, `lane:extraction`, `lane:core`, `lane:infra`; PR 2 `lane:app`, `lane:web`.
>
> Checklist:
> - [ ] PR 1 extraction + core: reader, shape data and script, recognition, lost characters, `Page.recovered`, `legibility`, docs, licences
> - [ ] PR 2 app + web: report warning, document notice, JSON field (EN + DE)
> - [ ] Follow-up issues for §6 filed

---
_Generated by [Claude Code](https://claude.ai/code)_
