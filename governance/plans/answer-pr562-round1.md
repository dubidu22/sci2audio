# Answer to review round 1 of PR #562

Fix commit 38b7717 on 55eec0e (one commit, no main merge).

- **M1 fixed** exactly as given: `_SourcelessFonts.has` returns False unless
  `FPDFText_HasUnicodeMapError == 1`, then looks the font up once per page. Class docstring's
  second paragraph now says the map error is asked first and a font is looked at only for a
  character PDFium could not map. Test
  `test_a_page_whose_characters_pdfium_maps_never_looks_at_a_font_program` (monkeypatches
  `pdf._sourceless` to raise; ToUnicode fixture plus a Helvetica line): fails on 55eec0e,
  passes on 38b7717.
- **M2 fixed**, the three groups as listed:
  1. `test_only_a_truetype_or_opentype_program_without_cmap_or_post_names_no_glyph`, 10 cases:
     truetype, cmap, post, true, OTTO, ttcf, no tables, cut short (numTables 3, 20 bytes),
     Type 1, empty.
  2. `test_the_limits_hold_at_their_boundaries`, 9 cases: unmapped 50/100 readable, 51/100
     unreadable; 99 pairs all rare readable; 5 of 100 unreadable; 4 of 100 readable; 49 letters
     all foreign readable; 10 of 50 unreadable; 9 of 50 readable; empty page readable.
  3. `test_private_use_and_replacement_characters_are_foreign_letters`: 60 private-use
     characters (U+E000 on) and 60 U+FFFD each give letters == foreign == 60, unreadable.
- **N2** wording: "hardly ever" in docs/unreadable-pdf-text.md (with "savvy", "XXL" and the
  5 % limit) and in the legibility module docstring. N1, N3: no change.
- Local: ruff, format clean; fast suite 7202 passed, 5 skipped.
