# ADR-005: Platform scope: web first, then a listening app; no desktop apps for now

`[ADR]` · Status: **Proposed** (advisor, 8 Nov 2026; refined 9 Nov after F-05 "no users yet") · Decider: Colin · Phase: 3 (web), 4 (apps) · Related: ADR-002, ADR-003, ADR-006 (iOS payment, pillar 03), `02-product-and-pipeline/doc-mobile-listening-app.md`

> **Superseded by ADR-007 (9 Nov 2026):** desktop first, local only; phones play exported files; Android optional later, no iOS.

---

## 1. Context

- Colin's stated future plan: expand to **Android, iOS, Windows and Mac apps**. [session decision] F-03
- **No users yet.** [session decision] F-05. Demand for any platform is unvalidated.
- `docs/design/PRODUCT.md` platform today: "web"; "every surface must be fully usable on phone and touch as well as desktop"; admin desktop-first. [repo fact]
- Two installations already share one design: **online** (sci2audio.com) and **local** ("this computer": own keys, no limits, prices shown but nothing charged; batch mode and run logs only locally). [repo fact]
- Users: students and researchers (German first, humanities and social sciences) listening "while commuting"; accessibility users (dyslexia, low vision); power users and lecturers; self-hosters; the operator. [repo fact] `docs/design/PRODUCT.md`
- Prepaid credit sold via Stripe; selling digital goods inside iOS apps is generally subject to Apple's in-app purchase rules, with regional exceptions (US, EU) that changed repeatedly since 2025. [external fact, checked 8 Nov 2026]

## 2. Decision

| Platform | Decision | When | Gate |
|---|---|---|---|
| **Web** (desktop + phone browsers) | Main product; all features | Now; new client in phase 3 | — |
| **Android + iOS** | One **listening-first** app from the web client codebase (ADR-003): library, mini-player, full player with read-along, offline downloads, background audio, lock-screen controls; later CarPlay/Android Auto; upload, editing and ordering start as web views | Phase 4 | (a) `/api/v1` stable and token auth live; (b) evidence of mobile listening demand; (c) iOS payment route decided (ADR-006) |
| **Windows + Mac** | **No separate apps.** Web covers editing and long sessions; local mode already runs on the user's computer. Installable PWA for a desktop icon | Not planned | Revisit only if local mode has real users who need a desktop shell (then Tauri with the same web client) |
| **Local mode** | Keep as is until decided (O-07); the phase-2 worker must keep supporting it (SQLite + in-process worker) | — | Decide before phase 2 design is final |

## 3. Why (rationale)

- **Native value is listening, not uploading.** Commuting students upload a PDF once (usually on a laptop, where the file is) and listen many times on the phone. What the browser does badly on phones (background playback, lock screen, offline, car integration) is exactly what an app adds.
- **Desktop apps add no user value** over the web for editing, and local mode already exists for people who want sci2audio on their own machine.
- **No users → validate before building.** Each native platform adds store review cycles, signing, plugin maintenance and (iOS) payment rules. Building them before anyone uses the web product spends the scarcest resource (20 h/week) on unvalidated demand.
- **Apple's minimum-functionality rule**: wrapped websites can be rejected; a listening-first app with offline and background audio has clear native value.

## 4. Options considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Web first, listening app later, no desktop apps (chosen)** | Focus; validated demand before native effort; matches the commuting use case | Mobile-first users wait for the app | **Proposed** |
| All four native platforms in parallel with the web rebuild | Matches the original ambition (F-03) | 4–5 release targets for one person; store and payment complexity before any user | Rejected |
| Mobile app first, web second | Phone-native audience | Uploading and editing on phones is poor; the spec is web-first; payment rules hit first | Rejected |
| Desktop apps (Electron/Tauri) for local mode | Easier install for self-hosters | Self-hosters are the smallest group; packaging Python + ONNX + ffmpeg + Tesseract per OS is heavy | Rejected for now |
| PWA only, never native | Cheapest | iOS PWA background audio and storage are more limited than native (verify in a phase-4 spike); no store presence | Interim step only |

## 5. Advisor pre-analysis

- **The real platform question is "who is the first paying user, and where do they listen?"** With zero users, the answer should come from the guided test and the first launch cohort, not from a platform wish list. Instrument the web player now: share of listening on mobile browsers, session length, how often playback stops when the screen locks.
- **A PWA is a cheap demand probe.** An installable web app with offline downloads (service worker) on Android costs little in phase 3 and shows whether people want "sci2audio on the home screen" before committing to store apps.
- **iOS is the expensive platform** (payment rules, review, CarPlay entitlements). Android can go first in phase 4 if demand is real and the iOS payment route is unclear.
- **Accessibility users may be the strongest app case.** Dyslexic students listening while reading along on a tablet is a high-value scenario; validate with that group (pillar 05).
- **Local mode is a strategic fork.** It serves self-hosters and keeps a "no limits, own keys" story, but it constrains the architecture (SQLite path, in-process worker) and the business (no revenue). Decide deliberately (O-07).

## 6. Consequences

**Positive:** one product surface to perfect before launch; native work starts with an API, a design system and real usage data.

**Negative:** no app-store presence at launch; mobile listening stays browser-based (screen lock may pause playback on some phones) until phase 4.

## 7. Revisit triggers
- Data after launch shows a majority of listening on mobile browsers with frequent interruptions → pull phase 4 forward (Android first).
- A university or accessibility partner requires an app → re-prioritise.
- Local-mode downloads or requests reach a meaningful number → evaluate a Tauri desktop shell.
- Apple changes payment rules again → update ADR-006 before committing to iOS.

## 8. Critical open questions

| # | Question | Why it matters | Default |
|---|---|---|---|
| Q1 | What evidence counts as "mobile listening demand"? | Gate (b) for phase 4 | Advisor proposal: ≥ 30% of listening minutes on mobile browsers **and** ≥ 5 of the first 50 active users asking for offline/background play |
| Q2 | Keep local mode as a product (O-07)? | Architecture (SQLite/in-process worker) and desktop decision | Keep until phase 2 design; decide then |
| Q3 | Android first or both mobile platforms at once? | Effort and payment complexity | Both from one codebase if the iOS payment route is clear; otherwise Android first |
| Q4 | Will the first app version sell credit at all? | Determines ADR-006 complexity | No: play and sync only, buying on the web (subject to current Apple rules) |
| Q5 | CarPlay/Android Auto in the first app version? | Entitlements and review effort | No; second app version |
