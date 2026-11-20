# Plan: Issue #73, EPUB extraction and cover images (with the EPUB part of #5)

Thread "Add EPUB extraction and cover images", 13 Nov 2026. Item 19 of the approved v1.0 plan
(`plans/v1-remaining-plan.md`, wave 3, lane extraction). Critical: adds extraction golden files and
(recommended) three optional core fields. No code or tests before the coordinator approves.
D-numbers: the coordinator assigns them; the questions below are numbered q1 to q16.

## 1. What the sample shows (measured on main 1064e18)

`tests/corpus/epub/wells-the-time-machine.epub` (Standard Ebooks, EPUB 3.0, already in the corpus
with its licence row from #15, public domain text, CC0 for Standard Ebooks' own work):

- `META-INF/container.xml` → `epub/content.opf`. Spine of **18** XHTML documents: titlepage,
  imprint, chapters I–XII, epilogue, endnotes, colophon, uncopyright. The navigation document
  `toc.xhtml` (manifest `properties="nav"`) and `toc.ncx` are **not** in the spine.
- Navigation: one `nav epub:type="toc"` with **18 entries, all level 1**, one per spine document,
  titles "Titlepage", "Imprint", "I" … "XII", "Epilogue", "Endnotes", "Colophon", "Uncopyright";
  hrefs without fragments. Entries 3–15 are exactly the 13 truth chapters
  (`tests/corpus/truth/wells-the-time-machine.toml`). A second `nav epub:type="landmarks"` exists.
- Metadata: one `dc:title` "The Time Machine", one `dc:creator` "H. G. Wells" (role via
  `refines`), `dc:language` "en-GB", unique identifier
  "https://standardebooks.org/ebooks/h-g-wells/the-time-machine", `dc:date` "2014-05-25T00:00:00Z"
  (the ebook's date, not 1895).
- Cover: manifest item `images/cover.jpg` with `properties="cover-image"` (JPEG, 359,616 bytes),
  not in the spine. The titlepage has an `<img alt="">`; imprint and colophon each have the
  publisher logo with alt text.
- Markup: chapters are `<section epub:type="chapter">` with `<h2>` and `<p>`; the one endnote is
  `<li id="note-1" epub:type="endnote footnote"><p>… —﻿<abbr>Ed.</abbr> <a … epub:type="backlink">↩︎</a></p>`,
  referenced by `<a href="endnotes.xhtml#note-1" id="noteref-1" epub:type="noteref">1</a>` in
  chapter VIII. The text has U+FEFF word joiners around em dashes.
- A quick prototype with Python's `html.parser` (one line per block element) gives **368 text
  lines** over the 18 spine documents (79 in chapter I), so the golden file stays readable.

What follows: the sample exercises spine, nav, metadata, cover, headings, an endnote with a
noteref link and pictures with and without alt text. It has no tables, no `<br>`, no nested
outline, no fragments in the nav and no EPUB 2 NCX-only case; those are covered by made-up EPUBs
in the tests (section 6).

## 2. PR split (q1)

`.github/lanes.yml`: a PR changes the files of its own lane only (plus tests and docs). The work
touches three lanes. **Recommendation: three PRs, each merged before the next opens**, as #24 did:

1. **Core** (lane:core, critical, about 30 lines + tests): three optional fields with empty
   defaults (q6–q8). PDF output and every existing golden file stay unchanged, because the export
   leaves out fields at their default.
2. **Extraction** (lane:extraction, critical: golden files): `extraction/epub.py`, the cover
   functions for EPUB and PDF, the EPUB golden file, the broken-EPUB set of #5, Hypothesis tests.
   Opens only after #24 part 2 (PDF bookmarks) has merged, on a branch from main after it.
3. **App** (lane:app, small): register `.epub` in `EXTRACTORS`, give `BookInfo` the cover, add the
   EPUB to the nightly command-line test (D-224), update the two web tests that pin ".pdf only".
   `Closes #73` goes here; PRs 1 and 2 say "Part of #73".

Alternatives not chosen: (a) two PRs without the core fields (extraction then app), losing the
anchor, picture path and cross-kind order (q6–q8), so #75 would have to guess; (b) one PR across
extraction and app (breaks the lane rule; app is single-threaded).

## 3. Parser (q2)

**Recommendation: the standard library only.** `zipfile` for the container; `xml.etree.ElementTree`
for `container.xml`, the OPF and the NCX, after refusing any of them that declares an entity
(`<!ENTITY`, so no entity expansion or billion-laughs case can start; these files never need one);
`html.parser.HTMLParser` for XHTML content documents and the navigation document. `html.parser`
never fails on malformed markup, knows HTML named entities (`&nbsp;`, which EPUB 2 XHTML often
uses without a DTD), never expands custom entities and never fetches anything.

Alternatives not chosen:
- **lxml** (BSD-3-Clause): fast, recover mode, XPath; but a compiled dependency on three systems,
  its XML parser resolves entities unless configured, and it adds nothing the sample needs.
- **BeautifulSoup4** (MIT) on top of `html.parser`: a nicer tree, but one more dependency for what
  a 60-line handler does.
- **EbookLib**: AGPL-3.0, refused by the licence gate (issue criterion).
- `xml.etree` for XHTML too: fails on `&nbsp;` and on any malformed chapter, which is common.

No new dependency, so no licence row.

## 4. What extraction records from a spine document

### q3. Text lines

- Each spine document becomes one `Page` (number = spine position from 1, `width`/`height` None).
- **A text line is the inline text of one block element**: `p`, `h1`–`h6`, `li`, `dt`, `dd`,
  `td`, `th`, `caption`, `figcaption`, `blockquote`, `pre`, `div`, `section`, `aside`, `header`,
  `footer`, `address`, etc. (the HTML block elements). Text directly inside a container (`div`,
  `section`, `li` before a nested list) becomes a line of its own. Lines keep document order.
- **White space** as a browser shows it (CSS `white-space: normal`): runs of ASCII space, tab, CR,
  LF and FF become one space, also across inline boundaries; none at the start or end of a line.
  No-break space, U+FEFF, soft hyphen and every other character are kept as stored (TP rules handle
  them, as for PDF). Inside `pre` white space is kept.
- **`<br>` and a line feed inside `pre` end the line**; the next line's runs get the tag `br`, so
  layout knows it continues the same element (a poem line, an address). Alternative: keep the break
  as "\n" inside one line (one line per element, but a `TextLine` would hold several printed lines
  and every later stage would meet "\n" in text).
- Not recorded: `head`, `script`, `style`, `template`. Everything else with text is recorded,
  including hidden, MathML and ruby text, with its tags; layout and text steps decide (D-63).
- Ids as for PDF: `p{n}-l{i}` for lines, `p{n}-i{k}` for pictures.

### q4. Tags (`TextRun.tags`)

The run's ancestors from below `<body>` to the run, outermost first. Each element adds its **name**,
then, where present:

| Tag | From | Example |
|---|---|---|
| `#<id>` | `id` | `#note-1` |
| `epub:<token>` | each `epub:type` token | `epub:endnote`, `epub:noteref`, `epub:z3998:roman` |
| `role:<token>` | each `role` token | `role:doc-endnote` |
| `lang:<tag>` | `lang` / `xml:lang` | `lang:fr` |
| `hidden`, `aria-hidden` | `hidden`, `aria-hidden="true"` | |
| `link:<item id>` | `href` to a place in the book, resolved after all pages are read | `link:p16-l2` (the first item at or after `#note-1` on page 16); `link:p16` when it points at a whole document |
| `href:<as stored>` | any other `href` (web, mail, or an anchor that does not resolve) | `href:https://standardebooks.org/` |

Example, the noteref run in chapter VIII: `("section", "#chapter-8", "role:doc-chapter",
"epub:chapter", "p", "a", "#noteref-1", "role:doc-noteref", "epub:noteref", "link:p16-l2")`.
`class` and `style` are not recorded (presentational; Standard Ebooks' classes repeat `epub:type`).
More than 100 nested elements add no further tags (bounds a hostile file; text is still recorded).
A new run starts wherever tags or style change.

Alternative not chosen: element names only. #75 needs `epub:type` for notes and `aside`, ids and
links to tie a noteref to its note when several chapters number notes from 1, and `lang` keeps a
later language switch possible (Colin: keep options open, identifiers as printed).

### q5. Bold and italic

From the HTML default rendering (WHATWG rendering section), not the book's CSS: bold for `b`,
`strong`, `th`, `h1`–`h6`; italic for `i`, `em`, `cite`, `dfn`, `var`, `address`. `font` stays ""
and `size` 0 (no sizes). Alternatives: read the book's CSS (a CSS engine for little gain; tags
already carry the semantics); never set bold/italic (layout's existing run-style checks would see
nothing on EPUB).

### q6. Positions, and the order of lines and pictures (core field)

EPUB has no positions: every `box` is None. But the `Page` keeps lines and pictures in two tuples,
so where a picture stands between lines is lost, and #75 needs it to put a figure placeholder
before its `figcaption`. **Recommendation: core field `Page.order: tuple[str, ...] = ()`**: the
ids of all the page's items in the order the file stores them, set only where items have no
position (EPUB now, Markdown in #74); empty for PDF. `Content` checks it is empty or exactly the
page's item ids. Alternatives: (a) one shared counter in ids (`p3-l1`, `p3-i2`, `p3-l3`) so layout
reads order from ids (no core change, but ids become meaningful and PDF ids differ); (b) pictures
recorded as lines (mixes kinds).

### q7. Pictures (core field)

`<img>`, SVG `<image>` and `<svg>` with an `<image>` inside become a `Picture` with `alt` as stored
(SVG: its `<title>`). `Picture` says "its box is enough to find it again"; an EPUB picture has no
box. **Recommendation: core field `Picture.ref: str = ""`**: where the image is stored in the file,
its path inside the EPUB (`epub/images/titlepage.png`); empty for PDF. Lets a later export name or
copy figures (keep options open). Alternative: no field (the picture cannot be found again).

## 5. Outline, metadata, cover

### q8. Navigation → `Content.outline` (core field for the anchor)

- **Source**: the EPUB 3 navigation document's `nav` with `epub:type="toc"`; if there is none,
  the EPUB 2 NCX (`navMap/navPoint`). Recommendation over "NCX first": EPUB 3 says the nav wins and
  EPUB 3 files may carry a stale NCX for old readers.
- **Level**: nesting depth (`ol` in `li`, or `navPoint` in `navPoint`), 1 = top; the flat order and
  level rule of D-263 hold by construction. Deeper than 15 levels left out (as D-267 for PDF).
- **Title**: the text of the entry's `a` or `span` (nav) or `navLabel/text` (NCX), with white space
  folded as for text lines (q3) and nothing else changed. EPUB titles are markup, so "as stored"
  means as a reader shows it; PDF titles stay raw (D-266).
- **Page**: the spine position of the document the `href` names; None for a `span` heading without
  link or a document not in the spine.
- **Anchor**: an `href` with a fragment (`ch01.xhtml#sec2`) points inside a page, which matters
  for EPUBs that hold several chapters in one file (Project Gutenberg's split files do).
  **Recommendation: core field `OutlineEntry.item: str = ""`**, the id of the first item at or
  after the anchor, checked by `Content` to be on the entry's page. D-265 foresaw this ("a field
  added later (an EPUB anchor in #73) changes no golden file"). Alternative: no field; #75 matches
  the title text on the page as PDF layout does (D-272), which fails when nav label and heading
  differ ("Chapter One" vs "I").
- **Damage never fails the file** (as D-268): a broken or missing nav/NCX gives what could be read,
  or an empty outline.

### q9. Metadata

| Field | From | Sample |
|---|---|---|
| `title` | first `dc:title` (white space folded) | "The Time Machine" |
| `authors` | every `dc:creator` in order whose role (EPUB 3 `refines` `role`, EPUB 2 `opf:role`) is `aut` or absent; each kept whole | ("H. G. Wells",) |
| `date` | first `dc:date`, its date part (`YYYY`, `YYYY-MM` or `YYYY-MM-DD`) as PDF does | "2014-05-25" |
| `identifier` | the package's `unique-identifier` `dc:identifier`, as stored | the Standard Ebooks URL |
| `language` | first `dc:language`, as stored | "en-GB" |

Alternatives: all creators including illustrators and translators (they are not authors on an
audiobook label); prefer an ISBN or DOI among several identifiers (a guess about which one the
file means; the unique identifier is the one it declares).

### q10. Cover image

**Recommendation: not in `Content`.** A function per format in extraction,
`extract_cover(path) -> Cover | None` with `Cover(data: bytes, media_type: str)` defined in
`extraction` (only app reads it), registered by the app next to `EXTRACTORS`:

- **EPUB**: only the cover the file declares: the manifest item with `properties="cover-image"`
  (EPUB 3), else `<meta name="cover" content="<item id>">` (EPUB 2). No guessing from file names.
  Kept only if its bytes are JPEG or PNG (sniffed, not trusted from the manifest) and at most
  20 MB; otherwise no cover (GIF, WebP and SVG covers need an image library: follow-up issue).
- **PDF**: page 1 rendered by pypdfium2 (already a dependency) inside the `_PDFIUM` lock, scaled so
  the longer side is 1400 px, written as PNG with a 20-line stdlib writer (`zlib`, `struct`):
  there is no Pillow in the lock and pypdfium2's image export needs it. Alternative: add Pillow
  (HPND licence, not on the allowed list as written, and a large binary for one image).
- **App** (PR 3): the audio job asks for the cover after reading the document, writes it to the
  working folder (`cover.jpg` / `cover.png`, atomically), and passes the path in `BookInfo.cover`;
  output already checks JPEG/PNG and embeds it in MP3 and M4B. Any failure means no cover, never a
  failed job. The script job does not need it.

Alternatives not chosen: cover bytes in `Content` (bytes are not exportable, `to_data` refuses
them, and golden files would hold an image); a cover path in `Metadata` read by the app (the app
would have to open EPUBs itself, extraction's job).

### q11. Spine edge cases

- A spine document missing from the zip **fails the file** ("chapter-3.xhtml is missing"): a
  chapter dropped silently breaks faithfulness. Alternative: an empty page (the book plays with a
  hole in it).
- `linear="no"` documents are recorded in spine order, unmarked. Alternative: tag their lines
  `nonlinear` (no stage would read it in v1.0).
- An SVG spine document is read with the same parser (`<text>` lines, `<image>` pictures); another
  media type follows its manifest `fallback` to an XHTML document; if there is none, the page holds
  one `Picture` if it is an image, else nothing.
- The navigation document, when it is in the spine, is a page like any other (a printed table of
  contents is furniture for layout, per the truth README).
- Print page markers (`epub:type="pagebreak"`, `page-list` nav) have no text and are not recorded
  in v1.0; follow-up issue to record printed page numbers for citation.

## 6. Broken files, limits and tests (#5, EPUB part)

### q12. What fails, with which message (all `ExtractionError("<name>: …")`, never a traceback or hang)

| Case | Result |
|---|---|
| empty file | "the file is empty" |
| not a zip (random bytes, a PDF renamed `.epub`) | "not an EPUB, or the file is damaged" |
| truncated zip (the sample cut in half) | same |
| zip entries encrypted with a password | "the EPUB is password-protected" |
| no `META-INF/container.xml` | "the EPUB has no container file (META-INF/container.xml)" |
| container names a missing package file | "the EPUB's package file … is missing" |
| package file not XML, or declares an entity | "the EPUB's package file is damaged" |
| empty spine | "the EPUB has no chapters" |
| spine document missing | "the EPUB is damaged: … is missing" |
| DRM: `META-INF/rights.xml` (Adobe), `sinf.xml` (Apple), `license.lcpl` (Readium LCP), or `encryption.xml` encrypting anything with an algorithm other than the two font-obfuscation ones | "the EPUB is protected by DRM; sci2audio can read only EPUBs without DRM" |
| a member that decompresses past 64 MB, or more than 512 MB read in all (zip bomb), or more than 10,000 spine items | "the EPUB is too large or damaged" |
| unsupported zip compression | "not an EPUB, or the file is damaged" |

**Read, not failed:** font obfuscation only (fonts are never read); a content document with
invalid UTF-8 or a wrong declared encoding is decoded with U+FFFD for the bad bytes (as PDF records
an unmappable glyph); malformed XHTML (html.parser recovers); a broken or missing nav/NCX (empty
outline); no metadata; no cover. Issue #5 lists "wrong encoding" among broken files; the
recommendation is to read it with U+FFFD, since the rest of the book is fine and the U+FFFD stays
visible in the report. Alternative: fail the file.

### q13. Sample EPUBs and licences

Only the corpus file (already recorded in `tests/corpus/LICENSES.md` by #15, public domain / CC0).
Every made-up and broken EPUB is **built inside the tests** by a new helper
`tests/unit/epub_maker.py` (zipfile; like `pdf_maker.py`), including the password case (the
encryption flag set in the headers) and DRM marker files, so no stored fixture and no third-party
content is added. `tests/fixtures/README.md` gains a line saying so. Alternative: stored fixture
files (CC0, our own) like `password-protected.pdf`: only needed if a case cannot be built.

### q14. Golden file format

`describe_epub()` in a new `tests/unit/test_extraction_epub_corpus.py`: source line, metadata,
outline (level, page, item, title in repr), then per page the lines with id and runs
`{tags; b; i}text` in full, and pictures with ref and alt. Full text, so a changed word shows in
the diff (estimated 250 KB). Alternative: first 60 characters per line plus a hash (smaller, but a
changed word in mid-line shows only as a hash).

### Tests (PR 2)

- **Corpus truth** (extraction records, layout decides): 18 pages; metadata as in q9; outline = the
  18 entries of section 1, and entries 3–15 equal the truth chapters; each truth chapter title is a
  line tagged `h2` on its page; the truth endnote text (U+FEFF ignored, back-link arrow aside) is
  on the endnotes page in a run tagged `epub:endnote`; the chapter VIII noteref run has
  `link:` to that line; cover = the bytes of `epub/images/cover.jpg`, `image/jpeg`.
- **Golden file** for the sample (q14).
- **Made-up EPUBs**: EPUB 2 with NCX only (nested, levels); nav with fragments (`item` set) and a
  `span` heading (page None); `<br>` and `pre`; tables; `figure` with `img` and `figcaption`
  (`Page.order`); inline SVG image; bold/italic elements; `&nbsp;` and malformed XHTML; white-space
  folding across inline elements; UTF-16 content document; `lang`, `hidden`; internal and external
  links; a nested-element bomb (tags capped at 100); a cover by EPUB 2 meta, a GIF cover (none),
  no cover.
- **Broken set**: every row of q12, each with a `pytest.mark.timeout`.
- **Hypothesis** (ci and nightly profiles): any bytes give `Content` or `ExtractionError`; the
  sample with random bytes changed in the zip or inside one XHTML document gives `Content` or
  `ExtractionError`; any XHTML text built from a small tag alphabet gives lines whose text has no
  leading, trailing or double ASCII white space and whose ids are unique.
- **PDF cover**: page 1 of a corpus paper renders to a valid PNG (signature, IHDR size with longer
  side 1400) and a password-protected PDF gives no cover.
- Fast suite, `ruff`, `lint-imports`, `deptry src`, nightly Hypothesis profile before opening.

### PR 3 tests

Registered suffix `.epub`; `read_document` on the sample gives a `Document` (layout today puts the
boxless lines in file order as paragraphs; #75 makes headings); the audio job passes a cover path
whose bytes equal the EPUB's cover (fake voice, as the existing audio-job tests), and no cover
when extraction gives none or fails; nightly `test_cli_end_to_end.py` also converts the EPUB
(D-224); `test_web_pages.py` and `tests/browser/test_flow.py` expect ".epub, .pdf".

## 7. Order, size, risks

- **Order**: PR 1 (core) can open as soon as the plan is approved (the core lane is free; it does
  not touch `pdf.py`). PR 2 opens after both PR 1 and #24 part 2 have merged, on a branch from main.
  PR 3 after PR 2.
- **Size**: PR 1 about 30 lines of code, 80 of tests; PR 2 about 450 lines of code, 700 of tests
  plus the golden file; PR 3 about 40 lines of code, 120 of tests.
- **Risks**: real-world EPUBs vary far more than one Standard Ebooks file (Calibre and Gutenberg
  exports, EPUB 2 with entities); the made-up cases and Hypothesis cover the parser's robustness,
  not every producer's habits. Layout on EPUB stays paragraph-only until #75.
- **Follow-up issues to file**: GIF/WebP/SVG covers; printed page numbers (pagebreak markers,
  page-list).
- **Licences**: no new dependency, no copied code, no new sample text.
- **Feature IDs**: IN-02, OU-01.

## 8. Questions for the coordinator (recommendation first)

| q | Question | Recommendation |
|---|---|---|
| q1 | PR split | Three PRs: core fields, extraction, app |
| q2 | Parser | Standard library: zipfile, xml.etree with entity refusal, html.parser for XHTML |
| q3 | What a text line is | One per block element; `<br>` and `pre` line feeds end a line, next line tagged `br`; CSS white-space folding |
| q4 | Tag vocabulary | Element names plus `#id`, `epub:`, `role:`, `lang:`, `hidden`, `aria-hidden`, `link:<item id>`, `href:` |
| q5 | Bold and italic | HTML default rendering, no CSS |
| q6 | Order of lines and pictures | Core field `Page.order` (ids in stored order, empty for PDF) |
| q7 | Pictures | Core field `Picture.ref` (path inside the file) |
| q8 | Outline | nav toc over NCX; folded titles; level by nesting, max 15; page by spine; core field `OutlineEntry.item` for anchors; damage never fails |
| q9 | Metadata | As the table in q9 |
| q10 | Cover | Not in Content; `extract_cover` per format; EPUB declared cover only, JPEG/PNG ≤ 20 MB; PDF page 1 as PNG, 1400 px, stdlib writer; app writes it to the working folder; failure = no cover |
| q11 | Spine edge cases | Missing document fails; `linear="no"` recorded unmarked; SVG read; fallback followed; page markers follow-up |
| q12 | Broken files | The table in q12; wrong encoding read with U+FFFD, not failed |
| q13 | Samples | Corpus file only; every made-up and broken EPUB built in the tests |
| q14 | Golden format | Full text with tags per run |
| q15 | Follow-ups | Issues for GIF/WebP/SVG covers and printed page numbers |
| q16 | PR 1 timing | Core PR opens right after approval; PR 2 after PR 1 and #24 part 2 merge |

## 9. Decisions (coordinator, 13 Nov 2026 08:10 UTC, under D-80; all sixteen as recommended)

| D | Question | Decision |
|---|---|---|
| D-304 | q1 | Three PRs: core fields, extraction (after #24 part 2 merges), app |
| D-305 | q2 | Standard-library parser: zipfile, xml.etree with entity refusal for container/OPF/NCX, html.parser for XHTML |
| D-306 | q3 | One text line per block element; `<br>` and `pre` line feeds end a line, the next line tagged `br`; CSS white-space folding |
| D-307 | q4 | Tag vocabulary: element names plus `#id`, `epub:`, `role:`, `lang:`, `hidden`, `aria-hidden`, `link:<item id>`, `href:` |
| D-308 | q5 | Bold and italic from the HTML default rendering, no CSS |
| D-309 | q6 | Core field `Page.order`: item ids in stored order where items have no position, empty for PDF |
| D-310 | q7 | Core field `Picture.ref`: where the image is stored in the file |
| D-311 | q8 | Outline from the nav toc over the NCX; folded titles; levels by nesting, max 15; page by spine; core field `OutlineEntry.item` for anchors; damage never fails |
| D-312 | q9 | Metadata as the q9 table |
| D-313 | q10 | Cover via `extract_cover` per format; EPUB declared cover, JPEG/PNG up to 20 MB; PDF page 1 as PNG, 1400 px, stdlib writer; app writes it to the working folder; failure means no cover |
| D-314 | q11 | Spine edge cases as q11; a missing spine document fails the file |
| D-315 | q12 | Broken-file table as q12; wrong encoding read with U+FFFD |
| D-316 | q13 | Corpus file only; every made-up and broken EPUB built in the tests |
| D-317 | q14 | Golden file with full text and tags per run |
| D-318 | q15 | Follow-up issues for GIF/WebP/SVG covers and printed page numbers |
| D-319 | q16 | Core PR opens right after approval; PR 2 after PR 1 and #24 part 2 (PR #133) merge |
