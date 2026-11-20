# Answer to the review of PR #561, round 2

Review: `plans/review-pr561-round2.md` (head df587f7). One test-only fix commit: **ad82259** on `layout/plain-text-structure-466`. No code changed. S1 fixed in full.

## S1 (fixed): two stated parts of `_title` had no test

Both in `tests/unit/test_extraction_text.py`. Each mutant was applied by hand to `extraction/text.py` and the file's tests run; the lists below are every test that failed.

| item | mutants | new test (fails on the mutants) |
|---|---|---|
| (a) closing quotes and brackets looked through | 13 (`rstrip(_CLOSERS)` → `rstrip()`), 14 (→ `lstrip(_CLOSERS)`) | `test_punctuation_before_closing_quotes_or_brackets_keeps_the_lines_joined`, three cases: `She said “yes,”` (English curly quotes), `Er sagte: »Ja,«` (German guillemets), `(see the note above,)` (closing bracket); each before a long line starting with a capital stays `p`, `p, br`. All three cases fail on 13 and on 14. |
| (b) the two-letter minimum | 3 (`< 2` → `<= 2`), 4 (`< 3`) | `test_a_two_letter_line_can_be_a_title_line`: `EU` before a long line starting with a capital gives `p`, `p`. Fails on 3 and on 4. The existing `"0"` test stays beside it. |

## Checks

- `ruff check`, `ruff format --check`: clean.
- `test_extraction_text.py`: 78 passed on ad82259.
- Not merged with main: #558 (c51e846) touched only layout files and their snapshots, none of this PR's files (MRG-03).
- `ci:full` label added on ad82259; the result goes in the hand-back message.
