# Plan: #199 outline-adds-only property vs tagged base levels

Layout lane, test-only (no code, golden, contract or KB change), not critical. Order D-436: before #163.

## Cause

`test_layout_headings.py::test_an_outline_only_adds_headings` (D-270, D-271, written for PDFs) demands that the outline never changes a section level found without it. For content without positions, the #75 design (D-405 to D-418) takes the level of the first outline entry pointing at a page as that page's base heading level, so an `h1` in a chapter the nav lists at level 2 becomes a level-2 heading. In the Hypothesis case, `outline_entries` drops the two entries without letters and the remaining level-2 entry sets the base. Any EPUB whose nav nests chapters breaks the property by design, so the property is too strict for this path (not the code).

## Change

- With positions: unchanged (`{(start, level)}` without the outline ⊆ with it; headings keep kind and label).
- Without positions (`tagged.positioned` false): every section start found without the outline is a section start with it, and every heading found without it is a heading with the same label; levels may differ.
- The Hypothesis case as an `@example`.

## Checks

`ci` and `nightly` profiles; mutation: an outline that turns a tagged heading back into a paragraph (or drops its label) must fail the test.

## Decisions to log

- D-437 (as corrected to the coordinator): keep the #75 base-level rule; restate the property for content without positions.
