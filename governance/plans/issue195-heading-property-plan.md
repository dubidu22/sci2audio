# Plan: #195 heading property test vs outline-only sections without positions

Layout lane, test-only change (no code, golden, contract or KB change), so not critical. Order decided by the coordinator (D-432): #195, #196, then #163.

## Cause

`test_layout_headings.py::test_sections_start_at_headings_and_carry_their_text` predates #75 and demands that every section start at a HEADING block. For content without positions, the #75 design (D-405 to D-418, "outline only where a page has no heading") lets an outline entry start a section at a non-heading block, titled as the entry (`tagged._Headings._from_entry`). The nightly profile finds such a case (one picture, one outline entry); the derandomised `ci` profile doesn't.

## Change

Restate the property for both paths in the one test:
- every HEADING block starts a section, and that section's title is `title(block.text)` (both paths);
- with positions (`tagged.positioned`), section starts are exactly the headings, as today;
- without positions, a section that starts at a non-heading block has the title of an outline entry (whitespace folded, as `_from_entry` does) whose page is that block's page.

Add the Hypothesis case as an `@example`.

## Checks

Test passes under `ci` and `nightly`; mutation (tagged path titles an outline-only section differently) makes it fail.

## Decisions to log

- Q1 (#195): keep the tagged outline-only sections as designed and restate the property test, rather than turning the block into a HEADING. Decided (Claude).
