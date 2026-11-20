# sci2audio: plan for the remaining v1.0 work

Status: **APPROVED with changes** by the coordinator, 12 Nov 2026 (under D-80; Colin informed in the project chat at 2026-11-12T22:39:45Z). Section 4 now holds the **decisions**, not recommendations; they win over anything else in this file. Second opinion with reasons and verified facts: `plans/v1-remaining-plan-review.md`. KB entries: D-96 to D-105, plus D-106 (truth-sentence format for #39, extends D-64), in sci2audio-design PR #21 (waiting for review). · Written 12 Nov 2026, after sci2audio PR #61 (af78e0b) · Sources: KB `sci2audio-design/docs/kb` (playbook-open-source-desktop-app, feature-list-2026-11-09, decision log up to D-95), `CLAUDE.md`, `.claude/rules/tests.md`, the v1.0 milestone and open issues, the code on `main`.

## 1. Summary

- v1.0 = the **41 Must features** of the feature list (milestone description). Code exists today for about 5 of them (IN-01 PDF layout, PE-01/02/04/05 in part). The other 36 have no code yet.
- Remaining work: **34 v1.0 issues** (16 already open plus 18 filed today, #63 to #80), about **38 to 42 code PRs** plus about 8 KB decision PRs.
- Revised estimate: **about 30 % done** (section 5). The layout stage was the hardest part, but most of the work is still ahead: the user-facing part (text rules, voice, audio, app, interface, release).
- Critical path: **#63 text-step interface → #70 script job → #71 audio job → #76 server → #77 interface → #78/#79 → #80 release**, with **#18 voice** and **#69 output** joining at #71.
- 15 questions, now **decided** (section 4).

## 2. Ordered work list

"Crit." = critical under D-69 (layer contract, core, KB, golden file) or `risk:high`; its plan waits for the coordinator. Nearly every remaining PR adds golden files or regression cases, so nearly all are critical (Q1).

### Wave 1: start now, in parallel (different lanes)

| # | Work item | Issue | Lane | Crit. | Depends on |
|---|---|---|---|---|---|
| 1 | Text-step interface, categories, registry, overlap rule, utterance cutter, furniture step (TP-01); conformance suite and regression harness | **#63** (closes #6 text part, starts #4) | textprep | yes | none |
| 2 | Kokoro English voice and voice contract, incl. speed and a preview call (VA-05); slow test, ASR round trip, benchmarks | **#18** (with #9, #11, #6 voice part) | voices | yes | none |
| 3 | Output: MP3 per chapter, M4B with chapters, cover, AI label, pauses, read-along JSON (read back without ffprobe, Q5) | **#69** | output | yes | Q5, Q8, Q9 |
| 4 | Corpus truth: verbatim sentences with footnote marks and inline maths (guards #36) | **#39** | docs/tests | yes | none |
| 5 | Flaky property test fix (nightly fails at random); start it first | **#47** (v1.0, Q14) | core tests | no | none |

### Wave 2: after #63 merges

| # | Work item | Issue | Lane | Crit. | Depends on |
|---|---|---|---|---|---|
| 6 | Formulas, tables, figures, footnotes, reference list as edits | **#64** | textprep | yes | #63, Q2, Q3 |
| 7 | Unicode clean-up and line-end hyphens | **#65** | textprep | yes | #63 |
| 8 | Citations, URLs, DOIs, e-mails | **#66** | textprep | yes | #63 |
| 9 | Numbers, dates, statistics (English) | **#67** | textprep | yes | #63 (misaki via #18 to check) |
| 10 | Abbreviations, symbols, units | **#68** | textprep | yes | #63 |
| 11 | Script job: file → layout → steps → script + report; chapters; JobSettings | **#70** | app | yes | #63, Q6 |
| 12 | Layout: join line pieces with a space only where printed | **#36** | layout | yes (golden) | #39 |
| 13 | Layout: body-size repeated lines taken for running heads | **#33** | layout | yes (golden) | #36 (same lane, serial) |
| 14 | Layout: loose rule joins the wrong block | **#58** | layout | yes (golden) | #33 |
| 15 | Outline field in core + PDF bookmarks as heading hint | **#24** (core PR, then extraction/layout PR) | core, extraction | yes | none |

Rules #64 to #68 can run two at a time (separate modules); the registry file is their only shared file.

### Wave 3: after the script job (#70), the voice (#18) and output (#69)

| # | Work item | Issue | Lane | Crit. | Depends on |
|---|---|---|---|---|---|
| 16 | Audio job: utterances → voice → chunks → output; resume, progress, estimate, fault injection | **#71** (closes #10) | app | yes | #70, #18, #69 |
| 17 | CLI: `script`, `convert`, `voices`; smoke test on 3 systems (PE-02) | **#72** | cli (+infra) | no | #70 (`script`), #71 (`convert`) |
| 18 | Local server and job API | **#76** (closes #7) | web | yes | #70; audio endpoints #71 |
| 19 | EPUB extraction and cover images | **#73** (with #5 for EPUB) | extraction | no | #24 core field |
| 20 | Markdown, text and pasted text | **#74** (with #5) | extraction | no | none (serial after #73 in the lane) |
| 21 | Layout for documents without positions (tags) | **#75** | layout | yes (golden) | #73, #74 |
| 22 | ACL checklist titles as headings | **#48** | layout | yes (golden) | #58 (lane order); #24 may help |
| 23 | Extraction golden files and broken files for PDF | **#5** (PDF part; EPUB/MD parts in #73/#74) | extraction | yes (golden) | none |

### Wave 4: interface

| # | Work item | Issue | Lane | Crit. | Depends on |
|---|---|---|---|---|---|
| 24 | Main flow: open, report with switches, chapters, voice with consent, preview, speed, run, results; Playwright + axe | **#77** (closes #8) | web | no | #76, #71, Q7 |
| 25 | Player with read-along on the original text | **#78** | web | no | #77, #69, Q9 |
| 26 | English and German interface; privacy page | **#79** | web | no | #77, Q10 |

### Wave 5: release

| # | Work item | Issue | Lane | Crit. | Depends on |
|---|---|---|---|---|---|
| 27 | OWASP ZAP baseline scan | **#12** | infra | no | #76 to #79 |
| 28 | Speed script and baseline numbers (Colin's M4 run) | **#11** (rest) | voices | no | #18, #71 |
| 29 | v1.0 on PyPI: install test on 3 systems, licences, README, changelog, release checklist, learning notes | **#80** | infra/docs | yes | everything; Q13 |

KB decision PRs follow each wave (one per batch of coordinator decisions), reviewed in their own threads as usual.

## 3. What each remaining stage must do (per the KB contracts)

**textprep.** Every text rule is a `TextStep` (id, languages, category, `find(document, context) -> list[Edit]`, D-57) that proposes marked edits on spans inside one block (D-61: remove, replace, pause, ask) and never changes the text, so read-along, the report and the per-category switches keep working. Placeholder notices for formulas and tables are `replace` edits from a step (D-61 (5), D-55); page furniture is removed by an edit (D-63, TP-01). v1.0 needs 11 Must rules (TP-01 to TP-11), FX-01/FX-02, IN-04, the English regression corpus (#4, PE-03) and the conformance suite (#6). The interface is internal in v1.0 and public in v1.1. **Gaps:** the KB does not define the category list, the order of steps, how overlapping edits are settled (D-61 only says "the app chooses"), what `context` holds, what D-57's "stage" field means, or who cuts the script into sentences for the voice (Q4, Q15). All go into the #63 plan.

**voices.** Abogen's contract types and Kokoro plugin are copied in with their MIT notice (D-52), on PyTorch (D-48), English first (D-50); models are downloaded only when the user starts it, from the official Hugging Face repo, with the licence shown (VA-03, CLAUDE.md network rule); `PYTORCH_ENABLE_MPS_FALLBACK=1` is set at start-up. The voice turns one utterance into audio; the app stores it as an `AudioChunk` (span, relative file, duration) in the job folder. **Gaps:** speed and preview are not in #18's criteria (VA-05 is a Must); misaki loads a spaCy English model and may download it at run time, which would be a network call the user did not start, and its espeak-ng fallback needs a licence and install check (Q12).

**output.** Turns audio chunks into one MP3 per chapter and an M4B with chapter marks, cover and metadata including the "AI-generated" label (OU-01, AQ-04, playbook 3.5), inserts pauses, and writes the read-along timing from the chunks' spans and durations (OU-02, core docstring). It imports only core, so its chapter input is a small type defined in `output` that the app fills. **Gaps:** where ffmpeg comes from (Q5), pause lengths (D-61 left them open, Q8), and the read-along file format (Q9).

**app.** The job runner and settings that wire the stages together (CLAUDE.md): each job gets its settings and working folder passed in (no global state); one job at a time; it picks extraction by file type, runs layout and the chosen text steps, settles overlapping edits, applies them (`apply_edits`), builds chapters, has the voice speak, and hands the chunks to output; it never stops to ask (D-61 (3)); it resumes by skipping finished chunks and chapters (WI-02); it measures speed on the first chapter for the time estimate (playbook 3.2); settings persist in a local config file (playbook 3.4). **Gaps:** what a chapter is (Q6), the report format (in #70), and where settings live (recommend `platformdirs`, MIT; decided in #70's plan).

**cli and web** (for completeness). `cli` gets `script`, `convert`, `voices` and `ui` (WI-03). `web` is one local browser interface (D-45) on a FastAPI server bound to 127.0.0.1 with token and origin checks (#7), accessible (AQ-01), in English and German (AQ-02), with read-along (OU-02).

## 4. Decisions (coordinator, 12 Nov 2026, Colin informed 22:39:45Z)

Each line is binding for the implementing threads. "KB" = recorded in the decision log (D-96 onward); "plan detail" = settled in that issue's plan, no KB entry.

| Q | Decision | Affects | KB |
|---|---|---|---|
| Q1 | **Keep D-69.** The plans of #64 to #68 are approved together, in one batch, once #63 merges; each PR still gets its own review thread. | throughput | yes (with Q14) |
| Q2 | **Footnotes are read where layout placed them (the column foot, in reading order)**, introduced by their mark ("Footnote 1."); footnote marks are removed from the running text; one category switch leaves all footnotes out. Refines TP-05, which named no place. Moving a note next to its mark waits for v1.1 (needs a core change, D-61 (1)). | #64 | yes |
| Q3 | **A placeholder's `replace` edit is one short notice naming the item through its caption's `describes` link**: "Table 2 is skipped." / "Figure 1 is skipped." / "Formula 4 is skipped." / "A formula is skipped." (no number, no caption). **The caption block is left to read as printed**, in its printed position (it already starts with its label). One wording table in `textprep`, English only (D-50). | #64 | plan detail |
| Q4 | **`textprep` owns the utterance cutter**, working on `ScriptPiece`s (sentence-sized spans inside one block; one `AudioChunk` per utterance); voices never see a `Document`. Line breaks inside a block become spaces in the cutter, not edits; a hyphen at a line end is an edit (#65). **Kokoro has a per-call input length limit, so a very long sentence gets a fallback cut at clause marks** (commas, semicolons, colons), tested. No core change. | #63, #71 | yes |
| Q5 | **ffmpeg from `imageio-ffmpeg`** (BSD-2 wrapper; 0.8.1 bundles ffmpeg 9.0), **with an ffmpeg on PATH as fallback**. imageio-ffmpeg ships **no ffprobe**: #69 reads its files back by parsing `ffmpeg -i` / `ffmpeg -f ffmetadata` output or with a Python reader, never ffprobe. The binaries are GPL builds (fine for GPL-3.0-or-later); the #69 PR names the licence per platform and confirms libmp3lame and aac are compiled in. | #69, #80 | yes |
| Q6 | **A chapter is a level-1 section.** Text before the first heading is the first chapter, titled with the document title from `Content.metadata` (the title the file gives), with the file name as fallback. EPUB: one chapter per top-level navigation entry. No headings: one chapter. References are deselected by default; appendices stay selected. **The #70 plan must state:** text steps run on the whole document; the chapter filter applies when utterances are cut; the report marks edits in deselected chapters as not spoken. | #70, #69, #72, #77 | yes |
| Q7 | **Server-rendered HTML** (FastAPI with Jinja2) plus a little plain JavaScript; progress by server-sent events through `StreamingResponse`; `python-multipart` for file upload; **no front-end build step**. The #78 player is the one page with real JavaScript. Licences: FastAPI MIT, uvicorn BSD-3, Jinja2 BSD-3, python-multipart Apache-2.0. | #76, #77, #78 | yes |
| Q8 | Pauses are output settings with defaults **2.0 s before a chapter, 1.0 s after a heading, 0.6 s between paragraphs, 0.5 s for a `pause` edit**. | #69 | plan detail |
| Q9 | **Read-along on the document's block text** (the original words, highlighted per utterance), not on PDF page images (later). The read-along JSON is **versioned and owned by `output`**. | #69, #78 | yes |
| Q10 | German interface stays in v1.0 (AQ-02 is a Must); spoken notices stay English. | #79 | no (no change) |
| Q11 | **`sci2audio.testing` (the conformance suite) sits beside `app`**: the layer line becomes `sci2audio.app \| sci2audio.testing` (it may import the stages and core; nothing imports it). It **must not import pytest or hypothesis at module import** (plain callables that the tests wrap, or behind an optional extra), so they never become run-time dependencies. Refines the D-46/D-63 layer contract. | #63, #18 | yes |
| Q12 | misaki's `G2P.__init__` downloads `en_core_web_sm` when missing, and **that model is not on PyPI** (no pinned dependency possible). So **the user-started voice setup fetches the model wheel (MIT) from explosion's GitHub release into the cache** and either puts it on `sys.path` or installs it; the #18 plan picks one and **tests the no-network path**. espeak-ng comes with the `espeakng-loader` wheel (GPL-3.0, bundled binaries): licence entry, no system install. **Set `HF_HUB_OFFLINE=1` except during the user-started download.** D-47's "everything for offline use" download = voice + spaCy model, named in #18. #72 and #76 call the one download function that #18 exposes in `voices`. | #18, #71, #72, #76 | yes |
| Q13 | Colin's own steps before v1.0, told to him now: listening test, screen-reader pass (VoiceOver, NVDA), speed run on the M4 (VA-02), PyPI trusted-publisher setup, **retiring the hosted demo** (playbook phase 1) and **the `sci2audio.com` homepage URL in `pyproject.toml`**. | #80, #11 | no (heads-up) |
| Q14 | **#47 moves into v1.0** and is fixed first (test-only). | #47 | yes (with Q1) |
| Q15 | **The registry is ordered coarse to fine**: whole-block removals (furniture, reference list, placeholder notices, footnote handling) before rules inside a block. **The earlier step wins** an overlap; the other edit is "set aside" and listed in the report. `ask` edits read the original until answered (D-61). **No built-in v1.0 step may emit `ask`** (nothing in v1.0 answers it; UC-04 is Should); the runner and report still support it. | #63, #70 | yes |

Further points from the approval:

- **VA-02 install size on Linux:** the PyPI `torch` wheel for Linux pulls the CUDA libraries (several GB). The #18 plan decides between documenting a CPU index for Linux and accepting the size (added to #18).
- **#39:** under D-80 the **review thread** checks every new truth sentence against the PDF, not Colin. Format (D-106): footnote marks and inline maths written in line as printed (no space where the page has none; Greek letters and symbols as Unicode; stacked scripts superscript first); `where` gains `footnote-mark` and `inline-maths`; `MAX_VERBATIM` 5 → 7; a footnote-mark sentence must contain a mark listed in the truth's footnotes for its page.
- **#5:** its text is narrowed to PDF only when #73/#74 start.
- **#63** may be split by its authoring thread into two PRs (interface + registry + runner + furniture step + harness, then the cutter); not required.
- **#64**'s corpus test runs on `apply_edits` output until #70 exists.

## 5. Revised estimate: about 30 % done

- **By feature:** about 5 of the 41 Must features have code (IN-01 complete; PE-01, PE-02, PE-04, PE-05 in part). That is about 12 %, but it undercounts, because layout was by far the largest single feature.
- **By PRs:** about 25 PRs are merged for setup, corpus, truth files, core, extraction and layout. About 38 to 42 code PRs remain (6 layout follow-ups and #24 in two parts, 6 textprep, 2 voices, 1 to 2 output, 2 app, 1 cli, 3 extraction, 4 web, 1 to 2 release). Counting a layout PR as about 1.3 remaining PRs, because each took more review rounds than most remaining work will: about 32 done of about 72 units, so 40 to 45 % by PR effort.
- **By risk:** the hardest uncertain piece (layout against truth counts) is done. Still open risks: PyTorch install size and CI time (#18), misaki's model download (Q12), ffmpeg (Q5), and the accessible interface, which has no code at all.
- **Weighting both:** about **30 %** (range 25 to 35 %). My number is lower than the earlier 40 % because the user-facing half (rules, voice, audio, app, interface, release) is about 60 % of the remaining PRs and has not started.
- **Time:** at today's pace about 2.5 to 3.5 working days of threads if every PR passes in one review round. Layout PRs needed two to three rounds, and the voice, ffmpeg and interface are integration work, so the second opinion's **4 to 6 thread-days** before #80 is the better planning figure. The steps that need Colin's hands (Q13) come on top, and the release cannot happen before them.

## Appendix: the 41 Must features and where they are

| Feature | Where |
|---|---|
| IN-01 PDF layout | done (#21); follow-ups #24, #33, #36, #39, #48, #58 |
| IN-02 EPUB | #73, #75, #5 |
| IN-03 Markdown, text, pasted | #74, #75 |
| IN-04 Unicode, ligatures | #65 |
| TP-01 furniture | #63 |
| TP-02 hyphenation | #65 |
| TP-03, TP-04, TP-07 citations, URLs | #66 |
| TP-05 footnotes, TP-06 references | #64 |
| TP-08 abbreviations, TP-10 symbols and units | #68 |
| TP-09 numbers, TP-11 statistics | #67 |
| FX-01 formulas, FX-02 tables | #64 |
| UC-01 report | #70, #77 |
| UC-02 category switches | #63, #77 |
| UC-03 chapter selection | #70, #77 |
| VA-01 Kokoro English, VA-02 PyTorch check | #18, #11 |
| VA-03 download with licence | #18, #72, #77 |
| VA-04 offline after setup | #71 (#10) |
| VA-05 preview and speed | #18, #77 |
| OU-01 MP3 and M4B | #69, cover #73 |
| OU-02 read-along | #69, #78 |
| WI-01 PyPI | #80 |
| WI-02 resume | #71 |
| WI-03 command line | #72 |
| AQ-01 accessible interface | #77, #78 (#8) |
| AQ-02 English and German interface | #79 |
| AQ-03 no telemetry, privacy statement | #76 (#7), #79, #12 |
| AQ-04 AI label | #69 |
| PE-01 licences | #80 |
| PE-02 CI with smoke test | #72 |
| PE-03 English regression corpus | #63 to #68 (#4) |
| PE-04 written contracts | CLAUDE.md (done); #63, #18 add the plugin contracts |
| PE-05 layers | done (lint-imports); #63 Q11 |
| PE-06 releases, changelog | #80 |
| PE-10 text-step interface | #63 (#6) |
