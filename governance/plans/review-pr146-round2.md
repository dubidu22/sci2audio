# Review of PR #146, round 2

Reviewed head a28af6b against round 1 (`review-pr146-round1.md`).

## Round 1 items

- M1 fixed: `test_the_font_rules_level_stands_for_unnumbered_headings_too` kills both mutants
  (guard removed; `found={}`).
- S1 fixed for one common title: `test_an_added_numbered_heading_under_the_appendices_title_moves_down`
  kills "no shift".
- S2 fixed: the full-width title kills "no NFKC".
- N1 fixed: docstring line and `test_the_first_of_two_entries_naming_one_block_decides_its_level`
  kills "last entry wins".

Mutation run, 22 mutants on a28af6b: 21 killed, 1 survived (R2-2 below).

## New findings (both from the S1 fix)

### R2-1 (should fix): `shift_from` keeps the last common title, the font rules shift from the first

`_numbered` sets `self.shift_from` every time it meets a common title, but its own `shift` turns
to 1 at the first one and stays 1. With two such titles ("Appendices", then "Supplement"), a
numbered heading the outline adds between them gets no shift:

```python
page = Page().heading("1 Introduction").body().heading("2 Method").body()
page.heading("Appendices", 16.0).body().heading("A Proofs").body()
page.heading("A.1 First").body()
plain(page, "A.2 Second").body()
page.heading("Supplement", 16.0).body().heading("B More").body().heading("B.1 Third").body()
page.build(OutlineEntry("Second", 1, 1))
# "A.2 Second" lands at level 2, a sibling of "A Proofs"; "A.1 First" is at level 3
```

Fix: set it only once (`if self.shift_from is None`), with this page as a test.

### R2-2 (should fix): nothing tests that a heading before the common title is not shifted

Mutant `shift = int(rules.shift_from is not None)` (shift every added numbered heading in a document
that has a common title) passes all 219 tests. Add a case: in a document with "Appendices", an added
"1.1 Early" before it stays at level 2.

## Verdict

Changes requested: R2-1 and R2-2, both small. Everything else is ready to merge.
