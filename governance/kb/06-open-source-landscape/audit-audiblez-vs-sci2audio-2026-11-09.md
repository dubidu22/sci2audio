# Audit: Audiblez vs. sci2audio (in-depth comparison)

`[AUDIT]` · Snapshot of 9 Nov 2026 · Owner: Colin · Advisor: Claude · Related: `audit-abogen-vs-sci2audio-2026-11-09.md`, `audit-similar-open-source-projects-2026-11-09.md`, `02-product-and-pipeline/audit-english-rules-vs-spacy-2026-11-09.md`, `decision-log.md` D-45, D-47, D-52 · Living version: Doc "Audiblez vs. sci2audio: in-depth comparison" (claude.ai artifact `HbTsHdbBohgqnkgGxmhHVW`)

> **Why this file exists.** After the Abogen deep dive, Colin ran Audiblez's window on his MacBook Pro M4 with an English EPUB ("The World Without Us", 595,205 characters) and asked for the same analysis, noting that Audiblez seems to lack rule-based editing even more than Abogen. He asked to verify that against the GitHub repository. Audiblez (`santinic/audiblez`, MIT, ~8,700 stars) is the second-most-starred Kokoro audiobook converter in the landscape survey.

---

## 1. Basis

| Item | Value | Provenance |
|---|---|---|
| Repository | `github.com/santinic/audiblez`, cloned in the session | [external fact] |
| State audited | Commit `788a6a8` ("kokoro 0.9.4 attempt"), 27 Feb 2026; version 0.4.9 | [external fact] |
| Files read | `audiblez/core.py` (420 lines, complete), `ui.py` (598), `cli.py` (43), `voices.py` (27), `pyproject.toml`, `README.md`, `.github/workflows/git-clone-and-run.yml`, `pip-install.yaml`, `test/` (3 files), git history | [external fact] |
| Colin's run | Screenshot of the wxPython window, 9 Nov 2026 | [session decision: Colin's own run] |

## 2. Short answer

- **Confirmed: Audiblez does essentially no rule-based editing.** Its complete text preparation is one loop in `find_document_chapters_and_extract_texts`: take the text of `title`, `p`, `h1`–`h4` and `li` elements from each EPUB document, append "." if the line doesn't end with one, join with newlines. Everything else is Kokoro's own English front end (misaki with spaCy). The only correction is manual editing in the per-chapter text box (`wx.EVT_TEXT` writes straight into `chapter.extracted_text`). [external fact]
- Audiblez is a small, focused tool (1,091 lines) that proved demand for "EPUB in, Kokoro audiobook out". It is EPUB-only, can't use the Apple GPU, names chapters after file names, and has been nearly dormant since March 2025. [external fact]
- **For sci2audio:** nothing to reuse from its text handling; its voice call is the same `KPipeline` already covered by Abogen's Kokoro plugin (D-52). It teaches how far a one-command install and a simple three-panel window carry a project. [advisor proposal]

## 3. At a glance

| Aspect | Audiblez | Abogen | sci2audio |
|---|---|---|---|
| Input | EPUB only (Markdown button commented out in `ui.py`) | EPUB, PDF, TXT, MD, subtitles | PDF, EPUB, MD, TXT, pasted text |
| Text preparation | None beyond tag text + "." per line | English normaliser, spaCy, optional LLM | Layout reader + 20 rule-based detectors |
| Chapter detection | File name contains `chapter`, `part_N`, `split_N`, `ch_N`, `chap_N` and text > 100 characters (`is_chapter`); else all files > 10 characters | EPUB navigation / PDF outline | EPUB navigation; PDF headings |
| Chapter names in the M4B | "Chapter 0", "Chapter 1", … (`create_index_file`) | From the table of contents | From the headings |
| Sentence splitting | spaCy `xx_ent_wiki_sm` + `sentencizer`; non-English sentences > 400 characters cut at a space | spaCy or regex, documented in `AGENTS.md` | Own rules (`satzteilung.py`) |
| Voice | Kokoro pinned `==0.9.4`, `KPipeline(lang_code=voice[0])` (PyTorch) | `KPipeline`, Supertonic, plugin contract | Kokoro EN via ONNX, DE via PyTorch; Piper |
| Apple GPU | No (CPU or CUDA; README: Apple Silicon not supported) | Yes (MPS) | Not yet |
| Output | WAV per chapter, M4B with cover (ffmpeg) | WAV, MP3, M4B, subtitles, EPUB 3 | MP3, M4B, Opus, read-along |
| Interface | CLI + wxPython window | PyQt6 + Flask | Browser UI + CLI |
| Code | 1,091 lines | ~43,000 | ~58,700 |
| Tests | 3 files, 20 test functions; not run in CI | ~1,600, 3-OS CI | ~1,220 (1,279 collected), CI off |
| Activity | 122 commits Jan 2025, 116 Feb 2025, 3 Mar 2025, 1 Feb 2026 | Bursts | Very active |
| Licence | MIT | MIT | GPL-3.0 |

## 4. Rule-based editing: verified gap list

| Rule-based step | Audiblez | sci2audio |
|---|---|---|
| Remove citations, footnote marks, URLs | No | Yes |
| Expand abbreviations (e.g., i.e., Fig., et al.) | No | Yes |
| Symbols, units, statistics | No | Yes |
| Write ALL-CAPS headings normally | No | Yes (`analysis/capitals.py`: common words in capitals written normally, real acronyms kept) |
| Skip notes, bibliography, index | No, unless unticked by hand | Yes (`sections.drop_reference_lists`, reference headings) |
| Heading text as chapter names | No | Yes |
| Search and replace, pronunciation fixes | No | Word lists; user-editable list planned (B5) |
| Manual text edit | Yes, per chapter | Yes |

[external fact for Audiblez; repo fact for sci2audio]

**Dead code and unused dependencies:** `epub-toc` and `qwen-tts` are declared in `pyproject.toml` but never imported; `unmark()` uses `Markdown`, which is never imported (would raise `NameError` if called). `deptry` is listed as a dev dependency but not run in CI. [external fact]

## 5. Colin's screenshot explained

| Observation | Cause in the code |
|---|---|
| Chapters named "The_World_Without_Us_split_035" | The list shows `chapter.get_name()` (EPUB file names); the table of contents is never read |
| Rows with 0, 8, 9, 22 characters | Every EPUB `ITEM_DOCUMENT` becomes a row (cover, title page, separators); files under 10 characters are skipped only during conversion |
| Long sections ticked that may be notes/bibliography/index | `find_good_chapters` ticks every file whose name matches `split_N` etc. and has > 100 characters; content is never checked |
| "SELECT BIBLIOGRAPHY. BOOKS. ARTICLES." | Each heading gets "." appended. Test with misaki (`en_core_web_sm`): "BOOKS" and "ARTICLES" in capitals are spelled letter by letter ("B-O-O-K-S"); lower case reads normally |
| Engine radio buttons: CPU / CUDA only | No MPS support; README: "We don't currently support Apple Silicon" (no Kokoro MLX implementation) |
| "Estimated Time Remaining: 00d 03h 17m 13s" | Not measured: `chars_per_sec = 500 if torch.cuda.is_available() else 50`. 11,833 s × 50 = 591,650 characters selected. README reports ~60 characters/s on an M2 CPU |

Also tested: a bibliography entry ("Weisman, Alan. 2007. … pp. 23–45.") through misaki — "pp." and "23–45" unknown (espeak-ng fallback), the year read as "two thousand seven". sci2audio drops reference lists before speaking. [test, 9 Nov 2026]

## 6. Voices, speed, packaging

- Voices: Kokoro 0.9.4, language from the voice name's first letter (`a` American, `b` British, `e` Spanish, `f` French, `h` Hindi, `i` Italian, `j` Japanese, `p` Portuguese, `z` Mandarin); no German. One MP4 sample per voice in `samples/`. [external fact]
- Speed: CPU on Apple Silicon; CUDA via `torch.set_default_device('cuda')`. [external fact]
- Install: `pip install audiblez` + `brew install ffmpeg espeak-ng`; window needs `pip install pillow wxpython`; Python 3.10–3.12; espeak-ng library located via Homebrew Cellar on macOS; spaCy `xx_ent_wiki_sm` downloads on first run. [external fact]
- Output: WAV per chapter → M4B via ffmpeg (AAC 64 kbit/s, cover as attached picture, chapter metadata file). [external fact]
- Resume: existing chapter WAVs are skipped on a second run. [external fact]

## 7. Engineering practice

| Practice | Audiblez |
|---|---|
| CI | `git-clone-and-run.yml`: on Linux and Windows, install, `audiblez --help`, download the DAISY "Fundamental Accessibility Tests" EPUB, convert it, check the M4B exists. Unit tests commented out. `pip-install.yaml`: install from PyPI and run |
| Releases | 4 tags, latest v0.4.9, PyPI |
| People | Claudio Santini 222 of 242 commits; 5 others |

[external fact]

**Habit worth copying:** the end-to-end smoke test with a public, openly licensed test document on several OS — cheap, and it catches broken installs that unit tests miss. [advisor proposal]

## 8. Take or avoid

| # | Item | Playbook phase | Entry |
|---|---|---|---|
| T1 | End-to-end smoke test in CI: one openly licensed EPUB and one PDF on Linux, macOS, Windows; check the audio file exists | 2.8 | — |
| T2 | Resume by skipping finished chapters (render per chapter) | 3.2 | — |
| T3 | Short README with one listenable sample per voice | 6 | — |
| T4 | Three-panel layout as the minimum UI: chapter list with ticks, text of the selected chapter, settings and progress | 3 (UI) | D-45 |
| A1 | Avoid file names as chapter names (also in M4B metadata) | 4.5 | — |
| A2 | Avoid chapter selection by file name; decide by content | — (already sci2audio's approach) | — |
| A3 | Avoid fixed speed estimates; measure on the first chapter | 3.2 | — |
| A4 | Avoid unused dependencies; run a dependency check (e.g. deptry) in CI | 2.8 | D-47 |

No new decisions: these refine D-45, D-47 and D-52. [advisor proposal]

## Advisor pre-analysis

- Audiblez's popularity with almost no text processing shows that most users convert well-made fiction EPUBs, where the text is already clean. sci2audio's audience (scientific PDFs) is exactly where that assumption breaks; the public README should demonstrate this with a two-column paper.
- Between Audiblez (1,091 lines, stalled) and Abogen (43,000 lines, layered, active), sci2audio's v1.0 should aim closer to Audiblez in *visible* simplicity and closer to Abogen in *engineering* discipline.

## Critical open questions

| # | Question | Default | Decides |
|---|---|---|---|
| ZQ1 | Which openly licensed EPUB and PDF for the CI smoke test? | DAISY accessibility test EPUB (as Audiblez) + one CC BY paper | T1 |
| ZQ2 | Copy the three-panel layout literally for v1.0? | Yes, as the starting shape of the browser UI | T4 |
