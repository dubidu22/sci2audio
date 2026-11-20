# sci2audio: roadmap after v1.0 (proposal)

Status: **SUPERSEDED by the decided roadmap** `plans/roadmap-after-v1.md` (Colin, 13 Nov 2026 21:56 UTC). Kept for the full issue table and the reasoning.

Sources: open issues in `dubidu22/sci2audio` (13 Nov 2026 21:25 UTC; v1.1 milestone 33 open, 26 with no milestone), KB decision log (D-47, D-50, D-55, D-57, D-61, D-102, D-377, D-378, D-400, D-401, D-430, D-442), feature list 2026-11-09 (Should/Could/Later), playbook phase 7, `plans/v1-remaining-plan.md`.

## 0. Before v1.0 itself: the milestone holds more than the five known items

The v1.0 milestone has **24 open issues**, not only #163, #189, #196, #199 and #80:

- **Probably done, never closed (check criteria, then close):** #4 regression corpus and property tests, #6 conformance suite, #9 voice slow test and ASR round trip (created 10 Nov as testing work for #63/#18, no activity since).
- **Small v1.0 bugs from reviews, untouched:** textprep #102, #109, #110, #111, #145, #151, #159, #160; app #104, #112, #118; web #117; install #87 (pipx on Python 3.13).

**Being handled (coordinator, D-443, 13 Nov):** a separate thread verifies and closes #4, #6, #9 and triages the 13 bugs: small ones are fixed before #80, larger ones go to v1.0.1. Not part of Colin's roadmap decision.

## 1a. Revision 1 (after Colin's answers, 13 Nov 21:50 UTC)

Colin: "bigger releases weekly sounds good. i mostly use the app myself and i do quite a bit of german reading. Formulas are not priority (for me personally)".

So the first audience is Colin, German moves to the front, formulas move to Later, and things only other people need (installers, public plugin interface) move to the back. One release per week, each with a theme. The "Prop." column in section 3 still shows the first proposal; this table wins.

| Release | Theme | Content |
|---|---|---|
| **v1.0.1** (only if needed) | Blockers from the listening test or screen-reader pass | Larger v1.0 leftovers (D-443); otherwise folded into v1.1 |
| **v1.1** (~1 week after v1.0) | **German reading** | German voice, starting with a short check that an offline German voice exists under a free licence (a German Kokoro voice per D-50; Piper's German voices as fallback, VA-08); German rules #96, #101, #113, #130; German spoken notices ("Formel 4 wird übersprungen."); the job's language from the document or the user's choice. Plus Colin's own player wins: #152 speed, #153 position, #154, #119 chapter order, #190 front matter |
| **v1.2** (~2 weeks after) | **Better listening for Colin's papers** | Footnotes next to their mark (core change, D-61 (1)); report warnings #186, #187; the rest of the English reading fixes (#100, #150, #97, #114, #131, #193, #191, #92, #93, stacked fractions D-442); robustness #185, #174 + #158, #175, #165; SRT/VTT; #155 read-along on page images |
| **v1.3** (~3 weeks after) | **Ready for others** | Installers with app window (WI-08, D-47) + #13 smoke tests; opt-in update check; public text-step plugin interface (PE-10, after the core change in v1.2); layout edge cases |
| **Later** | Ideas | Formulas via MathCAT (FX-05), OCR, DOCX/HTML, batch queue, layout model, local LLM, Android |

Main risk: the German voice. Kokoro's official voices have no German, and misaki has no German pronunciation of its own (espeak-ng would do it), so v1.1 starts with that check.

## 1. Proposed releases (first proposal, superseded by 1a)

| Release | Theme | Headline content | Rough size |
|---|---|---|---|
| **v1.0.1** (days after v1.0) | Fix what the listening test and screen-reader pass find | Whatever Colin's own release steps turn up; any v1.0 leftovers moved here | small |
| **v1.1** | **Safe to hand to others** | Installers with an app window (D-47, Colin's own decision); robustness and security; report warnings; quick player wins; English reading fixes | ~30 PRs |
| **v1.2** | **Read the hard parts** | Footnotes next to their mark (core change, D-61 (1)); formulas spoken via MathCAT (D-55, FX-05); read-along on PDF page images; SRT/VTT; then the **public text-step plugin interface**, once the core changes are in | ~20 PRs, one XL item |
| **v1.3 or later** | **German** (if Colin wants it later than v1.2) | German rules, German voice, German spoken notices | ~15 PRs |
| **Later** | Ideas | OCR, DOCX/HTML import, batch queue, layout model, local LLM, Android, EPUB media overlays | — |

Why this order:

- **v1.1 = robustness + installers**: D-47 already promises installers in v1.1, and an installer brings in people who never read a README, so the hostile-file and memory issues (#185, #174, #158) must be fixed first. A 1 MB PDF can make PDFium decompress 3.3 GB today (#185).
- **Plugin interface after the core changes**: D-57 says "public in v1.1". But footnotes-by-mark needs a core change (D-61 (1)) and formulas may too. Publishing the interface first would freeze `Edit`/`Span`/`Document` and turn those changes into breaking ones. Recommendation: **move public PE-10 to v1.2, after the core changes** (needs Colin, since D-57 is his decision).
- **German after formulas** follows D-50 ("German once English works end to end"). If Colin reads mostly German papers himself, swap v1.2 and v1.3.

## 2. What waits for Colin's own release steps

| Colin's step | Decides |
|---|---|
| **Listening test** | Pause lengths (Q8), notice wording ("Formula 4 is skipped."), whether footnotes at the column foot are bearable (decides urgency of footnotes-by-mark), whether formulas or German hurt more, #114 en-US/en-GB, stacked-fraction spacing (D-442) |
| **Screen-reader pass** (VoiceOver, NVDA) | #152 speed control, #119 chapter order, #155 read-along on page images, #14 visual regression; anything it finds goes to v1.0.1 |
| **M4 speed run** | #178 estimate model, #28 PDFium lock, whether a faster voice backend matters |
| **Retire hosted demo** | Nothing in this roadmap depends on it; it only needs doing before the v1.0 announcement |

## 3. Full backlog by theme (open issues + feature-list items without an issue)

Columns: proposed release · issue (or feature ID if no issue yet) · title · current milestone.

### 3.1 Reading quality, English

| Prop. | Issue | Title | Now |
|---|---|---|---|
| v1.2 | FX-05 (no issue) | Formulas spoken via MathCAT instead of "Formula 4 is skipped." (D-55, playbook phase 7; XL) | — |
| v1.2 | D-61 (1) (no issue) | Footnote read next to its mark, not at the column foot (core change; plan Q2 said v1.1) | — |
| v1.1 | D-442 (issue pending from #163) | Stacked-fraction spacing | v1.1 (planned) |
| v1.1 | #114 | Unit spelling by language tag (en-US, en-GB) | none (KB says v1.1) |
| v1.1 | #131 | Slash dates by the document's locale | v1.1 |
| v1.1 | #100 | Superscript numeric citations (Nature style) | v1.1 |
| v1.1 | #150 | Label and version numbers; smaller statistics notation | v1.1 |
| v1.1 | #97 | Words hyphenated across two blocks | v1.1 |
| v1.1 | #193 | Hidden runs and inline page-break markers (EPUB, Markdown) (D-430) | v1.1 |
| v1.1 | #191 | Name an uncaptioned figure by its alt text | v1.1 |
| v1.1 | #92 | Reference list printed without a heading | none |
| v1.1 | #93 | Author-affiliation marks in the title block | none |
| v1.1 | #95 | One table of reference-list names (app vs textprep) | none |
| v1.1 | #127 | Lone accent mark after punctuation | none |
| v1.1 | #141 | Capital after a maths symbol is no initial | none |
| v1.1 | #41 | PDF page-label table as second source of page labels | v1.1 |
| v1.1 | #135 | Printed page numbers from EPUB page markers | v1.1 |
| v1.1 | #156 | Small repeated edge lines taken for running heads | v1.1 |
| v1.1 | #181 | Narrow rule under an indented line joins the block before | v1.1 |
| v1.2 | #49 | Roman heading numbers (IEEE style) | none |
| v1.2 | #54, #55, #56, #59, #122, #125, #126 | Layout edge cases (list-like headings, text in uncaptioned figures, rule-less tables, scatter plots, joined headings, spacing accents, tall pieces) | none |
| v1.2 | #32 | Columns inside a column (nested cuts) | none |
| later | #25 | Layout model as second opinion | v1.1 |
| later | TP-17, FX-06, FX-07 | Acronym long forms, tables described, chemistry | — |

### 3.2 German

| Prop. | Issue | Title | Now |
|---|---|---|---|
| v1.3* | #96 | German line-end hyphens | v1.1 |
| v1.3* | #101 | German words for links and citations | v1.1 |
| v1.3* | #113 | German abbreviations, symbols, units | none |
| v1.3* | #130 | German numbers, dates, statistics | v1.1 |
| v1.3* | VA-07 (no issue) | German voice (Thorsten Kokoro) | — |
| v1.3* | Q10 (no issue) | German spoken notices ("Formel 4 wird übersprungen.") | — |
| later | TP-18 | Gender forms, foreign words, names | — |

\* or v1.2 if Colin wants German before formulas (question 1). **Recommend moving #96, #101, #130 out of v1.1** whichever way.

### 3.3 Robustness and security

| Prop. | Issue | Title | Now |
|---|---|---|---|
| v1.1 | #185 | PDFium decompresses without a size limit (child process with memory cap) | v1.1 |
| v1.1 | #174 + #158 | Per-document line/block limit; EPUB memory by items (D-377) | v1.1 |
| v1.1 | #175 | HTML reader result depends on Python patch version (D-378) | v1.1 |
| v1.1 | #165 | Small cover with huge pixel size costs ffmpeg ~2 GB | v1.1 |
| v1.1 | #186 | Report warning: picture-only pages (partly scanned) | v1.1 |
| v1.1 | #187 | Report warning: garbled font text | v1.1 |
| v1.1 | #143 | Library warnings printed to the terminal | none |
| v1.1 | #106 | Job killed while encoding blocks the rerun | none |
| v1.1 | #115 | `convert --with-script` stopped in script phase needs `--overwrite` | none |
| v1.1 | #172 | Permissions-Policy and COEP headers | v1.1 |
| v1.1 | #177 | Flaky ZAP walk step | v1.1 |
| v1.1 | #176 | pre-commit whitespace hooks rewrite `.ambr` golden files | none |
| v1.1 | #82 | Exact footnote-mark check in truth README | none |
| v1.1 | #89 | AudioChunk docstring wrong (D-117) | none |
| v1.1 | #173 | Document the quarantined marker (D-374) | none |
| v1.2 | #28 | PDFium lock for whole document (after M4 run) | v1.1 |
| v1.2 | #60, #62 | Quadratic figure grouping and formula detection | none |

### 3.4 Output and player

| Prop. | Issue | Title | Now |
|---|---|---|---|
| v1.1 | #152 | Playback speed control in every browser | v1.1 |
| v1.1 | #153 | Remember listening position across runs | v1.1 |
| v1.1 | #154 | Open a CLI-made audiobook from another folder | v1.1 |
| v1.1 | #119 | Choose chapter order | v1.1 |
| v1.1 | #190 | Deselect EPUB front/back matter by default | v1.1 |
| v1.1 | #134 | Covers in GIF, WebP, SVG | v1.1 |
| v1.1 | #178 | Estimate: leave first chapter out? (after M4 run) | v1.1 |
| v1.2 | OU-04 (no issue) | SRT/VTT subtitle export from read-along JSON | — |
| v1.2 | #155 | Read-along on PDF page images (D-102) | v1.1 |
| v1.2 | #14 | Visual regression for read-along view | none |
| later | OU-06, OU-07 | EPUB 3 media overlays; Audiobookshelf/podcast feed | — |

### 3.5 Platform and distribution

| Prop. | Issue | Title | Now |
|---|---|---|---|
| v1.1 | WI-08 (no issue) | Installers (.dmg, .exe, Linux) with pywebview app window (D-47) | — |
| v1.1 | #13 | Installer smoke tests on three systems | v1.1 |
| v1.1 | #87 | pipx on Python 3.13 refuses kokoro/misaki (if not fixed in v1.0) | v1.0 |
| v1.1 | AQ-07 (no issue) | Opt-in update check (sensible once installers exist) | — |
| v1.2 | PE-10 public (no issue) | Public text-step plugin interface with `sci2audio.text_steps` entry point (D-57 says v1.1) | — |
| v1.2 | PE-09, UC-08 (no issues) | Rule files as data per language; user pronunciation list | — |
| later | UC-04 | Editable script before audio | — |
| later | IN-05 | OCR for scanned PDFs | — |
| later | IN-06 | DOCX and HTML import | — |
| later | WI-06 | Batch/folder conversion queue | — |
| later | AI-01, AI-02, WI-10 | Local LLM rewrite, AI figure descriptions, Android | — |

## 4. Questions only Colin can answer

1. **German:** headline of v1.2 (before formulas), or after formulas in v1.3? Do you mostly listen to English or German papers yourself?
2. **Public plugin interface:** keep it in v1.1 as decided in D-57, or move it to v1.2 after the footnote/formula core changes (recommended)? Does a public plugin API matter to you at all, or is it mainly a learning exercise?
3. **First audience after release:** you yourself, a few colleagues, or a public launch (Show HN, Reddit)? Public means installers and robustness first (this proposal); just you means reading quality first.
4. **Formulas spoken via MathCAT:** worth the biggest single item (XL, Rust library, licence check), or keep "Formula 4 is skipped." longer?
5. **Release rhythm:** small releases about weekly, or one bigger release per theme?

### Answered 13 Nov 21:50 UTC
Q1 German first (Colin reads a lot of German), Q3 audience is Colin himself, Q4 formulas not a priority, Q5 bigger releases weekly.

### Open after revision 1
A. Installers: move from v1.1 (D-47, Colin's decision) to v1.3, since Colin installs with `uv` himself?
B. Public plugin interface: move from v1.1 (D-57) to v1.3, after the footnote core change? (Q2 restated.)
C. If no good free German Kokoro voice exists: accept a Piper German voice (sounds flatter) for v1.1, or wait for a better one?
