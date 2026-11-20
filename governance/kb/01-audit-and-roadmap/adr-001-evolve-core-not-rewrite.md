# ADR-001: Evolve the core, don't rewrite. Rebuild only the client

`[ADR]` · Status: **Proposed** (advisor, 8 Nov 2026; refined 9 Nov after Colin's answers F-05 to F-07; no objection recorded) · Decider: Colin · Related: ADR-002, ADR-003, ADR-004, ADR-005

> **Still valid after ADR-007:** the core is extracted and evolved, not rewritten.

---

## 1. Context

- Colin asked (8 Nov) whether a **full redesign, not just UI/UX but also technical**, is a good idea, given plans for Android, iOS, Windows and Mac apps and the planned English translation, and whether to use the translation as the moment to **refactor the whole codebase**. [session decision] F-03, F-04
- The codebase is **14 days old** (repo created 26 Oct 2026): about 51k Python lines + 12k JS/CSS lines, 1,279 tests, 306 PRs. [repo fact]
- The core (PDF reading, pre-analysis, routing, rewriting, TTS, read-along) is strong; the edges (`web.py` monolith, threads as jobs, vanilla JS front end, German names) are debt. See `audit-repo-state-2026-11-08.md`. [repo fact]
- A complete UX redesign already exists on paper and as a prototype in `sci2audio-design` (`docs/design/PRODUCT.md`, a 47 kB `docs/design/DESIGN.md`, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record), two review rounds, clickable vanilla-JS prototype). [repo fact]
- **No users yet; Colin works alone** (about 20 h/week); verification, not code generation, is the bottleneck. [session decision] F-02, F-05, F-06

## 2. Decision

1. **Keep the processing core in Python and refactor it in place**, protected by the existing tests and sample PDFs: extraction, layout, pre-analysis (20 detectors), routing, chunking, rewriting, TTS, encoding, read-along.
2. **Re-architect the boundary**: split `web.py` into a versioned API, a job worker and page routes (ADR-002).
3. **Rebuild the client once**, from the `sci2audio-design` spec, against the new API (ADR-003). This is the only rewrite worth doing.
4. **Translate to English as a separate, mechanical rename step** before the re-architecture (ADR-004).
5. **Because there are no users**: switch to the new client in one go once it covers the whole flow; no surface-by-surface user migration, no compatibility URLs. (Refinement 9 Nov, F-05.)

In short: keep the brain, replace the face, put a proper API between them.

## 3. Options considered

| | A. Big-bang rewrite | **B. Evolve core, rebuild client (chosen)** | C. Continue as is |
|---|---|---|---|
| What happens | New repo and structure, English, new UI; switch when on par | Tests stay the spec; split `web.py` into API + worker + pages; new client against the API; translate module by module | Keep adding features to the current structure |
| Product progress meanwhile | Stops until on par; likely months at 20 h/week | Continues; each step ships on its own | Fast now, slowing as `web.py` (7,245 lines) and `app.js` (4,579 lines) grow |
| Risk | High: subtle PDF and timing behaviour silently lost; two systems in parallel | Low to medium: every step reversible and checked by the same tests | Rising: no API means apps are blocked; thread-safety bugs in the web process |
| What you keep | Ideas and test files, re-ported by hand | Everything that works | Everything, including the debt |
| Enables apps | Eventually | After phase 2 (API) | No |
| Fit for one person with Claude | Poor: verifying a whole system at once | Good: small PRs, each checked | Until about the next platform |

## 4. Rationale

### Why not rewrite, even though the code is only 2 weeks old
- **The code was fast to write; its knowledge wasn't.** 306 PRs encode hundreds of edge cases: broken PDF font encodings (`kodierung.py`, glyph learning via OCR), footnotes across page breaks, tables with lines, running headers and footers, hyphenation, gender forms, citation styles, homographs, foreign words, chapter detection from bookmarks or headings or numbered lines, read-along timing per audio sample, Azure word boundaries, M4B without gaps. A rewrite re-discovers these one bug at a time.
- **Verification is the bottleneck, not typing.** Claude could regenerate 50k lines quickly, but someone has to verify that the new system reads PDFs as well as the old one. The existing tests and 19 sample PDFs are exactly that verification. A rewrite would first have to port them, then fight every diff.
- **Product stall.** Big-bang means no shippable progress until parity. With no users that's affordable in theory, but the launch (and learning from real users) moves out by months.
- **The parts that are actually wrong are separable.** The debt is concentrated at the edges (`web.py`, jobs as threads, `app.js`), and those can be replaced individually (strangler pattern, ADR-002).

### Why the client *is* rebuilt
- The current front end is vanilla JS that writes HTML via `innerHTML` (107× in `app.js`), plus HTML assembled in Python strings. It doesn't implement the `sci2audio-design` spec 1:1 and can't be reused by native apps.
- The target UI is fully specified already, so a rebuild is implementation, not design exploration.
- No users means no migration cost: switch once at parity.

## 5. Consequences

**Positive**
- Product keeps shipping during the transformation; every phase ends in a working system.
- Existing tests, sample PDFs, deploy gates and evaluator keep their value and guard each step.
- Apps become possible after phase 2 without touching the core again.

**Negative / costs**
- Two front ends exist for a while (old `app.js` and the new client) until the switch (phase 3).
- Refactoring in place needs discipline: rename-only PRs, behaviour-preserving splits, feature freezes per area while it's being moved.
- Some debt stays longer (German stored names, mixed table names) because changing stored data has migration cost (glossary §4).

**Guardrails (mandatory)**
- Every refactor PR keeps the test counts identical (same passed/skipped) unless it intentionally adds tests.
- No behaviour change in rename or move PRs; findings go to new Issues.
- `main` must be green before any refactor starts (fix `test_rechte.py` first).
- One area per thread; never two threads moving the same module.

## 6. Rejected alternatives in detail

| Alternative | Why rejected |
|---|---|
| Big-bang rewrite in a new repo | See §4; high silent-regression risk, months without progress, poor fit for a solo founder |
| Rewrite the core in another language (e.g. TypeScript, to share code with the client) | Loses the Python ecosystem the core depends on (pypdfium2, Tesseract bindings, onnxruntime, wordfreq, Azure SDK, ffmpeg tooling); no benefit for users |
| Keep the current front end and wrap it for mobile | Doesn't meet the design spec; `innerHTML` patterns; Apple's minimum-functionality risk for wrapped web apps; can't share a clean API layer |
| Incrementally improve `app.js` towards the design spec | Effort similar to a rebuild, result still without a component model and with weak typing |

## 7. Revisit triggers

Revisit this ADR if any of these become true:
- The test suite turns out to be an unreliable spec (many tests asserting implementation details, or a high flaky rate after phase 0).
- Phase 2 (API + worker) takes more than about twice the planned PRs because `web.py` coupling is deeper than audited.
- A different server language becomes mandatory (e.g. a hosting constraint).
- A buyer, investor or contributor requirement changes F-06 (solo).

## 8. Open questions

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | Does Colin accept the strategy as a binding decision? | Treat as Proposed; don't start phase 2 without explicit OK |
| Q2 | Target dates for M1 (stable test phase) and M2 (paid launch), which set how much of phases 1–3 must happen before launch | Launch on the current web client after phase 0; refactor phases continue after launch |
| Q3 | Should the paid launch wait for the new client (phase 3)? | No: launch earlier on the current UI if legal and payment items are done; new client follows. Decide explicitly |
