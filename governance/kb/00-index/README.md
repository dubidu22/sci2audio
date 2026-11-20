# sci2audio knowledge base: redesign and launch

> **Moved on 20 Nov 2026:** this knowledge base now lives in `governance/kb/` of `dubidu22/sci2audio`; the decision log is `governance/kb/decision-log.md`. Pillars 03 and 05 and most of 04 (the archived paid-service, tax and legal analyses) stay in the archived private repository `dubidu22/sci2audio-design`. Three personal details in the decision log were removed for privacy and are marked as such.

`[DOC]` · Status as of 2026-11-09 · Owner: Colin (founder, solo) · Advisor: Claude

> **Direction changed on 9 Nov 2026 (D-41, ADR-007):** sci2audio becomes a **free, open-source desktop app** and a learning project for AI-assisted development. Active plan: `01-audit-and-roadmap/playbook-open-source-desktop-app.md`. Pillars 03 and 05 and most of 04 are **archived** (kept as documentation of the paid-service analysis).

The single source of truth for the sci2audio.com redesign, re-architecture and (originally) paid launch. It consolidates the advisory session of 8–9 Nov 2026, the repo audits of `dubidu22/audiobook-generator` and `dubidu22/sci2audio-design`, fresh external checks (legal, tax, licences, market) and the decisions taken so far. **53 Markdown files in 7 folders, plus 3 helper scripts** (`02-product-and-pipeline/tools/extract_prompts.py`, `02-product-and-pipeline/tools/english_check/compare.py` with its sample text, `03-monetization-and-economics/tools/unit_economics.py`). Not legal or tax advice.

---

## 1. Status in one screen

| Item | State | Provenance |
|---|---|---|
| Product | sci2audio.com: scientific texts (PDF, EPUB, MD, TXT, pasted text) → listening script → audiobook (MP3/M4B) | [repo fact] |
| Users | **None yet.** Free test phase; guided-test infrastructure exists | [session decision] (Colin, 9 Nov) |
| Team | **Colin only**, about **20 h/week**, no other contributors planned | [session decision] (Colin, 8–9 Nov) |
| Codebase | 51k lines of Python (`sci2audio/`), 12k lines of vanilla JS/CSS, 1,279 tests (**`main` red: 1 failing**, 9 Nov); repo created 26 Oct 2026 | [repo fact] |
| Velocity | 540 commits / 305 PRs in 14 days (26 Oct – 8 Nov), all self-merged, 0 reviews | [repo fact] |
| Way of working | Claude Code **Projects** (cloud threads, branches `claude/project-thread-*`) | [repo fact] |
| Hosting | Fly.io `sci2audio-demo`, region `fra`, 0–4 machines, Postgres (Neon) + Tigris optional, SQLite fallback | [repo fact] |
| Current phase | **Open-source pivot, phase 1:** retire the hosted demo, then extract a public repo (ADR-007). Nothing implemented yet; no code changes in this session by request | [session decision] D-41 |
| Goal | Learn proper AI-assisted development methods for future client work; keep a tool Colin uses himself | [session decision] F-11 |
| Paid launch | **Dropped** (D-41). The launch gate and pillars 03–05 are archived | [session decision] |
| Biggest launch findings | (1) Live prices + uni discount can be loss-making; (2) **+19% reverse-charge VAT** on provider costs under § 19 UStG; (3) **no free German file voice in sales mode** (Thorsten is lessac-based); (4) paid lines only on green texts; (5) four DPAs missing, Neon/Tigris disclosure unverified | Batches 3–4 |
| Strategic direction | Evolve the core, re-architect the edges (API + worker), rebuild the client, translate to English as its own step, web first, listening app later | [advisor proposal], not objected to |
| Platforms planned | Web → Android/iOS (listening-first) → desktop only if local mode has real users | [advisor proposal], based on Colin's stated plan for Android/iOS/Windows/Mac |
| Wieder in Ordnung | Separate project and separate stack; out of scope here | [session decision] (Colin, 9 Nov) |

## 2. Next steps (open-source plan)

| # | Step | File |
|---|---|---|
| 1 | Tag `hosted-final`, notify testers, delete accounts/data, destroy the Fly app, revoke keys, static site on sci2audio.com (D-44) | `01-audit-and-roadmap/playbook-open-source-desktop-app.md` phase 1 |
| 2 | Confirm the voice set (D-43, English first per D-50) and the reuse of Abogen's Kokoro plugin (D-52); licence GPL-3.0 decided (D-42) | playbook phase 4, `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md` |
| 3 | Fix the failing test and set up CI in the new public repo (O-09 still applies) | playbook phase 2 |
| 4 | Extract the public repo with test-guarded removal Issues | playbook phase 2 |

## 3. Directory map

| Path | Purpose |
|---|---|
| `00-index/` | This file, decision log, glossary, sources |
| `01-audit-and-roadmap/` | Repo and process audit, ADR-001–005 and **ADR-007 (pivot)**, the **open-source desktop app playbook** (active plan), lifecycle and Claude toolkit playbooks |
| `02-product-and-pipeline/` | Product truth, UX redesign, mobile app scope, accessibility, pipeline architecture, detectors and prompts; **English text preparation: rules vs. spaCy (audit, 9 Nov)** |
| `03-monetization-and-economics/` | **Archived:** pricing, unit economics, payments and credit, iOS payment ADR, abuse guardrails |
| `04-legal-and-compliance/` | Voice/model licences (**active**); GDPR doc (used for the shutdown); copyright, terms, tax and lawyer brief (**archived**) |
| `05-gtm-and-operations/` | **Archived:** personas and positioning, launch phases and channels, operations and support, monitoring and incidents, the launch gate |
| `06-open-source-landscape/` | **New (9 Nov):** similar open-source projects on GitHub and in-depth comparisons with Abogen (closest desktop competitor) and Audiblez (most-starred Kokoro converter); an extended landscape of ~70 open-source projects incl. rule-based and AI text rewriting for speech; a **commercial** landscape of ~60 products (the folder holds both, despite its name); a **feature matrix** of all researched products and a **feature list** (93 features with priority, effort and release) for the desktop app; feeds D-45…D-55 |

## 4. Tags

Every file carries exactly one tag in its first lines.

| Tag | Meaning | Changes when |
|---|---|---|
| `[AUDIT]` | Current state as measured: repo, process, debt, gaps. Dated snapshot | Re-audit; never edited to look better |
| `[DOC]` | Target state: specs, architecture, models | Requirements change |
| `[ADR]` | A decision record: chosen option, why, rejected options, revisit triggers | Superseded by a new ADR (never rewritten silently) |
| `[PLAYBOOK]` | Step-by-step execution guide with definition of done per step | The process changes or a step is learned to be wrong |
| `[WORKING]` | Open questions, risks, assumptions, checklists | Continuously; items move out once resolved |

## 5. Provenance labels

Each substantive claim carries one label.

| Label | Meaning | Trust |
|---|---|---|
| `[session decision]` | Stated or chosen by Colin in the advisory session | Binding until changed |
| `[repo fact]` | Read from the repos on 8–9 Nov 2026 (code, docs, git history, GitHub API) | True as of that date |
| `[advisor proposal]` | Claude's recommendation; not yet confirmed by Colin | Must be accepted before acting |
| `[external fact]` | From an external source, with date checked (see `sources-and-provenance.md`) | Re-check before relying on it if older than about 3 months |

Rule: an `[advisor proposal]` becomes a `[session decision]` only when Colin says so. Record that in `../decision-log.md`.

## 6. Reading order

1. This file.
2. `../decision-log.md`: what is settled and what is not.
3. `01-audit-and-roadmap/audit-repo-state-2026-11-08.md` and `audit-process-and-velocity.md`: why change is needed.
4. `01-audit-and-roadmap/adr-007-pivot-open-source-local-app.md`: the current direction (and which earlier ADRs still apply); `adr-001` to `adr-005` for history.
5. `01-audit-and-roadmap/playbook-open-source-desktop-app.md`: what to do now, with the learning track.
6. `04-legal-and-compliance/doc-voice-and-model-licensing.md`: which voices the app may use.
7. `06-open-source-landscape/`: who else does this (open source and commercial), and what to copy from Abogen, Audiblez and paid readers; `feature-list-2026-11-09.md` turns this into the prioritised feature list for v1.0 and later.
8. Pillars 02–05 as the topic requires.

## 6a. File index

| Folder | Files |
|---|---|
| `00-index/` (4) | `README.md`, `../decision-log.md`, `glossary-de-en.md`, `sources-and-provenance.md` |
| `01-audit-and-roadmap/` (15) | `audit-repo-state-2026-11-08.md`, `audit-process-and-velocity.md`, `audit-pdfium-thread-crash.md`, `adr-001`…`adr-005`, `adr-007-pivot-open-source-local-app.md`, `playbook-open-source-desktop-app.md`, `playbook-phase-0-foundation.md`, `playbook-phases-1-4-refactor-roadmap.md`, `playbook-dev-lifecycle-operating-model.md`, `playbook-claude-toolkit-and-skills.md`, `working-tech-risks-and-open-questions.md` |
| `02-product-and-pipeline/` (9 + tools) | `doc-product-truth-and-positioning.md`, `doc-ux-redesign-spec.md`, `doc-mobile-listening-app.md`, `doc-accessibility-requirements.md`, `doc-pipeline-architecture.md`, `doc-prompts-and-detector-rules.md`, `playbook-pipeline-optimization.md`, `working-product-open-questions.md`, `audit-english-rules-vs-spacy-2026-11-09.md`; `tools/extract_prompts.py`, `tools/english_check/` |
| `03-monetization-and-economics/` (7 + tool) | `audit-pricing-consistency.md`, `doc-pricing-model-option-packages.md`, `doc-unit-economics.md`, `doc-payments-and-credit-system.md`, `adr-006-ios-payment-route.md`, `playbook-quota-and-abuse-guardrails.md`, `working-monetization-open-questions.md`; `tools/unit_economics.py` |
| `04-legal-and-compliance/` (6) | `audit-legal-readiness.md`, `doc-gdpr-and-subprocessors.md`, `doc-copyright-and-tos-liability.md`, `doc-voice-and-model-licensing.md`, `playbook-business-and-tax-setup.md`, `working-legal-questions-for-lawyer.md` |
| `05-gtm-and-operations/` (5) | `doc-personas-and-positioning.md`, `playbook-launch-and-channels.md`, `playbook-operations-and-support.md`, `playbook-monitoring-and-incidents.md`, `working-gtm-and-ops-open-questions.md` |
| `06-open-source-landscape/` (7) | `feature-list-2026-11-09.md`, `feature-matrix-2026-11-09.md`, `audit-similar-open-source-projects-2026-11-09.md`, `audit-tts-and-text-rewriting-landscape-2026-11-09.md`, `audit-commercial-tts-and-text-rewriting-landscape-2026-11-09.md`, `audit-abogen-vs-sci2audio-2026-11-09.md`, `audit-audiblez-vs-sci2audio-2026-11-09.md` |

## 7. Related living artifacts (outside this KB)

| Artifact | What it holds | Relation |
|---|---|---|
| Doc "English text preparation: spaCy or sci2audio's rules?" (claude.ai artifact `Y41pYQkGBsockBnktvqcCf`) | Evaluation with test table and pipeline diagram | Same content as `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md`; the KB file is the reference |
| Doc "sci2audio testing strategy: methods and tools" (claude.ai artifact `12FU3RdB3DyyFBLB9PQPRq`) | 24 testing methods ranked for sci2audio (8 high, 8 medium, 4 low, 4 none), pros and cons, the listed tools compared with a favourite or a Python alternative, two audio-specific methods (speech-recognition round-trip, listening test), when to add what (10 Nov 2026) | **The Doc is the reference**; proposed D-58 |
| Doc "sci2audio desktop app: how to start execution" (claude.ai artifact `PRWekgcRWVj9MHkZKWUhLt`) | Start order for the first three weeks, setup checklist with "done when", external tools, execution rules, decisions to close, risks and stop signals (10 Nov 2026) | **The Doc is the reference**; feeds D-56 and amends playbook phase 2 and the toolkit setup checklist |
| Doc "Feature matrix: sci2audio vs. all researched products" (claude.ai artifact `S51tv9ry75nsJDtKoNUyjJ`) | Full matrix: 77 apps × 41 features in two tabs, 68 building blocks × 10 features; tab "Feature list" with 11 sub-tabs: 93 features with description, acceptance criteria, technical details, competitors | **The Doc is the reference for the full matrix and the feature details**; `06-open-source-landscape/feature-matrix-2026-11-09.md` keeps legend, sci2audio rows and findings; `06-open-source-landscape/feature-list-2026-11-09.md` keeps the feature overview table |
| Doc "Commercial landscape: reading aloud and rewriting text for speech" (claude.ai artifact `PU1m3cpCDpYLRoU2FwRqrD`) | ~60 closed-source products in 6 categories, K-list of features | Same content as `06-open-source-landscape/audit-commercial-tts-and-text-rewriting-landscape-2026-11-09.md`; the KB file is the reference |
| Doc "Open-source landscape: reading aloud and rewriting text for speech" (claude.ai artifact `AyborQc4pgEDu4EvDXLQRt`) | ~70 projects in 5 categories with a map diagram | Same content as `06-open-source-landscape/audit-tts-and-text-rewriting-landscape-2026-11-09.md`; the KB file is the reference |
| Doc "Audiblez vs. sci2audio: in-depth comparison" (claude.ai artifact `HbTsHdbBohgqnkgGxmhHVW`) | Comparison with verified code excerpts | Same content as `06-open-source-landscape/audit-audiblez-vs-sci2audio-2026-11-09.md`; the KB file is the reference |
| Doc "Abogen vs. sci2audio: in-depth comparison" (claude.ai artifact `6zkXUjBx6Gg1xhHuV4Pt8r`) | Comparison with a pipeline diagram | Same content as `06-open-source-landscape/audit-abogen-vs-sci2audio-2026-11-09.md`; the KB file is the reference |
| Doc "sci2audio: Paid use cases, profitability and marketing" (artifact `9BV7TduSvjGYj7jiHL4sHn`) | Paid-service analysis (archived), the 9 Nov pivot note, similar open-source projects | Paid part archived by D-41; landscape section = `06-open-source-landscape/audit-similar-open-source-projects-2026-11-09.md` |
| Doc "sci2audio — Development Lifecycle Plan" (claude.ai artifact `SnLnhmCRZWB1YG3A2AZgux`) | Original lifecycle plan with diagrams (change flow, 30-day timeline, weekly toolkit flow) | Superseded in content by `01-audit-and-roadmap/playbook-*`; diagrams remain there |
| Doc "sci2audio — Rewrite, Redesign or Evolve?" (artifact `LX2zVDyJozHcTTRqbFWWms`) | Rewrite decision with architecture and roadmap diagrams | Superseded in content by `adr-001` to `adr-005` |
| Claude skills `ship-issue`, `triage`, `rename-area` (claude.ai account) | Executable procedures for threads | Specified in `playbook-claude-toolkit-and-skills.md` |
| `audiobook-generator/docs/RECHTSLAGE.md`, `docs/datenschutz/` | Legal research and GDPR records in the repo | Source for pillar 04 |
| `docs/design/PRODUCT.md`, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record), `docs/design/DESIGN.md` | Product and design specification | Source for pillar 02 |
| Legal research report (artifact `GPC5mpcFj1Ho2v7C1AvNhC`, referenced in `RECHTSLAGE.md`) | Full legal research with sources; chapter 9 has lawyer questions | Source for pillar 04 |

## 8. Maintenance rules

- New decision → append to `../decision-log.md`; if architectural or strategic, write an ADR and link it.
- Audits are snapshots: re-audit into a new dated file; don't edit old audit numbers.
- `[WORKING]` files are reviewed in the monthly retro (first Sunday of the month): close, promote to ADR, or re-date.
- Keep the KB in the repo (`sci2audio-design/docs/kb/`) so cloud threads can read it; root `CLAUDE.md` links the files threads need.
