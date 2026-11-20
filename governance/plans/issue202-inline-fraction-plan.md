# Plan: #202 an inline stacked fraction reads its numerator and denominator glued together

Thread "Make PDF layout more robust for v1.2", 14 Nov 2026. Lane: extraction/layout. Base: main e9167e3. #317 only touched textprep citations, so these measurements on 57f9fd2 still hold.

**Critical: yes.** Golden files change: the extraction and layout corpus snapshots, and new English regression cases. The PR gets the `risk:high` label and waits for plan approval. No core dataclass, layer contract or text-step interface changes.

## 1. Measured facts (main 57f9fd2, all 8 corpus papers)

- **Every inline fraction in the corpus has a drawn fraction bar.** TeX draws the bar as a thin filled rectangle, which extraction records as a `Drawing` 0.8 pt thick. I listed every thin horizontal drawing (at most 1.2 pt thick, 2 to 80 pt wide) that has text just above it and just below it, overlapping it horizontally. Only liu has any: 32 bars, 17 in FORMULA blocks and the rest in running text. The other 7 papers have none.
- **The glued fractions in running text are 5, all in liu.** They sit in 4 paragraph blocks:

| Printed | Read today | Where the glue comes from |
|---|---|---|
| µB = eℏ over 2mₑ (p2, bar p2-d131) | "eℏ2me" | layout: two pieces (p2-l107 ends "eℏ", p2-l108 starts "2me") joined by `geometry.separators` with no space, because the denominator starts 1.16 em back under the numerator, inside `stack_reach` (D-277) |
| 1 over ℏ (p2, p2-d133) | "1ℏ" | extraction: both in one `TextLine` (p2-l122). PDFium generated a space before ℏ, but `_Line._white` drops it because the letters touch and are not digit over digit (D-276, #128 M2) |
| ∂Eₘq over ∂q (p2, p2-d134) | "∂Emq∂q" | layout: two pieces (p2-l122 and p2-l123), as in the first row |
| i over ℏ (p2, p2-d135) | "iℏ" | extraction, as in the second row (PDFium generated a space there too) |
| eE over ℏ (p3, p3-d200) | "eEℏ" | extraction, as in the second row (generated space before ℏ) |

- The other fractions in running text already read with a space: "21 22" and "m0 4" (digit under digit, #128 M2), plus "i∂δ(q−q′) ∂q", "∂δ(Eq−Eq′ ) ∂Eq" and "cos ϕ∂Θ(EF−Eq) ∂Eq". Leaving those alone is part of the test.
- **Sub- and superscript stacks have no bar**, e.g. u with m above and q below, set at the same x. They glue by design (D-277) and must stay glued. Without a bar, a fraction and a script stack look alike to the geometry, so the bar is the only safe signal.
- **Prototype measurement (throwaway monkeypatch, nothing committed).** I applied the rule in section 3 in both places and diffed the blocks of all 8 papers. Only liu changes, and its block count stays at 134:
  - 4 paragraphs gain exactly the 5 missing spaces: "eℏ 2me", "1 ℏ ∂Emq ∂q", "i ℏ", "eE ℏ".
  - 5 FORMULA blocks gain a space ("−egsgν 12π", "i ℏ-V", and "−gsgν 4π" three times). These are placeholders and nobody hears their text.
- **Spoken-script diff for liu** (`prepare_script` steps, built-in): only the five places change, e.g. "Bohr-magneton μB equals eℏ 2me . The Berry …" and "⟨umq |vˆ|um′q⟩ equals 1 ℏ ∂Emq ∂q δm,m′ + i ℏ…". A second run over `rebuilt_from_script` of the first run's script reads the same, on main and with the fix.
- Cost: the new check runs only for a character, or a piece, that starts back under the letters before it on another baseline. That is rare, and it compares against the page's few thin drawings. No measurable time.

## 2. Decisions (with recommendations)

**Q1. What separates numerator and denominator?** (a) **A space, recommended.** It is the minimal faithful reading: PDFium itself puts a space there, and the voice reads two tokens. (b) "over" as a proposed REPLACE edit (D-57). Layout and extraction cannot put a marker for "fraction" into the text without inventing text. A text step would have to read the bars from `Document.content`, a new kind of step. That belongs with spoken formulas (MathCAT, Later, D-460). Recommend (a) now and no new issue, since D-460 already covers formulas.

**Q2. Where does the fix live?** (a) **Extraction and layout, same rule in both, recommended.** This is the precedent of D-274 and #128 M2 (digit under digit), which already lives in both places. Extraction keeps PDFium's generated space inside a line, and layout keeps a space between pieces. It fixes all 5 cases. (b) Layout only fixes 2 of 5: "1ℏ", "iℏ" and "eEℏ" are inside one extracted line, and layout cannot add a space inside a line's text, because the text stays at its offset (layout does not move text, D-414). (c) Extraction ends a line at a bar, so that layout alone decides. That changes item ids and splits lines, so far more golden churn for the same result. Not recommended.

**Q3. What is a fraction bar?** A `Drawing` at most `0.15 em` thick (em of the larger of the two letters' sizes) and at least 3 times as wide as it is thick. The text before it (the last character in extraction; in layout, every run of the piece before it that overlaps the bar horizontally) stands above it, and the next character or piece stands below it. "Above" and "below" are judged by the box centres. Both overlap the bar horizontally, and each stands within `0.6 em` of it. The prototype used exactly these values. Settings: `LayoutSettings.fraction_bar = 0.15` and `fraction_reach = 0.6`, and the extraction constants `FRACTION_BAR` and `FRACTION_REACH` with a comment pointing at the layout settings, like `SPACE`/`word_space` today. Recommend these. I will sweep each value in the PR (0.05 to 0.5 em, and 0.2 to 1.5 em) and report where the corpus result changes.

**Q4. Extraction only keeps a space PDFium generated; it never adds one.** A file that stores no space there stays glued inside the line. This matches D-276 (we decide which generated spaces to keep). All three liu cases have the generated space. Recommend.

**Q5. The digit-under-digit rule (#128 M2) stays** as it is. It also covers fractions set without a bar.

## 3. Changes

- `extraction/pdf.py`: `_pages` reads the page's graphics before its text lines (both need only the open page) and passes the thin drawings' boxes to `_lines`, then to `_Line`. `_Line._white` keeps a generated space when the char starts back under the last letter, on another baseline, with a fraction bar between them (`_across_bar`).
- `layout/geometry.py`: `separators(pieces, size, word_space, stack_reach, bars=())` keeps a space before a piece that starts under a fraction bar whose numerator is the piece before it. A helper `fraction_bars(drawings, ...)` lives here too.
- Callers pass the page's bars: `paragraphs._paragraph` (via the row's page), `split` and `footnotes._note`.
- `layout/settings.py`: the two new settings, each with a comment.

Layout does not move text: only the separator between two pieces changes, and every line part stays at its offset (`block.text[start:start+len(line.text)] == line.text`).

## 4. Tests (written first; each fails on main where marked)

1. Extraction (made-up PDF, `tests/unit/pdf_maker.py`, Text + Rect): "1" over a 0.4 pt bar over "h" in running text reads "1 h" **(fails on main)**. A stack of m above q with no bar stays "mq". A word with an underline and a subscript right after it stays glued. If pdf_maker's separate text objects don't make PDFium generate the space, I write the one text object with `Td` moves as raw content, as liu does.
2. Layout `separators` unit tests on made-up `TextLine`s: a numerator piece over a bar and a denominator piece under it get " " **(fails on main)**. With no bar, or a bar too thick (a frame line), or a bar not under the numerator, they get "" as today. A digit under a digit still gets " ".
3. Layout build test on made-up content: a paragraph line "µB = eh" + bar + "2me . The" reads "eh 2me . The". The text-at-offset invariant holds **(fails on main)**.
4. Hypothesis property: passing bars never turns a " " into "" (the rule only adds spaces). The existing layout properties (never fails on any Content, every item in one block) run unchanged.
5. English regression cases (`tests/regression/english.toml`, issue 202): the three liu sentences as layout now gives them, with their expected scripts. They pin that textprep keeps the two parts apart and reads them the same on a second run (the regression harness and `test_the_built_in_steps_never_fail_and_are_idempotent`).
6. Corpus: a liu test that the 5 places read with a space and the 3 already-spaced ones are unchanged. Plus a second-run check on liu's script (`rebuilt_from_script`, same as the runner property), since the corpus has no idempotence test of its own today.

## 5. Golden files that change (all liu only, each explained in the PR)

- `tests/unit/__snapshots__/test_extraction_corpus.ambr`: the 3 lines p2-l122, p2-l123 and p3-l65 gain one space each.
- `tests/unit/__snapshots__/test_layout_corpus.ambr`: 4 paragraphs and 5 formula blocks, one space each per fraction (block count unchanged).
- Not touched: `test_app_corpus.ambr`, which records scripts only for hardt, maass and seaborn, and the textprep corpus snapshots, which hold none of the five places (checked by grep).
- `tests/regression/english.toml`: 3 new cases.
- The PR shows the spoken-script diff (`sci2audio script FILE --chapters all --ignore-settings`) for all 8 papers. Only liu differs.

## 6. PR split

One PR, "layout: an inline fraction reads its numerator and denominator apart (#202)", `risk:high`. Splitting extraction from layout would leave half of the cases glued and change the same goldens twice. Size: about 80 lines of code plus tests.

## 7. Out of scope, to file as issues when the PR opens

- liu p2: an inline fraction at a line end ("−e gs gν over 12π · m∗ over mₑ") sends its denominator "12π" into a paragraph of its own (block 18) and its "me" to the end of block 17. This is a reading-order problem, not spacing (v1.2, lane:layout).
- Reading the bar as "over": stays with spoken formulas (D-460, Later). No new issue.
