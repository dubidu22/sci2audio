# Next batches after 19 Nov: the rest of v1.2

Status: **PROPOSED, waits for the coordinator** (criteria in §2 need approval under PLAN-04; batches in §3).
Author: planning thread "Plan the next round of v1.2 batches", 19 Nov 2026 ~03:00Z. Base: main 678fe3c (#582 merged).
Read: rules 1.4.7 (LANE-01..04, PLAN-04, CRIT-01..03, ROLE-02), `next-batches-2026-11-18.md`, `.github/lanes.yml`,
CLAUDE.md, the 31 issues of its §5 with all comments, the files each names, open PRs #593 #512–#515 through the API.
Probes: textprep rows run on main 678fe3c through `run_steps` + `rebuilt_from_script` (both runs), script in the
thread's scratch, results quoted below. Batch ids continue the 18 Nov plan (B9 to B17) and stay stable across revisions.

## 0. State on GitHub (checked 19 Nov ~02:40Z)

- Of the 31 issues in §5 of the 18 Nov plan, **30 are open, #187 is closed** (by #577). Milestone v1.2 now holds
  31 open issues: these 30 plus #442 (part 3 only, Colin's roadmap call).
- **Probably already met, propose closing (Colin):** none fully. **#249 is mostly met** by PR #368 (D-615): table
  and figure notices read "Tabelle 2 Punkt 1 wird übersprungen." (regression case `de-notice-dotted-caption-labels`,
  unit test `test_a_german_notice_names_the_figure_as_its_caption_reads`). Left over: a **formula** label still
  reads as printed, "Formel (3.2) wird übersprungen." (probe), which espeak-ng says "drei zwei". Kept, narrowed (§2).
- Still reproduce on main 678fe3c (probe, first run | second run):
  - #150: "Section 3 point 1 0", "t (34) equals 2.1", "X2 of 1", "Call 555 to 1234" (all four items open).
  - #379: "2 times m²" | "2 times m squared"; "2 m squared" | "2 metres squared".
  - #402: "We thank Smith and here." (en and de).
  - #405: all five rows and the comment's "[3] m²" row still differ on the second run.
  - #414: "It holds, references 2 and 3 here." (better than the issue's main column, still not the whole list).
  - #415: both probed rows read "is cited.".
- Read in code, still open: #407 (`web/player.py:375` keys on `(st_mtime_ns, st_size)`, no `st_ino`); #299
  (`static/app.js:481` reloads on the analysis end with no guard); #238 (`NOT_YET_COLUMNS` still lists maass p3);
  #207 (`app/report.py:485 shown_original` handles only "\n"); #186 (no picture-only warning anywhere); #381 (test
  still named "its own working folder"); #367 (`isolate._wait` returns "ended" with no cancel grace); #355
  (`MAX_GRAPHICS` still 500,000); #175 (`requires-python >=3.12`, reader still on stdlib HTMLParser behaviour).
- **#178 is blocked on Colin:** `docs/baseline.md` has his M4 rows for hardt only (MPS largest error 24 %, CPU 8 %),
  none for pymedphys, which is the paper the issue's first criterion asks about.
- **#220 is blocked on Colin:** its first criterion is his German listening test.

## 1. Per-issue table

Crit = critical under CRIT-01/02 (reason). AC = acceptance criteria in the issue (PLAN-04). Files on main 678fe3c.

| # | ms | lane | AC | crit | files | batch |
|---|---|---|---|---|---|---|
| 414 | v1.2 | textprep | yes | yes: regression rows en+de | `textprep/citations.py`; `english.toml`, `german.toml` | B9 |
| 415 | v1.2 | textprep | yes | yes: regression rows | `textprep/citations.py` (subject nests, D-599 cap) | B9 |
| 402 | v1.2 | textprep | yes | yes: regression rows en+de | `textprep/links.py` (join words, #256 #257) | B9 |
| 379 | v1.2 | textprep | yes | yes: regression row | `textprep/units.py`, `numbers.py` (letter powers) | B10 |
| 405 | v1.2 | textprep | yes | yes: regression rows en+de | `textprep/abbreviations.py`, `units.py`, `notation.py`, `citations.py` (read-as-number side) | B10 |
| 150 | v1.2 | textprep | yes (scripts agreed in plan) | yes: regression rows | `textprep/numbers.py`, `statistics.py`, `units.py` (label list) | B10 |
| 292 | v1.2 | textprep | **no** (§2) | yes: regression row | `textprep/placeholders.py` (code read as text), `utterances.py` (pause per line) | B11 |
| 249 | v1.2 | textprep | yes, narrowed (§2) | yes: regression row | `textprep/placeholders.py` / `wording.py` (formula label), `german.toml` | B11 |
| 468 | v1.2 | textprep (tests) | yes | yes: corpus file, truth, licence (risk:high) | `tests/corpus/papers/`, `LICENSES.md`, `truth/`, `tests/sentences/*`, `known-errors.toml` | B11 PR 2 |
| 281 | v1.2 | layout (+ textprep `wording.py`, D-756) | yes, amended (§2) | no (goldens unchanged; corpus has no "Listing" caption) | `layout/captions.py`, `layout/code.py`; maybe `textprep/wording.py` | B12 |
| 283 | v1.2 | layout | yes | no (seaborn listings stay one per page) | `layout/code.py`, `layout/build.py` (join across page break) | B12 |
| 282 | v1.2 | layout | yes | **yes** if block text gains leading spaces (seaborn golden moves); no if the player draws the indent from line boxes | `layout/code.py` or `web/player.py` + `static/player.js` (plan picks) | B12 |
| 284 | v1.2 | layout | yes (decision) | no unless a text sample changes (then sentence set, §4) | `layout/tagged.py` / `paragraphs.py` (plain text path) | B12 |
| 156 | v1.2 | layout | yes | yes if a golden moves; corpus truth tests in both directions | `layout/furniture.py`, `layout/settings.py` | B13 |
| 238 | v1.2 | layout | yes | yes: changes `NOT_YET_COLUMNS`, may move maass reading (sentence set) | `layout/build.py` (`columns_per_page`), `layout/order.py` | B13 |
| 322 | v1.2 | layout | yes | yes: liu golden moves | `layout/maths.py` / `formulas.py`, `order.py` | B13 |
| 354 | v1.2 | layout | yes | no (goldens unchanged; perf only) | `layout/order.py` (`figures`), `tests/unit/linear_time.py` | B13 (after B15's limit decision) |
| 175 | v1.2 | extraction | **no** (§2) | no (well-formed files and goldens read the same) | `extraction/markup.py` (`PageReader`) | B14 |
| 328 | v1.2 | extraction | yes | yes if the corpus EPUB's order or link targets move (`Content.order`) | `extraction/markup.py` (`picture()`, anchors) | B14 |
| 329 | v1.2 | extraction | yes | yes: input limits are a safety mechanism (#185, D-579) | `extraction/markup.py`, `epub.py`, `markdown.py` | B14 |
| 355 | v1.2 | extraction | yes | yes: child memory limit, safety mechanism | `extraction/pdf.py` (`MAX_GRAPHICS`, `MAX_PAGE_GRAPHICS`, pipe encoding), `isolate.py` | B15 |
| 367 | v1.2 | extraction | yes | yes: `isolate.py` cancel path (safety mechanism) | `extraction/isolate.py` (`_wait`), `pdf.py` (`ReadCancelled`), CLI exit 130 test | B15 |
| 356 | v1.2 | extraction + docs | yes | yes only if `_hard_limit` changes on macOS; else no (test + docs) | `tests/unit/` slow benchmark, `docs/baseline.md`, maybe `isolate.py` | B15 |
| 186 | v1.2 | app (+ web strings) | yes | no | `app/report.py`, `web/strings/en.toml`, `de.toml`, `web/templates/document.html`, `cli.py` | B16 |
| 207 | v1.2 | app | yes | no | `app/report.py` (`shown_original`), document page check table (`web/pages.py` / `document.html`) | B16 |
| 299 | v1.2 | web | yes | no | `web/static/app.js` (`reloadAt` guard), `tests/browser/` | B17 |
| 407 | v1.2 | web | yes | no | `web/player.py` (`load_readalong` key), shared stat helper | B17 |
| 381 | v1.2 | web (tests) | yes (the issue's (a)–(c) fix list) | no (tests and two docstrings; no behaviour change) | `tests/unit/test_web_outside.py`, docstring in `web/api.py` | B17 |
| 178 | v1.2 | app | yes | no | `app/audio.py` (`_Speech`) | **held: Colin** (§5) |
| 220 | v1.2 | voices | yes | no | `voices/` override list | **held: Colin** (§5) |
| 442 p3 | v1.2 | extraction | n/a | n/a | glyph-ID recovery | **held: Colin** (roadmap) |

## 2. Criteria to approve (PLAN-04)

- **#175** (D-378 left "the reader handles these cases itself" open)
  - AC-175.1 `PageReader` gives the same `Content` for each of the issue's eight broken-markup rows on every supported CPython 3.12/3.13 patch level; the expected result per row is fixed in the plan (prefer the patched behaviour, which the goldens follow).
  - AC-175.2 A parametrized unit test pins the eight rows; it runs in the three-system CI (macOS has the older patch level).
  - AC-175.3 Corpus EPUB and Markdown goldens unchanged.
- **#292**
  - AC-292.1 With "Code blocks" switched off, each printed line of a CODE block is read as its own utterance, with a pause after it (seaborn page 2 with `--off code`: one utterance per line).
  - AC-292.2 The plan decides whether the notation step reads symbols in code ("=" as "equals"); the decision goes in the KB and a regression row pins it, both runs.
  - AC-292.3 With "Code blocks" on (the default), nothing changes: corpus scripts unchanged.
- **#249, narrowed** (tables and figures met by PR #368, D-615)
  - AC-249.1 A German formula notice with a dotted label reads it with "Punkt": "Formel (3.2)" → "Formel 3 Punkt 2 wird übersprungen." (or with the parentheses kept, as the plan decides), both runs; a row added to `de-notice-dotted-caption-labels` or its own case.
  - AC-249.2 The English formula notice is unchanged.
- **#281, amended for LANE-02** (the issue asks for a regression case, which is textprep's file)
  - AC-281.1 unchanged ("Listing" and German "Listing"/"Quelltext" as caption labels describing the CODE block).
  - AC-281.2 The notice names it ("Listing 3 is skipped.", German as `wording.py` decides), pinned by a layout unit test and a textprep notice unit test; the regression row is added only while no textprep batch has a PR open, else it rides with the next textprep PR.
- **#381** has a fix list, not a criteria heading; read its (a), (b), (c) and the docstring rename as AC-381.1 to AC-381.4.
- **#329** criteria stand; the plan must name the measured numbers at the byte limits before choosing a bound.

## 3. Batches

| batch | lane | issues (PR split) | critical | review | may start |
|---|---|---|---|---|---|
| **B9** Citation lists and join words | textprep | one PR: #414 + #415 (citations.py); #402 (links.py) in the same PR or a second | yes | Opus high | after B6 merges |
| **B10** Second-run readings | textprep | #379 + #405 (units, abbreviations, notation), #150 (numbers, statistics) | yes | Opus high | after B9 merges |
| **B11** Code lines, formula notice, second German paper | textprep | PR 1 #292 + #249; PR 2 #468 | yes | Opus high | after B10 merges (PR 2 also needs B6's German floors) |
| **B12** Code blocks | layout | PR 1 #281 + #283 (+ #284 decision); PR 2 #282 | PR 1 no, PR 2 yes if layout route | PR 1 Opus medium, PR 2 Opus high | **now** |
| **B13** Page edges, columns, fractions, figure speed | layout | PR 1 #156 + #238; PR 2 #322 + #354 | yes (goldens) | Opus high | after B12 merges and after B6 merges (sentence set, §4); #354 also after B15's limit decision |
| **B14** Markup reader | extraction | one PR: #175 + #328 + #329 | yes (#329 limits, #328 order) | Opus high | after the Markdown Dependabot PRs #515 and #514 merge (§6) |
| **B15** PDF reader child | extraction | PR 1 #355 + #367; PR 2 #356 (docs + benchmark) | PR 1 yes, PR 2 only if `isolate.py` changes | Opus high | after B14 merges |
| **B16** Report warnings and quotes | app | one PR: #186 + #207 | no | Opus medium | **now** |
| **B17** Page race, read-along cache, shared folder tests | web | one PR: #299 + #407 + #381 | no | Opus medium | **now** |

Why these can run side by side (LANE-02):
- **B12 (layout) vs B5/B6 (textprep):** `layout/code.py`, `captions.py`, `build.py` vs textprep files and `known-errors.toml`. Disjoint, provided B12 PR 1 adds no regression row (AC-281.2) and #284 does not change a plain-text sample's reading while B6 is open (if it does, that PR waits for B6).
- **B16 (app) vs B17 (web):** `app/report.py`, `web/strings/*.toml`, `document.html`, `cli.py` vs `static/app.js`, `web/player.py`, `tests/unit/test_web_outside.py`, `web/api.py` docstring. Disjoint; condition C3: B17 adds no string to `web/strings/*.toml` (the reload guard needs none) and B16 does not touch `app.js`. If either plan finds a shared file, the later one waits.
- **B16/B17 vs B12:** #282 PR 2 may take the player route (`web/player.py`, `player.js`); it then waits for B17 to merge.
- **B14 vs layout:** extraction files only; #328 can move `Content.order` of the corpus EPUB, which layout reads, so B13 merges main and regenerates if both move a snapshot (never hand-resolve).
- **Corpus snapshots** (`test_app_corpus.ambr`): any lane that moves one merges main and regenerates.

## 4. Order and dependencies

1. **Start now (no dependency on B5):** B16 and B17 (small, non-critical, app and web are idle since B7/B8), and B12 PR 1 (layout is idle since B3). If the weekly budget is tight, start B17 first (two real bugs, #299 and #407), then B16, then B12.
2. **Dependabot (§6):** merge #513, then #515 + #514, before B14 starts; #512 when no browser-heavy PR is in review.
3. **Textprep, one after the other:** B5 (#593, in review) → B6 (#479 #482 #533, planned next) → B9 → B10 → B11. All rewrite `english.toml`/`german.toml`, so none of them run side by side.
4. **Sentence set** (`tests/sentences/`, `known-errors.toml`, floors) is shared by B6, B11 PR 2 (#468), B13 (#238 maass, #156 if a corpus line changes) and B12 #284 (plain-text samples). Order: B6 → B13 → B11 PR 2; #284 only if it leaves the samples' reading unchanged before B6 merges.
5. **#354 and #355 are decided together** (both issues say so): B15 PR 1 decides the drawing limit first (option 1, lower `MAX_GRAPHICS`, fixes both), then B13 PR 2 pins `assert_linear` against the new limit. One plan note under D-756 cross-lane handling.
6. **Once B5 merges:** start B6 (its plan first; #479 row and sentence gate are critical). Nothing else in this plan waits on B5 alone.

## 5. Proposed for Colin (his call: milestone, closing, hand steps)

| # | proposal | reason |
|---|---|---|
| 178 | Run `scripts/speed.py` on pymedphys on the M4 (MPS and CPU), or close as met, or move to Later | The first criterion needs that run; his M4 rows exist for hardt only (largest error 24 % MPS, 8 % CPU) |
| 220 | Keep blocked until his German listening test, or close as not needed, or move to Later | First criterion is the listening test (D-473) |
| 249 | Keep open, narrowed to formula labels (AC-249.1/2) | Tables and figures met by PR #368 (D-615); only "Formel (3.2)" remains |
| 284 | Close if the B12 plan finds no rule that leaves prose alone | The issue is a decision; a "no" leaves nothing to build |
| 468 | Keep in v1.2; the PR needs his truth-file check (D-60) after merge | Corpus and truth files follow D-60 |
| 442 p3 | Roadmap call (glyph-ID recovery) | Already listed for him |

Not triaged here: the newer follow-ups without a milestone (#563–#567, #570, #571, #576, #578–#581, #584, #586–#592, #596).

## 6. Dependabot PRs #512–#515 (lane:infra, critical; read-only check, nothing merged)

All four: one commit, `mergeable=clean`, Linux CI green ("CI passed" success, ZAP and licences green), but on old bases
(#512 16 commits behind main, #513–#515 31 behind). All bump the lock file header `revision = 3` → `5` (identical
line, so they do not conflict with each other there). None is on a release branch.

| PR | change | risk | recommendation |
|---|---|---|---|
| **#513** | fastapi 0.162.5 → 0.162.7 (`uv.lock` only, +4 −4) | Low. 0.162.7 fixes async yield dependency cleanup on cancellation; 0.162.6 drops Python 3.10 (we need ≥3.12). No new dependency in the lock diff. | **Merge first.** Update the branch (main moved 31 commits incl. web #582), Linux CI green, then merge. `THIRD_PARTY_LICENSES.md` row still says 0.162.5. |
| **#515** | markdown-it-py 4.2.0 → 4.3.0 (`uv.lock` only) | Medium. Security fixes (quadratic inline parsing, unterminated inline HTML), but also CommonMark 0.31.2 parsing changes: HTML block starts, whitespace trim set (U+001C–U+001F, U+0085 kept), image alt text keeps escapes, code spans and hard breaks. Our Markdown reader renders through it (`extraction/markdown.py:91`), so edge-case `Content` can change; the alt-text change reaches #293's alt text (merged after this PR's CI run). Corpus Markdown samples passed on the old base. | **Merge second,** after an update-branch and a fresh Linux CI on today's main (corpus snapshots and #582's figure tests must stay green). |
| **#514** | mdit-py-plugins 0.6.1 → 0.7.0, **`pyproject.toml` bound `<0.7` → `<0.8`** + `uv.lock` | Medium (0.x minor = breaking by its own notes). Renderer escaping and attrs/anchors changes: we use `dollarmath`, `footnote`, `front_matter` only and render maths with our own rules (`markdown.py:189-195`, own `escapeHtml`), so the escaping change should not reach us; `parse()` raising on unterminated attrs affects only attrs, which we don't load. Needs markdown-it-py ≥3.0 (met). Packaging change (pyproject) = critical. | **Merge third,** right after #515, with ci:full (three systems) since it changes a declared bound. Licence row says 0.6. |
| **#512** | dev group: playwright 1.65.1 → 1.65.2 (Chromium r1255), ruff 0.17.4 → 0.17.5, **syrupy 6.1.1 → 7.0.1 (major)** (`uv.lock` only, +35 −35) | Medium for CI, none for users. Syrupy 7 hardens snapshot update and cleanup under partial selection and xdist (we run `-n auto` with `.ambr` snapshots); 7.0.1 stops cleanup deleting snapshots of ignored tests. Playwright changes the CI browser cache key and the browser build (screenshots, axe); thread-local setups that link `chromium_headless_shell-1254` will need 1255. Ruff 0.17.5 may flag code merged since its base. | **Merge last,** when no web or browser PR is in review: update-branch, then ci:full plus one nightly-style browser run (WebKit/Firefox legs reported), and a `--snapshot-update` dry run showing no deleted snapshots. If syrupy 7 misbehaves, close #512 and ask Dependabot for playwright and ruff alone (ignore syrupy 7 in `dependabot.yml`, lane:infra). |

Process: one review thread for all four (Opus high is required for critical, but each is a read of release notes plus
CI; expect one round each). They run one at a time (all touch `uv.lock`, lane:infra is single-threaded). Afterwards,
one lane:docs line updates the version cells in `THIRD_PARTY_LICENSES.md` (FastAPI 0.162.7, markdown-it-py 4.3,
mdit-py-plugins 0.7, Playwright 1.65.2), folded into the next docs PR. ROLE-02's "Dependabot check" at release stays
Colin's hand step; these merges do not replace it.
