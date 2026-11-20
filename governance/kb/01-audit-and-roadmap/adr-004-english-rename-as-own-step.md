# ADR-004: English translation as a separate, rename-only step

`[ADR]` · Status: **Proposed** (advisor, 8 Nov 2026; simplified 9 Nov after F-06 "only Colin") · Decider: Colin · Phase: 1 · Related: ADR-001, ADR-002, `00-index/glossary-de-en.md`, skill `rename-area`

> **Still valid after ADR-007:** the rename becomes a post-v1.0 learning exercise for an international open-source audience.

---

## 1. Context

- Colin plans to translate the codebase to English and asked whether to combine it with a full refactor. [session decision] F-04
- The code is German throughout: about 65 German-named modules (full list in glossary §3) (e.g. `ablage`, `stapel`, `leerlauf`, `zahlung`, `mitlesen`), German functions, variables, comments, docstrings, routes (`/anmelden`, `/protokolle`, `/api/auftrag/{id}`), CLI commands (`voranalyse`, `musterprobe`, `synchrontest`, `leistungstest`, `rauchtest`, `luecke`, …), 110 `SCI2AUDIO_*` env vars, a German README (765 lines) and docs. Database tables are mixed German/English (30 tables). [repo fact]
- New code from phase 2 on (API `/api/v1`, worker, client) will be English. [advisor proposal] ADR-002, ADR-003
- **Only Colin will work in the code**, so there are no external contributors to serve. [session decision] F-06
- 10 test files patch modules by dotted string (`monkeypatch.setattr("sci2audio.…")`, `patch("sci2audio.…")`), which plain refactoring tools miss. [repo fact]

## 2. Decision

1. **Translate before the re-architecture** (phase 1 comes before phase 2), so the API and worker are written against English names and the codebase is never half-and-half for months.
2. **Rename only.** Each PR changes names, comments and docstrings, never behaviour. No bug fixes, refactors or formatting in the same PR; findings go to new Issues.
3. **Glossary first.** `00-index/glossary-de-en.md` §2 goes into the root `CLAUDE.md`; every thread uses it; new terms are added in the same PR that introduces them.
4. **One area per PR**, about 15–25 PRs over the 51k lines, each ≤ about 1,500 changed lines or ≤ 10 modules.
5. **No aliases** for old names (CLI, env vars, imports), because nobody else depends on them (F-06). Stored and public names follow glossary §4 (database, stored keys, URLs and German content stay).
6. Executed with the `rename-area` skill, using an AST-aware rename tool (e.g. `rope`) plus a whole-repo string search for the old names.

## 3. Scope

| In scope (phase 1) | Out of scope (later or never) |
|---|---|
| Module and package names (`git mv`), classes, functions, methods, parameters, variables, constants | Database tables and columns (migration with phase 2 schema work, if ever) |
| Comments, docstrings, log messages for developers | Stored values and JSON keys (job phases `fertig`/`fehler`/`abgebrochen`, checkpoint keys, decisions files) |
| Test names and test helpers (`_wait`, fixtures) | Public German URLs and article slugs (SEO) |
| CLI command names: **one dedicated PR**, updating `deploy.sh`, the CI workflow and docs together | User-facing UI text (German first, English via i18n) |
| Env var names: optional **dedicated PR**, updating `fly.toml`, Fly secrets, `.env.example`, docs together | German linguistic data (word lists, abbreviation tables, regexes in `analysis/`) |
| README and `docs/` to English (can trail the code) | `inhalte/de/*.html` articles |

## 4. Proposed PR sequence

| # | Area | Why this order | Notes |
|---|---|---|---|
| 1 | `CLAUDE.md` glossary + ruff/pyright config (formatting **not** applied yet) | Shared vocabulary before any rename | No code changes |
| 2–4 | `analysis/` (27 modules, 4,350 lines) | Well isolated, every rule has a test | `fremdwoerter` → `foreign_words`, `zeichensalat` → `garbled_text`; keep linguistic data |
| 5–6 | PDF reading: `pdfdatei`, `pdfschreiben`, `kodierung`, `verkleinern`, `bildmodell`, `abbildungen` | Core, covered by sample PDFs | Collision: `abbildungen` → `figure_display` (`figures.py` exists) |
| 7–8 | Text pipeline: `sprechfassung`, `lesefassung`, `satzteilung`, `satzliste`, `stolperwoerter`, `belege`, `herkunft`, `laenge`, `wortlisten` | | `belege` = short citations, not receipts |
| 9–10 | Voices: `browserstimme`, `geraetestimme`, `systemstimme`, `zweitstimme`, `quellenstimme`, `modellstimmen`, `piperstimmen`, `kokorostimmen`, `modell_sprecher`, `kokoro_sprecher`, `piper_lautschrift` | | Keep GPL-3 headers on the separate programs |
| 11 | Read-along and timing: `mitlesen`, `synchron` | Sync test must stay green | |
| 12 | Jobs and infra: `auslastung`, `leerlauf`, `maschinen`, `ablage`, `platz`, `verlauf`, `dauer`, `protokoll`, `stapel` | These modules change again in phase 2; rename first | Table `maschinen`, `konto_maschine` stay |
| 13–14 | Accounts and money: `demo` → `accounts`, `zahlung` → `payment`, `einladungen`, `uni`, `studimail`, `vorhoeren`, `einstellungen` → `account_settings`, `benachrichtigung`, `umfrage` | `risk:high` (payments, auth) | Separate PR for `zahlung` |
| 15 | Product surfaces: `bearbeitung`, `aenderungsbericht`, `berichtpdf`, `original`, `notizen`, `korrekturen`, `textprobe`, `startseite`, `inhalte`, `sprache`, `rechte`, `gefuehrter_test` | | Folder `recht/` → `legal_texts/` |
| 16–17 | `web.py` internal identifiers (not routes) | Largest file; do after its dependencies are renamed | Routes stay until `/api/v1` |
| 18 | `evaluator/`, `eigenstimme/` → `own_voice/` | Tooling, low risk | |
| 19 | Tests: file and function names | | |
| 20 | CLI commands (no aliases) + `deploy.sh` + CI workflow + docs | One coordinated change | |
| 21 | Env vars (optional) + `fly.toml` + Fly secrets + `.env.example` | Needs a manual secrets step by Colin | Can be skipped entirely |
| 22–25 | README and `docs/` to English | Can run in parallel after #19 | Keep German product terms where they're names |

## 5. Rules per PR (from the `rename-area` skill)

1. Start from green `main`; record the baseline test summary.
2. Check open PRs for files in the area; stop if one touches it.
3. Build the rename map from the glossary; collision check (`figures.py`, `legal.py`, `config.Settings`, `foreign.py`).
4. Apply with `git mv` + an AST-aware tool; then search the whole repo for each old name as a string: test patch strings, `importlib`/`getattr`, `deploy/`, `.github/`, `docs/`, README.
5. Translate comments and docstrings faithfully; no "improvements".
6. Verify: `python -m compileall -q sci2audio tests`; pytest summary **identical** to baseline (passed/skipped/failed counts); `sci2audio voranalyse tests/sample_voranalyse_de.md`; `--dry-run`; zero hits for old names except the kept list.
7. PR body: rename map table, kept names, before/after test summary, findings left alone.
8. Feature freeze in the area while its PR is open.

## 6. Options considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Separate rename-only phase before re-architecture (chosen)** | Trivially reviewable (tests identical); new code English from the start; no half-German phase | Costs about 15–25 PRs of calendar time before structural work | **Chosen** |
| Rename while refactoring each area in phase 2 | Each area touched once | Rename + behaviour change in one PR is impossible to review; renamed and unrenamed code coexist for months | Rejected |
| Rename everything in one giant PR | Fast | Unreviewable; conflicts with every open branch; one mistake breaks everything | Rejected |
| Don't translate | Zero cost | Mixed-language codebase once English API/client code arrives; Colin wants English (F-04) | Rejected |
| Translate with aliases for old names | Safer for external users | No external users or contributors (F-06) | Rejected (simplification 9 Nov) |

## 7. Consequences

**Positive:** consistent English codebase; better tooling support (linters, LSP, Claude); clean base for phase 2.

**Negative:** about 2–4 weeks of calendar time at WIP 2 (advisor estimate; check after the first 2 PRs) with little visible product change; merge conflicts with any feature work in the same area (mitigated by freezes); German product terms remain in the UI and stored data, so the glossary stays necessary.

## 8. Open questions

| # | Question | Default |
|---|---|---|
| Q1 | Rename env vars at all? (needs a manual Fly secrets update) | Skip unless it's bothersome; low value |
| Q2 | README and docs in English too, or keep German docs? | English (code and docs in one language); German stays for user-facing content |
| Q3 | Apply ruff formatting in phase 1? | Separate formatting-only PR **after** the renames, so rename diffs stay readable |
| Q4 | Start before or after the paid launch? | Before phase 2; can run in parallel with launch preparation (legal, payments) since it changes no behaviour |
