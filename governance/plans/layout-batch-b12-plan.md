# Layout batch B12: code blocks (#281, #283, #284, #282)

Status: posted 19 Nov 2026 by the B12 layout thread. Base main 678fe3c. Batch plan: plans/next-batches-2026-11-19.md (D-776), rows 281/283/282/284, §3.
PR 1 is non-critical (no golden, snapshot, regression row or sentence-set change); work on it starts now. PR 2 (#282) is non-critical on the route chosen below and waits for web B17 to merge. Item numbers are fixed (PLAN-03).

## 1. #281 "Listing 3" captions name their code block (PR 1)

**Cause.** `layout/captions.py` knows only Figure/Table/Algorithm labels (and German ones), so "Listing 3: ..." stays a PARAGRAPH and the CODE block has no caption; textprep's notice step then says "A code block is skipped.". Textprep already names any placeholder through the captions that describe it (`_NoticeStep`, `wording.skipped`), CODE included, so no textprep source change is needed: "Listing 3 is skipped." / "Listing 3 wird übersprungen." / "Quelltext 2 wird übersprungen." come out of the existing wording.

**Change.**
1.1 `captions.py`: add `Listing|LISTING|Quelltext|QUELLTEXT` to `_NAMES` (German "Listing" is the same word), and a public `LISTING` tuple of those names. The label rule stays as is: a number, then a colon or full stop (or a bold label), so "Listing 1 shows ..." in running text stays a paragraph.
1.2 `captions.py`: a listing caption is cut where its first wholly monospace line starts (the line after it is code, as for an algorithm's numbered lines). Measured on made-up pages: a full-width caption line on the line pitch followed by code lines takes the first two code lines into its paragraph today (probe in the scratch notes); with the cut they go back to the code run. Uses `code.monospace` (captions imports code; code does not import captions, so no cycle).
1.3 `graphics.py` (`find_graphics`): a listing caption reads no float. A listing is text set in typewriter type, found later by `find_code`; walking from the caption would take the code lines into a FIGURE block. Known limit, stated in the module docstring: a listing printed as a picture gets no caption link (its picture stays an uncaptioned figure, as today).
1.4 `code.py` (`find_code`, after the CODE blocks are made): each listing caption that describes nothing describes the CODE block next to it in reading order: the one before or after it; when both are CODE, the nearer on the page (white between the caption's box and the code's nearest line; a neighbour on another page counts as farther). A CODE block is described by at most one listing caption this way. A caption next to no CODE block describes nothing and reads as printed.
1.5 Tagged path (EPUB/Markdown): a `figcaption` "Listing 1: ..." next to a `pre`+`code` block already describes it (`tagged._described`, `is_placeholder`); with 1.1 it now carries the label "Listing 1", so the notice names it too. One test pins it.

**Tests (written first, failing on main).** `tests/unit/test_layout_captions.py`: "Listing 3:", "LISTING 2.", "Quelltext 1:" are captions with their labels; "Listing 1 shows the loop" is a paragraph. `tests/unit/test_layout_code.py`: caption above / below a listing describes the CODE block; two listings each with a caption above, and each with a caption below, pair up right; a full-width caption on the pitch keeps the code lines out of the caption (1.2); a listing caption next to prose describes nothing; the code lines are not taken into a FIGURE (1.3); the property test keeps "every item in exactly one block". `tests/unit/test_layout_tagged.py`: figcaption + pre/code. Textprep notice unit test (AC-281.2) in `tests/unit/test_textprep_placeholders.py`: a CODE block described by "Listing 3" reads "Listing 3 is skipped."; German "Quelltext 2 wird übersprungen.". Test-only touch of a textprep test file, no textprep source (D-756 cross-lane note); #593 does not touch that file.
**Regression row:** none in this PR (AC-281.2: textprep PR #593 is open); it rides with the next textprep PR. I will name the row text in the PR body so the textprep thread can add it.
**Goldens:** none move (corpus has no "Listing"/"Quelltext" caption; checked by grep over tests/corpus, snapshots, regression and sentences; the full fast suite with snapshots confirms).

## 2. #283 one code block for a listing broken across a page (PR 1)

**Cause.** Confirmed on made-up pages (4 pages, running head and page number on each, listing from the foot of page 2 to the top of page 3): blocks read `code`, furniture `page-number 2`, furniture `running-head`, `code`. `find_code` joins only adjacent code paragraphs, and the page's furniture stands between them.

**Change.** 2.1 `code.py` (`find_code`): while a code run is open, FURNITURE blocks are held; if the next block is a code paragraph whose first line is on a later page than the run's last line, and it does not start a section, it joins the run and the held furniture is placed right after the joined CODE block (what a paragraph running across a page does with what it met, `paragraphs`/`_in_page_order`). Otherwise the held furniture stays where it was. Only furniture may stand between (the AC); a footnote, figure, caption or heading between still ends the run. The links-only and all-bold checks apply to the joined run, as now. Sections and caption links move with `new_of`, as now.
2.2 `build.py`: no change needed (find_code already runs last); the module docstring of code.py drops "A listing broken by a page break is two CODE blocks (#283)".

**Tests.** `test_layout_code.py`: the two-page listing is one CODE block with all its lines in order, followed by the page-2 page number and page-3 running head, then the prose; a listing on page 2 and another on page 3 with prose between stay two blocks; furniture between two code paragraphs on the SAME page (a side stamp) does not join them; a code paragraph after a page break that starts a section (heading) does not join. **Goldens:** none (seaborn's listing is on one page; snapshots unchanged).

## 3. #284 code in plain text: decision, propose closing

Finding: no layout rule can find code in plain text and leave prose alone.
- Extraction folds white space before layout sees a line (`extraction/text.py`, D-306): a 4-space or tab indent never reaches layout. An indent rule would need an extraction change in another lane, and even then indented lines in plain text are just as often prose: the corpus sample `sci2audio-sample-plain.txt` opens a paragraph with a tab; hanging-indent reference lists, block quotes, indented poems and addresses are common in text files.
- A "code punctuation" rule (`=`, `(`, `)`, `;`, `{}`) catches the formulas that plain-text papers write inline ("x = (a + b) / 2", "f(x) = 3x; g(x) = x^2"), which must be read, not skipped (faithful text, D-57), and misses code without punctuation ("import seaborn as sns").
- Code in a text file has a working route already: a Markdown file with a fenced or indented block is CODE (D-544).
**Proposal for Colin via the coordinator:** close #284 as not planned, with this reasoning in a closing comment (I can post it on the go). No code, no sample reading changes, so nothing waits for B6.

## 4. #282 code indent in the player: route choice (PR 2, after PR 1)

**Choice: the player route, non-critical.** `web/player.py` builds `view.code` for a CODE block of a PDF from its line boxes: each line indented by round((line.x0 - leftmost x0) / character width) spaces, the character width measured on the block itself (median of box width / characters over its lines; seaborn: 21 pt at 5.25 pt = 4 spaces). Tagged documents keep their text as is (Markdown code keeps its own spaces). `static/player.js` needs no change if `view.code` is already shown in a `<pre>` (to confirm when PR 2 starts; if it must change, it is one line).
Reasons: AC-282.1 asks for the indent "without inventing block text"; block text stays as printed, so the layout golden, the app golden and the read-along text do not move (no critical PR), and the player only draws. The layout route would add spaces to `Block.text` (the seaborn layout and app snapshots move, critical, and the script would carry text the PDF does not hold).
Files: `web/player.py`, `tests/unit/test_web_player.py`, maybe `tests/browser/test_player.py` (seaborn page 2: four argument lines indented, AC-282.2 via the corpus file in a unit test of `_block_view`). Web lane files, so PR 2 waits for web B17 to merge (batch plan §3) and is a web-lane PR from this thread (D-756 note).
Plan for PR 2 is short and lives here; I start it when B17 has merged and PR 1 is merged.

## 5. PR split, files, CHANGELOG

- **PR 1** `layout/issue281-283-code-captions`: `src/sci2audio/layout/captions.py`, `code.py`, `graphics.py`; tests `tests/unit/test_layout_captions.py`, `test_layout_code.py`, `test_layout_tagged.py`, `test_textprep_placeholders.py` (test only); `CHANGELOG.md`. Size: ~80 lines of code, ~200 of tests.
- **PR 2** `web/issue282-code-indent`: as in §4.
- CHANGELOG Unreleased (D-768), PR 1: "A code listing is named by its caption and read once (#281, #283): a "Listing 3: ..." caption (German "Listing" or "Quelltext") now names the code block next to it, so the voice says "Listing 3 is skipped." instead of "A code block is skipped.", and a listing that runs over a page break is one code block with one notice." PR 2: "The player shows a PDF's code with its indentation (#282): the lines of a code listing are indented as printed, measured from the page; the script and the audiobook are unchanged."

## 6. Out of scope, noted

- A prose paragraph whose last line is full width, followed on the line pitch by code lines, takes the first code lines into the paragraph (pre-existing, the same cause as 1.2 but outside captions). Splitting paragraphs at a change to wholly monospace lines touches the paragraph join rules for all documents (lessons: join rules must not override font-style changes, and the reverse). I will file it as a follow-up (v1.2.x proposed) and give the number.
