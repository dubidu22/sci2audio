# Audit: English text preparation — sci2audio's rules vs. spaCy and Kokoro's front end

`[AUDIT]` · Snapshot of 9 Nov 2026 · Owner: Colin · Advisor: Claude · Related: `06-open-source-landscape/audit-abogen-vs-sci2audio-2026-11-09.md`, `01-audit-and-roadmap/playbook-open-source-desktop-app.md` (phases 4–5), `decision-log.md` D-50…D-54, `doc-pipeline-architecture.md`, `doc-prompts-and-detector-rules.md` · Reproduce with `tools/english_check/compare.py` and `tools/english_check/sample_en.md` · Living version with diagram: Doc "English text preparation: spaCy or sci2audio's rules?" (claude.ai artifact `Y41pYQkGBsockBnktvqcCf`)

> **Why this file exists.** Colin ran Abogen's desktop app on a MacBook Pro M4 (9 Nov 2026): about 8 minutes of English audio in about 30 seconds, English voice "very good", but URLs read as "h t t p s double colon slash slash…" and visible PDF artefacts in the text. He then decided: **English first** (bigger community) and **rule-based preparation, not AI rewriting** (D-50, D-51). He asked whether spaCy could help the rule-based approach or whether sci2audio should stick with its own rules, and proposed reusing Abogen's TTS module. This audit answers both with a reproducible test.

---

## 1. Short answer

- **Keep sci2audio's rule engine for the scientific clean-up.** It handles citations, URLs, e-mail addresses, symbols, statistics, units, figure/table references, abbreviations and running footers; neither spaCy nor Kokoro's front end does. [advisor proposal, based on §4]
- **Use spaCy where it is strong — inside misaki, Kokoro's English pronunciation front end — not as a second rule engine.** misaki uses spaCy's part-of-speech tags to choose pronunciations of homographs ("read", "record", "wound") and speaks ordinary numbers correctly. Reusing Abogen's Kokoro plugin brings misaki and spaCy along. [repo fact for Abogen; external fact for misaki; advisor proposal for the split]
- **spaCy on its own adds little** to scientific text: noisy named entities, sentence splits at "Approx.", no help with hyphenation, symbols, units or ligatures. [test result, §4]
- **Why Abogen sounded better:** sci2audio sends English to Kokoro through `kokoro-onnx` `create(text, lang=…)`, which phonemises with espeak-ng. Abogen uses Kokoro's `KPipeline`, which runs misaki (dictionary + spaCy) first and uses espeak-ng only for unknown words. [repo fact: `sci2audio/kokoro_sprecher.py` line 115; Abogen `webui/conversion_runner.py` `KPipeline(lang_code=…, repo_id="hexgrad/Kokoro-82M", device=…)`]

## 2. What went wrong in Colin's Abogen run

Evidence: Abogen "Select Pages" screenshot and the web-UI log, 9 Nov 2026. [session decision: Colin's own run]

| Observation | Example | Cause |
|---|---|---|
| Hyphenation left in the text | "diffi- culties", "rea- sons", "develop- ment", "Fig- ure", "ter- ror-related" | Abogen's `PdfParser.process_content` reads raw page text and never joins hyphenated words |
| Space before full stops | "events . Specifically", "stan- dards , which" | Regex removes bracketed citation numbers, leaves the preceding space |
| Some citations kept | "searched [2–6, 16, 17]" | Citation regex misses ranges with an en dash and lists |
| Journal footer read | "Child Psychiatry Hum Dev (2016) 47:950–965 951" | No running-footer detection; only page numbers removed |
| Chapters "(Duplicate)", text starting mid-sentence | "Search Strategy…" starts "to misunderstanding of…" | Chapters cut by page from the PDF outline; several headings on one page become duplicates |
| URLs spelled letter by letter | "h t t p s colon slash slash…" | misaki has no URL rule; Kokoro's espeak-ng fallback spells the characters |
| Ligature kept | "Androﬀ" in the log preview | No Unicode compatibility normalisation of ligatures |
| Web UI job failed | `RuntimeError: MPS requested but fallback not enabled` | `abogen-web` (`webui/app.py`) doesn't set `PYTORCH_ENABLE_MPS_FALLBACK=1`; the desktop app (`pyqt/main.py`) and `abogen/main.py` do. Workaround: `PYTORCH_ENABLE_MPS_FALLBACK=1 abogen-web`, or CPU, or the desktop app |

[external fact: Abogen repo at commit `1807822`]

sci2audio's layout reader and detectors cover all of the text problems (hyphenation joined in `pdflayout.py`, citations and URLs removed, footers detected, chapters cut at headings). [repo fact]

## 3. What spaCy is and isn't

| spaCy feature | Useful for listening? | Evidence |
|---|---|---|
| Part-of-speech tags | **Yes**: homograph choice | 6 of 8 homograph cases right (via misaki) |
| `like_url`, `like_email` | Yes, but sci2audio's regex already finds them | All 3 found by both |
| Sentence segmentation | Partly | Wrong split after "Approx." and before "[1.2, 3.4])."; heading merged into the first sentence |
| Named entities | **No** for scientific text | "Fig" and "≥" as PERSON, "Table 2" as LAW, "CI" as WORK_OF_ART, citation "16" as DATE |
| `Matcher`, `EntityRuler` | Possible, but a different syntax for rules sci2audio already has | — |
| Hyphenation, symbols, units, ligatures | No | Not covered |

**Facts about the dependency:** spaCy 3.8.18 (MIT); `en_core_web_sm` 3.8.0, licence MIT per its metadata, ~15 MB on disk, pipes `tok2vec, tagger, parser, attribute_ruler, lemmatizer, ner`; 273 tokens processed in 0.04 s on the session machine. spaCy is a dependency of misaki's English G2P, so reusing Kokoro's `KPipeline` brings it in anyway. German needs a separate model (`de_core_news_*`). [external fact, measured 9 Nov 2026]

**Idea for later:** the Schwartz–Hearst abbreviation-definition algorithm (used in scispaCy) pairs "post-traumatic stress disorder (PTSD)" with its short form. It is a small rule algorithm sci2audio could implement directly to read the long form at first mention. [advisor proposal]

## 4. Test

**Setup.** A 270-word English text written for this test in the style of a psychology paper (`tools/english_check/sample_en.md`: author-year and numeric citations, URL, e-mail, hyphenation, ligature, symbols, statistics, units, abbreviations, a large number, Roman numerals, acronyms, homographs, a running footer). sci2audio ran its English path: `analyse(text, "en")` → `apply_fixes` → `rule_based_script(lang="en")`. misaki ran as Kokoro uses it (`misaki.en.G2P(trf=False)`, spaCy `en_core_web_sm`), with unknown words marked instead of sent to espeak-ng. [test, 9 Nov 2026]

**Result: sci2audio 7 right, 6 partly, 1 wrong of 14; misaki 3 right, 1 partly.**

| Case | Input | sci2audio rules | misaki (Kokoro EN) |
|---|---|---|---|
| Author-year citations | (Smith et al., 2019; Jones & Lee, 2020) | **Right:** "Sources: Smith and colleagues, twenty nineteen; Jones and Lee, twenty twenty" | Wrong: read inline, "et" unknown |
| Numeric citations | [2–6, 16, 17] | **Right:** removed | Wrong: numbers read |
| URL and e-mail | https://doi.org/…, www…, j.doe@… | Partly: removed, leaves "available at and." and "Contact:." | Wrong: spelled out |
| Hyphenation | develop- ment, diffi- culties, pro- cessing | Partly: 3 decisions for the user, not joined | Wrong: "develop ment" |
| Ligature | Androﬀ | Partly: decision, not fixed | Wrong: unknown |
| Symbols | ≥ 18, ± 12% | **Right:** "greater than or equal to eighteen", "plus or minus twelve percent" | Wrong: unknown |
| Statistics | n = 35, p < .05, 95% CI [1.2, 3.4] | Partly: "n equals thirty-five", "ninety-five percent confidence interval", but "p < zero point zero five" | Wrong: "=", "<" unknown; "CI" as letters |
| Units | 3.5 mg/kg, 37 °C | Partly: "three point five milligrams/kg"; "thirty-seven degrees Celsius" | Wrong: unknown |
| Abbreviations | i.e., e.g., vs., Dr., Fig. 1, Table 2, Approx. | **Right** except "Approx." (kept, next word capitalised) | Partly: Dr., vs. right; i.e., e.g. as letters |
| Large number | 1,234 participants | **Wrong:** "Twelve thirty-four" (read as a year) | **Right:** "one thousand two hundred thirty-four" |
| Roman numerals | World War II, Phase III | **Right:** "Two", "three" | Wrong: "World War I I" |
| Acronyms | PTSD, ADHD, CBCL | **Right:** spelled | **Right:** spelled |
| Homographs | read ×2, record ×2, wound ×2, lead ×2 | Partly: 8 decisions for the user | **Right** 6 of 8 (misses present-tense "read" and noun "lead") |
| Running footer | Child Psychiatry Hum Dev (2016) 47:950–965 951 | **Right** as a finding (decision), read aloud until confirmed | Wrong: read |

**Gaps in sci2audio's English rules found by the test (to fix, test-first):**
1. Speak "<" and ">" ("less than", "greater than") in statistics.
2. Units with a slash: "mg/kg" → "milligrams per kilogram".
3. Expand "Approx." (and don't capitalise the next word).
4. Read "1,234" as a number; only bare four-digit tokens in year contexts as years.
5. Tidy the words left behind when a URL or e-mail is removed ("available at and.", "Contact:.").
6. Join hyphenation and replace ligatures automatically when the joined/normalised word is a known word (wordfreq), instead of asking.
7. Drop a repeating running footer by default (decision only when uncertain).

Homograph decisions can be removed for English once misaki decides them (D-54).

## 5. Recommended architecture

1. **Input** (PDF, EPUB, text) → **layout reader** (`pdflayout.py`) → **rule engine** (20 detectors) — sci2audio's own GPL-3.0 code.
2. Hand-off: **clean English prose**. The rule engine leaves homographs and ordinary numbers alone.
3. **misaki** (spaCy POS for homographs, numbers, acronyms, dictionary; espeak-ng fallback for unknown words) → **Kokoro** model (PyTorch on the Apple chip, or ONNX with misaki phonemes via `is_phonemes=True`) — reused from Abogen's Kokoro plugin (MIT) and Kokoro/misaki (Apache-2.0).
4. **Output:** MP3 or M4B with read-along.

[advisor proposal]

## 6. Reusing Abogen's TTS module

| Part | Lines | Take? | Why |
|---|---|---|---|
| `abogen/tts_plugin/types.py`, `engine.py`, `errors.py` | ~310 | **Yes** | The contract: engine, session, synthesis request, audio result |
| `plugins/kokoro/engine.py`, `__init__.py` | ~400 | **Yes**, adapted | Wraps `KPipeline` (misaki + spaCy); voice list; language mapping |
| `tts_plugin/loader.py`, `manifest.py`, `plugin_manager.py`, `capabilities.py`, `host_context.py`, `utils.py` | ~1,350 | Not now | Third-party plugin discovery |
| Voice formulas and profiles | — | Later | Voice blending, not core |

[external fact: line counts at commit `1807822`; advisor proposal: selection]

- **How:** copy into `sci2audio/voices/`, keep Abogen's MIT copyright notice in each file header and in `THIRD_PARTY_LICENSES.md`. MIT code may be included in a GPL-3.0 app (D-42). Don't depend on the `abogen` package (pulls PyQt6, Flask, the whole app).
- **PyTorch vs. ONNX:** Abogen's speed on the M4 comes from Kokoro on PyTorch with the Apple GPU (MPS). `kokoro-onnx` 0.6.1 needs no PyTorch and accepts phonemes (`create(…, is_phonemes=True)`), so **misaki + ONNX** is a third option. A one-day spike decides (D-48 stays open until then).
- **Apple GPU:** set `PYTORCH_ENABLE_MPS_FALLBACK=1` before Kokoro loads.
- **Simplification:** `kokoro_sprecher.py` runs Kokoro in a separate process only to keep espeak-ng's GPL away from MIT code. With the app under GPL-3.0 (D-42), Kokoro can run in-process. [repo fact: module docstring]
- **Effort:** about 2–3 days including tests and the spike. [advisor proposal]

## 7. Consequences for the plan

- Playbook phase 4 now starts with **English** (4.1) and moves German to 4.2 (D-50). The German Thorsten Kokoro voice stays in D-43 but later.
- D-46 (slim plugin contract) is refined by D-52: the contract types and Kokoro plugin come from Abogen.
- D-48 (ONNX first) stays Proposed until the speed spike; misaki + ONNX keeps PyTorch optional if quality matches.
- `kokoro_sprecher.py`'s separate-process design can go during phase 3/4.

## Advisor pre-analysis

- The decisive fact is that Kokoro's English quality comes largely from misaki's front end, not only from the voice model. Any sci2audio English path that bypasses misaki (as the current ONNX + espeak-ng path does) gives that up.
- The split of work is clean and testable: sci2audio owns everything that is *scientific notation or layout*; misaki owns everything that is *ordinary English*. Each rule in the engine should be checked against that line — e.g. sci2audio's number rules should stop reading "1,234" and leave ordinary numbers to misaki.
- Turning the 14 cases into a regression test before touching rules is the AI-assisted-development habit to practise here: Claude threads can then change rules freely while the test guards behaviour.

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| EQ1 | PyTorch (MPS), misaki + ONNX, or espeak-ng + ONNX for English? | Decide by the one-day spike on Colin's M4 | D-48, D-52 |
| EQ2 | Should sci2audio pre-resolve homographs with spaCy for the read-along text, or trust misaki? | Trust misaki; revisit if listening tests find errors | D-54 |
| EQ3 | Implement the Schwartz–Hearst abbreviation pairing (long form at first mention)? | After v1.0 | Scope |
| EQ4 | Test corpus: which openly licensed English papers (CC BY) to add beyond the synthetic sample? | 3 CC BY papers from different fields | Regression coverage |
