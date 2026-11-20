# Accessibility (a11y) requirements

`[DOC]` · Requirements for every sci2audio surface (web client, public site, player, editor, mobile app) and for the **audio product itself**. Accessibility users (dyslexia, low vision) are a named primary audience in `docs/design/PRODUCT.md`, so this is a product requirement first and a legal one second. Target standard: **WCAG 2.2 Level AA** (the basis of EN 301 549, the harmonised standard under the European Accessibility Act). Provenance as labelled; contrast values computed 9 Nov 2026 from `docs/design/DESIGN.md` tokens.

---

## 1. Legal frame (pre-analysis, not legal advice)

| Item | Finding | Source |
|---|---|---|
| European Accessibility Act → German **BFSG** (Barrierefreiheitsstärkungsgesetz) | Applies since end of June 2025 to listed products and to services such as **e-commerce services for consumers** (online shops, booking tools), and also lists e-books and dedicated software | `[external fact]` IHK, Händlerbund, IT-Recht Kanzlei, checked 9 Nov 2026 |
| **Microenterprise exemption for services** | Service providers with **fewer than 10 employees and annual turnover or balance sheet ≤ €2 million** are exempt from the service obligations; the exemption doesn't cover *products* | `[external fact]` same sources (§ 2 Nr. 17, § 3 Abs. 3 BFSG) |
| Application to sci2audio | Colin's sole proprietorship (Kleinunternehmer, solo) very likely qualifies as a microenterprise, so **BFSG obligations probably don't apply today**. Open: whether producing audiobooks counts as an "e-book" service; growth beyond the thresholds ends the exemption | `[advisor proposal]`; confirm with the lawyer (pillar 04) |
| Why comply anyway | (a) accessibility users are a core segment; (b) universities and disability offices (a likely channel) expect WCAG conformance; (c) the exemption ends with growth; (d) app stores review accessibility basics | `[advisor proposal]` |
| Accessibility statement | Not legally required while exempt; **recommended** on the site (what is supported, known gaps, contact) | `[advisor proposal]` |

## 2. What already exists `[repo fact]`

| Area | State |
|---|---|
| Typeface | **Atkinson Hyperlegible Next** (variable 200–800) + Mono, self-hosted; chosen because dyslexic and low-vision readers are named users |
| State by form | Rule fix = wash + weight, decision = outline, AI = dashed ink, dropped = strike; never colour alone |
| Focus | Dedicated **focus blue** `#1e4fd8` 2px outline, deliberately different from the selection orange |
| Motion | One authored motion (specimen morph, 520ms); snaps to end state under `prefers-reduced-motion` |
| Text size floor | 0.75rem (12px) minimum; nothing smaller ships |
| Touch targets | Small controls grow to **2.75rem** on coarse pointers and under 760px; minimum button height 2.5rem (critique found 34px buttons in the editor: violation) |
| Appearance | Light / dark / system choice |
| Language | DE + EN UI; system-inserted labels follow the document language |
| Player | `navigator.mediaSession` (lock screen), read-along player, keyboard requirement stated in `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §10 |
| Automated check | axe-based review after 6 Nov; `tests/test_barrierefreiheit_review.py` asserts: no button inside the upload zone, unreached steps marked `aria-disabled`, landmarks (no `aside` inside `main`) |
| Known violations (critique 6 Nov) | Editor buttons 34px; signal used for current chapter; text-character icons; phone layout of step 1 broken at 375px |

## 3. Contrast audit of the design tokens (light mode, against `paper` `#f3f4f1`)

| Pair | Ratio | WCAG 2.2 requirement | Result |
|---|---|---|---|
| `ink` `#121212` text | 16.97:1 | 4.5:1 (text) | Pass (AAA) |
| `ink-2` `#4a4b47` quiet text | 7.96:1 | 4.5:1 | Pass (AAA) |
| `ink-2` on `paper-2` | 7.27:1 | 4.5:1 | Pass |
| `ink` on `wash` `#ffd4c4` (rule-fix highlight, spoken word) | 13.80:1 | 4.5:1 | Pass |
| `signal` `#e8431a` (selection bars, playhead) | 3.62:1 | 3:1 non-text; 4.5:1 if text | Pass as non-text; **never use for text** |
| `signal` on `paper-2` | 3.31:1 | 3:1 non-text | Pass (narrow) |
| `signal-ink` `#b8300c` | 5.49:1 | 4.5:1 text | Pass |
| `focus` `#1e4fd8` outline | 6.01:1 | 3:1 (focus appearance) | Pass |
| `warn-ink` / `err-ink` / `ok-ink` | 7.08 / 7.10 / 5.90 | 4.5:1 | Pass |
| `series-2` `#85867f` (chart series) | 3.33:1 | 3:1 non-text | Pass (narrow) |
| **`rule` `#cfd0cb` (hairlines; input, chip and checkbox borders at rest)** | **1.41:1** | **3:1 for boundaries needed to identify a component (SC 1.4.11)** | **Fail where the border is the only cue** |

**Fix for the `rule` finding:** hairlines between rows are decorative (no requirement), but **input fields, chips and segmented controls at rest** need a ≥ 3:1 boundary or another identifying cue. Options: a darker `rule-control` token for control borders (e.g. a grey with ≥ 3:1 on paper), or rely on an always-visible label plus a 2px bottom rule in `ink-2`. Decide in phase 3 component work; dark mode values need the same audit.

## 4. Requirements by surface

### 4.1 Global (all web surfaces)
| # | Requirement | WCAG SC | Test |
|---|---|---|---|
| G1 | All functionality operable by keyboard; visible focus (focus blue); no keyboard traps; logical focus order | 2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11 | Playwright keyboard walk per surface |
| G2 | Landmarks (`header`, `nav`, `main`, `footer`); one `h1` per page; heading levels in order; skip link | 1.3.1, 2.4.1, 2.4.6 | axe + unit test |
| G3 | Every control has an accessible name; icon buttons labelled; status words exposed as text (not only icons) | 4.1.2, 1.1.1 | axe |
| G4 | Text contrast ≥ 4.5:1; component boundaries and states ≥ 3:1 (see §3 fix) | 1.4.3, 1.4.11 | Token audit + axe |
| G5 | Reflow at 320 CSS px without horizontal scroll (except data tables); text resize to 200% | 1.4.10, 1.4.4 | Playwright at 320/375px |
| G6 | Target size ≥ 24×24 CSS px (WCAG 2.2 AA); design standard 2.75rem on touch | 2.5.8 | Visual + script |
| G7 | No information by colour alone (already a design rule) | 1.4.1 | Review |
| G8 | Respect `prefers-reduced-motion`; no auto-playing audio | 2.3.3 (AAA, adopted), 1.4.2 | Unit |
| G9 | `lang` attribute per page; inserted document-language labels carry their own `lang` | 3.1.1, 3.1.2 | Unit |
| G10 | Errors identified in text, with suggestions; no time limits except the login code (30 min, announced, re-sendable) | 3.3.1, 3.3.3, 2.2.1 | Review |
| G11 | Consistent navigation and help location across pages (menu, "So geht's") | 3.2.3, 3.2.6 | Review |
| G12 | Authentication without cognitive function tests: e-mail code is fine; allow paste and autofill (`autocomplete="one-time-code"`) | 3.3.8 | Unit |

### 4.2 Quick Start
- Step indicator exposes current step (`aria-current="step"`); unreached steps `aria-disabled` (done).
- Upload zone is a labelled region with one button (done); progress announced politely (`aria-live="polite"`, at most every 10% or 10 s).
- Level columns: a radio group with the price inside the accessible name ("Klar und Direkt, KI, 10 Cent pro 1.000 Wörter").
- Specimen sentence: provide a text alternative describing the changes ("3 Stellen durch Regeln korrigiert, 1 Entscheidung, KI schreibt 2 Sätze um"); the visual morph is decorative.
- Cost and consent: consent checkbox with full label; price total announced when it changes.

### 4.3 Run page
- Percent and remaining time in a polite live region with throttling; pause/resume/cancel buttons labelled; completion and failure announced assertively once.

### 4.4 Player and read-along (highest priority)
| # | Requirement |
|---|---|
| P1 | Keyboard shortcuts: Space play/pause; ←/→ skip (15 s); Shift+←/→ previous/next sentence; ↑/↓ speed; `C` chapters; shortcuts listed in "So geht's" and not active while typing in fields (2.1.4) |
| P2 | Transport buttons labelled with state ("Pause", "Abspielen"); slider for position with `aria-valuetext` in time ("1 Stunde 4 Minuten von 4 Stunden 12") |
| P3 | **Read-along highlighting must not spam screen readers**: no live announcements per sentence; the current sentence is exposed via `aria-current="true"` and focusable on demand ("zum aktuellen Satz") |
| P4 | Spoken word at 800 on wash (13.8:1); current paragraph in ink; rest in quiet ink (7.96:1); user option for larger read-along text (up to 200%) and for disabling word highlighting (some dyslexic users find motion distracting) |
| P5 | Performance: highlighting stays smooth on 1,000-page books (virtualised rendering); jump latency < 100 ms |
| P6 | Tap/click a sentence to jump; keyboard equivalent |
| P7 | Figures shown when mentioned have alt text from the figure's caption or "Abbildung N"; pausing is possible |
| P8 | Notes and markers reachable by keyboard; export as Markdown/PDF (tagged PDF where feasible) |

### 4.5 Editor
- Selecting a paragraph is a single, labelled action; actions appear in a toolbar announced by role; delete confirms inline (no modal trap); bottom sheet on phones must trap focus correctly and close with Escape.
- Pronunciation dialog: fields labelled; preview listening operable by keyboard.
- Original view: the scanned page image needs a text alternative; the extracted text is the accessible equivalent, linked.
- Buttons ≥ 2.5rem (fix the 34px ones).

### 4.6 Comparison view
- Two text columns readable in sequence by screen readers (Original, then script, per row); change marks exposed as text ("durch Regel geändert", "KI", "nicht vorgelesen") via visually hidden labels, since wash/dash/strike are visual only.

### 4.7 Account, credit, receipts
- Tables with headers (`th`, `scope`); receipt PDFs tagged; balance announced as text with currency.

### 4.8 Public site
- Articles with proper headings; contents rail as `nav` with a label; FAQ disclosures as `details/summary` or ARIA buttons with `aria-expanded`; price calculator inputs labelled; hreflang and `lang`.

### 4.9 Mobile app (phase 4)
- VoiceOver/TalkBack labels for all controls; dynamic type; hit targets ≥ 44pt (iOS) / 48dp (Android); lock-screen controls; reduced motion; read-along as in §4.4.

## 5. The audio product as an accessibility feature

| # | Requirement | Where implemented |
|---|---|---|
| A1 | Nothing a voice would stumble on reaches the voice: page numbers, hyphenation, footnote marks, citations, abbreviations, numbers, symbols, gender forms, URLs | Pre-analysis + rules (`doc-prompts-and-detector-rules.md`) |
| A2 | Structure audible: pause before chapters (default 2.0 s), at section breaks (1.0 s), chapter marks in M4B | `config.chapter_pause`, `section_pause` |
| A3 | Sources distinguishable: short citations spoken "a little quieter and faster" with short pauses (`quellenstimme.py`) | Citation mode KURZ_AUTOR_JAHR |
| A4 | Long quotations announced ("Zitat: … Zitat Ende") in rule mode; AI modes announce quotes with a colon and name the speaker of an "ich" | Detector `zeichen`; prompts |
| A5 | Pronunciation control: glossary per user, locked words, foreign words spoken in their language where the voice supports it | Editor, glossary, `fremdwoerter` |
| A6 | Speed control 0.5–2×; Thorsten defaults to 0.85 (listening test 31 Oct) | Player, `PIPER_TEMPO` |
| A7 | "KI-generiert" label in player and metadata | EU AI transparency |
| A8 | Read-along aligns the **original** text, not the rewritten script, so a dyslexic reader sees the author's words while hearing the accessible version | `mitlesen.py` |

## 6. Testing and governance
| Layer | Tool | When |
|---|---|---|
| Unit/integration | Existing pytest a11y assertions; extend per surface | Tier 1 |
| Automated scan | axe (via Playwright) on every surface, light/dark, DE/EN, 375/1440px | Nightly tier 2 (phase 3) |
| Keyboard walk | Scripted Playwright paths for Quick Start, player, editor | Phase 3 switch checklist |
| Screen reader smoke | Manual: NVDA + Firefox (Windows), VoiceOver + Safari (macOS/iOS), TalkBack (Android) on Quick Start + player | Before M2 and before the client switch |
| Users | 3–5 accessibility users in the first test cohort (dyslexia, low vision) | Pillar 05 |
| Statement | Accessibility statement page with known gaps and contact | Before M2 |

## 7. Advisor pre-analysis
- **sci2audio's accessibility story is unusually strong at the design level** (typeface, state by form, focus colour, read-along of the original). The gaps are implementation (button sizes, control borders, live-region discipline) and verification (no screen-reader testing yet).
- **The `rule` contrast failure is systemic but easy**: one token for control borders fixes it everywhere in the new client.
- **Read-along is the hardest a11y problem**: highlighting that helps sighted dyslexic readers can overwhelm screen-reader users if implemented as live announcements. Separate the two needs explicitly (P3).
- **Disability offices are a channel.** A short, honest accessibility statement and a tested player are what they'll ask for.

## 8. Critical open questions
| # | Question | Default |
|---|---|---|
| Q1 | Does the BFSG microenterprise exemption apply, and could audiobook generation count as an "e-book" service? | Lawyer question (pillar 04); comply voluntarily anyway |
| Q2 | Target WCAG 2.2 AA for the whole app, or AA for Quick Start + player first? | AA for Quick Start, player, account at the client switch; editor and admin best effort |
| Q3 | Offer an option to turn off word-level highlighting? | Yes (some users find it distracting) |
| Q4 | Tagged PDF for receipts and change reports? | Receipts yes; reports best effort |
| Q5 | Recruit accessibility testers how (university disability offices, dyslexia associations)? | Pillar 05 |
