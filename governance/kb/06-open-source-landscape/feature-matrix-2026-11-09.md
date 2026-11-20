# Feature matrix: sci2audio vs. all researched products

`[AUDIT]` · Snapshot of 9 Nov 2026 · Owner: Colin · Advisor: Claude · Built from `audit-tts-and-text-rewriting-landscape-2026-11-09.md`, `audit-commercial-tts-and-text-rewriting-landscape-2026-11-09.md`, `audit-abogen-vs-sci2audio-2026-11-09.md`, `audit-audiblez-vs-sci2audio-2026-11-09.md`, `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md` · **The full matrix lives in the Doc "Feature matrix: sci2audio vs. all researched products" (claude.ai artifact `S51tv9ry75nsJDtKoNUyjJ`)**: tab "Apps: text preparation" (77 rows × 23 features), tab "Apps: input, voice, platform" (77 × 18), tab "Libraries, platforms, services" (68 × 10). This file keeps the legend, the sci2audio rows and the findings; edit the matrix in the Doc.

> **Why this file exists.** Colin asked (9 Nov 2026) for one table document with all possible features and, for every researched competitor, which features exist. Cells are marked only from the sources in the audits above; Abogen, Audiblez and sci2audio from their code.

## Legend

| Symbol | Meaning |
|---|---|
| ✓ | Yes, documented or verified in code |
| ◐ | Partly (some cases, paid tier only, or via another component such as Kokoro's front end) |
| ✗ | No, documented or verified |
| ? | Not documented in the sources checked |
| – | Not applicable |
| P / L | Planned for sci2audio v1.0 / later (phase 7) |
| skip / note / desc / raw / speak | Tables, figures, formulas: skipped, spoken notice, described, read raw, spoken properly; "(AI)" = language model |

Groups: S = sci2audio, OA = open-source app, OT = open-source AI/paper tool, RA = commercial reader app, PA = paper app, AT = assistive/math tool, AN = AI narration; libraries tab: NL, VR, MA, AI, DS, PDF, TTS.

## Feature list

**Text preparation (23):** page furniture; hyphenation; citations; footnotes; URLs; reference list; abbreviations; numbers/dates; symbols/units; statistics; Roman numerals; homographs; Unicode/ligatures; tables; figures; formulas; skip toggles; pronunciation dictionary; user regex; sections; edit text; AI faithful rewrite; AI summary.

**Input, voice, platform (18):** PDF; EPUB; other documents; web/URL; OCR; chapters; local voice; cloud voice; German voice; MP3/M4B export; read-along; subtitles/EPUB 3; desktop/CLI; mobile; web/extension; open source; free use; local processing.

**Libraries, platforms, services (10):** open source; licence/price; numbers & dates; units & symbols; abbreviations; URLs; math; pronunciation lexicon; German; offline.

## sci2audio rows

| Row | Furniture | Hyphen | Citations | Footnotes | URLs | Ref. list | Abbrev. | Numbers | Symbols/units | Statistics | Roman | Homographs | Unicode | Tables | Figures | Formulas | Toggles | Pron. dict | Regex | Sections | Edit | AI faithful | AI summary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sci2audio today | ✓ | ✓ | ✓ | ✓ | ◐ | ✓ | ✓ | ◐ | ✓ | ◐ | ✓ | ◐ | ◐ | note | ◐ | raw | ◐ | ◐ | ✗ | ◐ | ✓ | ✓ | ✗ |
| sci2audio v1.0 plan | ✓ | ✓ | P | ✓ | P | ✓ | ✓ | P | ✓ | P | ✓ | P | P | note | ◐ | note (L: speak) | P | L | L | P | P | L | ✗ |

| Row | PDF | EPUB | Other | Web | OCR | Chapters | Local voice | Cloud voice | German | MP3/M4B | Read-along | Subtitles | Desktop | Mobile | Web | Open source | Free | Local processing |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sci2audio today | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ◐ | ✗ | ✓ | ✗ | ◐ | ◐ |
| sci2audio v1.0 plan | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ | L | ✓ | ✓ | L | ✓ | ✗ | ✓ (local) | ✓ | ✓ | ✓ |

## Findings

- No other app combines faithful scientific text preparation, local processing, open source and German.
- Nearest per area: Paper2Audio (cloud; AI-described tables, figures, formulas; grammar-aware citations), Audeus (skip toggles), the autiobooks fork (general rules), Listening (sections, Zotero), Voice Dream/Balabolka/TTSReader (pronunciation dictionaries).
- Only assistive tools (JAWS, EasyReader, Kurzweil, VoiceOver, all via MathCAT except VoiceOver) speak formulas today. sci2audio v1.0 skips them with a spoken notice (D-55).
- sci2audio's gaps vs. the market: per-category toggles (K1), grammar-aware citation removal (K2), section choice (K3), user pronunciation dictionary (K4), mobile apps.
- Many cells are "?": most products don't document their text handling. Explaining exactly what sci2audio does is itself a differentiator.

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| FQ1 | Hands-on tests to replace "?" for the closest competitors (Paper2Audio, Audeus, Listening, Speechify, autiobooks fork) on the same two PDFs | Yes, before v1.0 positioning text | Accuracy of the matrix |
| FQ2 | Keep the matrix updated when? | With each landscape re-run (v1.0 or 3 months) | Revisit trigger |
