# Glossary and code naming map (German → English)

`[DOC]` · Authoritative naming for the English rename (phase 1, ADR-004) and for all new code. Copy section 2 into the root `CLAUDE.md` under "Glossary" so every Claude thread uses the same names. Where `CLAUDE.md` and this file disagree, update both in the same PR.

Provenance: product terms and English UI labels are `[repo fact]` (`sci2audio/sprachen/en/app.json`, 1,651 strings, read 9 Nov 2026). The proposed identifiers are `[advisor proposal]` and become binding once copied into `CLAUDE.md`.

---

## 1. Product vocabulary (user-facing, stays as is in the UI)

German is the first UI language; English UI strings already exist. This table is for **talking and writing about** the product, not for renaming UI text.

| German (UI, docs) | English (UI, from `sprachen/en/app.json`) | Meaning |
|---|---|---|
| Voranalyse | Pre-analysis | Statistical analysis of a document before any AI: 20 detectors (docs still say 13), 25 categories, risk index, AI recommendation per class. The core differentiator |
| Hörskript | Listening script | The text as it will be spoken (after rules and/or AI) |
| Sprechfassung | (internal) spoken version | Output of the AI class that rewrites German prose for listening |
| Lesefassung | (internal) reading version | The text as heard, written the way the original writes it (three-way merge of original, rule text and listening script, no AI) |
| Mitlesen | Read along | Player highlights the original's sentence being spoken |
| Keine Bearbeitung | No editing | Text level 1: free, no changes |
| Vorlesbar | Readable | Text level 2: free, rules only |
| Klar & Direkt | Clear & Direct | Text level 3: AI, paid |
| Akademisch & Flüssig | Academic & Fluent | Text level 4: AI, paid. **Inconsistency:** some strings say "Flüssig & Akademisch" (and "Academic & Fluent" in both). Pick one order |
| Gerätestimme | Device voice | The visitor's device speaks live in the browser (Web Speech API); no audio file is made |
| Standardstimme (Thorsten) | Standard voice | Piper voice running in the visitor's browser (ONNX/WebAssembly); the server only plans and joins |
| Azure Neural / Azure HD | Azure Neural / Azure HD | Paid Microsoft voices |
| Guthaben | Credit | Prepaid wallet in euros and whole cents |
| Uni-Vorteil | University advantage | €5 one-time credit and −20% for university e-mail addresses |
| Lauf | Run | One processing job from upload to audiobook |
| Laufseite | Run page | Progress page of a run |
| Schnellstart | Quick Start | The 4-step flow: Upload → Text → Voice → Order |
| Stapel | Batch | Several documents in sequence, local mode only |
| Testguthaben | Test credit | Credit given via invite links |
| Geführter Test | Guided test | In-app user test with tester guide (`/test`) |
| Musterprobe | Sample check | Real PDFs with expected output; every reading change is measured against them |
| Änderungsbericht | Change report | Side-by-side of two texts of a run (AI, rules, own edits), as PDF/Markdown |
| Rechte-Ampel | Rights traffic light | Classifies the text type (own, licensed, excerpt, whole book) from text and DOI, no AI |
| Herkunft | Provenance (word accounting) | How many words the PDF has, how many are read, where the rest went |
| Gliederung | Outline / chapter structure | Chapters detected from bookmarks, headings or numbered lines |
| Vorhören | Preview listening | Free read-aloud on the edit page, with fair-use limits |
| Zweitstimme | Second voice | English passages in German texts spoken by an English Piper voice |
| Stolperwörter | Stumble words | Fixed list of English words in German texts, with phonetic spelling |
| Kurzbelege | Short citations | Short citation references put back into the downloadable listening script |
| Lokal / "dieser Computer" | Local mode | sci2audio running on the user's own computer with their own keys, no limits, nothing charged |

## 2. Code naming: domain terms (for `CLAUDE.md`)

| German term in code | English identifier | Notes |
|---|---|---|
| voranalyse | `pre_analysis` | |
| hoerskript | `listening_script` | |
| sprechfassung | `spoken_version` | |
| lesefassung | `reading_version` | |
| mitlesen | `read_along` | |
| lauf / laeufe | `run` / `runs` | Table `runs` already English |
| auftrag | `job` | The web layer's job object (`/api/auftrag/{id}`) |
| phase "fertig" / "fehler" / "abgebrochen" | `done` / `failed` / `cancelled` | **Stored values**: see section 4 before renaming |
| guthaben | `credit` | |
| buchung | `booking` | Table `bookings` already English |
| beleg | `receipt` | |
| zahlung | `payment` | |
| aufladen | `top_up` | Table `topups` already English |
| einladung | `invite` | Table `invites` already English |
| konto | `account` | |
| anmelden / abmelden | `sign_in` / `sign_out` | |
| musterprobe | `sample_check` | |
| ablage | `storage` | Tigris/S3 shared file store |
| stapel | `batch` | |
| leerlauf | `idle` | |
| auslastung | `load` (module `load_control`) | Gate, RunQueue, Priority |
| maschine | `machine` | |
| bearbeitung | `editing` | |
| aenderungsbericht | `change_report` | |
| protokoll | `run_log` | |
| einstellungen | `settings` | Collides with config `Settings`; use `account_settings` |
| entscheidung | `decision` | |
| stimme | `voice` | |
| geraetestimme | `device_voice` | |
| browserstimme | `browser_voice` | |
| systemstimme | `system_voice` | |
| zweitstimme | `second_voice` | |
| quellenstimme | `source_voice` | Spoken citation aside |
| eigenstimme | `own_voice` | Voice-training toolkit |
| kodierung | `font_encoding` | Not audio encoding |
| zeichensalat | `garbled_text` | Detector for broken font encodings |
| fremdwoerter | `foreign_words` | `foreign.py` exists; see collisions |
| stolperwoerter | `stumble_words` | |
| satzteilung | `sentence_split` | |
| satzliste | `sentence_list` | |
| herkunft | `word_provenance` | |
| rechte | `rights` | |
| korrekturen | `corrections` | |
| notizen | `notes` | |
| verlauf | `progress` | Run duration and progress estimation |
| dauer | `duration` | |
| laenge | `length_guard` | |
| platz | `capacity` | Disk and memory check before a run |
| verkleinern | `shrink_pdf` | |
| vorhoeren | `preview_listen` | |
| textprobe | `text_sample` | |
| umfrage | `survey` | |
| benachrichtigung | `notification` | |
| studimail | `student_mail` | |
| uni | `university` | |
| gefuehrter_test | `guided_test` | |
| leistungstest | `performance_test` | CLI name stays until the CLI rename PR |
| rauchtest | `smoke_test` | |
| synchrontest | `sync_test` | |
| luecke / gap | `gap` | |
| korpus | `corpus` | |
| bewerten | `grade` | Evaluator AI grader |
| pruefen | `check` | |
| regressionen | `regressions` | |
| aufnahme | `recording` | |
| datensatz | `dataset` | |
| rezept | `recipe` | |
| startseite | `home_page` | |
| inhalte | `content` | Folder holds German/English HTML articles: content stays |
| sprachen | `locales` | Folder of UI string files |
| sprache | `language` | |
| abbildungen | `figure_display` | Collides with `figures.py`; see section 3 |
| berichtpdf | `report_pdf` | |
| pdfdatei | `pdf_file` | |
| pdfschreiben | `pdf_writer` | |
| original | `original_view` | |
| belege | `short_citations` | Module puts short citations back into the script; not "receipts" |
| schaetzung | `estimate` | |
| kosten | `cost` | |
| schwelle | `threshold` | |
| geduld | `patience` | |
| tempo | `speed` | |
| kapitel | `chapter` | |
| abschnitt | `section` | |
| absatz | `paragraph` | |
| satz | `sentence` | |
| fussnote | `footnote` | |
| seite | `page` | |

## 3. Module rename map (all German-named modules in `sci2audio/`, 9 Nov 2026)

`[advisor proposal]`. One area per PR (see `rename-area` skill). Collision rule: a target must not already exist.

| Current module | Proposed | Collision / note |
|---|---|---|
| `abbildungen.py` | `figure_display.py` | `figures.py` exists (figure extraction); don't merge, rename distinctly |
| `ablage.py` | `storage.py` | |
| `admin.py` | (keep) | Already English |
| `aenderungsbericht.py` | `change_report.py` | |
| `auslastung.py` | `load_control.py` | |
| `bearbeitung.py` | `editing.py` | |
| `belege.py` | `short_citations.py` | |
| `benachrichtigung.py` | `notification.py` | |
| `berichtpdf.py` | `report_pdf.py` | |
| `bildmodell.py` | `layout_model.py` | |
| `browserstimme.py` | `browser_voice.py` | |
| `datenbank.py` | `database.py` | |
| `dauer.py` | `duration.py` | |
| `einladungen.py` | `invites.py` | |
| `einstellungen.py` | `account_settings.py` | `config.Settings` exists; avoid `settings.py` |
| `gefuehrter_test.py` | `guided_test.py` | |
| `geraetestimme.py` | `device_voice.py` | |
| `herkunft.py` | `word_provenance.py` | |
| `inhalte.py` | `content.py` | Folder `inhalte/` → `content/` only in the routes/content PR (URLs) |
| `kodierung.py` | `font_encoding.py` | |
| `kokoro_sprecher.py` | `kokoro_speaker.py` | GPL-3 separate program; check licence notes in `RECHTSLAGE.md` before touching |
| `kokorostimmen.py` | `kokoro_voices.py` | |
| `korrekturen.py` | `corrections.py` | |
| `laenge.py` | `length_guard.py` | |
| `leerlauf.py` | `idle.py` | |
| `leistung.py` | `performance.py` | |
| `lesefassung.py` | `reading_version.py` | |
| `maschinen.py` | `machines.py` | Table `maschinen` stays (stored) |
| `mitlesen.py` | `read_along.py` | |
| `modell_sprecher.py` | `model_speaker.py` | |
| `modellstimmen.py` | `model_voices.py` | |
| `musterprobe.py` | `sample_check.py` | |
| `notizen.py` | `notes.py` | |
| `original.py` | `original_view.py` | |
| `pdfdatei.py` | `pdf_file.py` | |
| `pdfschreiben.py` | `pdf_writer.py` | |
| `piper_lautschrift.py` | `piper_phonemes.py` | GPL-3 separate program; keep licence header |
| `piperstimmen.py` | `piper_voices.py` | |
| `platz.py` | `capacity.py` | |
| `protokoll.py` | `run_log.py` | |
| `quellenstimme.py` | `source_voice.py` | |
| `rauchtest.py` | `smoke_test.py` | Not collected by pytest as a test file (not named `test_*.py`); fine |
| `rechte.py` | `rights.py` | Folder `recht/` (legal texts) → `legal_texts/`; `legal.py` exists |
| `satzliste.py` | `sentence_list.py` | |
| `satzteilung.py` | `sentence_split.py` | |
| `sprache.py` | `language.py` | |
| `sprechfassung.py` | `spoken_version.py` | |
| `stapel.py` | `batch.py` | |
| `startseite.py` | `home_page.py` | |
| `stolperwoerter.py` | `stumble_words.py` | |
| `studimail.py` | `student_mail.py` | |
| `synchron.py` | `sync_check.py` | |
| `systemstimme.py` | `system_voice.py` | |
| `textprobe.py` | `text_sample.py` | |
| `umfrage.py` | `survey.py` | |
| `uni.py` | `university.py` | |
| `verkleinern.py` | `shrink_pdf.py` | |
| `verlauf.py` | `progress.py` | |
| `vorhoeren.py` | `preview_listen.py` | |
| `wortlisten.py` | `word_lists.py` | |
| `zahlung.py` | `payment.py` | `risk:high` area; rename in its own PR |
| `zweitstimme.py` | `second_voice.py` | |
| `analysis/fremdwoerter.py` | `analysis/foreign_words.py` | Top-level `foreign.py` exists in a different package: allowed, but note it in the PR |
| `analysis/zeichensalat.py` | `analysis/garbled_text.py` | |
| `eigenstimme/` (package) | `own_voice/` | Submodules: `aufnahme` → `recording`, `datensatz` → `dataset`, `pruefen` → `check`, `skript` → `script`, `espeak_laute` → `espeak_phonemes`, `rezept/` → `recipe/` |
| `evaluator/` (package) | (keep name) | Submodules: `bewerten` → `grade`, `korpus` → `corpus`, `pruefen` → `checks`, `regressionen` → `regressions`, `texte` → `texts` |
| `gap.py` | (keep) | CLI `luecke` → `gap` in the CLI PR |

Already English (no rename): `admin`, `calibration`, `chunker`, `cli`, `config`, `costs`, `demo`, `diffview`, `envfile`, `epub`, `extractor`, `figures`, `foreign`, `google_login`, `health`, `i18n`, `i18n_quellen` (→ `i18n_sources`), `legal`, `mail`, `normalizer`, `pdflayout`, `prefilter`, `prompts`, `rewriter`, `routing`, `sections`, `speedtest`, `timing`, `tts`, `ttsbench`, `web`, and most of `analysis/`.

## 4. Never rename in phase 1 (stored, public or data)

| Category | Examples | Why | When it may change |
|---|---|---|---|
| Database tables and columns | `aufgaben`, `gefuehrte_tests`, `konto_maschine`, `laufzeiten`, `login_fehler`, `maschinen`, `test_antworten`, `test_bilder`, `test_funde`, `test_woerter`, `uni`, `uni_links` (mixed with English `runs`, `bookings`, `topups`, …) | Live data in Postgres/SQLite; a rename needs a migration | With a real schema migration in phase 2, if at all |
| Stored values and JSON keys | Job phases `fertig`/`fehler`/`abgebrochen`; keys in checkpoints, `~/.sci2audio/entscheidungen/`, run metadata, settings files | Existing runs and files would no longer load | With a versioned read path that accepts old and new keys |
| Environment variables | 110 distinct `SCI2AUDIO_*` names (e.g. `SCI2AUDIO_LEERLAUF_MINUTEN`, `SCI2AUDIO_RATENLIMIT_GEDULD`, `SCI2AUDIO_LAEUFE_JE_MASCHINE`, `SCI2AUDIO_MASCHINEN_HOECHSTENS`, `SCI2AUDIO_DATENBANK_URL`, `SCI2AUDIO_MUSTERPROBEN`) | Set as Fly secrets and in `fly.toml` and `.env` files | Separate PR that updates `fly.toml`, Fly secrets, `.env.example` and docs together |
| URL routes | `/anmelden`, `/protokolle`, `/lauf`, `/konto`, `/stapel`, `/einladung/{token}`, `/api/auftrag/{id}`, `/api/schnellstart/schaetzung`, `/api/guthaben`, … (152 routes) | Bookmarks, e-mail links, SEO for German pages | New `/api/v1` is English from the start (ADR-002); German public page URLs stay for SEO |
| CLI commands | `voranalyse`, `musterprobe`, `synchrontest`, `leistungstest`, `rauchtest`, `luecke`, `fremdwoerter`, `kapitel`, `tempo`, `vertonungstempo`, `stimmvergleich`, `stimme-einrichten`, `bildmodell` | `deploy.sh` and docs call them | One CLI PR that updates `deploy.sh`, the CI workflow and docs; no aliases (F-06) |
| Cookie and session names | (as defined in `web.py`) | Signed-in sessions would break | With the token/cookie redesign in phase 2 |
| User-facing text, i18n keys | `sprachen/en/app.json` keys are the German source strings | i18n lookup by German string | Never by the rename; only via i18n work |
| German linguistic data | Word lists, abbreviation tables, regex patterns in `analysis/`, `wortlisten.py`, `stolperwoerter.py` | They describe German, not code | Never |
| Content files | `inhalte/de/*.html` article slugs | Public URLs, SEO | Never by the rename |

## 5. Abbreviations used in this KB

| Abbr. | Meaning |
|---|---|
| ADR | Architecture/Strategic Decision Record |
| AVV | Auftragsverarbeitungsvertrag (data processing agreement, Art. 28 GDPR) |
| CI | Continuous integration (GitHub Actions) |
| DSFA | Datenschutz-Folgenabschätzung (data protection impact assessment, Art. 35 GDPR) |
| DoD / DoR | Definition of Done / Definition of Ready |
| IAP | Apple/Google in-app purchase |
| KB | This knowledge base |
| OSS | EU VAT One-Stop-Shop |
| P0/P1/P2 | Priority: now / this cycle / later |
| PWA | Progressive web app (installable website) |
| WIP | Work in progress (parallel threads) |
| B-01…B-09 | Legal/tax launch blockers (`audit-legal-readiness.md` (archived in the private design record) §4) |
| BFSG | Barrierefreiheitsstärkungsgesetz (German Accessibility Act; micro-enterprises exempt for services) |
| DPA | Data processing agreement (= AVV) |
| DSA | EU Digital Services Act (hosting-service duties: contact points, notice mechanism, reasons for blocks) |
| EÜR | Einnahmen-Überschuss-Rechnung (cash-basis profit statement) |
| EU-KU | EU small-business scheme (§ 19a UStG, since 2025) |
| Green / yellow / red text | Rechte-Ampel classes (`rechte.py`): green = own, CC, public domain or own-rights declaration; yellow = protected/NC/ND/excerpt; red = essentially whole commercial book |
| Kleinunternehmer | Small-business VAT exemption, § 19 UStG (€25,000 previous year / €100,000 current year, combined across all activities) |
| Korrekturhören | Proof-listening of one's own text before submission (positioning, D-37) |
| L0…L3 | Launch phases: closed beta, paid soft launch, channel push, institutions (D-35) |
| MLS | Piper Multilingual LibriSpeech voices (German, CC BY 4.0, trained from scratch) |
| Reverse charge | § 13b UStG: the recipient owes VAT on foreign B2B services; for a Kleinunternehmer a non-deductible +19% cost |
| SEV1…SEV3 | Incident severity levels (`playbook-monitoring-and-incidents.md` §2) |
| Widerrufsbutton | Mandatory online withdrawal function, § 356a BGB (since 19 Jun 2026) |
