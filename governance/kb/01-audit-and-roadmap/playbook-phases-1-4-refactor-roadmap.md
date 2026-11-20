# Playbook: phases 1–4, refactoring roadmap

`[PLAYBOOK]` · Sequence after phase 0: **1 English names → 2 worker + API → 3 new web client → 4 listening app.** Each phase ships on its own and ends at a gate. Decisions behind it: ADR-001 to ADR-005. Status: `[advisor proposal]`. All durations are rough advisor estimates at about 15 h/week of Colin's time with 3–4 parallel threads under the lane rules; re-estimate after the first two PRs of each phase.

> **Replaced by `playbook-open-source-desktop-app.md` (ADR-007, 9 Nov 2026)** for the roadmap; the refactoring techniques here still apply.

---

## 1. Overview

| Phase | Goal | Gate to exit | PRs (est.) | Calendar (est.) | Parallel feature work allowed in |
|---|---|---|---|---|---|
| 0 Foundation | Verified changes, green `main`, staging, visibility | 7 exit criteria (phase-0 playbook) | 20–30 | 4 weeks | Green lanes once tier-1 CI is on |
| **1 English names** | Rename-only translation of code, tests, docs | **All names in English** (except the never-rename list); test counts unchanged | 15–25 | 2–4 weeks | Lanes not currently being renamed |
| **2 Worker + API** | Jobs out of the web process; versioned `/api/v1`; token auth | **Every client action available via `/api/v1`**; no PDFium or job threads in the web process | 25–40 | 6–10 weeks | `lane:analysis`, `lane:voice`, `lane:docs`, legal/pricing work |
| **3 New web client** | Design-spec client against `/api/v1`; one-shot switch | **Full flow covered** (switch checklist §5.4) and old client deleted | 30–50 | 8–12 weeks | Core lanes (pdf, analysis, ai, voice) |
| **4 Listening app** | iOS/Android app from the same client; playback-first | **Payment route decided (ADR-006) + evidence of user demand** before start; store release to exit | 15–25 | 6–10 weeks | Everything except `client/` |

Total through phase 3: roughly 5–7 months of calendar time (estimate). Phase 4 is conditional.

## 2. How phases relate to the launch

The paid launch (M2) is mostly gated by **legal, licensing and payment work** (pillars 03–04), not by refactoring. Two scenarios:

| | Scenario A: launch early (recommended) | Scenario B: launch on the new client |
|---|---|---|
| Sequence | Phase 0 → M1 stable test phase → **M2 paid launch on the current UI** → phases 1–3 continue | Phase 0 → 1 → 2 → 3 → M2 |
| Time to first revenue | Weeks (legal items permitting) | Months |
| Learning | Real users shape phases 2–3 (what to build in the app, which flows matter) | Building for imagined users |
| Cost | Some UI work on the old client is thrown away (keep it minimal) | No throw-away |
| Risk | Refactoring a live system: but phases 1–2 are behaviour-preserving with tests, and with few early users impact is small | Longer runway without validation |

`[advisor proposal]`: A. It matches F-05 (no users yet: learning is the scarcest input) and ADR-001 (evolve, ship continuously). Requires decision O-03 (dates).

## 3. Phase 1: English names (ADR-004)

**Entry:** phase 0 exit criteria met; `CLAUDE.md` glossary merged; `rename-area` skill saved.

**Order of areas** (one PR each, ≤ about 1,500 changed lines or ≤ 10 modules):

| # | Area | Lane | Notes |
|---|---|---|---|
| 1 | Glossary into `CLAUDE.md`; ruff + pyright config (not applied) | docs/tools | No code changes |
| 2–4 | `analysis/` (27 modules, 4,350 lines) | analysis | Keep German linguistic data |
| 5–6 | PDF reading (`pdfdatei`, `pdfschreiben`, `kodierung`, `verkleinern`, `bildmodell`, `abbildungen` → `figure_display`) | pdf | Sample PDFs must pass |
| 7–8 | Text pipeline (`sprechfassung`, `lesefassung`, `satzteilung`, `satzliste`, `stolperwoerter`, `belege`, `herkunft`, `laenge`, `wortlisten`) | readalong/analysis | |
| 9–10 | Voices (`*stimme*`, `*sprecher`, `piper_lautschrift`) | voice | Keep GPL headers |
| 11 | Read-along (`mitlesen`, `synchron`) | readalong | Sync test |
| 12 | Jobs/infra (`auslastung`, `leerlauf`, `maschinen`, `ablage`, `platz`, `verlauf`, `dauer`, `protokoll`, `stapel`) | infra | Before phase 2 touches them |
| 13–14 | Accounts/money (`demo` → `accounts`, `zahlung` → `payment` in its own PR, `einladungen`, `uni`, `studimail`, `vorhoeren`, `einstellungen` → `account_settings`, `benachrichtigung`, `umfrage`) | web/money | `risk:high` |
| 15 | Product surfaces (`bearbeitung`, `aenderungsbericht`, `berichtpdf`, `original`, `notizen`, `korrekturen`, `textprobe`, `startseite`, `inhalte`, `sprache`, `rechte`, `gefuehrter_test`; `recht/` → `legal_texts/`) | product | |
| 16–17 | `web.py` internal identifiers (routes unchanged) | web | Single-threaded lane |
| 18 | `evaluator/`, `eigenstimme/` → `own_voice/` | tools | |
| 19 | Test file and function names | tools | |
| 20 | CLI commands, no aliases, + `deploy.sh` + CI + docs | infra | One coordinated PR |
| 21 | Env vars (optional) + `fly.toml` + Fly secrets + `.env.example` | infra | Manual secrets step |
| 22–25 | README + `docs/` to English | docs | Parallel after #19 |
| 26 | Formatting-only PR (ruff format) | tools | After all renames, so rename diffs stay readable |

**Parallelism:** 2–3 rename threads in different lanes; renames change imports across lanes, so run `scope-check` with an exception list for import-only edits, or keep to 2 threads.

**Exit gate:** `grep` for each old module name finds only kept items; full suite counts identical to the start of phase 1 (plus tests added deliberately); glossary complete.

## 4. Phase 2: worker + API (ADR-002)

**Entry:** phase 1 done (or at least areas 12–17 renamed); O-07 (local mode) decided; migrations approach chosen (ADR-002 Q4).

| Step | PR(s) | Lane | Risk | Done when |
|---|---|---|---|---|
| 2.1 | Introduce versioned migrations (`schema_version` + numbered SQL or Alembic); baseline = current 30 tables | infra | high | Applies cleanly to staging and a production copy |
| 2.2 | `jobs` table + queue module (claim with `FOR UPDATE SKIP LOCKED`, lease, heartbeat, states `queued/running/paused/done/failed/cancelled`, priorities as in `auslastung.Priority`) | infra | high | Unit tests incl. lease expiry and double-claim prevention |
| 2.3 | Worker entry point `python -m sci2audio.worker`; runs existing pipeline per job, one job per process; reuses checkpoints | ai/pdf | high | Same run outputs as before on the sample set |
| 2.4 | Web enqueues instead of starting threads (feature flag `SCI2AUDIO_WORKER=on`); old thread start sites (`web.py` ~3156/3158) removed after a week on staging | web | high | All run tests pass with flag on; staging runs end to end |
| 2.5 | Reading/pre-analysis as jobs (removes PDFium from the web process; `markdown()` reading thread ~1699 removed) | web/pdf | high | No `pypdfium2` import reachable from the web process (test) |
| 2.6 | Fly process groups (`web`, `worker`); worker idle stop (logic from `leerlauf.py`); drain on deploy within `kill_timeout` | infra | high | Deploy of web doesn't interrupt a run (test on staging) |
| 2.7 | Global LLM rate limit + 429 backoff in Postgres (replaces per-process `Gate`); global daily spend cap; per-run `--max-kosten` enforced in worker | ai | high | Load test with `SCI2AUDIO_FAKE_429` on 2 workers |
| 2.8 | `/api/v1` skeleton: error shape, auth dependency, OpenAPI export committed, CI diff check | web | normal | `openapi.json` in repo; CI fails on unreviewed breaking change |
| 2.9–2.20 | Endpoints by resource (one PR each, using `/api-endpoint` skill): `files`, `estimates`, `runs` (create with idempotency key, cancel, pause, resume), `runs/{id}` progress, `results`/downloads, player data (sentences, timings, figures, notes), `voices` (incl. browser-voice planning), `edit` (editor operations), `account`, `credit` + `bookings` + receipts, `invites`/`uni`, `admin` | web/money/product | mixed | Contract test per endpoint; old endpoints untouched |
| 2.21 | Token auth for apps (opaque tokens in Postgres, per device, revocable; refresh flow) | money/web | high | Tokens issued after e-mail code; revocation tested |
| 2.22 | Presigned uploads to Tigris (phase 2b) | infra | normal | Upload > 1 MB works without `fly-replay` 409 path |
| 2.23 | Remove `konto_maschine` pinning and `fly-replay` | infra | high | Multi-machine test without pinning |

**Exit gate:** a checklist mapping every action in `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §3–§8 to an `/api/v1` endpoint, each with a contract test; zero job/PDFium threads in the web process.

## 5. Phase 3: new web client (ADR-003)

**Entry:** `/api/v1` covers the Quick Start, run, result and account flows; O-05 (framework) decided; design tokens extracted.

### 5.1 Setup PRs
1. `client/` workspace: TypeScript, Vite, chosen framework, Vitest, Playwright, lint/format; CI job for the client (tier 1: type-check + unit tests; tier 2 nightly: Playwright against staging).
2. Tokens file generated from `docs/design/DESIGN.md` (colours, type scale, spacing, radii, light/dark).
3. Generated API client from `openapi.json`; query layer.
4. App shell: routing, auth (cookie session), language switch (DE/EN), error and empty states from `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §9.

### 5.2 Surface order (one or more PRs each; Playwright test per surface)
| # | Surface | Why this order |
|---|---|---|
| 1 | Login (6-digit e-mail code, Google, invitation links) | Everything else needs it |
| 2 | Quick Start step 1 Upload (PDF/EPUB/MD/TXT, paste, page range, chapters) | Core flow start |
| 3 | Step 2 Text (four levels, sample sentence, pre-analysis summary, per-category AI switches) | The differentiator made visible |
| 4 | Step 3 Voice (device voice, standard voice, Azure Neural, Azure HD; samples; honest quality labels) | |
| 5 | Step 4 Order (price before start, single consent box: rights-holder confirmation, terms, withdrawal waiver) | Money + legal |
| 6 | Run page (percent, remaining time, pause/resume/cancel, e-mail on finish) | |
| 7 | Result + player (chapter marks, speed, read-along, figures, markers and notes, downloads M4B/MP3/ZIP/script/comparison/notes PDF+MD, cost transparency) | Hardest UI after the editor |
| 8 | "Meine Hörbücher" library + details tab (retention, delete) | |
| 9 | Credit, top-up (Stripe), receipts, uni advantage | Money |
| 10 | Settings and account (delete account, sharing revocation, e-mail preferences) | Privacy |
| 11 | Editor (in-paragraph writing, compact bar, split screen with original, regions, omissions, pronunciation, preview listening) | Most complex; last |
| 12 | Local-mode extras (batch, run logs), if O-07 = keep | Local only |
| — | Admin stays server-rendered until after launch (ADR-003 Q3) | Internal |
| — | Public site: restyle server-rendered pages to the tokens (separate PRs) | SEO |

### 5.3 Rules during phase 3
- Old client (`static/app.js`, `bearbeiten.js`) **frozen**: bug fixes only.
- New client behind a switch (e.g. cookie or `?client=new`) on production for Colin and testers.
- Each surface PR attaches screenshots vs. the prototype (`sci2audio-design/prototype/…`).
- Accessibility checks per surface (keyboard path, screen reader labels, contrast), see pillar 02.

### 5.4 Switch checklist (one-shot switch, F-05)
- [ ] All surfaces 1–11 implemented; Playwright suite green on staging for DE and EN
- [ ] All `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §9 states reachable and designed (empty, loading, running, paused, cancelled, failed-with-nothing-charged, expired, no credit, consent missing, server busy, voice switched, unreadable file, too large, browser-voice download, success, destructive confirmations, estimate vs. exact cost, free vs. paid CTAs, first-time vs. returning, light/dark)
- [ ] Read-along accuracy equal to the old player (sync test + manual check on 3 sample books)
- [ ] Payment flow tested end to end in Stripe test mode on staging
- [ ] Lighthouse/a11y check passes the agreed thresholds (pillar 02)
- [ ] Rollback: old client still deployable for 2 weeks

**After the switch:** delete `static/app.js`, `bearbeiten.js`, HTML-in-Python page routes no longer used; remove old `/api/…` endpoints with no caller.

## 6. Phase 4: listening app (ADR-005)

**Entry gate (all):** `/api/v1` stable for ≥ 4 weeks; token auth live; ADR-006 iOS payment route decided; demand evidence per ADR-005 Q1 (proposal: ≥ 30% of listening minutes on mobile browsers and ≥ 5 of the first 50 active users asking for offline/background play).

| Step | Content |
|---|---|
| 4.1 Spike (1–2 weeks) | Capacitor wrapper of the client; native audio plugin: background playback, lock-screen controls, interruption handling; offline download of an M4B/MP3 + timing data; read-along from local files. Test on one real iPhone and one mid-range Android |
| 4.2 Accounts | Apple Developer Program and Google Play Console accounts (fees: verify current prices); bundle IDs; signing; privacy nutrition labels / data safety forms consistent with `docs/datenschutz/` |
| 4.3 App scope v1 | Library, mini-player, full player with read-along, downloads, settings, sign-in; upload/edit/order open the web (or web views) |
| 4.4 Payments | Per ADR-006 (play-and-sync without in-app purchase as default proposal; verify against current Apple rules) |
| 4.5 Test distribution | TestFlight + Google Play internal testing with first users |
| 4.6 Store release | Review cycles; minimum-functionality risk mitigated by native playback/offline value |
| 4.7 v2 candidates | CarPlay/Android Auto, share-to-app for PDFs, on-device device voice (platform TTS) and Thorsten via ONNX |

## 7. Cross-phase rules

| Rule | Why |
|---|---|
| Behaviour-preserving PRs (rename, move, split) never contain features or fixes | Reviewable by test counts |
| Feature freeze per area while it's being renamed or moved | Avoid conflicts and mixed diffs |
| `risk:high` PRs only merged inside release windows | Staging check before production |
| Every phase ends with a retro and an ADR update if a decision changed | Keeps ADRs truthful |
| Re-estimate after the first two PRs of each phase | Estimates here are rough |

## 8. Milestones mapping

| Milestone | Definition | Phase dependency | Pillars |
|---|---|---|---|
| M1 Stable test phase | No P0/P1 risks open; guided-test findings triaged; phase 0 exit criteria met | Phase 0 | 01, 05 |
| M2 Paid launch | Someone can pay, gets what they paid for, costs stay below price; legal items closed | Phase 0 (+ scenario A: current UI) | 03, 04, 05 |
| M3 Rule coverage | Roadmap items 7–14 (headers/footers, figure references, lists, short tables, homographs, English rules, foreign-word suggestions, measurement in CI) | Any time after phase 0, `lane:analysis` | 02 |
| M4 New client live | Phase 3 switch done | Phases 2–3 | 01, 02 |
| M5 App in stores | Phase 4 exit | Phase 4 | 01, 02, 03 |
