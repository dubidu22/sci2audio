# sci2audio feature status (19 Nov 2026)

Copy of the Doc https://claude.ai/artifact/APnyYwUgqxneF6zRBdELtp (the Doc is the live version). Checked against main, CHANGELOG.md and GitHub milestones on 19 Nov 2026 ~07:00Z.

## Where it stands

sci2audio turns a PDF, EPUB, Markdown or text file into a faithful offline audiobook, in English and German, with a read-along player in the new Working Reader design. Version 1.0.0 is on PyPI. Everything for v1.1 (German) and most of v1.2 is merged on main with its tests green, but v1.1.0 is not tagged or published: publishing is parked until the v1.4 installers (D-721).

Milestone counts on GitHub today: v1.1 done, v1.3 The Working Reader done except one flaky browser test (#437), v1.2 has 21 open issues (all planned into batches), v1.2.x 52, v1.4 19, v1.5 7, Later 16.

## Implemented and tested

All of this is merged to main with CI green. Items marked **(1.0.0)** are also in the published PyPI release; the rest is on main only.

**Reading files and PDF extraction**

- PDF, EPUB, Markdown, plain text and pasted text in, with bookmarks, covers and metadata (1.0.0).
- Reading order, columns, headings, sections, footnotes, captions and lists; running heads, page numbers and line numbers left out (1.0.0).
- Damaged, hostile or huge files refused safely: PDFs read in a separate process with memory and time limits; size limits for text, Markdown and EPUB (#185, #174, #158).
- Turned pages read upright; contents pages and page labels recognised (#537, #529, #535).
- Scanned picture-only pages named in the report (#186); a PDF with unreadable fonts stops before voicing instead of reading nonsense (#442 parts 1–2, #187).
- Page progress ("page 120 of 400") and a quick cancel while a PDF is read (#343, #344).
- Plain-text titles and lists recognised (#466); EPUB imprint, colophon and index left out by default (#190).

**Reading rules: what the listener hears**

- Every change is a marked edit with a reason, shown in a report; nothing is rewritten silently (1.0.0).
- Citations, links, DOIs, e-mail addresses removed with the sentence kept whole; formulas, tables, figures and code blocks get a short spoken notice (1.0.0, #280, #281).
- Numbers, statistics, units, abbreviations, symbols, ligatures and line-end hyphens read correctly (1.0.0, many fixes since).
- Footnotes read right after the sentence that marks them (#213).
- Long sentences cut at a natural clause and spoken as one sentence (#480); spelled-out acronyms at your own pace (#295).
- Readings are stable: a second pass over the script reads the same (dozens of fixes, D-577, D-605).

**German**

- German voice Kokoro Thorsten, offline (#211).
- Language guessed when the file states none (#219, #237).
- German abbreviations, units, numbers, dates, statistics, links, citations, sentence ends, legal forms and hyphens (#96, #101, #113, #130, #227, #229 and more).
- Spoken notices and footnote introductions in German (#212).
- A real German paper in the test corpus (#235).

**Player and web app (The Working Reader)**

- Local interface on your own computer only, English and German, privacy page (1.0.0).
- New design: cobalt rail, library table with search and drag-and-drop, reading shelf, Settings, Voices with previews (#385–#390, #416, #417, #419).
- Prepare page with the job inline; choose and reorder chapters (#391, #119).
- Listen page with a static reading highlight, side panel, docked player, resume bar, Focus listening, keyboard shortcuts, markers with notes (#392–#394, #452, #471, #474).
- Speed control, remembered position, figures, tables and formulas shown as page crops where their notice is read, code shown with its indentation (#152, #153, #293, #282).
- Subtitles (SRT and WebVTT) next to each chapter and the M4B (#214).

**Desktop app, files and command line**

- MP3 per chapter and an M4B with chapters, cover and AI-voice label; interrupted runs resume (1.0.0, #504).
- Each audiobook in its own folder under Documents/sci2audio; removing a document deletes its files after a warning, with "Keep the audiobook files" (#469, #470).
- Command line: script, convert, listen, voices, clean (1.0.0, #154).

**Release and safety**

- v1.0.0 on PyPI, installed and tested on macOS, Windows and Linux by the release workflow (#80).
- Nothing leaves your computer: no account, upload or telemetry; security scans in CI (1.0.0, #12).

## Coming next: the rest of v1.2

These batches finish v1.2 and cover all 21 of its open issues. Three run now, side by side in separate lanes; the rest follow when the batch before them in the same lane merges. The order is a plan approved by Claude (D-761, D-776), not set by Colin, except that Colin put the glyph-shape reading (B18) into v1.2.

**Running now**

1. **Citation lists and join words** (textprep, B9): "[1], [2] and [3]" reads as one citation, author nests keep every name, no stray "and" before a removed link (#414, #415, #402). Pull request open.
2. **Page edges, columns and fractions** (layout, B13): small repeated edge lines such as continued table headers stay in the text, text inside a figure no longer counts as a column, a fraction at a line end stays in its sentence, faster figure grouping (#156, #238, #322, #354). First pull request open.
3. **Markup reader** (extraction, B14): broken EPUB/HTML markup reads the same on every Python, pictures stay where shown, tighter EPUB and Markdown limits (#175, #328, #329, #602). Final review round.

**Queued, in this order per lane**

4. **Second-run readings** (textprep, B10, after B9): "2x m²", label and version numbers, statistics notation and other shapes read the same on both passes (#379, #405, #150).
5. **Code lines, formula notice, second German paper** (textprep, B11, after B10): when you turn off the code-block skip, each code line is read on its own with a pause; "Formel 3.2" read with "Punkt"; a second German paper in the test corpus (#292, #249, #468).
6. **PDF reader child** (extraction, B15, after B14): less memory on drawing-heavy PDFs, a clean Ctrl-C at any moment, reader costs on macOS and Windows documented (#355, #367, #356).
7. **Letters from glyph shapes** (extraction + app, B18, after B15): PDFs whose fonts hold only glyph numbers are read by recognising the letters' shapes, so they can be voiced instead of stopped (#618, #442 part 3). Plan approved.

## Coming later, by release

The order of the releases is Colin's (roadmap D-453 to D-460, reordered by D-666 and D-722). The order inside v1.2.x and between items of one release is a plan only.

1. **v1.2.x, polish (52 open, no order set yet).** Mostly follow-ups found in reviews: rarer citation, number and unit shapes that read differently on a second pass, German dating brackets and times (#588, #591, #594, #595), arrows like "=⇒" (#590), raised exponents before K/M/B (#576); explain the paper's own abbreviations (#346) and say known acronyms as words, "BERT" as "Bert" (#296); more pictures in the player (Markdown, GIF/WebP, audiobooks opened with listen: #579–#581); speech cache kept out of backups (#531); listing layout details (#599, #603, #612).
2. **v1.3 The Working Reader** is built. One flaky WebKit test remains (#437).
3. **v1.4, ready for others** (Colin's scope; order inside is plan):
   1. Installers with an app window for macOS, Windows and Linux, with smoke tests (#215, #13). Publishing to PyPI resumes here.
   2. Public plugin interface for text rules, with docs for plugin authors (#216, #203).
   3. Opt-in update check (#217).
   4. Layout edge cases: nested columns, Roman heading numbers, accents drawn apart, scatter plots, rule-less tables, page-label table, EPUB page numbers and covers (#32, #49, #125, #59, #56, #41, #135, #134 and others).
4. **v1.5 Study layer** (order from the design plan): an ADR first (#395), then the capture model (#396, #475), capture while listening (#397), a Captures page (#398), captures on the library and shelf (#418), export (#399).
5. **Later, no date:** read-along on the PDF page images (#155), keep playing between pages (#400), keep finished chapters when a job fails (#401), word-level highlighting and subtitles (#348, #352), your own abbreviation list (#347), footnotes where printed as an option (#301), Nature-style superscript citations (#100), en-US/en-GB spelling (#114), a layout model (#25); also formulas read aloud, OCR, DOCX/HTML, a batch queue and a local LLM (D-460).

Small leftovers still sit in the v1.0.1 and v1.1 milestones (11 issues, such as screen-reader navigation #314 and the start token #117); they have no batch yet.
