# Audit: Abogen vs. sci2audio (in-depth comparison)

`[AUDIT]` · Snapshot of 9 Nov 2026 · Owner: Colin · Advisor: Claude · Related: `audit-similar-open-source-projects-2026-11-09.md`, `01-audit-and-roadmap/adr-007-pivot-open-source-local-app.md`, `01-audit-and-roadmap/playbook-open-source-desktop-app.md`, `decision-log.md` D-45…D-49, O-15 · Living version with diagram: Doc "Abogen vs. sci2audio: in-depth comparison" (claude.ai artifact `6zkXUjBx6Gg1xhHuV4Pt8r`)

> **Why this file exists.** After the open-source pivot (D-41), Colin asked to study the closest open-source competitor in depth. Abogen (`denizsafak/abogen`, MIT, ~6,100 GitHub stars) is the most similar desktop app: local Kokoro voices, EPUB/PDF/text in, audiobook with subtitles out. This audit compares it with sci2audio stage by stage and derives what the open-source plan should adopt, avoid or contribute upstream. It is a dated snapshot: re-audit into a new file rather than editing the numbers.

---

## 1. Basis of the comparison

| Item | Abogen | sci2audio | Provenance |
|---|---|---|---|
| Repository | `github.com/denizsafak/abogen` (public) | `dubidu22/audiobook-generator` (private) | — |
| State audited | Commit `1807822`, 1 Nov 2026, cloned into the session | `main` at `35db2c1`, 8 Nov 2026 | [external fact] / [repo fact] |
| Files read | `pyproject.toml`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `docs/tts-plugin-architecture.md`, `docs/getting-started.md`, `abogen/book_parser.py`, `abogen/text_extractor.py`, `abogen/kokoro_text_normalization.py`, `abogen/llm_client.py`, `abogen/hf_tracker.py`, `plugins/kokoro/engine.py`, `.github/workflows/*`, git history | `pyproject.toml`, `sci2audio/pdflayout.py`, `mitlesen.py`, `epub.py`, `synchron.py`, `cli.py`, `analysis/`, `.github/workflows/sci2audio.yml` | — |
| Counting method | `wc -l` over `*.py`; `def test_` matches in `tests/`; `git log` | Same (pytest collects 1,279 tests, see S-03) | [external fact] / [repo fact] |

## 2. Short answer

- **Abogen is a mature, general-purpose audiobook maker; sci2audio is a specialised tool for reading scientific German texts aloud.** They overlap only in the last step (local voice → MP3/M4B). [advisor proposal, based on the code reading below]
- **sci2audio is clearly ahead in the text pipeline:** PDF layout reading (columns, footnotes, headings, tables, running heads, hyphenation) and the rule-based pre-analysis (20 detectors, 25 categories). Abogen treats a PDF as raw page text with page numbers stripped by regex. [repo fact] [external fact]
- **Abogen is clearly ahead around the core:** one-command install, desktop app, 3-OS CI on every pull request, 27 releases on PyPI, a written TTS plugin contract, several contributors. These are exactly the parts the open-source playbook still has to build. [external fact]
- **Conclusion:** keep sci2audio's text pipeline; adopt Abogen's packaging and engineering habits; don't merge into Abogen (it has no German voice, and sci2audio's value is in the text preparation Abogen lacks). Optionally contribute a German Kokoro plugin upstream as a learning exercise (O-15). [advisor proposal]

## 3. At a glance

| Aspect | Abogen | sci2audio |
|---|---|---|
| Purpose | Any book or text → audiobook with subtitles | Scientific texts → audiobook that is pleasant to listen to |
| Input | EPUB, PDF, TXT, MD, SRT/ASS/VTT subtitle files, timestamped text | PDF, EPUB, MD, TXT, pasted text |
| PDF reading | Page text via PyMuPDF; page numbers and bracketed numbers stripped by four regexes; chapters from the PDF outline or one per page | Own layout reader `pdflayout.py` from letter positions: columns, headings, paragraphs, footnotes, tables, running heads, hyphenation, picture text; no model |
| Text preparation | English-focused normaliser (`kokoro_text_normalization.py`, 2,427 lines): dates, times, currency, Roman numerals, contractions; spaCy sentences and proper nouns; optional rewrite by any OpenAI-compatible LLM (Ollama works) | 20 rule-based detectors in 25 categories: abbreviations, citations, figures, footnotes, numbers, foreign words, gender forms, homographs, headings, hyphenation and more |
| Languages | 9: US/UK English, Spanish, French, Hindi, Italian, Japanese, Brazilian Portuguese, Mandarin | German and English |
| Voices | Kokoro (PyTorch package `kokoro>=0.9.4`), Supertonic; plugin contract for more engines | Kokoro EN via `kokoro-onnx`; Kokoro DE (Thorsten) via PyTorch + German forks of `kokoro`/`misaki`; Piper; cloud voices to be removed (ADR-007) |
| Output | WAV, MP3, M4B with chapters and cover; EPUB 3 with media overlays; push to Audiobookshelf | MP3, M4B, Opus |
| Read-along | SRT/ASS subtitles of the spoken text; word-level only for English Kokoro | Highlights the sentence of the **original** text, aligned to the spoken script (`mitlesen.py`) |
| Interface | PyQt6 desktop app + Flask web UI (Docker) | FastAPI web app in the browser + Typer CLI |
| Install | `uv tool install --python 3.12 abogen` (+ CUDA/ROCm variants), Windows batch installer with embedded Python, Docker; espeak-ng installed separately on Windows | `pip install` from source; no public package yet |
| Size | ~43,200 lines of Python | ~58,700 lines incl. subpackages (51,131 top-level), incl. hosted-service parts to be removed |
| Tests | 118 test files, ~1,600 test functions | 124 test files, ~1,220 test functions (1,279 collected) |
| CI | Every push and PR, Linux/macOS/Windows, Qt tested headless | Disabled for budget; manual start only, Linux; `main` has 1 failing test (O-09) |
| Releases | 27 tags, latest v1.3.1, on PyPI | None |
| People | 3 main contributors (366 / 249 / 199 commits) plus occasional ones; 14 commits by coding agents | Colin alone, Claude Code builds almost everything |
| Licence | MIT (but depends on PyMuPDF AGPL-3.0 and PyQt6 GPL-3.0) | GPL-3.0 (decided, D-42) |

Provenance: Abogen column [external fact, clone of 1 Nov 2026]; sci2audio column [repo fact, 8–9 Nov 2026].

## 4. Architecture

Both apps run the same six stages: **input → extract → prepare → split → voice → output**. The living Doc has a side-by-side drawing.

| Stage | Abogen | sci2audio | Who does more |
|---|---|---|---|
| Input | EPUB nav/NCX for chapters; PDF outline or one chapter per page | EPUB nav/NCX (`epub.py`); PDF to the layout reader | Equal |
| Extract | `book_parser.py`: `page.get_text()` + regex cleanup | `pdflayout.py`: statistics and geometry on letters | **sci2audio** |
| Prepare | English normaliser + optional LLM | 20 detectors, report with user decisions | **sci2audio** |
| Split | Patterns fixed in `AGENTS.md` per language and subtitle mode; spaCy pre-split for non-English | `satzteilung.py`, `chunker.py`, `sections.py` | Abogen documents it better; sci2audio handles German better |
| Voice | Plugins behind a contract (`tts_plugin/`, `plugins/kokoro`, `plugins/supertonic`) | Providers inside one module `tts.py` | **Abogen** (structure) |
| Output | WAV/MP3/M4B, SRT/ASS, EPUB 3 media overlays, Audiobookshelf | MP3/M4B/Opus + read-along JSON aligned to the original | Abogen in formats; **sci2audio** in read-along quality |

**Code structure.** Abogen's core is layered: `domain/` (pure logic: chunking, voice resolution, subtitles, metadata), `application/` (use cases, `conversion_ports.py`, planner, executor), `infrastructure/` (exporters, subtitle writer), with `pyqt/` and `webui/` on top. The layering arrived with v1.3.0 in one contribution of more than 55,000 lines. sci2audio is a flat package of about 100 modules with `web.py` at 7,245 lines; Abogen's largest file is `pyqt/gui.py` at 4,375 lines. [external fact] [repo fact]

## 5. Text pipeline

**PDF.** Abogen's `PdfParser.process_content` loops over pages, calls `clean_text(page.get_text())` and removes bracketed numbers, standalone page numbers, page numbers at the end and dashed page numbers with four compiled regexes. Chapters come from `get_toc()`; without an outline, every page becomes a chapter titled "Page N – first line". There is no column detection, no footnote handling, no running-head removal beyond page numbers, no table handling and no joining of words broken at the line end. A two-column paper therefore comes out in PyMuPDF's text order. [external fact]

sci2audio's `pdflayout.py` replaced pymupdf4llm (AGPL) with its own reader: letters to lines on a baseline (superscripts kept), gutters found as vertical strips no line crosses, bands for titles spanning both columns, paragraphs from gaps/indents/size changes, heading levels from font size, footnote marks as superscripts, tables as Markdown tables, running heads and feet removed when they repeat in the same place on many pages, table-of-contents dot leaders dropped. [repo fact]

**EPUB.** Both read the EPUB 3 nav document or the EPUB 2 NCX. Abogen's EPUB handling is more battle-tested: dedicated tests for content slicing, missing files, heuristic navigation, NCX and standard nav. [external fact] [repo fact]

**Preparing the words.** Abogen's normaliser is built for English: ISO and US dates, times, address abbreviations, internet slang, numbers and ranges, fractions, Roman numerals in titles, all-caps quotes, contractions ("he'd"), currency, URLs, dotted acronyms, phoneme hints. spaCy finds sentence boundaries and proper nouns (`entity_analysis.py`); a pronunciation store and heteronym overrides fix individual words; an optional LLM pass (`llm_client.py`, any OpenAI-compatible URL, Ollama recognised) rewrites sentences via regex replacements returned by the model. [external fact]

sci2audio's detectors target what makes scientific German hard to hear: abbreviations ("z. B.", "vgl."), citations ("(Müller 2019, S. 12)"), figure and table references, footnote marks, gender forms, foreign words, homographs, hyphenation, links, markup, names, numbers, passages, publisher lines and garbled characters (`zeichensalat.py`). All run without a model; the user reviews decisions in a report. [repo fact]

**User control.** Abogen lets users edit the extracted text with inline markers for chapters, voices, metadata and timestamps. sci2audio shows the pre-analysis report with decisions to accept or change. Abogen's approach is simpler to build; sci2audio's explains itself better. [advisor proposal]

## 6. Voices and audio

- **Engines.** Since v1.3, each Abogen engine is a plugin behind a written contract (`docs/tts-plugin-architecture.md`): `Engine.createSession()`, `EngineSession.synthesize(SynthesisRequest) → SynthesizedAudio`, immutable value objects for request, voice selection and audio, explicit `dispose()` rules and thread-safety statements. New engines don't touch the core. sci2audio switches providers inside `tts.py`. [external fact] [repo fact]
- **German.** Abogen doesn't support German: official Kokoro has no German voice and the language enum stops at nine languages. sci2audio already runs the Thorsten Kokoro German fine-tune (Apache-2.0, CC0 data) via the `semidark` forks of `kokoro` and `misaki` (`pyproject.toml` extra `kokoro-de`). This is the one piece Abogen users would gain from an upstream plugin (O-15). [external fact] [repo fact]
- **Voice features only Abogen has:** voice mixer with weighted blends ("voice formulas"), saved voice profiles, multi-voice books with LLM speaker attribution, GPU support (CUDA, ROCm, Apple MPS), voice previews. [external fact]
- **Output.** Abogen writes WAV, MP3, M4B with chapters and cover art, EPUB 3 with media overlays, and pushes to Audiobookshelf. sci2audio writes MP3, M4B, Opus. [external fact] [repo fact]
- **Read-along.** Abogen subtitles the spoken text; only English Kokoro reports per-word timestamps, other languages fall back to segment timing split proportionally (documented in `AGENTS.md`). sci2audio's `mitlesen.py` aligns sentences of the original with sentences of the spoken script (monotone alignment, keep/split/merge/drop, verified pairs only) and highlights the original; unmatched sentences light their paragraph instead of a guessed time. [external fact] [repo fact]

## 7. Installation, interface and packaging

- **Install path.** macOS/Linux: `uv tool install --python 3.12 abogen`, with `[cuda]`, `[cuda126]`, `[cuda130]` and ROCm variants. Windows: `WINDOWS_INSTALL.bat` downloads an embedded Python and PyTorch and creates a desktop shortcut; espeak-ng must be installed separately from its `.msi`. Models download from Hugging Face on first use with a message (`hf_tracker.py`); a settings option pre-downloads everything for offline use. Docker serves the web UI. [external fact]
- **Cost of that path.** PyTorch makes the install large (gigabytes with graphics-card support) and pins Python to 3.10–3.12. Many changelog fixes are installer problems: Windows DLL initialisation errors, a missing `libxcb-cursor0` on Linux, `pip` missing under `uv`. There is still no signed, double-click installer — yet Abogen reached ~6,100 stars. [external fact]
- **Two interfaces.** PyQt6 desktop app plus a Flask web UI added by a contributor. `AGENTS.md` warns that the text-splitting logic exists in both (`conversion_pipeline.py` for the web UI, an inline branch in `pyqt/conversion.py` for the desktop app) and "both UIs must stay in sync". [external fact]
- **Licences of dependencies.** Abogen is MIT but depends on PyMuPDF (AGPL-3.0) and PyQt6 (GPL-3.0). sci2audio uses pypdfium2 (permissive) and, being GPL-3.0 (D-42), could use either without conflict. [external fact] [repo fact]

## 8. Engineering practice

| Practice | Abogen | sci2audio |
|---|---|---|
| History | 888 commits since 24 Apr 2025, in bursts (173 in Oct 2025, 219 in Jul 2026, 1–2 per month in between) | 540 commits and 305 PRs in 14 days (26 Oct – 8 Nov 2026), all self-merged, 0 reviews |
| CI | `test_pip.yml`: every push to `main` and every PR touching Python; matrix ubuntu/macos-14/windows, Python 3.12, `uv` with cache, `QT_QPA_PLATFORM=offscreen` | `sci2audio.yml`: `workflow_dispatch` only ("CI bis November 2026 abgeschaltet (Budget)"), Ubuntu, Python 3.10/3.12 |
| Structure | Layered domain/application/infrastructure + plugin system | Flat; `web.py` 7,245 lines |
| Contracts | `AGENTS.md` (segmentation and subtitle contract, written after a regression); TTS plugin specification | KB and ADRs; no module contracts yet |
| AI agents | Open use: `AGENTS.md` addressed to coding agents; 9 commits by `copilot-swe-agent[bot]`, 5 by `agent` | Claude Code builds nearly everything |
| Releases | 27 tags, PyPI, changelog crediting contributors by name and PR | None |
| Developer docs | `getting-started.md`, `developer-guide.md`, `testing.md`, `contributing.md` | Internal KB only |

Provenance: [external fact] for Abogen (git history and workflow files); [repo fact] for sci2audio (see `audit-process-and-velocity.md`).

**Two cautions from Abogen's history:** a single 55,000-line contribution locked in the layered core *and* the two-interface duplication in one step; and activity drops to 1–2 commits a month between bursts, so issues wait. Both are normal for a hobby project and worth avoiding deliberately. [advisor proposal]

## 9. Recommendations (mapped to the playbook)

| # | Recommendation | Playbook phase | Decision entry |
|---|---|---|---|
| R1 | Publish to PyPI so `uv tool install sci2audio` / `pipx install sci2audio` works; message while voices download; "download everything for offline use" option | 5 (and 4.4) | D-47 |
| R2 | One interface only: keep the browser UI served locally, optionally in a window shell later; no Qt app | 3 (Q2) | D-45 |
| R3 | Split `web.py` into layers like Abogen: `domain/` (pure logic), `application/` (use cases), `infrastructure/` (file, audio, PDF adapters), UI on top | 3.1 | D-46 |
| R4 | Voice plugin contract modelled on Abogen's spec (engine, session, synthesis request, audio result) for `tts.py` | 4 | D-46 |
| R5 | Written contracts for fragile parts (`CLAUDE.md` or short contract files), added after each regression — agents follow written rules far better than implied ones | 2.1 onward | learning track |
| R6 | CI on Linux/macOS/Windows for every PR (free for public repos); tagged releases with a changelog | 2.8, 5, 6 | — (already in playbook) |
| R7 | Keep English Kokoro on ONNX; German PyTorch as an optional extra until an ONNX German model exists. **Refined the same day** by `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md`: Abogen's English quality comes from misaki (Kokoro's front end); decide PyTorch/MPS vs. misaki + ONNX by a spike | 4.1 | D-48, D-52 |
| R8 | Later, high value per effort: SRT/VTT export from the read-along data, cover art in M4B, EPUB 3 with media overlays | 7 | — |
| R9 | Optional learning project: German Kokoro plugin for Abogen (Colin can license that code to Abogen under MIT as copyright holder) | 7 | O-15 |

**Avoid:** PyTorch as a required dependency; two front ends; giant single changes; English-only normalisation patterns copied into German code.

## Advisor pre-analysis

- The comparison confirms the pivot's bet: the only defensible reason for a separate app is the text pipeline. If the layout reader and detectors were not clearly better than Abogen's page-text approach on scientific PDFs, contributing to Abogen would be the better learning path. A quick measurement would settle it: run both on 3 own scientific PDFs (two-column, footnotes, formulas) and count reading-order errors and unread footnote marks.
- Abogen's most transferable asset for Colin is not code but **process**: written contracts for agents, 3-OS CI, releases, changelog. That matches the learning goal in ADR-007 exactly.
- Abogen's plugin contract is a good template but heavier than sci2audio needs (session lifecycle, dispose rules). Start with engine + `synthesize()` + voice list; add sessions only when concurrency needs them.
- Don't copy the dual-UI path: one browser UI is enough for v1.0 and already exists.

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| AQ1 | Measure sci2audio vs. Abogen on 3 own scientific PDFs before v1.0? | Yes, in phase 3 as a characterisation fixture | Whether the text pipeline is as far ahead as the code suggests |
| AQ2 | Adopt Abogen's full plugin spec or a slimmer version? | Slimmer (engine + synthesize + voices) | D-46 scope |
| AQ3 | Contribute the German plugin upstream before or after sci2audio v1.0? | After v1.0 | O-15 timing |
| AQ4 | Offer EPUB 3 media-overlay export? | v1.1+, only if users ask | Scope of v1.0 |
| AQ5 | Re-audit Abogen when? | When sci2audio v1.0 ships, or if Abogen adds German or a layout-aware PDF reader | Revisit trigger |
