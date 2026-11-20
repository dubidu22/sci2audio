# UX/UI redesign specification

`[DOC]` · Target UX for the new client (phase 3, ADR-003). Consolidates `sci2audio-design` (HEAD `5d7acb8`): `docs/design/PRODUCT.md`, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §3–§10, `docs/design/DESIGN.md` (≈ 47 kB), `CRITIQUE-FINDINGS.md` (superseded, in the private design record) (6 Nov), `REVIEW-FINDINGS.md` (superseded, in the private design record), `prototype/`. **The design repo stays the source of truth**; this file is the index and the decisions layered on top. Provenance: `[repo fact]` unless marked.

---

## 1. Status

| Item | State |
|---|---|
| Design system | Complete: `docs/design/DESIGN.md` (tokens in YAML frontmatter, typography, layout, elevation, shapes, ~45 components, do's and don'ts) |
| Functional brief | Complete: §1–§10 (flows, editor, accounts, admin, states, constraints); partly outdated (§9 of `doc-product-truth-and-positioning.md`) |
| Prototype | Clickable vanilla HTML/JS of the retired hosted service: `prototype/{account, admin, compare, editor, local, player, quickstart, shared, site}` (superseded, in the private design record) |
| Implementation | Current app (`sci2audio/static/app.js`, `bearbeiten.js`, `app.css`) implements much of it, with deviations listed in the two findings files |
| UX critique (6 Nov, Nielsen heuristics 0–4 × 10) | **Quick Start 26/40, editor 22/40**: "acceptable"; each with four major problems |
| Platform line in `docs/design/PRODUCT.md` | "web" → **to change**: "web first; then an iOS/Android listening app; no separate desktop apps for now" (ADR-005) |

## 2. Design system essentials

### 2.1 North star
**"The Living Type Specimen":** one sentence set at specimen scale on cool paper changes in place, word by word, as the user chooses how the text is prepared. Rule fixes thicken and sit on a pale orange wash, the user's decisions get an outline, AI rewrites get a dashed ink underline, dropped material is struck through. Density moderate, reading vertical; options are rows and columns separated by rules under a heavy 2px top rule, **never cards in a grid**. Accessibility is part of the material (Atkinson Hyperlegible Next; state carried by form, not colour alone; reduced motion respected).

### 2.2 Colour tokens (light)
| Token | Hex | Role |
|---|---|---|
| `paper` | `#f3f4f1` | Page background, sticky bars, popovers, inputs |
| `paper-2` | `#e9eae6` | The only tonal step: hover, grooves, scanned original page ground |
| `ink` | `#121212` | Text, primary button fill, selected segments, progress fills, AI dashes, decision outlines |
| `ink-2` | `#4a4b47` | Quiet ink: descriptions, hints, legends, struck words |
| `rule` | `#cfd0cb` | 1px hairlines, input/chip borders, dashed drop zone |
| `rule-strong` | `#121212` | 2px top rule opening each list or section |
| `signal` | `#e8431a` | Selection only (selected level bar, selected voice, playhead, the brand "2") |
| `signal-ink` | `#b8300c` | Orange carrying text (rare) |
| `wash` | `#ffd4c4` | Rule-fix highlighter band; "automatic" tag fill; dark mode `#5c2412` |
| `on-ink` | `#f3f4f1` | Text on ink |
| `warn-ink` / `err-ink` / `ok-ink` | `#8a3a00` / `#a3160d` / `#1f6b3a` | Notices: text and 1px outlines only, never fills |
| `focus` | `#1e4fd8` | 2px focus outline only (deliberately not orange) |
| `series-2` | `#85867f` | Second data series in admin charts only |

Dark mode inverts paper and ink, warms the signal a step, deepens the wash.

### 2.3 Named rules (non-negotiable)
| Rule | Meaning |
|---|---|
| Selection-Only Signal | Orange means "this is the one chosen" (or the brand's "2"); also playhead and playing chapter's progress; never headings, links, decoration |
| AI Is Ink | Anything AI: dashed ink line (specimen underline, dashed "KI"/"AI" tag border, dashed consent box). AI never gets orange, never a fill |
| One Tonal Step | Depth from rules, not tints; paper-2 only for hover and grooves |
| Scan Ground | The scanned original page sits on paper-2, so the source reads as a different material |
| Weight Is the Message | In the specimen: plain 300, rule fixes and decisions 800, AI rewrites 600; weight morphs over 520ms |
| Big Numbers Speak Text | Large figures in the text face with tabular numerals; mono only for small data |
| No Eyebrow | Headings stand alone; context goes underneath in quiet ink |
| Rule, Not the Box | Group with a rule above, not a container; boxes only for menu popover, notices, consent box, top-up panel (and jump list, chart readout, publish dialog) |

### 2.4 Typography
- **Atkinson Hyperlegible Next** (variable 200–800, self-hosted as "Hyperlegible") for everything; **Atkinson Hyperlegible Mono** for small figures and measurements only.
- Scale: Figure Hero (200, clamp 5–13rem: run percentage) · Clock (200, 3.5–6.5rem: player time, credit balance) · Display (300, 2.125–4rem: specimen ≤ 34ch, headlines ≤ 18ch) · Headline (800, 1.75–2.75rem, ≤ 24ch) · Title (800, 1.25–1.625rem) · Section (800, 1.375rem) · Body (400, 1rem/1.5, tabular) · Body Small (0.9375rem) · Label (0.75–0.8125rem; **0.75rem is the floor**; sentence case, never uppercase) · Read-along (400, 1.125–1.3125rem/1.6, max 40rem; spoken word at 800 on the wash) · Script (400, 1.0625rem/1.65, max 50rem) · Mono (≤ 0.9375rem).

### 2.5 Layout, shape, elevation
- Single centred column up to **92rem**, fluid gutter clamp(1–3.5rem); section gaps clamp(2.5rem, 6vw, 4.5rem); site sections clamp(4.5rem, 10vw, 8rem); sticky **4rem** top bar.
- Breakpoints in use: **960px** (2×2 level columns; editor/comparison stack), **760px** (single column; touch targets **2.75rem**), 1320px (account rows fold).
- **Flat:** no drop shadows anywhere; depth from rules and stickiness.
- Corners: controls 4px, tags 3px, focus/specimen marks 2px, drop zone 6px; grooves 4px/2px rounding, meters 6px/3px.

### 2.6 Signature components (implement first in the component library)
Level Columns · Specimen Sentence · Read-along marks · Player transport, tabs, resume line · Proof-margin paragraphs (editor) · Original page (editor) · Editor bar · Disclosure rows · Data tables · Status words (word + drawn icon, not pills) · Grooves and meters · Proof row and Comparison band · Settings rows · Code field (6 slots) · Receipt · Test-phase price · Queue row / Setup pane / "Dieser Computer" note (local) · Voice ladder, Price columns, Reading frame, Footer sitemap (site) · Publish bar and diff, charts (admin).

## 3. Surfaces and behaviour (target)

### 3.1 Quick Start (4 steps, own page each, step indicator, back allowed)
| Step | Must have |
|---|---|
| **1 Upload** | Drag & drop / picker for PDF, EPUB, MD, TXT; paste text; "try with a sample text"; up to ≈ 500 MB online (account limits; free runs have a word limit); batch entry (local); analysis progress (percent + remaining time); result: file name, pages/words, detected language (override DE/EN/auto), chapters, cover; local-only toggle for the layout model; returning users: "Continue with my settings" vs. "Change settings" (preselect, never start) |
| **2 Text** | Four level columns (name, AI or not, one-line promise, price per 1,000 words); **levels before counts; the bottom bar is the only "Weiter"** (change of 7 Nov); fixed sample sentence (`textprobe.py`) in the four levels (specimen); Schnellweg with three presets (recommended preset decided by Colin); cost before start (a price, not a formula); optional editor before voice; for AI levels optional stop after the script is written; chapter/range selection (nested, numbering as in original; bibliography/index/formalities deselected; page range or start/end markers; per-chapter pages/words/cost); pre-analysis summary (auto-fixed / your decision / only AI can solve + price). Fine settings live in account settings (decision 6 Nov) |
| **3 Voice** | Voice rows with honest quality labels and sample (2 sentences from the user's text); quality order device < standard < Azure Neural < Azure HD; "about X per audio hour"; time-to-finish per voice; speaker select **inside the chosen voice's row**; output MP3/M4B (+ per-chapter files); figures-in-player option; cover/metadata (default first PDF page or EPUB cover; upload, reset, remove; edit title/author); third-party consent at the moment it matters; paid-voice failure → switch at no extra charge, said plainly |
| **4 Order** | Summary (file, chapters/words, level, voice, format, itemised price: text, voice, discounts, credit used; estimated duration); **one consent box** (rights-holder/own-use, terms and copyright, withdrawal-right waiver); primary "Zahlungspflichtig bestellen" or "Kostenlos starten" at 0; inline top-up when credit is short; money-back guarantee near the button |

### 3.2 Run page
Figure Hero percent at the real counter; time per step estimated and learned per account and device type (`verlauf.py`, 7 Nov); karaoke line in Display; pause/resume/cancel; "you can leave, we'll e-mail you"; failure says nothing was charged; cancel of a waiting run ends without voice and keeps the text for the device voice (#291).

### 3.3 Result and player
Two columns on desktop; clock; groove with signal playhead; tabs (ink underline); transport docked at the bottom on phones; chapter marks; speed; read-along of the **original** text (sentence pairs verified; unverified sentences light their paragraph); figures appear when mentioned; markers and notes (with position in the original; export PDF/Markdown); downloads: M4B/MP3, per-chapter ZIP, listening script, reading version, original ↔ script comparison, change report (PDF + Markdown), "Alles herunterladen"; cost transparency; details tab (key data, voice, times, listening progress, original, retention, delete audiobook).

### 3.4 Editor ("Text bearbeiten", free, no AI)
Proofing sheet: full width, two equal columns: original page + tool panel left (sticky, own scroll, follows the scroll while nothing is selected), script right. Under 960px one column. Proof margin (5.5rem desktop, 4rem phone) holds block kind, page, "Weggelassen", pauses. **Selecting is not editing**; only the selected paragraph has actions; "Weglassen" before delete; delete confirms inline; action row as bottom sheet on phones; "Tabelle" block. Actions: chapter/heading (level), pauses, leave out, edit in paragraph, pronunciation (spelling as it should sound, e.g. "Burdjöh" for Bourdieu; optional IPA, only Azure Neural honours IPA; saved words are locked), preview listening (with fair-use limits), search & replace (locked words never replaced), undo/redo, autosave, change log with per-change revert, "Weggelassen" tab, file menu (import/export MD/text, discard, restart), "Original anzeigen" with paragraph highlighting (incl. AI paragraphs mapped to source words), review screen "Deine Änderungen prüfen" (grouped, filterable, "this exact text will be spoken"), optional anonymous contribution of structure corrections (`korrekturen.py`), built-in "So geht's".

### 3.5 Comparison view
Three-track grid: 5.5rem proof margin + Original + Hörskript (each ≤ 72ch); words split by origin (rules on wash, AI dashed); change counter as a disclosure opening the jump list (current change underlined in signal); **interface language follows the user, not the document** (review finding); document title, not file name; bar with "Zum Hörbuch" and "Meine Hörbücher".

### 3.6 Account area
Shell: 12.5rem list nav (tab row under 760px). Sections: Meine Hörbücher (filters: Alle, Läuft, Fertig, …; secondary "Anhören" buttons, one primary per view), Guthaben (Clock-scale balance; top-up panel; bonus; uni advantage via code: send code to the address, or student mails code from the university address to us, or manual check within 48 h), Belege (receipts, PDF, § 19 note), Einstellungen (option lists, not wrapped segmented controls: quick-start profile, fine points, sound and output, e-mails with per-kind unsubscribe), Konto (profile, third-party consent revocable, delete account with e-mail confirmation, delete all files).

### 3.7 Login
E-mail → 6-digit code (valid 30 min, 5 attempts, only in the requesting browser, max 5 codes per address per 30 min) or Google; invitation links; sessions 30 days; disposable-address block; code field with 6 slots (2.75 × 3.5rem on phones).

### 3.8 Public site
Landing (specimen story), Preise (four price columns + calculator; prices never hardcoded in artwork), FAQ (grouped by topic as disclosure rows with counts, "Alle aufklappen"), articles (Display 300 titles ≤ 17ch, lede at read-along size, proof-margin example rows "Vorlage"/"Hörskript"), reading frame with sticky contents rail, legal pages (Impressum, Datenschutz, Nutzungsbedingungen, Widerruf), DE + EN with hreflang, footer sitemap. Server-rendered (ADR-002/003).

### 3.9 Local mode pages
"Dieser Computer" note under the bar; bar names the place instead of a balance; batch (queue ≈ 1.65fr + setup pane ≥ 21rem; first starts immediately; ZIP of everything; resume; abort all) and run logs (ruled table, CSV of AI requests, statistics); same navigation on both pages.

### 3.10 Admin (desktop-first, server-rendered until after launch)
14.5rem section rail; users (search, detail, credit adjust, block), costs vs. revenue (real AI and Azure cost, margin), price editor with publish bar and diff, invitation links, uni requests, guided-test findings, quality statistics, corrections export.

## 4. Required states (`FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §9)
Empty · loading (percent + remaining time) · running · paused · cancelled · failed (nothing charged) · expired/deleted · no credit · consent missing · server busy · voice unavailable (switched-voice notice) · unsupported/unreadable file (scan without OCR) · file too large · language without voice on this device · offline/browser voice downloading (≈ 65 MB) · success · destructive confirmations (delete file, account, marker) · estimate vs. exact cost · free vs. paid variant · first-time vs. returning · light/dark. Each needs a designed screen and a Playwright test in phase 3.

## 5. Constraints (`FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §10, still valid)
Prices admin-configurable, never in artwork · plain language; AI options identifiable; "KI-generiert" on audio · euros, whole cents; no USD or model IDs · long jobs normal; pages meaningful when returning · 1 page to 1,000+ pages, dozens of nested chapters · keyboard and assistive tech in players; fast sync highlighting on long books · brand "sci2audio".

## 6. Known issues in the current implementation (to fix in the old client only if P0/P1; otherwise solved by the rebuild)

| # | Issue | Source | Severity |
|---|---|---|---|
| 1 | **Step 1 broken on phones at 375px** after upload: file details squeezed to 0px (`.fileline` grid), primary "Schnellweg einrichten" at x 351–490 unreachable (`overflow-x: clip`), "Schritt 1 von 4" overlaps "Dieser Computer", "ist fertig" notice overflows by 219px | Critique §1 | P1 regression |
| 2 | Start page adopts another document: restores the open file, then attaches to the newest running job and overwrites `qFileId`; sample-text buttons stay disabled | Review §1 | P1 bug |
| 3 | Comparison: interface follows document language; raw file name as title; no way back; change counter plain text | Review §2 | P2 |
| 4 | Editor: not full-width proof sheet; tools under the page instead of the editor bar; proof margin missing; dashed border on a non-AI button; buttons 34px (min 2.5rem, 2.75rem touch); current chapter marked with signal | Review §4, critique | P2 |
| 5 | Account: 40 filled primary "Anhören" buttons on one page; "Fertig" without icon/ok-ink; receipt statuses with decision-outline border; settings as wrapping segmented controls; no filters (46 local entries) | Review §5 | P2 |
| 6 | Site: missing contents rail; FAQ as numbered list; article titles at 800; examples as block quotes | Review §6 | P2 |
| 7 | Local pages: missing "Dieser Computer" note; inconsistent bars | Review §7 | P3 |
| 8 | Across pages: titles are raw file names cut mid-word; text-character icons instead of drawn SVG (24 viewBox, 1.75 stroke); order total "0 ct" vs. "kostenlos"; speaker select below the list; English menu label "Sprache" | Review §8 | P2 |
| 9 | Accessibility (axe, after 6 Nov): button inside the upload zone, unreached steps not marked, lines outside landmarks | `tests/test_barrierefreiheit_review.py` (now covered) | Fixed |

## 7. Changes for multi-platform (new in this KB)

| Change | Why | Owner |
|---|---|---|
| Update `docs/design/PRODUCT.md` platform line | Every later design question depends on it | Colin |
| Extract tokens from `docs/design/DESIGN.md` frontmatter into one tokens file (CSS custom properties; JSON for native) | Web client and app read the same values; light/dark consistent | Phase 3 setup |
| Design the phone app's listening experience separately: library, mini-player, full player with read-along, downloads/offline state, lock-screen and notification controls | Native conventions (tab bar, mini-player), not the web layout shrunk | Phase 4 (`doc-mobile-listening-app.md`) |
| Upload/edit/order in the app start as web views | Keeps scope small; editor is inherently web-like | Phase 4 |
| Tester findings become Issues against the spec, not quick fixes in `app.js` | The old client is being replaced | Process |
| One primary action per view; status as words + drawn icons; no pills or cards | Already in `docs/design/DESIGN.md`; enforce in components | Phase 3 |

## 8. Advisor pre-analysis

- **Don't redesign again.** Two review rounds and a scored critique already exist; the gap is implementation fidelity, which a component library built from the tokens closes structurally.
- **The specimen sentence is the product's best explainer.** It shows "rules vs. decision vs. AI vs. dropped" in one glance. Use it on the landing page and in onboarding, not only on step 2.
- **The editor is the highest-risk surface** (critique 22/40, most complex, power users only). Build it last in phase 3; consider shipping the new client without the editor first and linking to the old editor for one release.
- **Mobile is where the flow breaks today** (step 1 at 375px). Phase 3 must test every surface at 375px and 1440px, light and dark, DE and EN; automate it with Playwright screenshots.
- **Cognitive load on step 2** is the conversion risk: four levels + counts + chapter list + cost. The 7 Nov change (levels first, one "Weiter") is right; measure drop-off between steps once users exist.

## 9. Critical open questions

| # | Question | Default |
|---|---|---|
| Q1 | Where does the **full pre-analysis report** live on demand (hidden in Quick Start today)? | Result page "Details" tab + link from step 2 summary |
| Q2 | Show detected **rights information** (rights light) to the customer? | Show only when it blocks or warns (rot/gelb) |
| Q3 | Ship the new client **without the editor** first? | Yes, one release, if the editor isn't ready |
| Q4 | Keep the Schnellweg presets in the new client unchanged? | Yes (Colin's decision of 6 Nov) |
| Q5 | Logo: keep wordmark only, or commission one? | Wordmark until after launch |
| Q6 | Which surfaces does the app (phase 4) own natively vs. as web views? | Library, player, downloads native; the rest web views |
