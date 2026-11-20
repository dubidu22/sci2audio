# Review PR #575 round 1 (#574, critical: core dataclass, lane:infra; D-767, D-768, D-769)

Head reviewed: c826c99b3979dd593bc3e37c52a5e442e429a5a3 on main d44cf5d (main has not moved since). Reviewer: B1 review thread (Opus high), 18 Nov 2026.
CI: Linux run 44411726189 green; ci:full run 44413477380 green on ubuntu, macOS, Windows.

## Verdict: APPROVED (final round)

## Verified

- AC-1: three strict regression cases in `test_textprep_placeholders.py` (table, figure, formula). With main's `core/content.py` swapped back in, all three fail: StepError 'table-figure-notices' for table and figure, and 'formula-notices' for the formula, so the formula step was affected too. With the fix they pass; together with the core and legibility tests that is 370 passed.
- AC-2: core refuses only `unmapped < 0` (the `Page(1, unmapped=-1)` case stays). The bound moved into the extraction tests: `test_no_page_extraction_makes_counts_more_glyph_numbers_than_it_holds` covers German, far order, mixed with a caption, cropped, and turned 90 (#559 x #562). Every case also asserts `unmapped > 0`, so none passes vacuously. The core test pins that a page rebuilt from some lines keeps its count.
- AC-3: the `Page` docstring and docs/unreadable-pdf-text.md say the count belongs to the page as extracted, and that the share should be measured on extraction's pages, as `legibility` does. `PageLegibility.unreadable` guards `characters == 0`.
- AC-4: no golden or snapshot file changed.
- Other consumers: the only `replace(page, ...)` calls in src/ are `extraction/markup.py` (EPUB, where `unmapped` is always 0) and `textprep/placeholders.py` (this case). No app, layout or web code reads `unmapped` yet.
- D-768 CHANGELOG: five Fixed lines (#574; #537/#543; #485 for #556 and #568; #529/#535; #466). The #485 line's message matches `_too_large` in pdf.py ("reading it needs more than … of memory").
- Commit message: no closing keyword. The body says Closes #574.

## Findings

None.
