# Playbook: phase 0, foundation (first 30 days)

`[PLAYBOOK]` · Goal: every change verified, `main` always green, a staging step before production, visibility into errors and cost. Start: Monday 9 Nov 2026 (week 1 = 9–15 Nov). Status: `[advisor proposal]`; numbers marked `[repo fact]` were measured 9 Nov 2026 on Python 3.12.3 (production version).

> **After ADR-007:** tests, CI, `CLAUDE.md`, Issues, reviews and the PDFium fix stay valid (now in the public repo); staging, Fly, Postgres restore, spend caps and uptime monitoring no longer apply. See `playbook-open-source-desktop-app.md`.

**Exit criteria for phase 0 (all must hold):**
1. `main` green on tier 1 and tier 2 for 7 consecutive days.
2. Every PR runs tier-1 CI + scope check; `deploy.sh` refuses to deploy on red tier 1.
3. PDFium access serialised; concurrency test green on 3.12 (and 3.13 canary).
4. Staging app live; at least two releases went staging → production with tags.
5. Error tracking, uptime monitor and provider spend caps active.
6. A Postgres restore into staging done once.
7. `CLAUDE.md`, lanes, labels, skills and scheduled tasks (PR review + nightly) in use.

---

## Step 0 (day 1): make `main` green and clear the stale PR

Nothing else starts until this is done: a test gate on a red suite just blocks every deploy.

### 0.1 Fix the failing test

`[repo fact]` `tests/test_rechte.py::test_whole_book_needs_the_own_rights_declaration` fails on `main` (full suite: 1 failed, 1,274 passed, 4 skipped, 8 min 10–13 s).

**Investigation done 9 Nov:**

| Check | Result |
|---|---|
| Earlier assertions in the test | Pass: rights light `rot` for a whole book; order refused with HTTP 400 mentioning `§ 53 Abs. 4`; estimate `gelb` for an excerpt |
| Failing line | `assert _wait(client, job_id)["phase"] == "fertig"`; `_wait` (`tests/test_web.py:42`) polls `/api/auftrag/{id}` 200 × 0.02 s = **4 s**, then raises "Auftrag wurde nicht fertig" |
| Alone | Fails (66 s for the file) |
| With the polling budget raised to 120 s (local experiment, reverted) | **Passes**; test takes 61.8 s |
| Duration profile | Slowest test of the suite: 56.6 s when failing |

**Diagnosis:** not a hang. The job completes a few seconds after the 4 s polling window. `_wait` assumes jobs finish within 4 s, which this test's whole-book job exceeds on this machine. Probably also flaky on Colin's Mac under load.

**Fix (one PR, `lane:tools`, normal risk):**
1. Make `_wait` deadline-based (`time.monotonic()`), default 30 s, overridable by env (`SCI2AUDIO_TEST_WAIT_S`); on timeout, include the job's last phase and error in the assertion message.
2. Mark the test `slow` (step 3).
3. Optional follow-up Issue (`lane:product`): why does this test take about 55 s? Profile it; if the job processes a large fixture, shrink the fixture so the test checks the rule, not throughput.

Definition of done: full suite green on 3.12; failing message now shows phase and error on timeout.

### 0.2 Resolve stale PR #127

`[repo fact]` PR #127 "Thorsten natürlicher: Pausen, Textregeln, eine Lautstärke je Stück, Nachbearbeitung", opened 1 Nov 2026 15:30, untouched since. 8 files, +543/−39: `docs/THORSTEN-KLANG.md` (+55), `sci2audio/browserstimme.py` (+29/−13), `sci2audio/piper_lautschrift.py` (+46), new `sci2audio/piperklang.py` (+182), `sci2audio/sprachen/en/server.json` (+2/−1), `sci2audio/static/browserstimme-worker.js` (+17/−13), `sci2audio/tts.py` (+46/−12), new `tests/test_piperklang.py` (+166). Purpose: pauses between paragraphs and after headings (0.32 s between sentences etc.), text rules, one loudness per piece, post-processing, for Piper Thorsten on server and in browser.

Considerations:
- `browserstimme.py`, `tts.py` and the worker JS changed many times after 1 Nov (read-along work 7–8 Nov), so conflicts are likely.
- Thorsten's commercial licence is unresolved (pillar 04); Thorsten is excluded in sales mode (`SOLD_VOICES`). Investing in its sound now may be wasted if it's replaced by a self-trained or Kokoro voice.

**Recommended:** close #127 with a comment linking a new Issue "voice: natural pauses and loudness for Piper voices" (`lane:voice`, P2, `inbox`) that keeps the description and the branch name. Re-open the work after the voice licence decision. Alternative if Colin wants it now: one thread rebases in `lane:voice`, runs `synchrontest`, re-opens as a fresh PR.

Definition of done: no open PR older than 7 days.

---

## Step 1 (days 1–2): PDFium lock (P0)

Details: `audit-pdfium-thread-crash.md`. `lane:pdf`, `risk:high` (crash class).

1. Module-level `threading.RLock` in `sci2audio/pdfdatei.py`; every method touching `self._pdf`, `self._page` or `pypdfium2.raw` runs under it; lock per page, not per document.
2. `grep -rn "pypdfium2" sci2audio/`: route any direct use through `pdfdatei`.
3. Never wait on another thread while holding the lock.
4. New `tests/test_pdf_concurrency.py`: 4–8 threads × about 50 iterations extracting test PDFs in parallel; text identical to a single-threaded baseline; marked `slow`.
5. Run on 3.12 and 3.13 (3.13 reproduced the segfault on 8 Nov; keep it as a canary in the nightly).

---

## Step 2 (days 2–3): two-tier test strategy

### 2.1 Measured profile `[repo fact]` (Python 3.12.3, this environment, `--durations=0`)

| Slice | Tests | Time | Share |
|---|---|---|---|
| Whole suite | 1,279 (1,274 pass, 1 fail, 4 skip) | 490 s wall (476.6 s measured in test phases) | 100% |
| Tests ≥ 5 s | 17 | 247.4 s | 52% |
| Tests ≥ 2 s | 41 | 319.0 s | 67% |
| **Tests ≥ 1 s** | **74** | **365.0 s** | **77%** |
| Tests ≥ 0.5 s | 147 | 415.1 s | 87% |
| **Remaining (< 1 s)** | **about 1,205** | **about 112 s** | **23%** |

Slowest tests: `test_rechte` whole-book (56.6 s, failing), `test_zeitlinie::test_a_browser_lands_on_the_second_it_jumps_to` (25.6 s), `test_gefuehrter_test::test_step_4_says_free_in_the_test_and_why_not` (23.9 s), `test_gefuehrter_test::test_the_panel_beside_the_app_and_as_a_sheet_on_a_phone` (19.1 s), `test_schritt2_hoehe::test_levels_reach_the_first_view` (18.1 s), `test_protokoll::test_a_local_web_run_leaves_a_full_protocol_and_the_pages_show_it` (16.6 s), `test_bestellmoment::test_online_test_phase_says_free_and_how_long_files_stay` (12.0 s), `test_rechte::test_paid_mode_offers_licensed_voices_and_ai_for_green_texts` (10.7 s), `test_editor_auswahl::test_editor_writes_in_place` (10.2 s), `test_kodierung::test_own_glyph_order_is_solved_with_the_dictionary` (9.4 s), `test_web::test_simulated_rate_limit_is_waited_out` (7.8 s), `test_scan::test_many_scanned_pages_are_read_side_by_side` (7.6 s).

Slowest files: `test_rechte` 68.3 s, `test_gefuehrter_test` 51.3 s, `test_zeitlinie` 40.0 s, `test_web` 27.1 s, `test_schritt2_hoehe` 18.1 s, `test_protokoll` 17.0 s, `test_bestellmoment` 13.7 s, `test_eigenstimme` 10.8 s, `test_kodierung` 10.8 s, `test_editor_auswahl` 10.2 s, `test_scan` 10.0 s. 57 files run under 2 s each (37 s together).

### 2.2 Tiers

| Tier | Content | Command | Expected time | Runs where |
|---|---|---|---|---|
| **Tier 1, fast** | Everything not marked `slow` (about 1,205 tests) + CLI smoke (`--dry-run`, `voranalyse`, `ui --help`) | `python -m pytest -m "not slow" -q` | about 2 min serial (112 s measured + collection); 1 min or less with `pytest-xdist -n auto` if the suite is parallel-safe (to verify) | Every PR (CI), every thread before opening a PR, `deploy.sh` staging + prod |
| **Tier 2, full** | Tier 1 + `slow` (74+ tests, about 6 min) + sample PDFs (`musterprobe pruefen`) + sync test (`synchrontest`) + PDF concurrency test + 3.13 canary | `python -m pytest -q` + the CLI checks | about 9–10 min | Nightly scheduled task (subscription, **0 Actions minutes**); `deploy.sh --ziel prod` unless the last nightly was green on the same commit; on demand for `risk:high` PRs via label `full-tests` |
| **Lane extras** | `lane:pdf`: sample PDFs; `lane:readalong`/`lane:voice`: sync test | as in `CLAUDE.md` | 1–3 min | Thread before PR |

### 2.3 Marking slow tests without editing 74 tests
1. Generate `tests/slow_tests.txt` from a `--durations=0` run: every test node ID with call + setup ≥ 1.0 s.
2. In `tests/conftest.py`, `pytest_collection_modifyitems` adds `pytest.mark.slow` to items whose node ID is in the file; register the marker in `pyproject.toml` (`[tool.pytest.ini_options] markers = ["slow: …"]`).
3. Convention for new tests: explicit `@pytest.mark.slow` if they take > 1 s or need PDFium on real files, ffmpeg, Tesseract or ONNX models.
4. Refresh `slow_tests.txt` monthly (retro) from the nightly's durations output.
5. Add `pytest-timeout` with a generous default (e.g. 120 s per test) so a hang fails fast instead of stalling CI.

### 2.4 Parallel execution (experiment, not a dependency)
`pytest-xdist -n auto` uses processes (safe for PDFium). Risks: shared temp dirs, fixed ports, global state in `~/.sci2audio`. Run once with `-n 4`; adopt only if green three times in a row.

---

## Step 3 (day 3): pytest gate in `deploy.sh`

Add before the existing gates:
```bash
echo "== Tests, fast tier (about 2 minutes) =="
if ! "${run[0]}" -m pytest -m "not slow" -q; then
  [ "$anyway" = 1 ] || { echo "Not deployed: fast tests are red. Send the output to Claude." >&2; exit 1; }
fi
```
For `--ziel prod` additionally: if the last nightly (tier 2) wasn't green on `git rev-parse HEAD`, run the slow tier too (about 6 min). The existing gates stay: performance test vs. reference → sample PDFs → sync test → `fly deploy` (`PAKETE_STAND`, `SCI2AUDIO_COMMIT`) → smoke test → new reference.

---

## Step 4 (days 3–5): repo rules, lanes, backlog

| # | Item | Details |
|---|---|---|
| 4.1 | Root `CLAUDE.md` + `.claude/rules/{pdf,money,privacy,i18n}.md` | Content in `playbook-claude-toolkit-and-skills.md` §3 |
| 4.2 | `.github/lanes.yml` | Lane map in `playbook-dev-lifecycle-operating-model.md` §4.1 |
| 4.3 | Labels | Run `/triage` once (creates `inbox ready bug feature chore risk:high P0 P1 P2`); add `approved`, `full-tests` and the 12 `lane:*` labels |
| 4.4 | Skills on the account | `ship-issue`, `triage`, `rename-area` (drafted 9 Nov) |
| 4.5 | Project instructions + setup script | Toolkit playbook §4, §7 |
| 4.6 | Seed the backlog | `/triage` this KB's P0/P1 items (debt register TD-01 to TD-20, risk register) into Issues |
| 4.7 | Close or refresh stale PRs | Weekly rule |

---

## Step 5 (end of week 1): first gated release
`./deploy.sh` (production only, staging comes in week 2) with tier 1 green → tag `v2026.11.13` (or the actual date) → `gh release create --generate-notes`. Establishes the tag habit and the rollback map (tag → Fly image).

---

## Week 2 (16–22 Nov): staging, CI, review, visibility

### 2.A Staging app (O-02)
- `fly apps create sci2audio-staging`; own volume (1 GB) and own Postgres (Neon branch or a small separate project) + Tigris bucket; separate Anthropic and Azure keys with low monthly caps; Stripe **test mode** keys; `SCI2AUDIO_DEMO_URL=https://sci2audio-staging.fly.dev`.
- Auto-stop when idle (the app's own idle stop, `leerlauf.py`).
- `deploy.sh --ziel staging|prod` chooses `fly.toml` vs. `fly.staging.toml`.
- Check Fly's pricing for a mostly-stopped app with a 1 GB volume before creating it.

### 2.B Lean CI (re-enable)

**Budget math** `[advisor proposal]` (verify against real runs):
- GitHub Free, private repo: **2,000 Actions minutes/month** (Linux 1×); each job is billed rounded up to whole minutes. GitHub Pro reportedly includes 3,000 (verify at purchase, O-01).
- The earlier "≈ 320 min/month" was a **usage estimate** (8 min × 40 PRs), not a budget. With the old design (full suite about 8 min + install 3–4 min, × 2 Python versions ≈ 20–25 min per run), 2,000 minutes buy only about 80–100 PR runs, and threads that auto-fix CI push several times per PR.
- With tier 1 only, one Python version, cached `uv` installs: about 1 min setup + 1 min install + 2 min tests ≈ **4–5 billed minutes per run**.

| PR runs/month (incl. re-pushes) | Tier-1 minutes | Fits 2,000? |
|---|---|---|
| 150 | 600–750 | Yes |
| 300 | 1,200–1,500 | Yes, tight |
| 450 (today's PR rate with re-runs) | 1,800–2,250 | No, so lanes + review cap reduce PR count; xdist cuts test time; or Pro |

Tier 2 runs as a scheduled task on the Claude subscription, so it costs 0 Actions minutes.

**Workflow** (`.github/workflows/tests.yml`, replaces `sci2audio.yml`):
```yaml
name: tests
on:
  pull_request:
  workflow_dispatch:
concurrency:
  group: tests-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
jobs:
  tier1:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: changes
        with:
          filters: |
            code:
              - 'sci2audio/**'
              - 'tests/**'
              - 'pyproject.toml'
              - 'deploy/**'
      - name: Scope check (lane label vs. changed files)
        run: python .github/scope_check.py "${{ github.event.pull_request.number }}"
        env: { GH_TOKEN: "${{ github.token }}" }
      - if: steps.changes.outputs.code == 'true'
        uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - if: steps.changes.outputs.code == 'true'
        uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - if: steps.changes.outputs.code == 'true'
        run: sudo apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-deu
      - if: steps.changes.outputs.code == 'true'
        run: uv pip install --system -e ".[dev,all]"
      - if: steps.changes.outputs.code == 'true'
        run: python -m pytest -m "not slow" -q
      - if: steps.changes.outputs.code == 'true'
        run: |
          sci2audio tests/sample_scientific_de.txt --dry-run
          sci2audio voranalyse tests/sample_voranalyse_de.md
          sci2audio ui --help
```
Design notes:
- **One job** (scope check + tests) avoids paying a second rounded-up minute.
- **No workflow-level `paths-ignore`**: with required checks, a workflow skipped by path filter leaves the check "pending" forever and blocks docs PRs. The job-level filter lets docs PRs pass in seconds.
- `cancel-in-progress` drops superseded runs when a thread pushes fixes.
- `full-tests` label → a second workflow runs tier 2 on that PR (`risk:high` only).

### 2.C Review automation
Scheduled task "PR review" on `pull_request.opened` (toolkit playbook §8). Verify `/code-review --comment` works in that context.

### 2.D Branch protection (needs GitHub Pro, O-01)
Required check `tests / tier1`; require branches up to date; enable auto-merge; no direct pushes to `main`.

### 2.E Visibility
| Item | Proposal | Done when |
|---|---|---|
| Error tracking | A hosted error tracker with a free tier (e.g. Sentry); Python SDK in web + (later) worker; PII scrubbing on (no document text, no e-mails in events); add to `docs/datenschutz/avv-liste.md` as processor | A forced test exception arrives by e-mail |
| Uptime | External monitor (free tier) on the start page + `/api/…` health endpoint (new, returns DB and storage reachability), every 5 min, alert by e-mail | Alert fires when the staging app is stopped |
| Health endpoint | `GET /healthz` (no auth): process up; `GET /readyz`: Postgres + Tigris reachable | Monitor uses it |

---

## Week 3 (23–29 Nov): money and data safety

| # | Item | Lane / risk | Details |
|---|---|---|---|
| 3.1 | Provider spend caps | — (console settings) | Anthropic Console monthly limit; Azure budget + alert; Stripe: no cap needed (incoming). `docs/DEMO-SERVER.md` already recommends a monthly provider limit as "the second safety net next to credit" |
| 3.2 | `--max-kosten` hard cap + confirmation before every paid run | `lane:ai`, `risk:high` | Roadmap item 3, open since 26 Oct ("kein Lauf darf überraschen") |
| 3.3 | Daily cost e-mail | `lane:infra` | Sum of real costs per day from run stats; alert when above a threshold |
| 3.4 | Backups: Postgres | `lane:infra`, `risk:high` | Document what Neon's plan provides (point-in-time restore window, verify); write `docs/BACKUP.md` |
| 3.5 | Backups: Tigris files | `lane:infra` | Retention is 7/30 days by design; decide whether files need backup at all (probably not: regenerable, and the privacy promise says they're deleted) |
| 3.6 | Restore test | Colin + thread | Restore production Postgres into staging (or a Neon branch); app starts; an account's credit and bookings match. Repeat quarterly |
| 3.7 | Dependabot | `lane:infra` | `.github/dependabot.yml`: pip weekly, grouped into one PR; GitHub Actions monthly |

---

## Week 4 (30 Nov – 6 Dec): planning hygiene and retro

| # | Item | Details |
|---|---|---|
| 4.1 | Rewrite `ROADMAP.md` | One page: guiding rule ("Erst alle statistischen Möglichkeiten ausschöpfen, dann KI"), Now / Next / Later, each line linking a GitHub milestone (M1 stable test phase, M2 paid launch, M3 rule coverage); detailed tables move into Issues |
| 4.2 | Milestones | Create M1–M3; assign Issues; dates per O-03 |
| 4.3 | Metrics baseline | Runs started → finished → downloaded; failed runs/week + top error; real cost per 1,000 words per option vs. list price; active accounts/week + uni share; open P0/P1 Issues |
| 4.4 | First monthly retro (Sun 6 Dec) | Review: red-`main` time, lane conflicts, review findings that slipped, CI minutes used vs. budget, `slow_tests.txt` refresh, project memory → `CLAUDE.md` |

---

## Day-by-day for week 1

| Day | Colin (time) | Threads |
|---|---|---|
| Mon 9 Nov | 30 min: decide #127 (close + Issue), approve step-0 PR, decide O-01 (GitHub Pro) | `lane:tools`: fix `_wait` + mark slow |
| Tue 10 Nov | 20 min: review PDFium lock PR (`risk:high`) | `lane:pdf`: PDFium lock + concurrency test; `lane:tools`: `slow_tests.txt` + conftest + pytest-timeout |
| Wed 11 Nov | 20 min: release window (first release with tier-1 gate) | `lane:infra`: pytest gate in `deploy.sh` |
| Thu 12 Nov | 30 min: save skills, Project instructions, setup script | `lane:docs`: `CLAUDE.md`, rules, `lanes.yml` |
| Fri 13 Nov | 15 min: label setup via `/triage` | `lane:docs`: seed Issues from KB P0/P1 |
| Sun 15 Nov | 30 min: first Sunday planning; release + tag | — |

## Risks in phase 0

| Risk | Mitigation |
|---|---|
| Tier 1 misses a regression only a slow test catches | Nightly tier 2 opens a P0 Issue the next morning; prod deploy runs tier 2 if nightly isn't green on that commit |
| CI minutes run out mid-month | `cancel-in-progress`, job-level path filter, lanes reduce PR count; watch usage weekly; GitHub Pro as fallback |
| Scheduled-task features change (research preview) | CI and `deploy.sh` gates don't depend on them |
| Phase 0 feels like no progress | It's about 2 weeks of thread time; feature work continues in green lanes once tier-1 CI is on |
