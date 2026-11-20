# Playbook: from hosted service to open-source desktop app (v1.0)

`[PLAYBOOK]` · Status: **active** (follows ADR-007, Decided 9 Nov 2026) · Owner: Colin · Time budget: ~15 h/week · Estimate: **about 9–11 weeks to v1.0** `[advisor proposal]` · Related: ADR-007, `playbook-dev-lifecycle-operating-model.md`, `playbook-claude-toolkit-and-skills.md`, `playbook-phase-0-foundation.md`, `04-legal-and-compliance/doc-voice-and-model-licensing.md`, `06-open-source-landscape/` (what to copy from Abogen and others: D-45…D-49)

**Goal (definition of done for v1.0):**
- A free, open-source desktop app (Windows, macOS, Linux) that turns a PDF, EPUB, Markdown or TXT file into a faithful listening script and an MP3/M4B audiobook with chapters, entirely offline.
- Uses only the rule-based pre-analysis and local, freely licensed voices.
- Published under GPL-3.0 with complete licence notices, an "AI-generated" label in the audio metadata, and no telemetry.
- Built and released with a documented AI-assisted development workflow.

Provenance: code facts are `[repo fact]` (9 Nov 2026); licence facts are `[external fact]` from `doc-voice-and-model-licensing.md`; estimates and choices are `[advisor proposal]`.

Feature scope: `06-open-source-landscape/feature-list-2026-11-09.md` lists 93 features with IDs (IN, TP, FX, UC, VA, OU, WI, AQ, PE, AI, WD); its 40 **Must** features with release "v1.0" are the scope of phases 1–6, "Later" maps to phase 7. Details per feature are in the Doc (artifact `S51tv9ry75nsJDtKoNUyjJ`, tab "Feature list").

---

## 0. Learning track (the real goal)

Each phase practises one set of AI-assisted methods. Write a short "what I learned" note at the end of each phase (`docs/learning/phase-N.md`). These notes become the portfolio for client work.

| Phase | Method practised | Artefact for the portfolio |
|---|---|---|
| 1 Retire the hosted service | Writing runbooks with Claude; safe destructive operations with checklists | Shutdown runbook |
| 2 Extract the public repo | Spec-first Issues, `CLAUDE.md`, skills (`ship-issue`), deleting code safely under tests, secret scanning | Issue/PR history, `CLAUDE.md` |
| 3 Refactor the core | Test-driven refactoring with Claude, splitting a 7,245-line module, fresh-session code review | Before/after architecture notes |
| 4 Voices and audio | Spikes with measurable criteria, licence audits as a checklist | Voice evaluation table |
| 5 Packaging and CI | GitHub Actions matrix builds, reproducible releases | Release pipeline |
| 6 Release and docs | Docs-as-code, changelog, semantic versioning | Public v1.0 release |
| 7 Optional | English rename (ADR-004) with the `rename-area` skill; local LLM plugin; Android | Large-scale rename case study |

Keep the lifecycle rules from `playbook-dev-lifecycle-operating-model.md`: one Issue per thread, green tests before merge, review queue ≤ 3, Sunday planning, a monthly retro.

## Phase 1: Retire the hosted service (week 1, ~4 h)

| # | Step | Done when |
|---|---|---|
| 1.1 | Tag the current state of `audiobook-generator`: `git tag hosted-final` and push the tag | Tag exists |
| 1.2 | E-mail invited testers: the hosted test ends on a date (≥ 14 days ahead); results can be downloaded until then; an open-source desktop version will follow | Mail sent |
| 1.3 | On the date: delete all accounts, uploads and results (the privacy policy promised deletion); keep nothing personal. Bookings: no payments were ever live, so there are no accounting records to keep | Database and volumes empty |
| 1.4 | `fly scale count 0 -a sci2audio-demo`, then destroy the app and volumes; delete the Neon project and Tigris bucket if they exist | Nothing billed |
| 1.5 | Revoke or rotate the production API keys (Anthropic, Azure); Stripe test keys can simply be deleted | Old keys dead |
| 1.6 | Replace sci2audio.com with a static page on GitHub Pages: what the app does, download (later), licence, contact. A short Impressum is cheap insurance | Static site live |
| 1.7 | Cancel paid services no longer needed (mailbox if unused); keep the domain | Monthly cost ≈ domain only |

## Phase 2: Extract the public repository

> **Proposed change (D-56, 10 Nov 2026):** build the public repo by moving the kept modules in, one Issue each, instead of deleting in the private repo. Start order, setup checklist and tools: Doc "sci2audio desktop app: how to start execution" (artifact `PRWekgcRWVj9MHkZKWUhLt`). (weeks 2–4, ~35 h)

> **Decided change (D-59, 12 Nov 2026):** the kept modules are not moved in. Each area is **rewritten** in English against the D-46 layers and D-57 text steps, with the old code as reference only; no old output is used as an answer key. Steps 2.2 (dependency map) and 2.3 (removal Issues) and 3.1 (split `web.py`) no longer apply; the table below now lists what to *read* when rewriting each area. Golden files: D-60.

> **Decided change (D-63, 12 Nov 2026):** the pipeline gets a **layout** stage: `extraction → layout → textprep → voices → output`. Extraction only records what the file holds (positions, fonts, sizes, bold/italic, pictures, drawings, source tags); layout decides reading order, blocks, kinds and sections. When rewriting PDF extraction, the old `pdflayout.py` heuristics (columns, reading order, headings) belong to the layout issue, not to extraction. Types: sci2audio Issue #17 (PRs #20, #19).

### 2.1 Keep, remove, decide `[repo fact, 9 Nov 2026]`
| Keep (core) | Remove (hosted/cloud) | Decide during extraction |
|---|---|---|
| `analysis/` (20 detectors, 25 categories), `extractor.py`, `pdflayout.py`, `pdfdatei.py`, `epub.py`, `normalizer.py`, `sections.py`, `chunker.py`, `satzteilung.py`, `figures.py`, `abbildungen.py`, `kodierung.py`, `sprache.py`, `wortlisten.py`, `stolperwoerter.py`, `mitlesen.py` (read-along), `synchron.py`, `tts.py` (local providers only), `kokoro_sprecher.py`, `piper_lautschrift.py`, `cli.py` | `zahlung.py` (Stripe), account/admin/invite/uni/survey parts of `demo.py`, `einladungen.py`, `uni.py`, `studimail.py`, `umfrage.py`, `gefuehrter_test.py`, `admin.py`, `maschinen.py`, `ablage.py` (Tigris), `datenbank.py` (Postgres), `leerlauf.py`, `auslastung.py`, `legal.py` + `recht/`, `google_login.py`, `mail.py`, `benachrichtigung.py`, `vorhoeren.py`, Fly files (`fly.toml`, `deploy/`, `deploy.sh`), Azure/Edge/OpenAI/ElevenLabs providers, Anthropic rewriting (`rewriter.py`, `sprechfassung.py`, `prompts.py`) | `web.py` (7,245 lines): keep as the local UI, but strip all hosted routes; `bildmodell.py` (Apache 2.0, local) keep; `evaluator/`, `musterprobe.py`: keep only with own or openly licensed test texts |

### 2.2 Steps
| # | Step | Done when |
|---|---|---|
| 2.1 | Write `CLAUDE.md` for the new repo: goal (ADR-007), what's out of scope (no network calls, no paid APIs, no telemetry), glossary, test commands | File committed |
| 2.2 | Let a Claude thread produce a **dependency map**: which modules import the cloud parts; save as `docs/extraction-map.md` | Map reviewed |
| 2.3 | Create Issues per removal (one module or provider each, `lane:` labels); run them with the `ship-issue` skill; tests stay green after each | All removal Issues closed |
| 2.4 | Remove **third-party sample texts**: anything not written by Colin or not openly licensed (check `beispiele/`, `evaluator/`, test fixtures, the Musterproben set if present). Replace with own or CC BY/public-domain texts with attribution | `grep` for book titles/ISBNs is clean |
| 2.5 | Remove personal data from docs (operator address, phone, e-mail in the processing register and legal pages) | Nothing personal left |
| 2.6 | **Secret scan** before the first public push: run `gitleaks` (or similar) on the new tree; never publish the old history | Scan clean |
| 2.7 | New public repo `sci2audio` with a **fresh history** (one initial commit from the cleaned tree), `LICENSE` (GPL-3.0), `THIRD_PARTY_LICENSES.md`, `README.md` | Repo public |
| 2.8 | GitHub Actions: tests on Linux, macOS and Windows on every PR (free for public repos; Abogen's `test_pip.yml` with `uv` cache is a working template); branch protection on `main` (free for public repos) ; plus an end-to-end smoke test as in Audiblez: convert one openly licensed EPUB and one PDF and check the audio file exists; a dependency check (e.g. deptry) | CI green on 3 OS, smoke test passes |

## Phase 3: Refactor the core for a desktop app (weeks 4–6, ~30 h)

| # | Step | Done when |
|---|---|---|
| 3.1 | Split `web.py` into routers (files, analysis, runs, results, settings) with characterisation tests first; place logic in layers `domain/` / `application/` / `infrastructure/` with the UI on top (D-46, modelled on Abogen) | No file > 1,500 lines; tests green |
| 3.2 | Replace the job/thread handling meant for a server with a simple local job runner (one run at a time, pause/resume kept) ; render per chapter and skip finished chapters on a re-run (as Audiblez); measure speed on the first chapter for the time estimate (not a fixed rate) | Runs survive closing the window |
| 3.3 | Fix the pypdfium2 thread-safety issue with a module-level lock (`audit-pdfium-thread-crash.md`) | Concurrency test green |
| 3.4 | Settings in a local config file (output folder, voice, speed); no accounts | Settings persist |
| 3.5 | Keep the "KI-generiert / AI-generated" metadata label in every audio file (AI Act Art. 50 also covers open-source tools that are put on the market; it costs nothing) | Metadata test green |

> **UI and rule items from the commercial landscape (`06-open-source-landscape/audit-commercial-tts-and-text-rewriting-landscape-2026-11-09.md` §8):** K1 per-category toggles named as users know them from Audeus/Speechify (page furniture, headings, equations, footnotes and captions, tables, URLs/DOIs, citations, super/subscript, brackets); K3 section detection and picker; K7 one normalisation on/off/auto switch per document; K10 editable final script — all in the phase 3 UI work. K2 grammar-aware citation removal and K8 unit plural agreement go into the 4.0 English regression set.

## Phase 4: Voices and audio

> **Decided 10 Nov (D-48): PyTorch.** Step 4.1 verifies instead of choosing (speed without a GPU, install size, `PYTORCH_ENABLE_MPS_FALLBACK=1` set by the app); the misaki + ONNX and espeak-ng + ONNX paths are dropped. Text rules become plugins behind one interface (D-57, feature PE-10). (weeks 6–7, ~20 h)

| # | Step | Done when |
|---|---|---|
| 4.0 | **English regression test first:** turn the 14 cases of `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md` §4 into tests; fix the 7 English rule gaps listed there; add the English part of PolyNorm-Bench (licence permitting) and missing cases from the autiobooks fork and Kokoro-FastAPI rule sets (`06-open-source-landscape/audit-tts-and-text-rewriting-landscape-2026-11-09.md` L1–L3, L7) | Tests green; script re-run with `tools/english_check/compare.py` |
| 4.1 | **English first (D-50):** copy Abogen's Kokoro plugin and contract types into `sci2audio/voices/` (D-52, MIT notice kept); one-day spike on the M4: Kokoro PyTorch/MPS vs. misaki + `kokoro-onnx` (`is_phonemes=True`) vs. current espeak-ng + ONNX, speed per 1,000 words and a listening test; set `PYTORCH_ENABLE_MPS_FALLBACK=1`. Kokoro-82M English voices (Apache 2.0); optionally Piper voices trained from scratch on public-domain data (Linda, Kristin, Cori, Norman) | Engine chosen (D-48); two English voices work |
| 4.2 | **German (after English works end to end):** Kokoro German by Thorsten-Voice (Apache 2.0, CC0 data) through the same plugin; whether an ONNX export avoids shipping PyTorch | German voice works through the same interface |
| 4.3 | **Remove** Thorsten-Piper (lessac-based), all lessac/Ryan-derived voices, HFC, Edge, system-voice export | Not in the code |
| 4.4 | Models are **downloaded on first use** from their official Hugging Face repos into the user's cache, with the MODEL_CARD/licence shown in the app; nothing is bundled that the user didn't choose | First-run download works offline afterwards |
| 4.5 | Export MP3 (ffmpeg) and M4B with chapter marks; read-along stays | Listening test on 3 sample texts |
| 4.6 | Slim voice plugin contract for `tts.py` (engine, `synthesize()`, voice list) taken from Abogen's spec (D-46, D-52); Kokoro runs in-process (the separate `kokoro_sprecher.py` process existed only to keep espeak-ng's GPL apart from MIT code, obsolete under D-42) | Kokoro EN (and later DE) run through the same interface |

## Phase 5: Packaging and CI releases (weeks 7–9, ~30 h)

| Option | For whom | Cost | Note |
|---|---|---|---|
| `pipx install sci2audio` / `uv tool install sci2audio` | Technical users | €0 | Easiest first release (D-47); needs Python and ffmpeg/Tesseract installed. Abogen reached ~6,100 stars this way without a native installer |
| Briefcase (BeeWare) or PyInstaller installers built in GitHub Actions | Everyone | €0 | Windows SmartScreen and macOS Gatekeeper warn about unsigned apps; document the "open anyway" step |
| Code signing (Apple Developer Program, Windows certificate) | Polished releases | Yearly fees | Not needed for a learning project |

Steps: release workflow on tag (`v1.0.0`) builds the three artefacts and attaches them to a GitHub Release; checksums published; the app opens the local UI in the browser (existing `sci2audio ui` local mode) or in a small window shell later.

## Phase 6: Release and documentation (weeks 9–10, ~15 h)

- README with a 30-second demo GIF, one short listenable sample per voice (as Audiblez), install steps per OS, what the rules do (before/after specimen from an own text), privacy statement ("no data leaves your computer"), licence notes.
- `CONTRIBUTING.md`, issue templates, `CHANGELOG.md`, semantic versioning.
- Project site on sci2audio.com (GitHub Pages) linking to Releases.
- Blog post / case study: "Extracting and open-sourcing a 51k-line Python app with Claude" — the learning notes condensed.

## Phase 7: Optional after v1.0
- English rename of the codebase (ADR-004) with the `rename-area` skill: an ideal large-scale, test-protected exercise.
- Optional local LLM plugin (e.g. via Ollama) for a rewrite level; check each model's licence (Apache-licensed models are simplest).
- Android build later (F-Droid); no iOS (GPL vs. App Store terms).
- A new client in TypeScript (ADR-003) purely as a learning exercise.
- SRT/VTT subtitle export from the read-along data; cover art in M4B; EPUB 3 media overlays only if users ask (Abogen audit R8).
- Formulas: v1.0 skips them with a short spoken notice (D-55); speaking them via MathCAT comes here.
- Optional backends: Docling for hard PDFs; formulas via MathCAT (Rust + Python interface, preferred) or Speech Rule Engine (D-49, landscape L6).
- User pronunciation list in the W3C PLS format with regex entries, as DAISY Pipeline uses (landscape L4).
- Upstream contribution: German Kokoro plugin for Abogen (O-15) — the full open-source workflow (issue, fork, review, release) as a learning exercise.

## Legal checklist for the open-source app (all low-effort)
- [ ] GPL-3.0 licence and `THIRD_PARTY_LICENSES.md` (Kokoro, Thorsten-Voice, espeak-ng, Piper runtime if used, ffmpeg build, Tesseract, lamejs if the browser export stays, onnxruntime)
- [ ] Only freely licensed voices; MODEL_CARDs shown
- [ ] No third-party texts in the repo, tests or screenshots
- [ ] No network calls except user-initiated model downloads; no telemetry
- [ ] AI-generated label in audio metadata
- [ ] README note: users must only convert texts they may use (private copy); no DRM circumvention
- [ ] Short Impressum on the project website

## Advisor pre-analysis
- Phase 2 is the biggest and most instructive: deleting about half of a codebase safely is exactly the skill clients pay for. Do it in small, test-guarded Issues, never in one sweep.
- English comes first (D-50). Kokoro's English quality depends on misaki (Kokoro's English front end with spaCy inside); the current espeak-ng + ONNX path bypasses it. The 4.1 spike decides between PyTorch/MPS and misaki + ONNX.
- The German voice's size (PyTorch) is the main risk of 4.2; if it stays heavy, ship German Kokoro as an optional download.
- Keep scope small: v1.0 is "file in, faithful audiobook out, offline". Everything else waits for v1.1+.

## Critical open questions
| # | Question | Default |
|---|---|---|
| Q1 | New repo name `sci2audio` (public) and archive `audiobook-generator` (private)? | **Decided 10 Nov:** `dubidu22/sci2audio` created; `audiobook-generator` is a frozen reference (archive suggested) |
| Q2 | Keep the browser UI or add a window shell (pywebview/Tauri) in v1? | Browser UI in v1; never a second UI (D-45) |
| Q3 | Keep the design repo `sci2audio-design` as the home of the knowledge base? | Yes, until the public repo has `docs/` |
| Q4 | Accept unsigned installers for v1? | Yes, documented |
