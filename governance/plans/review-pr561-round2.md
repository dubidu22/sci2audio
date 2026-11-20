# Review PR #561 (#466), round 2

- Head reviewed: df587f7 (fix commit on 3836204). Answer: `plans/answer-pr561-round1.md`.
- **Verdict: changes requested, tests only (1 should-fix). M1, M2 and S1 of round 1 are fixed; the code is accepted.**

## Verified

- Diff 3836204..df587f7: `extraction/text.py` (anchor rule for list markers, `longest` over lines holding a space, docstrings) and `tests/unit/test_extraction_text.py` (+76).
- Round-1 probes on df587f7: `plans/b3-review/probe561c.py` 0 of 2000 (was 350), `probe561d.py` 0 of 2000 (was 248).
- Corpus comparison: all 13 documents' outputs on df587f7 are byte-identical to 3836204 (so only the two text samples differ from main, as in round 1). Text, tagged, language and sentence tests: 172 passed here.
- The anchor also applies to the first line of a numbered run (the author's addition, "am\n3. Oktober und am\n4. November"): agreed.
- CI on df587f7: `CI passed` green in 44399793442 (PR; Windows job re-run once after the known flate-bomb failure, D-731, coordinator's ruling) and 44399801401 (ci:full); `tests (ubuntu/macos/windows-latest)` success in both.
- Nightly property run 44401683375: green.
- Mutation run 44401678397 (2 runners; `text.x_paragraph_tags*`, `x__items*`, `x__run*`, `x__title*`; tests `test_extraction_text.py test_layout_tagged_corpus.py test_extraction_text_corpus.py`; baseline passed): 109 killed, 11 survived. Read one by one (`mutmut show`, local generation on df587f7):
  - `paragraph_tags` 11, 18 (default of `max` for an empty paragraph, never read), 20, 21, 22 (start value of `element`, always reset at line 0), 34 (`rstrip`→`lstrip` before `endswith(":")`; `fold` already strips spaces): equivalent.
  - `_title` 5 (`>` → `>=` at exactly `TITLE_SHARE`): boundary, accepted.
  - **`_title` 13, 14 and 3, 4: real gaps, see S1.**

## Findings

**S1 (should fix, tests only).** Two stated parts of `_title` have no test (`plans/b3-review/p13.py` shows each behaviour change):
- (a) Mutants 13 (`rstrip(_CLOSERS)` → `rstrip()`) and 14 (`→ lstrip(_CLOSERS)`): closing quotes and brackets are never looked through in a test. `'She said “yes,”\nThen the second line runs on …'` and `'Er sagte: »Ja,«\nDann läuft …'` stay joined on df587f7 and are cut with either mutant. Add both as a test (English curly quotes, German guillemets; a closing bracket too if you like).
- (b) Mutants 3 (`< 2` → `<= 2`) and 4 (`< 3`): the two-letter minimum is tested only with "0" (no letters). `'EU\nThe second line runs on …'` is cut on df587f7 and joined with either mutant. Add a two-letter title line that cuts, beside the existing "0" test.
Each new test must fail on its mutants (say which in the answer).

## Next

One test-only fix commit; answers in `plans/answer-pr561-round2.md`; Linux CI and `ci:full` on the fix head. Round 3 is the final round: the code is unchanged, so this round's mutation and property runs stand; then merge pinned to the fix head.
