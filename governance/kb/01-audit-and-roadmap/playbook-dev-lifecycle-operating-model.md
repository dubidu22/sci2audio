# Playbook: development lifecycle and operating model

`[PLAYBOOK]` · How work flows from idea to production with one founder (Colin, about 20 h/week) and many parallel Claude threads. Replaces the "Operating model", "Code flow" and "Environments and releases" sections of the lifecycle-plan doc (artifact `SnLnhmCRZWB1YG3A2AZgux`). Status: `[advisor proposal]` unless marked otherwise.

---

## 1. The design problem in numbers

| Fact | Value | Source |
|---|---|---|
| Thread branches per day (peak) | **28** (26 Oct); 21 (29 Oct); 15 (8 Nov) | [repo fact] `audit-process-and-velocity.md` |
| PRs per day (average / peak) | about 21 / 45 | [repo fact] |
| Merge latency | median **6 s**; 89% within 60 s | [repo fact] |
| Reviews | 0 on 306 PRs | [repo fact] |
| Automated checks on PRs | none (CI off, pytest not in `deploy.sh`) | [repo fact] |
| `main` state | red (`test_rechte.py`) | [repo fact] 9 Nov |
| Colin's time | about 20 h/week, shared with Wieder in Ordnung | [session decision] F-02 |
| Human review cost | 5–15 min per normal PR; 30+ min for `risk:high` | [advisor proposal] estimate |

**Conclusion:** the goal isn't to slow Claude down to human speed. It's to make **every merge verified** and to spend Colin's minutes only where a machine can't judge. Velocity comes from parallelism that can't collide plus automated gates; safety comes from checks that run without Colin.

## 2. Principles

1. **Verify by machine first, by human last.** Tests, scope checks and an AI review run on every PR before Colin looks.
2. **Parallelism by boundary, not by count.** Threads may run in parallel when they can't touch the same files. The limit is "one thread per lane", not a fixed number.
3. **Limit the review queue, not the thread count.** At most **3 PRs waiting for Colin** at any time. Threads beyond that wait before opening new PRs.
4. **Risk decides the gate.** Green-lane PRs can auto-merge when checks pass; normal PRs need a 1-minute skim; `risk:high` needs a real review and a staging check.
5. **`main` is always green.** A red `main` stops all merges until fixed (P0).
6. **One Issue, one PR, one lane.** Scope creep becomes a new Issue.

## 3. Roles

| Role | Who | Owns | Time budget |
|---|---|---|---|
| Product owner | Colin | Backlog order, `ready` label, acceptance | Sunday planning 30 min + triage |
| Release manager | Colin | Release windows, deploys, rollback | 2 × 20 min/week |
| Gatekeeper for `risk:high` | Colin | Reading `risk:high` diffs and review findings | about 30 min per PR, 1–3 per week |
| Developers | Claude threads in the Project "sci2audio" | One Issue → one PR, tests, docs | Unlimited, within lane rules |
| Reviewer | Scheduled task on `pull_request.opened` (`/code-review --comment` + checklist); `pr-review-toolkit` or ultrareview for `risk:high` | Findings as PR comments | Automated |
| Verifier | CI tier 1 on every PR; nightly full suite (tier 2) | Pass/fail signals | Automated |

## 4. Lanes: safe parallel work

A **lane** is a set of paths that only one thread may change at a time. Two threads in different lanes can't produce merge conflicts or hidden interactions in the same files.

### 4.1 Lane map (until the phase 2 split)

| Lane | Paths (main ones) | Risk class | Notes |
|---|---|---|---|
| `lane:pdf` | `extractor.py`, `pdflayout.py`, `pdfdatei.py`, `pdfschreiben.py`, `kodierung.py`, `sections.py`, `figures.py`, `abbildungen.py`, `verkleinern.py`, `bildmodell.py`, `epub.py`, `herkunft.py` | normal | Sample PDFs must pass |
| `lane:analysis` | `analysis/**`, `prefilter.py`, `foreign.py`, `stolperwoerter.py`, `wortlisten.py`, `normalizer.py`, `tests/sample_voranalyse_de.md` | green/normal | Rule changes need test + example sentence |
| `lane:ai` | `routing.py`, `rewriter.py`, `prompts.py`, `sprechfassung.py`, `chunker.py`, `calibration.py`, `costs.py`, `auslastung.py`, `health.py`, `gap.py` | normal; `risk:high` for cost logic | Paid API calls |
| `lane:voice` | `tts.py`, `browserstimme.py`, `geraetestimme.py`, `systemstimme.py`, `zweitstimme.py`, `quellenstimme.py`, `*stimmen.py`, `*_sprecher.py`, `piper_lautschrift.py`, `laenge.py`, `static/browserstimme*.js`, `static/geraetestimme.js` | normal | Licences (pillar 04) |
| `lane:readalong` | `mitlesen.py`, `synchron.py`, `satzliste.py`, `satzteilung.py`, `timing.py`, `lesefassung.py`, `belege.py` | normal | Sync test must pass |
| `lane:web` | `web.py`, `demo.py`, `startseite.py`, `admin.py`, `legal.py`, `inhalte.py`, `i18n*.py`, `sprache.py`, `sprachen/**`, `web_page.html`, `demo_login.html` | `risk:high` when auth/consent | **Single-threaded lane**: `web.py` is 7,245 lines; only one thread here, ever |
| `lane:money` | `zahlung.py`, `einladungen.py`, `uni.py`, `studimail.py`, `vorhoeren.py`, credit/booking parts of `demo.py` | **always `risk:high`** | Shares `demo.py` with `lane:web`, so never parallel with `lane:web` |
| `lane:client` | `static/app.js`, `static/bearbeiten.js`, `static/app.css`, `static/i18n.js`, `static/testleitfaden.js`; later `client/**` | normal | Old client frozen once phase 3 starts |
| `lane:product` | `bearbeitung.py`, `aenderungsbericht.py`, `berichtpdf.py`, `original.py`, `notizen.py`, `korrekturen.py`, `textprobe.py`, `rechte.py`, `gefuehrter_test.py`, `umfrage.py`, `verlauf.py`, `dauer.py`, `protokoll.py`, `stapel.py` | normal | |
| `lane:infra` | `deploy.sh`, `deploy/**`, `fly.toml`, `.github/**`, `maschinen.py`, `leerlauf.py`, `ablage.py`, `platz.py`, `datenbank.py`, `pyproject.toml` | `risk:high` for data/deploy | Phase 0 work lives here |
| `lane:tools` | `evaluator/**`, `eigenstimme/**`, `musterprobe.py`, `leistung.py`, `rauchtest.py`, `ttsbench.py`, `speedtest.py`, `cli.py` | green/normal | |
| `lane:docs` | `README.md`, `ROADMAP.md`, `docs/**`, `CLAUDE.md`, `.claude/rules/**`, `inhalte/**` | green | Can always run in parallel |

Tests follow their code: a thread may edit `tests/test_<module>.py` for modules in its lane. New shared fixtures (`conftest.py`, `llm_fakes.py`) belong to `lane:tools`.

After phase 2 the map simplifies: `api/`, `worker/`, `core/…`, `client/`. Update `.github/lanes.yml` (§4.3) in the same PR that moves files.

### 4.2 How many threads at once

| Situation | Max concurrent threads | Why |
|---|---|---|
| Normal week | **One per free lane, at most 4** | 4 parallel PRs is about what review automation plus a 3-PR human queue can absorb |
| Rename sprint (phase 1) | 2–3, each in a different lane | Renames touch imports across lanes, so keep low |
| Phase 2 (`web.py` split) | 1 in `lane:web` + `lane:infra` combined, plus up to 2 elsewhere | The split touches the riskiest file |
| `main` red | **0 new threads**; 1 thread fixes `main` | Nothing merges on red |
| Review queue ≥ 3 PRs waiting for Colin | Threads may continue but not open new PRs | Pull-based limit |

This replaces the earlier flat "WIP limit of 2" (D-03). The flat limit was a stand-in for "never collide, never outrun verification"; lanes plus the review-queue cap achieve that while keeping more parallelism.

### 4.3 Enforcing lanes automatically

1. **`.github/lanes.yml`**: maps lane names to path globs (the table in §4.1).
2. **PR label `lane:<name>`**: set by the thread (`ship-issue` skill step 8) from the Issue's lane.
3. **CI job `scope-check`** (tier 1, seconds): reads the label and the changed files; fails if any file is outside the lane (tests for those modules and `CLAUDE.md` glossary additions excepted). Also fails if two open PRs share a single-threaded lane (`lane:web`, `lane:money`).
4. **`CLAUDE.md` scope rules** (loaded by every Project thread):
   ```markdown
   ## Scope
   - Every Issue names one lane (see .github/lanes.yml). Change only files in that lane
     and their tests. Need something outside? Stop and open a new Issue.
   - Before starting, list open PRs; if one has the same lane, say so and wait.
   - lane:web and lane:money are single-threaded and always risk:high when they touch
     auth, consent, credit, payments or deletion.
   ```
5. **Project instructions** repeat: "Run at most 4 threads, never two in the same lane, and don't open a PR while 3 PRs are waiting for my review."

## 5. Gates by risk class

| Class | Examples | Required before merge | Who merges |
|---|---|---|---|
| **Green** | `lane:docs`; tests-only; new analysis rule with test and example sentence; evaluator tooling | Tier-1 CI green + scope check green | **Auto-merge** when green (needs GitHub Pro: branch protection + required checks) |
| **Normal** | Most feature and bug PRs | Tier-1 CI green + scope check + AI review without blocking findings + Colin's 1-minute skim of the PR summary and test lines | Colin (or auto-merge after Colin adds label `approved`) |
| **`risk:high`** | Auth, sessions, consent, credit, payments (Stripe webhook), deletion/retention, third-party data flows, paid-API cost logic, DB schema, deploy/infra | All of the above + deeper review (`pr-review-toolkit` or `/code-review ultra`) + Colin reads the diff + check on staging | Colin, inside a release window |

Without GitHub Pro (private repo: no branch protection, no required checks, no auto-merge), the gates are conventions only. The `ship-issue` skill tells threads never to merge, but nothing stops a click. That's why O-01 (GitHub Pro, about $4/month) is the first decision.

**Update 12 Nov 2026 (D-68–D-72, decided):** for the public `sci2audio` repo the "Who merges" column above is replaced. Every PR is reviewed in a new, separate thread before merging (D-68). A change is **critical** when it touches a layer contract, the core dataclasses, the KB or a golden file, or carries `risk:high` (D-69). Non-critical reviewed PRs may be merged by the coordinator, with one project-chat line per merge; critical PRs wait for Colin's approval (D-70). Colin is told of every architectural decision. Plans are always posted; non-critical plans with high confidence start without waiting (D-72).

**Update 12 Nov 2026 (D-80, decided): until v1.0** Claude also decides and merges critical matters: the coordinator approves critical plans and has reviewed critical PRs merged, without waiting for Colin. Colin is informed in the project chat of every decision and every merge. All other rules above stay in force.

## 6. Work item flow

```
idea / tester finding / error
  → /triage → Issue (labels: inbox, type, P0–P2, lane:…, risk:high?)
  → Sunday planning: Colin sets `ready` on up to 5–8 Issues (≤ capacity, one lane each)
  → Project conversation: "start #12 (lane:pdf), #15 (lane:analysis), #18 (lane:docs)"
  → thread: /ship-issue N → PR (lane label, test summary, risk)
  → CI tier 1 + scope check → AI review comments
  → gate by class (auto / skim / full review + staging)
  → merge (squash) → release window → staging → production → tag → Issue closed
```

### 6.1 Labels
| Group | Labels |
|---|---|
| Status | `inbox` (new), `ready` (Colin only), `approved` (Colin, for auto-merge of normal PRs) |
| Type | `bug`, `feature`, `chore` |
| Priority | `P0` (now: data loss, crash, wrong charge, privacy), `P1` (this cycle: blocked or misled in a main flow), `P2` (later) |
| Risk | `risk:high` |
| Lane | `lane:pdf`, `lane:analysis`, `lane:ai`, `lane:voice`, `lane:readalong`, `lane:web`, `lane:money`, `lane:client`, `lane:product`, `lane:infra`, `lane:tools`, `lane:docs` |

GitHub Project boards need GraphQL, which isn't reachable from cloud sessions, so status is by label (D-14).

### 6.2 Definition of Ready (Issue → `ready`)
- [ ] Describes the problem or user outcome, not only a solution
- [ ] Acceptance criteria: how Colin checks it in the UI or CLI
- [ ] Exactly one lane; small enough for one PR (about one thread session)
- [ ] `risk:high` set if it touches the risk areas
- [ ] No open PR in the same single-threaded lane

### 6.3 Definition of Done (PR → merge)
- [ ] Tier-1 tests green; tier-2 checks relevant to the lane green (sample PDFs for `lane:pdf`, sync test for `lane:readalong`) or explicitly "not runnable here" with reason
- [ ] New behaviour has a test; bugs have a failing-first test
- [ ] Scope check green (only lane files)
- [ ] AI review: no unresolved blocking findings
- [ ] Docs, README, `docs/datenschutz/` updated when behaviour, data flow or providers changed
- [ ] `risk:high`: Colin read the diff and checked it on staging
- [ ] PR title `<area>: <outcome> (#N)`; body has `Closes #N`, test summary, risk statement, out-of-scope Issues

## 7. Cadence (20 h/week)

| When | What | Time |
|---|---|---|
| Sunday | Planning: read the Sunday brief (scheduled task), triage Inbox, set `ready` on up to 5–8 Issues across lanes, start threads | 30–45 min |
| Daily (optional, phone) | Clear the review queue: skim normal PRs, add `approved`; unblock threads | 10–20 min |
| Wednesday + Sunday | Release window: staging → production → tag (§8) | 20 min each |
| `risk:high` PRs | Full review in a fixed slot (e.g. Wednesday before the release) | 30 min each |
| First Sunday of the month | Retro: incidents, red `main` episodes, review findings that slipped, lane conflicts; update `CLAUDE.md` rules; review `[WORKING]` files | 30 min |
| Busy or holiday weeks | Freeze: bug fixes only, no new threads except P0 | — |

Expected management time: about 2–3 h/week; the rest is building, product work and Wieder in Ordnung.

## 8. Environments and release

| | Local | Staging | Production |
|---|---|---|---|
| Fly app | — | `sci2audio-staging` (new, O-02) | `sci2audio-demo` |
| URL | localhost:8765 | `sci2audio-staging.fly.dev` | sci2audio.com |
| Data | Colin's files | Own small Postgres + volume, test accounts | Real accounts |
| API keys | Colin's | Separate Anthropic + Azure keys with low monthly caps; Stripe test mode | Production keys with caps |
| Runs | any time | release windows only (auto-stop) | always |

**Release steps** (skill `/release`, run locally because Fly needs Colin's machine):
1. `main` green (tier 1 + last nightly tier 2).
2. `./deploy.sh --ziel staging`: pytest tier 1 → existing gates (performance, sample PDFs, sync) → deploy staging → smoke test.
3. On staging, run each released Issue's acceptance criteria (5–10 min); `risk:high` items first.
4. `./deploy.sh --ziel prod`: same gates → deploy → smoke test → new performance reference.
5. Tag `vYYYY.MM.DD[-n]`, `gh release create --generate-notes` (PR titles become the changelog).
6. Close released Issues; post-deploy scheduled task checks logs and smoke result.

**Rollback:** `fly releases --image` → `fly deploy --image <previous>`; the tag tells which image belongs to which release. **Big features** go behind `SCI2AUDIO_*` flags: deploy off, test on staging, switch on in production.

## 9. Where work happens

| Place | Use for |
|---|---|
| Claude Code Project "sci2audio" (both repos) | All implementation threads; Project conversation for steering ("start #12 and #15", "status?", "pause the rename") |
| Local Claude Code (Colin's Mac) | `/release`, `deploy.sh`, `/eval-bewerten`, local mode, anything needing Fly or the local `.venv`; or one Project thread via Remote Control |
| claude.ai chat | Strategy, architecture, pricing, legal questions, this KB, `/triage` of large pasted batches |
| GitHub (web or app) | Backlog, reviewing PRs, merging |
| claude.ai/code/routines | Scheduled tasks (PR review, nightly, Sunday brief, post-deploy) |
| Separate Project "Wieder in Ordnung" | Its work only (separate memory and instructions) |

## 10. Anti-patterns to stop

| Anti-pattern | Seen | Replacement |
|---|---|---|
| Merge within seconds of opening | median 6 s | Gate by class (§5); auto-merge only for green lane after checks |
| Threads started from a prompt, not an Issue | 0 Issues ever | `/triage` + `ready` + `/ship-issue N` |
| Many threads in `web.py` at once | 28 branches/day, one 7k-line file | `lane:web` single-threaded |
| Shipping features the roadmap rejected | read-along vs. `ROADMAP.md` | Roadmap = milestones; changes go through Sunday planning |
| Stale PRs | #127 open since 1 Nov | Weekly: close or refresh PRs older than 7 days |
| Deploying an unknown state | `main` red unnoticed | Tier-1 tests in CI and `deploy.sh`; nightly tier 2 |

## 11. Metrics for the retro

| Metric | Target | Source |
|---|---|---|
| `main` red time per week | 0 h | CI history |
| PRs merged without green tier 1 | 0 | CI / branch protection |
| Review queue max length | ≤ 3 | GitHub |
| Lane conflicts (scope-check failures, merge conflicts) | trending down | CI |
| Post-release defects (P0/P1 Issues within 7 days of a release) | ≤ 1 per release | Issues |
| PR lead time (opened → merged) | normal: < 24 h; green: < 1 h | GitHub |
| Colin's management time | ≤ 3 h/week | self-report |
