# App batch B7: unreadable PDFs stop, retried names, merge-through-link test

Status: **PLAN, waiting for the coordinator's approval** (critical batch: #442 B user-facing stop, #493 CRIT-02).
Author: app/release lane thread "Stop unreadable PDFs and fix app leftovers", 18 Nov 2026 ~23:55Z. Base: main 5a605e5.
Read: `next-batches-2026-11-18.md` (B7 row, §2 AC-442.3, §5), `extraction-batch-b1-plan.md` §1.3 (B7 policy, D-762),
`docs/unreadable-pdf-text.md`, `extraction/legibility.py`, issues #442 #187 #493 #544, CLAUDE.md, rules 1.4.7.

## PR split

| PR | issues | critical | branch | labels |
|---|---|---|---|---|
| PR 1 | #442 part B + #187 | yes (user-facing stop; risk:high) | `app/unreadable-text-442` | lane:app, risk:high |
| PR 2 | #493 + #544 (test only) | yes (CRIT-02: names of files written into the person's folders) | `app/retried-names-493` | lane:app, risk:high |

Both branch from main. PR 2 touches other functions of two files PR 1 also touches (`app/audio.py`, `app/job.py`);
whichever merges second merges main (no hand-resolve expected: different functions).
#544 rides in PR 2 (a test only, the same "files are safe" area) rather than a third PR, to save a review set-up.

## PR 1: stop before voices on unreadable text (#442 B, AC-442.3) and the report warning (#187)

**Policy (pinned by D-762, reused as is).** `extraction.legibility(content)` gives the per-page verdict.
Stop when `2 * sum(characters of unreadable pages) > sum(characters of all pages)`; otherwise any unreadable page
gets a warning naming it. Pages are named by `Page.number` (1 = first page, as a PDF viewer counts), as ranges ("1–3, 7").

**Choice Q1 (recommended: PDF only).** The policy applies to PDF sources only. `Page` means a printed page only in a
PDF (an EPUB "page" is a spine file, a text file is one page), #187 and #442 are about PDF fonts, and a text file's
encoding guess already has its own warning (D-346). Alternative: all formats, naming pages only for PDFs; more strings,
no known case.

**Code**
- `app/readability.py` (new, ~50 lines): `Unreadable(pages: tuple[int, ...], stops: bool)`, `unreadable(document) -> Unreadable | None`
  (None when no page is unreadable or the source is not a PDF), `page_ranges(pages) -> str`.
- `app/job.py`: `UnreadableTextError(UnreadableFileError)`: the CLI maps it to exit 5 (UNREADABLE, `cli.py` unchanged);
  message names the pages ("the text of pages 1–3 cannot be read: the PDF stores no letters for it, only glyph numbers,
  so the voice would read nonsense; no audiobook is made from it").
- `app/audio.py` `run_audio_job`: right after `read_document`, before the voice check and any speech or write:
  `if (u := unreadable(document)) and u.stops: raise UnreadableTextError(...)`. No audio, no cover, no record written.
- `app/report.py`: `Report.unreadable: Unreadable | None = None`; `build_report` sets it and adds one English warning
  (stop: "…no audiobook can be made from it"; partial: "the text of page 4 looks garbled… those pages read as nonsense;
  leave their chapters out"). `report_data` adds `"unreadable": {"pages": [...], "stops": bool}` **only when set**, so every
  corpus report, the CLI goldens and `test_app_corpus.ambr` stay byte-identical (no golden moves). The script job
  (analysis) still writes script and report: it speaks nothing, and the report is where the person learns why.
- `web/tasks.py` `_KINDS`: `("unreadable-text", UnreadableTextError)` before `JobError` (API or a stale page that starts
  a job anyway gets a translated reason, the pages in the details).
- `web/templates/document.html` (step 1 and step 3 only): a callout in step 1, `bad` for a stop, `warn` for a partial
  case, translated with the page list; in step 3 `blocked = 'needs_readable_text'` when the report says it stops.
  `app.js` keeps any blocked value it does not know (line 433) and refuses the click with the note: **no app.js change**.
- `web/strings/en.toml`, `de.toml`: `document.unreadable_stop.one/.other`, `document.unreadable_pages.one/.other`,
  `make.needs_readable_text` (exported to the script by the existing `make.needs_` prefix), `error.unreadable-text`.
- `docs/unreadable-pdf-text.md`: the "What the app does" section says where it is done and names the report key;
  `README.md` exit code 5 line adds "or its text can't be read". CHANGELOG Unreleased line (D-768).
- #187's "measure and threshold recorded in the KB": they are D-762 and `docs/unreadable-pdf-text.md`; the PR body
  asks the KB thread for nothing new beyond the daily log entry. #187 closes with PR 1.

**Tests (written first)**
- `tests/unit/test_app_readability.py`: policy on built `Content`/`Document` (exactly half does not stop, one character
  more does; zero characters never stops; EPUB/Markdown/text never flagged; ranges "1–3, 7"); Hypothesis: never fails
  on any `Content` (`core_strategies.contents()`), pages ⊆ document pages, `stops` implies pages non-empty.
- `tests/unit/test_app_audio_job.py` (or a new `test_app_unreadable_job.py`): on `glyph_number_pdf(GERMAN)` the audio job
  raises `UnreadableTextError` naming page 1, the fake voice is never made, the output folder and the work folder hold
  no audio, cover or record (mutant: remove the check → test fails). A two-page PDF (one glyph-number page, one plain
  Helvetica page with fewer characters) does not stop and its report warns about page 1 only. Helper `joined_pdf(*pdfs)`
  in `tests/unit/pdf_maker.py` (pypdfium2 `import_pages`, already a dependency) — a test-helper addition in the
  extraction lane's helper file, listed here for the coordinator.
- `tests/unit/test_app_report.py`: JSON key present only when set; Markdown warning line; corpus reports carry no key
  (the existing corpus snapshot test proves it unchanged).
- `tests/unit/test_cli_errors.py`: `sci2audio convert` on the glyph PDF exits 5 with the pages named.
- `tests/unit/test_web_*.py` (TestClient): document page shows the stop callout and `data-blocked="needs_readable_text"`
  in EN and DE; partial warning callout; a job started through the API ends failed with `unreadable-text`.
- `tests/browser/test_prepare.py`: one browser test: the blocked make button says why, axe passes light/dark/German.

Rough size: ~250 lines of code and strings, ~350 lines of tests.

## PR 2: a refused name is retried, never over a person's file (#493), and the link test (#544)

**Where a cleaned name is first written**
1. `web/documents.py` `DocumentStore._place` (`os.replace(part, target)`): the stored copy in sci2audio's own data folder.
2. `app/job.py` `script_files` / `_write`: `<name>.script.txt`, `.report.json`, `.report.md` (web: the document's own
   `script/` folder; CLI: next to the source or in `-o`, a person's folder).
3. `output/write.py` `write_audiobook` and `app/audio.py` `audiobook_files`: the MP3s, M4B, subtitles and read-along file
   in the audiobook folder (a person's folder). ffmpeg creates the MP3/M4B, so an EILSEQ there comes back as an
   `FfmpegError`, not an `OSError`: catching it at write time is not possible for the audio files.

**Design: decide the names before any work, by asking the file system once per name that needs it.**
- `output/names.py` (pure): `older(text)` turns every code point not assigned in Unicode 3.2 into a space
  (`unicodedata.ucd_3_2_0`, in the standard library: no data table, no dependency). 3.2 is older than APFS's oldest
  table (9.0), so every Mac accepts what is left; a few newer letters become spaces in a retried name only.
  `retried(name, fallback)` = `clean(older(name), fallback)`.
- `output/write.py`: `refused(folder, name) -> bool`: only for a name that `older` would change (every other name is
  never asked: zero file-system side effects for ordinary names), create the hidden probe `.<name>.partial` with
  `O_CREAT | O_EXCL`, remove it if this call made it; True only for `errno.EILSEQ`. An existing probe (left by a killed
  run, or anyone's) is never removed by the probe and counts as accepted.
  `audiobook_targets(out_folder, title, chapter_titles, settings) -> Written-shaped paths`: the one place the audiobook's
  names are made; book base and each chapter name retried when refused. `write_audiobook` and `app.audio.audiobook_files`
  both use it, so the "exists already" check before speech (D-163), the commit check (link, never replace without
  `overwrite`), the removal of new files on failure (`_encode`), the record and the web's project record all see the
  same, retried names. `_encode` makes the output folder before naming (inside its try), so the probe can run.
- `app/job.py` `script_files`: the same for the stem when the output folder exists; `_write` names again after it made
  a missing folder (nothing can exist in a new folder, so the overwrite check before work stays exact).
- `web/documents.py` `_place`: catch `OSError` with `EILSEQ` on `os.replace`, retry once with `stored_name` of the older
  text, then the fallback `document<suffix>`; this folder is sci2audio's own data folder (no person's file in it).

**The CRIT-02 guarantee, stated for the review:** a retried name is never written over an existing file unless the
person chose to replace files *and* the refusal they answered named that retried name. Concretely: (a) without
`overwrite`, an existing file under the retried name is refused before speech (OutputExistsError names it) and again at
the commit (link refuses); (b) the retried name is the one listed in that refusal, because the check and the writer
share `audiobook_targets`; (c) the probe never removes a file it did not create.

**Tests (written first; fake file system call raising EILSEQ, as the issue asks; CI's Mac can't produce it)**
- `test_output_names.py` (new, or the file that tests `clean` today): `older`/`retried` (a Unicode 15 emoji becomes a space; "Café" unchanged; all-new → fallback);
  Hypothesis: `retried` output is always `clean`-stable and holds only 3.2-assigned code points.
- `test_output_faults.py` (or a new `test_output_retried_names.py`): monkeypatched `os.open` raising EILSEQ for names holding U+1FAE8: the audiobook is written
  under the retried names; a plain name is never probed (spy); a pre-existing file under the retried name is refused
  without `overwrite` and left byte-identical (CRIT-02 test; mutant: drop the existence check for retried names →
  fails); the probe never removes a probe file it did not make.
- `test_app_audio_job.py`: the pre-speech check names the retried file; `_encode` failure removes only new files under
  retried names.
- `test_app_job.py`: script job into a folder refusing the stem writes under the retried stem.
- `test_web_documents.py`: opening "\U0001FAE8 paper.pdf" with `os.replace` raising EILSEQ keeps the file as
  " paper.pdf"/"document.pdf", never a 500 `store-failed` (AC 1); each retry pinned by a test failing without it (AC 2).
- #544 in `tests/unit/test_app_projects.py`: exactly the issue's criterion (linked `from-earlier-version`, identical
  file outside, old file kept and in `outcome.left`, outside folder unchanged; `can_link` skip); the PR body states the
  mutant `if False:` and that the test fails under it.

Out of scope, will be filed if confirmed: the project folder's own name (`web/project.py` `folder_name`, `mkdir`) can
in principle meet EILSEQ too; it is made from the stored name, which PR 2 already makes acceptable on the same disk, so
only a Documents folder on another volume could still refuse it. I will check and file an issue rather than widen PR 2.

Rough size: ~180 lines of code, ~300 lines of tests.

## Files (for the B8 disjointness check)

| file | PR | note |
|---|---|---|
| `src/sci2audio/app/readability.py` (new), `app/job.py`, `app/audio.py`, `app/report.py`, `app/__init__.py` | 1, 2 | app |
| `src/sci2audio/output/names.py`, `output/write.py` | 2 | output (lane app+output per plan) |
| `src/sci2audio/web/documents.py` | 2 | `_place` only |
| `src/sci2audio/web/tasks.py` | 1 | `_KINDS` one row |
| `src/sci2audio/web/templates/document.html` | 1 | **template**: step 1 callout, step 3 `blocked` expression only |
| `src/sci2audio/web/strings/en.toml`, `de.toml` | 1 | new keys in `[document]`, `[make]`, `[error]` |
| `docs/unreadable-pdf-text.md`, `README.md` (exit 5 line), `CHANGELOG.md` | 1, 2 | |
| tests: `test_app_readability.py` (new), `test_app_audio_job.py`, `test_app_report.py`, `test_app_job.py`, `test_cli_errors.py`, `test_output_names.py`, `test_output_faults.py`, `test_web_documents.py`, `test_web_pages.py`, `test_app_projects.py`, `tests/browser/test_prepare.py`, helper `tests/unit/pdf_maker.py` (`joined_pdf`) | 1, 2 | |

Not touched: `web/player.py`, `web/api.py`, `web/models.py`, `web/pages.py`, `static/*.js`, `listen.html`, `_paper.html`,
any other template, `cli.py`, extraction, layout, textprep, goldens, regression cases.
**Overlap with B8 to confirm:** `document.html` (B8's #293 should only need the player templates) and the two strings
files (B8 likely adds `[player]` keys; different sections, so a merge of main resolves them; whichever lands second
merges main and re-runs CI).

## Questions for the coordinator
- Q1 above (PDF only; recommended).
- Confirm B8 does not edit `document.html`; if it must, PR 1 lands first or I move the callout into a macro file of my own.
