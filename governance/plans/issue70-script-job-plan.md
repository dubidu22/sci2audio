# Plan: Issue #70, the script job (app layer)

Status: **waiting for the coordinator's approval** (critical: golden files, a new dependency, KB entries). Written 12 Nov 2026 on `main` at 006c964 (after #83 and #86). Thread "Build the script job".

Sources read: Issue #70; `CLAUDE.md`, `.claude/rules/tests.md`, `.claude/rules/licences.md`, `.github/lanes.yml`; `plans/v1-remaining-plan.md` row 11, the app paragraph and §4 Q6/Q15; KB D-57, D-61, D-105, D-109, D-115, D-128; code on `main`: `core`, `extraction.extract_pdf`, `layout.build_document`, `textprep.run_steps` / `StepRun` / `cut_utterances`, `output.names`, `output.write` (partial-file pattern), `sci2audio.testing`. I ran extraction and layout on all 7 corpus papers to see their level-1 sections (whole run: 3.7 s for all 7).

## 1. What the job does

`file → extraction → layout → text steps (whole document) → apply_edits → chapters → utterances of the selected chapters → script + report`, never stopping to ask (D-61 (3)).

1. **Pick extraction by file type** (suffix, case-insensitive): `.pdf → extract_pdf`. EPUB, Markdown and text join the same table as #73/#74 land. Any other suffix: `UnsupportedFileError` before anything runs.
2. **Layout**: `build_document(content, LayoutSettings(language=settings.language))`.
3. **Text steps on the whole document**: `run_steps(document, StepContext(document.language), steps, switched_off=settings.switched_off)`. Every block is seen by every step, whatever chapters are chosen, so the report is complete and a switch or chapter change needs no new analysis.
4. **Script**: `StepRun.script()` (= `apply_edits` of the accepted edits) for the whole document.
5. **Chapters** from the document (section 3), with the selection from the settings.
6. **Chapter filter at cutting**: the script pieces of each *selected* chapter (pieces whose block lies in the chapter's block range) go to `cut_utterances(document, pieces)`; deselected chapters get no utterances. Because the cutter never joins pieces of different blocks, this equals cutting the whole script and dropping the deselected chapters' utterances; a property test proves it.
7. **Report** from the `StepRun`, the chapters and the selection (section 4). Edits in deselected chapters are marked **not spoken**.
8. **Write** the script, the report (JSON and Markdown) to the output folder and a job record to the working folder (section 5).

## 2. Modules (all in `src/sci2audio/app/`, lane `app`; core and the layer contract stay unchanged)

| Module | Holds |
|---|---|
| `settings.py` | `JobSettings` (frozen dataclass, validated) |
| `config.py` | `default_config_file()`, `load_settings(file)`, `save_settings(settings, file)` |
| `chapters.py` | `Chapter`, `find_chapters(document)`, `default_selection(chapters)`, `REFERENCE_NAMES` |
| `script.py` | `ScriptResult`, `ChapterScript`, `prepare_script(document, settings, steps)`: steps 3 to 7 in memory, no files |
| `report.py` | `Report`, `ReportEdit`, `CategoryCount`, `build_report(...)`, `report_data(report) -> dict` (JSON), `report_markdown(report) -> str`, `script_text(result) -> str` |
| `job.py` | `JobRunner` (one job at a time), `run_script_job(source, settings, work, *, overwrite, progress, steps)`, `Phase`, `JobError`, `UnsupportedFileError`, `JobBusyError`, `JobWritten` |
| `files.py` | `write_atomically(path, text, overwrite)`: `.<name>.partial`, then rename (the #69 pattern) |

`app/__init__.py` re-exports the public names. The app may import `core`, the five stages and (not needed here) `output.names` for safe file names.

### `JobSettings` (acceptance criterion 1)

```python
@dataclass(frozen=True)
class JobSettings:
    language: str = ""                                  # "" = the file's own, else "en"
    switched_off: frozenset[Category] = frozenset()     # category switches (UC-02)
    chapters: frozenset[int] | None = None              # chosen chapters by index; None = default
    voice: str = ""                                     # for #71; "" = the default voice
    speed: float = 1.0                                  # for #71; 0.5 to 2.0
    output_folder: Path | None = None                   # None = the source file's folder
```

Validation in `__post_init__`: language "" or a tag like `en` / `en-GB`; categories are `Category`; chapter indices ≥ 0; speed finite and in range. Passed into every call; nothing reads global state. The working folder is a separate argument, not a setting (it belongs to one job).

## 3. Chapters (Q6)

- `Chapter(index, title, start, end, references: bool)`: block range `start` up to `end`, title as printed (white space runs → one space, so "2 Related Work" keeps its number; referenceable as printed).
- **Each top-level section of `Document.sections` starts a chapter**; a chapter runs to the next chapter's start or the document's end, so every block is in exactly one chapter even where the section tree leaves gaps.
- **Text before the first heading** (blocks `0` up to the first section's start, when that is > 0) is the first chapter, titled with `Content.metadata.title`, else the file name without its extension (`acl2023-hardt-ellipsis`).
- **No headings**: one chapter over all blocks, titled the same way (arXiv Liu in the corpus).
- **References**: a chapter whose title, without its printed number, is one of `REFERENCE_NAMES` (References, Bibliography, Reference list, Works cited, Literature cited, Literatur, Literaturverzeichnis; case-insensitive) is marked `references` and deselected by default. Appendices ("A Appendix", "Supplementary Material: Appendices", "A Proof of Lem. 1") stay selected (TP-06).
- **Selection**: `settings.chapters is None` → every chapter but the references. Otherwise exactly the given indices; an index the document doesn't have is ignored and named in the report's warnings (the job never stops).
- EPUB (one chapter per top-level navigation entry) needs no extra code here if #75's layout makes those entries the level-1 sections; #73/#75 test it.

What the corpus gives today (from my run): chi 12 chapters (front, Abstract, 1–5, Limitations, Ethics Statement, Acknowledgements, References, Appendices), hardt 12, nowak 14, arsiwalla 9, Liu 1, seaborn 7 (front titled "seaborn: statistical data visualization"), pymedphys 5.

## 4. The report (UC-01, Q15)

One entry per proposed edit (every `Outcome` of the run), in the runner's order (step order, then document order):

| Field | Meaning |
|---|---|
| `category`, `category_label` | `Category` value and its label ("Page furniture") |
| `step`, `kind`, `reason` | from the edit |
| `status` | `accepted`, `set-aside`, `switched-off` (runner) |
| `spoken` | false when its chapter is deselected (or it isn't accepted); the Markdown says "not spoken (chapter deselected)" |
| `original` | the original text of its span, as printed |
| `said` | what is read instead: the replacement; "" for remove; `[pause]` for pause; the original for `ask` |
| `block`, `start`, `end` | its span |
| `page`, `printed_page` | the page of the span's first character (via `Block.part_at` and the content's items) and the label printed on it ("" if none) |
| `chapter` | index of its chapter |
| `won_by` | set-aside only: step, kind and span of the accepted edit that won |

Plus: source (name, format, sha256), language, settings, chapters (index, title, block range, first page, `references`, `selected`, utterance count), **counts per category** (accepted, set aside, switched off, accepted but not spoken), problems (failed steps), steps not run for the language, warnings (ignored chapter indices).

JSON: `{"format": "sci2audio-report", "version": 1, ...}`, keys in a fixed order, UTF-8, two-space indent. Markdown: a summary table of counts per category, the chapter list with chosen ones ticked, then the edits grouped by category (page, original → said, reason, status), set-aside edits with what won.

## 5. Files

- **Output folder** (`settings.output_folder`, else the source's folder): `<stem>.script.txt`, `<stem>.report.json`, `<stem>.report.md`, `<stem>` = the source name without extension through `output.names.clean`.
- **Script text**: a header (source, language), then per chapter `# <title>`; a deselected chapter shows `# <title> (not spoken)` and nothing under it. Under a chapter: **one utterance per line** (exactly what the voice gets per call), a blank line between blocks, a pause as `[pause]` on its own line.
- **Working folder** (passed in, created if missing): `job.json` = `{"format": "sci2audio-job", "version": 1, sci2audio version, source name/format/sha256, settings, selected chapters, files written}`. #71 adds its chunk records and uses this to resume (same sha256 and settings → skip finished chunks).
- Every file is written as `.<name>.partial` and renamed when complete; on any error the partial file is removed. **Existing outputs are replaced only with `overwrite=True`** (checked before extraction starts, so a refusal costs nothing), the same rule as #69.

## 6. Running jobs

- `JobRunner` owns a lock: `runner.run_script(...)` raises `JobBusyError` if a job is already running on that runner (one job at a time; cli and web each create one runner; no module-level state).
- `progress: Callable[[Phase], None] | None` is called as each phase starts (extracting, laying out, text steps, cutting, writing, done), for #76's server-sent events. **The time estimate and resume are #71's**; the phases and `job.json` are the shape they build on.
- The job never stops to ask: a failing text step is a problem in the report (runner); an `ask` edit reads the original and is listed; a deselected or empty chapter is listed. It *fails* (raises `JobError` with a clear message, nothing half-written) only when it cannot go on: unsupported type, unreadable or vanished file, extraction error, a write error such as a full disk.

## 7. Settings file (decide platformdirs)

`default_config_file()` = `platformdirs.user_config_path("sci2audio", appauthor=False, roaming=True) / "settings.json"` (Windows `%APPDATA%\sci2audio`, macOS `~/Library/Application Support/sci2audio`, Linux `$XDG_CONFIG_HOME/sci2audio`). Only the cli and web call it; the job never touches the file. JSON (`tomllib` can only read). Saved: every `JobSettings` field **except `chapters`** (a choice for one document), plus `"version": 1`. `load_settings` never fails the start-up: a missing file gives the defaults; broken JSON or a bad field gives the defaults for that field and a warning the caller shows. `save_settings` writes atomically.

**Dependency**: `platformdirs>=4.14.5,<5` (MIT, latest 4.14.5 released 4 Nov 2026, no dependencies, Python ≥ 3.11). Row in `THIRD_PARTY_LICENSES.md`; `pyproject.toml` and `uv.lock` change in this PR (as #69 did for imageio-ffmpeg).

## 8. Tests

- `test_app_settings.py`: validation of every field; config round trip; missing, broken and partly bad files give defaults plus warnings; `chapters` never saved; the default path is per OS (platformdirs mocked); save is atomic (old file intact when the write fails).
- `test_app_chapters.py`: front chapter titled from metadata, else the file name; no headings → one chapter; references deselected, appendices selected (names with and without numbers); a top-level section of level 2; gaps in the tree; ignored indices. **Hypothesis**: on any document (`core_strategies.documents`), chapters cover every block exactly once in order, titles non-empty, exactly one front chapter when the first section starts after 0.
- `test_app_script.py` (the three Q6 statements): a recording step shows **the steps saw every block** although chapters are deselected; **utterances exist only for selected chapters** and equal the whole-script cut with the deselected chapters dropped (Hypothesis, random documents, edits and selections); **edits in deselected chapters are `spoken: false`** and counted as not spoken. Also: an `ask`-proposing test step and a failing test step → the job finishes, report lists both; set-aside edits listed with the edit that won; counts sum to the outcomes.
- `test_app_report.py`: JSON key order and version; Markdown sections; printed page and physical page for a span on page 2 with a label; `said` per edit kind.
- `test_app_job.py`: extraction picked by suffix (`.PDF` too); unsupported suffix; corrupt PDF → `JobError` naming the file; output folder default; `overwrite` refusal before any work; `job.json` content; `JobBusyError` from a second run on the same runner (one thread blocked in a progress callback); progress phases in order.
- `test_app_faults.py` (file writing, tests.md): **disk full** (`OSError(ENOSPC)` on write) → `JobError`, no partial or half file left, earlier outputs untouched; **file removed during the run** (removed in the progress callback before extraction) → clear `JobError`; **no network** (whole job under `sci2audio.testing.no_network`); **killed mid-run and run again** (a write interrupted after the first file) → the next run gives identical files, no `.partial` left.
- `test_app_corpus.py`: **golden snapshots (syrupy) of the script text, report JSON and report Markdown for `acl2023-hardt-ellipsis` and `joss2021-waskom-seaborn`** (references and an appendix; a metadata title); all 7 papers run with no problems and every chapter list as in section 3. Each later text-step PR (#64 to #68) updates these snapshots and explains the diff.
- `test_app_benchmark.py` (`benchmark`): the script job on `arxiv2024-arsiwalla-qualia-meaning` (28 pages, the largest paper) with a budget of **30 s** (asserted), and a row in `docs/baseline.md`.

Before the PR: the full CLAUDE.md check list, plus the Hypothesis `nightly` profile on the new property tests.

Rough size: about 700 lines of code, 900 lines of tests, plus snapshots.

## 9. Decisions (numbered, for the KB)

1. **Text steps run on the whole document; the chapter filter applies when utterances are cut**; the report marks edits in deselected chapters as not spoken (Q6, as instructed). Alternative not chosen: running steps only on chosen chapters (report incomplete; a new analysis per chapter change).
2. **Chapter boundaries**: each top-level section starts a chapter and the chapter runs to the next one's start, so gaps in the section tree belong to the chapter before them; a top-level section of a deeper level (no level-1 heading above it) also starts a chapter. Alternative: only level-1 sections (blocks under a stray top-level level-2 section would belong to no chapter).
3. **Front chapter and no-heading chapter title**: `Content.metadata.title`, else the file name **without its extension**. The front chapter exists whenever the first heading isn't block 0, even if it holds only furniture; a chapter with nothing to say is listed with 0 utterances and #71 gives it no audio.
4. **Reference chapters are found by title** (printed number removed, case-insensitive) in a fixed list of English and German names; appendices are never deselected.
5. **Chapter selection is by index into the chapter list**; `None` = the default; unknown indices are ignored with a warning in the report, never an error.
6. **Report format**: versioned JSON `sci2audio-report` v1 owned by the app, plus Markdown; fields as in section 4 (page as both physical number and printed label).
7. **Script text format**: one utterance per line, blank line between blocks, `# title` per chapter, deselected chapters named with "(not spoken)".
8. **Files and overwriting**: outputs `<stem>.script.txt`, `<stem>.report.json`, `<stem>.report.md` in the output folder (default: the source's folder); partial-then-rename; replace existing files only with `overwrite=True`, checked before work starts (same as #69).
9. **Working folder record** `job.json` (`sci2audio-job` v1) as the shape for #71's resume.
10. **One job at a time per `JobRunner`** (a lock owned by the runner object, `JobBusyError` when busy); progress as phase callbacks.
11. **Settings file**: `platformdirs` (MIT) `user_config_path("sci2audio", roaming=True)/settings.json`, JSON, version 1; chosen chapters are not saved; a broken file never stops start-up (defaults plus warnings). Alternative not chosen: hand-written per-OS paths (about 20 lines, but platformdirs handles XDG, roaming profiles and macOS correctly and is widely used).
12. **Failing vs asking**: the job fails with `JobError` only when it cannot go on (unsupported, unreadable or vanished file, extraction error, write error); everything else is reported and the run completes (D-61 (3)).

## 10. Out of scope (with issues where new)

- Audio, voice and speed use, resume, time estimate: #71. Command line `script`: #72. Server and interface: #76/#77.
- EPUB, Markdown and text extraction: #73/#74 (they add their row to the extraction table).
- Caching the analysed document between a preview and the real run: not needed at today's speed (under 1 s per paper); an issue only if #76 needs it.
