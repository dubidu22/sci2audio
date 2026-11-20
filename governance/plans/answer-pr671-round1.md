# PR #671, answer to review round 1 (head 933cdf4 → 6a759bb)

Thread layout-b-l1 (implementation). One fix commit, 6a759bb; Linux CI only (D-698).

## M1, a second lone accent over the same letter was lost: fixed

- Cause: `_under` took any one-character text with `isalpha()` as a letter, and the circumflex (U+02C6) and caron (U+02C7) are modifier letters (category Lm). A second accent could therefore go onto the first accent's character, whose line is left out.
- Fix (`extraction/pdf.py`, new `_letter`): a spacing accent is never a letter. A letter that already took an accent (NFD: one letter plus combining marks) still is one, so a second accent goes onto the letter itself, whether or not NFC composes the pair into one code point.
- Found while testing: two stacked accents stored together come out as one line holding both. The rule now takes a line made only of spacing accents (`_only_accents`), not just a line of one. It places such a line only if every accent in it finds a letter, so no accent is dropped. This widens the plan's "a line made of one spacing accent" to "a line made only of spacing accents", and the reason is M1's "no character is lost". No corpus output changes (all goldens identical to 933cdf4).
- Tests:
  - `test_two_accents_stacked_on_one_letter_both_go_onto_it`: "Nguyen" with a circumflex and an acute, in both stored orders. Both go onto the "e", in the order they are stored: circumflex then acute gives NFC "ế"; acute then circumflex gives "é" plus a combining circumflex, as stored. Placed {1, 2}. It failed on 933cdf4 ("ê").
  - The Hypothesis property now draws a second, different accent over the same letter now and then. It asserts that no line is accents only, that the letters read are the word's, and that each drawn accent is found exactly as often as it was drawn, as a spacing or a combining mark. It failed on 933cdf4. The same accent drawn twice in one place is left out of the property: PDFium takes it for a glyph drawn twice and keeps one.
  - Run with `HYPOTHESIS_PROFILE=nightly`: green.

## S1, the planned corpus check was missing: fixed

`tests/unit/test_layout_corpus.py::test_accents_and_lines_under_braces_read_as_printed` checks the blocks directly, not through the snapshots:
- Chi: "Ana Marasović, Swabha", "({SOUPS} 2016), pages\n321–340.", "({USENIX} Security 18), pages\n531–548.".
- Hardt: "Ana Marasović, Noah A\nSmith".
- Liu: "J. Železn´y, …", "L. Šmejkal,\nT. Jungwirth".
- In all three papers, no line is a lone acute or caron, and no line ends in a stray one.

It fails with main's `pdf.py` and `paragraphs.py` (3 failed) and passes on the fix head.

## N1, N2

- N1: accepted as explained in the PR body.
- N2: done. The repeated `if r.box` filter in `paragraphs._band` is gone.

## Checks on 6a759bb

ruff, ruff format, lint-imports (3 kept), deptry and the fast suite: green, 8375 passed, 6 skipped, 6 xfailed, 77 snapshots passed. The three real-espeak tests are deselected on this Mac, as in the PR body. No golden file changed in this commit.
