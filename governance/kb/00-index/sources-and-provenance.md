# Sources and provenance

`[WORKING]` · Every source this KB draws on, with the date checked and how quickly it goes stale. Re-verify anything marked **fast** before acting on it if it's older than about 3 months.

---

## 1. Repository sources (read 8–9 Nov 2026)

### 1.1 `dubidu22/audiobook-generator` (private): code, main branch HEAD `35db2c1` on 8 Nov 2026

| File / source | Used for | KB files |
|---|---|---|
| Git history (`git log`, depth 400) and GitHub REST `pulls?state=all` | 540 commits and 305 PRs since 26 Oct; commits per day; merge latency; branch names `claude/project-thread-*`; 0 reviews | `audit-process-and-velocity.md` |
| GitHub REST `repos/…` | Repo created 2026-10-26T07:17Z; PR #1 on 2026-10-26T07:28Z; **0 Issues ever created** (the only open item the issues endpoint returns is PR #127 "Thorsten natürlicher: Pausen, Textregeln, eine Lautstärke je Stück, Nachbearbeitung"; GitHub lists PRs as issues); branch protection needs GitHub Pro (HTTP 403) | audits |
| `sci2audio/*.py`, `analysis/`, `evaluator/`, `eigenstimme/` | Line counts (51,131 in `sci2audio/*.py` top level; package total about 58.7k lines incl. subpackages), module inventory, docstrings, thread usage, queue design | audits, glossary, ADR-002 |
| `sci2audio/web.py` | 7,245 lines; 152 route decorators; `threading.Thread` at lines 1699, 2650, 3156, 3158, 3213, 3232, 4373, 4447, 6055; `SOLD_VOICES = (TTSProvider.AZURE, TTSProvider.AZURE_HD)` at line 129 | `audit-repo-state-2026-11-08.md`, ADR-002 |
| `sci2audio/static/` | `app.js` 4,579 lines, `bearbeiten.js` 2,979, `app.css` 3,062, `testleitfaden.js` 498, `geraetestimme.js` 438, `browserstimme-worker.js` 150, `browserstimme.js` 145, `i18n.js` 139 (11,990 total); 107 `innerHTML` writes and 64 `/api/` references in `app.js` | audit, ADR-003 |
| `sci2audio/auslastung.py` | `Gate` (halves parallel LLM calls 4→2→1 after HTTP 429, recovers after 8 clean calls), `RunQueue`, `Priority` (batches yield), patience 900 s (`SCI2AUDIO_RATENLIMIT_GEDULD`) | ADR-002 |
| `sci2audio/leerlauf.py`, `maschinen.py`, `docs/MEHRERE-MASCHINEN.md` | Idle stop after 10 min; heartbeat every 15 s; `konto_maschine` account-to-machine ownership; `fly-replay`; uploads >1 MB get 409 + re-send with `fly-force-instance-id`; files synced to Tigris after each run, every 5 min and before stop; 3 runs per machine, max 4 machines | ADR-002 |
| `sci2audio/pdfdatei.py` | `Page.__init__` calls `doc.raw[index]` (pypdfium2) with no lock | `audit-pdfium-thread-crash.md` |
| `sci2audio/datenbank.py` | Postgres URL or SQLite path; 30 `CREATE TABLE` statements (mixed German/English names) | glossary, audit |
| `sci2audio/sprachen/en/app.json` | 1,651 UI strings with English translations | glossary |
| `deploy.sh` | Gates: `leistungstest` → `musterprobe pruefen --leer-ok` → `synchrontest --leer-ok` → `fly deploy` (with `PAKETE_STAND=YYYY-MM`, `SCI2AUDIO_COMMIT`) → `rauchtest` → `leistungstest --referenz-uebernehmen`; `--trotzdem` override; rollback hint | audits, phase-0 playbook |
| `deploy/Dockerfile` | `FROM python:3.12-slim` (production Python version) | PDFium audit |
| `fly.toml` | App `sci2audio-demo`, region `fra`, `shared-cpu-1x` 2 GB, volume `daten` at `/data`, `kill_timeout = 120`, `auto_stop_machines = "off"`, `min_machines_running = 0`, concurrency soft limit 50, redirects from `sci2audio.colinmeng.de`, `www.sci2audio.com`, `sci2audio-demo.fly.dev` | audit, ADR-002 |
| `.github/workflows/sci2audio.yml` | CI turned off "until November 2026 (budget)"; `workflow_dispatch` only; matrix Python 3.10 + 3.12; installs ffmpeg; `pip install ".[dev,all]"`; pytest + 3 CLI smoke commands | audits |
| `pyproject.toml` | `requires-python >=3.10`; extras `openai`, `edge`, `elevenlabs`, `all` (fastapi, uvicorn, python-multipart, dkimpy, dnspython, piper-tts, azure-cognitiveservices-speech, kokoro-onnx, …), `dev` (pytest) | audits |
| `ROADMAP.md` (26 Oct 2026, 86 lines) | Phases 1–4, items 1–16, "deliberately not planned" list (incl. "Player mit Text-Hervorhebung und Live-Tempo: verworfen") | process audit, pillar 02 |
| `README.md` (765 lines, about 54 kB) | Pipeline description (extraction → sections → pre-analysis → chunking → rewriting → TTS) | pillar 02 |
| `docs/VORANALYSE.md` (243 lines) | Detector catalogue and architecture | pillar 02 |
| `docs/RECHTSLAGE.md` (126 lines, as of 29 Oct / 4 Nov 2026) | Four conditions for paid generation; voice licences; formalities; open items before money flows | pillar 04 |
| `docs/datenschutz/` (`README`, `avv-liste`, `dsfa-notiz`, `verarbeitungsverzeichnis`; as of 4 Nov 2026) | Processors, contracts, DPIA note, processing record | pillar 04 |
| `docs/DEMO-SERVER.md` (549 lines) | Fly setup, invite credit, Stripe top-up, e-mail login, uni advantage, notifications, Google login, account deletion | pillars 03–05 |
| `docs/EVALUATOR.md` (181 lines), `docs/MUSTERPROBEN.md` (75 lines) | Evaluation corpus and AI grader; sample PDFs on Colin's Mac in `~/.sci2audio/musterproben/` and for cloud threads in `/mnt/project-files/sci2audio/musterproben/` (19 samples) | pillar 02, toolkit playbook |
| `.claude/commands/eval-bewerten.md` | Only custom command in the repo; uses the Claude subscription via Claude Code | toolkit playbook |
| Full test run, Python 3.12.3, 9 Nov 2026 (this environment) | **1,279 tests: 1,274 passed, 1 failed, 4 skipped, 8 min 13 s**; failing: `tests/test_rechte.py::test_whole_book_needs_the_own_rights_declaration` (job didn't reach `fertig` within `_wait`'s 200 × 0.02 s = 4 s; also fails when run alone, 66 s) | audits, decision log |
| Test run, Python 3.13.18, 8 Nov 2026 (this environment) | Segmentation fault after about 800 tests; two threads in pypdfium2 (`web.py` prepare → `pdfdatei.py` `Page.__init__` / `chars`) | PDFium audit |

### 1.2 `dubidu22/sci2audio-design` (private), HEAD `5d7acb8` "Guided test: coordinator prompt and German tester guide"

| File | Used for |
|---|---|
| `docs/design/PRODUCT.md` (about 9.5 kB) | Platform "web", users, purpose, positioning, operating context, capabilities and constraints, prices (AI 10/35 ct, Azure +15, HD +25 ct per 1,000 words; standard voice free up to 50,000 words/month then 5 ct; about 8,000 words per audio hour; uni €5 + −20%; top-up bonus 10% from €25; 14-day money-back, max 2 claims/month) |
| `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) (about 23 kB; §1–§10) | Flows, states (§9), constraints (§10) |
| `docs/design/DESIGN.md` (about 47 kB) | Visual design system |
| `CRITIQUE-FINDINGS.md` (superseded, in the private design record), `REVIEW-FINDINGS.md` (superseded, in the private design record) | Two review rounds |
| `GUIDED-TEST-PROMPT.md` (superseded, in the private design record), `TESTANLEITUNG.md` (superseded, in the private design record) | Guided user test |
| `docs/design/IMPLEMENTATION-PROMPT.md` | Handoff to implementation |
| `prototype/` (vanilla HTML/JS: account, admin, compare, editor, local, player, quickstart, shared, site) | Reference implementation for the new client |
| `docs/design/design.json` (written with the `.impeccable` design skill, fork `dubidu22/impeccable`) | Design skill set in use |

### 1.3 Live site

| Source | Checked | Used for |
|---|---|---|
| https://sci2audio.com (WebFetch) | 2026-11-08 | Public claims: prices AI €0.08 / €0.15, Azure +€0.12 / +€0.20 per 1,000 words; 20% uni discount; everything free during test phase; e-mail code login; Azure + Anthropic as processors; server in Frankfurt; files deleted after 7 days by default; German and English UI. **Price conflict with `docs/design/PRODUCT.md`** (see pillar 03) |

## 2. External sources

| Source | Checked | Fact used | Staleness |
|---|---|---|---|
| Claude Code docs: Projects, https://code.claude.com/docs/en/claude-projects.md | 2026-11-09 | Projects in public beta on Pro/Max (not Team/Enterprise); cloud threads load root `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/` only; repo skills, agents, commands, `.mcp.json`, plugins from settings, permission rules, hooks and `env` not loaded; skills via claude.ai account; plugins via Project settings → Plugins; connectors from claude.ai; project instructions up to 16,000 characters; project memory `MEMORY.md`; threads auto-fix PRs; a project belongs to one user; draws on plan limits faster | **fast** (beta) |
| Claude Code docs: Cloud environments, `…/cloud-environments.md` | 2026-11-09 | Non-project cloud sessions *do* load repo `.claude/skills`, agents, commands, hooks and `.mcp.json` (single repo); plugins in repo settings not installed; setup scripts; network secrets | fast |
| Claude Code docs: Scheduled tasks (formerly routines), `…/routines.md` | 2026-11-09 | Research preview; Pro/Max/Team/Enterprise; triggers: schedule, API (`/fire`, bearer token), GitHub events; per-account hourly caps; runs act as the user; outside project threads, repo skills load | **fast** (preview) |
| Claude Code docs: Code Review, `…/code-review.md` | 2026-11-09 | Managed review service is **Team/Enterprise only**; `/code-review` works on any plan; ultrareview needs a claude.ai account; GitHub Action as alternative | fast |
| Claude Code docs: Local code review, `…/code-review-local.md` | 2026-11-09 | `/code-review [target] [--fix] [--comment] [--max-findings]`; runs as a background subagent; `/review` alias; `ultra` escalation | fast |
| Claude Code docs: GitHub Actions, `…/github-actions.md` | 2026-11-09 | `claude-code-action@v1`; auth via `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (Pro/Max/Team/Enterprise, `claude setup-token`); consumes Actions minutes | medium |
| Claude Code docs: Skills, `…/skills.md` | 2026-11-09 | `SKILL.md` + frontmatter; project `.claude/skills/` vs. personal `~/.claude/skills/`; commands merged into skills; bundled skills (`/code-review`, `/verify`, `/simplify`, `/batch`, `/debug`, `/loop`, …) | medium |
| Claude Code docs: Plugins overview and install, `…/plugins/overview.md`, `…/plugins/install.md` | 2026-11-09 | Plugins bundle skills, agents, hooks, MCP; official marketplace `claude-plugins-official` added automatically; scopes user/project/local; each enabled plugin costs context every turn; cloud sessions don't load locally installed plugins | medium |
| `anthropics/claude-plugins-official` (git clone) | 2026-11-09 | Plugin names: `feature-dev`, `code-review`, `pr-review-toolkit`, `security-guidance`, `code-simplifier`, `claude-md-management`, `hookify`, `code-modernization`, `frontend-design`, `pyright-lsp`, `typescript-lsp`, `claude-security`, `session-report`, `claude-code-setup`, `skill-creator`, …; external: `playwright`, `context7`, `github`, …; marketplace lists `superpowers` | medium |
| `obra/superpowers` (GitHub) | 2026-11-09 | About 314.7k stars; MIT; skills brainstorming, writing-plans, executing-plans, test-driven-development, systematic-debugging, verification-before-completion, requesting/receiving-code-review, using-git-worktrees, finishing-a-development-branch, subagent-driven-development | medium |
| Apple external purchase rules: TechCrunch (2 May 2025), 9to5Mac, iClarified (Dec 2025), FKKS (30 Apr 2025 injunction), Dodo Payments 2026 overview, stora.sh (May 2026) | 2026-11-08 | Digital goods in iOS apps generally need IAP; US: court-ordered external links (history of 27%/12% commission, injunction 30 Apr 2025, appeals); EU: DMA alternative terms / external purchase entitlement with own fees; rules changed repeatedly since 2025 | **very fast**: re-verify before phase 4 |
| GitHub plans (branch protection on private repos needs Pro; Free = 2,000 Actions minutes/month for private repos) | 2026-11-08 (API 403 message + general knowledge) | Branch protection cost; CI budget estimate | medium; verify price before buying |
| Kleinunternehmerregelung 2025/26: Finanzamt BW, IHK Erfurt, service.berlin.de, selbststaendigkeit.de, mehrwertsteuerrechner.de, der-betrieb.de | 2026-11-09 | § 19 UStG € 25,000 previous year / € 100,000 current year (hard limit, immediate loss); § 19a EU small-business scheme via BZSt since 2025 | medium (law stable since 2025) |
| Unternehmenseinheit and separate Gewerbebetriebe: steuer-berater.de, steuerschroeder.de (BFH X R 8/23, 28 Jan 2026), deubner-steuern.de, rechtslupe.de | 2026-11-09 | Several activities of one person = one business for VAT (combined € limits); for trade tax several Betriebe with own € 24,500 allowance if not connected | medium |
| EU B2C e-services threshold: IHK Berlin/Stuttgart/Rhein-Neckar, Handelskammer Hamburg, accountable.de, steuerschroeder.de; BMF 14 Dec 2018; Art. 24b MwSt-DVO | 2026-11-09 | € 10,000 EU-wide (previous and current year) keeps place of supply in DE; above it customer's state; one piece of location evidence below € 100,000 | medium |
| Reverse charge for Kleinunternehmer: Lexware, norman.finance, accountable.de, steuerberater-tabak.com, selbststaendigkeit.de | 2026-11-09 | § 13b: Kleinunternehmer owes 19% on foreign B2B services, no deduction, files pre-returns; USt-IdNr needed for net EU invoices | medium |
| Vouchers: BFH XI R 14/24 (25 Jun 2025) via ecovis, KPMG, taxandbytes | 2026-11-09 | Single- vs multi-purpose voucher decided at issue; digital credit cards treated as single-purpose | medium |
| BEG IV retention: IHK Karlsruhe, IHK Konstanz, Lexware, steuer-berater.de | 2026-11-09 | Buchungsbelege 8 years from 1 Jan 2025 (§ 147 AO, § 257 HGB) | stable |
| Widerruf digital content/services: wettbewerbszentrale.de, it-recht-kanzlei.de, haufe.de, heuking.de, iww.de, gesetze.legal, nwb (excerpt) | 2026-11-09 | § 356 Abs. 5 (digital content: express consent, acknowledgement, § 312f confirmation); services: consent + acknowledgement, ends at full performance; LG Köln 31 O 372/17 (combined notice insufficient); § 356 numbering possibly changed in 2026 | **verify numbering** |
| Widerrufsbutton § 356a: IHK Osnabrück/Erfurt/Ulm/Hanau/Rheinhessen, fieldfisher, heuking, datenschutz-generator, Bitkom guide | 2026-11-09 | Mandatory since 19 Jun 2026 for online B2C contracts with a withdrawal right, incl. digital content and services; two steps; e-mail receipt with content, date and time | stable |
| BFSG micro-enterprise exemption: IHK Nürnberg/Berlin, Händlerbund, cms.law, xictron | 2026-11-09 | Services (incl. e-commerce) exempt for < 10 employees and ≤ € 2 M turnover/balance; not for products; documentation advised | medium |
| AI Act Art. 50 after the Digital Omnibus: cookiebot, iubenda, McCann FitzGerald, dastra, CSA, usercentrics | 2026-11-09 | Omnibus in force 27 Jul 2026; Art. 50 applies from 2 Aug 2026; 50(2) marking grace to 2 Dec 2026 only for systems already on the market | medium |
| Gewerbeummeldung: Stadt Köln, hamburg.de, Berlin FIM, München, service-bw (Heidelberg) | 2026-11-09 | Extension of activity requires Ummeldung at the time of change; fees about € 15–40; late notice → warning fee/fine | stable |
| Voice licences: HF model cards (rhasspy/piper-voices Thorsten medium, lessac), Thorsten-Voice/Kokoro, hexgrad/Kokoro-82M, kikiri/HUI German Kokoro bundles | 2026-11-09 | Thorsten medium fine-tuned from lessac (Blizzard 2013 research-only); German Kokoro by Thorsten-Voice Apache 2.0 on CC0 data; Kokoro-82M Apache 2.0 with GPLv3 espeak-ng dependency | medium |
| Azure TTS terms: Microsoft Learn (Code of Conduct, data/privacy page, Q&A on output rights and F0) | 2026-11-09 | Commercial output rights for prebuilt voices on the paid tier only; disclosure; no training of TTS on output; prebuilt input/output not logged | medium |
| Edge TTS: Microsoft Q&A; Firefox add-on developer note (17 Dec 2025 block) | 2026-11-09 | Not licensed commercially; Microsoft recommends Azure | stable |
| Anthropic retention: privacy.claude.com (commercial API), developersdigest summary | 2026-11-09 | API inputs/outputs deleted within 30 days (exceptions); Covered Models require 30-day retention; no training on API data | fast-moving |
| Fly.io DPA/transfers: community.fly.io, third-party summaries | 2026-11-09 | DPA available on request/dashboard; SCC; US-company transfer concerns | verify when filing |
| Legal research artifact "Bezahlt vertonen, aber rechtssicher" (`GPC5mpcFj1Ho2v7C1AvNhC`) | 2026-10-29 (read 2026-11-09) | Copyright analysis, case law, DSA, consumer law, lawyer questions | as of its date |
| Students with impairments: Deutsches Studierendenwerk (22. Sozialerhebung, best3 pages), DZHW press release 4 Dec 2023, Uni Trier | 2026-11-09 | 16% of students with study-impairing health conditions (2021; 11% in 2016); 65% psychological; text-to-speech/"Hörmedien" as aids for dyslexia; funding via integration assistance possible | slow (survey cycles) |
| Competitors: Speechify pricing (casrai, Aug 2026; omidsaffari, Aug 2026), ElevenReader (audeus; mydealz student offer Nov 2026), Listening.com (audeus, alternativeto, own blog), Paper2Audio (Capterra), NotebookLM Audio Overviews in German (heise, Google blog, 2025) | 2026-11-09 | Speechify $29/month or $139/year, 50% student discount; ElevenReader free 10 h/month and 12 months Ultra free for students (reported); Listening no permanent free tier, 7-day trial; NotebookLM summaries in 50+ languages | **fast-moving**: re-check before using in copy |
| GitHub repository pages of 17 similar projects (ebook2audiobook, Audiblez, Abogen, epub_to_audiobook, kokoro-tts, epub2tts, Audiobook Creator, Speech Note, OpenReader WebUI, Docling, Marker, GROBID, Speech Rule Engine, MathReader, Paper Voice, Open Notebook, Podcastfy); links in the landscape audit | 2026-11-09 | Stars, licences, features, languages, packaging | **fast-moving**: re-check after ~3 months |
| Vendor pages, docs, app-store pages and 2025–2026 reviews of ~60 commercial products (reader apps, paper apps, TTS platforms, assistive/math tools, AI narration, PDF services); listed in the commercial landscape audit | 2026-11-09 | Prices, skipping features, normalisation classes, lexicon formats, German support, privacy | **fast-moving**: re-check before quoting prices |
| GitHub, Hugging Face and arXiv pages of ~70 projects (three parallel research passes): reader apps, rule-based normalisation, formula speech, AI rewriting, PDF clean-up, datasets; links in the landscape audit | 2026-11-09 | Stars, licences, approach, German support | **fast-moving**: re-check after ~3 months |
| Audiblez repository cloned (`santinic/audiblez`, commit `788a6a8`, 27 Feb 2026) and Colin's screenshot of its window (9 Nov) | 2026-11-09 | Text preparation loop, chapter detection, fixed speed estimate, CI smoke test, activity | as of that commit |
| Abogen repository cloned (`denizsafak/abogen`, commit `1807822`, 1 Nov 2026) | 2026-11-09 | Code structure, PDF parser, normaliser, plugin spec, CI, releases, contributors | as of that commit |
| Hugging Face `Thorsten-Voice/Kokoro` model card | 2026-11-09 | German Kokoro fine-tune, Apache-2.0, CC0 data, needs German forks of `misaki`/`kokoro` and espeak-ng | medium |
| Test run in the session: spaCy 3.8.18, `en_core_web_sm` 3.8.0 (MIT per metadata), misaki English G2P, `kokoro-onnx` 0.6.1 source; sci2audio English path at `35db2c1` | 2026-11-09 | 14-case comparison, homograph tags, NER noise, `create(…, is_phonemes=True)` | re-run with `02-product-and-pipeline/tools/english_check/compare.py` |
| Colin's Abogen run on a MacBook Pro M4 (screenshot of the desktop app, web-UI log) | 2026-11-09 | Speed (~8 min audio in ~30 s), PDF artefacts, URL spelling, MPS fallback error | as of that run |

## 3. Claims not yet verified (treat as assumptions)

| Claim | Where used | How to verify |
|---|---|---|
| CI run ≈ 8 min per PR on GitHub runners | Lean-CI budget (≈ 320 min/month) | Local full suite took 8 min 13 s here; measure the first real CI run |
| GitHub Pro ≈ $4/month | Decision O-01 | GitHub pricing page at purchase |
| Fly staging app cost "small when stopped" | Phase 0 | Fly pricing page; first month's invoice |
| Bundled `/code-review` available inside Project cloud threads | Toolkit playbook | Run `/code-review` once in a thread |
| `pyright-lsp` works in cloud threads if Pyright is installed by the setup script | Toolkit playbook | Add to setup script; test with a rename |
| GitHub GraphQL blocked in Project threads as in this session | Skills use REST | First `/triage` run in a thread |
| The failing `test_rechte.py` test is a real regression vs. a too-tight 4 s timeout on slower machines | Decision O-09 | Run on Colin's Mac; inspect the job's phase and log |
| 90-day funnel targets (300 signups, 30 first paid runs, 20 paying) | `playbook-launch-and-channels.md` §5 | First 90 days of L1 data |
| Piper MLS German speakers are good enough as the free German voice | D-36 | MLS spike in L0 (listen test with 5 testers) |
| 60-second Azure sample costs ≈ 1.4 ct | Launch §2.1 | First month's Azure invoice / run_stats |
| Kleinunternehmer can't usefully combine OSS with § 19 at home (tax treatment above € 10,000 EU B2C) | Tax playbook §4 | Tax adviser T03 |
