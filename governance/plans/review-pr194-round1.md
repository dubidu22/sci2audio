# Review of PR #194, round 1 (issue #189, footnote marks tied by noteref link tags)

Reviewed head 0adc3dd (merge of main f5ec33f), 13 Nov 2026 ~21:00 UTC. Critical, risk:high.

## What I checked myself

- **Fast suite** on the head: 3158 passed, 1 skipped (92 s). `ruff check`, `ruff format --check`, `lint-imports` (3 kept), `deptry src`: clean. CI on the head: all green.
- **Corpus, main vs PR**, `run_script_job` with default settings, all 10 corpus files (7 PDFs, the EPUB, the Markdown sample, the text sample):
  - 7 PDFs and the text sample: script, report.json, report.md and job.json **byte-identical**.
  - Markdown sample: exactly the 5 lines of the plan's table change; report gains the 3 mark removals and the 2 introductions change wording.
  - The Time Machine: exactly the 2 places of the plan change (the sentence splits at "all.", the endnote reads "Footnote 1." and loses " ↩︎"); utterance count 132 → 133. No other line differs.
- **Test-first:** commit 4ee04b7 adds the three regression cases with today's output; a7e8314 changes them with the rule. OK.
- **Hypothesis nightly profile** on both new properties: pass. My own fuzz (different generator: multi-line blocks, captions, tables, furniture, labels taken from the text, links to line 0-2 of any block, noterefs without links, runs tagged noteref+back-link): 28,000 documents, `check_text_step` plus strict `run_steps` with default switches and with "Footnote texts" on: 0 failures. Density: in 3,000 documents, 775 linked-mark/linked-intro edits and 2,647 back-link removals.
- **Time:** 100k marks of one note 0.69 s; 100k back-links in one note 0.65 s; 200k spaces before a back-link 0.01 s; 50k marks of another note inside a note (the `_lead`/`_without` path) 0.41 s. Linear.
- **Hand probes** (all behave as the rule says): mark run " 1" with a space inside; back-link on the second line of a note; back-link before a labelled "1. Text"; a heading's noteref with Footnote texts on; a caption's noteref linking the note's second line; "( 1 )".
- **Mutation:** 48 hand mutants of the new code in footnotes.py, documents.py and regression.py, run against the four footnote/regression test files. 35 killed, 13 survived. Equivalent: #30 (reversed groups, only one group is set), #32 (greedy bracket regex gives the same "Footnote." for "[1][2]" and "[[1]]"), #39 (`continue` in `_without`, `max` covers it), #41 (`_lead` `<` vs `<=`: same spoken text), #22/#23 (see N1). The others are the should-fix items below.

## Must fix

None.

## Should fix (tests only; no behaviour change asked)

- **S1. Single-tag variants are untested** (mutants #0, #3 survive). Every test and both corpus files carry `role:doc-noteref` and `epub:noteref` together, and `role:doc-backlink` with `epub:backlink`. Dropping `epub:noteref` from NOTEREF_TAGS, or `role:doc-backlink` from BACKLINK_TAGS, passes every test. Add a unit test with a noteref tagged only `epub:noteref` (EPUB without ARIA roles) and a back-link tagged only `role:doc-backlink`. Probe on the head: `"Sloped.1 End."` + `"Hill. ↩︎"` → `["Sloped. End.", "Footnote 1. Hill."]`.
- **S2. The "seemed to start with Footnote" test the PR body names does not exist** (mutant #27, `_INTRODUCED.match(text, lead)` in place of `_without(...)`, survives). Add it. Example on the head: note `"Footnote1 rest."` whose "1" is a noteref to another note, and a body mark linking to this note → the note reads `"Footnote rest."` with no introduction (D-144), strict run passes.
- **S3. A printed label that overlaps a removal is untested** (mutants #24 removed-without-marks, #28 `if linked is not None`, #38 `lead <= span.end` survive):
  - labelled note `"2 See note two."`, label "2", where "2" is a noteref to another note, and a body mark "1" linking to it → `"Footnote. See note two."` (label path refused, `not label` keeps the linked intro out), strict run passes;
  - labelled note `"↩︎1. Text"`, label "1", the arrow a back-link → `"Footnote 1. Text"` (a removal that ends where the label starts is not an overlap).
- **S4. `page = true` is accepted as page 1** (`isinstance(True, int)`). Refuse bools in `regression._case` as `JobSettings` does for chapters, and add a row to `test_a_bad_run_names_the_case`.
- **S5. Same-link runs on two lines** (mutant #10, offset check dropped, survives): add a test with `"Word 1\n1 word"`, both "1" linking the same note → two edits, reads `"Word word"`.

## Nits (no change required)

- **N1.** In `_backlinks`, `taken` can no longer matter: each back-link edit now ends on a non-space character (`rstrip`), so the next one's walk over white space always stops at or after it. Mutants #22/#23 are equivalent and `test_a_back_link_ending_in_a_space_leaves_that_space_to_the_next_one` passes without the guard. Keep it as a guard if you like; say so in a comment, or drop it.
- **N2.** `"( 1 )"` introduces as "Footnote." (inner text has spaces). No corpus file has one; fine.

## For the KB (coordinator)

Plan q4 / D-423 says the printed-label rule "still applies" to a noteref that does not reach a note; D-428 §2.5 says the printed-label pass skips every noteref run. The code follows D-428 (`test_the_printed_label_rule_never_takes_a_noteref`). The KB entry for D-423 should note that D-428 refines this clause.
