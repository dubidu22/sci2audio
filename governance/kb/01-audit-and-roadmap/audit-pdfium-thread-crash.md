# Audit: PDFium thread-safety crash

`[AUDIT]` · Found 8 Nov 2026 while running the test suite; re-checked 9 Nov 2026 on the production Python version. Severity **P0** (latent production crash), fix effort **S** (lock) now, **L** (worker processes) in phase 2.

---

## 1. What happened

| Run | Environment | Result |
|---|---|---|
| 8 Nov 2026 | Python 3.13.18, `pip install -e ".[dev,all]"`, full pytest | **`Fatal Python error: Segmentation fault`** after about 800 tests (exit 139, about 3.5 min) |
| 9 Nov 2026 | Python 3.12.3 (= production `python:3.12-slim`), same install, full pytest | No crash. 1 failed (unrelated: `test_rechte.py`), 1,274 passed, 4 skipped in 8 min 13 s |

**Crash stack (3.13), current thread:**
```
pypdfium2/_helpers/document.py:406  get_page
pypdfium2/_helpers/document.py:133  __getitem__
sci2audio/pdfdatei.py:275           Page.__init__   (self._page = doc.raw[index])
```
**At the same moment, another thread was inside pypdfium2:**
```
sci2audio/pdfdatei.py:380   chars
sci2audio/pdflayout.py:287  raw_lines
sci2audio/pdflayout.py:1027 read_page
sci2audio/extractor.py:601  _pdf_pages
sci2audio/extractor.py:99   extract
sci2audio/web.py:1727       _read
sci2audio/web.py:1702       markdown
sci2audio/web.py:2203       prepare
```
Two threads were executing PDFium calls simultaneously.

## 2. Root cause

`[external fact]` pypdfium2 documentation, "Incompatibility with Threading" (checked 9 Nov 2026): **PDFium is inherently not thread-safe. It is not allowed to call pdfium functions simultaneously across different threads, not even with different documents.** Doing so "would crash or corrupt the process". It's allowed in a threaded program only if a mutex ensures one PDFium call at a time; for parallel PDF work, use processes. PDFium's own header note and Android's framework say the same (no PDFium API is thread-safe; global state).

`[repo fact]` `sci2audio/pdfdatei.py` wraps pypdfium2 (`_pdfium()` imports it; `Document.__init__` opens `PdfDocument`; `Page.__init__` calls `doc.raw[index]`) **without any lock**. Note: `web.py` has a `self._lock` around its cache dictionaries (lines ~1689–1700), but that lock protects the cache, not PDFium calls; the reading itself runs outside it.

## 3. Where concurrent PDFium access comes from

| Source of a thread | Code | PDFium work done |
|---|---|---|
| Reading thread per upload | `web.py` `markdown()` starts `threading.Thread(target=…self._read…, name=f"lesen-{file_id}")` for each new `(file_id, pages, layout_model)` key | Full extraction: `extractor.extract` → `pdflayout.read_page` → `pdfdatei` chars, text pages, fonts |
| Run (job) threads | `web.py` lines 3156/3158: `threading.Thread(target=self._in_line / self._run …)` | Re-reading, figures, original view, change report |
| FastAPI threadpool | Every plain `def` endpoint runs in a worker thread; up to 50 concurrent requests per machine (`fly.toml` soft limit) | Endpoints touching originals, notes, figures, PDF exports |
| Other background threads | `web.py` lines 2650 (corrections), 4373/4447 (Tigris sync), 6055 (clean-up) | Mostly no PDFium; verify |

Modules that call into `pdfdatei` (number of references): `original.py` 8, `notizen.py` 7, `extractor.py` 7, `figures.py` 5, `kodierung.py` 4, `verkleinern.py` 3, `bildmodell.py` 3, `pdfschreiben.py` 2, `pdflayout.py` 2, plus `musterprobe`, `leistung`, `korrekturen`, `evaluator/texte`, `epub`, `cli`, `berichtpdf`, `abbildungen` (1 each). Any two of these running at the same time in one process is a violation.

## 4. Production exposure

| Question | Answer |
|---|---|
| Can it happen in production? | **Yes, in principle.** Two users uploading PDFs at about the same time on the same machine, or one user's run reading while another opens the original view, gives concurrent PDFium calls. Each account is pinned to one machine (`konto_maschine`), but one machine serves several accounts (up to 3 runs per machine) |
| Why no crash on 3.12? | The race is timing-dependent; 3.13 changed interpreter timing. No crash in one run isn't evidence of safety. The rule above is unconditional |
| Effect of a crash | Segfault kills the whole web process on that machine: all runs on it stop (they resume after restart, per `MEHRERE-MASCHINEN.md`), open requests fail, uploads in flight are lost. Fly restarts the machine (`restart policy on-failure`, 10 retries) |
| Silent corruption | Possible per the pypdfium2 docs ("crash or corrupt"): wrong text from a page without a crash. Would surface as reading errors the sample PDFs might not cover |
| Current load | No users, so actual risk today is near zero. **It becomes real on the first busy day after launch** |

## 5. Fix options

| Option | How | Pros | Cons | When |
|---|---|---|---|---|
| **A. Process-wide lock** | One module-level `threading.RLock` in `pdfdatei.py`; every public method of `Document` and `Page` (and every direct `pypdfium2.raw` call) runs under it. RLock, because methods call each other (re-entrant) | Small change (one module); matches the official guidance; testable | Serialises all PDF work in a process; slow scanned PDFs (Tesseract) must release the lock between pages, or one big upload blocks everyone's PDF work for minutes | **Now (phase 0, week 1)** |
| B. Process pool for PDF work | `concurrent.futures.ProcessPoolExecutor` (spawn) for `extract()` and other heavy PDF calls | True parallelism; a crash only kills the child process | Memory: each process loads PDFium + layout data; the 2 GB VM limits pool size to 2–3; pickling of results | Optional bridge if A is too slow before phase 2 |
| C. Worker processes (ADR-002) | Jobs run in separate worker processes fed by a Postgres queue; each worker handles one job at a time; the web process does no PDF work | Clean isolation; also fixes deploy interrupts and the global rate limit | Large change | Phase 2 (target) |

**Recommendation** `[advisor proposal]`: A now, C in phase 2. B only if measurements after A show unacceptable queueing.

### Implementation notes for option A
1. `_PDFIUM_LOCK = threading.RLock()` at module level in `pdfdatei.py`.
2. A small decorator or context manager wraps every method that touches `self._pdf`, `self._page` or `_pdfium().raw`.
3. Keep the hold time short: lock per page, not per document, so other threads can interleave between pages.
4. Never call anything that waits on another thread while holding the lock (deadlock risk with `future.result()` in `web.py`).
5. Check modules that import `pypdfium2` directly instead of via `pdfdatei` (`grep -rn "pypdfium2" sci2audio/`) and route them through the wrapper.
6. Text recognition (Tesseract via subprocess) and the layout model (onnxruntime) don't need the lock; only the PDFium calls do.

### Test to add (definition of done)
- `tests/test_pdf_concurrency.py`: 4–8 threads repeatedly extract the test PDFs (and page renders) in parallel, e.g. 50 iterations each; assert identical text to a single-threaded baseline and no crash.
- Run it on Python 3.12 **and** 3.13 (3.13 reproduced the crash; keep it as a canary even though production is 3.12).
- The nightly scheduled task runs this test explicitly.

## 6. Related findings

- **Crash coverage gap:** no test exercised concurrent uploads, so 1,279 green tests on 3.12 would have hidden this. Add concurrency to the test plan for every component that wraps a C library: PDFium, onnxruntime (layout model, Kokoro), Tesseract (subprocess, fine), ffmpeg (subprocess, fine), Azure SDK (thread-safe per client, verify).
- **Python version policy:** production is 3.12, `requires-python >=3.10`, CI matrix 3.10 + 3.12. Proposal: test on 3.12 (production) in CI; add 3.13 to the nightly run as an early warning.
