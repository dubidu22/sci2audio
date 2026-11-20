# Plan: Issue #74, Markdown, plain text and pasted text (with the #5 part for these formats)

Thread "Add Markdown, text and pasted text input", 13 Nov 2026. Item 20 of the approved v1.0 plan
(`plans/v1-remaining-plan.md`, extraction lane, after #73). Critical: adds golden files, truth
files and (recommended) two optional core fields. No code or tests before the coordinator
approves. The coordinator assigns D-numbers; the questions below are numbered q1 to q16.

The pattern is #73 (`plans/issue73-epub-plan.md`, D-304 to D-319): one line per block element,
the same tag vocabulary, `Page.order`, `Picture.ref`, full-text golden files, broken files built
in the tests. #75 (layout without positions) reads EPUB, Markdown and text, so the aim is that
it meets **one** shape: a Markdown file looks to layout exactly like an EPUB chapter, and a text
file like an EPUB chapter of plain `<p>` elements.

## 1. What I measured (main 2079d12)

- **markdown-it-py 4.2.0** (MIT, CommonMark-compliant, pure Python) is already in the lock and
  already installed at run time (spacy → typer → rich → markdown-it-py). **mdit-py-plugins
  0.6.1** (MIT; footnotes, dollar maths, front matter) is in the lock through dev tools only.
- Rendering with footnotes, maths, front matter, GFM tables and strikethrough works; output
  checked by hand (section 4).
- Speed (CommonMark's pathological cases, 20,000 repeats each): 20,000 nested `[` 0.25 s,
  80,000 emphasis delimiters 0.27 s, 20,000 table rows 0.62 s, 20,000 link definitions 0.43 s,
  4 MB of nested list 0.28 s, 5 MB of plain prose 0.77 s. No case was worse than linear.
- **Silent text loss found**: markdown-it stops parsing a block deeper than `maxNesting` (20 in
  the CommonMark preset) and **drops the rest of that block without an error**. 30 nested list
  items keep only the first 9 and lose the paragraph after the list; 30 nested block quotes lose
  their text. With `maxNesting` 100 depth 30 is kept, depth 200 is lost; with 1000, depth 3000
  raises `RecursionError`. Inline nesting (3,000 deep brackets or emphasis) never loses text.
  So a nesting limit with a check is needed (q15).
- Front matter that is not closed by `---` is read as ordinary Markdown (nothing lost).
- The web already keeps pasted text as `<name>.txt` in UTF-8 (`DocumentStore.store_text`, default
  name "pasted text") and shows the paste form as soon as `.txt` is a registered suffix
  (`index.html`, `pages.py:125`). Report `warnings` are already shown on the document page
  ("Notes:") and the CLI already prints warnings to stderr.
- #69 set the precedent for a dependency: `pyproject.toml`, `uv.lock` and
  `THIRD_PARTY_LICENSES.md` changed in the feature PR (#85, lane:output).

## 2. PR split (q1)

**Recommendation: three PRs, each merged before the next opens**, as #73 did (D-304):

1. **Core** (lane:core, critical, ~20 lines + tests): `Source.encoding: str = ""` and
   `Source.encoding_guessed: bool = False` (q10). Defaults are left out of the export, so every
   existing golden file stays unchanged.
2. **Extraction** (lane:extraction, critical): the HTML reader moved out of `epub.py` into a
   shared `extraction/markup.py` (EPUB golden file byte-identical), `extraction/text.py` (decoding,
   plain text), `extraction/markdown.py`, two own sample files with truth and golden files, the
   broken-file sets, Hypothesis tests; `markdown-it-py` and `mdit-py-plugins` as direct
   dependencies with licence rows ("Part of #74", "Part of #5").
3. **App** (lane:app, plus one CLI warning line, small): register `.md`, `.markdown`, `.txt`;
   the report warning for a guessed encoding; web tests that pin ".epub, .pdf"; a browser test for
   the paste form (axe); the nightly CLI test converts the Markdown sample. `Closes #74`.

Alternative: no core PR, the app re-detects the encoding itself through an extraction function
(as covers do); see q10.

## 3. Markdown parser (q2)

**Recommendation: markdown-it-py with mdit-py-plugins**, both pinned directly
(`markdown-it-py>=4.2,<5`, `mdit-py-plugins>=0.6.1,<0.7`), rows in `THIRD_PARTY_LICENSES.md`.

Alternatives not chosen:
- **Own parser**: CommonMark has about 650 spec examples of corner cases (lazy continuation,
  emphasis rules, link reference definitions); a hand-written parser would be wrong in many of
  them, and a wrongly parsed line is read wrongly.
- **mistune** (BSD-3) or **Python-Markdown** (BSD-3): not CommonMark-compliant, not in the lock.
- **cmarkgfm** (MIT): compiled C on three systems; no footnote or maths support.

## 4. Markdown → Content

### q3. Dialect

CommonMark, plus: GFM tables, strikethrough (`~~x~~`), footnotes (`[^1]`, Pandoc and GitHub),
dollar maths (`$…$`, `$$…$$`, Pandoc, GitHub, Quarto), YAML front matter. Raw HTML **on**
(CommonMark default: `<sup>`, `<br>`, `<details>` and comments are common in Markdown).
Off: typographer (no smart quotes: text as typed), linkify (needs another package; bare URLs stay
text, which the URL step #66 reads), task lists, definition lists, heading anchors (would invent
ids the file does not hold).

Alternative: CommonMark plus tables only (the issue's list). Then `[^1]` and `$x^2$` are read as
typed, and `*` inside TeX can turn into emphasis and lose its characters.

### q4. How a Markdown file becomes lines

**Recommendation: render the Markdown to HTML with markdown-it, then read that HTML with the EPUB
reader.** The reader (`_Reader`, `_Anchors`, `_runs`, `_resolve_links`, folding) moves unchanged
from `epub.py` into a shared `extraction/markup.py`; the EPUB golden file must stay byte-identical
(characterisation). So a Markdown file gets exactly D-306 to D-310:

- one page (number 1, no size); one text line per block element (`h1`–`h6`, `p`, `li`, `td`,
  `th`, `blockquote`, `pre`, ...); `<br>` (a hard break) and line feeds in code blocks end a line,
  the next line tagged `br`; soft line breaks fold to one space as a browser shows them;
- tags as D-307 (element names, `#id`, `role:`, `lang:`, `hidden`, `link:<item id>` for a link
  to a place in the file, `href:<as stored>` otherwise); bold and italic from the HTML default
  rendering (D-308), so `## Methods` gives a line tagged `h2`, bold;
- images become `Picture`s with their alt text and `ref` = the path as written (a `data:` URL
  gives ""); `Page.order` keeps where they stand between the lines; ids `p1-l<n>`, `p1-i<n>`.
- raw HTML inside the Markdown is read by the same reader (`<script>`/`<style>` skipped).

Rendering then re-parsing is faithful: markdown-it escapes `&`, `<`, `>`, `"` in text and the
reader unescapes them. Alternative: walk markdown-it's tokens directly (about 300 more lines, a
second tag reader to keep in step with EPUB's, and raw HTML inside Markdown would be read as
text).

### q5. Footnotes and maths: markup that #75 can recognise

The plugins' default HTML marks notes and maths only by `class`, which D-307 does not record. So
the renderer is set to the DPUB-ARIA and ARIA roles that Standard Ebooks' EPUBs already use:

- note mark: `<sup><a href="#fn1" id="fnref1" role="doc-noteref">1</a></sup>` → tags
  `sup, a, #fnref1, role:doc-noteref, link:p1-l<n>`; the mark is the number Markdown renders
  (notes are numbered in order of first use, also for `[^name]` labels);
- notes, at the end as the plugin places them: `<section role="doc-endnotes"><ol><li id="fn1"
  role="doc-endnote">…` → the same `role:doc-endnote` an EPUB endnote has. No back-link arrow
  (it is not in the file);
- maths: `<span role="math">x^2</span>` inline, `<div role="math">E = mc^2</div>` for display,
  the TeX as typed → `role:math`, so #75 can make a formula placeholder (D-55).

Alternative: record `class` tokens for Markdown only (a second vocabulary for the same things).

### q6. Front matter → Metadata

A YAML block at the very start (`---` … `---`) is not text a reader shows (Pandoc, Jekyll,
Quarto, R Markdown all hide it). **Recommendation**: its lines are not recorded; these keys fill
`Metadata`: `title`; `author` or `authors` (one string, a `[a, b]` list, `- a` lines, or `- name:
a` entries) in order; `date` (date part, as D-312); `lang` or `language`; `doi`, else
`identifier`, else `isbn`. Read by a small stdlib line reader (no YAML library: PyYAML's alias
expansion is a memory risk on hostile files and its types are more than we need). Anything else
in it is ignored; damage never fails the file; an unclosed block is ordinary Markdown.

Alternatives: (a) also record its lines, tagged `front-matter`, for layout to mark as furniture;
(b) no front matter support (the YAML becomes an `hr` and a setext heading "title: … author: …"
read aloud).

### q7. Outline

**Empty for Markdown.** The headings are lines tagged `h1`–`h6` (#75 builds the sections from
them); Markdown has no table of contents of its own. Alternative: copy the headings into
`Content.outline` (the same fact stored twice).

## 5. Plain text → Content

### q8. Lines and paragraphs

- One page (number 1, no size), `Page.order` set (no positions, as D-309).
- **One text line per printed line**; a paragraph is a run of non-blank lines (a blank line holds
  only spaces, tabs or form feeds). The first line of a paragraph is tagged `p`, each following
  line `p`, `br`: exactly what an EPUB `<p>` with `<br>`s gives (D-306), so #75 joins them the
  same way, and a line-end hyphen stays visible for the hyphen step.
- Line ends `\n`, `\r\n` and `\r`. White space folded as D-306 (runs of ASCII space, tab, form
  feed become one space, none at line start or end); no-break spaces and every other character
  kept as stored. No bold, italic, font or size.
- Metadata empty, outline empty.

Alternatives: (a) one text line per paragraph, its lines joined by a space (simplest for #75, but
the printed lines, a poem's or an address's, and line-end hyphens are lost); (b) white space kept
as in `pre` (indentation kept, but every later stage meets leading spaces).

### q9. Encoding (text and Markdown alike)

1. A byte order mark decides: UTF-8, UTF-16 LE/BE, UTF-32 LE/BE. Bad sequences become U+FFFD
   (as D-315). Not a guess: the file declares it.
2. No mark: strict UTF-8.
3. Otherwise **Windows-1252 as the WHATWG Encoding Standard decodes it** (what browsers do for
   "latin1" too): never fails; its five unassigned bytes become U+0081 etc., so no byte is lost.
   Marked as guessed (q10).

Alternatives: (a) charset-normalizer (MIT, already installed through requests): guesses among
many encodings, but its answer can change between versions (golden files), is slow on large
files and unreliable on short ones; v1.0 is English with a German interface, which Windows-1252
covers; (b) Latin-1 (loses the curly quotes and dashes Windows writes at 0x91–0x97); (c) fail
the file. Known limit: a UTF-8 file with one stray Latin-1 byte is read wholly as Windows-1252;
the notice tells the user to check.

### q10. The notice when the encoding was guessed

**Recommendation: two optional core fields**, `Source.encoding` (the WHATWG name the text was read
with: "utf-8", "utf-16le", "windows-1252", ...; "" for PDF and EPUB) and `Source.encoding_guessed`
(True only for the Windows-1252 fallback; `Source` refuses guessed without an encoding). The app
adds a report warning, which the document page already shows under "Notes:" and the CLI prints:
"notes.txt is not saved as UTF-8; it was read as Windows-1252, a guess. If letters look wrong,
save it as UTF-8 and open it again."

Alternatives: (a) no core change: the app asks extraction for the encoding by suffix, as it does
for covers (the file is read and decoded twice, and the exported `Content` doesn't say how it was
read); (b) a free-text `Source.notes` (English text inside core; the interface can't word it).

## 6. Broken files, limits, samples, tests (#5, Markdown and text part)

### q11. What fails, with which message (all `ExtractionError("<name>: …")`, never a traceback or hang)

| Case | Result |
|---|---|
| empty file (0 bytes) | "the file is empty" |
| only white space, or a byte order mark only | "the file holds no text" |
| Markdown with no text and no picture (e.g. only front matter or comments) | same |
| a NUL byte (no UTF-16/32 mark), or U+0000 after decoding | "not a text file" |
| starts like a PDF (`%PDF-`) | "this is a PDF, not a text file; open it with the .pdf ending" |
| starts like a zip (`PK\x03\x04`: EPUB, Word, ...), PNG, JPEG, GIF, gzip | "not a text file" |
| larger than 64 MB (`MAX_TEXT`, as an EPUB member) | "the file is too large" |
| Markdown nested too deeply for the parser (q15) | "the Markdown is nested too deeply to read" |
| cannot be opened | "cannot be opened (…)" as PDF and EPUB |

**Read, not failed**: invalid UTF-8 (Windows-1252, guessed, notice); bad sequences after a byte
order mark (U+FFFD); any Markdown at all (CommonMark never rejects input); unclosed front matter;
control characters other than NUL (kept; text steps decide).

### q12. Samples

Two own files written for the repo (no third-party text), `tests/corpus/markdown/sci2audio-
sample.md` and `tests/corpus/text/sci2audio-sample.txt`: a short made-up research note (about
2 KB each) with front matter, headings on three levels, emphasis, inline code, links (web, to a
note, to a heading), tight and loose and nested lists, a block quote, fenced and indented code, a
table, an image with and one without alt text, footnotes, inline and display maths, a hard break,
raw HTML (`<sup>`, a comment), an entity, and non-ASCII text (é, ü, µ, –, “ ”); the text file
with hard-wrapped paragraphs, a line-end hyphen, a numbered heading-like line and a list.
Licence **CC0-1.0**, one row each in `tests/corpus/LICENSES.md` (its "stored as downloaded" rule
gets "or written for sci2audio"; `test_corpus.py` learns the two folders). Encoding and line-end
variants (BOM, UTF-16, CRLF, CR, Windows-1252) are built in the tests from these bytes, not stored.

**Truth files** for both (D-60), so #75 has something to test Markdown blocks against: a new README
section with `headings` (level, text), `footnotes` (mark, text), `tables`, `figures` (alt),
`sentences` (a few, verbatim); `test_corpus_truth.py` checks them.

Alternative: samples only built inside the tests (no truth file, so #75 starts without one).

### q13. Golden files

Full text with tags per run, as D-317, one for each sample; the `describe` function of the EPUB
golden moves to a shared test helper with its output unchanged.

### q14. Suffixes and pasted text

`.md` and `.markdown` → Markdown, `.txt` → text. Not `.text`, `.mdown`, `.qmd`, `.Rmd` in v1.0
(easy to add later). Pasted text stays as the web keeps it: `<name>.txt` in UTF-8, default name
"pasted text", so it takes the plain-text path; registering `.txt` shows the paste form.

### q15. Limits

`MAX_TEXT` = 64 MB of file bytes. markdown-it `maxNesting` = 100 (depth 100 is far below Python's
recursion limit; measured safe at 200 levels of input), and a check that the parse reached the
limit: any token at level 99 or deeper fails the file (q11) instead of losing text silently.
Measured: every case that lost text had such a token; the check also refuses a few files that
were still read whole (lists nested 49 deep, quotes 99 deep), a price worth paying.
`RecursionError` is caught as the same failure. Timing tests for the pathological cases of section 1
(each under 2 s at 20,000 repeats).

### q16. Order

Core PR opens right after approval (the core lane is free); extraction after it merges; app after
extraction.

### Tests

- **PR 1**: `Source` defaults, refusal of guessed-without-encoding, export round trip, an
  existing golden file unchanged.
- **PR 2**: EPUB golden byte-identical after the move; Markdown and text truth tests; golden files;
  one unit test per Markdown construct (q3–q6) and per text rule (q8); encoding table (q9) with
  each variant of the samples giving the same lines; every row of q11 with `pytest.mark.timeout`;
  Hypothesis (ci and nightly): any bytes give `Content` or `ExtractionError` for both readers; any
  Markdown from a syntax alphabet gives lines without leading, trailing or double ASCII white
  space outside `pre` and unique ids; any list of paragraphs, encoded in each supported way, comes
  back line for line. Fast suite, ruff, `lint-imports`, `deptry src`, nightly profile before
  opening. Mutation pass by hand on the new modules.
- **PR 3**: suffixes registered; `read_document` on both samples gives a `Document`; a
  Windows-1252 file gives the report warning and the CLI warning, a UTF-8 file none; the paste API
  then a script job; browser test: paste form visible, axe clean, pasted text opens its document
  page; web tests expect ".epub, .markdown, .md, .pdf, .txt"; nightly CLI end-to-end converts the
  Markdown sample.

## 7. Size, risks, follow-ups

- **Size**: PR 1 ~20 lines + 60 of tests; PR 2 ~350 lines of code (move excluded), ~700 of tests,
  two samples, two truth and two golden files; PR 3 ~40 lines + 150 of tests.
- **Risks**: Markdown flavours vary (MyST, Pandoc attributes, Obsidian links): those are read as
  CommonMark text, never lost. Layout keeps Markdown and text as plain paragraphs until #75.
- **Follow-ups to file**: none required; possible later: more suffixes (`.qmd`, `.Rmd`), heading
  anchors for `[x](#heading)` links.
- **Licences**: markdown-it-py MIT, mdit-py-plugins MIT, mdurl MIT (already installed through
  rich); own samples CC0-1.0.
- **Feature IDs**: IN-03.

## 8. Questions for the coordinator (recommendation first)

| q | Question | Recommendation |
|---|---|---|
| q1 | PR split | Three PRs: core fields, extraction, app (+ one CLI warning line) |
| q2 | Markdown parser | markdown-it-py + mdit-py-plugins, direct dependencies, MIT |
| q3 | Dialect | CommonMark + GFM tables, strikethrough, footnotes, dollar maths, front matter; raw HTML on; typographer, linkify, anchors off |
| q4 | Markdown to lines | Render to HTML, read with the EPUB reader moved to a shared module (EPUB golden unchanged); one page |
| q5 | Notes and maths | Rendered with roles `doc-noteref`, `doc-endnotes`, `doc-endnote`, `math`; mark = rendered number; no back-link arrow |
| q6 | Front matter | Not recorded as lines; title, authors, date, language, identifier to Metadata by a stdlib reader; damage never fails |
| q7 | Markdown outline | Empty |
| q8 | Plain text lines | One line per printed line; paragraph at blank lines; `p`, continuation lines `p`, `br`; D-306 folding; one page with order |
| q9 | Encoding | BOM, else strict UTF-8, else WHATWG Windows-1252 (guessed) |
| q10 | Notice | Core fields `Source.encoding`, `Source.encoding_guessed`; app report warning and CLI warning |
| q11 | Broken files | The q11 table |
| q12 | Samples | Two own CC0 files in the corpus with truth files; variants built in tests |
| q13 | Golden | Full text with tags per run, shared describe helper |
| q14 | Suffixes | `.md`, `.markdown`, `.txt`; pasted text as today's `<name>.txt` |
| q15 | Limits | 64 MB; nesting 100 with a fail-not-lose check; timing tests |
| q16 | Order | Core PR now; extraction after it; app after extraction |

## 9. Decisions (coordinator, 13 Nov 2026 14:48 UTC, under D-80; all sixteen as recommended)

| D | Question | Decision |
|---|---|---|
| D-337 | q1 | Three PRs: core, extraction, app |
| D-338 | q2 | markdown-it-py + mdit-py-plugins, direct dependencies, MIT |
| D-339 | q3 | Dialect: CommonMark + GFM tables, strikethrough, footnotes, dollar maths, front matter; raw HTML on; typographer, linkify, anchors off |
| D-340 | q4 | Render to HTML, read with the EPUB reader moved to a shared module, EPUB golden unchanged, one page |
| D-341 | q5 | Notes and maths with roles `doc-noteref`, `doc-endnotes`, `doc-endnote`, `math`; mark = rendered number; no back-link arrow |
| D-342 | q6 | Front matter not recorded as lines; title, authors, date, language, identifier to Metadata by a stdlib reader; damage never fails |
| D-343 | q7 | Markdown outline empty |
| D-344 | q8 | Plain text: one line per printed line, paragraph at blank lines, `p` and `br` tags, D-306 folding, one page with order |
| D-345 | q9 | BOM, else strict UTF-8, else WHATWG Windows-1252 marked guessed |
| D-346 | q10 | Core fields `Source.encoding` and `Source.encoding_guessed`; report warning and CLI warning |
| D-347 | q11 | The q11 broken-file table |
| D-348 | q12 | Two own CC0 sample files in the corpus with truth files; variants built in tests |
| D-349 | q13 | Full-text golden with tags per run, shared describe helper |
| D-350 | q14 | `.md`, `.markdown`, `.txt`; pasted text as `<name>.txt` |
| D-351 | q15 | 64 MB limit; nesting limit 100 with a fail-not-lose check; timing tests |
| D-352 | q16 | Core PR now, extraction after it, app after extraction |
