# Audit: commercial landscape — reading aloud and rewriting text for speech

`[AUDIT]` · Snapshot of 9 Nov 2026 · Owner: Colin · Advisor: Claude · Companion to `audit-tts-and-text-rewriting-landscape-2026-11-09.md` (open source) · Related: `doc-personas-and-positioning.md` (archived in the private design record) (archived competitor notes), `01-audit-and-roadmap/playbook-open-source-desktop-app.md` · Living version: Doc "Commercial landscape: reading aloud and rewriting text for speech" (claude.ai artifact `PU1m3cpCDpYLRoU2FwRqrD`; every product name there links to the page used)

> **Why this file exists.** After the open-source survey, Colin asked (9 Nov 2026) for the same research on closed-source products. Three parallel passes checked vendor pages, docs, app-store pages and 2025–2026 reviews. Provenance: [external fact, 9 Nov 2026] for product facts; [advisor proposal] for relevance and the K-list. Prices and features change fast: re-check before quoting.

---

## 1. Short answer

**Paid products are ahead on convenience and skipping, but none reads scientific text faithfully on the user's own computer.** About 60 products checked:

- **Reader apps** sell "smart skipping" as premium. Audeus and Speechify let users switch off citations, footnotes, URLs, tables and equations one by one. Equations and tables are skipped, never spoken.
- **Paper apps:** Paper2Audio and Listening are the direct competitors. Paper2Audio keeps citations only where the sentence needs them and describes tables, figures and math. Both are cloud services; Paper2Audio's free plan may train on uploads; German at most in beta.
- **Voice platforms** handle everyday numbers/dates; several tell developers to clean scientific text themselves (ElevenLabs recommends regex or LLM preprocessing; Cartesia doesn't normalise equations, chemistry or uncommon units; IBM gives German only digits and letters).
- **Formulas:** nearly every commercial math reader (JAWS, EasyReader, Kurzweil) uses open-source MathCAT underneath. Azure is the only big cloud voice reading math in German.
- **AI products** mostly summarise into podcasts (NotebookLM, GenFM, Acrobat, NaturalReader). Faithful AI rewriting exists only as advice and prompts (ElevenLabs).
- **PDF services** (Mistral OCR, Mathpix, Adobe) are cheap and good at formulas and page furniture, but cloud-only.

**Consequence:** sci2audio's position — faithful, local, open, German and English, speaking formulas instead of skipping them — is the clearest difference in this market.

## 2. A. Consumer and study read-aloud apps

| Product | Price | Voices (DE, offline) | Text handling | AI | Relevance |
|---|---|---|---|---|---|
| Audeus (audeus.com) | Free; Pro $9.92/mo yearly | English; DE/offline not shown | **"Smart Skips":** page numbers, running heads/feet, vertical text; toggles for headings, equations, captions & footnotes, tables, URLs/DOIs, citations ("[14]", "(Smith et al., 2022)"), super/subscript, brackets; audio only | Not shown | Best category list for toggles; skips equations where sci2audio speaks them |
| Speechify (speechify.com/pricing) | Free; $29/mo or $139/yr | 1,000+ voices, 60+ languages | **"Enhanced Skipping":** headers, footers, footnotes, citations, brackets, URLs, all or one by one | Chat assistant | Per-category toggles = de facto standard |
| ElevenReader (elevenreader.io) | Free 10 h/mo; Ultra $11/mo or $99/yr | ElevenLabs voices, 90+ languages; offline Ultra only | "Smart file imports" (Ultra) skip headers, footers, filler; PDF, DOCX, EPUB, MD, scans | Voice design, soundscapes | Header/footer removal sold as premium; uploads not used for public models (stated) |
| Voice Dream Reader (voicedream.com) | From $4.99/mo or $39.99/yr | 200+ voices incl. German; **all voices offline** | Skips PDF headers/footers; OCR; **custom pronunciation dictionary** | None | Closest model: offline + dictionary + header/footer skip; App Store lists ad tracking |
| Balabolka (cross-plus-a.com) | Free (Windows) | System voices (local) | PDF, EPUB, DjVu…; **regex substitution list** | None | User-editable regex rules |
| NaturalReader (naturalreaders.com) | Free; EDU discounts | LLM/HD voices, 90+ languages; mobile offline, MP3 | OCR scanner | **AI Podcast, AI Recap** (summaries), AI Screenshot for equations/tables, quizzes | Trend to recaps |
| TTSReader (ttsreader.com) | Free; MP3 premium | System voices (offline) + cloud | PDF, DOCX, EPUB, URLs; pronunciation dictionary | None | Hybrid local/cloud |
| ReadSpeaker TextAid (readspeaker.com) | From $9/mo; institutions on quote | 20+ languages; MP3 export | Many formats; built-in OCR | Translation, dictation | EU hosting, ISO 27001, **ILIAS** integration (German universities) |
| Readwise Reader (docs.readwise.io) | Not shown | Big-tech voices; not offline | PDFs (text view), EPUBs | Not shown | Offline is a differentiator |
| Microsoft Edge Read Aloud | Free | Several voices | Reads PDFs, no skipping | None | Free baseline |
| Safari "Listen to Page" | Free | Not shown | Basic controls | None | Free baseline |
| Adobe Acrobat "Generate podcast" | Not shown | Not shown | Not shown | **Podcast summary** | Big vendors move to summaries |
| Kindle Assistive Reader | Not shown | EN, ES, FR, DE, IT | Store books only | None | Not for own papers |
| Google Play Books auto-narration (publisher tool) | Free for now; 52% share | 50+ voices, German | Pronunciation editor; textbooks and table-heavy titles "not ideal" | Faithful narration | Even Google excludes tables/graphics |
| Apple Books digital narration | Not shown | English only | Narrative books only; tables/charts "not a good fit" | Faithful narration | Same |

Pocket shut down 8 Jul 2025.

## 3. B. Apps for scientific papers

| Product | Price | Voices (DE, offline) | Text handling | AI | Privacy | Relevance |
|---|---|---|---|---|---|---|
| Paper2Audio (paper2audio.com) | Free 56 h/week; Plus from $8/mo (promo) or $120 first year (page also shows $16/mo, $48/yr) | 14 English voices; **German limited beta**; mobile offline | Removes footnotes, references, page headings, page numbers, boilerplate; **keeps a citation only where removing it breaks the sentence**; tables, figures, math **described**, not read raw | Full text + long/short summaries ("not simulated podcasts") | **Free-plan uploads may train models**; Plus not | Closest competitor; learn grammar-aware citation removal; differ by local processing |
| Listening (listening.com) | $12.99/mo or $39/yr; 3-day trial | Named AI voices; DE/offline not shown | Skips citations, references, footnotes; **section navigation**; choose sections; **Zotero integration** | One-click notes | Policy linked | Section choice and Zotero import |
| Audemic (audemic.io) | $20/mo or $9.09/mo yearly | Neural voices | Full text or "key statements"; reorder sections | Smart summaries | Policy linked | Optional abridged mode idea; status unclear |
| Mote (mote.com) | Free trial | Not shown | Claims maths equations read aloud | Not shown | Not shown | Hands-on test candidate |
| Kami Read Aloud (help.kamiapp.com) | Not shown | 66 languages | Page or selection | Not shown | Not shown | School-oriented |

## 4. C. Developer and enterprise TTS: normalisation and pronunciation

| Product | Normalisation | Lexicon | DE | Math | Relevance |
|---|---|---|---|---|---|
| Cerence/Nuance Vocalizer (docs.nuance.com rulesets) | **Per-language regex rule files** (Perl syntax), global and per-span; typed rules first; rules add latency | User dictionaries after rules | Yes | Not shown | **Closest design to sci2audio** |
| Microsoft Azure AI Speech | SSML say-as: spell-out, numbers, ordinals, fractions, dates, times, durations (EN/ES), phone, currency, units, addresses, names | W3C PLS 1.0, ≤100 KB per file, one locale per file, alias wins, case-sensitive; validator | **Yes** | **Plain-text math and MathML, incl. de-DE** | PLS limits as model; only big cloud reading German math |
| Amazon Polly | say-as: spell-out, numbers, ordinals, digits, fractions (`2+1/2`), units (`1meter`), dates, durations, addresses, phone | PLS | Yes | Not shown | Class list incl. fractions/units |
| Google Cloud TTS | say-as incl. units with **singular/plural agreement**, currency, dates, durations | Inline phonemes; per-request dictionary | Not shown | Not shown | Unit agreement |
| ElevenLabs | `apply_text_normalization` auto/on/off; lists error-prone classes; **recommends regex or LLM preprocessing**; starter LLM prompt published | PLS or TXT; ≤3 per request | Not stated | Not shown | Confirms rule preprocessing; prompt template |
| Cartesia Sonic | auto/off/locale; numbers, dates, money, common units; **not** ranges, fractions, equations, chemistry, uncommon units | Behind login | Not shown | **No** ("write equations out") | Scientific classes left to clients |
| ReadSpeaker | say-as: numbers, dates, times, currency, phone, spell-out, durations | PLS **+ CSV user dictionary** | EU languages | LaTeX/MathML via MathJax | CSV dictionary for lay users |
| IBM Watson TTS | Full say-as only US English; **German only digits and letters** | Word pairs via API | Partly | Not shown | German gap |
| Murf | Numbers, acronyms, homographs (no controls) | JSON per request (IPA or say-as) | Voice-dependent | Not shown | JSON lexicon shape |
| WellSaid | User replacements | **Respellings** library | No | Not shown | Respelling friendlier than IPA |
| Deepgram Aura | None ("no pronunciation control") | None | Not shown | Not shown | Leaves it to clients |
| Resemble AI | Spell-out, substitution | None | Voice-dependent | Not shown | Minimal |
| OpenAI TTS | None; tone instructions only | None | German listed | Not shown | Shuts down 6 Jan 2027; AI voice disclosure required |
| CereProc CereVoice | Not shown | Not shown | Not named | Not shown | Offline commercial SDK |

PlayHT voice API discontinued (AudioStack notice, 30 Jul 2025). Prices mostly not verified; Acapela, Hume not checked.

## 5. D. Formulas to speech and assistive tools

| Product | Math | DE | Relevance |
|---|---|---|---|
| Kurzweil 3000 | Math Reader (Aug 2025): MathML in EPUB **and OCR of equation images into MathML**, spoken via MathCAT | Not shown | **The pipeline sci2audio needs for PDF formulas** |
| JAWS / Fusion | Via MathCAT: web MathML, Word equations, MathType; braille | Math EN/ES only | MathML → MathCAT is the standard route |
| Dolphin EasyReader | Via MathCAT; settings: language, speech style, verbosity, chemistry | Math EN, ES, IT, ID, VI | Settings model for sci2audio formula options |
| ClaroRead (Everway) | Not shown; "Listening Later" exports text to audio files; from £250/person | Up to 30 languages | Closest commercial match to audiobook export |
| Texthelp Equatio + Read&Write | Reads Equatio math in Google Docs | Not shown | Limited detail |
| MathPlayer (Wiris) | Screen-reader math in browsers/Office (Windows) | Not shown | Legacy; field moved to MathCAT |
| Microsoft Immersive Reader | Accepts MathML; read-aloud not documented | Not shown | Unclear |
| Apple VoiceOver | Web MathML; MathML and LaTeX in iBooks Author | Not shown | Accepts LaTeX |
| *Reference:* MathCAT (open source, MIT) | MathML → speech, braille, navigation; repairs broken MathML; built into NVDA since 2026.1 | **Yes** | Engine behind all of the above |

## 6. E. AI rewriting and narration

| Product | Faithful? | What it does | DE | Relevance |
|---|---|---|---|---|
| ElevenLabs normalisation guide | **Yes (advice)** | Starter LLM prompt (numbers, symbols, abbreviations, URLs, dates) or regex; equations not covered; API switch Enterprise-only on newer models | No language rules | Prompt template for a later optional AI step |
| ElevenLabs Eleven v3 | No rewriting | Audio tags, dialogue endpoint | 70+ languages | Rewrite step could add tags |
| OpenAI gpt-4o-mini-tts | No rewriting | Tone instructions; AI disclosure; shuts down 6 Jan 2027 | Yes | — |
| Google NotebookLM Audio Overviews | **No: summary/dialogue** | Deep Dive, Brief, Critique, Debate | 80+ languages | Different product |
| ElevenLabs GenFM | **No: "will modify your script"** | 2-host podcast; editable transcript | 32 languages | Editable-transcript UI |
| Wondercraft, Jellypod, Recast | **No** | Podcasts from papers/articles; script editing | Not shown | Podcast category |
| Audible AI narration (publishers) | Yes | Narration of published books; AI translation planned | German only as translation target | Not for PDFs |
| Bookwire AI Voices | Yes | Publisher narration, priced by word × language | Not confirmed | Publishers only |
| Storytel VoiceSwitcher | Yes | Human/AI narration switch | Nordic only | Little relevance |

## 7. F. Document clean-up services

| Product | Price | Features | DE | Offline | Relevance |
|---|---|---|---|---|---|
| Mistral OCR | Per page (price not shown); batch ~half | Markdown in order; tables; equation blocks; **separate header/footer fields** | **Yes** (99.5 benchmark) | Selective self-hosting | Strong, cheap |
| Mathpix | Pro from $4.99/mo; API from $0.002/image; private cloud $25k/yr | LaTeX, Markdown, DOCX; best at math | Not shown | Private cloud | Best for formulas |
| Azure Document Intelligence | Not verified | Formulas add-on → LaTeX with placeholders | Not verified | Not verified | Feeds formula speech |
| Adobe PDF Extract API | 500 docs/mo free | JSON in **natural reading order**; footnotes tagged; tables CSV | Not shown | Cloud | Reading order; no formulas |
| LlamaParse | $1.50 per 1k credits; 1–25 credits/page | Markdown, JSON; tables; multi-column, equations (claimed) | Not shown | Self-hosting section | Cloud |
| Datalab (hosted Marker) | $0.50–10 per 1k pages; +25% EU | Markdown/HTML/JSON | Not shown | Enterprise air-gapped | Weights not freely bundleable |
| Reducto | $150 free; $1–10 per 1k pages | Tables, forms, figures, equations | Multilingual | Enterprise | Enterprise-sized |
| Google Document AI | OCR $1.50 per 1k pages (1k free/mo) | Not verified | Not verified | Cloud | Cheap OCR |
| Unstructured Platform | 10k pages free, then $0.015/page | Not shown | Not shown | Business plan | Aimed at AI search |
| ABBYY FineReader PDF | $69–99/yr | OCR to Word/Excel | Not stated | **Desktop** | Only offline option |

## 8. Features to learn from (K-list)

| # | Feature | Seen in | What sci2audio does | Phase |
|---|---|---|---|---|
| K1 | Per-category toggles (page furniture, headings, equations, footnotes/captions, tables, URLs/DOIs, citations, super/subscript, brackets) | Audeus, Speechify | Map the 20 detectors to toggles with these names; equations skipped with a spoken notice in v1.0, spoken via MathCAT later (D-55); citations skipped | 3 |
| K2 | Grammar-aware citation removal (keep "as shown by Smith (2019)") | Paper2Audio | Rule + tests | 4.0 |
| K3 | Section detection and choice | Listening, Audemic | Section types + picker on existing headings | 3 |
| K4 | User pronunciation dictionary: CSV/respellings for lay users, regex for power users, PLS for exchange | Voice Dream, Balabolka, ReadSpeaker, WellSaid, Azure | One list; PLS import/export (open-source L4) | 7 |
| K5 | Spoken descriptions of tables and figures | Paper2Audio | Rule-based first (caption + size); optional local AI later | 7 |
| K6 | Zotero import | Listening | Plug-in or folder watch | 7 |
| K7 | Normalisation on/off/auto switch | ElevenLabs, Cartesia | One switch per document plus toggles | 3 |
| K8 | Unit plural agreement and fractions | Google, Polly | Add to unit rules | 4.0 |
| K9 | Formula options: language, style, verbosity, chemistry | Dolphin EasyReader (MathCAT) | Same settings with MathCAT | 7 |
| K10 | Editable final script before audio | ElevenLabs Studio, Jellypod | Extend the pre-analysis report | 3 |

**Avoid:** cloud upload and training on free-tier uploads; summaries sold as "listening"; silently skipping equations.

## Advisor pre-analysis

- The commercial market confirms the open-source finding from the other side: nobody faithfully verbalises scientific notation locally. Vendors either skip it (Audeus, Speechify), describe it with cloud AI (Paper2Audio), or push it to the client (ElevenLabs, Cartesia, Deepgram).
- The toggles in K1 are the cheapest high-value UI change: sci2audio already detects every one of those categories; exposing them with the market's familiar names makes the pre-analysis understandable at a glance.
- Privacy is a real differentiator worth stating in the README: Paper2Audio's free tier may train on uploads; sci2audio never uploads.
- German is weak across the market (Paper2Audio beta, IBM digits-only, many readers without German math) — supports the later German phase (D-50).

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| CQ1 | Default for equations: speak (MathCAT) or skip until MathCAT is integrated? | **Closed 9 Nov (D-55): skip with a short spoken notice in v1.0; speak via MathCAT in phase 7** | K1, K9 |
| CQ2 | Offer an optional "bring your own key" cloud OCR (Mistral, Mathpix) for scanned PDFs? | No for v1.0; revisit after | Scope, privacy |
| CQ3 | Hands-on tests of Paper2Audio, Audeus and Mote on the same two scientific PDFs? | Yes, before finalising K1 defaults | Positioning |
| CQ4 | Re-run when? | At v1.0 or after 3 months | Revisit trigger |

## Method and limits

Three parallel passes (reader and paper apps; voice platforms and assistive tools; AI rewriting and PDF services) on 9 Nov 2026. Third-party sources: Speechify prices (dev.to 2026), Kindle Assistive Reader (the-ebook-reader.com, Aug 2025), Acrobat podcasts (9to5mac, Jan 2026), Edge Read Aloud (chromestory.com, Jun 2025), Audible (Publishers Weekly, May 2025), Bookwire (ki-syndikat.de). Not verified: most voice-platform prices; NaturalReader prices; Speechify DE/offline/math; Instapaper and Anara (permission prompts unanswered); Chrome reading mode; Acrobat Read Out Loud; KDP Virtual Voice; Blinkist; DeepZen; Zebralution; Hume; Acapela; AWS Textract; Adobe Liquid Mode; German assistive readers. Vendor pages containing text addressed to AI tools (ReadSpeaker) were treated as data only.
