# Audit: repository state, 8–9 Nov 2026

`[AUDIT]` · Snapshot of `dubidu22/audiobook-generator` (HEAD `35db2c1`, 8 Nov 2026 20:41) and `dubidu22/sci2audio-design` (HEAD `5d7acb8`). All numbers are `[repo fact]` unless labelled otherwise. Don't edit numbers later; re-audit into a new dated file.

---

## 1. Verdict

- **Core: strong.** The processing pipeline, 20 statistical detectors (docs still say 13), the test suite, the sample-PDF regression set, the deploy gates and the privacy documentation are well above typical for a 2-week-old codebase.
- **Edges: debt.** One 7,245-line web module mixes HTML pages, a JSON API, auth, admin, the guided test and job execution (threads). The front end is 12k lines of hand-written JS that writes HTML via `innerHTML`, and some HTML is assembled in Python strings. Naming is German throughout.
- **Safety net: present but unused.** 1,279 tests exist, but nothing runs them automatically, and `main` is currently **red** (1 failing test).
- **Blocks the roadmap:** no API boundary, so no native apps; jobs inside the web process, so deploys interrupt runs and thread-safety bugs are possible.
- **Overall:** evolve the core, re-architect the web layer, rebuild the client (ADR-001).

## 2. Size and shape

| Metric | Value | Note |
|---|---|---|
| Repo created | 2026-10-26 07:17 UTC | PR #1 at 07:28 UTC the same day |
| Python, `sci2audio/*.py` (top level) | 51,131 lines | about 58.7k incl. `analysis/`, `evaluator/`, `eigenstimme/` |
| `analysis/` | 27 modules, 4,350 lines | The pre-analysis (detectors, routing, report) |
| Largest modules | `web.py` 7,245 · `tts.py` 2,914 · `extractor.py` 2,280 · `demo.py` 2,148 · `cli.py` 1,710 · `pdflayout.py` 1,660 · `protokoll.py` 1,630 · `normalizer.py` 1,437 · `admin.py` 1,353 · `diffview.py` 1,267 · `sprechfassung.py` 1,153 · `bearbeitung.py` 1,048 · `routing.py` 1,025 | `web.py` alone is 14% of the top-level Python |
| `web.py` internals | 152 route decorators, 444 functions, Pydantic request models, 9 `threading.Thread` start sites | Mixed responsibilities (section 4) |
| Front end (`sci2audio/static/`) | 11,990 lines: `app.js` 4,579, `app.css` 3,062, `bearbeiten.js` 2,979, `testleitfaden.js` 498, `geraetestimme.js` 438, `browserstimme-worker.js` 150, `browserstimme.js` 145, `i18n.js` 139 | Vanilla JS, no framework, no build step; 107 `innerHTML` writes and 64 `/api/` calls in `app.js` |
| HTML in Python | `startseite.py` (38 tag literals), `admin.py` (49), `web.py` (3), plus `web_page.html`, `demo_login.html` | Server-rendered pages assembled in Python strings |
| Tests | 121 `test_*.py` files, 24,223 lines; **1,279 tests collected** | `conftest.py`, `llm_fakes.py` (fake LLM), sample texts |
| UI strings | 1,651 German → English pairs in `sprachen/en/app.json` | i18n keyed by the German string |
| Environment variables | 110 distinct `SCI2AUDIO_*` names | Configuration surface |
| Database | 30 tables via `CREATE TABLE IF NOT EXISTS` in code; Postgres (Neon) or SQLite | No migration tool; schema created in code |
| Docs | `README.md` 765 lines (about 54 kB), `ROADMAP.md` 86, `docs/DEMO-SERVER.md` 549, `docs/VORANALYSE.md` 243, `docs/EVALUATOR.md` 181, `docs/RECHTSLAGE.md` 126, `docs/MUSTERPROBEN.md` 75, `docs/MEHRERE-MASCHINEN.md` 72, `docs/datenschutz/` 4 files | Extensive, German |
| Python | `requires-python >=3.10`; production image `python:3.12-slim` | CI matrix (disabled) 3.10 + 3.12 |
| Licence | MIT; deliberately no AGPL/GPL imports (PyMuPDF and EbookLib avoided; Piper phonemizer isolated in `piper_lautschrift.py` as a separate GPL-3 program) | See pillar 04 |

## 3. Test suite health (measured 9 Nov 2026)

| Run | Result | Duration |
|---|---|---|
| Python 3.12.3 (= production), full suite, `pip install -e ".[dev,all]"` | **1 failed, 1,274 passed, 4 skipped**, 2 warnings | 8 min 13 s |
| Same failing file alone (`tests/test_rechte.py`) | 1 failed, 8 passed | 66 s |
| Python 3.13.18, full suite (8 Nov) | **Segmentation fault** after about 800 tests in pypdfium2 | about 3.5 min until crash |
| Python 3.13, with only `.[dev]` installed | 44 collection errors (`fastapi` missing) | Expected: the suite needs `.[dev,all]` |

**Failing test:** `tests/test_rechte.py::test_whole_book_needs_the_own_rights_declaration`
- Assertions before the failure pass: the rights light is `rot` for a whole book; the order is refused with HTTP 400 mentioning `§ 53 Abs. 4`; the estimate shows `gelb` for an excerpt.
- It fails at `_wait(client, job_id)["phase"] == "fertig"`: the helper polls `/api/auftrag/{id}` 200 times × 0.02 s (**4 s total**) and raises "Auftrag wurde nicht fertig".
- Reproducible in isolation. **Unknown** whether it's a real regression (the job hangs or ends in another phase) or a timing assumption too tight for slower machines. Either way, `main` is red and nobody noticed, which is the core process finding.
- Warnings: Starlette `TestClient` per-request cookies deprecated (`tests/test_inhalte.py`, 2×). Harmless today; breaks on a future Starlette upgrade.

**Crash on 3.13** (details in `audit-pdfium-thread-crash.md`): not reproduced on 3.12, but the code has no lock around pypdfium2, which isn't thread-safe. Treat it as a latent production risk, not a 3.13-only issue.

## 4. Layer-by-layer audit

| Layer | Modules | What's good | Debt / risk | Verdict |
|---|---|---|---|---|
| **PDF and document reading** | `extractor.py`, `pdflayout.py` (own layout detection: columns, headings, footnotes, tables), `pdfdatei.py` (pypdfium2 wrapper, no AGPL), `kodierung.py` (broken font encodings, OCR glyph learning), `epub.py`, `sections.py`, `figures.py`, `bildmodell.py` (optional PP-DocLayoutV2 via onnxruntime, local only), `verkleinern.py`, Tesseract for scans | Deep handling of real-world PDFs; licence-clean; tested by sample PDFs (`musterprobe`, 19 samples) | pypdfium2 access isn't serialised (crash risk); layout model 0.3–0.9 s and 0.5 GB per page, so it can't run online | **Keep**; add the lock now; run in the worker later |
| **Pre-analysis (Voranalyse)** | `analysis/` (27 modules: abbreviations, capitals, categories, citations, decisions, figures, footnotes, foreign words, gender, headings, homographs, hyphenation, layout, links, markup, names, numbers, passages, publisher, render, report, sentences, structures, garbled text), `prefilter.py`, `foreign.py`, `stolperwoerter.py`, `wortlisten.py` | The product's differentiator; each rule has a test and an example sentence (`tests/sample_voranalyse_de.md`); re-check after AI rewrite (`NAME.nachpruefung.md`) | German-first rules; English rules partial (roadmap item 12) | **Keep and extend** (pillar 02) |
| **Routing and AI rewriting** | `routing.py` (three classes: no AI / sentence smoothing → Haiku / understanding needed → Sonnet), `chunker.py` (600–800 words, sentence-safe, read-only context of 2–3 previous sentences), `rewriter.py` (tenacity retries, `retry-after`, JSON checkpoint per chunk), `prompts.py`, `sprechfassung.py`, `calibration.py`, `costs.py`, `health.py` (tiny pre-flight call), `auslastung.py` (429 gate, run queue, batch priority) | Cost-aware: only paragraphs that need AI go to a model (54% of the sample PDF needs none); checkpoints make runs resumable; careful rate-limit handling | Rate limits are process-local (one `Gate` per machine), not global across 4 machines; roadmap item 3 (`--max-kosten` hard cap) still open | **Keep**; move into the worker; make limits global in phase 2 |
| **TTS and audio** | `tts.py` (Azure, Edge (tests/CLI only), OpenAI, ElevenLabs; parallel segments, retry, cache), `browserstimme.py` (Piper ONNX in the visitor's browser), `geraetestimme.py` (Web Speech API), `systemstimme.py`, `zweitstimme.py`, `quellenstimme.py`, `kokoro_sprecher.py`, `piper_lautschrift.py` (GPL-3 separate program), `modellstimmen.py`, `piperstimmen.py`, `kokorostimmen.py`, `laenge.py` (length guard per voiced segment); audio encoding via ffmpeg (MP3, M4B with chapters and cover, Opus) | Clever split: free voices run client-side, so the server pays nothing for audio | Voice licensing open before sale (Thorsten; see pillar 04); segment cache not content-hashed yet (roadmap item 15) | **Keep**; licensing work in pillar 04 |
| **Read-along and timing** | `mitlesen.py`, `synchron.py` (sync test at the audio), `satzliste.py`, `satzteilung.py`, `timing.py`, `zeitlinie` tests | Sample-accurate sentence starts; verified by `synchrontest` in `deploy.sh` | Shipped although `ROADMAP.md` lists "Player mit Text-Hervorhebung … verworfen" (process finding) | **Keep** |
| **Web server and API** | `web.py` (7,245 lines, 152 routes): HTML pages, `/api/…` JSON, login (e-mail code, Google), credit, invites, admin, guided test, run start, files, player data | FastAPI + Pydantic models already in place; tested via `TestClient` | No API boundary or versioning; pages and JSON mixed; cookie sessions only (apps need tokens); German routes (`/anmelden`, `/api/auftrag/{id}`); jobs started as threads (`web.py` lines 3156/3158) | **Split** into `/api/v1` + page routes + worker (ADR-002) |
| **Jobs and scaling** | Threads in the web process; `auslastung.RunQueue`; `maschinen.py` (0–4 Fly machines, heartbeat 15 s, `konto_maschine` ownership, `fly-replay`, 409 + `fly-force-instance-id` for uploads >1 MB); `leerlauf.py` (self-stop after 10 min idle); `ablage.py` (Tigris sync after each run, every 5 min, before stop); `kill_timeout = 120` | Works on one machine and scales to 4 without a queue service; crashed runs resume like after a restart | Each account is pinned to a machine, so scaling is per account; deploys restart the process and interrupt running jobs (they resume, but the user waits); thread-safety bugs possible (PDFium) | **Replace** with Postgres job queue + worker processes (ADR-002) |
| **Accounts, credit, payments** | `demo.py` (2,148 lines: accounts, sessions, login codes, `login_fehler` rate limit), `zahlung.py` (Stripe Checkout + webhook without the Stripe library; Stripe fee absorbed, § 270a BGB), `belege` (receipts page), `einladungen.py`, `uni.py`, `studimail.py`, `vorhoeren.py` (fair use), `admin.py` | Prepaid wallet in whole cents; webhook events de-duplicated via `stripe_events` (`handle_event`: "safe to receive twice"); login-failure rate limit; test vs. sales mode switch | `risk:high` code without review history; module name `demo.py` hides that it's the account system | **Keep logic**; move behind `/api/v1`; review before paid launch |
| **Front end** | `static/app.js`, `bearbeiten.js` (editor), `app.css`, `i18n.js`, voice workers; server-rendered pages | Works on phone and desktop; read-along player; editor with split screen | No component model; HTML built via `innerHTML` (107×), so escaping depends on discipline (XSS review needed); design spec in `sci2audio-design` not implemented 1:1 | **Replace** with the new client (ADR-003) |
| **Public site and content** | `startseite.py`, `inhalte.py`, `inhalte/de|en/*.html` (6 articles each: FAQ, voices compared, footnotes/citations, PDF read aloud for studies, editing yourself, scientific texts as audiobook), sitemap, robots, hreflang | SEO basics present; bilingual | Assembled in Python strings | **Keep server-rendered**; restyle to the design system |
| **Legal texts and privacy** | `legal.py`, `recht/` (+ `recht/en/`), `rechte.py` (rights traffic light), `docs/datenschutz/` | Unusually complete for the stage: processing record, processor list, DPIA note, consent flow for AI/Azure, retention | Processor contracts not yet filed as PDFs (`avv-liste.md` checkboxes); lawyer review open | Pillar 04 |
| **Evaluation and quality tooling** | `evaluator/` (corpus of 10–20-page chapters, fixed checks, regressions from the audit report, AI grader via Claude subscription `/eval-bewerten`), `musterprobe.py`, `leistung.py` (performance test with reference), `rauchtest.py`, `gap.py` (`luecke`), `ttsbench.py`, `speedtest.py`, `protokoll.py` (local run logs) | A real measurement culture: sample PDFs, performance reference, smoke test, AI grader | Not wired into CI; `/eval-bewerten` invisible to Project threads (commands in `.claude/` aren't loaded) | **Keep**; wire into nightly scheduled task |
| **Voice training** | `eigenstimme/` (recording page on 127.0.0.1, dataset ZIP, takes checker, Piper training recipe from random weights on CC0 Thorsten data) | Path to a licence-clean German voice | Not trained yet ("GPU rental after approval") | Pillar 04 (voice licensing) |
| **Deployment** | `deploy.sh`, `fly.toml`, `deploy/Dockerfile` (`python:3.12-slim`), `deploy/docker-compose.yml`, `Caddyfile`, `start.sh` | Gated deploy: performance test → sample PDFs → sync test → `fly deploy` (monthly fresh packages via `PAKETE_STAND`, commit as app version) → smoke test → new reference; `--trotzdem` override; rollback hint | **pytest isn't a gate**; deploys from a laptop straight to production; no staging; no tags or releases | **Keep and extend** (phase 0) |
| **CI** | `.github/workflows/sci2audio.yml` | Correct content (ffmpeg, `.[dev,all]`, pytest, 3 CLI smoke commands) | **Disabled** since late Oct ("until November 2026, budget"); `workflow_dispatch` only; 2-version matrix | **Re-enable lean** (phase 0) |
| **Observability** | Python `logging`; Fly logs; `rauchtest`; `health.py` (API key pre-flight, not an HTTP health endpoint) | — | No error tracking, no uptime monitor, no cost alerting, no `/health` endpoint for monitors | Add in phase 0 |
| **Backups** | `docs/DEMO-SERVER.md` § Sicherung: `docker compose cp …/demo.sqlite` (self-hosted variant B only) | — | No documented backup or restore for the Fly + Neon Postgres + Tigris setup | Add and test in phase 0 |
| **Code quality tooling** | — | — | No linter/formatter config (ruff, black), no type checker (mypy/pyright), no pre-commit hooks | Add ruff + pyright gradually (phase 1, rename is a good moment) |
| **Agent context** | `.claude/commands/eval-bewerten.md` only | — | No `CLAUDE.md`/`AGENTS.md` in either repo; the 54 kB README is the only orientation for each session | Add `CLAUDE.md` + `.claude/rules/` (phase 0) |

## 5. Technical debt register

| ID | Debt | Impact | Effort | Fix in |
|---|---|---|---|---|
| TD-01 | `main` red: `test_rechte.py` failing, unnoticed | Merges and deploys on an unknown state | S | Phase 0, week 1 (P0) |
| TD-02 | pytest not part of `deploy.sh`, CI off | Regressions reach production | S | Phase 0, week 1 |
| TD-03 | pypdfium2 used from several threads without a lock | Possible process crash under concurrent uploads | S (lock) / M (worker) | Phase 0 (lock), phase 2 (worker) |
| TD-04 | Jobs as threads in the web process | Deploy interrupts runs; one bad job can take the web server down; no global limits | L | Phase 2 |
| TD-05 | `web.py` monolith (pages + API + auth + admin + jobs) | Every change touches the riskiest file; parallel threads collide here | L | Phase 2 |
| TD-06 | No versioned API, cookie-only auth | Native apps impossible | M | Phase 2 |
| TD-07 | Vanilla JS with `innerHTML` (107×) | XSS risk depends on discipline; hard to extend; design spec not implementable cleanly | L | Phase 3 (replace) |
| TD-08 | German identifiers, routes, env vars, tables | Friction for English API and client code; mixed-language codebase | M | Phase 1 (code), later (stored names) |
| TD-09 | Schema created in code, no migrations | Risky schema changes once real data exists | M | Phase 2 (introduce migrations, e.g. Alembic or plain numbered SQL) |
| TD-10 | Rate-limit gate per process, not global | 4 machines × 4 parallel calls can exceed provider limits | M | Phase 2 (global limiter in Postgres) |
| TD-11 | No error tracking, uptime, cost alerts | Failures and cost spikes discovered by users or invoices | S | Phase 0 |
| TD-12 | No backup/restore procedure for Postgres + Tigris | Data loss unrecoverable | S | Phase 0 |
| TD-13 | No staging environment | Production is the first test | S | Phase 0 |
| TD-14 | No lint/format/type-check tooling | Style drift across 300+ AI-authored PRs | S–M | Phase 1 |
| TD-15 | `ROADMAP.md` stale after 2 weeks | Priorities set per session, not by the owner | S | Phase 0 (rewrite as Now/Next/Later + milestones) |
| TD-16 | `demo.py` name hides the account and session system | Misleading for every reader and agent | S | Phase 1 rename (`accounts.py`) |
| TD-17 | Price lists inconsistent (live site vs. `docs/design/PRODUCT.md`) | Wrong charges or copy at launch | S | Pillar 03 |
| TD-18 | Starlette per-request cookie deprecation in tests | Future upgrade breaks tests | S | Phase 1 |
| TD-19 | Processor contracts not filed (`avv-liste.md` boxes unchecked) | GDPR documentation gap | S | Pillar 04, before paid launch |
| TD-20 | Thorsten voice licence unresolved for sale | Standard voice can't be sold (already excluded in sales mode via `SOLD_VOICES`) | M–L | Pillar 04 |

Effort: S = under 1 day, M = 1–5 days, L = more than 5 days of Claude-thread work plus review.

## 6. Strengths to preserve (don't lose these in any refactor)

1. **1,279 tests** with an LLM fake (`llm_fakes.py`). The behaviour spec for every refactor.
2. **Sample PDFs (`musterprobe`, 19 cases incl. cloud copy)**: real-world reading regressions; known-wrong cases tracked as `bekannt`.
3. **Deploy gates** (`deploy.sh`): performance reference, sample PDFs, sync test, smoke test, explicit `--trotzdem`, rollback hint, monthly fresh packages.
4. **Cost discipline** in the pipeline: "rules first, AI second"; routing per paragraph; real cost recorded after each run; calibration.
5. **Licence hygiene**: no AGPL; GPL parts isolated; model cards shipped; `SOLD_VOICES` restricts sale-mode voices.
6. **Privacy documentation**: processing record, processor list, DPIA note, consent, retention, account deletion with sharing revocation.
7. **Evaluator**: corpus + fixed checks + AI grader on subscription (zero API cost).
8. **Scaling design** for a solo budget: 0–4 machines, idle self-stop, Neon sleeping Postgres.

## 7. Gap analysis: current vs. target (summary)

| Capability | Today | Target | Gap closes in |
|---|---|---|---|
| Automated verification on every change | None (CI off, pytest not in deploy) | pytest + smoke on every PR; full checks nightly; pytest in `deploy.sh` | Phase 0 |
| Code review | 0 reviews on 305 PRs | Scheduled-task review on PR open; `risk:high` needs explicit review | Phase 0 |
| Environments | Laptop → production | Local → staging → production | Phase 0 |
| Releases | Untagged deploys | Tagged releases with generated notes | Phase 0 |
| Job execution | Threads in web process | Postgres queue + worker processes | Phase 2 |
| API | Mixed `/api/…`, unversioned, cookies | `/api/v1`, OpenAPI, tokens + cookies | Phase 2 |
| Client | Vanilla JS, not matching the design spec | TypeScript client from `sci2audio-design`, shared tokens | Phase 3 |
| Mobile | Responsive web | Listening app (iOS/Android) | Phase 4 |
| Naming | German | English code; German UI first; stored names unchanged | Phase 1 |
| Observability | Logs only | Error tracking, uptime, cost alerts, 5 weekly metrics | Phase 0 |
| Data safety | No restore procedure | Documented, tested quarterly | Phase 0 |
