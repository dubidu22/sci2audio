# ADR-007: Pivot to a free, open-source desktop app (learning project)

`[ADR]` · Status: **Decided** (Colin, 9 Nov 2026: "yes. I think I am sure about it.") · Decider: Colin · Supersedes in part: ADR-002, ADR-003, ADR-005, ADR-006; archives pillars 03 and 05 and most of pillar 04 · Related: `playbook-open-source-desktop-app.md`, `decision-log.md` D-41, `06-open-source-landscape/` (similar projects, Abogen comparison)

---

## 1. Context

- sci2audio started as a tool Colin built for himself. [session decision]
- The paid-launch analysis (Batches 3–5, the doc "sci2audio: Paid use cases, profitability and marketing") showed:
  - a narrow legally safe paid market;
  - thin student margins (≈ €0.30–1.80 per audio hour after reverse-charge VAT);
  - strong free competitors;
  - a long list of legal, tax and operational work before the first euro.

  Realistic outcome: covering running costs, rarely more. [advisor proposal, accepted as context]
- Colin can't afford a lawyer or any copyright litigation risk now, and doesn't want to found a GmbH/UG. [session decision, 9 Nov]
- Colin's actual goal: **learn proper AI-assisted development methods** and use that knowledge for future client work, while keeping a tool he can use himself. [session decision, 9 Nov]

## 2. Decision

sci2audio becomes a **free, open-source desktop application** that runs entirely on the user's own computer:

1. **No hosted service for other people, no payments, no accounts, no uploads to any server.**
2. **No paid APIs.** No Anthropic, Azure, OpenAI, ElevenLabs or Edge in the public app. Speech comes from **local, freely licensed voices**.
3. **The core is the rule-based pre-analysis** ("Keine Bearbeitung" and "Vorlesbar"): citations, footnotes, hyphenation, abbreviations, numbers, gender forms, headings, tables and figures handled without AI.
4. **Desktop first** (Windows, macOS, Linux). Phones play the exported MP3/M4B files in any audiobook or podcast app. A phone app is optional and later (Android via F-Droid; no iOS because of GPL vs. App Store terms).
5. **Licence: GPL-3.0** for the whole app (decided in D-42, 9 Nov), compatible with espeak-ng and Piper.
6. **The hosted demo at sci2audio.com is retired**; the domain becomes a static project site (download, docs).
7. **The project's main purpose is learning.** Every phase is run with the AI-assisted development methods from pillar 01 (lifecycle, skills, reviews, CI, ADRs) and documented, so it can serve as a reference for client work.

## 3. Why

| Need | How the decision meets it |
|---|---|
| No legal risk | The user converts their own files on their own device (their private copy); Colin distributes a tool, not copies. No consumer contracts, no personal data processed by Colin, no hosting liability |
| No costs | No API or hosting costs for other users' runs; GitHub hosts code, releases and the site for free |
| Learning value | A real 51k-line codebase to extract, refactor, test, package and release with Claude: the full lifecycle at small scale |
| Own use | Colin keeps using it. For personal runs he may still use his own API keys in a private, local configuration (his own private copies, his own cost), outside the public app |
| Reference for client work | A public repo, ADRs, a knowledge base and a documented AI-assisted workflow are concrete proof of method |

## 4. Options considered

| Option | Why not (now) |
|---|---|
| Paid hosted service, green texts only (Batches 3–5) | Legal and tax overhead, thin margins; needs a lawyer before launch |
| "Middle path" (paid voice-only on protected texts) | Deliberate copyright risk; excluded by Colin's risk tolerance |
| Local app with paid licence / bring-your-own-key | Still a consumer sale (terms, withdrawal, tax); can be revisited after v1.0 |
| Engine licensing / B2B services | Requires sales time and contracts; possible later as client work built on this reference |
| Stop the project | Loses the learning vehicle and Colin's own tool |

## 5. Consequences

**Positive:** no legal blockers, no running costs, a clear learning roadmap, public portfolio material.

**Negative:**
- The AI rewrite levels (Klar & Direkt, Akademisch & Flüssig) leave the public app. A free local LLM could return as an optional extra later.
- Kokoro German needs PyTorch, which makes installers large (hundreds of MB to GBs) until an ONNX path is found.
- Unsigned installers trigger OS warnings: macOS notarization needs a paid Apple Developer account, and Windows code signing costs money.
- No revenue.

**Status of earlier documents:**

| Document set | New status |
|---|---|
| ADR-001 (evolve the core), ADR-004 (English rename as its own step) | **Still valid**; the rename becomes more useful for an international open-source audience |
| ADR-002 (API + worker split) | **Superseded**: no server; a local job runner is enough |
| ADR-003 (TypeScript + Capacitor client) | **Deferred**: v1 keeps the existing local web UI; a new client is an optional learning exercise |
| ADR-005 (web first, then a listening app) | **Superseded** by desktop first |
| ADR-006 (iOS payment route) | **Archived** (no payments) |
| Pillar 01 playbooks (phase 0, lifecycle, toolkit) | **Valid**, adapted in `playbook-open-source-desktop-app.md` (no staging/Fly, no spend caps; CI, tests, reviews, releases stay) |
| Pillar 02 (product, pipeline, accessibility) | **Valid** for the rule-based core; AI-level and hosted-UX parts archived |
| Pillar 03 (monetization) | **Archived** |
| Pillar 04 | `doc-voice-and-model-licensing.md` **active**; GDPR doc used once for the shutdown; the rest **archived** |
| Pillar 05 (GTM and operations) | **Archived** |

## 6. Revisit triggers
- Users of the open-source app ask for a hosted version or paid support.
- A client wants the engine licensed or customised (paid client work, contract-based).
- Funding with an open-source requirement fits the project (e.g. a Prototype Fund round on accessibility or public interest).

## 7. Advisor pre-analysis
- This is the right call for the stated goal. The hard part of sci2audio was never the code; it was the business around it. Removing the business keeps the interesting engineering and the learning.
- The extraction is itself the best learning exercise: splitting a 7,245-line `web.py`, deleting cloud paths safely under tests, and packaging Python for three operating systems. These are realistic client problems.
- Keep the knowledge base: the archived pillars document a full commercial analysis, which is also useful material for client conversations.

## 8. Critical open questions
| # | Question | Default |
|---|---|---|
| Q1 | GPL-3.0 or keep MIT with GPL parts only as separate processes? | **Closed 9 Nov: GPL-3.0** (D-42) |
| Q2 | Keep the AI levels as an optional "bring your own key" plugin later? | Not in v1; revisit after v1.0 |
| Q3 | Repository name and home: rename `audiobook-generator` or a new public repo `sci2audio`? | New public repo, fresh history |
