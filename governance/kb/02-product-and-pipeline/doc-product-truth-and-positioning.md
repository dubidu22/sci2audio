# Product truth and positioning

`[DOC]` · The durable definition of what sci2audio is, for whom, and what it promises. Consolidates `docs/design/PRODUCT.md`, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §1–2, the live site (checked 8 Nov 2026) and the code (9 Nov 2026). Where sources disagree, the conflict is listed in §9 and resolved in `working-product-open-questions.md`.

---

## 1. One sentence

**sci2audio turns scientific and long-form texts (PDF, EPUB, Markdown, TXT, pasted text) into audiobooks by first building a near-perfect listening script with free statistical rules, using AI only where rules can't solve a problem, and stating the price before anything starts.** [repo fact] `docs/design/PRODUCT.md` "Product Purpose"

Success = the listener can follow a dense academic text by ear, knew exactly what it would cost and what quality to expect before starting, and never had to fight the tool. [repo fact]

## 2. Users

| Segment | Need | Why sci2audio fits | Source |
|---|---|---|---|
| **Primary: students and researchers** (German-speaking first; humanities and social sciences: social work, pedagogy, philosophy) | Listen to papers, theses, textbooks while commuting, without citations and footnotes wrecking the flow | Pre-analysis removes or reshapes citations, footnotes, page numbers, abbreviations; price per 1,000 words; uni advantage | [repo fact] `docs/design/PRODUCT.md` |
| **Accessibility users** (dyslexia, low vision) | Reliable, controllable reading; visual read-along; control over pronunciation | Read-along player, glossary/pronunciation, Atkinson Hyperlegible type, state by form not colour | [repo fact] `docs/design/PRODUCT.md`, `docs/design/DESIGN.md` |
| **Power users and lecturers** | Batch many documents, edit the script precisely, one file per chapter | Editor, batch (local), per-chapter files | [repo fact] |
| **Self-hosters / local users** | Run on their own computer with their own keys | Local mode: same flow and look, no limits, euro prices shown but nothing charged ("local = demo") | [repo fact] |
| **Operator (admin)** | Manage users, credit, invitations, prices, costs, quality statistics | Separate internal admin area, desktop-first | [repo fact] |

Users not served (by design): fiction listeners wanting multi-voice drama; emotional performance tags (`ROADMAP.md` "Bewusst nicht geplant": character recognition and multiple voices per book, emotion tags like `<laugh>`, local GPU TTS like Kokoro/Orpheus on a MacBook). [repo fact]

## 3. Positioning

| Claim | Substance | Status |
|---|---|---|
| **The differentiator is the statistical pre-analysis (Voranalyse), not the voice** | Detectors find and fix, without AI, what a voice would stumble on: page numbers, hyphenation, footnotes, citations, abbreviations, numbers, gender forms, tables, formulas, long sentences, foreign words, names, garbled font encodings, publisher boilerplate, headings, figures | [repo fact]. **Marketing says "13 detectors"; the code runs 20** (see §9) |
| **Rules first, AI second** | AI only where rules can't solve a problem; free rule-based options are first-class; AI options are clearly marked as AI | [repo fact] `docs/design/PRODUCT.md`, `ROADMAP.md` guiding rule "Erst alle statistischen Möglichkeiten ausschöpfen, dann KI" |
| **Price known before starting** | Deterministic price: depends on word count, not on real AI cost; nothing starts by itself | [repo fact] `demo.Pricing` docstring: "The price depends only on the text, so it is known exactly before the run" |
| **Honest labels** | Each text level and voice states quality, cost and limits, including the voice quality order (device < standard < Azure Neural < Azure HD) | [repo fact] |
| **Control over the text** | Chapter and page selection, auto-deselected bibliography/index/formalities, pronunciation and personal glossary, free text editor | [repo fact] |

Brand commitments [repo fact] `docs/design/PRODUCT.md`:
- Name **sci2audio**, lowercase; the "2" is part of the word; domain sci2audio.com; no logo yet.
- Voice: plain, honest, explanatory German and English, no tech jargon; wherever a choice is made, say what it does and what it costs.
- Audio carries a **"KI-generiert" (AI-generated)** label (EU AI transparency); every AI-using option is identifiable as AI.
- Reminder on runs and results: **for your own use only; do not pass on, publish or share**.
- Seller: **Colin Meng, self-employed software developer (colinmeng.de), Kleinunternehmer under § 19 UStG**; no VAT shown; receipts and pricing carry the § 19 note.

## 4. Product principles (binding for every surface)

1. **Rules first, AI second, and visibly so.** Free rule-based paths are never second-class. AI is marked as AI and offered only where it adds something.
2. **Price and expectations before commitment.** Every option states quality, cost and limits before the user pays. Nothing starts without an explicit action.
3. **Leaving is normal.** Long jobs survive a closed tab, a pause or a failure. Every page still makes sense when the user returns; failures say plainly that nothing was charged.
4. **The user decides what is spoken.** Selection, pronunciation, omissions and edits are first-class and reversible.
5. **Plain language, honest money.** No jargon, no dark patterns. Fees, discounts, guarantees and retention are stated openly.

## 5. Offer as built (9 Nov 2026)

### 5.1 Text levels (Quick Start step 2)

| Level (DE / EN UI) | Internal mode | Technology | Price list default (ct / 1,000 words) | Notes |
|---|---|---|---|---|
| Keine Bearbeitung / No editing | `vorlesen` | none | 0 | Original read as is |
| Vorlesbar / Readable | `regeln` | rules only (pre-analysis fixes + rule-based script) | 0 | Free forever ("immer kostenlos") |
| Klar & Direkt / Clear & Direct | `ki` | AI: Sprechfassung by **Claude Haiku (effort high)** in whole subchapters (≈ 1,500 words per call); routing classes for the rest | **10** (`SCI2AUDIO_PREIS_TEXT_KI`) | Simplifies vocabulary ("einfache Wörter statt Erklärungen") |
| Akademisch & Flüssig / Academic & Fluent | `premium` | AI: Sprechfassung by **Claude Sonnet (effort medium)** in ≈ 900-word groups with the academic prompt | **35** (`SCI2AUDIO_PREIS_TEXT_PREMIUM`) | Keeps academic vocabulary; blind test 5 Nov: won 8 of 9 against Sonnet high with the plain prompt at a third of the cost |

### 5.2 Voices (Quick Start step 3)

| Voice | What it is | Price default | Output |
|---|---|---|---|
| Gerätestimme / Device voice | The visitor's device reads live in the browser (Web Speech API); page must stay open | free | Live only, **no file** |
| Standardstimme / Standard voice ("Thorsten im Browser") | Piper Thorsten (DE) / LJ Speech and others (EN) running in the visitor's browser via ONNX/WebAssembly (≈ 63–65 MB first download); server only plans and joins | Included when the text is paid; in free-text runs 50,000 words/month free, then **5 ct** | MP3/M4B |
| Azure Neural | Microsoft neural voices (e.g. Seraphina multilingual) | **+15 ct** | MP3/M4B |
| Azure HD | Microsoft's most natural voices (Seraphina HD …) | **+25 ct** | MP3/M4B |

Sales mode sells only Azure voices (`SOLD_VOICES = (AZURE, AZURE_HD)`); Thorsten's commercial licence is open (pillar 04). Server-side Thorsten, helper computers and 24-hour delivery were removed on 1 Nov 2026. [repo fact] `web.py` comments

### 5.3 Money and account rules (defaults, admin-configurable)

| Rule | Value | Source |
|---|---|---|
| Wallet | Prepaid credit in euros and whole cents; no subscription, no expiry | `docs/design/PRODUCT.md` |
| Top-up | Stripe Checkout; minimum amount; **+10% bonus from €25** | `demo.Pricing` (`bonus_ab_cent=2500`, `bonus_prozent=10`) |
| Uni advantage | **€5 one-time credit** + **−20%** on every paid line for confirmed university addresses | `uni_startguthaben_cent=500`, `uni_rabatt=20` |
| Money-back guarantee | **14 days** after a paid run, no reason; **max 2 claims per account per month** | `garantie_tage=14`, `garantie_je_monat=2` |
| Free AI words | **None** since 4 Nov 2026 (`gratis_woerter=0`); global hard cap for free AI words 1,000,000/month (`gratis_deckel`) | `demo.Pricing` |
| Failed runs | Technical errors are free and return free words; a cancelled run pays the finished share, each line rounded down ("when in doubt, cancelling is free") | `Pricing.charge` docstring |
| Retention | **7 days** (30 days for paid runs), warning mail 2 days before; then files, text and images deleted; only key data and costs remain | `docs/design/PRODUCT.md`, UI strings |
| Modes | **Test mode** (now: everything free during the test phase) and **sales mode**, switched by a flag; every surface supports both | `docs/design/PRODUCT.md` |
| Conversion assumption | **≈ 8,000 words ≈ 1 audio hour**; listening speed 140 words/min | `docs/design/PRODUCT.md`, `dauer.WORDS_PER_MINUTE` |
| Reference book | 100 pages ≈ 35,000 words (350 words/page) | `dauer.EXAMPLE_PAGES/WORDS` |

## 6. Operating context

- **Quick Start: 4 steps**, each its own page with a step indicator, back navigation: **1 Upload → 2 Text → 3 Voice → 4 Order**, then the run page, then result (player and downloads). [repo fact]
- **Jobs run minutes to hours.** The user may leave; an e-mail arrives when done. Pause, resume, cancel; finished parts are kept; only finished work is charged. [repo fact]
- **Result page:** player (chapter marks, speed), read-along, figures, markers and notes, downloads (M4B/MP3, per-chapter ZIP, script, original ↔ script comparison, notes as PDF/Markdown, change report, reading version), cost transparency. [repo fact]
- **Documents** range from single pages to 1,000+ page books with dozens of nested chapters. [repo fact]
- **Two installations share one design:** online (sci2audio.com) and local ("Dieser Computer"). Batch mode and run logs exist only locally. [repo fact]
- **Customer-facing money:** euros, whole cents. Never USD, model names, "tokens" or technical stage names. Progress as percent and remaining time. [repo fact]
- **Consent:** AI levels and Azure voices send text to Anthropic or Microsoft; one explicit, revocable consent shown when it matters; the order step has one consent box (rights-holder confirmation, terms, withdrawal waiver). [repo fact]
- **Language:** UI German first, every user-facing string with an English version (1,651 strings); labels the system inserts into a document follow the document's language; layouts must survive longer German text. [repo fact]

## 7. Evidence on hand vs. absent

| Have | Never fabricate |
|---|---|
| Pre-analysis showcase examples: "Sozial- arbeit" re-joined; "(vgl. Müller 2020, S. 12)" shortened; "z. B." spelled out; SFBT/SES asked about; "Klient*innen" spoken naturally; tables described; "Abb. 3: …" removable | Testimonials, user numbers, reviews, press, quality benchmarks |
| Sample PDFs with expected output (19 Musterproben, `.soll.md`/`.soll.json`) | Using the sample PDFs publicly as marketing (third-party copyrighted works) |
| Real voiced example (Thorsten, "community organizing") and comparison output | — |
| Evaluator corpus (18 documents) and audit report of 4 runs (96 documented errors: 38 rules, 16 extraction, 29 pure AI) | Public quality claims derived from internal tests without method disclosure |

## 8. Advisor pre-analysis

- **The moat is real but invisible.** The pre-analysis and the faithfulness rules in the prompts (no invented "ich", no lost negation, sources not turned into claims) are the hard-won differentiation. Generic text-to-speech apps read PDFs too; none of them advertise refusing to invent a count. The positioning must make "faithful to the source" tangible, e.g. through the specimen sentence (design signature) and the comparison view, not through a voice demo.
- **"Rules first" is also a margin strategy.** On the sample PDF, 54% of text needs no AI; every new rule lowers cost per book at a fixed price per word. That's the business case for M3 (rule coverage).
- **Academic integrity is a selling point for the primary segment.** Students and lecturers worry that AI changes meaning. "Akademisch & Flüssig keeps your discipline's vocabulary and never states an assumption as a fact" is a stronger promise than "natural voice".
- **The accessibility segment may be the more durable one.** Dyslexic and low-vision students have a recurring, non-optional need; universities' disability offices are an institutional channel (pillar 05).
- **Two lists of numbers are out of sync** (13 vs. 20 detectors; site vs. `docs/design/PRODUCT.md` prices). Product truth must have one owner and one source (§10).
- **Local mode dilutes the story** ("no limits, own keys, nothing charged") unless positioned as an open/self-host option for institutions. Decide (O-07).
- **No users means positioning is a hypothesis.** The first 50 users (pillar 05) should test the core claims: does the pre-analysis report matter to them? Do they choose Klar or Akademisch? Do they listen on phones?

## 9. Conflicts between sources (as of 9 Nov 2026)

| Topic | Source A | Source B | Resolution proposal |
|---|---|---|---|
| Number of detectors | "13" in `docs/design/PRODUCT.md`, `ROADMAP.md`, `README.md` ("Dreizehn statistische Detektoren"), `docs/VORANALYSE.md`, marketing | **20** in code (`analysis/__init__.py` BUILTIN: zeichensalat, layout, publisher, hyphenation, footnotes, links, figures, headings, markup, citations, capitals, abbreviations, numbers, gender, structures, sentences, names, homographs, passages, fremdwoerter) | Say "20 detectors" or "over 60 kinds of problems in 22 categories" (more stable); update docs |
| AI text prices | `docs/design/PRODUCT.md` / `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) / code defaults: 10 ct and 35 ct; Azure +15 / +25 ct | Live site (8 Nov): €0.08 and €0.15; Azure +€0.12 / +€0.20 | Prices are admin-configurable; production may carry other values. Pillar 03 decides the authoritative list |
| Standard voice in sales mode | Price page and brief: "Standardstimme (Thorsten) 0,00 €" | Code: German Thorsten `sale=False` (not served when selling); English Piper voices `sale=True` | Price page + brief per D-36 (pillar 04 audit D-05; pillar 05 launch §2) |
| Standard voice location | `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) step 3: "runs on our/own server (or in the browser)" | Code: server Thorsten removed 1 Nov; browser only online | Update the brief |
| Free AI words | Brief mentions "free-allowance shown struck-through" | `gratis_woerter=0` since 4 Nov | Update the brief or remove the struck-through display |
| "Flüssig & Akademisch" vs. "Akademisch & Flüssig" | Both orders appear in UI strings and code comments | — | Pick "Akademisch & Flüssig" (used in `TEXT_TITLES`) |
| Read-along | `ROADMAP.md`: "Player mit Text-Hervorhebung … verworfen" | Shipped and specified as a core accessibility feature | Update the roadmap |

## 10. Ownership of product truth

| Fact | Single source of truth | Consumers |
|---|---|---|
| Prices, discounts, guarantees | Admin settings (`demo.Pricing`, `PRICE_FIELDS`) | Site, app, receipts; docs refer, never restate numbers |
| Detector list and counts | `analysis/__init__.py` + `analysis/categories.py` | Docs, marketing generated or checked by a test |
| Text levels and voices | `demo.TEXT_MODES`, `TEXT_TITLES`, `web.OFFERED_VOICES` / `SOLD_VOICES` | UI, site |
| Principles, users, positioning | This file + `docs/design/PRODUCT.md` | Design, marketing |

Proposal: a test that fails when docs or site copy state a detector count different from the code. That's cheap and prevents the drift recurring.

## 11. Critical open questions

| # | Question | Why it matters |
|---|---|---|
| Q1 | Which segment is first: students in general, or accessibility users via disability offices? | Channel, copy, pricing sensitivity |
| Q2 | Is "faithful to the source" (AI integrity) the headline claim, or "listen to your readings on the go"? | Landing page, ads |
| Q3 | Keep two AI levels, or test one AI level at launch to simplify the choice? | Conversion and support |
| Q4 | What is the role of local mode: product, open-source showcase, or developer tool? | Positioning, architecture (O-07) |
| Q5 | Which price list is live and authoritative? | Trust, receipts, legal |
| Q6 | Will the "own use only" reminder satisfy copyright risk in sales mode, or is a stronger gate needed for whole books (rights light "rot" blocks today)? | Pillar 04 |
