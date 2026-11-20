# Working: technical risks, open questions and assumptions

`[WORKING]` · Living register for pillar 01. Reviewed in the monthly retro (first Sunday); items move out when resolved (→ decision log / ADR) or are re-dated. Last update: 9 Nov 2026.

**Scales:** Likelihood L1 (rare) to L4 (very likely) · Impact I1 (minor) to I4 (severe: data loss, money, legal, outage) · Priority P0 (now) / P1 (this cycle) / P2 (later).

---

## 1. Advisor pre-analysis

- **The three P0 items are all the same failure mode:** checks exist but nothing runs them. A red test sat on `main`; a crash class sits in code that tests don't stress; CI is off for budget reasons. Fixing the mechanism (tiered tests, gates, nightly) matters more than any single fix.
- **The largest structural risk is phase 2** (worker + API split): it touches money, sessions and job state at once. It needs migrations and a feature flag, and must not start before tier-1 CI, staging and branch protection exist.
- **Platform-feature risk is real:** Projects (beta), scheduled tasks (research preview) and cloud-thread loading rules can change. The process must still work if they do: CI and `deploy.sh` gates are the backbone; Claude automation is an accelerator.
- **Budget pressure shifts from Actions minutes to subscription usage** once nightly tests and reviews run as scheduled tasks; Projects also "draw on plan limits faster". Watch both.

## 2. P0 items (open now)

### P0-1: `main` red: `tests/test_rechte.py::test_whole_book_needs_the_own_rights_declaration`
| Field | Value |
|---|---|
| Status | Open; root cause identified 9 Nov |
| Evidence | Full suite on Python 3.12.3: 1 failed, 1,274 passed, 4 skipped (8 min 10–13 s). Fails alone too (66 s for the file). Slowest test of the suite (56.6 s when failing) |
| Root cause | `_wait()` in `tests/test_web.py:42` polls 200 × 0.02 s = **4 s**. The whole-book job finishes a few seconds later; with the window raised to 120 s (local experiment, reverted) the test **passes** (61.8 s). Not a hang |
| Fix | Deadline-based `_wait` (default 30 s, env `SCI2AUDIO_TEST_WAIT_S`), timeout message shows last phase + error; mark `slow`; follow-up Issue to shrink the fixture (why 55 s?) |
| Owner / lane | Thread, `lane:tools`; Colin approves |
| Done when | Full suite green on 3.12 three times in a row |
| Related | Phase 0 step 0.1 |

### P0-2: pypdfium2 used from several threads without a lock
| Field | Value |
|---|---|
| Status | Open |
| Evidence | Python 3.13.18 (8 Nov): segfault after about 800 tests, two threads inside PDFium (`pdfdatei.Page.__init__` → `doc.raw[index]` vs. `pdfdatei.chars` via `web.py` `_read`). Python 3.12.3 (9 Nov, = production): no crash in 2 full runs |
| Why 3.12 doesn't make it safe | pypdfium2 docs: PDFium isn't thread-safe; simultaneous calls across threads, **even on different documents**, are not allowed and can crash or corrupt the process. The race is timing-dependent; 3.13's timing exposed it. Absence of a crash on 3.12 is luck, not safety |
| Concurrency sources | Reading thread per upload (`web.py` ~1699, `lesen-{file_id}`); run threads (~3156/3158); FastAPI threadpool for sync endpoints (up to 50 concurrent requests per machine); modules calling `pdfdatei`: `original` 8, `notizen` 7, `extractor` 7, `figures` 5, `kodierung` 4, `verkleinern` 3, `bildmodell` 3, `pdfschreiben` 2, `pdflayout` 2, others 1 each |
| Lock implementation details | Module-level `threading.RLock` (re-entrant: wrapper methods call each other); acquire per page operation, not per document (lets other threads interleave; one 300-page scan mustn't block everyone); never wait on futures/other threads while holding it (`web.py` waits on `future.result()`); Tesseract (subprocess) and onnxruntime work outside the lock; route any direct `pypdfium2` import through `pdfdatei` |
| Test | `tests/test_pdf_concurrency.py`: 4–8 threads × about 50 iterations, compare text to the single-threaded baseline; run on 3.12 (CI nightly) and 3.13 (canary) |
| Long-term | Worker processes (ADR-002) remove PDFium from the web process entirely |
| Owner / lane | Thread, `lane:pdf`, `risk:high` |

### P0-3: CI off; test runtime vs. Actions budget
| Field | Value |
|---|---|
| Status | Open |
| Facts | Full suite 8 min 10–13 s here (plus 3–4 min heavy install). Old workflow: matrix 3.10 + 3.12 → about 20–25 min per run. GitHub Free private: **2,000 min/month**, jobs rounded up to whole minutes. Today's rate: about 21 PRs/day plus re-pushes |
| Math | Old design: 2,000 / 22 ≈ 90 runs/month (vs. 600+ needed). Tier 1 (about 1,205 tests, about 112 s measured) + `uv` cached install + one Python version → about 4–5 billed min/run → 400–500 runs/month. Note: "≈ 320 min/month" from 8 Nov was a usage estimate for 40 PRs, not the budget |
| Profile | 74 tests ≥ 1 s take 365 s (77%); 17 tests ≥ 5 s take 247 s (52%); slowest files `test_rechte` 68 s, `test_gefuehrter_test` 51 s, `test_zeitlinie` 40 s, `test_web` 27 s |
| Mitigation | Two tiers (`-m "not slow"` on PRs and in `deploy.sh`; full suite nightly as a scheduled task = 0 Actions minutes); `cancel-in-progress`; job-level path filter (not workflow-level, which would block required checks); `pytest-xdist` experiment; lanes + review cap reduce PR count; GitHub Pro (more minutes; verify) |
| Owner / lane | Thread, `lane:infra` + `lane:tools`; Colin decides O-01 |

## 3. Risk register

| ID | Risk | L | I | Pri | Mitigation | Trigger to re-assess | Status |
|---|---|---|---|---|---|---|---|
| R-01 | Regression reaches production (no gate) | L4 | I3 | P0 | Tier 1 in CI + `deploy.sh`; nightly tier 2; staging | Any P0/P1 within 7 days of a release | Open |
| R-02 | PDFium concurrent access crashes or corrupts | L2 now, L3 after launch | I3 | P0 | Lock now, worker later | Any segfault in logs | Open |
| R-03 | `main` red unnoticed | L3 (happened) | I2 | P0 | Nightly opens P0 Issue; branch protection | — | Open |
| R-04 | `risk:high` change merged unreviewed (credit, consent, deletion) | L3 | I4 | P1 | Labels, AI review, Colin review, staging check | First paid transaction | Open |
| R-05 | Parallel threads collide (esp. `web.py`, 7,245 lines) | L4 | I2 | P1 | Lanes, single-threaded `lane:web`/`lane:money`, scope check | Scope-check failures > 2/week | Open |
| R-06 | Deploy interrupts running jobs | L3 | I2 | P2 | Deploy in windows; phase 2 worker drain | Users report restarts | Accepted until phase 2 |
| R-07 | Per-process rate limit exceeded across 4 machines (429 storms) | L2 | I2 | P2 | Global limiter in phase 2; `auslastung.Gate` backoff meanwhile | 429s in logs | Open |
| R-08 | Runaway LLM/Azure cost (bug, abuse, loop) | L2 | I4 | P1 | Provider spend caps (week 3), `--max-kosten`, daily cost e-mail | Daily cost > threshold | Open |
| R-09 | Data loss (Postgres) without restore path | L1 | I4 | P1 | Document Neon restore; restore test into staging quarterly | Before first paid user | Open |
| R-10 | Neon/Tigris/Fly outage | L2 | I3 | P2 | Uptime monitor; status pages; accept for now | — | Accepted |
| R-11 | XSS via `innerHTML` (107 writes in `app.js`) | L2 | I3 | P1 | `security-guidance` plugin; targeted review of user-controlled strings (titles, notes, file names); replaced in phase 3 | Security scan before M2 | Open |
| R-12 | Secrets leak (keys in repo, logs, error reports) | L1 | I4 | P1 | `.env` ignored; Fly secrets; PII/secret scrubbing in error tracking; `security-guidance` | — | Open |
| R-13 | Schema change without migrations breaks production data | L2 | I3 | P1 | Migrations before phase 2 (step 2.1) | First schema change | Open |
| R-14 | Phase 2 larger than estimated (`web.py` coupling) | L3 | I2 | P2 | Strangler steps with feature flag; re-estimate after 2 PRs | > 2× estimate | Open |
| R-15 | Claude platform changes (Projects beta, scheduled tasks preview, loading rules) | L3 | I2 | P2 | Gates in CI/`deploy.sh` independent of Claude features; re-check quarterly | Release notes | Open |
| R-16 | Subscription usage limits hit (Projects + scheduled tasks + reviews) | L3 | I2 | P2 | Cap scheduled tasks; fewer concurrent threads; single sessions for routine Issues | Limit reached twice in a month | Open |
| R-17 | CI minutes exhausted mid-month | L3 | I2 | P1 | Tiering, cancel-in-progress, lanes; weekly usage check; GitHub Pro | > 60% used by mid-month | Open |
| R-18 | Flaky tests erode trust in gates | L2 | I2 | P2 | `pytest-timeout`; deadline-based waits; quarantine label with an Issue | Same test fails/passes on same commit | Open |
| R-19 | Python version drift (3.13 behaviour) | L2 | I2 | P2 | Production pinned 3.12; nightly 3.13 canary | Plan to upgrade the image | Open |
| R-20 | Stale branches/PRs conflict (e.g. #127) | L3 | I1 | P2 | Weekly rule: close or refresh PRs > 7 days | — | Open |
| R-21 | Local mode diverges from online behaviour during phase 2 | L2 | I2 | P2 | Decide O-07; shared queue abstraction with SQLite | Phase 2 design | Open |
| R-22 | Licence contamination (GPL/AGPL) through new dependencies | L2 | I3 | P2 | Dependabot PRs reviewed for licence; keep GPL parts as separate programs (`piper_lautschrift.py`, `kokoro_sprecher.py`) | New dependency | Open |

## 4. Open technical questions (owner: Colin unless noted)

| ID | Question | Options | Recommendation | Blocks | Ref |
|---|---|---|---|---|---|
| O-01 | Pay for GitHub Pro (branch protection, required checks, auto-merge, more Actions minutes)? | Yes / no (conventions only) | **Yes** | Enforced gates, auto-merge for green lane | Phase 0 2.D |
| O-02 | Create staging app `sci2audio-staging`? | Yes / no | **Yes** (stopped when idle) | Release process | Phase 0 2.A |
| O-05 | Client framework | React / Svelte / Vue | React | Phase 3 | ADR-003 |
| O-07 | Keep local mode as a product? | Keep / drop | Decide before phase 2 design | Worker design, desktop | ADR-005 |
| O-09 | Fix approach for `test_rechte` | Deadline wait + slow mark / shrink fixture / both | Both | Green `main` | P0-1 |
| T-01 | Migrations: Alembic vs. numbered SQL | — | Numbered SQL unless SQLAlchemy is adopted | Phase 2.1 | ADR-002 Q4 |
| T-02 | Token format for apps | Opaque in Postgres / JWT | Opaque | Phase 2.21 | ADR-002 Q3 |
| T-03 | `pytest-xdist` adoption | Yes if 3 green parallel runs | Experiment | Faster tier 1 | Phase 0 2.4 |
| T-04 | Error-tracking vendor and data scrubbing | Hosted free tier / self-hosted | Hosted free tier, scrub document text and e-mails, add to processor list | Phase 0 2.E | Pillar 04 |
| T-05 | Monorepo `client/` vs. separate repo | — | Same repo | Phase 3 | ADR-003 Q2 |
| T-06 | Rename env vars at all? | Yes / skip | Skip unless bothersome | Phase 1 #21 | ADR-004 Q1 |
| T-07 | Launch scenario A (current UI) vs. B (new client) | A / B | A | M2 timing | Phases 1–4 §2 |

## 5. Unvalidated assumptions

| Assumption | Used in | How to validate | By |
|---|---|---|---|
| Tier 1 takes about 2 min on GitHub runners | CI budget | First CI run | Phase 0 week 2 |
| `uv` cached install ≈ 1 min for `.[dev,all]` | CI budget | First CI run | Week 2 |
| GitHub Pro includes more Actions minutes (about 3,000) and costs about $4/month | O-01 | GitHub pricing page | Before purchase |
| Bundled `/code-review` works in Project threads and scheduled tasks | Review automation | Run once | Week 1 |
| GraphQL unreachable in Project threads | Skills use REST | First `/triage` | Week 1 |
| `pyright-lsp` works with the setup script | Toolkit | Rename test | Week 1 |
| Neon plan provides adequate point-in-time restore | R-09 | Neon dashboard / docs | Week 3 |
| Fly cost of a mostly-stopped staging app is small | O-02 | Fly pricing + first invoice | Week 2 |
| 3–4 threads + gates yield 8–15 verified merges/day | Lifecycle playbook | Measure in weeks 2–4 | Retro 6 Dec |
| Phase durations (2–12 weeks) | Roadmap | Re-estimate after 2 PRs per phase | Each phase |

## 6. Checklists

### 6.1 Before merging any PR
- [ ] Tier-1 CI green; scope check green
- [ ] AI review: no unresolved blocking findings
- [ ] PR body: `Closes #N`, test summary, risk statement
- [ ] `risk:high`: Colin read the diff; staging check planned in the next window

### 6.2 Before every production release
- [ ] `main` green on tier 1; last nightly tier 2 green on this commit (else run it)
- [ ] Staging deploy + acceptance checks of included Issues
- [ ] Spend caps in place; error tracking receiving events
- [ ] Tag + release notes; previous image noted for rollback

### 6.3 Technical readiness for paid launch (M2), tech part
- [ ] Phase 0 exit criteria met
- [ ] `--max-kosten` + confirmation before paid runs live
- [ ] Payment flow tested end to end in Stripe test mode on staging; webhook replay/duplicate handling verified (`stripe_events`)
- [ ] `claude-security` deep scan done; findings triaged
- [ ] XSS review of user-controlled strings in the current client (R-11)
- [ ] Restore test done (R-09)
- [ ] PDFium lock live; concurrency test green
- [ ] Load test: 3 parallel runs on one machine + 1 upload burst without errors
