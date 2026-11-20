# Extraction batch B14 "Markup reader": plan (#175, #328, #329)

Thread: extraction lane implementation, started 19 Nov 2026 03:18Z. Base: main a9dad14 (has #514 0c8ebb2, #515 64c0c59, #600). One PR, critical (`risk:high`: #329 limits are a safety mechanism, #175 copies third-party code under PSF-2.0). Review: Opus high.

All numbers below were measured in this thread on main a9dad14 in the uv-managed CPython 3.12.16 of `.python-version` (CPU time, `ru_maxrss` of a fresh process; Linux cloud container), unless a row says otherwise. Prototypes of the #175 and #328 changes were run against the corpus goldens (results in each section); nothing is pushed.

## 1. #175: the reader's result on broken markup depends on the Python patch level

### Cause

`PageReader` (markup.py) and `_NavReader` (epub.py) subclass the standard library's `html.parser.HTMLParser`. CPython changed that parser in security releases, and it has changed **twice**, not once. I ran the reader on the issue's eight rows plus 19 more broken-markup rows on nine interpreters (uv-managed 3.12.10, 3.12.11, 3.12.12, 3.12.16, 3.13.3, 3.13.5, 3.13.6, Ubuntu's 3.12.3 with backports, and 3.13.18):

| rows (after `<p>A</p>`) | ≤ 3.12.11, ≤ 3.13.5 | 3.12.12, 3.13.6 | 3.12.16, 3.13.18, Ubuntu 3.12.3 |
|---|---|---|---|
| the issue's 8 rows, and `<title><b>x</b></title>B`, `</p` at the end, `<?x`, `<!-->B`, `<!DOCTYPE x` | old (markup read as text; `<textarea>`/`<title>` content parsed as tags) | patched | patched |
| `<plaintext><b>x</b>`, `<xmp><b>x</b></xmp>B` | `x` | `x` | `<b>x</b>` (raw text) |

Three generations, so "require a patched Python" (the issue's first option) would need a moving minimum, and a user's own Python (`requires-python = ">=3.12"`, any distribution build) can be any of them. Also, 3.13.18 differs from 3.12.16 in `html/parser.py` again (character references in attribute values, e.g. `href="?a=1&copy=2"` keeps `&copy=`, as the HTML standard says; incomplete `&#` at the end), and 3.14.10 is identical to 3.13.18 in behaviour (one regex spelling `\Z` → `\z`, which 3.12 does not know). `_markupbase.py`, `html/__init__.py` (`unescape`) and `html/entities.py` are identical from 3.12.10 to 3.13.18.

Note on AC-175.2: since D-378 every CI leg (Linux, macOS, Windows) runs the uv-managed 3.12.16, so "macOS has the older patch level" no longer holds; the three-system run proves nothing about patch levels. The fix below makes the stdlib version irrelevant instead, and the test pins that.

### Change (decision q1)

Copy CPython 3.13.18's `html/parser.py` and `_markupbase.py` (PSF-2.0) into one module `src/sci2audio/extraction/htmlparser.py`, unchanged except: the two files joined, `import _markupbase` replaced by the class defined above it, and the PSF copyright and licence notice at the top (licence gate rule 4). `PageReader` and `_NavReader` subclass that `HTMLParser`. The result is then the same on every Python, now and after future CPython security releases; it imports only `re`, `html.unescape` and `html.entities.html5`, which are identical on all measured versions.

- Why 3.13.18 and not 3.12.16 (whose behaviour the goldens follow): it is the newest behaviour (3.14.10 behaves the same), it is a superset of the 3.12.16 fixes, and it is closer to the HTML standard for attribute values. Measured: with the 3.13.18 copy on 3.12.16, **every golden is unchanged** (extraction, EPUB corpus, Markdown/text corpus, CLI golden, app corpus, layout: 30 snapshots and 383 tests passed); the corpus holds no attribute the difference touches.
- With the copy in place, all 27 rows give the same `Content` on all nine interpreters (measured: 0 differences).
- Licence (q1b): PSF-2.0 is permissive and GPL-compatible, and `THIRD_PARTY_LICENSES.md` already accepts it for dependencies (row "All other packages ... PSF-2.0 or CNRI-Python"), but `.claude/rules/licences.md` does not list it among the allowed licences by name, so this is the coordinator's call. New row in `THIRD_PARTY_LICENSES.md` for the copied file. The PR body names the licence.
- Tooling: `pyproject.toml` is the infra lane's file, so the copy is not excluded there: it carries a file-level `# ruff: noqa` (lint) and is run through `ruff format` once (quotes and line breaks only). A later refresh formats the new CPython file the same way and diffs it; the module docstring says so. The PR diff shows the `ruff format` step as its own commit on top of the verbatim copy, so the review can check the copy against CPython.
- Rejected alternatives: (a) override the changed methods in the subclass: the changes sit inside `goahead`, `parse_starttag`, `check_for_whole_start_tag`, `parse_comment`, `parse_html_declaration`, `set_cdata_mode` and the module's regexes, so overriding them is a copy anyway, only spread out and still mixed with whatever the stdlib does next; (b) require Python ≥ 3.12.16/3.13.18: does not cover distribution builds and must move with each CPython fix.

Fixed results (the patched behaviour, which the goldens follow), pinned per row:

| input after `<p>A</p>` | result lines after "A" |
|---|---|
| `<!-- x\n\ny` | none |
| `<a href` | none |
| `<![CDATA[x` | `x` |
| `<!x` | none |
| `<!--->B` | `B` |
| `<!-- a --!>B` | `B` |
| `<textarea><b>x</b></textarea>` | `<b>x</b>` |
| `<a b='x>B` | none |
| plus: `<title><b>x</b></title>B` → `<b>x</b>`, `B` runs; `</p` → none; `<?x` → none; `<!-->B` → `B`; `<!DOCTYPE x` → none; `<plaintext><b>x</b>` → `<b>x</b>`; `<xmp><b>x</b></xmp>B` → `<b>x</b>`, `B` runs | |

### Tests

- `tests/unit/test_extraction_markup_parser.py` (new): parametrized over the 15 rows above, each giving exactly that list of lines (AC-175.1, AC-175.2). Without the copy all 15 rows fail on 3.12.10/3.13.5, two (`plaintext`, `xmp`) fail on 3.12.12/3.13.6, and none fail on CI's 3.12.16, so on CI the row test alone cannot catch a revert to the stdlib parser; therefore also:
- a test that `PageReader` and `_NavReader` subclass `sci2audio.extraction.htmlparser.HTMLParser`, and an AST check that no module in `src/sci2audio/extraction/` imports `html.parser` or `_markupbase` (fails on a revert on any Python);
- a test that the copied module still holds the PSF notice and names CPython 3.13.18 (so a later refresh states its source).
- AC-175.3: corpus EPUB and Markdown goldens unchanged (measured above; the PR runs them).

## 2. #328: a picture's place depends on the white space before it

### Cause

`PageReader.add` sets `in_line = True` for every piece of text, white space included, before it checks whether that white space is folded away (D-306). A pretty-printed `<p>\n  <img/>\n  Some text</p>` then counts the picture as inside a line and places it after the line; the same paragraph without indentation places it before. An `id` just before the picture follows it.

### Change (decision q2)

White space that is folded away does not start a line: `in_line` is set only after `folded_away` returns False (two lines move in `add`). Both rows of the issue then give "picture, line", and an anchor before the picture names the picture in both. White space inside `<pre>` is never folded away, so a picture after kept white space in `<pre>` still follows its line.

### Goldens and layout (D-756, §3 of next-batches)

Measured with the prototype: **no golden moves**. The Time Machine EPUB (3 pictures) and both Markdown samples give identical `Content.order` and link targets; extraction, EPUB corpus, CLI golden, app corpus and layout snapshots all pass unchanged. So #328 moves no snapshot that layout (B12/B13) reads. The only tests that change are the three from PR #327 that pinned today's behaviour on purpose (`test_a_picture_after_white_space_in_a_line_still_follows_that_line` ×2, `test_an_anchor_before_such_a_picture_still_names_the_line`); they are rewritten to the new rule (names say so), not deleted.

### Tests

- Both issue rows give `order == (picture, line)` and the same anchor target (rewritten tests above, plus the `<span> </span>` row: folded, so before).
- A picture after real text, and after kept white space in `<pre>`, still follows its line (guards against moving the flag too far).
- Property: inserting folded white space (spaces, tabs, line feeds) between tags anywhere in a generated paragraph outside `<pre>` never changes `Page.order` or anchor targets (Hypothesis, existing markup strategies).

## 3. #329: inputs bounded only by bytes

### Measured at the byte limits (main a9dad14, before any change)

EPUB, one spine document read by `PageReader` (time is CPU):

| input | size | time | peak (`ru_maxrss`) | stopped by |
|---|---|---|---|---|
| empty `<p></p>` | 8 MB (1.2 M elements) | 13.4 s | 55 MB | nothing |
| empty `<p></p>` | **64 MB (9.6 M elements)** | **104.6 s** | 162 MB | nothing |
| `<br>` | 8 MB | 9.1 s | 50 MB | nothing |
| `<b></b>` inside one `<p>` | 8 MB | 10.8 s | 50 MB | nothing |
| stray `</p>` | 8 MB | 4.4 s | 50 MB | nothing |
| empty comments `<!---->` | 64 MB | 11.9 s | 162 MB | nothing |
| white space only | 64 MB | 0.2 s | 162 MB | nothing |
| **one `<p>` of `"word "`** | **64 MB** | 2.6 s | **1,047 MB** | nothing |
| 16 `<p>` of 4 MB each | 64 MB | 2.2 s | 208 MB | nothing |
| prose, 40 words per `<p>` (legitimate shape) | 64 MB | 9.8 s | 293 MB | nothing (322,638 lines) |
| one `<span>` per word (legitimate shape) | 16 MB | 7.3 s | 165 MB | item limit (1,000,000) |

So an EPUB at `MAX_TOTAL` (512 MB, eight 64 MB documents) of empty elements takes about 14 minutes, while every legitimate shape stops at the item limit within about 10 s. The cost per element is about 11 µs whether or not it holds text; elements with text are bounded by the item limit, empty ones by nothing. A single paragraph costs about 16 times its size in memory.

Markdown (`read_markdown`; the line limit is 250,000 lines):

| input | size | time | peak | stopped by |
|---|---|---|---|---|
| one line of `"word "` | 8 MB | 0.5 s | 184 MB | nothing |
| one line of `"word "` | 16 / 32 MB | 0.9 / 1.9 s | 335 / 637 MB | nothing |
| **one line of `"word "`** | **64 MB** | 4.1 s | **1,239 MB** | nothing |
| **one paragraph of 240,000 lines** (266 B each, no blank line) | **64 MB** | 7.6 s | **1,387 MB** | nothing |
| 120,000 paragraphs of 532 B | 64 MB | 9.3 s | 567 MB | nothing |
| 16 one-line paragraphs of 4 MB | 64 MB | 3.4 s | 392 MB | nothing |
| 16 paragraphs of 4 MB, 266 B lines | 64 MB | 7.0 s | 595 MB | nothing |

The Markdown peak is markdown-it's, before `PageReader` sees anything, and it follows the longest paragraph, not the longest line: a 64 MB paragraph of short lines is the worst case (1.39 GB), above D-579's accepted ceiling (about 900 MB for a Markdown file at the limits). Plain text (`read_text`, not in this issue): one 64 MB line also peaks at 1,047 MB (16 MB: 287 MB); see §6 follow-up.

Real files, for scale: the Time Machine EPUB has 566 tags, 873 items, longest line 2,235 characters; the Markdown samples 74 and 53 tags, longest line 145 and 202 characters, longest stretch between blank lines 193 and 202 characters. Legitimate books have fewer tags than items (Time Machine 0.65 per item; a one-`<span>`-per-word book about 0.5, since each word and each space between words is an item).

### Decision q3: a markup budget per book (EPUB and Markdown)

`MAX_MARKUP = 2_000_000` per book, in `markup.py`, counted by the same `Budget` as the items but as its own number: every start tag (void and self-closed ones included), every end tag that closes no open element (matched end tags are paid for by their start tag), every comment, declaration, processing instruction and CDATA section. Past it, `TooMuchText` with its own message: "the EPUB holds too much markup to read (more than 2,000,000 tags)" (Markdown likewise).

- Why 2,000,000: twice the item limit, so a book the item limit lets through is never refused by the markup count (real books hold 0.5 to 0.65 tags per item, so they reach the item limit first; a book needs more than two tags per piece of text, over 500,000 words, to reach this one). Measured cost at the limit: 2,000,000 empty `<p></p>` (14 MB) take 21.6 s and 47 MB; before, a 64 MB document took 105 s and a 512 MB book about 14 minutes.
- Alternative: 1,000,000 (about 11 s at the limit), which could refuse a very long book with two nested tags per word. I recommend 2,000,000.
- White space between tags stays uncounted: 64 MB of it costs 0.2 s.

### Decision q4: the longest line (EPUB and Markdown)

`MAX_LINE = 4_000_000` characters of one line (one `TextLine`: a paragraph, a heading, a list item, a line of `<pre>`) as the file stores them, counted in `PageReader.add` as the pieces arrive, before any run is built; folded-away white space counts nothing (it is never kept). Past it, `TooMuchText`: "the EPUB holds a paragraph longer than 4,000,000 characters". This bounds the 16-fold copy cost of one paragraph (4 MB → about 65 MB) and gives layout and the text steps no paragraph longer than 4,000,000 characters. Measured: 16 such paragraphs in one 64 MB document take 208 MB (vs 1,047 MB for one 64 MB paragraph).

### Decision q5: the longest block in Markdown, before parsing

`MAX_BLOCK = 4_000_000` characters between two blank lines (a line of only spaces and tabs is blank, as in CommonMark; CR LF, CR and LF all end lines), checked on the decoded text before markdown-it runs, beside `check_lines` and the marks count (D-579), with a linear scan that copies nothing. A paragraph, a tight list, a table, a block quote or a fenced code block longer than that is refused: "the Markdown holds a paragraph or block longer than 4,000,000 characters". Measured worst after the limit: 16 blocks of 4 MB of short lines in a 64 MB file, 595 MB, under the D-579 ceiling (before: 1,387 MB). The D-579 worst case (250,000 tight list items of one emphasis each, about 1.8 MB in one block) still reads. `MAX_LINE` (q4) also applies to Markdown after rendering, as a second guard.

Alternatives considered: a lower byte limit for Markdown (16 MB: 335 MB for one line) refuses large legitimate files that are fine today and still allows a 16 MB paragraph; accepting it as the user's own file leaves 1.4 GB per Markdown file and 1 GB per EPUB document.

### Tests (each fails without its limit)

- markup budget: with `MAX_MARKUP` patched to 1,000, a document of 1,001 counted things fails with the markup message for each kind (parametrized: empty `<p></p>`, `<br>`, `<b></b>`, stray `</p>`, `<!---->`, `<!DOCTYPE x>`, `<?x?>`, `<![CDATA[]]>`), and exactly 1,000 reads; the count is per book (two documents of 600 fail); matched end tags count nothing (1,000 `<p></p>` read at limit 1,000); a 1,000,000-element document at limit 1,000 stops early (`assert_near` against a 2,000-element document, so reading does not go on past the limit).
- longest line: with `MAX_LINE` patched to 1,000, a line of 1,001 characters fails and 1,000 reads; pieces split by inline tags add up (`<b>` halves); `<pre>` lines count one by one; folded white space between pieces counts nothing. At the real limit, one 8 MB paragraph is refused with a tracemalloc peak bound (measured in the PR; the bound is set at about half of what the same input costs with the limit removed).
- Markdown block: with `MAX_BLOCK` patched to 1,000, a block of 1,001 characters is refused before markdown-it is called (its parse patched to fail if called, as in the existing "refused before parsing" tests), exactly 1,000 reads; a line of spaces and tabs separates blocks; CR LF and CR line ends are counted as line ends; the scan is linear (`assert_linear`). At the real limit, an 8 MB one-line file is refused with a tracemalloc peak bound.
- `test_the_limits_are_the_decided_ones`: `MAX_MARKUP == 2_000_000`, `MAX_LINE == 4_000_000`, `MAX_BLOCK == 4_000_000` (the review lesson: monkeypatched limits survive tenfold mutants unless the decided values are pinned).
- Hypothesis: the existing "with low limits any Markdown reads or names a limit" and the EPUB fail-not-lose properties run with the new limits patched low, so any input either reads whole or names one of the limits.
- Consumers (the #574 lesson): no core dataclass gains an invariant (`TextLine`, `Page` unchanged); the new errors are `ExtractionError`s with existing handling in `app` and `cli` (`grep TooMuchText` shows only epub.py and markdown.py catch it).

## 4. #602 (alt text with HTML tags since markdown-it-py 4.3), decision q6

The limits do not touch alt text (attributes are not counted as text or markup). #602 is in my lane and in `markdown.py`, non-critical, with acceptance criteria, and no golden change expected. I propose to fold it into this PR (one more change in `markdown.py`'s image rendering plus four unit tests), because B15 is PDF-only and the next markup batch is not planned. If you prefer the critical PR to stay narrow, it waits for the next extraction batch.

## 5. Files, size, CHANGELOG

- `src/sci2audio/extraction/htmlparser.py` (new, about 960 copied lines, PSF notice), `markup.py` (+about 50: import, markup count, line count, #328 two lines), `epub.py` (import, two messages), `markdown.py` (block check, message; #602 if q6), `THIRD_PARTY_LICENSES.md` (row), `CHANGELOG.md`, tests in `tests/unit/` (`test_extraction_markup_parser.py` new, `test_extraction_epub.py`, `test_extraction_markdown.py`). All in the extraction lane plus its tests and docs (`*.md` is docs, allowed beside a lane's files by `.github/lanes.yml`); no infra file. About 250 lines of own code and tests plus the copy.
- Goldens touched: none (measured for #175 and #328; the limits refuse only inputs no golden holds).
- CHANGELOG Unreleased (D-768), under "Fixed":
  - "EPUB and Markdown files with broken markup read the same on every Python version: sci2audio now brings its own copy of Python's HTML parser (#175)."
  - "A picture in an indented (pretty-printed) EPUB paragraph is placed before its text, as in a browser, not after it (#328)."
  - "EPUB and Markdown files can no longer make sci2audio work for minutes or use gigabytes of memory: a book may hold at most 2,000,000 tags, a paragraph at most 4,000,000 characters, and a Markdown block between blank lines at most 4,000,000 characters (#329)."
  - (#602 if folded in.)
- KB (via the KB thread): q1 to q6 as decisions, the measured numbers in §3 with them.

## 6. Follow-ups (filed when the PR opens, v1.2.x proposed)

- Plain text: one 64 MB line in a `.txt` file peaks at 1,047 MB (`read_text`), the same paragraph problem as q4/q5 in `text.py`; propose the same longest-paragraph bound there.
- A later CPython refresh of `htmlparser.py`: nothing to file now; the module docstring says how to diff it against a newer CPython.

## 7. Questions for the coordinator

- q1 vendor CPython 3.13.18's HTML parser (PSF-2.0, licence gate call) vs requiring a minimum Python. Recommended: vendor.
- q2 folded white space does not start a line for pictures and anchors. Recommended: yes (no golden moves).
- q3 `MAX_MARKUP = 2,000,000` per book (alternative 1,000,000).
- q4 `MAX_LINE = 4,000,000` characters per line, EPUB and Markdown.
- q5 `MAX_BLOCK = 4,000,000` characters between blank lines in Markdown, before parsing.
- q6 fold #602 into this PR. Recommended: yes.
