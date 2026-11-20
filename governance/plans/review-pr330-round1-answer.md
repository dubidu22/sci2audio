# PR #330, answer to review round 1

Head 1c6f75c (main fbc6de8 merged in; CHANGELOG conflict resolved, both entries kept).

**R1-1 fixed, depth-independent (D-588).** Inside one look, `_cited_once_inner_citations_go` judges a bracket on its own text with its inner edits made (new `_Read`), and `_separators_left` blanks the separator or join word an inner removal leaves at the bracket's start, after its lead words, or at its end. So comma, semicolon, "and"/"und" and "e.g."/"vgl." nests go whole in one look. New `_shells`: brackets left empty around a removal go with it. A nest longer than the bracket cap is decided from its own text (linear time; its reason names its ends). Later looks still run until one changes nothing, now bounded by the block's bracket count instead of 3.
- Regression cases `citations-a-nest-of-any-depth` (your four rows, a semicolon row, an 8-deep row) and `de-citations-a-nest-of-any-depth` (comma, "und", "vgl.").
- Seeds 555, 8080, 41, 99, 7, 2026, 31337 pass (nightly profile; citations, German citations and both regression files).
- Timing: citation shapes ratio 6.7 to 8.8 (limit 32). `assert_near` shapes: 2.6 and 2.9 here, 5.6 and 6.5 on main (limit 16); untested "see (527794)" 9.4 (main 5.9), "(Müller, 2019) 2020" 9.2 (main 4.5). New `test_a_deep_citation_nest_takes_linear_time` (comma, lead-word, identifier nests, 400 to 3200 levels): ratio 1.6 to 2.8. A look per level had taken 19 s for 400 levels.

**R1-2 fixed.** The oracle's leftover pattern takes "."; a separator that goes with a citation at a bracket's edge is allowed ("( noise and (see also [48, 135]))" → "( noise)", which seed 41 hit next); the lead word's own comma ("e.g.,") is kept. Row `It holds ( [12]. see (see also [48, 135])) here.` → `It holds here.` added to the #272/#259 case. Seed 41 passes.

**R1-3 fixed.** The four reasons name #324 (one constant per file). #324 has the criterion to remove them from SECOND_RUN_EXCEPTIONS in both files.

**R1-4.** `test_the_edge_rules_read_the_same_on_a_second_run`, each row also the same on a second run; I checked each mutant fails it:
- glue-abbrev: de `Es gilt vgl.(527794)2019 hier.`, en `See e.g.(527794)2019 here.`
- closing-pair: `It holds and (see [12])) here.` → `It holds and) here.`
- numeric-at: `It holds and (Smith, 2019) [12] more.` → `It holds and reference 12 more.`
- pairs-check: `It holds (see (527794), results here.` → `It holds (see, results here.` (the comma before an unclosed bracket's prose stays)
- looks (bound minus one): `It holds (Smith, 2019, https://example.org) here.` needs every look its one bracket allows
- new `_shells`: two rows fail without it
- merge-crossing: removed. `_Rewrite.printed` puts a later edit's ends outside every removal and drops one ending inside a reading, so a later edit never crosses an earlier one nor lies inside it; over 8000 fuzz texts the mutant read the same as the code.

**R1-5 fixed.** German #291 row 1 in `de-citations-a-nest-reads-on-the-first-run-as-on-the-second`; #272 row 3 in `de-citations-a-separator-left-by-a-removed-citation-goes-with-it`; both read as given, the same on a second run.

**R1-6.** Filed #337, #338, #339 (v1.2, same on main), listed under Out of scope.

**Checks.** Fast suite 5068 passed, 6 xfailed, 76 snapshots unchanged; ruff, lint-imports, deptry clean. 13 corpus documents byte-identical to main fbc6de8. Fuzz 20 000 texts: 9 second-run breaks, all also on main. PR body updated.
