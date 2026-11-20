# Mobile listening app (iOS + Android): scope and specification

`[DOC]` · Target-state spec for phase 4 (ADR-005), built from the web client with Capacitor (ADR-003). Status: `[advisor proposal]`; **conditional**: phase 4 starts only after the gate in ADR-005 (stable `/api/v1` + token auth, evidence of mobile listening demand, iOS payment route decided in ADR-006). Facts about today's web client are `[repo fact]` (9 Nov 2026).

---

## 1. Why an app at all

| Job to be done | Web today | What an app adds |
|---|---|---|
| Upload a PDF once, configure, pay | Good on desktop; phone flow broke at 375px (critique 6 Nov) | Little (share-to-app later) |
| **Listen many times while commuting** | Works in mobile browsers: `navigator.mediaSession` already sets lock-screen metadata and controls (`static/app.js:998`); PWA manifest exists (`static/icons/manifest.webmanifest`, icons 192/512/maskable) | **Reliable background playback, offline downloads, resume position across devices, car integration, OS-level media controls**: the browser's weak spots |
| Read along (accessibility) | Read-along player in the browser | Same, offline, on tablets; larger-text and dark presets |
| Get notified when a long run finishes | E-mail | Push notification |

**Conclusion:** the app is a **listening client**. Production (upload, text level, editor, order, payment) stays on the web in v1.

## 2. v1 scope

| In v1 | Out of v1 (later or never) |
|---|---|
| Sign-in (e-mail code → device token; Google) | Upload from the phone (v2: share sheet "Open in sci2audio") |
| Library ("Meine Hörbücher"): runs with status, title, cover, duration, progress | Text editor (web only) |
| Full player: chapters, speed (0.5–2×), ±15 s / ±30 s skip, sleep timer, resume line | Ordering and paying (see §7) |
| **Read-along of the original** (same JSON as web) | CarPlay / Android Auto (v2) |
| Figures shown when mentioned (if the run has them) | On-device generation (device voice via platform TTS, Thorsten via ONNX) (v2+) |
| Markers and notes (create, list, sync) | Batch, run logs, admin |
| **Offline downloads** per book: audio + read-along + figures + metadata | Social/sharing features (conflicts with "own use only") |
| Background audio, lock-screen controls, headset buttons, audio-focus/interruption handling | Multiple simultaneous downloads beyond a small queue |
| Push notification: run finished / failed (nothing charged) / files expire in 2 days | — |
| Light/dark/system; DE/EN UI; dynamic type | — |
| Retention awareness: "available until …" (7 days; 30 for paid runs) and auto-removal of expired downloads | — |

## 3. Screens (native conventions, design-system tokens)

| Screen | Content | Notes |
|---|---|---|
| Sign-in | E-mail → 6-digit code (6 slots, 2.75 × 3.5rem on phones), Google | Same rules as web: code valid 30 min, 5 tries |
| Library (tab 1) | Ruled list rows (no cards): cover, title (document title, never raw file name), duration, listening progress groove, status word + icon (Läuft/Fertig/Abgebrochen/Fehler, kostenlos/Abgelaufen), download state | Filter chips: Alle, Läuft, Fertig, Heruntergeladen |
| Mini-player | Persistent above the tab bar: title, play/pause, progress groove with signal playhead | Signal = playhead only |
| Player (full) | Clock (elapsed), chapter list, transport, speed, sleep timer, tabs: Mitlesen / Kapitel / Notizen / Abbildungen / Details | Transport docked at the bottom |
| Read-along | Read-along type (400, ≈ 1.125–1.3125rem, max 40rem): quiet ink at rest, current paragraph in ink, spoken sentence at 800 on the wash; tap a sentence to jump; unverified sentences light their paragraph | Must stay smooth on 1,000-page books (virtualised list) |
| Downloads (tab 2) | Per book size, available-until date, delete; total storage; Wi-Fi-only toggle | |
| Settings (tab 3) | Appearance, language, playback defaults (speed, skip lengths), notifications, storage, account (opens web for account deletion), legal links | |
| Web views | "Neues Hörbuch", "Guthaben", "Einstellungen (alle)", "Text bearbeiten" open the web client (in-app browser or system browser per §7) | |

## 4. Offline downloads

| Item | Format | Size estimate |
|---|---|---|
| Audio | MP3 96 kbps mono (server encodes MP3 at 96k: `tts.py` ffmpeg `-b:a 96k`) or the run's M4B | ≈ 43 MB per audio hour (96 kbit/s × 3,600 s ÷ 8); a 35,000-word book (≈ 4.4 h at 8,000 words/h) ≈ 190 MB `[advisor proposal]` arithmetic |
| Read-along | The run's `.mitlesen.json` (original blocks and sentences with seconds) | Small (≪ 1 MB for a typical book; verify on a 1,000-page book) |
| Figures | Images referenced by the read-along | Varies |
| Metadata | Title, author, cover, chapters, retention date, cost note, "KI-generiert" label | Small |

Rules:
- Downloads use time-limited signed URLs from `/api/v1` (Tigris presigned), resumable.
- **Retention is enforced on the device too**: when the server-side retention ends (7 days; 30 for paid), the app deletes the local copy unless the user explicitly saved the audio file to the device's file system (export). This keeps the privacy promise "files are deleted after N days" honest. Export follows the "own use only" reminder.
- Listening position syncs (last write wins, per book); notes and markers sync with conflict-free IDs.

## 5. Audio behaviour

| Behaviour | Requirement |
|---|---|
| Background playback | Continues with screen locked and app backgrounded (iOS audio session category "playback"; Android foreground media service) |
| Lock screen / notification controls | Title, chapter, cover, play/pause, skip ±, scrubbing |
| Interruptions | Pause on call or other audio focus; resume when appropriate; pause on headphone unplug |
| Speed | 0.5–2× with pitch correction |
| Chapter navigation | From M4B chapter marks or the read-along JSON |
| Sleep timer | End of chapter, 15/30/60 min |
| Resume | Position saved every few seconds and on pause; synced to server |
| Accessibility | All controls labelled for VoiceOver/TalkBack; large hit targets (≥ 44pt iOS / 48dp Android); respects reduce-motion and dynamic type |

Implementation (ADR-003): Capacitor + a maintained native audio/media-session plugin (to be chosen in the phase 4 spike). The web `<audio>` element in a WebView isn't reliable for background playback on iOS; the spike must prove this on a real device.

## 6. Notifications
| Event | Channel | Content |
|---|---|---|
| Run finished | Push (+ e-mail as today) | "„Titel“ ist fertig: 4 h 12 min" |
| Run failed | Push | "… konnte nicht fertig werden. Es wurde nichts berechnet." |
| Files expire in 2 days | Push | "… wird am … gelöscht. Jetzt herunterladen?" |
| Login code | E-mail only | — |
Opt-in per kind (mirrors the e-mail settings with per-kind unsubscribe).

## 7. Payments and store rules (link to ADR-006, pillar 03)

| Option | v1 behaviour | Constraint |
|---|---|---|
| **A. Play-and-sync app (default proposal)** | The app shows the library and plays what was bought on the web; no prices, no top-up buttons, no links that steer to buying, unless allowed in the storefront | Must be verified against the current App Review Guidelines for "multiplatform services" and reader-style apps; rules changed repeatedly since 2025 `[external fact, 8 Nov 2026]` |
| B. External purchase link | "Guthaben aufladen" opens the website in the system browser | Allowed in the US storefront after the Epic ruling (history of commission demands and injunctions) and in the EU under DMA terms with their own fees and entitlement; region-specific UI needed |
| C. In-app purchase | Credit packs as consumable IAP | Apple/Google commission must be priced in; separate price lists per store; refunds via the store |
Android/Google Play has its own billing rules; check them in the same review. **Decision required before the phase 4 spike** (ADR-006).

## 8. Privacy and compliance specifics
- Store privacy labels / data-safety forms must match `docs/datenschutz/verarbeitungsverzeichnis.md` (e-mail, usage data, documents processed on the server; no tracking SDKs).
- No third-party analytics SDK in v1; server-side metrics only.
- "KI-generiert" label visible in the player and in exported audio metadata (EU AI transparency).
- Account deletion reachable from the app (store requirement): opens the web account page or calls the API.
- Device tokens revocable in the web account page ("Geräte").

## 9. Technical dependencies (from phase 2/3)
| Dependency | Phase | Status |
|---|---|---|
| `/api/v1` for runs, results, player data, notes, progress | 2 | Planned (ADR-002) |
| Token auth per device, refresh, revocation | 2.21 | Planned |
| Presigned download URLs (Tigris) | 2.22 | Planned |
| Push service (APNs, FCM) + device registration endpoint | 4 | New |
| Shared client codebase + tokens | 3 | Planned (ADR-003) |
| Native audio plugin | 4 spike | To select |

## 10. Spike plan (phase 4.1, 1–2 weeks)
1. Capacitor shell around the new client's library + player routes.
2. Native audio plugin: background playback on a real iPhone and a mid-range Android; lock-screen controls; interruptions; speed with pitch correction.
3. Offline: download one 4-hour book + read-along JSON; play in airplane mode; measure storage and battery for 1 hour of playback with read-along on/off.
4. Read-along performance: 1,000-page book, scroll and jump latency < 100 ms on the Android test device.
5. Go/no-go: if background audio isn't reliable via Capacitor, evaluate a native player screen (Swift/Kotlin) inside the Capacitor app.

## 11. Advisor pre-analysis
- **The web already does more than expected** (media session, PWA manifest). A cheap intermediate step is to make the PWA installable with offline downloads on Android (service worker + cache) and measure whether people install it. That's the demand probe for gate (b).
- **The killer feature is resume + offline**, not a new UI. A commuter who loses their place or hits a dead zone churns.
- **Retention vs. offline is a product tension.** "Files deleted after 7 days" is a privacy promise; a listener expects downloaded books to stay. Options: longer retention for downloaded copies on the device (the server still deletes), or a paid "keep" option. Decide before v1 (Q2).
- **iOS payments are the biggest uncertainty**; Android can ship first if ADR-006 stalls.
- **Accessibility users may prefer tablets**: test read-along on iPad and Android tablets, not only phones.

## 12. Critical open questions
| # | Question | Default |
|---|---|---|
| Q1 | Android first, or both at once? | Both from one codebase if ADR-006 is decided; else Android first |
| Q2 | Do downloaded copies outlive server retention (7/30 days)? | Device copy may stay until the user deletes it, with clear wording; server copy deleted as promised |
| Q3 | Push notifications in v1? | Yes (run finished/failed); low effort, high value for long jobs |
| Q4 | Any purchasing in the app v1? | No (option A), subject to current store rules |
| Q5 | Minimum OS versions? | Decide in the spike (Capacitor's supported range) |
| Q6 | Store listing language: DE first or DE + EN? | DE + EN (UI already bilingual) |
