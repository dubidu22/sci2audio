# PR #609 round 1: answer (extraction B14 thread)

Round file: plans/review-pr609-round1.md. Main merged first (origin/main fc076e9, #610; the only conflict was CHANGELOG.md "Fixed", both sides kept), then one fix commit.

## Must fix

- **F1, fixed (D-783).** `markup.MAX_TAG = 1_000_000` characters per start or end tag, `<` and `>` included. `markup.TagLimitedParser(HTMLParser)` overrides `check_for_whole_start_tag` and `parse_endtag` (end tags only when `endtagopen` matches; otherwise the parser's bogus-comment path finds the next `>` linearly). Both call `_check_tag`, which runs `locatetagend.match(rawdata, i + skip, i + MAX_TAG + 1)` and raises `TooMuchText(MAX_TAG, "tag")` when the match passes `i + MAX_TAG`. Then `super()`. The copied module is untouched. `PageReader` and `_NavReader` both subclass it. Message: "the EPUB holds a tag longer than 1,000,000 characters" (Markdown likewise); in the nav, past it the book has no outline.
  - Measured (CPU, tracemalloc, CPython 3.12.16):
    - one 4 MB tag (`<p` + ` a` × 2,000,000) is refused at a 176 MB peak in 0.4 s; with the check lifted it peaks at 653 MB and takes 16.7 s;
    - one 1.2 MB tag is refused at 168 MB (209 MB without the check);
    - 1,000,000 `<p></p>` take 12.98 s with and 12.98 s without the check, so the second regex pass on short tags costs nothing measurable.
  - Tests:
    - `test_a_tag_past_the_tag_limit_fails`, four rows (start tag, end tag, the quoted `a=">"` row, self-closed `<br .../>`): exactly at the limit reads, one character over fails with `TAG_MESSAGE`;
    - `test_a_tag_in_the_navigation_document_is_bounded_too`;
    - `test_a_tag_past_the_real_tag_limit_fails_small`, the 4 MB tag, peak < 256 MB;
    - `test_the_tag_limit_applies_to_html_in_markdown`;
    - `MAX_TAG == 1_000_000` pinned in both decided-values tests;
    - `MAX_TAG` patched low in both "with low limits any ... reads or names a limit" properties.

## Should fix

- **F2, fixed.** `_NavReader.handle_data` counts each label's characters (reset when a label starts) through the new `markup.check_line`, so past `MAX_LINE` the book has no outline. Test: `test_a_navigation_label_is_bounded_as_a_line_is`. A label of 1,000 characters (`MAX_LINE` 1,000) gives an outline, two labels of 600 give both entries (the per-label reset), and 1,001 gives `outline == ()` while the pages still read.
- **F3, fixed.** Each open `<svg>` is now a small `_Svg` dataclass (title pieces, picture indexes, title length). The title's characters go through `check_line`. Test: `test_an_svg_title_is_bounded_as_a_line_is`. A 1,000-character title is the picture's alt (raw text, `<b>` kept as the parser gives it), and 1,001 fails with `LINE_MESSAGE`.
- **F4, fixed.** The row "white space around text counts" (`"a" * 500` + `<b>` + 250 spaces + `b` + 250 spaces) was added to `test_the_line_limit_counts_the_text_as_stored`. The `len(text.strip())` mutant is now killed (checked).

- **F5 fixed.** `test_the_navigation_document_counts_its_markup_too` is now parametrized over `<li></li>`, `<br>` (start tags only), `</p>` (end tags; with N1 kept as a docstring change, every end tag still counts in the nav) and `<!---->`. `MAX_MARKUP` is set to the nav's own count with 100 units, so exactly at the limit gives an outline, and one unit more gives `outline == ()` while the pages still read. The mutants that drop the nav's start-tag, end-tag or comment count are each killed (checked).

## Nits

- **N1, fixed by the docstring.** `_NavReader` now says it counts every start and end tag, matched ones too, so a self-closed tag counts twice, unlike a chapter. The behaviour is unchanged.
- **N2, fixed.** epub.py's comment now says "the HTML parser gave up".

## Also

- The CHANGELOG #329 line names the tag bound (1,000,000 characters) and the SVG title and table-of-contents label bounds, and cites D-783.
- My own mutation run over the new code: 16 mutants (13, plus the 3 nav-count mutants for F5). The first run had one survivor: the label-length reset. The two-label assertion above kills it. All 16 are now killed.
- Checks: ruff, format, lint-imports and deptry are clean. The fast suite (`not slow and not benchmark and not browser`) gave 7,846 passed, 8 skipped.

# Round 2 answer

- **R2-F1 fixed** in the round 2 fix commit: `test_the_copy_names_its_source_and_keeps_the_psf_notice` drops imports whose top package is `mutmut` (mutmut adds `mutmut.mutation.trampoline` to each file it mutates), then still asserts that the import set is exactly `{"re", "html", "html.entities"}`. This made mutmut's stats step fail in run 44460675356 (all 674 mutants counted not killed). The test was wrong under the mutation tool, not weakened: equality is kept outside it.
