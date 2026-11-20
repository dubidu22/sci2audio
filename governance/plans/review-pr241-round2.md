# Review of PR #241 (#237 stated language tags), round 2

Head reviewed: 5282b10 (merge of main c19cb0d as 2206df7, then the fix commit). Verdict: passes.

## Round 1 fix list

- **F1 fixed.** `markdown._language(values)` normalises every value of `lang`, then `language`,
  and takes the first that names a language, the same rule as EPUB's dc:language. New test
  `test_markdown_states_its_first_language_that_names_one`: `lang: [und, de]`, `lang: und` +
  `language: de`, `lang:` list of x-default and de, each "de".
- **F2 fixed.** PR body golden line now names the tagged corpus files (en-GB twice, de once).
  Nit, not worth a round: it says "all 12 corpus scripts"; after #239 the corpus has 13
  documents, and this review compared all 13 (see below).

## Checks on 5282b10

- Diff vs main c19cb0d: only the six PR files (CHANGELOG, extraction/epub.py, language.py,
  markdown.py, pdf.py, the new test file); the merge brought nothing else. CHANGELOG keeps #235
  under Added and #237 under Fixed.
- ruff, format, lint-imports (3 kept), deptry clean. Fast suite: 3,750 passed, 5 skipped.
- `run_script_job` on all 13 corpus documents (incl. arxiv2017-maass-privacyscore.pdf) with
  main c19cb0d vs the PR: all 52 scripts and reports byte-identical.

Nothing deferred. CI on 5282b10 all green; squash-merged into main as 5a254e4 (14 Nov 2026), #237 closed.
