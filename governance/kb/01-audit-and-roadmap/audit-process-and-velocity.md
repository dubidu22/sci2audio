# Audit: development process and velocity, 26 Oct – 9 Nov 2026

`[AUDIT]` · How work flows from idea to production today. Data from git history and the GitHub REST API (`pulls?state=all`, 306 PRs), read 9 Nov 2026. All numbers are `[repo fact]` unless labelled otherwise.

---

## 1. Diagnosis

**Claude produces changes far faster than one person can verify them, and verification has quietly dropped to almost zero.** Merging has become a reflex (median 6 s after opening), automated checks are off, the test suite is red without anyone noticing, and priorities are set session by session instead of by the owner. Nothing is broken badly yet, because there are no users. That's exactly why now is the cheapest moment to install the process.

## 2. Throughput

| Metric | Value |
|---|---|
| Period | 26 Oct 2026 (repo created) – 8 Nov 2026 (14 days); plus 1 PR on 9 Nov |
| Commits on `main` | 540 (26 Oct – 8 Nov) |
| Pull requests | 306 total: 300 merged, 5 closed unmerged (#1–#5 on day 1), **1 open and stale** (#127, opened 1 Nov, branch `claude/project-thread-v611vu`) |
| Distinct branches | 159, all `claude/project-thread-*` (Claude Code Projects threads) |
| Peak commits/day | 85 (29 Oct); 81 (26 Oct); 59 (1 Nov) |
| Peak PRs/day | 45 (29 Oct); 35 (7 Nov); 31 (26 Oct) |
| Peak distinct thread branches/day | 28 (26 Oct); 21 (29 Oct); 18 (3 Nov); 15 (8 Nov) |

Commits per day:

| Date | Commits | PRs | Thread branches |
|---|---|---|---|
| 26 Oct | 81 | 31 | 28 |
| 27 Oct | 24 | 13 | 9 |
| 28 Oct | 29 | 16 | 15 |
| 29 Oct | 85 | 45 | 21 |
| 30 Oct | 3 | 3 | 3 |
| 31 Oct | 6 | 2 | 2 |
| 1 Nov | 59 | 27 | 17 |
| 2 Nov | 50 | 25 | 17 |
| 3 Nov | 46 | 24 | 18 |
| 4 Nov | 30 | 14 | 8 |
| 5 Nov | 45 | 23 | 12 |
| 6 Nov | 21 | 25 | 1 |
| 7 Nov | 38 | 35 | 8 |
| 8 Nov | 23 | 22 | 15 |
| 9 Nov (00:24) | — | 1 | 1 |

Note: an earlier session estimate said "up to 6 parallel threads in one day". The full data shows up to **28 distinct thread branches per day**. How many ran *concurrently* isn't recorded in git. Either way, it's far above the proposed WIP limit of 2.

## 3. Review and merge behaviour

| Metric | Value |
|---|---|
| Reviews on PRs | **0** (sampled PR #305: 0 reviews; no review activity seen anywhere) |
| Merged by | `dubidu22` (Colin) for every PR |
| Merge latency (PR opened → merged), 300 merged PRs | **median 6 s**; 266 of 300 (89%) within 60 s; 277 (92%) within 5 min; 90th percentile 193 s; max 15.4 h |
| Example | #305 opened 19:41:07, merged 19:41:14 (7 s) |
| Branch protection | None; not available on private repos without GitHub Pro (API: HTTP 403 "Upgrade to GitHub Pro") |
| Required checks | None (CI disabled) |

Interpretation: at a 6-second median, the PR isn't a review step. It's a transport mechanism from the thread to `main`. Any defect a thread introduces lands in `main` unless the thread itself caught it.

## 4. Verification in the pipeline

| Check | Exists | Runs automatically | Gate before production |
|---|---|---|---|
| pytest (1,279 tests) | Yes | **No**: CI disabled; not in `deploy.sh` | **No** |
| CLI smoke (`--dry-run`, `voranalyse`, `ui --help`) | Yes (in CI workflow) | No (CI disabled) | No |
| Performance test vs. reference (`leistungstest`) | Yes | In `deploy.sh` | Yes (override `--trotzdem`) |
| Sample PDFs (`musterprobe pruefen --leer-ok`) | Yes, 19 samples | In `deploy.sh` | Yes; passes when no samples are present (`--leer-ok`) |
| Read-along sync test (`synchrontest --leer-ok`) | Yes | In `deploy.sh` | Yes; passes when empty |
| Post-deploy smoke test (`rauchtest`) | Yes | In `deploy.sh` | After deploy (prints rollback hint) |
| AI grader (`/eval-bewerten`, evaluator) | Yes | Manual, local only | No |
| Code review | No | — | — |
| Staging check | No staging | — | — |

**State of `main` on 9 Nov:** red. `tests/test_rechte.py::test_whole_book_needs_the_own_rights_declaration` fails, reproducibly (see `audit-repo-state-2026-11-08.md` §3). Nothing in the process would have surfaced it.

**CI:** `.github/workflows/sci2audio.yml` has the comment "CI bis November 2026 abgeschaltet (Budget). Nur noch manuell startbar." Triggers: `workflow_dispatch` only. Job: matrix Python 3.10 + 3.12, apt ffmpeg, `pip install ".[dev,all]"`, pytest, 3 CLI smoke commands. Content is correct; only the triggers are off.

**Budget reasoning, re-checked** `[advisor proposal]`: GitHub Free gives 2,000 Actions minutes/month for private repos. The full suite takes about 8 min locally, plus installs (~3–4 min for heavy extras), × 2 Python versions ≈ 20–25 min per PR. At ~300 PRs per 2 weeks that's about 13,000 min/month: far over budget, so switching it off was rational. The lean design (one Python version, PR-only, pip cache, cancel in-progress, skip docs-only, ~40 PRs/month after the WIP limit) comes to ≈ 320–500 min/month. See `playbook-phase-0-foundation.md`.

## 5. Planning and prioritisation

| Aspect | Finding |
|---|---|
| Backlog | GitHub Issues **unused: 0 Issues ever created** (corrected 9 Nov: the one open item, "Thorsten natürlicher: Pausen, Textregeln, eine Lautstärke je Stück, Nachbearbeitung", is PR #127, which GitHub also lists under issues) |
| Roadmap | `ROADMAP.md` dated 26 Oct 2026, 86 lines, phases 1–4, items 1–16 |
| Roadmap drift | Shipped but not on the roadmap: accounts and e-mail code login, Google login, uni advantage (3 variants, 7–8 Nov), guided test (4 parts, 7 Nov), multi-machine Postgres + Tigris (7 Nov), money-back guarantee, invite credit, read-along player, editor, evaluator. **Read-along shipped although the roadmap lists "Player mit Text-Hervorhebung und Live-Tempo: verworfen"** |
| Roadmap items still open | 3 (`--max-kosten` hard cap + confirmation before paid runs; "Q ist kostensensibel; kein Lauf darf überraschen"), 6 (targeted repair), 7–14 (more rules, English rules, measurement in CI), 15 (content-hashed segment cache), 16 (Piper offline, optional) |
| Who decides priorities | De facto each thread session, from Colin's prompt of the moment; no weekly selection |
| Definition of Ready / Done | None written |
| Release notes / changelog | None; PR titles are good (German, outcome-oriented, e.g. "PDF-Auslesen: Tabellen mit Linien, Fußnoten über den Seitenumbruch, kaputte Schriften, Lücken melden (#303)") and would make a usable changelog |
| Releases / tags | None (`gh release list`: empty; `git tag`: empty) |

## 6. Agent context and tooling

| Aspect | Finding |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | None in `audiobook-generator` or `sci2audio-design` |
| `.claude/` | `audiobook-generator/.claude/commands/eval-bewerten.md` only (AI grader via subscription). `sci2audio-design/.claude/` exists (impeccable design skills) |
| Visibility in Project threads | Project cloud threads load only the root `CLAUDE.md`, `.claude/CLAUDE.md` and `.claude/rules/`; **commands, skills, agents, hooks, `.mcp.json` and repo-declared plugins aren't loaded** `[external fact, 9 Nov 2026]`. So `/eval-bewerten` is invisible to the threads doing most of the work |
| Orientation per session | The 54 kB German README, re-read by each thread |
| Project memory / instructions | Unknown (not visible from the repo); to be set up (playbook) |
| Repo docs refer to the owner as "Q" | Many docstrings and docs say "Q" (e.g. "Q ist kostensensibel", "Qs Entscheidung"). The session clarified that Colin is the owner (F-01). Harmless, but `CLAUDE.md` should state who decides |

## 7. Environments and release path

| Step | Today |
|---|---|
| Develop | Claude cloud threads (Projects), branch per thread |
| Integrate | Self-merge to `main`, median 6 s |
| Test | Whatever the thread ran; nothing enforced |
| Deploy | `git pull && ./deploy.sh` on Colin's laptop → Fly `sci2audio-demo` (production) |
| Verify | Gates in `deploy.sh` (performance, sample PDFs, sync), then smoke test |
| Rollback | Manual: `fly releases --image`, then `fly deploy --image <previous>` |
| Staging | None |
| Versioning | Commit SHA passed as `SCI2AUDIO_COMMIT` (good); no tags |

## 8. Capacity reality

| Factor | Value | Source |
|---|---|---|
| Colin's time | about 20 h/week, shared with Wieder in Ordnung | [session decision] F-02 |
| Output rate | about 21 PRs/day on average | [repo fact] |
| Time to genuinely review one PR | 5–15 min for a small change; 30+ min for `risk:high` | [advisor proposal], estimate |
| Implied review load at current rate | 21 PRs × 5 min ≈ 1.75 h/day ≈ 12 h/week, before any other work | [advisor proposal], arithmetic |
| Conclusion | Real review at today's rate would use 60% of the week. Either cut throughput (WIP 2, ≤ 5 Issues/week) or automate most verification (tests, scheduled review), and in practice both | [advisor proposal] |

## 9. Risks this process creates

| Risk | Likelihood | Impact | Mitigation (phase 0) |
|---|---|---|---|
| Regression reaches production unnoticed | High (already happened: red `main`) | Medium now (no users); high after launch | pytest gate in `deploy.sh`; lean CI; nightly full check |
| `risk:high` change (payments, deletion, consent) merged without review | Medium | High: money, GDPR | `risk:high` label + scheduled-task review + explicit human review |
| Parallel threads collide in `web.py` | High (28 branches/day, one 7k-line file) | Medium: rework, subtle merge bugs | WIP 2, one thread per area |
| Priorities drift from business goals | High (roadmap drift) | Medium: time spent on non-critical features before launch | Sunday planning; Issues only from `ready` |
| Knowledge only in threads' heads | Medium | Medium | `CLAUDE.md`, project memory, this KB |
| Stale open PR #127 conflicts later | Medium | Low | Close or rebase in phase 0 week 1 |

## 10. What works and should be kept

- PR titles: descriptive, outcome-oriented. Keep them; they become the changelog.
- One branch per thread, squash into `main`. Keep.
- `deploy.sh` gating philosophy (refuse unless green, explicit override). Extend with pytest.
- Measurement culture (performance reference, sample PDFs, evaluator). Wire it into automation.
- High willingness to write docs (`docs/`, privacy records). Channel it into this KB and `CLAUDE.md`.
