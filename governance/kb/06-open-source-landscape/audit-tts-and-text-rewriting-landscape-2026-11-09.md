# Audit: open-source landscape — reading aloud and rewriting text for speech

`[AUDIT]` · Snapshot of 9 Nov 2026 · Commercial companion: `audit-commercial-tts-and-text-rewriting-landscape-2026-11-09.md` · Owner: Colin · Advisor: Claude · Extends `audit-similar-open-source-projects-2026-11-09.md` (first survey, 17 projects) with about 70 projects in five categories, including rule-based and AI-based text rewriting for speech (not summarising) · Related: `audit-abogen-vs-sci2audio-2026-11-09.md`, `audit-audiblez-vs-sci2audio-2026-11-09.md`, `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md`, playbook phases 3, 4.0, 7 · Living version with a map diagram: Doc "Open-source landscape: reading aloud and rewriting text for speech" (claude.ai artifact `AyborQc4pgEDu4EvDXLQRt`)

> **Why this file exists.** Colin asked (9 Nov 2026) for an extensive list of similar projects and of any projects using rule-based or AI-based text rewriting for speech, explicitly not summarising. Three parallel research passes checked each project's GitHub, Hugging Face or paper page. Provenance for every row: [external fact, 9 Nov 2026]; relevance column and shortlist: [advisor proposal]. Stars and features change quickly: re-check after about 3 months.

---

## 1. Short answer

**About 70 open-source projects touch this area; none does what sci2audio does: faithful, rule-based preparation of scientific text for listening.** The pieces exist separately:

- **Reader apps** (26 in A) mostly do no text preparation. The exception, a small fork of autiobooks, has a rule list worth comparing with sci2audio's.
- **Rule-based normalisers** (17 in B) handle numbers, dates and money well; none targets citations, units in formulas or statistics. NVIDIA's grammars are the most complete for English and German but heavy to install.
- **Formula readers** (5 in C): MathCAT and Speech Rule Engine read formulas aloud in German and English.
- **AI rewriting that stays faithful** (D) is mostly research. Apple's PolyNorm shows prompted LLMs beat rules on normalisation, including German; its test set is public. Most "paper to audio" tools summarise.
- **PDF clean-up** (11 in E): the strongest neural tools have restrictive model licences; ftfy and Pyphen fit a GPL desktop app.

**Consequence:** sci2audio's niche is real; it can borrow a test set (PolyNorm-Bench), a number library (num2words), a pronunciation-list format (PLS) and a formula reader (MathCAT) instead of building them.

## 2. Map

Every reader app (A) wraps four stages: **E clean-up → B rule-based normalisation → D optional AI rewriting → voice** (pronunciation front end + TTS model), with **C formulas and notation** feeding B/D. sci2audio's own work sits in B and, later and optionally, D. (Diagram in the living Doc.)

## 3. A. Audiobook and read-aloud apps

**Only one small app does serious rule-based preparation (autiobooks fork).** Sorted by amount of text preparation.

| Project | Form | Stars | Licence | Text preparation | DE | Relevance |
|---|---|---|---|---|---|---|
| [autiobooks (tecmage fork)](https://github.com/tecmage/autiobooks) | Desktop (tkinter), CLI, Docker | 4 | MIT | **Extensive rules:** Unicode clean-up, abbreviations and symbols, Roman numerals by context, fractions, URL/e-mail removal, scene breaks, spaCy homographs, user word substitutions, pronunciation overrides | No | Closest peer to sci2audio's rules; compare feature by feature |
| [Abogen](https://github.com/denizsafak/abogen) | Desktop (PyQt6) + web UI | 6.1k | MIT | English normaliser, spaCy, optional LLM | No | Own deep-dive audit |
| [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) | Local server, OpenAI-compatible API, web UI | 5.5k | Apache-2.0 | Number normalisation switchable per request; inline IPA `[word](/ipa/)`; pause/voice tags; SSML; README warns the normaliser can change phrases | No | Copy: per-request toggles, inline pronunciation syntax |
| [pdf-narrator](https://github.com/mateogon/pdf-narrator) | Desktop GUI | 214 | MIT | Structural: skips headers, footers, page numbers; chapters from PDF outline | Not shown | Same stack (PDF + Kokoro); compare header/footer rules |
| [Calliope](https://github.com/hugohammer/TTS-Narrated-Ebook-Creator) ([paper](https://arxiv.org/html/2602.10735)) | CLI library | Not shown | MIT (per paper) | Light: Unicode, punctuation, sentence length 60–200 characters | Unknown | Sentence-length rules; EPUB 3 read-along |
| [epub2tts-edge](https://github.com/aedocw/epub2tts-edge) | CLI, Docker | 216 | GPL-3.0 | Manual: edit an intermediate text file | Not shown | Manual override layer |
| [ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook) | Gradio, Docker | 20.4k | Apache-2.0 | Little; translation, SML tags | Yes (XTTS) | Reach, not text quality |
| [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) | CLI + Gradio | 2.1k | MIT | Regex search and replace | Not shown | User-editable replacement list |
| [Audiblez](https://github.com/santinic/audiblez) | CLI + wxPython | 8.7k | MIT | None | No | Own deep-dive audit |
| [autiobooks (upstream)](https://github.com/plusuncold/autiobooks) | Desktop | 265 | MIT | None described | No | Fork added all rules |
| [kokoro-tts](https://github.com/nazdridoy/kokoro-tts) | CLI | 1.8k | MIT | Chunking only | No | Kokoro via ONNX |
| [epub2tts](https://github.com/aedocw/epub2tts) | CLI, Docker | 958 | Apache-2.0 | Chapter detection | Not shown | Older |
| [audible-epub3-maker](https://github.com/funway/audible-epub3-maker) | CLI + Gradio | 34 | MIT | Segmentation, forced alignment | Not shown | EPUB 3 read-along export |
| [Audiobook Creator](https://github.com/prakharsr/audiobook-creator) | Gradio, Docker | 524 | GPL-3.0 | LLM dialogue attribution | No | Fiction |
| [VoxNovel](https://github.com/DrewThomasson/VoxNovel) | GUI, Docker | 375 | MIT | BookNLP speaker attribution | Partly | Fiction |
| [OpenReader WebUI](https://github.com/richardr1126/OpenReader-WebUI) | Web + desktop | 555 | MIT | Layout-aware PDF parsing | Not shown | Read-along UX |
| [Speech Note](https://github.com/mkiol/dsnote) | Linux desktop | 1.7k | MPL-2.0 | None for documents | Yes | In-app voice download |
| [Kokoro Web](https://github.com/eduardolat/kokoro-web) | Web, Docker | 753 | MIT | Not shown | Not shown | Kokoro in the browser |
| [Read Aloud](https://github.com/ken107/read-aloud) | Browser extension | 1.8k | MIT | Not shown | Not shown | Highlighting UX |
| [Readest](https://github.com/readest/readest) | Reader, all platforms | 25.6k | AGPL-3.0 | Not shown | Not confirmed | Reader UX |
| [Thorium Reader](https://github.com/edrlab/thorium-reader) | Desktop EPUB reader | 2.9k | BSD-3-Clause | Not shown | UI yes | Player for EPUB 3 read-along |
| [Foliate](https://github.com/johnfactotum/foliate) | Linux reader | 8.8k | GPL-3.0 | Not shown | Not confirmed | System-voice route |
| [NVDA](https://github.com/nvaccess/nvda) | Windows screen reader | 2.7k | GPL-2.0 (modified) | Speech dictionaries (not verified on repo page) | Not shown | Accessibility reference |
| [ttsfm](https://github.com/dbccccccc/ttsfm) | Package, server | 735 | MIT | Splitting only | Not shown | Low |
| [pdf2mp3](https://github.com/zphy/pdf2mp3) | Scripts | 0 | Not shown | Folds Unicode math letters (NFKC) | Not shown | One useful trick |
| [arxiv2speech](https://github.com/dfm/arxiv2speech) | CLI (macOS) | Not shown | BSD-2-Clause | html2text only | Not shown | Abandoned (2013) |

**Voice runtimes for German:** [Piper (piper1-gpl)](https://github.com/OHF-Voice/piper1-gpl) (5.1k, GPL-3.0; maintainers wanted); [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (15.5k, Apache-2.0; runs Piper German voices everywhere, incl. as an Android system voice). Also checked: Calibre (25.7k, GPL-3.0), KOReader (29.5k, AGPL-3.0), Librera (4.8k, GPL-3.0) — read-aloud features, no text preparation described. Storyteller not verified.

## 4. B. Rule-based text normalisation for speech

**Mature normalisers exist; none targets scientific notation.**

| Project | Stars | Licence | Runtime | What, how | DE | Relevance |
|---|---|---|---|---|---|---|
| [misaki](https://github.com/hexgrad/misaki) | 500 | Apache-2.0 | Python | Kokoro's front end: dictionaries, spaCy, num2words; espeak-ng fallback | No | **Highest:** sci2audio's rules must hand it text it handles well |
| [NeMo-text-processing](https://github.com/NVIDIA/NeMo-text-processing) | 515 | Apache-2.0 | Python + Pynini/OpenFst | WFST normalisation and inverse; context-aware mode | Yes | Most complete EN/DE rule set; heavy install on Windows (conda) |
| [num2words](https://github.com/savoirfairelinux/num2words) | 970 | Check (COPYING) | Python | Cardinal, ordinal, year, currency | Yes | Building block; misaki uses it |
| [german_transliterate](https://github.com/repodiac/german_transliterate) | 39 | CC-BY-4.0 | Python | German TTS clean-up: numbers, ordinals with case endings, dates, currencies, acronyms, abbreviations | Yes | Readable German rules for the German phase |
| [gruut](https://github.com/rhasspy/gruut) | 332 | MIT | Python | Cleaner + phonemiser; numbers, dates, currency; SSML subset | Yes | Reference; archived Oct 2025 |
| [inflect](https://github.com/jaraco/inflect) | 1.1k | Check | Python | Number words, ordinals, plurals, a/an | No | English helper |
| [DAISY Pipeline 2](https://github.com/daisy/pipeline) ([TTS docs](https://daisy.github.io/pipeline/Get-Help/User-Guide/Text-To-Speech/)) | 26 (umbrella) | Not shown | Java | PLS pronunciation lexicons with regex entries; Aural CSS | Not shown | **Standard format** for a user pronunciation dictionary |
| [WeTextProcessing](https://github.com/wenet-e2e/WeTextProcessing) | 828 | Apache-2.0 | Python + C++ | FST rules, C++ runtime | No | Lighter grammar engine; Chinese-centred |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) | 7.0k | GPL-3.0 | C | Per-language rule/dictionary files | Yes | In Kokoro's fallback path |
| [phonemizer](https://github.com/bootphon/phonemizer) | 1.6k | GPL-3.0 | Python | espeak wrapper, no normalisation | Via espeak | Fallback chain only |
| [Duckling](https://github.com/facebook/duckling) | 4.3k | BSD | Haskell | Parses numbers, money, units, URLs into values | Varies | Design reference |
| [pynini](https://github.com/kylebgorman/pynini) | 176 | Apache-2.0 | C++/Python | Grammar toolkit, no grammars | — | Only with NeMo |
| [MaryTTS](https://github.com/marytts/marytts) | 2.6k | LGPL-3.0 | Java | TTS with German preprocessing | Not shown | Source to read for German rules |
| [Coqui TTS](https://github.com/coqui-ai/TTS) | 45.9k | MPL-2.0 (models vary) | Python | Text cleaners | Not shown | Reference |
| [Flite](https://github.com/festvox/flite) | 1.1k | Check | C | English tokenisation | No | Reference |
| [piper-phonemize](https://github.com/rhasspy/piper-phonemize) | 143 | MIT | C++ | Phonemes for Piper | Not shown | Archived Jul 2025 |
| [Sparrowhawk](https://github.com/google/sparrowhawk) | 216 | Apache-2.0 | C++ | Open Kestrel normaliser | Not shown | Archived Sep 2022 |

## 5. C. Formulas and scientific notation to speech

**Two mature rule engines read formulas in German and English; both need MathML.**

| Project | Stars | Licence | Runtime | What | DE | Relevance |
|---|---|---|---|---|---|---|
| [MathCAT](https://github.com/NSoiffer/MathCAT) | 129 | MIT | Rust + Python interface | MathML to speech, braille, navigation; used by NVDA and JAWS | Yes | **Best fit** for a Python app |
| [Speech Rule Engine](https://github.com/speech-rule-engine/speech-rule-engine) | 105 | Apache-2.0 | Node.js/TypeScript | MathSpeak/ClearSpeak rules; LaTeX for some locales | Yes | Mature; needs Node.js |
| [latex-access](https://github.com/latex-access/latex-access) | 3 | GPL-2.0 (check "or later") | Python | LaTeX to spoken English and braille | No | Works on LaTeX directly; licence check |
| [latex2speech](https://github.com/hutchresearch/latex2speech) | Not shown | MIT | Python, AWS | LaTeX to MP3 via cloud TTS | Not shown | Mappings reusable; cloud |
| [AutoChemplete](https://github.com/human-centered-systems-lab/AutoChemplete) ([KIT](https://h-lab.win.kit.edu/news_2838.php)) | Not checked | Check | Not shown | Molecule recognition from formula images | Unknown | Only if chemistry figures in scope |

**Not found:** a library that reads chemical formulas/SMILES aloud or speaks units with correct grammar — a gap sci2audio's own rules can fill.

## 6. D. AI-based rewriting for listening (not summarising)

**Faithful AI rewriting is mostly research or cloud-dependent; PolyNorm is the strongest German evidence and its test set is public.**

| Item | Type | Stars | Licence | Rewrites what, how | Faithful? | DE | Local? | Relevance |
|---|---|---|---|---|---|---|---|---|
| [PolyNorm (Apple)](https://arxiv.org/html/2511.03080v1) ([bench](https://github.com/apple/ml-speech-polynorm-bench)) | Research + benchmark | ~10 | Paper CC BY-NC-ND; repo licence not named | Few-shot prompted LLM normalisation (GPT-4o); error 4.2–7.9% vs. 9.7–17.5% for Apple's rule baseline | Yes | **Yes** | No | Best evidence LLM normalisation works for German; test set reusable |
| [NeMo-text-processing (LM rescoring)](https://github.com/NVIDIA/NeMo-text-processing) | Hybrid library | 515 | Apache-2.0 | Grammar candidates ranked by a masked LM ("St." Saint/Street) | Yes | Grammar yes; rescoring not shown | Yes | Hybrid: rules propose, model chooses |
| [NeMo Duplex TN (T5)](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/nemo/models/neural_text_normalization_t5) | Model | — | NGC terms | Tagger + T5 verbaliser; grammars for URLs/abbreviations | Yes | No | Yes | Reference design; weights not usable in GPL app |
| [TontaubeV1-Verbalizer](https://huggingface.co/TontaubeAI/TontaubeV1-Verbalizer) | Model (~2B, Qwen3-based) | ~5 | Conflicting | Numbers, dates, currencies, symbols, abbreviations; keeps wording | Yes (stated) | No | Yes (GPU) | Closest small local verbaliser; licence unclear |
| [MathReader](https://github.com/AIDASLab/MathReader) ([paper](https://arxiv.org/abs/2501.07088)) | Research code | ~35 | Not shown | Nougat OCR → T5 LaTeX-to-speech; math WER 0.28 vs. 0.51 Edge | Formulas only | Unknown | Yes | Test on formulas if weights released |
| [audia](https://github.com/yauheniya-ai/audia) | Tool | ~1 | MIT | Regex pre-pass, then mandatory LLM: math to English, tables to sentences; condenses tables/acknowledgements | Partly | Unknown | No (OpenAI/Anthropic) | Closest match to an optional AI step; study prompts |
| [Paper Voice](https://github.com/gojiplus/paper_voice) | Tool | ~1 | MIT | One LLM prompt for spoken math | Mostly | Unknown | No | Prompt reference |
| [Abogen (web UI)](https://github.com/denizsafak/abogen) | Tool | 6.1k | MIT | Optional LLM for contractions/apostrophes; editable prompt; Ollama | Yes | No | Yes | UX pattern |
| [ArxivPapers](https://github.com/imelnyk/ArxivPapers) | Tool | 544 | Not shown | arXiv LaTeX → text, GPT rewrite; long version narrates with section summaries | Mixed | Unknown | No | LaTeX source as cleaner input |
| [Proteno (Amazon)](https://arxiv.org/abs/2104.07777) | Research | Not verified | Not verified | TN as token classification (BiLSTM) | Yes | No | — | Low-data hybrid idea |
| [PDF2Audio](https://github.com/lamm-mit/PDF2Audio) | Tool | 1.4k | Apache-2.0 | GPT templates: podcast, lecture, summary | No | Unknown | No | Out of scope |
| [Podcastfy](https://github.com/souzatharsis/podcastfy), [Open NotebookLM](https://github.com/gabrielchua/open-notebooklm), [NotebookLlama](https://github.com/meta-llama/llama-recipes/tree/main/recipes/quickstart/NotebookLlama) | Tools | 6.8k / — / — | Apache-2.0 / Apache-2.0 / not shown | Dialogue podcasts | **No: summarise** | Unknown | Partly | Contrast; NotebookLlama's 1B PDF clean-up step is a faithful idea |

**Test data:**

| Dataset | Content | DE | Use |
|---|---|---|---|
| [PolyNorm-Bench](https://github.com/apple/ml-speech-polynorm-bench) | 8 languages × 27 categories × 20 examples, expert-checked | **Yes** | Ready-made EN/DE test set for sci2audio's rules |
| [Google TN data](https://github.com/rwsproat/text-normalization-data) | Written/spoken pairs by class | No (EN, RU, PL) | Large English benchmark |
| [MathBridge](https://arxiv.org/abs/2408.07081v3) | ~23M LaTeX ↔ spoken English pairs | No | Formula reading style |
| [Speech2Latex](https://huggingface.co/papers/2508.03542) | 66k spoken equations, human-annotated | No (EN, RU) | How people read math aloud |

## 7. E. Document clean-up before speech

**Neural PDF tools read hard layouts best but most have restrictive/unclear model licences; light rule-based helpers fit better.**

| Project | Stars | Licence | Runtime | What | Relevance |
|---|---|---|---|---|---|
| [Docling](https://github.com/docling-project/docling) | 69.8k | MIT code; model licences per package | Python | Layout, reading order, tables, formulas, OCR, EPUB; offline | Optional backend (D-49) |
| [GROBID](https://github.com/kermitt2/grobid) | 5.2k | Apache-2.0 | Java, Docker | Scholarly PDF → TEI: metadata, references, sections, figures | Best at references; Java service |
| [Marker](https://github.com/datalab-to/marker) | 40.8k | Code Apache-2.0; weights restricted | Python | PDF → Markdown, equations as LaTeX | Not bundleable |
| [MinerU](https://github.com/opendatalab/MinerU) | 83.1k | Check | Python | PDF/Office/EPUB → Markdown/JSON with formulas | Licence unclear |
| [Nougat](https://github.com/facebookresearch/nougat) | 10.1k | MIT code; weights CC-BY-NC | Python | Academic PDF OCR | Ruled out |
| [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm) | 2.3k | AGPL-3.0 | Python | PyMuPDF Markdown | Already replaced by `pdflayout.py` |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | 15.7k | Apache-2.0 | Python | Documents → typed elements | Heavier than needed |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | 10.7k | MIT | Python | Character/line positions, tables | Similar to `pdflayout.py` |
| [ftfy](https://github.com/rspeer/python-ftfy) | 4.1k | Apache (confirm) | Python | Repairs broken Unicode/mojibake | Cheap first step |
| [Pyphen](https://github.com/Kozea/Pyphen) | 230 | GPL/LGPL/MPL | Python | Hyphenation points (LibreOffice dictionaries) | Check line-end hyphens before joining; German compounds |
| [trafilatura](https://github.com/adbar/trafilatura) | 7.0k | Apache-2.0 | Python | Main text from web pages | HTML/EPUB only |

## 8. Shortlist for sci2audio

| # | Item | What to do | Phase |
|---|---|---|---|
| L1 | PolyNorm-Bench | Run the English rules on the English part as regression/score test; German later; check repo licence first | 4.0 |
| L2 | autiobooks fork + Kokoro-FastAPI rule sets | Compare rule by rule with the 20 detectors; copy missing cases as tests (MIT / Apache-2.0) | 4.0 |
| L3 | num2words | Number words for EN and DE, once licence confirmed | 4.0 |
| L4 | DAISY Pipeline PLS lexicons | W3C PLS (with regex entries) as the format of the user pronunciation list | 7 (B5) |
| L5 | ftfy + Pyphen | Test as broken-character fix and hyphenation check | 3 |
| L6 | MathCAT | Spike LaTeX → MathML → DE/EN speech via its Python interface | 7 |
| L7 | NeMo-text-processing | Read EN/DE grammars as rule reference; no dependency | 4.0 |
| L8 | audia + PolyNorm prompts | Reference for a later optional local AI step (Ollama, editable prompt as in Abogen) | 7 |

## Advisor pre-analysis

- The landscape confirms the split found in the English audit: general normalisation is a solved, shared problem (misaki, NeMo, num2words); scientific notation, citations and layout are not. sci2audio should spend its effort there and borrow the rest.
- PolyNorm's result (LLM beats rules) doesn't argue against the rule-first decision (D-51): it needs GPT-4o in the cloud. It does make a later local-LLM option (D-section, Ollama) worth measuring against the same benchmark.
- Licences decide reuse more than quality: Marker, Nougat, NeMo Duplex and MinerU are strong but not bundleable in a GPL app.

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| LQ5 | Licence of PolyNorm-Bench (repo LICENSE not named on the page) | Check before committing test data | L1 |
| LQ6 | Licences of num2words and inflect (COPYING/unnamed) | Check LICENSE files | L3 |
| LQ7 | MathCAT Python interface: wheels for macOS/Windows/Linux? | Spike in phase 7 | L6 |
| LQ8 | Re-run this survey when? | At v1.0 or after 3 months | Revisit trigger |

## Method and limits

Three parallel research passes (reader apps; rule-based normalisation, formulas and clean-up; AI rewriting and datasets), plus the first survey and the Abogen/Audiblez deep dives. GitHub API unavailable: stars as rendered; most pages showed no last-commit date ("not shown" ≠ inactive). Not verified: Storyteller, dehyphen, amazon-research/proteno, epub2tts-kokoro, Orca, Festival, MathJax speech details, WeTextProcessing's and NeMo's German coverage per mode. Not found: chemistry/SMILES speakers, grammatical unit speakers, German-focused open-source reader apps.
