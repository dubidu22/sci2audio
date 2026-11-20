# Feature list for the open-source desktop app

`[DOC]` · Snapshot of 9 Nov 2026 · Owner: Colin · Advisor: Claude · Built from `feature-matrix-2026-11-09.md`, the open-source and commercial landscape audits, the Abogen and Audiblez comparisons, `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md` and `01-audit-and-roadmap/playbook-open-source-desktop-app.md` · **The details per feature live in the Doc "Feature matrix: sci2audio vs. all researched products" (claude.ai artifact `S51tv9ry75nsJDtKoNUyjJ`), tab "Feature list" and its 11 sub-tabs (IN, TP, FX, UC, VA, OU, WI, AQ, PE, AI, WD).** This file keeps the overview table; edit the details in the Doc.

> **Why this file exists.** Colin asked (9 Nov 2026) for a comprehensive list of possible features, each with description, priority, effort, acceptance criteria, technical details and the competitors that have it. Fields added on Claude's suggestion and accepted by Colin: ID, status today, release target, user problem, language, dependencies/licence, test approach, risks, "you practise", plus the areas workflow, output, transparency, integrations, app quality, project/engineering and won't-do.

**94 features in 11 areas: 41 Must, 28 Should, 20 Could, 5 Won't** (updated 10 Nov: PE-10 added, WI-08 moved to Should/v1.1, VA-02 changed after D-48). About half already exist in sci2audio's code at least partly.

## Legend

**Priority (MoSCoW, for v1.0):** Must = v1.0 doesn't ship without it · Should = v1.0 if time allows, else v1.1 · Could = later, nice to have · Won't = explicitly out of scope.

**Effort (at \~20 h/week):** S ≤ 4 h · M ≤ 1 day (8 h) · L ≤ 3 days · XL > 3 days.

**Status today:** ✓ exists · ◐ partly · ✗ new. **Release:** v1.0 = playbook phases 1–6 · v1.1 · Later = phase 7. **Lang:** EN, DE or both.

## Detail format in the Doc

Each feature in its area sub-tab has: priority · effort · release · language · status; description and user problem; acceptance criteria; technical approach; tests; risks; what Colin practises (AI-assisted development); competitors.

## Links to decisions

- Formulas skipped with a spoken notice (FX-01) = **D-55**, decided. MathCAT later (FX-05).
- English first (VA-01, PE-03, TP-09, TP-14) = **D-50**, decided; rule-based first, AI only later and optional (AI-01…03) = **D-51**, decided.
- Reuse Abogen's voice plugin (VA-01, PE-07) = D-52; engine spike (VA-02) = D-48/D-52; homographs and numbers via misaki (TP-09, TP-14) = D-54; no second rule system in spaCy = D-53; PyPI first (WI-01) = D-47; layers and `web.py` split (PE-05) = D-46; one browser UI (AQ-01, AQ-02) = D-45; optional Docling (IN-07) = D-49. All proposed, not yet approved.
- Won't-do list (WD-01…05) follows ADR-007 and D-41.

## Overview

| ID | Feature | Status | Priority | Effort | Release | Lang | Competitors with it |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **IN** | **Input and extraction** |  |  |  |  |  |  |
| IN-01 | PDF layout reading (columns, headings, footnotes, tables, running heads) | ✓ | Must | S | v1.0 | both | Paper2Audio, pdf-narrator (partly), OpenReader (partly), Abogen (partly) |
| IN-02 | EPUB import with chapters from navigation | ✓ | Must | S | v1.0 | both | Abogen, Audiblez, autiobooks, ebook2audiobook, epub\_to\_audiobook, Thorium, EasyReader |
| IN-03 | Markdown, text and pasted text | ✓ | Must | S | v1.0 | both | Abogen, kokoro-tts, Speechify, TTSReader |
| IN-04 | Unicode clean-up and ligatures | ◐ | Must | S | v1.0 | both | autiobooks fork, Calliope, pdf2mp3 |
| IN-05 | OCR for scanned PDFs | ◐ | Should | M | v1.0 | both | ElevenReader, Voice Dream, ReadSpeaker, NaturalReader, Paper2Audio, ebook2audiobook |
| IN-06 | DOCX and HTML import | ✗ | Could | M | v1.1 | both | ebook2audiobook, ElevenReader, Speechify, TTSReader, ReadSpeaker |
| IN-07 | Optional Docling backend for hard PDFs | ✗ | Could | L | Later | both | (library: Docling) |
| IN-08 | LaTeX source import (arXiv) | ✗ | Could | L | Later | EN | ArxivPapers, Paper Voice, latex-access |
| **TP** | **Text preparation (rules)** |  |  |  |  |  |  |
| TP-01 | Page furniture removed by default | ◐ | Must | S | v1.0 | both | Audeus, Speechify, ElevenReader, Voice Dream, Paper2Audio, pdf-narrator |
| TP-02 | Automatic hyphenation joining | ◐ | Must | S | v1.0 | both | none found in apps |
| TP-03 | Citation removal (numeric and author-year) | ✓ | Must | S | v1.0 | both | Audeus, Speechify, Listening, Paper2Audio, audia |
| TP-04 | Grammar-aware citation handling | ✗ | Must | M | v1.0 | both | Paper2Audio |
| TP-05 | Footnote marks and footnote text | ✓ | Must | S | v1.0 | both | Audeus, Speechify, Listening, Paper2Audio |
| TP-06 | Reference list and back matter removal | ✓ | Must | S | v1.0 | both | Listening, Paper2Audio, ArxivPapers |
| TP-07 | URL, DOI and e-mail removal with sentence repair | ◐ | Must | S | v1.0 | both | Audeus, Speechify, autiobooks fork |
| TP-08 | Abbreviation expansion | ◐ | Must | S | v1.0 | both | autiobooks fork, Abogen (partly) |
| TP-09 | Numbers and dates, handed off to misaki | ◐ | Must | M | v1.0 | EN | Abogen, autiobooks fork, Kokoro-FastAPI, misaki |
| TP-10 | Symbols and units incl. "per" and plurals | ◐ | Must | M | v1.0 | both | autiobooks fork, Google TTS, Polly |
| TP-11 | Statistics (p, n, CI, ±, <, >) | ◐ | Must | S | v1.0 | both | none found |
| TP-12 | Figure and table references and captions | ◐ | Should | S | v1.0 | both | Audeus, audia |
| TP-13 | Roman numerals by context | ✓ | Should | S | v1.0 | both | Abogen, autiobooks fork |
| TP-14 | Homographs via misaki, no user questions | ◐ | Should | S | v1.0 | EN | Abogen, autiobooks fork, Audiblez (via misaki) |
| TP-15 | Words in capitals written normally | ✓ | Should | S | v1.0 | both | none found |
| TP-16 | Section detection and types | ◐ | Should | M | v1.0 | both | Listening, Audemic |
| TP-17 | Acronym long form at first mention | ✗ | Could | M | Later | EN | none (scispaCy algorithm) |
| TP-18 | German specifics: gender forms, foreign words, names | ✓ | Should | M | Later | DE | none found |
| **FX** | **Formulas, tables, figures** |  |  |  |  |  |  |
| FX-01 | Formulas skipped with a spoken notice (D-55) | ◐ | Must | S | v1.0 | both | Audeus (skips silently) |
| FX-02 | Tables replaced by a notice with caption | ✓ | Must | S | v1.0 | both | Audeus (skips silently) |
| FX-03 | Figures: caption read, image announced | ◐ | Should | S | v1.0 | both | Paper2Audio (AI), audia |
| FX-04 | Unicode math letters folded | ◐ | Should | S | v1.0 | both | pdf2mp3 |
| FX-05 | Formulas spoken via MathCAT | ✗ | Should | XL | Later | both | JAWS, EasyReader, Kurzweil, NVDA, VoiceOver, Mote, Azure |
| FX-06 | Tables described by rules | ✗ | Could | M | Later | both | Paper2Audio (AI), audia (AI), NaturalReader (AI) |
| FX-07 | Chemical formulas and units in formulas | ✗ | Could | M | Later | both | EasyReader (chemistry setting) |
| **UC** | **User control and transparency** |  |  |  |  |  |  |
| UC-01 | Pre-analysis report with decisions | ✓ | Must | S | v1.0 | both | none found |
| UC-02 | Per-category toggles | ◐ | Must | M | v1.0 | both | Audeus, Speechify, Kokoro-FastAPI, autiobooks fork (partly) |
| UC-03 | Chapter selection and order | ◐ | Must | S | v1.0 | both | Audiblez, Abogen, Audemic |
| UC-04 | Editable final script before audio | ◐ | Should | M | v1.0 | both | Abogen, epub2tts-edge, Audiblez, GenFM, Wondercraft |
| UC-05 | "What changed" view | ◐ | Should | M | v1.0 | both | none found |
| UC-06 | Normalisation on/off/auto per document | ✗ | Should | S | v1.0 | both | ElevenLabs, Cartesia, Kokoro-FastAPI |
| UC-07 | Section picker | ✗ | Should | M | v1.1 | both | Listening, Audemic |
| UC-08 | User pronunciation list | ◐ | Should | M | v1.1 | both | Voice Dream, Balabolka, TTSReader, epub\_to\_audiobook, Abogen, autiobooks fork, WellSaid |
| UC-09 | Regex rules for power users | ✗ | Could | S | Later | both | Balabolka, epub\_to\_audiobook, Nuance |
| UC-10 | PLS import and export | ✗ | Could | M | Later | both | DAISY Pipeline, Azure, Polly, ElevenLabs, ReadSpeaker |
| **VA** | **Voices and audio** |  |  |  |  |  |  |
| VA-01 | Kokoro English via Abogen's plugin (misaki) | ✗ | Must | M | v1.0 | EN | Abogen, Audiblez, autiobooks, Kokoro-FastAPI |
| VA-02 | Verify PyTorch on three systems: speed without GPU, install size, Apple GPU setting (D-48: PyTorch decided) | ✗ | Must | M | v1.0 | EN | Abogen (Apple GPU) |
| VA-03 | Voice download on first use, licence shown | ◐ | Must | M | v1.0 | both | Speech Note, Abogen |
| VA-04 | Fully offline after setup | ◐ | Must | S | v1.0 | both | Voice Dream, Abogen, Audiblez |
| VA-05 | Voice preview and speed | ◐ | Must | S | v1.0 | both | nearly all apps |
| VA-06 | Pauses for paragraphs, headings, lists | ◐ | Should | S | v1.0 | both | Kokoro-FastAPI, epub2tts-edge, DAISY Pipeline |
| VA-07 | German voice (Thorsten Kokoro) | ◐ | Should | M | Later | DE | VoxNovel, ebook2audiobook, Voice Dream |
| VA-08 | Piper fallback with public-domain voices | ✗ | Could | M | Later | both | Piper, sherpa-onnx, epub\_to\_audiobook |
| VA-09 | Voice blending and profiles | ✗ | Could | M | Later | EN | Abogen |
| **OU** | **Output and listening** |  |  |  |  |  |  |
| OU-01 | MP3 per chapter and M4B with chapters and cover | ◐ | Must | S | v1.0 | both | Abogen, Audiblez, epub2tts, ebook2audiobook |
| OU-02 | Read-along on the original text | ✓ | Must | S | v1.0 | both | Speechify, Audemic, OpenReader, Kurzweil, Read Aloud |
| OU-03 | Metadata and file names | ◐ | Should | S | v1.0 | both | Audiblez, Abogen |
| OU-04 | SRT/VTT subtitle export | ✗ | Should | S | v1.1 | both | Abogen, Calliope, audible-epub3-maker |
| OU-05 | Opus for small files | ✓ | Could | S | v1.0 | both | — |
| OU-06 | EPUB 3 with media overlays | ✗ | Could | L | Later | both | Abogen, Calliope, audible-epub3-maker |
| OU-07 | Audiobookshelf push or private podcast feed | ✗ | Could | M | Later | both | Abogen |
| **WI** | **Workflow and integrations** |  |  |  |  |  |  |
| WI-01 | One-command install from PyPI | ✗ | Must | M | v1.0 | both | Audiblez, Abogen |
| WI-02 | Resume: skip finished chapters | ◐ | Must | S | v1.0 | both | Audiblez, Abogen |
| WI-03 | Command line and scripting | ✓ | Must | S | v1.0 | both | Audiblez, Abogen, kokoro-tts, epub\_to\_audiobook |
| WI-04 | Measured time estimate | ✗ | Should | S | v1.0 | both | (Audiblez uses a fixed rate) |
| WI-05 | Paragraph preview before full render | ◐ | Should | S | v1.0 | both | Speechify, Abogen |
| WI-06 | Batch and folder conversion with a queue | ◐ | Should | M | v1.1 | both | pdf-narrator, Abogen |
| WI-07 | Zotero import | ✗ | Could | M | Later | both | Listening |
| WI-08 | Installers (.dmg, .exe) with an app window (pywebview) (D-47) | ✗ | Should | L | v1.1 | both | Abogen (Windows script) |
| WI-09 | Calibre plugin and "Open with" | ✗ | Could | M | Later | both | — |
| WI-10 | Android app (F-Droid) | ✗ | Could | XL | Later | both | Readest, Librera, KOReader, sherpa-onnx |
| **AQ** | **App quality, accessibility, privacy** |  |  |  |  |  |  |
| AQ-01 | Accessible interface (screen reader, keyboard, contrast) | ◐ | Must | M | v1.0 | both | Thorium, EasyReader |
| AQ-02 | Interface in English and German | ◐ | Must | M | v1.0 | both | Thorium, ReadSpeaker |
| AQ-03 | No telemetry, no upload; privacy statement | ◐ | Must | S | v1.0 | both | Voice Dream, Abogen, Audiblez (local apps) |
| AQ-04 | AI-generated audio label in metadata | ✓ | Must | S | v1.0 | both | OpenAI (disclosure rule) |
| AQ-05 | Clear errors and diagnostics bundle | ◐ | Should | S | v1.0 | both | — |
| AQ-06 | Performance budget (size, speed, memory) | ✗ | Should | M | v1.0 | both | — |
| AQ-07 | Opt-in update check | ✗ | Could | S | v1.1 | both | — |
| **PE** | **Project and engineering** |  |  |  |  |  |  |
| PE-01 | Public repository, GPL-3.0, third-party licences | ✗ | Must | M | v1.0 | — | Abogen, Audiblez (MIT) |
| PE-02 | CI on 3 operating systems with smoke test | ✗ | Must | M | v1.0 | — | Abogen, Audiblez |
| PE-03 | English regression corpus | ✗ | Must | M | v1.0 | EN | — |
| PE-04 | Written contracts for agents | ◐ | Must | S | v1.0 | — | Abogen (AGENTS.md) |
| PE-05 | Layered architecture, `web.py` split | ✗ | Must | L | v1.0 | — | Abogen |
| PE-06 | Releases with changelog and contributor docs | ✗ | Must | S | v1.0 | — | Abogen |
| PE-07 | Voice plugin contract | ✗ | Should | M | v1.0 | — | Abogen |
| PE-08 | Dependency and licence check in CI | ✗ | Should | S | v1.0 | — | (Audiblez lists deptry, unused) |
| PE-09 | Rule files as data, per language | ◐ | Should | L | v1.1 | both | Nuance rulesets, DAISY Pipeline |
| PE-10 | Text-step plugin interface: rules propose marked edits; built-in detectors use it; user plugins and rule files (D-57) | ✗ | Must | L | v1.0 (public in v1.1) | both | Abogen (voice plugins only), Balabolka and epub_to_audiobook (rule files) |
| **AI** | **Optional AI (later)** |  |  |  |  |  |  |
| AI-01 | Optional local language-model rewrite (faithful, editable prompt) | ✗ | Could | L | Later | both | Abogen, audia, Paper Voice, ElevenLabs guide |
| AI-02 | Local AI descriptions of tables and figures | ✗ | Could | L | Later | both | Paper2Audio, audia, NaturalReader |
| AI-03 | Benchmark: rules vs. local model on PolyNorm-Bench | ✗ | Could | M | Later | both | (PolyNorm study) |
| **WD** | **Won't do** |  |  |  |  |  |  |
| WD-01 | Cloud processing or accounts | — | Won't | — | — | — | Paper2Audio, Speechify, Listening, ElevenReader |
| WD-02 | Summaries or podcasts | — | Won't | — | — | — | NotebookLM, GenFM, Podcastfy, PDF2Audio, NaturalReader |
| WD-03 | iOS app | — | Won't | — | — | — | Voice Dream, Speechify, Paper2Audio |
| WD-04 | Voice cloning | — | Won't | — | — | — | ebook2audiobook, NaturalReader |
| WD-05 | Translation | — | Won't | — | — | — | ebook2audiobook, ReadSpeaker, Audible |

## New ideas (NX), added 9 Nov 2026

Ten ideas that are not among the 93 features and were not found in any of the ~145 researched products. "New" means not found in our research, not proven to exist nowhere. Unprioritised, after v1.0. All offline and rule-based, and none rewrites the author's words. Details are in the Doc, sub-tab "NX: New ideas".

| ID | Idea | Effort | Closest thing that exists |
| --- | --- | --- | --- |
| NX-01 | Spoken roadmap of the paper's structure and timing, plus sound signposts at section starts and skipped items | M | Audiobook chapter lists; screen-reader earcons |
| NX-02 | Citations on demand: removed from the audio, played back on request for the last sentence | M | Citation removal (TP-03) |
| NX-03 | The paper's own glossary: the authors' definitions, word for word, before the sections that use them | M | Acronym long form (TP-17) |
| NX-04 | Listen only to what changed between two versions (preprint v1 → v2) | L | Text diff tools; arXiv version history |
| NX-05 | The voice signals uncertain passages (low OCR confidence, rule conflicts) and keeps a check list | M | OCR confidence values, never spoken |
| NX-06 | Pace that follows text density (numbers, units, terms) | M | Fixed speed per document |
| NX-07 | Track of the author's claim sentences, word for word (an extract, not a summary) | M | AI summaries (WD-02), the opposite approach |
| NX-08 | Voice commands by structure, offline ("skip methods", "repeat that number") | L | Play/pause voice control in audiobook apps |
| NX-09 | Cite-a-moment: audio clip plus a note with the original sentence, page and DOI | S | Snipd (podcast snips, AI and cloud) |
| NX-10 | Hearing table and figure trends as a short tone sequence | L | Chart sonification in accessibility tools |

Suggested first picks: NX-09, NX-02, NX-05; NX-04 is the boldest.
