# Next batches after 18 Nov: v1.2, v1.2.x and docs

Status: **APPROVED as D-761 (18 Nov 20:26Z)**: B1 to B4 start now under conditions C1 and C2; the §2 criteria are approved as written and posted to the issues as "Acceptance criteria (D-761)".
Author: planning thread "Plan the next v1.2 batches", 18 Nov 2026 20:20Z. Base: main 1797ceb.
Read: rules 1.4.6 (LANE-01..04, PLAN-04, CRIT-01..03), decisions D-731, D-744, D-759, D-760,
`per-project-folders-plan.md` (app lane files), `textprep-batch-3-plan.md`,
`layout-batch-german-pdf-plan.md`, the 23 issues and their comments, `.github/lanes.yml`, and the
files each issue names (checked on main 1797ceb). Open PR #552 files checked through the API.
Batch ids (B1..B8), item ids and criteria ids (AC-x.y) are pinned and stay stable across revisions.

## 0. Constraints that shape the grouping

- **Running app lane** (PR #552, then PR 3 #470): owns `src/sci2audio/app/**` and
  `src/sci2audio/web/**` (`api.py`, `player.py`, `project.py`, `tasks.py`, `documents.py`,
  `models.py`, `pages.py`, `templates/_remove.html`, `static/app.js`, `strings/*.toml`),
  `cli.py`, `scripts/zap_scan.py`, and their tests (`test_web_*`, `test_app_projects*`,
  `tests/browser/test_player*.py`). Nothing below that runs now touches these.
- `app` and `web` are `single_threaded` in lanes.yml. So every issue whose fix lives in `app/` or
  `web/` waits for the app lane: **#293, #534, #544, #493, and part B of #442** (B7, B8).
- Shared test truth that forces order: `tests/regression/*.toml` (textprep only),
  `tests/sentences/known-errors.toml` and the sentence gate (layout #466 and textprep #479/#482),
  corpus snapshots `test_app_corpus.ambr` (any lane that moves a reading of a corpus document).
- One implementation and one review thread per lane (LANE-02). Textprep has three batches here,
  so they run one after the other.

## 1. Per-issue table

Crit = critical under CRIT-01/02 (reason). AC = acceptance criteria in the issue (PLAN-04).

| # | ms | lane | AC | crit | files (main 1797ceb) | batch |
|---|---|---|---|---|---|---|
| 442 | v1.2 P1 | extraction (+core) then app/web | **no** (§2) | yes: core dataclass (`core/content.py`, lane:infra) for A; B adds a user-facing stop | A: `extraction/pdf.py`, `core/content.py`, `docs/` document format; B: `app/job.py` or `app/script.py`, `web/strings/*`, report | A: B1, B: B7 |
| 445 | v1.2 | textprep | **no** (§2) | yes: risk:high, regression rows | `textprep/footnotes.py` (`unread_marks`), `units.py`, `numbers.py`, `statistics.py`, `abbreviations.py`, `furniture.py` (`edits_around`); `tests/regression/english.toml`, `german.toml` | B2 |
| 448 | v1.2 | textprep | **no** (§2) | yes: risk:high, regression rows | `textprep/footnotes.py` (affiliation marks, #93); `english.toml` (+ `german.toml` if the shape exists) | B2 |
| 449 | v1.2 | textprep | **no** (§2) | yes: risk:high, regression rows | `textprep/numbers.py` ("K" = thousand); `english.toml` | B2 |
| 466 | v1.2 | layout (+ `extraction/text.py`) | yes | yes: removes rows from `tests/sentences/known-errors.toml`, moves the two text samples' corpus snapshots | `extraction/text.py`, `layout/tagged.py`, `layout/lists.py` / `paragraphs.py`; `tests/sentences/known-errors.toml` | B3 PR 2 |
| 529 | v1.2 | layout | yes | no (goldens unchanged) | `layout/furniture.py` (`_contents`, `_entries`) | B3 PR 1 |
| 535 | v1.2.x | layout | yes | no (goldens unchanged or explained; a moved golden makes it critical) | `layout/furniture.py` (`page_label`, `_counted`), `layout/build.py` | B3 PR 1 |
| 537 | v1.2.x | extraction | yes | no (corpus unchanged) | `extraction/pdf.py` (`_Frame`, positions) | B1 PR 2 |
| 543 | v1.2.x | extraction | yes | no (issue says so) | `extraction/pdf.py` (`_Frame.of`), `tests/unit/test_extraction_pdf.py`, `pdf_maker` helper | B1 PR 2 |
| 485 | v1.2.x | extraction | **no** (§2) | yes if `extraction/isolate.py` changes (memory limit = safety mechanism); test-only otherwise | `tests/unit/test_extraction_pdf_process.py:73`, maybe `extraction/isolate.py` | B1 PR 3 |
| 522 | v1.2.x | docs | yes | yes: contract document | `docs/readalong-format.md:54` | B4 |
| 526 | none | docs | yes | yes: CLAUDE.md process text | `CLAUDE.md` items 2 and 9 | B4 |
| 536 | v1.2.x | textprep | yes | yes: regression row | `textprep/numbers_de.py`, `german.toml`, `test_textprep_numbers_statistics_de.py` | B5 |
| 483 | v1.2.x | textprep | yes | yes: regression row | `textprep/citations.py`, `numbers_de.py` (`_YEAR_WORDS`), `german.toml` | B5 |
| 527 | none | textprep | yes | yes: regression rows en + de | `textprep/numbers.py` / `notation.py` (minus rule) | B5 |
| 479 | v1.2.x | textprep | yes | yes: regression row; sentence gate | `textprep/utterances.py` (`_after_label`), `german.toml` | B6 |
| 482 | v1.2.x | textprep | yes | no (unit test + probe; corpus unchanged) | `textprep/utterances.py` (cut ranking) | B6 |
| 533 | v1.2.x | textprep (tests) | yes | no (unit tests only) | `tests/unit/test_textprep_utterances.py` | B6 |
| 544 | v1.2 | app | yes | no (test only) | `tests/unit/test_app_projects*.py` (`app/projects.py` `_merge_file`) | B7 |
| 493 | v1.2.x | app (+ output) | yes | yes: CRIT-02, a retried name must never overwrite a user file | `web/documents.py:166,244`, `app/job.py:139`, `output/write.py` | B7 |
| 293 | v1.2 | web | **no** (§2) | yes: new route serving bytes from the source file (D-310 path safety), crop cache inside the project folder that #470 removal must delete | `web/player.py`, `web/api.py`, templates, `static/player.js`, maybe `extraction/epub.py` | B8 |
| 534 | v1.2.x | web | yes | no | `web/models.py:12` (and `:216` if the value changes) | B8 |
| 541 | v1.2.x | web (tests) | yes | no | none for the isolation run; `static/player.js` only if it fails | §4 now, fix in B8 |

Milestone notes: #527 and #526 have no milestone (propose v1.2.x for both). Milestone 7's title on
GitHub is still "v1.2.x abbreviations" (Colin's rename step, open).

## 2. Issues without acceptance criteria (PLAN-04): proposed criteria for approval

- **#442** (part 3, glyph-ID recovery, is a roadmap call for Colin and is out of these batches)
  - AC-442.1 Extraction flags a font as having no Unicode source when it is a CID font with Identity encoding, no ToUnicode and an embedded program without `cmap` and `post` (or a simple font with unknown glyph names), and records per page the share of characters from such fonts. Tested on a generated fixture (subset font, no copyrighted file).
  - AC-442.2 A text-level check (the #187 measure plus a letter-bigram check) flags the shift-by-29 ASCII case on the same fixture.
  - AC-442.3 When most characters of a document (the plan pins the share) come from flagged fonts, preparing stops before voices with an EN and DE notice naming the pages; no audio is written. A partly affected document gets the #187 report warning with its page list.
  - AC-442.4 No corpus document is flagged; corpus extraction and goldens unchanged. Any `Content` field added is additive with an empty default, and `docs/` names it.
- **#445** AC-445.1 The three rows of the issue (de x2, en x1) become regression cases and read like the same text without the hidden run, on run 1 and on run 2. AC-445.2 `fuzz5.py FAMILY=hidden` shows 0 differences for number, unit, statistic and abbreviation matches over a seeded run. AC-445.3 Corpus scripts unchanged.
- **#448** AC-448.1 Both title rows keep their mass numbers (en rows; de rows where the shape exists). AC-448.2 Affiliation lines whose first word is an element symbol keep today's reading. AC-448.3 The cue is structural (for example: only blocks after the author line count as affiliations), not a longer word list. AC-448.4 Corpus rows chi, arsiwalla, liu, biggs unchanged.
- **#449** AC-449.1 A number tagged `sup`, or set small and raised, directly before "K" is not read "thousand" (it reads as printed); en regression row. AC-449.2 Plain "40K" reads as today; a row pins it. AC-449.3 German "40K-Atome" unchanged.
- **#485** AC-485.1 The test prints the child's stderr and exit status when it fails. AC-485.2 The cause under `-n auto` load is found and fixed, then the marker is removed; proof is 40 isolated Windows runs plus three full fast-suite Windows runs, all green. AC-485.3 If no cause is found, the quarantine stays and the evidence goes into the issue (it must still be fixed before the next release, TST rule).
- **#293** AC-293.1 A PDF figure, table or formula placeholder shows a crop of its parts' boxes inside its notice box, rendered locally with pypdfium2 (no new dependency, no network). AC-293.2 An EPUB or Markdown picture is shown from its `ref` under the D-310 checks; a table there keeps today's text view. AC-293.3 Each image has alt text: the picture's alt, else the caption, else the notice. AC-293.4 The text view stays the one accessible view: keyboard behaviour unchanged, axe passes in light, dark and German. AC-293.5 Crops are cached in the project's data folder with a size cap and are removed with the project (#470).

## 3. Batches

| batch | lane | issues (PR split) | critical | review | may start |
|---|---|---|---|---|---|
| **B1** Unreadable fonts and page frames | extraction/voices | PR 1 #442 part A; PR 2 #537 + #543; PR 3 #485 | PR 1 yes (core, lane:infra), PR 2 no, PR 3 if `isolate.py` changes | Opus high | **now** |
| **B2** Marks and hidden runs | textprep | one PR or two: #445 + #449 (number/unit readings), #448 (affiliation marks) | yes (risk:high, rows) | Opus high | **now** |
| **B3** Plain-text structure and contents pages | layout | PR 1 #529 + #535; PR 2 #466 | PR 1 no, PR 2 yes | Opus high (batch max) | **now** |
| **B4** Contract and CLAUDE.md wording | docs | one PR: #522 + #526 | yes (docs only) | Opus high, one round expected | **now** |
| **B5** German readings | textprep | #536, #483, #527 | yes (rows) | Opus high | after B2 merges |
| **B6** Sentence cutter | textprep | #479, #482, #533 | yes (#479 row, gate) | Opus high | after B5 and after B3 PR 2 merges |
| **B7** Next app/release batch | app/release | #442 part B (+ #187), #493, #544 | yes (#493 CRIT-02) | Opus high | after app lane PR 3 (#470) merges |
| **B8** Player figures and web leftovers | web | #293; #534 rides along; #541 fix only if §4 fails | yes (#293) | Opus high | after app lane PR 3 merges; beside B7 only if their files are disjoint (B7 touches `web/documents.py` and strings; B8 `player.py`, `api.py`, templates) |

Why these can run side by side now (LANE-02):
- **B1 vs B3:** `extraction/pdf.py`, `isolate.py`, `core/content.py` vs `extraction/text.py` and `layout/`. Disjoint files. Risk: B1 PR 1 changes the `Content` contract that layout reads. Condition C1: B1 PR 1's plan keeps the change additive with an empty default and no golden move; if it cannot, B3 PR 2 waits for B1 PR 1.
- **B2 vs B3:** textprep files vs layout files. B2 writes `english.toml`/`german.toml` only; B3 PR 2 writes `known-errors.toml` and moves the plain-text samples' snapshots. Condition C2: if B2's plan finds a corpus snapshot change, it names it, and the two merge main and regenerate, never hand-resolve.
- **B4:** documents nobody else edits in these batches.
- **App lane:** none of B1 to B4 touches `app/`, `web/`, `cli.py` or their tests.
- **B6 after B3 PR 2:** both touch `tests/sentences/known-errors.toml` and the sentence gate floors.

## 4. Order and what to start first

1. **Start now, four lanes:** B1 (it carries the only P1, #442, which Colin hit on his own book), B2 (the three risk:high v1.2 textprep items), B3 (two v1.2 layout items), B4 (small, critical docs, clears two old follow-ups).
   If the weekly token budget is tight (80% on 17 Nov), start B1 and B2 first, then B3, then B4.
2. **#541 now, without a thread:** dispatch `isolate.yml` on main with tests `tests/browser/test_markers.py::test_the_markers_tab_passes_axe_in_light_dark_and_german`, browsers `webkit`, `webkit_macos: true`, runs 40, mode `full`, and write the counts into #541 (TST-08). Any thread with GitHub API access can do it. Green closes #541's first criterion; red goes to B8 or same-day quarantine.
3. **When the app lane's PR 3 merges:** B7, then B8 (or both, if their plans show disjoint files).
4. **Textprep:** B2 → B5 → B6.
5. #442 part A's plan should cover part B too, so B7 reuses it (one plan, two lanes, D-756 cross-lane handling).

## 5. Found while planning

- **Milestone v1.2 holds 40 open issues, not 8.** Besides the 8 planned above it has 32 more, by lane:
  textprep #150 #249 #292 #379 #402 #405 #414 #415; layout #156 #238 #281 #282 #283 #284 #322 #354;
  extraction #175 #328 #329 #355 #367; app/web #178 #186 #187 #207 #299 #381 #407 (+ #470 running);
  voices #220; tests #468; docs #356.
  Under the autonomy horizon (D-740) these are open work too. They need a triage (keep in v1.2, move,
  or close) before the next round of batches. Natural fits now: #187 and #186 into B7, #407 into B8.
- #527 and #526 have no milestone.
- Four Dependabot PRs (#512 to #515) are open; they touch `uv.lock` (lane:infra, critical) and would
  conflict with B1 PR 1 only if it also touches `pyproject.toml` (it should not).
