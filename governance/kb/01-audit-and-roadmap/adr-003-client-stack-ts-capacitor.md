# ADR-003: Client stack: TypeScript web client + Capacitor

`[ADR]` · Status: **Proposed; framework choice open** (advisor, 8 Nov 2026; confirmed 9 Nov that Wieder in Ordnung doesn't share the stack, F-07) · Decider: Colin · Phases: 3 (web client), 4 (apps) · Related: ADR-001, ADR-002, ADR-005, `02-product-and-pipeline/doc-ux-redesign-spec.md`

> **Deferred by ADR-007 (9 Nov 2026):** v1 keeps the existing local web UI; a TypeScript client is an optional learning exercise after v1.0.

---

## 1. Context

- **Current client** `[repo fact]`: vanilla JS without a build step: `static/app.js` 4,579 lines (107 `innerHTML` writes, 64 `/api/` calls), `bearbeiten.js` 2,979 (editor), `app.css` 3,062, `i18n.js` 139, `geraetestimme.js` 438 (Web Speech API), `browserstimme.js` 145 + `browserstimme-worker.js` 150 (Piper Thorsten via onnxruntime-web/WebAssembly, phonemes from the server, lamejs for MP3), `testleitfaden.js` 498 (guided test). Plus server-rendered HTML in `startseite.py`, `admin.py`, `web_page.html`, `demo_login.html`.
- **Target UI** `[repo fact]`: fully specified in `sci2audio-design` (`docs/design/DESIGN.md` about 47 kB, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §1–10 with required states in §9, `docs/design/PRODUCT.md`), with a clickable vanilla-JS prototype (`prototype/`: account, admin, compare, editor, local, player, quickstart, shared, site). `docs/design/PRODUCT.md` platform: "web"; every surface usable on phone and desktop; admin desktop-first.
- **Platform plan** `[session decision]`: Android, iOS, Windows and Mac apps were mentioned (F-03); refined to web first, then a listening-first iOS/Android app (ADR-005).
- **Solo, Claude-built** `[session decision]`: Colin alone (F-06); almost all code written by Claude threads, so stack popularity directly affects output quality.
- **No shared stack with Wieder in Ordnung** `[session decision]` F-07 (its app is a vanilla-JS PWA, reworked separately).

## 2. Requirements the client must meet

| # | Requirement | Source |
|---|---|---|
| R1 | Implement the `sci2audio-design` system 1:1 (tokens, components, states, light/dark) | `docs/design/DESIGN.md`, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §9 |
| R2 | German first, English complete; German text runs longer and layouts must survive it | `docs/design/PRODUCT.md` |
| R3 | Quick Start (Upload → Text → Voice → Order), run page, result page with player | `docs/design/PRODUCT.md` |
| R4 | Player with read-along: highlight the original's sentence, sample-accurate timing, tap to jump, chapter marks, speed, figures, markers and notes | `mitlesen.py`, `notizen.py`, `abbildungen.py` |
| R5 | Editor: write in the paragraph, compact bar, split screen with original view, regions, omissions, pronunciation | `bearbeiten.js`, `bearbeitung.py`, `original.py` |
| R6 | Client-side voices: device voice (Web Speech API on web; platform TTS in apps) and Thorsten via ONNX/WebAssembly | `geraetestimme.py`, `browserstimme.py` |
| R7 | Accessibility (dyslexia, low vision): keyboard, screen readers, contrast, focus, reduced motion | `docs/design/PRODUCT.md` users |
| R8 | Apps: background audio, lock-screen controls, offline downloads, share-to-app for PDFs, CarPlay/Android Auto (later) | ADR-005 |
| R9 | Typed API client generated from the OpenAPI spec (ADR-002) | ADR-002 |
| R10 | Admin area (desktop-first) | `docs/design/PRODUCT.md` |
| R11 | Public site (landing, prices, FAQ, articles, legal) server-rendered for SEO and speed | ADR-002 §3.1, `inhalte/` |

## 3. Decision (proposed)

| Layer | Choice | Status |
|---|---|---|
| Language | **TypeScript** | Proposed |
| UI framework | **React** (via Vite, single-page app behind login) | **Open** (O-05); alternatives Svelte, Vue |
| API client | Generated from `openapi.json` (e.g. `openapi-typescript` + a thin fetch wrapper); server state via a query library (e.g. TanStack Query) | Proposed |
| Styling | Design tokens extracted from `docs/design/DESIGN.md` into one tokens file (CSS custom properties); component CSS per component; no CSS framework that fights the spec | Proposed |
| i18n | Keep the German-string-as-key catalogue initially (1,651 strings in `sprachen/en/app.json`); migrate to stable keys later | Proposed |
| Mobile | **Capacitor** wrapping the same web client for iOS and Android, plus native plugins for audio session/background playback, file sharing, secure token storage | Proposed |
| Desktop | No separate app now; installable PWA; Tauri only if local mode needs a desktop shell (ADR-005) | Proposed |
| Public site | Stays server-rendered by the Python app (restyled to the design tokens) | Proposed |
| Testing | Vitest (units), Playwright (end-to-end: upload → run → player on staging), visual checks against the prototype | Proposed |
| Hosting | Static build served by the API app or a CDN; same origin as the API for cookies | Proposed |

## 4. Options considered

| Option | Covers | Fit for sci2audio | Against | Verdict |
|---|---|---|---|---|
| **TypeScript web client (React) + Capacitor** | Web, iOS, Android; desktop via PWA/Tauri | Reuses the design system 1:1; one codebase; most common stack, so Claude writes it best; the Thorsten ONNX/WebAssembly voice works unchanged inside the Capacitor WebView | Audio/offline need native plugins; Apple may reject apps that look like a website in a wrapper, so the app needs real native value (playback, offline) | **Proposed** |
| TypeScript + Svelte/SvelteKit + Capacitor | Same | Less code, fast; good fit for a content-heavy UI | Smaller ecosystem; somewhat less training data for Claude; fewer ready components | Alternative for O-05 |
| TypeScript + Vue + Capacitor | Same | Approachable; good ecosystem | Middle ground with no decisive advantage here | Alternative |
| Flutter | All platforms incl. web and desktop | Very good native feel and audio | Design system rebuilt in Dart; web output weaker for the public site and SEO; second language next to Python; ONNX voice needs a separate path | Rejected |
| React Native / Expo (+ separate web) | iOS, Android, web (react-native-web); desktop partly | Native feel | In practice two UIs (web and app); desktop support less mature; the editor (R5) is hard in React Native | Rejected |
| Native Swift + Kotlin + web | Best platform fit | Three codebases for one person | Rejected |
| Keep vanilla JS (no framework) | Web; PWA | No build step; what the prototype uses | No component model for a large app; `innerHTML` safety; no typed API client | Rejected for the app; fine for small static pages |

## 5. Advisor pre-analysis

- **The decisive factor is Claude's output quality, not Colin's taste.** With a solo founder and Claude writing most code, the stack with the most real-world examples (TypeScript + React) gives the most reliable code and the best plugin support (`typescript-lsp`, `frontend-design`, Playwright).
- **Capacitor is right because the hard part is the web UI**, not native widgets. The editor and the read-along player are inherently web-like (rich text, precise highlighting); building them twice (web + React Native) would double the riskiest UI work.
- **The Thorsten-in-browser voice is a hidden advantage of the WebView route**: onnxruntime-web/WebAssembly runs inside Capacitor, so the free voice works in the app without porting.
- **Apple risk (guideline on minimum functionality):** a thin wrapper around the website may be rejected. Mitigation: the app's core is native-backed listening (library, offline downloads, background audio, lock screen, CarPlay), not a website mirror. That fits the product anyway (ADR-005).
- **The prototype is the spec, not the code base.** Port page by page; don't copy prototype JS.
- **Keep the public site out of the SPA.** SEO articles in `inhalte/` and the landing page stay server-rendered; this keeps the SPA simpler (no SSR framework needed).

## 6. Consequences

**Positive:** one UI codebase for web and apps; typed contract with the API; design system enforced by tokens and components; testable end to end.

**Negative:** a build toolchain (Node, Vite) enters the repo; two front ends coexist until the switch; native plugin maintenance for audio; Apple/Google review cycles from phase 4.

## 7. Revisit triggers
- Capacitor audio/background playback proves unreliable on iOS in a phase-4 spike → consider a native audio module or a native player screen.
- Performance of the editor on mid-range Android is unacceptable → profile; consider a lighter framework.
- A desktop app becomes a requirement (local mode demand) → evaluate Tauri with the same web client.

## 8. Critical open questions

| # | Question | Why it matters | Default |
|---|---|---|---|
| Q1 (O-05) | React, Svelte or Vue? | Ecosystem and Claude quality vs. code size | React |
| Q2 | Same repo (monorepo `client/` folder) or separate repo for the client? | Cloud threads see one repo more easily; CI simpler | Same repo (`audiobook-generator/client/`), design repo stays the spec |
| Q3 | Where does the admin area live: new client or keep server-rendered? | Admin is desktop-first and internal | Keep server-rendered until after launch; port later |
| Q4 | Switch criterion: what exactly is "full flow covered"? | One-shot switch (F-05) needs a clear checklist | All `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §3–§7 surfaces + §9 states pass Playwright on staging |
| Q5 | i18n: keep German-string keys or move to stable IDs during the rebuild? | String keys break when German copy changes | Move to stable IDs in the new client; generate from the current catalogue |
