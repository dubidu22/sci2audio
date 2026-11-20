# Pipeline architecture: document → listening script → audio → read-along

`[DOC]` · How a run works end to end, stage by stage, with modules, artefacts, costs and the constraints that matter for the phase-2 worker split (ADR-002). Facts are `[repo fact]` from `audiobook-generator` HEAD `35db2c1` (8–9 Nov 2026) unless marked. Detector and prompt details: `doc-prompts-and-detector-rules.md`.

---

## 1. Overview

```
Upload (PDF / EPUB / MD / TXT / pasted text)
  │
  ▼
1 EXTRACT ─────────── pdfdatei (pypdfium2) · pdflayout (own layout engine) · kodierung (broken fonts)
  │                    Tesseract OCR for scans · bildmodell (layout model, local only) · epub · figures markers
  ▼  Markdown with <!-- seite N --> page marks and <!-- bild … --> picture markers
2 STRUCTURE ───────── sections (chapters from bookmarks / headings / numbered lines) · back matter deselected
  │                    page range · start/end markers · user's editor version (bearbeitung) if any
  ▼
3 PRE-ANALYSIS ────── analysis/ (20 detectors) → Report (findings: AUTO / DECISION / INFO; risk index)
  │                    decisions per document (categories on/off, per-finding rule/AI/ignore) · glossary
  ▼
4 ROUTE ───────────── routing.build_route: rule fixes applied; AI paragraphs marked by class
  │                    classes: ohne KI · Satzglättung (Haiku) · Verständnis nötig (Sonnet) · Sprechfassung
  ▼
5 REWRITE ─────────── rules: normalizer.rule_based_script (+ satzteilung, glossary)
  │                    AI: RoutedRewriter (batched units, checkpoints) · sprechfassung (whole subchapters / 900-word groups)
  │                    sprechfassung checks: rule check + faithfulness → one targeted retry → rules stand in
  ▼
6 POST-CHECK ──────── same detectors over the finished script; rules fix residue; NAME.nachpruefung.md
  ▼
7 VOICE ───────────── tts (Azure Neural/HD on server) · browserstimme (Thorsten in the visitor's browser)
  │                    geraetestimme (live device voice, no file) · quellenstimme · zweitstimme · pauses
  ▼
8 ENCODE ──────────── ffmpeg: MP3 96k mono / M4B with chapters + cover / Opus; per-chapter files optional
  ▼
9 READ-ALONG ──────── mitlesen: original ↔ script sentence alignment (no model) → .mitlesen.json
  ▼
10 REPORTS ────────── lesefassung (reading version) · diffview (comparison) · aenderungsbericht (change report PDF/MD)
```

## 2. Stages in detail

### 2.1 Extract
| Aspect | Detail |
|---|---|
| PDF engine | **pypdfium2** (PDFium; Apache/BSD) wrapped in `pdfdatei.py`; **no AGPL** (PyMuPDF deliberately avoided) |
| Layout | `pdflayout.py` (1,660 lines): columns, headings, footnotes, tables (incl. tables with lines, 8 Nov), running headers/footers (rough), footnotes across page breaks |
| Broken fonts | `kodierung.py`: PDF text stored as glyph numbers; solved via dictionary/learned glyph order; few-word fonts: glyphs learned via OCR (#294) |
| Scans | Tesseract OCR (`tesseract-ocr` + `-deu`); OCR cache per upload; pages read side by side |
| Layout model | `bildmodell.py`: PP-DocLayoutV2 (PaddleOCR, Apache 2.0) via onnxruntime on uncertain pages; 213 MB; 0.3–0.9 s and 0.5 GB per page; **local only, never online** (`SCI2AUDIO_BILDMODELL=ja|alle|nein`) |
| EPUB | Own reader (`epub.py`) + beautifulsoup4 (EbookLib avoided: AGPL) |
| Figures | `figures.py`: marker `<!-- bild p3@72,140,450,322 600x360 -->` where a picture stands (long edge ≤ `MAX_EDGE`); logos/rules/icons get no marker |
| Cover | First PDF page or EPUB cover; user upload overrides |
| Output | Markdown with page marks; cached per upload; `RECOGNISED` OCR results kept with the upload |
| Size handling | `verkleinern.py` resamples pictures after reading; `platz.py` checks disk and memory before a run; uploads up to ≈ 500 MB online |
| Concurrency | **PDFium not thread-safe**: today read in a thread per upload (`web.py` `lesen-{file_id}`) without a lock (P0, `audit-pdfium-thread-crash.md`) |

### 2.2 Structure (`sections.py`)
- Chapters from PDF bookmarks (with page numbers), else layout headings; EPUB headings + TOC; plain text: numbered lines ("2 Methoden", "Kapitel 3").
- Back matter deselected by default: bibliography, index, formalities (declaration of authorship, acknowledgements), recognised by the whole heading ("Literatur und Gesellschaft" stays); same-named subsections at chapter end dropped; `skip_sections` default `literatur,register,formalia`.
- Selection by chapters, page range, or text between start and end markers.
- Editor version (`bearbeitung.py`) replaces extraction when the user edited (their text, their chapters; nothing left out by rules).

### 2.3 Pre-analysis (`analysis/`)
20 detectors in fixed order → `Report` with findings (`AUTO` fix, `DECISION` for the user, `INFO` = needs AI), confidence 0–1, page, context; 22 categories in 4 groups; risk index per 1,000 words (AUTO 0.05, INFO 1, DECISION 3, homographs 1.5; < 8 low, < 20 medium, above high). Decisions per document in `~/.sci2audio/entscheidungen/ID.json` (SHA-256 of content, 16 chars). Free, no model, cached per file and options (`Workspace._analysis`). Full catalogue: `doc-prompts-and-detector-rules.md`.

### 2.4 Route (`routing.py`, 1,025 lines)
- Applies all rule fixes except those set to "KI"; marks paragraphs with AI findings; class from the hints (`AI_KINDS`): smoothing kinds → **Satzglättung**, understanding kinds → **Verständnis nötig**; higher class wins (`CLASS_RANK`: glaettung 1 < verstaendnis 2 < sprechfassung 3).
- Consecutive AI paragraphs of the same class form a **unit**; units are batched per class up to the class's word size and **at most 12 units per call** (`MAX_UNITS_PER_CALL`: "more tags per answer make a lost or merged paragraph likelier").
- Class settings: Satzglättung on `smoothing_model` (**Haiku, low**) unless the scale is Haiku; Verständnis on the scale's model; Sprechfassung on its own model/effort and call size.
- Ignored text shielded by placeholders during rule normalisation.
- `estimate_route()` gives cost and range per class; calibrated after real runs (`calibration.py`).

### 2.5 Rewrite
| Path | When | How |
|---|---|---|
| Rules | "Vorlesbar", and every paragraph without AI | `normalizer.rule_based_script` (abbreviations, numbers, units, gender, citations per mode, symbols), `satzteilung.split_long` (sentence limit, if set), glossary |
| Routed AI (classic) | AI classes outside the Sprechfassung | `RoutedRewriter`: units tagged `<absatz nr="N">`; falls back to one call per unit on a broken answer; checkpoint per unit; system prompt `prompts.SYSTEM_PROMPT_TEMPLATE` (cacheable, 3 config values) + user prompt with `<kontext_vorheriger_abschnitt>` + `<zu_verarbeitender_text>`; optional verify pass (`VERIFY_SYSTEM_PROMPT`) |
| **Sprechfassung** (Quick Start AI levels) | "Klar & Direkt": **Haiku high**, whole subchapters ≈ **1,500 words/call**; "Akademisch & Flüssig": **Sonnet medium**, ≈ **900-word groups** | Paragraphs numbered `[N]` (max 40 per call); neighbours as `<davor>`/`<danach>` context; footnotes as `<fussnote>`; glossary; model gets the **original's digits, sources and quotation marks** (`AI_ORIGINAL_FORMS`), rules speak digits afterwards; rule check + faithfulness check → one targeted retry with hints → if still severe (invented "ich" or count), **the rules' text stands in** |
| Classic quality presets (CLI/expert) | `regelbasiert` / `schnell` (Haiku low) / `standard` (Sonnet medium) / `präzise` (Opus high) | Chunk sizes: regelbasiert & schnell 1,200–1,600 words, context 0/1 sentences; präzise 400–600 words, 5 context sentences; standard 600–800 (README) |

Reliability: retries with `tenacity`, honours `retry-after`; process-wide 429 gate (4 → 2 → 1 parallel calls; recovers after 8 clean calls; patience 900 s); run queue limits parallel AI runs per account; batches yield to normal runs; `health.py` pre-flight call checks key, credit and model. Checkpoints (JSON) make runs resumable after crash or deploy.

### 2.6 Post-check (`pipeline.post_check`)
Same detectors over the finished script; rules fix what a model left (digits, abbreviations, brackets, gender forms); residue reported in `NAME.nachpruefung.md` and one result line ("Nachprüfung: 7 Stellen nachträglich per Regel korrigiert, 2 Entscheidungen und 3 Hinweise bleiben"). SSML scripts: report only. Free.

### 2.7 Voice
| Voice | Where it runs | Speed (s per 1,000 words, `dauer.RUN_SECONDS`) | Cost to sci2audio |
|---|---|---|---|
| Azure Neural | Server → Microsoft (EU region selectable) | 12 | USD 15 per 1M characters (`tts.TTS_PRICES_USD`) |
| Azure HD | Server → Microsoft | 15 | USD 22 per 1M characters |
| Thorsten / Piper in the browser | Visitor's browser (onnxruntime-web, WebAssembly, ≤ 4 workers, phones 2; lamejs MP3) | 30 | 0 (server plans pieces and joins) |
| Device voice | Visitor's device, live (Web Speech API) | 0 (no file) | 0 |
| Piper full (local) | Own computer, all cores | 13 | 0 |
| Kokoro, system voices, Edge, OpenAI, ElevenLabs, others | CLI / local only (licensing, `RECHTSLAGE.md`) | Kokoro 120, system 15 | varies |
Other run phases: start 30 s; "ki" 30 s and "premium" 45 s per 1,000 words (AI writing). Segments synthesised in parallel (`tts_workers` 16, capped per engine), cached, retried; sources spoken quieter and faster (`quellenstimme.py`); English passages by a second voice (`zweitstimme.py`); length guard per segment (`laenge.py`); Piper tempo 0.85. Paid voice fails → switch to another voice at no extra charge.

### 2.8 Encode
ffmpeg: MP3 at **96 kbps mono** (≈ 43 MB per audio hour), M4B with chapter marks, cover and metadata ("KI-generiert"), Opus; per-chapter files optional (ZIP); pauses: **2.0 s before each chapter**, **1.0 s at section breaks**; parts joined losslessly when all share format (sample rate, channels, constant bitrate), encoded once at the end.

### 2.9 Read-along (`mitlesen.py`, no model, no tokens)
1. Every spoken sentence gets its time: from voice marks (Azure word boundaries), the counted first sample per sentence (Piper/Thorsten in browser via `satzliste.py`), device-voice pieces, else by character share.
2. Script sentences are found in the spoken stream.
3. Original sentences aligned to script sentences monotonically (keep, split into up to 4, merge, drop), chunk by chunk (edited scripts as a whole within a band); a pair counts only when enough words are shared (`verified`); unverified sentences light their paragraph (`block_spans`).
Output: `.mitlesen.json` (original blocks + sentences + seconds; tables with layout). Verified by `sci2audio synchrontest` (sentence starts checked at the audio).

### 2.10 Reports
- **Lesefassung** (`lesefassung.py`): three-way merge of original (O), rules-only (R) and script (S); where S = R the original's spelling returns ("1980", "u. a."), real rewrites stay.
- **Comparison** (`diffview.py`): sentence-by-sentence original ↔ script with marks by origin.
- **Change report** (`aenderungsbericht.py`, `berichtpdf.py`): only changes or whole text; PDF (sci2audio look, neutral, or git-diff look) or Markdown; user's editor steps at the end; made on request, never kept.
- **Word provenance** (`herkunft.py`): how many words the PDF has, how many are read, where the rest went.

## 3. Artefacts per run (local result files, `demo.LOCAL_RESULT_FILES`)
| Suffix | Content |
|---|---|
| `.hoerskript.txt` | Listening script |
| `.vergleich.html` | Comparison view |
| `.aenderungen.json` | Change data (first report format) |
| `.fassungen.json` | Versions for reading version and reports |
| `.nachpruefung.md` | Post-check residue |
| `.mitlesen.json` | Read-along timing |
| `.geraetestimme.json` | Device-voice plan |
| `.mp3` / `.m4b` | Audio |
Plus checkpoints, the pre-analysis report (`--json`, `--bericht`), run log (local `protokoll.py`), cost record (`run_stats`, real cost vs. estimate).

## 4. Configuration surface (selected)
| Setting | Default | Effect |
|---|---|---|
| `citation_mode` | NARRATIV_EINWEBEN / KOMPLETT_IGNORIEREN / **KURZ_AUTOR_JAHR** | How sources are spoken |
| `formula_detail` | SPRECHTEXT_KOMPLETT / KONZEPTIONELLE_ZUSAMMENFASSUNG | Formulas fully or as statement |
| `smoothing_model` / `smoothing_effort` | `claude-haiku-5-5` / low | Satzglättung class |
| `sprechfassung`, `sprech_model`, `sprech_effort`, `sprech_words` | off (CLI); Quick Start sets Haiku high / Sonnet medium; words by model (1,500 / 900) | Sprechfassung class |
| `sentence_limit` | 0 (off) | Split sentences of N+ words |
| `foreign_words` | on | Detect and mark foreign words |
| `text_language` | auto | de / en |
| `analysis_off` | "" | Categories off |
| `skip_sections` | literatur, register, formalia | Back matter left out |
| `chapter_pause` / `section_pause` | 2.0 s / 1.0 s | Audio pauses |
| `audio_format`, `per_chapter` | MP3, off | Output |
| `tts_workers` | 16 | Parallel segments |
| `bildmodell` | ja (local only) | Layout model |
| `price_input` / `price_output` | built-in table | Cost estimate override |

## 5. Constraints for the phase-2 worker split
| Constraint | Consequence |
|---|---|
| PDFium not thread-safe | One job per worker process; no PDF work in the web process |
| Checkpoints per unit | Re-claimed jobs resume; keep checkpoint format stable (stored data) |
| Browser voice runs on the client | The worker plans pieces and joins audio uploaded by the client; job state must wait for client-side synthesis (or let the user leave and continue later) |
| Device voice produces no file | Nothing for the worker; player plays live |
| Rate limits are per process today | Global limiter in Postgres (ADR-002 step 2.7) |
| Heavy dependencies (Tesseract, ffmpeg, ONNX, PDFium) | Worker image = today's Docker image; web image can slim down later |
| Long jobs (minutes to hours) | Leases + heartbeats; progress in Postgres; e-mail/push on finish |
| Costs recorded per class and model | Keep the cost record schema; margin report depends on it |

## 6. Costs per stage (orientation; pillar 03 owns economics)
| Stage | Cost driver | Free? |
|---|---|---|
| Extract, structure, pre-analysis, route, post-check, read-along, reports | CPU on Fly | Yes (no model) |
| Layout model | CPU/RAM, local only | Yes |
| Rewrite: rules | CPU | Yes |
| Rewrite: AI | Anthropic tokens incl. thinking; measured: **Haiku high 2.5–4.6 US¢ per 1,000 words** and **Sonnet high 25–42 US¢** for the Sprechfassung (31 Oct, four books; thinking 23× (Haiku) / 10× (Sonnet) the answer tokens at effort high); Sonnet high 900-word packs **21.2 ¢** measured 1 Nov (`PREMIUM_USD_PER_1000 = 0.23`); Akademisch now on Sonnet **medium** (≈ a third of Sonnet high's cost per the 5 Nov blind test) | No |
| Figures described by AI | Image tokens, only if "Abbildungen" set to KI | No |
| Voice: Azure | USD 15 / 22 per 1M characters | No |
| Voice: browser / device | Visitor's device | Yes |

## 7. Advisor pre-analysis
- **The architecture is already "rules first" in code, not just in marketing.** Every expensive step is optional and bounded: routing sends only marked paragraphs; the Sprechfassung has rule checks and a fallback to the rules' text.
- **Client-side voices are a cost moat and an architectural complication.** They make the free tier nearly free to serve, but jobs depend on the visitor's device finishing synthesis. Phase 2 must model that state explicitly ("waiting for your browser").
- **The pipeline is long but linear.** That suits a job queue with checkpoints per stage; resumability already exists.
- **Measurement exists for every stage** (sample PDFs → extraction; detector tests + `sample_voranalyse_de.md` → analysis; evaluator → rewrite; sync test → read-along; performance test → speed). Wire them into the nightly so optimisation work is safe (`playbook-pipeline-optimization.md`).

## 8. Open questions
| # | Question | Default |
|---|---|---|
| Q1 | Should the layout model ever run online (e.g. as a paid option on a bigger worker)? | No until worker machines with more RAM exist; measure demand first |
| Q2 | Keep the classic routed rewriter (non-Sprechfassung classes) for the Quick Start, or move everything to the Sprechfassung? | Keep both; Sprechfassung for prose, classes for tables/formulas/figures |
| Q3 | Keep M4B + MP3 + Opus, or simplify outputs? | Keep MP3 + M4B; Opus CLI only |
| Q4 | Server-side Thorsten again (when licensed) for users without capable devices? | Only after the licence decision (pillar 04) |
