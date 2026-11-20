# Plan: #574 lost table, figure and formula notices on glyph-number pages

Lane extraction + lane:infra, critical (core dataclass), risk:high. Branch `extraction/unmapped-bound-574` from main d44cf5d. Criteria: D-767 (they match the issue's AC-1 to AC-4 with AC-2's recommended option; nothing differs). CHANGELOG: D-768.

## Change

1. `core/content.py` `Page.__post_init__`: refuse only `unmapped < 0` (message "page N unmapped must be >= 0, got X"). The upper bound against `characters` goes.
2. `Page` docstring: `unmapped` is the count extraction made for the page as read. Extraction's pages always hold `unmapped <= characters`; a page a later stage builds from some of the lines (textprep's scratch pages in `_read_in_place`) may keep the count, so core does not check it against `characters`.
3. `docs/unreadable-pdf-text.md`, section "What extraction records": the same rule in two sentences (AC-3).
4. `textprep/placeholders.py`: unchanged. Resetting `unmapped` there would fix one caller only (issue AC-2 alternative, not chosen).

## Tests (failing first)

- `test_textprep_placeholders.py`: the issue's reproduction as a regression test, `strict=True`, parametrized over a captioned table ("Table 2 is skipped."), a captioned figure and a labelled formula (the second `_read_in_place` call), each on a page with `unmapped` above the kept lines' characters. Fails on main with the StepError, passes after.
- `test_core_content.py`: the case `Page(1, lines=<"ab c">, unmapped=4)` moves from the refused list to a new test that a page may keep more `unmapped` than its lines hold (a `replace(page, lines=subset)` keeps the count); `unmapped=-1` stays refused.
- `test_extraction_legibility.py`: the bound stays in extraction's tests: one test reads the glyph-number PDFs (German, English, mixed with a Helvetica line, the "far" glyph order, and shown through /Rotate 90 via `pdf_maker.turned`) and checks `0 <= unmapped <= characters` on every page; the corpus test already checks 0 on every corpus page.

## CHANGELOG (D-768), Unreleased, one line each in the existing style

- Fixed: #574 (table, figure and formula notices kept on a page with glyph-number text).
- Fixed: #559 (a turned page is read as shown).
- Fixed: #556/#568 (a too-large PDF on a busy Windows machine gets the size message).
- Fixed: #558 (#529 #535: contents pages with numbers at the left edge, page labels from running heads).
- Fixed: #561 (#466: a plain-text title or subtitle and "- " list items keep their structure).
Wording from each PR's body; I check each against the merged diff.

## Checks

ruff, format, lint-imports, deptry, fast suite; corpus snapshots and goldens unchanged (AC-4, no `--snapshot-update`). Then Linux CI, then `ci:full`, remove label, freeze, report PR + head SHA. Size: about 15 lines of source and docs, 60 of tests, 5 CHANGELOG lines.
