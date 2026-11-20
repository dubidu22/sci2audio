# PR #609 review, round 1 (head 37ec25d)

Reviewer: B14 extraction review thread, Opus high. 19 Nov 2026. Plan: plans/extraction-batch-b14-plan.md (D-777).
Verdict: **changes requested** (1 must-fix, 2 should-fix, 2 nits) plus a required update from main (conflict).

## Checked and fine

- **Verbatim copy (#175).** 19de8ee's two sections diffed against CPython `v3.13.18` `Lib/_markupbase.py` and `Lib/html/parser.py` (raw.githubusercontent.com): the only differences are the removed `import _markupbase`, `class HTMLParser(ParserBase)`, and blank lines at the joins. The PSF licence text in the header equals CPython v3.13.18 `LICENSE` word for word, including "Copyright (c) 2001-2024". e98b94a equals `ruff format` of 19de8ee plus the `# ruff: noqa` line, and the AST of 19de8ee and 37ec25d's `htmlparser.py` is identical (37ec25d does not touch the file).
- **Licence gate.** Notice, clause-3 change summary and the THIRD_PARTY_LICENSES.md row are present; the `licences` CI job is green.
- **Goldens.** No snapshot, truth file or regression case in the diff (9 files: the module, markup.py, epub.py, markdown.py, CHANGELOG, THIRD_PARTY_LICENSES, three test files).
- **Core dataclasses.** `sci2audio.core` is untouched; no invariant added. `TooMuchText` is caught only in epub.py (pages loop and `outline`) and markdown.py.
- **Error path.** CLI on a 4.1 MB one-block Markdown file: `sci2audio: big.md: the Markdown holds a paragraph or block longer than 4,000,000 characters (counted between blank lines)`, exit 5 (the existing extraction exit code).
- **Limits, measured main 7e68106 vs PR (CPU s, ru_maxrss):** 9 M `<!---->` 10.4 s → refused 2.9 s; 2.5 M `<br/>` refused; nav with 3 M `<p></p>` 11.6 s → no outline at 4.0 s; Markdown `<textarea>` html block of 62 MB 1,148 MB → refused at 425 MB; Markdown 64 MB fenced code, indented code, `$$` math and `<pre>` html block with a blank line every 2.4 MB: 478–616 MB on both (under D-579's 900 MB; these blocks span blank lines but are not inline-parsed, so MAX_BLOCK does not need to cover them).
- **The nav addition (asked by the coordinator).** Sound: the nav document has its own `Budget`, so it never uses up the chapters' count, and past the limit `outline()` returns `()` and the book reads (D-311), as `test_the_navigation_document_counts_its_markup_too` pins. See N1 for its counting.
- **Mutation** (my own run, ROOT=/tmp/claude-0/wt-pr at 37ec25d, `PYTHONPATH=$ROOT/src`, tests `tests/unit/test_extraction_markup_parser.py tests/unit/test_extraction_epub.py tests/unit/test_extraction_markdown.py`, baseline 287 passed): still running at the time of writing; results so far are in the addendum below. Survivors, if any, are added before your fix commit.

## Must fix

**F1. One long tag still costs about 150 times its size, before any limit is checked.** The vendored parser's `locatetagend` regex (used by `check_for_whole_start_tag` and `parse_endtag`) keeps backtracking state per repeated attribute, so one start or end tag with many attributes blows up inside the regex, before `handle_starttag` runs:

| input (EPUB chapter, PageReader) | main 7e68106 | PR 37ec25d |
|---|---|---|
| `<p ` + `a ` × 4,000,000 + `>` (8 MB, one start tag) | 1,207 MB | 1,267 MB |
| `<p>A</p></p` + ` a` × 4,000,000 + `>` (one end tag) | | 1,267 MB |
| `<p a=">" ` + `a ` × 4,000,000 + `>` | | 1,267 MB |
| `<p ` + `a="b" ` × 1,600,000 + `>` (11 MB) | | 978 MB |
| `<nav>` entry `<a href=… ` + `a ` × 4,000,000 + `>` | | 1,267 MB |

A 64 MB chapter holding one such tag extrapolates to about 10 GB. It is pre-existing, but it is the #329 class ("bounded only by bytes"), and the CHANGELOG line of this PR says EPUB and Markdown files "can no longer ... take gigabytes of memory". Fix:

1. `markup.MAX_TAG = 1_000_000` characters per start or end tag (decided: D-783, coordinator 04:20Z; the corpus EPUB's longest start tag is 272 characters; 1,000,000 leaves room for long SVG `d` paths and `data:` URIs). Measured with a prototype: 64 tags of 999,980 characters (64 MB of attributes) read in 29.7 s at 284 MB; one tag over the limit is refused at 199 MB in 0.2 s.
2. Check it before the parser's own regex runs over the whole tag, in both `PageReader` and `_NavReader` (one shared helper in markup.py): for a tag at `i`, `locatetagend.match(self.rawdata, i + skip, i + MAX_TAG + 1)` (skip 1 for a start tag, 2 for an end tag; `endpos`, not a slice, so a normal tag copies nothing), and if the match reaches `i + MAX_TAG + 1`, raise `TooMuchText(MAX_TAG, "tag")`. Hook it by overriding `check_for_whole_start_tag` and `parse_endtag` and calling `super()`. Do not edit the copied module. A `rawdata.find(">")` check is not enough: `<p a=">" a a a …>` passes it (row 3 above).
3. `TooMuchText.message` for kind "tag": "the EPUB holds a tag longer than 1,000,000 characters" (Markdown likewise). In the nav, past it the book has no outline, as for the markup count.
4. Tests, each failing without the check: with `MAX_TAG` patched to 1,000, a start tag of 1,001 characters fails and one of 1,000 reads; the same for an end tag; the `a=">"` row; the nav row gives no outline; at the real limit, `<p ` + `a ` × 600,000 + `>` (1.2 MB) is refused with a tracemalloc peak bound (prototype 199 MB ru_maxrss; set the bound from your measurement with and without the check); a 1,000,000-tag chapter's time does not grow by more than the second regex pass costs (prototype 9.1 s → 10.5 s; optional: override `check_for_whole_start_tag` with one `endpos` match to avoid the second pass). Add `MAX_TAG == 1_000_000` to `test_the_markup_and_line_limits_are_the_decided_ones`, and add `MAX_TAG` (patched low) to the two "with low limits any … reads or names a limit" properties.

## Should fix

**F2. The navigation document's labels are not bounded by `MAX_LINE`.** One 60 MB nav label (`<li><a href="a.xhtml">` + `word ` × 12,000,000) peaks at 935 MB on main and on the PR. Count each entry label's characters as they arrive in `_NavReader.handle_data`, the same way `PageReader.add` does, and raise `TooMuchText(MAX_LINE, "line")` past `MAX_LINE`; the book then reads without an outline. Test with `MAX_LINE` patched to 1,000: label of 1,000 gives an outline, 1,001 gives `outline == ()` and the pages read.

**F3. An SVG `<title>` (a picture's alternative text) is not bounded by `MAX_LINE`.** `PageReader.handle_data` appends the title text to `self.svgs[-1][0]` before `add`, so `<svg><title>` + 60 MB + `</title><image href="a.png"/></svg>` peaks at 935 MB on main and on the PR, and hands layout and the text steps a 60 MB alt text, which the plan says they no longer get. Count the title's characters (per SVG) against `MAX_LINE` and raise `TooMuchText(MAX_LINE, "line")`. Test with `MAX_LINE` patched to 1,000: a title of 1,000 reads as the picture's alt, 1,001 fails with `LINE_MESSAGE`.

## Nits

- **N1.** `_NavReader` counts every end tag and counts a self-closed tag twice (`handle_startendtag` calls both handlers), so a nav entry `<li><a>…</a></li>` costs 4 where a chapter's costs 2; its docstring says "as in the chapters". Either count only unmatched end tags as `PageReader` does, or change the docstring to say the nav counts end tags too. No test change needed beyond what exists.
- **N2.** epub.py:278 still says `# html.parser gave up`; make it "the HTML parser gave up" as in `outline`.

## Branch update (MRG-03: conflict)

GitHub reports the PR as `dirty`: `CHANGELOG.md` conflicts with main ff7bf8d (#601, web). Merge `origin/main` into the branch (merge, never rebase), keeping both sides' lines under "Fixed", then the fix commit. No other file of this PR changed on main.

## Next

After the fix commit (and the merge): Linux CI green, then I run round 2 as the final round: `ci:full` on the new head (you add the label and remove it after the run, or I do), mutation over the new code, nightly Hypothesis seeds for the three extraction test modules on Linux, macOS and Windows.

## Addendum: decision

- D-783 (04:20Z): `MAX_TAG = 1_000_000` approved as proposed. Own `TooMuchText` message, pinned in the decided-values test, a refused-over-limit test with a tracemalloc bound, and the CHANGELOG #329 line names the tag bound too. Main is green again (#610).

## Addendum: mutation survivor (my run, see "Checked and fine" for the command)

**F4 (should fix). `self.line_length += len(text.strip())` survives** (mutant 12 of 24; 1–11 killed). No test has white space at the edge of a kept piece: "white space inside text counts" is one piece with inner spaces only. Add a row to `test_the_line_limit_counts_the_text_as_stored`: `"<p>" + "a" * 500 + "<b>" + " " * 250 + "b" + " " * 250 + "</b></p>"` with `MAX_LINE` 1,000 fails with `LINE_MESSAGE` (1,001 characters as stored).

**F5 (should fix). Removing `self.spend_markup()` from `_NavReader.handle_starttag` survives** (mutant 18): `test_the_navigation_document_counts_its_markup_too` adds `<li></li>` × 100, and the end tags alone reach the limit. Parametrize that test over units that count through one handler each, after your N1 choice: `<br>` × 101 (start tags only), `<!---->` × 101 (comments), and, if unmatched end tags still count, `</p>` × 101; each gives `outline == ()` with `MAX_MARKUP` 100, and the at-limit case still gives an outline.

Mutation result on 37ec25d: 24 mutants, 22 killed, 2 survived (F4, F5). Mutants: the six markup counts, line reset, both `>` → `>=`, the three decided values ×10, `strip()` in the line count, the block check, `_BLANK` without tabs, `_LINE` without CR, block reset, nav start count, outline `except TooMuchText`, #328 flag order, alt soft/hard break, alt code spans, the html.parser import in markup.py and epub.py.
