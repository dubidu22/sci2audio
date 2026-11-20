# Review of PR #133, round 1: PDF bookmarks into `Content.outline` (#24, part 2)

Reviewed head `f041af4` (main `1064e18` merged in, branch up to date). Critical (extraction, golden file).
Checked against plan `issue24-outline-plan.md` sections 4 and 7 (D-262 to D-273).

## What I ran

- `ruff check`, `ruff format --check`, `lint-imports` (3 contracts kept), `deptry src`: clean.
- Fast suite, ci profile, without `tests/browser`: **2125 passed**, 19 subtests, 54 snapshots (2 min 28 s).
- Nightly Hypothesis profile on `test_extraction_pdf.py` and `test_extraction_corpus.py`: 108 passed; both
  damage tests 2000 passing examples each.
- CI on `f041af4`: all green, tests on ubuntu, macOS and Windows, browser, lint and layers, security,
  licences, CodeQL.
- Hand mutations of `_outline`, `_title`, `_target` (strict decoding, level + 2, no upper page bound,
  depth 16, no terminator cut, page index unshifted): every one killed.
- Probes (scripts in my scratchpad, not in the PR):
  - D-268, outline damage never fails the file: 20,000 random changes of 1 to 8 bytes inside the outline
    objects. Every case that gave an `ExtractionError` also gave it with `_outline` stubbed out, so no
    failure came from the outline.
  - Fuzz density of the PR's own Hypothesis test (same mutation shape, 3000 draws): outline unchanged 485,
    changed 553, empty 358, error 1604. The test exercises damaged outlines well.
  - Loops: a child whose `/First` points back at its parent, and a bookmark whose `/Next` is itself, both
    end with each entry once.
  - 50,000 sibling bookmarks: read in 0.8 s.

The code matches the plan. Taking the page from `FPDFBookmark_GetDest` alone is right: PDFium follows
`/A /GoTo` itself (pinned by a test), so the plan's `FPDFBookmark_GetAction` fallback is not needed. The
corpus outlines match the measured facts in plan section 1. The truth cross-check is two-way: an entry
listed in `NOT_TRUTH_HEADINGS` that starts matching fails the test too.

## Must-fix

None.

## Should-fix

**S1. `PRINTED_NUMBER` is not anchored, so it can strip text in the middle of a heading.**
`tests/unit/test_extraction_corpus.py`: `PRINTED_NUMBER.sub("", heading["text"], count=1)` removes the
first match anywhere, and the pattern also matches a capital letter or a number followed by a space in
mid-heading. On the corpus truth, "ACL 2023 Responsible NLP Checklist" (chi, hardt) becomes
"AC2023 Responsible NLP Checklist". This is harmless today only because the ACL papers have no
outline. A future paper with bookmarks would get a wrong failure, or a wrong match against a mangled
heading. Fix: anchor the pattern (`^`, or `PRINTED_NUMBER.match` with slicing), and add a one-line
check that the ACL heading comes through unchanged.

## Nits

**N1. "As stored" is PDFium's reading.** PDFium turns control characters in a bookmark title into
spaces: `b"A\x00B"` is read as `"A B"`, and `"x\ny\x01"` as `"x y "`. That fits D-266 in spirit,
since nothing is stripped or dropped. Say so in `_title`'s docstring, and optionally pin it in
`test_bookmark_titles_are_decoded_as_stored`.

**N2. pypdfium2's warning reaches the terminal.** On a looped outline, `sci2audio script loop.pdf`
prints "A circular bookmark reference was detected while traversing the table of contents." between
"Reading the file ..." and "Finding the reading order ...". This happens because no logging handler
is set up, so Python's last-resort handler prints it. The same goes for the "Maximum recursion depth
15 reached" warning. It is only cosmetic, so fix it here or file an issue (CLI/web logging setup).

**N3. Optional test for a child loop.** Only a sibling loop (`/Next`) is tested. A `/First` that
points back at an ancestor is also handled (see the probe above). One more case in
`test_a_bookmark_loop_ends_and_the_pages_are_still_read` would pin it.

## Verdict

Changes requested for S1 only. N1 to N3: fix them or say why not, and anything deferred gets an
issue. Round 2 will re-run the fast suite, the nightly extraction tests and CI on the new head, then
merge.

## Round 2 and merge (13 Nov 2026)

The author's answer was commit b45a8e2. S1 is fixed: the pattern is anchored with `^`, and a new test checks the ACL heading. N1 is fixed with a docstring and the test pins the control characters. N3 is fixed: `Mark(loop=True)` now builds a `/First` loop, and a test covers it. N2 is deferred to #143.
Main was merged in twice, once after #128 (801cda9) and once after #140 and #137 (9f083d6). The only conflicts were in the imports and in CHANGELOG.md.
Checks on 9f083d6: the fast suite gives 2171 passed, the nightly extraction tests 130 passed, the layer check finds 3 contracts kept, and CI is green on all jobs.
On b45a8e2 the browser job needed one re-run for the #138 flake; 801cda9 and 9f083d6 passed on the first attempt.
Merged with squash as c39752b.
