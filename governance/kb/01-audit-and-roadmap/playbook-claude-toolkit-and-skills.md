# Playbook: Claude toolkit, skills and parallel threads

`[PLAYBOOK]` · How to set up and use Claude Code (Projects, skills, plugins, scheduled tasks, CI integration) for sci2audio so many threads can run in parallel without unverified merges. Platform facts are `[external fact]` checked 9 Nov 2026 against code.claude.com (see `00-index/sources-and-provenance.md`); several features are beta or research preview, so re-check quarterly.

---

## 1. The constraint everything follows from

Colin works in **Claude Code Projects** (all 159 branches are `claude/project-thread-*`). `[repo fact]`

What a **Project cloud thread** loads from the repo `[external fact]`:

| Repo item | Loaded in Project threads? | Consequence |
|---|---|---|
| Root `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/` (root) | **Yes**, every thread | Put all rules here |
| `CLAUDE.md` in subfolders, path-specific rules | No | Keep rules at the root |
| `.claude/skills/` | **No** | Enable skills on the claude.ai account instead |
| `.claude/agents/`, `.claude/commands/` | **No** | `/eval-bewerten` is invisible to threads |
| Hooks in `.claude/settings.json` | **No** | Enforcement must live in GitHub/CI |
| Permission rules, `env` in `.claude/settings.json` | No | Set env in the cloud environment |
| `.mcp.json` | No | Use claude.ai connectors |
| Plugins declared in `.claude/settings.json` | No | Add in **Project settings → Plugins** |

Contrast: **plain cloud sessions and scheduled tasks** (outside Projects) *do* load repo skills, agents, commands, hooks and `.mcp.json` for single-repo sessions; local sessions load everything. `[external fact]`

**Three rules follow:**
1. Rules → root `CLAUDE.md` + `.claude/rules/`.
2. Procedures → skills enabled on Colin's claude.ai account (source copy also in `.claude/skills/` for local sessions and scheduled tasks).
3. Enforcement → GitHub (CI, scope check, branch protection), never hooks alone.

## 2. Setup checklist (one-time, about 2 h)

| # | Step | Where | Done when |
|---|---|---|---|
| 1 | Write root `CLAUDE.md` (§3) and `.claude/rules/*.md` | `audiobook-generator` and `sci2audio-design` | Merged; a new thread quotes a rule back |
| 2 | Save skills `ship-issue`, `triage`, `rename-area` to the account (drafted 9 Nov, D-15); later `release`, `api-endpoint`, `pdf-regression` | claude.ai skill cards | `/ship-issue` autocompletes in a thread |
| 3 | Project instructions (§4) | Project settings → Memory → Project instructions | Saved (≤ 16,000 characters) |
| 4 | Add both repos to the Project | Project settings → Environment | Threads can clone both |
| 5 | Cloud environment setup script (§7) | Project settings → Environment | A thread runs `pytest -m "not slow"` without installing anything |
| 6 | Plugins: `superpowers`, `security-guidance`, `pyright-lsp` (§6) | Project settings → Plugins | Listed in a thread |
| 7 | Connector: GitHub (already); later error tracking | claude.ai connectors | Visible in a thread's **+ → Connectors** |
| 8 | Scheduled tasks (§8): PR review, nightly, Sunday brief, post-deploy | claude.ai/code/routines or `/schedule` | First run reported |
| 9 | Labels (run `/triage` once) and `.github/lanes.yml` | GitHub | Labels exist; scope-check CI job runs |
| 10 | GitHub Pro + branch protection + required checks (O-01) | GitHub settings | Merge button disabled on red PRs |

## 3. Root `CLAUDE.md`: proposed content

```markdown
# sci2audio – rules for every Claude session

## Who decides
Colin is the owner and the only human in this repo. Repo docs sometimes say "Q": that is
the account name; decisions are Colin's. Never merge, never push to main, never deploy.

## Workflow
- Work only on the GitHub Issue you were given (`/ship-issue N`). Out-of-scope ideas:
  open a new Issue with label `inbox` (REST: gh api repos/dubidu22/audiobook-generator/issues …).
- One Issue, one PR. Title "<area>: <outcome> (#N)"; body starts "Closes #N".
- Paste the pytest summary line into the PR body. Never weaken or delete a test to pass.
- `gh` GraphQL commands may fail here; use `gh api` REST.
- "Never merge" overrides any skill or plugin that offers to merge
  (e.g. superpowers finishing-a-development-branch). Projects' "Merge it" button is Colin's.

## Scope (lanes)
- Every Issue names one lane (.github/lanes.yml). Change only files in that lane and their
  tests. Need something outside? Stop and open a new Issue.
- Before starting, list open PRs (gh api 'repos/dubidu22/audiobook-generator/pulls?state=open');
  if one has the same lane, say so and wait.
- lane:web and lane:money are single-threaded. They are risk:high when touching auth,
  sessions, consent, credit, payments, deletion or retention.

## Tests
- Fast tier (every PR): `python -m pytest -m "not slow" -q`
- Full tier (lane-dependent and nightly): `python -m pytest -q`
- lane:pdf → also `SCI2AUDIO_MUSTERPROBEN=/mnt/project-files/sci2audio/musterproben sci2audio musterprobe pruefen --leer-ok`
- lane:readalong / lane:voice → also `sci2audio synchrontest --leer-ok`
- New tests that take > 2 s or need PDFium/ffmpeg/Tesseract/ONNX get `@pytest.mark.slow`.
- PDFium (pypdfium2) is not thread-safe: all access goes through sci2audio/pdfdatei.py
  under its lock. Never call pypdfium2 directly.

## Risk
risk:high = accounts/login/sessions, credit/payments (zahlung.py, Stripe), deletion/retention,
third-party data flows (Anthropic, Azure, mail), paid API calls and cost estimates, DB schema,
deploy/infra. Post a plan and wait for Colin's go-ahead.

## Glossary (German → English for all new code)
(copy section 2 of 00-index/glossary-de-en.md here)

## Never rename
DB tables/columns, stored keys and job phases (fertig/fehler/abgebrochen), SCI2AUDIO_* env vars,
URL routes, CLI commands (except in their dedicated PRs), UI strings, German word lists.
```

`.claude/rules/` files (root, loaded by threads): `pdf.md` (PDFium lock, sample PDFs), `money.md` (cents only, idempotency, no Stripe library, § 270a BGB fee absorbed), `privacy.md` (update `docs/datenschutz/` on new providers; consent before sending text to Anthropic/Azure), `i18n.md` (every user-facing string needs DE + EN).

## 4. Project instructions: proposed content

```text
This project builds sci2audio.com (repos: dubidu22/audiobook-generator, dubidu22/sci2audio-design).
Owner: Colin, about 20 h/week. Knowledge base: sci2audio-design/docs/kb/.

Threads
- Start a thread only for an Issue labelled `ready`, via /ship-issue N.
- Run at most 4 threads at once, never two with the same lane label, never two in lane:web or lane:money.
- Don't open a PR while 3 PRs are waiting for my review; finish the work and wait.
- Before calling work done: tests per CLAUDE.md; paste the summary lines.
- If something you need is missing (repo access, secret, sample PDFs, a tool), say exactly what in
  your first message and stop. Don't mock or guess.
- risk:high: post the plan, wait for my go-ahead, never merge.
- After I correct a thread, remember the correction in project memory.

Updates
- Post only when a thread finishes, is blocked, or needs a decision.
- Status on request: one line per thread (Issue, lane, state, PR).
```

**Models (D-73, decided 12 Nov 2026):** the project coordinator runs on Fable 5.1; every new thread, including review threads and critical work, runs on Opus 5.5 with high effort. The live project instructions carry this rule together with the review and merge rules of D-68–D-72. When the coordinator is uncertain (a critical decision, a hard review, conflicting plans), it may run that thread on Fable 5.1 with medium or high effort instead (D-80).

**Project memory hygiene:** Colin says "remember this" after every correction. In the monthly retro, read Project settings → Memory; promote stable rules into `CLAUDE.md` (versioned, reviewable) and delete them from memory.

## 5. Skills

### 5.1 Own skills (sci2audio-specific)

| Skill | Status | Trigger | What it does | Lane |
|---|---|---|---|---|
| `/ship-issue N` | Drafted 9 Nov (D-15) | Every thread | Read Issue via REST; stop if not `ready`/no acceptance criteria/too big; check open PRs for collisions; plan (≤ 8 lines); `risk:high` → wait; implement (failing test first for bugs; sample case first for PDF bugs); verify (pytest, `voranalyse`, `--dry-run`, plus sample PDFs / sync test by lane); docs; out-of-scope Issues; PR with template; never merge | any |
| `/triage` | Drafted 9 Nov | Colin, Sunday or ad hoc | Create labels once; split input into findings; search duplicates; show plan table; wait for "go"; create Issues (template: problem, evidence with quotes, acceptance criteria, notes) with `inbox` + type + priority (+ `risk:high`); never set `ready` | docs |
| `/rename-area PATH` | Drafted 9 Nov | Phase 1 | Rename-only with glossary, collision check, never-rename list, `git mv` + AST tool + whole-repo string search, identical test counts, PR with rename map | per area |
| `/release staging\|prod` | To write | Colin, locally | Wrap `deploy.sh`, run acceptance checks list, tag, release notes, close Issues | infra |
| `/api-endpoint` | To write (phase 2) | Threads | Pattern for `/api/v1`: Pydantic schema, auth, error shape, idempotency for money, OpenAPI regen, contract test | web |
| `/pdf-regression FILE` | To write | Threads on PDF bugs | Add the PDF to the sample set with expected output (known-wrong marked `bekannt`), then fix | pdf |

**Update needed for lanes (9 Nov):** `ship-issue` step 8 should add the `lane:<name>` label from the Issue; `triage` should assign a lane per Issue. Propose as skill edits after `lanes.yml` exists.

### 5.2 Bundled skills (built into Claude Code)
| Skill | Use |
|---|---|
| `/code-review [target] [--comment] [--fix]` | Review a branch or PR in a background subagent; `--comment` posts inline on the PR; works on any plan. Basis of the PR-review scheduled task |
| `/code-review ultra` | Deeper cloud review for `risk:high` (needs claude.ai login; see its cost page) |
| `/verify` | Launch and verify the app after a change |
| `/simplify` | Cleanup-only review that applies fixes; occasional cleanup PRs |
| `/schedule` | Create scheduled tasks conversationally |

## 6. Plugins

### 6.1 Always on (Project settings → Plugins), at most three
| Plugin | Source | Why for sci2audio | Caveat |
|---|---|---|---|
| `superpowers` | `claude-plugins-official` (obra/superpowers, about 314k stars, MIT) | Brainstorming → plans → test-driven development → systematic debugging → verification before claiming done | Its `finishing-a-development-branch` offers to merge: `CLAUDE.md` overrides (D-17). Brainstorming asks questions, so use it in the Project conversation or chat, not unattended threads |
| `security-guidance` | official | Pattern warnings on edits, diff review at stop, commit reviewer for injection, XSS, SSRF, hardcoded secrets: relevant for login, Stripe webhook, uploads, 107 `innerHTML` writes | Adds context every turn |
| `pyright-lsp` | official | Exact references and renames across 51k lines; most valuable in phase 1 | Needs Pyright installed by the setup script (§7) |

### 6.2 On demand (mostly local or one thread)
| Step | Plugin | Use |
|---|---|---|
| Design | `impeccable` (community, already in `sci2audio-design`); `frontend-design` (official) from phase 3 | Keep the design system consistent |
| Build big pieces | `feature-dev` (official: explorer, architect, reviewer agents) | Phase 2 API |
| Code intelligence | `typescript-lsp` | Phase 3 client |
| Verify | `playwright` (Microsoft, external in the official marketplace) | Click through upload → run → player on staging |
| Review `risk:high` | `pr-review-toolkit` (silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer, code-simplifier) | Payments, credit, deletion |
| Security before paid launch | `claude-security` (deep scan with verified findings, patches never auto-applied) | M2 gate |
| Refactor assessment | `code-modernization` (`/modernize-assess`, architecture critic) | Once, before splitting `web.py` |
| Docs lookup | `context7` (Upstash) | Current FastAPI, Capacitor, Fly docs |
| Maintenance | `claude-md-management` (`/revise-claude-md`), `hookify` (local guard-rails), `session-report` (usage) | Monthly retro |

Avoid large catch-all skill collections: each enabled plugin adds context on every turn.

## 7. Cloud environment setup script (Project environment)

```bash
#!/usr/bin/env bash
set -euo pipefail
apt-get update -qq
apt-get install -y -qq --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-deu
python3 -m pip install -q --break-system-packages -e ".[dev,all]" || python3 -m pip install -q -e ".[dev,all]"
npm install -g pyright >/dev/null 2>&1 || true   # for pyright-lsp
```
Mirrors `deploy/Dockerfile` (ffmpeg, tesseract-ocr, tesseract-ocr-deu). Environment caching avoids re-installing per thread. Sample PDFs are already uploaded under `/mnt/project-files/sci2audio/musterproben/` (19 samples, per `docs/MUSTERPROBEN.md`).

## 8. Scheduled tasks

Research preview; Pro/Max OK; runs act as Colin on GitHub and count against plan usage; per-account hourly caps on GitHub-triggered runs. `[external fact]`

| Task | Trigger | Prompt (abridged) | Output |
|---|---|---|---|
| **PR review** | GitHub `pull_request.opened` (+ `synchronize` for `risk:high` only) | "Run `/code-review --comment <PR>`. Then check the PR against `CLAUDE.md` scope (lane label vs. files), Definition of Done, and for `risk:high` the checklist in `.claude/rules/money.md`/`privacy.md`. Post one summary comment: blocking / non-blocking / OK." | Inline comments + summary |
| **Nightly full check** | Schedule 02:00 Europe/Berlin | "On `main`: full pytest (incl. slow), sample PDFs, sync test, PDF concurrency test on 3.12 (and 3.13 canary). If red, open a `P0` Issue with the failing output and the last 24 h of merged PRs; else comment nothing." | Issue only on red |
| **Sunday brief** | Schedule Sunday 08:00 | "Summarise for planning: new `inbox` Issues, PRs waiting for Colin, red nightly runs, releases since last Sunday, stale PRs (> 7 days), lane occupancy. One page, as an Issue comment on a pinned 'Planning' Issue." | Brief |
| **Post-deploy check** | API trigger called at the end of `deploy.sh` | "Read Fly logs since deploy, the smoke-test output, error tracking. Open a `P0`/`P1` Issue on regressions; else post OK on the release." | Issue or OK |

Start with PR review + nightly; add the others after a quiet week. Scheduled tasks (outside Projects) load repo skills, so the review task can use `.claude/skills/` copies.

## 9. Running many threads safely (the 28-branches-a-day question)

Peak was 28 thread branches in one day with a 6 s median merge. The aim is to keep high throughput while making every merge verified:

| Mechanism | What it prevents | Where |
|---|---|---|
| **Lanes** (one thread per lane; `lane:web`/`lane:money` single-threaded) | Two threads editing the same files; hidden interactions in `web.py` | `.github/lanes.yml`, `CLAUDE.md`, Project instructions |
| **Scope-check CI job** | A thread drifting outside its lane | CI tier 1 |
| **Tier-1 CI on every PR + nightly tier 2** | Merging untested code; red `main` unnoticed | GitHub Actions + scheduled task |
| **Automatic AI review on PR open** | Unreviewed logic and security errors | Scheduled task |
| **Review-queue cap (≤ 3 waiting for Colin)** | Colin becoming a rubber stamp | Project instructions |
| **Risk-class gates (green auto / normal skim / `risk:high` full)** | Spending human time where machines suffice | Labels + branch protection |
| **Branch protection + required checks + auto-merge** (GitHub Pro) | Click-merging red PRs; it also gives safe auto-merge for green-lane PRs | GitHub |
| **Threads auto-fix their own PRs** (Projects watch PRs: fix CI, address review comments) | PRs stalling on red CI | Built into Projects (with CI back on) |
| **"Rebase before merge" rule** (required up-to-date branches) | Two individually green PRs breaking `main` together | Branch protection setting |
| **Daily batch rhythm**: start 3–4 threads in different lanes in the morning; clear the queue in the evening | Interrupt-driven micro-merging | Habit |

Realistic throughput with these gates: 3–4 concurrent threads, about 8–15 merged PRs/day on good days (vs. about 21 unverified today), every one green and reviewed. `[advisor proposal]` estimate.

**Thread kickoff message (Project conversation):**
```text
Start /ship-issue 12 (lane:pdf), /ship-issue 15 (lane:analysis), /ship-issue 18 (lane:docs).
Max 3 threads. Tell me when each PR is open with its test summary.
```

## 10. CI integration for Claude

- Projects' threads react to CI on their PRs (auto-fix), so **turning CI back on also makes threads self-correcting**.
- `claude-code-action` (GitHub Action, `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` to use the subscription) is an alternative to scheduled tasks for `@claude` mentions; it consumes Actions minutes, so prefer scheduled tasks for review.
- The managed Code Review service needs a Team/Enterprise plan; not an option on Pro/Max. `[external fact]`

## 11. Verification of unverified assumptions (do in week 1)

| Assumption | Test |
|---|---|
| Bundled `/code-review` works inside a Project thread | Run it once on an open PR |
| GraphQL blocked in threads (skills use REST) | First `/triage` run |
| `pyright-lsp` works with the setup script | Rename a symbol in a thread via LSP |
| Account skills load in threads | `/ship-issue` autocompletes |
| Scheduled task GitHub trigger fires on PR open | Open a docs PR |
