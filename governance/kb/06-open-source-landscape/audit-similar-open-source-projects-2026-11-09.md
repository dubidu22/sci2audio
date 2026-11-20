# Audit: similar open-source projects (landscape)

`[AUDIT]` · Snapshot of 9 Nov 2026 · **Extended the same day by `audit-tts-and-text-rewriting-landscape-2026-11-09.md` (~70 projects)** · Owner: Colin · Advisor: Claude · Related: `audit-abogen-vs-sci2audio-2026-11-09.md` (deep dive on the closest project), `01-audit-and-roadmap/playbook-open-source-desktop-app.md`, `04-legal-and-compliance/doc-voice-and-model-licensing.md`, `decision-log.md` D-45…D-49 · Living version: section "Similar open-source projects" in the Doc "sci2audio: Paid use cases, profitability and marketing" (claude.ai artifact `9BV7TduSvjGYj7jiHL4sHn`)

> **Why this file exists.** After the open-source pivot (D-41) and the GPL-3.0 decision (D-42), Colin asked which similar projects exist on GitHub and what sci2audio can learn from them. This file records the landscape as found on 9 Nov 2026. Star counts and feature claims change quickly: re-check before relying on them after about 3 months.

---

## 1. Finding

**No open-source project combines sci2audio's three traits: German first, preparation of scientific texts for listening, and a local desktop app.** [advisor proposal, based on the survey below]

- The popular audiobook converters run Kokoro locally but treat a PDF as plain text. The two most-starred Kokoro converters, Audiblez and Abogen, don't list German. [external fact]
- The scientific tools are either research code (MathReader) or need a cloud language model (Paper Voice, audia). [external fact]
- The NotebookLM-style tools summarise into conversations; they don't read a text faithfully. Different product. [external fact]
- **sci2audio's niche is real, but its weak spot is packaging.** The popular tools win with a one-line install. [advisor proposal]

## 2. Method

- Web searches (9 Nov 2026) for: PDF/EPUB to audiobook with Kokoro on desktop; scientific paper / arXiv to audio with math; open-source NotebookLM alternatives; offline TTS desktop apps.
- Each candidate's GitHub page fetched for stars, licence, features, languages and packaging. The GitHub API was not available from this session (HTTP 403 for repos not attached), so numbers are as rendered on the repository pages. [external fact]
- Abogen was additionally cloned and read in full (see the deep-dive audit).

## 3. Landscape table

Stars as shown on GitHub on 9 Nov 2026, sorted by category, then stars. All [external fact].

| Project | Category | Stars | Licence | What it does | Relevance for sci2audio |
|---|---|---|---|---|---|
| [ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook) | Audiobook converter | 20.4k | Apache-2.0 | About 30 ebook and document formats; engines incl. XTTSv2, Bark, Piper; 1,158 languages incl. German; Gradio UI, Docker, OCR, voice cloning | Widest reach, but heavy (GPU options, voice cloning) |
| [Audiblez](https://github.com/santinic/audiblez) | Audiobook converter | 8.7k | MIT | EPUB → M4B with Kokoro; pip install; small wxPython GUI; German not listed; needs espeak-ng and ffmpeg | Benchmark for a simple install and one-command use → deep-dive audit `audit-audiblez-vs-sci2audio-2026-11-09.md` |
| [Abogen](https://github.com/denizsafak/abogen) | Audiobook converter | 6.1k | MIT | EPUB, PDF, TXT, MD → audio with synced SRT/ASS subtitles and M4B chapters; PyQt6 desktop + Flask web UI; Kokoro, Supertonic; German not listed | Closest desktop competitor → deep-dive audit |
| [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) | Audiobook converter | 2.1k | MIT | EPUB → one MP3 per chapter; Azure/OpenAI/Edge or local Piper/Kokoro; regex pronunciation fixes; Gradio UI | Pattern for user-editable pronunciation fixes |
| [kokoro-tts](https://github.com/nazdridoy/kokoro-tts) | Audiobook converter | 1.8k | MIT | CLI, TXT/EPUB/PDF → audio; Kokoro via ONNX; German not listed; Python 3.11–3.12 | Shows Kokoro running without PyTorch |
| [epub2tts](https://github.com/aedocw/epub2tts) | Audiobook converter | 958 | Apache-2.0 | EPUB → M4B with Coqui, XTTS, Edge, OpenAI or Kokoro; Docker image marked outdated | Older; author now points to sibling projects |
| [Audiobook Creator](https://github.com/prakharsr/audiobook-creator) | Audiobook converter | 524 | GPL-3.0 | Fiction: LLM assigns dialogue to characters; Kokoro/Orpheus; Gradio, Docker | GPL-3.0 precedent in the same field |
| [Speech Note](https://github.com/mkiol/dsnote) | Read-aloud app | 1.7k | MPL-2.0 | Linux/Sailfish offline speech-to-text, TTS (Piper, Kokoro, espeak-ng, Coqui and more) and translation; in-app model browser from `models.json`; Flatpak | Model for downloading voices inside the app; no PDF/EPUB import |
| [OpenReader WebUI](https://github.com/richardr1126/OpenReader-WebUI) | Read-aloud app | 555 | MIT | EPUB, PDF, DOCX, TXT, MD read-along with word highlighting, layout-aware PDF parsing, M4B/MP3 export; local Kokoro or cloud; Docker + desktop apps | Closest to sci2audio's listening experience |
| [Docling](https://github.com/docling-project/docling) | Scientific PDF | 69.8k | MIT (code; model licences per package) | Layout, reading order, tables, formulas, code; runs locally; LF AI & Data Foundation (started by IBM Research Zurich) | Candidate optional extraction backend for hard PDFs |
| [Marker](https://github.com/datalab-to/marker) | Scientific PDF | 40.8k | Apache-2.0 code; model weights under a modified AI Pubs Open Rail-M licence | PDF → Markdown with equations as LaTeX; weights free only for research, personal use and startups under $5M | Strong, but the weights licence is not open source |
| [GROBID](https://github.com/kermitt2/grobid) | Scientific PDF | 5.2k | Apache-2.0 | Header metadata, references, citation contexts, sections, figure captions from papers; Java/Docker; no Windows | Reference standard for structure; too heavy to bundle |
| [Speech Rule Engine](https://github.com/Speech-Rule-Engine/speech-rule-engine) | Math to speech | 103 | Apache-2.0 | MathML (some LaTeX) → spoken text, rule-based; German locale ("ist gleich"); Node.js, CLI, browser bundle | German math reading without an LLM |
| [MathReader](https://github.com/AIDASLab/MathReader) | Math to speech | 35 | not stated | Research code (ICASSP 2025): Nougat OCR, LaTeX → text, NeMo TTS | Confirms the problem; not reusable as is |
| [Paper Voice](https://github.com/gojiplus/paper_voice) | Math to speech | 1 | MIT | Academic PDFs → audio; math explained by an OpenAI model; local fallback pyttsx3 | Same idea, cloud-dependent |
| [Open Notebook](https://github.com/lfnovo/open-notebook) | NotebookLM-style | 40.6k | MIT | Self-hosted NotebookLM: notebooks, chat, podcasts with 1–4 speakers; Docker; local LLMs via Ollama, TTS providers cloud | Summarises instead of reading verbatim |
| [Podcastfy](https://github.com/souzatharsis/podcastfy) | NotebookLM-style | 6.8k | Apache-2.0 | Content → conversational podcast; 100+ LLMs; TTS OpenAI/Google/ElevenLabs/Edge | Different product |

Also seen but not tabled (too small or not relevant): Speechfony (Tauri + Rust Kokoro PDF reader, 0 stars), Kokoro-Desktop (CLI fork), AI Audiobook Studio (.NET/WPF, 0 stars), audia (PyPI package, LLM rewrite of papers, MIT), Local-NotebookLM, open-notebooklm, Meta's NotebookLlama recipe, ArxivPapers (LaTeX → audio/video with Google TTS and OpenAI).

## 4. German voices outside sci2audio

- **Thorsten-Voice/Kokoro** on Hugging Face: German fine-tune of Kokoro-82M on the Thorsten-Voice dataset (CC0), Apache-2.0; needs the German forks of `misaki` and `kokoro` plus system espeak-ng. Thorsten-Voice also publishes Docker images for a Kokoro TTS server (standard German and Hessian dialect). [external fact]
- Community German Kokoro voices (e.g. from the `kikiri-tts` recipe, Apache-2.0) and a German multi-speaker base model exist in GGUF form. Not evaluated; candidates for D-43 if Thorsten alone is too narrow. [external fact]
- sci2audio already uses the same forks (`pyproject.toml` extra `kokoro-de`). None of the mainstream Kokoro audiobook tools ships German. [repo fact] [external fact]

## 5. Where sci2audio stands apart

| Trait | sci2audio | Best alternative | Gap |
|---|---|---|---|
| German first | Thorsten Kokoro DE + German detectors | ebook2audiobook (German via XTTS etc., heavy) | Large for lightweight local tools |
| Scientific text preparation | 20 rule-based detectors, layout reader | Docling/Marker (extraction only, no listening preparation); Paper Voice (cloud LLM) | Large |
| Read-along on the original text | Sentence alignment script ↔ original | OpenReader (word highlighting of the read text) | Medium |
| Packaging | Not packaged | Audiblez/Abogen one-command install | sci2audio is behind |
| Engineering process | CI off, no releases | Abogen: 3-OS CI, 27 releases | sci2audio is behind |

## 6. What to borrow (ordered by value for the plan)

| # | Borrow | From | Playbook phase | Entry |
|---|---|---|---|---|
| B1 | One-command install (`uv tool install sci2audio`), installers later | Audiblez, Abogen | 5 | D-47 |
| B2 | Voice download inside the app from a model list, with licence shown; offline pre-download | Speech Note, Abogen | 4.4 | D-43, D-47 |
| B3 | Kokoro through ONNX to avoid PyTorch and shrink the download | kokoro-tts | 4.1 | D-48 |
| B4 | Subtitle export (SRT/VTT) from existing sync data | Abogen | 7 | — |
| B5 | User-editable pronunciation list (expose `wortlisten.py` / `stolperwoerter.py`) | epub_to_audiobook, Abogen | 7 | — |
| B6 | Optional backends, never hard dependencies: Docling (MIT) for hard PDFs; Speech Rule Engine (Apache-2.0, German) for formulas. Both GPL-3.0-compatible. Marker's weights licence and GROBID's Java runtime make them a poor fit to bundle | Docling, SRE | 7 | D-49 |

**Licence compatibility note:** MIT, Apache-2.0 and MPL-2.0 code can be combined into a GPL-3.0 app (D-42). Marker's model weights cannot be redistributed freely. [external fact] Not legal advice; standard open-source practice.

**Learning option:** contributing German support or a scientific-text mode to Abogen or Audiblez teaches open-source collaboration and reaches more users, at the cost of product control (O-15). [advisor proposal]

## Advisor pre-analysis

- The landscape is crowded for "EPUB to audiobook" and empty for "scientific German PDF to faithful audiobook". The README of the public repo should say this in one sentence, and the demo should use a two-column scientific PDF — exactly where the converters fail.
- Docling is the one external component worth a spike: if it reads hard PDFs better than `pdflayout.py` on the own test set, it could be an optional backend. Keep `pdflayout.py` as the default (no model, fast, already tuned for German papers).
- Speech Rule Engine would add a Node.js runtime. Only worth it if formulas are common in Colin's own texts; otherwise keep formula handling as it is.

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| LQ1 | Spike Docling against `pdflayout.py` on 3 own PDFs? | After v1.0 | D-49 |
| LQ2 | Add Speech Rule Engine for German formulas? | Only if formulas matter in own texts | D-49 |
| LQ3 | Evaluate further German Kokoro voices (kikiri-tts, HUI base) for D-43? | Yes, during phase 4.1 | D-43 |
| LQ4 | Re-run this survey when? | At v1.0 release, or after 3 months | Revisit trigger |
