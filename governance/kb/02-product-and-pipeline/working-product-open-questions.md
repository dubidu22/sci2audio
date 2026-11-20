# Working: product open questions, assumptions and risks

`[WORKING]` · Living register for pillar 02. Consolidates the open questions of the seven pillar-02 files, the source conflicts found on 9 Nov 2026, the unvalidated product assumptions, and how to test them with the first users. Reviewed in the monthly retro. Last update: 9 Nov 2026.

---

## 1. Advisor pre-analysis

- **Every product claim is a hypothesis until users exist** (F-05: no users yet). The product is unusually complete for that stage: 4-step flow, 4 text levels, 4 voices, editor, read-along, comparison, reports, uni advantage, guarantee, admin. The risk is not missing features; it's **not knowing which of them matter**.
- **The first 50 users should answer five questions** (§4): do they understand and value the pre-analysis, which AI level they pick and why, where and how they listen, what breaks trust (a wrong statement, a mispronunciation, a price surprise), and whether they come back with a second document.
- **Source-of-truth drift is the cheapest problem to fix and the most embarrassing to ship** (13 vs. 20 detectors, 22 vs. 25 categories, two price lists, outdated brief). Fix before any public launch copy.
- **Instrument now, privacy-friendly and server-side.** Without events there's nothing to learn from the guided test or the first cohort.

## 2. Source conflicts to resolve (owner: Colin)

| ID | Conflict | Proposed resolution | Blocks |
|---|---|---|---|
| C-01 | "13 detectors" (docs, marketing, `FUNCTIONAL-BRIEF.md` (superseded, in the private design record) §4, `README.md`) vs. **20** in code | Use "20 detectors" or "60+ kinds of problems in 25 categories"; update docs; add a count test | Launch copy |
| C-02 | "22 categories" (`VORANALYSE.md`) vs. **25** in `analysis/categories.py` | Same as C-01 | Docs |
| C-03 | Prices: code/`docs/design/PRODUCT.md` 10/35 ct, Azure +15/+25 vs. live site €0.08/€0.15, +€0.12/+€0.20 | Decide in pillar 03; admin settings are the single source; site copy reads from them | Launch, receipts |
| C-04 | Brief says the standard voice runs on the server too; code removed server Thorsten (1 Nov) | Update brief and FAQ: browser only online | Copy |
| C-05 | Brief shows a struck-through free AI allowance; `gratis_woerter = 0` since 4 Nov | Remove the display or set an allowance deliberately | UI |
| C-06 | "Flüssig & Akademisch" vs. "Akademisch & Flüssig" | "Akademisch & Flüssig" everywhere | Copy |
| C-07 | `ROADMAP.md` rejects the read-along player; it shipped and is core | Rewrite the roadmap (phase 0 week 4) | Planning |
| C-08 | `docs/design/PRODUCT.md` platform "web" vs. app plans | "Web first; then an iOS/Android listening app" | Design decisions |

## 3. Consolidated open questions

### 3.1 Strategy and positioning
| ID | Question | Options | Recommendation | From |
|---|---|---|---|---|
| PQ-01 | First segment: students in general, or accessibility users via disability offices? | General / accessibility-first / both | Both in the first cohort; channel test decides (pillar 05) | product truth Q1 |
| PQ-02 | Headline promise: "faithful to the source" vs. "listen to your readings on the go"? | Integrity / convenience | Integrity first, convenience second; test both on the landing page | product truth Q2 |
| PQ-03 | Two AI levels at launch, or one? | Keep both / Klar only / Akademisch only | Keep both (distinct prompts, clear story), measure choice share | product truth Q3 |
| PQ-04 | Role of local mode | Product / open-source showcase / dev tool | Decide before phase 2 (O-07) | product truth Q4 |
| PQ-05 | Stronger copyright gate than "own use only" in sales mode? | Keep / add checks | Pillar 04 | product truth Q6 |

### 3.2 UX
| ID | Question | Recommendation | From |
|---|---|---|---|
| PQ-06 | Where does the full pre-analysis report live on demand? | Result page "Details" tab + link from step 2 | UX Q1 |
| PQ-07 | Show the rights light to customers? | Only when it blocks or warns | UX Q2 |
| PQ-08 | Ship the new client without the editor first? | Yes, one release, if needed | UX Q3 |
| PQ-09 | Keep the Schnellweg presets unchanged in the new client? | Yes (Colin's decision 6 Nov) | UX Q4 |
| PQ-10 | Logo or wordmark only? | Wordmark until after launch | UX Q5 |
| PQ-11 | Fine settings: account settings only (decision 6 Nov) or also per run? | Account settings + "Alle Einstellungen" link per run | Brief §3 vs. critique |

### 3.3 Mobile
| ID | Question | Recommendation | From |
|---|---|---|---|
| PQ-12 | Android first or both? | Both if ADR-006 decided; else Android first | mobile Q1 |
| PQ-13 | Do downloaded copies outlive server retention (7/30 days)? | Device copy stays until deleted, clearly worded; server copy deleted as promised | mobile Q2 |
| PQ-14 | Push notifications in v1? | Yes | mobile Q3 |
| PQ-15 | Purchasing in the app v1? | No (play-and-sync), subject to store rules | mobile Q4 |
| PQ-16 | Minimum OS versions, store languages | Decide in spike; DE + EN | mobile Q5–Q6 |
| PQ-17 | Make the PWA installable with offline downloads as a demand probe (phase 3)? | Yes, Android-focused | mobile pre-analysis |

### 3.4 Accessibility
| ID | Question | Recommendation | From |
|---|---|---|---|
| PQ-18 | BFSG exemption / "e-book" classification | Lawyer (pillar 04); comply voluntarily | a11y Q1 |
| PQ-19 | AA scope at the client switch | Quick Start, player, account AA; editor/admin best effort | a11y Q2 |
| PQ-20 | Option to turn off word-level highlighting | Yes | a11y Q3 |
| PQ-21 | Control-border contrast fix (`rule` 1.41:1) | New `rule-control` token ≥ 3:1 | a11y §3 |
| PQ-22 | Recruit accessibility testers how? | Disability offices, dyslexia associations (pillar 05) | a11y Q5 |

### 3.5 Pipeline and quality
| ID | Question | Recommendation | From |
|---|---|---|---|
| PQ-23 | Layout model online as a paid option? | Not until bigger workers + demand | pipeline Q1 |
| PQ-24 | Keep classic routed classes beside the Sprechfassung? | Yes (tables, formulas, figures) | pipeline Q2, optimisation Q4 |
| PQ-25 | Output formats | MP3 + M4B; Opus CLI only | pipeline Q3 |
| PQ-26 | Server-side Thorsten again after licensing? | Only after the licence decision | pipeline Q4 |
| PQ-27 | Quality north-star metric | Regression cases passing + post-check residue per 1,000 words | optimisation Q1 |
| PQ-28 | Monthly budget for paid evaluation runs | e.g. $20 pilot cap | optimisation Q2 |
| PQ-29 | English rules now or on demand? | On demand | optimisation Q3 |

## 4. Product assumptions to validate (with the guided test and the first 50 users)

| ID | Assumption | Evidence today | How to validate | Success signal `[advisor proposal]` |
|---|---|---|---|---|
| A-01 | Students want to **listen** to academic texts (not just read summaries) | Product premise; no users | Landing page + uni channel sign-ups; first-run completion | ≥ 30% of sign-ups complete a first audiobook |
| A-02 | The pre-analysis report builds trust and is understood | Survey item exists ("Wie verständlich ist der Prüfbericht vor dem Start?", 1–5 scale, `umfrage.py`) | Guided test + survey | Median ≥ 4/5 |
| A-03 | Price transparency matters ("Preis vor dem Start") | Survey item "Wie nachvollziehbar sind die Kosten für KI-Läufe?" | Survey + order-step drop-off | Median ≥ 4/5; drop-off at order step < 30% |
| A-04 | Users will pay 10–35 ct per 1,000 words for AI text | Pricing design only | Sales mode with first users; uni discount uptake | ≥ 10% of active users pay within 30 days |
| A-05 | Free levels (Vorlesbar + device/standard voice) are good enough to hook users | Design | Share of second runs after a free first run | ≥ 25% come back within 14 days |
| A-06 | Listening happens mostly on phones while commuting | Persona statement | Server-side events: player sessions by device class, interruptions | ≥ 30% of listening minutes on mobile (ADR-005 gate) |
| A-07 | Read-along matters to accessibility users | Persona; design | Usage share of read-along tab; tester interviews | Used in ≥ 50% of accessibility testers' sessions |
| A-08 | Akademisch & Flüssig is worth 3.5× Klar & Direkt to users | Blind tests on quality, not on users | Choice share; complaints; guarantee claims | ≥ 25% of paid AI runs choose Akademisch |
| A-09 | Faithfulness errors are rare enough not to break trust | Audit: 29 AI errors across 4 runs | Evaluator + user-reported issues | < 1 user-reported meaning error per 10 runs |
| A-10 | The 14-day money-back guarantee isn't abused | 2-claims/month cap | Claim rate | < 5% of paid runs |
| A-11 | Uni e-mail verification is feasible across universities | `uni.py` domain list; 3 verification paths | Verification success rate; manual checks within 48 h | ≥ 90% automatic |
| A-12 | Users accept browser-based voice generation (≈ 65 MB download, page open) | Design choice for cost | Abandonment during browser synthesis | < 20% abandon |
| A-13 | 7-day retention is acceptable | Privacy-first choice | Complaints; downloads before expiry; reminder mail clicks | < 10% complain |

## 5. Instrumentation needed (privacy-friendly, server-side, no third-party trackers)
| Event | Properties | Use |
|---|---|---|
| upload_completed | pages, words, language, file type (no content) | Funnel, document mix |
| step_viewed / step_left | step 1–4, duration | Drop-off per step |
| level_chosen | vorlesen/regeln/ki/premium | A-08 |
| voice_chosen | geraet/browser/azure/azure-hd | Cost mix |
| order_placed | price band, discount used, credit vs. free | A-04 |
| run_finished / run_failed | duration, class shares, real cost, failure reason | Quality, margin |
| player_session | device class, minutes, read-along on/off, interruptions | A-06, A-07 |
| download | format | Retention vs. offline |
| guarantee_claim | reason (free text optional) | A-10 |
| survey_answer | item, value | A-02, A-03 |
Retention of raw events: short (e.g. 90 days), then aggregates only; documented in the processing record (pillar 04).

## 6. Product risks

| ID | Risk | L | I | Mitigation |
|---|---|---|---|---|
| PR-01 | Users don't understand four levels × four voices; choice paralysis | 3 | 3 | Schnellweg presets; recommended preset; measure drop-off |
| PR-02 | A published meaning error in an academic text damages trust | 2 | 4 | Faithfulness checks, regression cases, "KI-generiert" label, comparison view, guarantee |
| PR-03 | Copyright complaint from a publisher | 2 | 4 | Own-use gate, rights light, whole-book block, terms (pillar 04) |
| PR-04 | Browser voice fails on low-end phones | 3 | 2 | Device voice fallback; Azure option; clear requirement text |
| PR-05 | Docs and marketing drift from code again | 3 | 2 | Count tests; single source of truth table |
| PR-06 | Feature surface too large to maintain for one person | 3 | 3 | Freeze features until M2; measure usage; remove unused surfaces after launch |
| PR-07 | Retention promise conflicts with offline app expectations | 2 | 2 | PQ-13 decision |
| PR-08 | Accessibility claims without screen-reader testing | 2 | 3 | Test before M2; honest accessibility statement |

## 7. Decision checklist before M2 (product part)
- [ ] C-01 to C-08 resolved
- [ ] PQ-03 (AI levels at launch), PQ-06 (report location), PQ-13 (retention vs. offline, if app relevant) decided
- [ ] Instrumentation (§5) live and documented in the processing record
- [ ] Accessibility: Quick Start + player keyboard and screen-reader smoke test done; statement published
- [ ] Guided test findings triaged into Issues
- [ ] First-cohort plan agreed (pillar 05): size, channels, survey, interview slots
