# Playbook: optimising the PDF → rules/LLM → TTS pipeline

`[PLAYBOOK]` · How to improve listening quality, faithfulness, cost and speed safely, with the measurement tools that already exist. Backlog items are `[repo fact]` from `ROADMAP.md` (26 Oct), `docs/MUSTERPROBEN.md` and `docs/EVALUATOR.md` (8 Nov). Prioritisation and process are `[advisor proposal]`. Lanes refer to `playbook-dev-lifecycle-operating-model.md` §4.

---

## 1. Objectives and metrics

| Objective | Metric | Today (where known) | Source of truth |
|---|---|---|---|
| **Faithfulness** (no changed meaning) | Regression cases passing; meta sentences; invented "ich"/counts; lost negations/conditions/sources | Audit report of 4 runs: **96 documented errors: 38 from rules, 16 from extraction, 29 pure AI** | Evaluator (`sci2audio eval`), `regressionen.json` |
| **Reading accuracy** (extraction) | Sample PDFs passing; known-wrong (`bekannt`) count; coverage per page (`abdeckung_*`, `abgleich_*`), `seiten_fehlend`, `rueckspruenge` | 19 samples; **6 known-wrong** (§3) | `sci2audio musterprobe pruefen`, evaluator |
| **Speakability** (rule coverage) | Share of text needing no AI; risk index before/after; residue in post-check; digits/spelled-out letters/abbreviations left in the script | **54%** of the sample PDF needs no AI | Pre-analysis report, post-check, evaluator "Hörskript" metrics |
| **Cost** | Real US$ per 1,000 words per class and model; estimate error | Haiku high 2.5–4.6 ¢; Sonnet high 25–42 ¢ (31 Oct); Sonnet high 900-word packs 21.2 ¢ (1 Nov); Akademisch on Sonnet medium ≈ ⅓ of Sonnet high | `run_stats`, calibration, margin report |
| **Speed** | Seconds per 1,000 words per phase/voice; wall time per run | start 30 s; ki 30 s; premium 45 s; Azure 12 s; Azure HD 15 s; browser 30 s; Kokoro 120 s (`dauer.RUN_SECONDS`) | `sci2audio leistungstest` (reference per deploy), `verlauf.py` learning |
| **Read-along accuracy** | Sentence starts at the audio; verified pairs share | Sync test in `deploy.sh` | `sci2audio synchrontest` |

## 2. Measurement toolbox (use before every change)

| Tool | What it measures | Cost | When |
|---|---|---|---|
| Detector tests (`tests/test_analysis.py`) + example sentences in `tests/sample_voranalyse_de.md` | Every rule has a test and a sentence | Free | Every rule PR (tier 1) |
| **Sample PDFs** (`musterprobe pruefen`; 19 PDFs with `.soll.json`/`.soll.md`: outline, paragraph and word counts, what isn't read and why, hand checks `nicht_im_text`, `im_text`, `ueberschrift` + `ebene`, `keine_ueberschrift`, `nicht_vorlesen`; `bekannt: true` = known error, reported as "behoben" once fixed) | Extraction and structure | Free | Every `lane:pdf` PR; nightly |
| **Evaluator fixed checks** (`sci2audio eval pruefen`) | Coverage, order, artefacts (underscores, `##`, structure lines, garbled text, superscripts), fragments, reading-version years/quotes/number words, script digits/spelled letters/abbreviations/capital acronyms, meta sentences, bibliography words, report integrity | **Free** (no model in `sci2audio/evaluator/`, enforced by a test) | Every rules/prompt change |
| **Evaluator corpus** (18 documents: 5+5 training DE/EN, 2+2 test, 4 regression; chapters 10–20 pages; 3 German scans) | Before/after on real chapters | Free for rule levels; AI levels only with `--bezahlt --budget` (pilot: ≤ $1 per call) | Prompt and rule changes |
| **AI grader** (`/eval-bewerten VARIANTE`, Claude Code on the **subscription**, never the API; sections ≈ 800 words; hashed tasks so unchanged sections aren't re-graded) | Invented or distorted statements, missing sentences, torn tables | Subscription usage | Prompt variants |
| `sci2audio luecke DATEI` (`gap.py`) | How far the free run is from the AI run | Free | Prioritising rules |
| `sci2audio leistungstest` | Time and memory per step vs. reference | Free | Every deploy (gate) |
| `sci2audio synchrontest` | Read-along sentence starts at the audio | Free | `lane:readalong`/`lane:voice`; deploy gate |
| `sci2audio ttsbench`, `tempo`, `vertonungstempo`, `stimmvergleich` | Voice speed and comparison | Free / small | Voice work |
| Post-check residue (`NAME.nachpruefung.md`) | What still needs a decision or AI after the run | Free | Every run |
| Anonymous correction statistics (`korrekturen.py`) | What users fix by hand in the outline | Free | Monthly review |

**Rule for every optimisation PR:** state the metric, show before/after on the relevant tool, and keep the test set untouched by inspection (the evaluator's `test` role exists so improvements aren't overfitted to it).

## 3. Backlog (consolidated, with priority)

### 3.1 Known extraction errors (sample PDFs marked `bekannt`, 8 Nov 2026)
| Sample | Error | Lane | Priority |
|---|---|---|---|
| healy | Letter-spaced chapter line "C H A P T E R 6" read letter by letter | pdf | P1 |
| cubela | Publisher logo "U N R A S T" read; letter-spacing tears words in headings ("Geschic hte", "war um"); subtitle "– oder warum …" becomes its own chapter | pdf | P1 |
| bauer-dahme-wohlfahrt | Two-line headings glued at the line end ("Aufgabenprofilsder", "Lohndumpingstatt") | pdf | P1 |
| maruschke | TOC without dot leaders becomes headings; front-matter running title becomes a heading | pdf | P1 |
| jogh | Formula "logit ( )= +" and "Correspondence to:" become headings | pdf | P2 |
| al-najjar | Table labels ("Table 1") become headings | pdf | P2 |
Common root: **letter-spaced text and heading classification**. One rule family for letter-spacing (detect single letters separated by spaces across a line, join when the result is a word or known label) fixes three samples.

### 3.2 `ROADMAP.md` items still open
| # | Item | Why (from roadmap) | Lane | Priority | Notes |
|---|---|---|---|---|---|
| 3 | `--max-kosten` hard cap + confirmation before every paid run | "Q ist kostensensibel; kein Lauf darf überraschen" | ai | **P1** (`risk:high`) | Also in phase 0 week 3 |
| 6 | **Targeted repair**: send only post-check residue with its paragraph to a model (stronger if needed), instead of the whole text again | With Haiku, residue remains; a second full pass would pay everything twice | ai | P1 | Big quality lever for Klar & Direkt |
| 7 | Running headers/footers detected statistically (lines repeating on many pages) | Today rough in extraction; confidence 0.6 in analysis | pdf / analysis | P1 | Evaluator already defines running lines (same line top/bottom on ≥ 3 pages) |
| 8 | Captions and figure references ("siehe Abb. 3") as a decision with suggestion | References into nothing disturb listening | analysis | P2 | Partly done by `abbildungen` detector (8 Nov) |
| 9 | Lists into sentences by rule ("erstens, … zweitens, …") | Saves the AI class for simple enumerations | analysis | P2 | |
| 10 | Short tables (two columns) as "Zeile: Wert" by rule | Many tables in student papers are simple mappings | analysis | P2 | |
| 11 | Homographs decided by context word lists ("modern" before a noun vs. verb) | Turns decisions into automatic fixes | analysis | P3 | Confidence today 0.4 |
| 12 | English texts: abbreviations, numbers, dates, units for `en` | Pipeline is language-capable, rules are German | analysis | P1 if English users matter | EN prompts exist |
| 13 | English technical words without lexicon entry: suggest by spelling pattern | Edge TTS can't switch language; most frequent manual decision | analysis | P3 | Lautschrift removed 5 Nov; re-check relevance |
| 14 | **Measure per test book**: share per class, risk before/after, false alarms; target in CI | "Ohne Zahlen keine Priorität" | tools | **P1** | Wire evaluator fixed checks into the nightly |
| 15 | Content-hashed segment cache for TTS (text + voice) | A corrected sentence re-voices only itself | voice | P2 | Saves Azure cost on edits |
| 16 | Piper as offline TTS, optional | From the old tool; only if wanted | voice | P3 | Licensing (pillar 04) |

### 3.3 New items from this KB
| Item | Lane | Priority |
|---|---|---|
| Docs drift: "13 detectors" → 20; "22 categories" → 25; add a test that checks counts in docs vs. code | docs / tools | P2 |
| PDFium lock + concurrency test | pdf | **P0** (phase 0) |
| Shrink the 55 s `test_rechte` fixture so tests check rules, not throughput | tools | P2 |
| Evaluator AI grader as a scheduled task (subscription) after prompt PRs | tools | P2 |
| Error taxonomy from the 96-error audit report as Issues (38 rules / 16 extraction / 29 AI), each linked to a regression case | docs | P1 |

## 4. Prioritisation logic
1. **Faithfulness before cost.** A wrong statement in a scientific text is worse than a higher bill; AI errors (29) and rule errors (38) from the audit come first.
2. **Rules before prompts.** Every rule saves tokens on every book and is deterministic; prompts are the safety net. (`VORANALYSE.md` §5: proposals covered statistically first, prompt only as backup.)
3. **Biggest audience first.** German humanities texts before English; English parity (item 12) when English users appear.
4. **Measured impact.** Use `luecke` and the evaluator to rank: which category costs the most AI words or causes the most residue?

## 5. Change protocols

### 5.1 New or changed rule (`lane:analysis` / `lane:pdf`)
1. Issue with example text (or sample PDF) and the expected spoken form.
2. Failing test first; add a sentence to `tests/sample_voranalyse_de.md`.
3. Implement as a `Detector` (or extend one): name, title, description, order, `run()` yielding findings with action and confidence; `claims` if spans must be protected.
4. Run: tier 1, `voranalyse` on the sample text, sample PDFs (`--leer-ok` only in environments without samples, stated in the PR), evaluator fixed checks on the training corpus (rule levels are free).
5. PR shows: findings before/after on the training set, false alarms checked, share of "ohne KI" before/after.

### 5.2 Prompt change (`lane:ai`, often `risk:high` for cost)
1. Create a variant folder: `sci2audio eval prompts` writes the four built-ins (`klar-de.md`, `klar-en.md`, `akademisch-de.md`, `akademisch-en.md`); edit only what's needed.
2. Pilot on training chapters with `--bezahlt --budget` (≤ $1 per call); compare against the baseline (two baseline repetitions exist: `basis-w2`).
3. Fixed checks + regression cases + AI grader (`/eval-bewerten`).
4. Test set measured, never inspected for tuning.
5. Adopt only if faithfulness doesn't regress and cost per 1,000 words stays within the price margin; update `doc-prompts-and-detector-rules.md` appendices with `tools/extract_prompts.py` in the same PR.

### 5.3 Model or effort change
Triggered by new model releases or price changes. Blind test as done on 31 Oct / 1 Nov / 5 Nov (Argon, four books): same chapters, rules + check + repair included; record cost and thinking ratio; update `sprechfassung.THINKING_HIGH` and calibration.

### 5.4 Voice change
Licence check first (pillar 04, `RECHTSLAGE.md`), then `stimmvergleich`, `ttsbench`, sync test, listening test; set tempo (Thorsten 0.85).

## 6. 90-day optimisation plan (after phase 0; parallel to phases 1–2 in `lane:analysis`/`lane:pdf`)

| Weeks | Focus | Deliverables | Metric target `[advisor proposal]` |
|---|---|---|---|
| 1–2 | Measurement in CI (item 14) | Nightly runs evaluator fixed checks on the training corpus (rule levels) + sample PDFs; results file per night; dashboard table in the Sunday brief | Baseline numbers recorded |
| 3–4 | Letter-spacing and heading classification | Fix healy, cubela, bauer-dahme-wohlfahrt, maruschke | 4 of 6 `bekannt` → "behoben" |
| 5–6 | Running headers/footers (item 7) + publisher boilerplate tuning | Statistical detection with evaluator's definition | Artefact counts ↓; coverage unchanged |
| 7–8 | Targeted repair (item 6) | Residue paragraphs re-sent (Haiku → Sonnet if needed) | Post-check residue ↓ by ≥ 50% on Klar & Direkt at ≤ +10% cost |
| 9–10 | Lists + short tables by rule (items 9, 10) | Two rule families | "ohne KI" share ↑ (e.g. 54% → 60%+) |
| 11–12 | `--max-kosten` (item 3) + segment cache (item 15) | Hard cap, confirmation; cache keyed by text+voice | No run exceeds its quote; re-voicing after edits ↓ |

## 7. Advisor pre-analysis
- **The measurement system is better than most startups' and underused.** It isn't automated, so improvements are anecdotal. Item 14 (measure in CI) is the multiplier for everything else.
- **Faithfulness is the brand promise for academics.** The prompts already encode an unusually careful rule set (modality, attribution, negations, counts, no meta talk). The remaining 29 AI errors should become regression cases, then prompt or rule fixes, measured.
- **Haiku for Klar & Direkt is a margin decision** (2.5–4.6 ¢ cost vs. 10 ct price list). Targeted repair keeps that margin while lifting quality.
- **Letter-spacing is a cheap, high-visibility win** (three of six known errors).
- **Beware overfitting to the 4 audit documents.** Keep the test split sacred.

## 8. Open questions
| # | Question | Default |
|---|---|---|
| Q1 | Which metric is the north star for quality? | Regression cases passing + post-check residue per 1,000 words |
| Q2 | Budget per month for paid evaluation runs? | e.g. $20 pilot cap; AI grader on subscription |
| Q3 | Prioritise English rules (item 12) now or after the first English users? | After first English demand signal |
| Q4 | Keep the classic routed classes alongside the Sprechfassung? | Yes, for tables/formulas/figures |
