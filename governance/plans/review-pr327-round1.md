# Review PR #327, round 1 (head f88ffa0)

PR: extraction: refuse text, Markdown and EPUB files too large to read safely, and huge covers (#174, #158, #165; #298). Plan: plans/input-limits-plan.md, D-579 with addendum. Not critical.

**Verdict: changes requested, 4 items (R1-1 to R1-4).** The limits, numbers, messages, cover header reading and the #298 timing conversion are right; the fixes below are small.

## What was checked

- Fast suite on the head, Linux, `-n 4`, `HYPOTHESIS_PROFILE=ci`: 4768 passed, 1 skipped, 76 snapshots passed. ruff, format, lint-imports, deptry clean. CI on the head: all three systems green.
- Slow tests: `test_a_file_of_exactly_the_limit_still_reads` passes (text, 500,000 lines). `test_a_book_of_more_items_than_the_limit_fails` **fails: pytest-timeout at 60 s** (R1-4).
- Worst cases reproduced (CPU time, peak RSS growth, one process, Python 3.12, Linux):
  - Markdown `"- a *b*\n"` × 250,000: read 26.5 s, +864 MB; layout 3.7 s, peak +864 MB (PR: 24.6 s, +888 MB).
  - EPUB `<p>a</p>` × 499,999: read 10.0 s, +191 MB; layout 7.2 s, peak +567 MB (PR: 9.3 s, +176 MB, 559 MB).
  - #158 row (197 tokens, 200,000 children): main +359 MB, PR +36 MB (PR: 369 → 39 MB).
- Real books: a 10 M character hard-wrapped book is about 143,000 to 160,000 lines and, at our own density of 13 marks per 1,000 characters, 130,000 marks: within 250,000 lines and 500,000 marks. The corpus EPUB uses 834 items.
- Budget counts text pieces before they merge into runs (`add`, not `_runs`): confirmed, so one line of `<i>a</i>` is bounded.
- Fourth Markdown message ("the Markdown is too large to read (more than N pieces of text)") matches the EPUB one and the D-394 bracket style. Fine.
- Covers: `pixel_size` reads real images right: ffmpeg JPEG and PNG, 16-bit RGBA PNG, a Pillow progressive JPEG with a 3 KB EXIF and a 70 KB ICC profile (several APP2 segments), a CMYK JPEG, an 8-bit grey PNG, and the corpus EPUB's cover (1400 × 2100 JPEG, still kept). Truncated, zero-length and scan-first headers give None, and the Hypothesis property covers any bytes after either signature. No crash path found.
- tracemalloc bounds: all relative to inputs of a few MB with bounds at 20 MB / 40 MB / 1 GB against measured peaks well below them; Python allocations are the same on the three systems, and CI passed on all three. `assert_linear` on Windows has the 62.5 ms floor, so a base run under it allows 2 s for the large run, about 4 times what the slowest case needs. Robust.
- White space folding in `add` (`folded_away`): differential test of main against the PR on 9,000 random XHTML snippets (p, i, b, span, div, pre, br, img, a id, a href, spaces, tabs, line feeds, no-break spaces). The text and runs of every line are identical. 111 snippets differ, every one only in `Page.order` and in the link targets that follow from it: R1-1.

## Fix list

**R1-1. Folding white space away moved pictures and anchors.** `picture()` places a picture after the line being read when `self.segments` is non-empty. White space at the start of a line used to be a segment and is now never kept, so in the usual pretty-printed form the picture moves from after its line to before it, and an `id` just before it now names the picture instead of the line:
- `<p>\n  <img src="x.png" alt=""/>\n  Some text</p>`: main `('p1-l1', 'p1-i1')`, PR `('p1-i1', 'p1-l1')`.
- `<p><span> </span><img src="x.png" alt=""/>Text</p>`: the same.
- `<span><b><a href="#q">\t<a id="q"/><img src="x.png" alt=""/>\n d a`: the link becomes `link:p1-i1` (main `link:p1-l1`).

The PR says the output is unchanged; this is an unannounced change to `Content.order` that no golden covers (the corpus EPUB has no inline picture). Fix: keep main's placement exactly. For example a flag `self.in_line`, set by `add` for any non-empty text before the fold check and cleared in `flush`, used by `picture()` in place of `self.segments`. Add a test that pins the first two examples to main's order and the third to main's link target. Whether main's rule is the right one (the compact form `<p><img/> text</p>` gives the other order) is now #328, out of scope here.

**R1-2. Ids and link records are not counted, and they stay for the whole book.** `start` keeps every `id` (in `pending`, then `anchors.items`) and `tags` keeps every `<a href>` (in `anchors.links`), even for an element with no text. Measured on the head, tracemalloc:
- 300,000 `<a id="iN"/>` (5.0 MB of XHTML): peak 54 MB, 181 B each;
- 300,000 `<a href="#q"/>` (4.2 MB): peak 52 MB, 173 B each.

That is 12 to 15 times the file, so about 1 GB for one 64 MB chapter and 6 to 7 GB for a book at `MAX_TOTAL` (512 MB): the #158 problem the PR closes, and Markdown is covered only by its mark limit. Fix: spend one item from the budget for each `id` taken into `pending` and for each link record appended in `tags`. Real books hold far fewer ids and links than lines. Add fast tests with `MAX_ITEMS` patched low: a chapter of empty `<a id>` and one of empty `<a href>` each fail with the EPUB message, and a book exactly at the limit still reads.

**R1-3. The open-element stack and the open-element counter are not bounded.** 300,000 unclosed `<span>` (1.8 MB) hold 300,000 `_Element`s: peak 51 MB, 170 B each, 28 times the file, so about 1.8 GB for one 64 MB chapter. 300,000 distinct tag names (`<t1></t1><t2></t2>…`, 5.5 MB) leave a key each in `self.open` after they close: peak 33 MB, 110 B each, about 400 MB per chapter. Fix: (a) raise `TooMuchText(self.budget.limit)` in `push` when the stack is already `budget.limit` deep (one limit and one message, about 170 MB at the limit); (b) delete a name from `self.open` in `closed` when its count reaches 0. Tests with `MAX_ITEMS` patched low for (a), and a check that `reader.open` is empty after reading 1,000 distinct closed tags for (b).

**R1-4. The slow EPUB test times out.** `test_a_book_of_more_items_than_the_limit_fails` runs under the module's `pytestmark = pytest.mark.timeout(60)`. The PR measured 54 s; here it took 63.5 s and failed with "Timeout (>60.0s) from pytest-timeout". The nightly runners on macOS and Windows are slower. Fix: give this test its own `@pytest.mark.timeout(600)` (or another bound with the same margin), and say in the PR how long it took.

## Deferred (issues filed)

- #328: whether a picture lands before or after its line depends on the white space before it (main's behaviour, kept by R1-1).
- #329: empty EPUB elements (time, not memory: 300,000 empty `<p></p>` about 17 s under tracemalloc) and one long plain Markdown line (about 1 GB at 64 MB, the PR's out-of-scope note) are still bounded only by bytes.

## Merge

After R1-1 to R1-4 and a green run. PR #325 (lean CI) is still open, so all three systems run on every push today; if it lands first, the review thread adds `ci:full` before merging.
