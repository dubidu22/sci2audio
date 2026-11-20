# Plan: read PDFs in a separate process with memory and time limits (#185, #28)

Thread "Make PDF layout more robust for v1.2", 14 Nov 2026. Lane: extraction. Base: main 334e5a8. Third in the lane order (D-572). Requested by the coordinator after PR #327 went to review.

**Critical: yes.** It changes how the extraction stage runs: a child process per PDF read, and a `freeze_support()` call in the CLI entry point for packaged builds. No change to the `lint-imports` layers (stdlib only), no core dataclass changes, no golden file changes (corpus output identical, checked in the PR). It waits for approval.

## 1. Measured facts (main 334e5a8, pypdfium2 5.15.2, Python 3.12.3, Linux, 4 cores; peak RSS growth of one process)

**Real reads in one process:**

| Input | Pages, characters | Read | Peak growth | Pickled result |
|---|---|---|---|---|
| corpus, 8 papers | 4 to 28 pages | 0.24 to 1.57 s (56 to 71 ms a page) | +6 to +11 MB | 0.1 to 0.6 MB, under 0.01 s each way |
| a made-up book, 400 pages × 3,000 characters | 1.2 M | 20.9 s | +21 MB | 5.0 MB, 0.10 s / 0.08 s |
| the same, 1,000 pages | 3.6 M | 66.1 s | +59 MB | 14.9 MB, 0.43 s / 0.33 s |
| 2,000 pages × 5,000 characters (refused at `MAX_CHARS`, D-394) | 10 M | 189 s | +169 MB | |
| densest page that the limits allow (90,000 characters) | | 2.0 s | | |

**#28, the lock:** `_PDFIUM` is held for the whole of `read_pdf`. Every other PDF read waits 21 s behind a 400-page book and 66 s behind a 1,000-page book.

**The same reads in a child process (prototype, `multiprocessing` spawn, result pickled over a pipe):**
- Starting the child and importing pypdfium2 and the extraction module takes 0.07 to 0.12 s. The child starts at 28 MB RSS and 41 MB of address space (VSZ).
- hardt takes 0.61 to 0.75 s in the child against 0.44 s in one process, so the extra cost is about 0.2 s per read.
- With a watchdog thread in the child, the address space rises to 113 MB (thread stack and malloc arena).

**Hostile files (from #185 and its review comment), with a 1 GB limit in the child:**

| File | Size | In one process (#185) | In the child |
|---|---|---|---|
| one page, 500 MB of spaces, Flate | 0.5 MB | 1.5 s, 1.5 GB | reads (PDFium stays under 1 GB RSS here) |
| one page, 1.1 GB of spaces, Flate | 1.1 MB | 13 s, 3.3 GB | watchdog: stopped at 1 GB after 0.9 s. With an `RLIMIT_AS` of 1 GB, PDFium aborts the child (SIGABRT). In both cases the parent stays at 14 MB |
| 1,000,000 filled 1 × 1 rectangles, Flate | 2.4 MB | 13 s, 861 MB | **the child reads it under 1 GB in 21 s, and then the parent grows to 1,041 MB unpickling 1,000,000 `Drawing`s** |
| forms nested 7 deep, ×10 each (#185 comment) | 4 KB | 19.5 s, 1.96 GB, of which 1.58 GB at page load | stopped by the memory limit (page load is over 1 GB) |

So a memory limit on the child does not bound what comes back. The result needs its own limit, like D-394 for characters (Q5).

**Page objects in the corpus:** the most on one page is 1,836 drawings (chi, a chart) and 4 pictures (hardt). The most in one paper is 1,863 drawings and 8 pictures.

**JSON instead of pickle** (`core.export`, no unpickling of the child's output): the 400-page book is 6.6 MB of JSON. Writing it takes 0.64 s, and reading it back takes 5.28 s (`from_data`), against 0.08 s for pickle.

## 2. Decisions (with recommendations)

**Q1. Where does the child run?**
- (a) **Recommended: inside extraction.** `extract_pdf(path)` and `extract_pdf_cover(path)` each read the file in a child process, through a small new module `extraction/isolate.py`. Every caller is then guarded: the job, the CLI and the web document page. `read_pdf(data, name)` stays in-process: it is the child's own body and is used by tests. Its docstring will say it is not guarded and that files from users go through `extract_pdf`.
- (b) In `app`, wrapping `EXTRACTORS`. That guards jobs only, and puts a PDF-specific concern into the job runner.
- (c) A long-lived worker process or pool. It saves about 0.1 s per read, but state, a leak or a half-crashed PDFium would carry over from one user file to the next.

**Q2. How the child is started and how its result comes back.**
- (a) **Recommended: `multiprocessing` with the "spawn" start method on all three systems, and the result pickled over a one-way pipe.** Spawn is the only method that is safe from the web server's threads and behaves the same everywhere. Pickle is 60 times faster than JSON for a book. The parent unpickles only its own child's output. If PDFium were exploited in the child, the attacker would already run code as the same user, so unpickling adds no access.
- (b) JSON through `core.export`. It costs 5 s for 400 pages until `from_data` gets faster.
- (c) `subprocess` with `python -c`. It does not work in a frozen (installer) build without a second entry point.

**Q3. The memory limit: 1 GB per child (recommended).** Alternatives: 512 MB or 2 GB.
- A read at `MAX_CHARS` needs about 200 MB. The corpus needs under 40 MB, and the 1,000-page book under 90 MB, so 1 GB is about 5 times the largest legitimate read.
- 512 MB would still pass every legitimate case measured, with less headroom for heavy vector pages.
- 2 GB lets the 1.1 GB Flate bomb through at about 3 GB; "most laptops" have 8 GB.
- The limit applies to each child, so two jobs at once use at most 2 GB.

**Q4. How memory is measured and enforced on each system (the Windows question).**
- (a) **Recommended: one watchdog thread in the child on all three systems, plus the system's own hard limit at twice the limit where there is one.**
  - **The watchdog.** It reads the child's peak memory every 20 ms and exits with a code the parent turns into the memory message:
    - Linux: `getrusage` peak RSS, in KB.
    - macOS: `getrusage` peak RSS, in bytes.
    - Windows: `PeakPagefileUsage` from `K32GetProcessMemoryInfo` through ctypes. That is committed private memory, which is what Windows charges.
  - **Hard limits, as backstop.** They catch an allocation that grows faster than the 20 ms polling:
    - Linux: `RLIMIT_AS`.
    - Windows: a job object with `JOB_OBJECT_LIMIT_PROCESS_MEMORY`. The child creates it and assigns itself; nested jobs work on Windows 8 and later, and Python 3.12 needs 8.1. No parent-side handle or suspended start is needed.
    - macOS: none, because macOS does not enforce `RLIMIT_AS`. I will confirm that on the CI runner in the PR.
  - When a hard limit trips, PDFium aborts the child, and the parent reports the "stopped" message.
- (b) Watchdog only. This is simpler, but nothing catches a very fast single allocation. The overshoot is bounded by how fast memory can be written in 20 ms, about 200 MB.
- (c) Hard limits only. This leaves macOS unguarded, and `RLIMIT_AS` counts reserved address space as well as used memory. The watchdog thread alone raised the child's address space from 41 to 113 MB and made the 500 MB Flate file abort under a 1 GB `RLIMIT_AS`, so a hard limit at the exact number would refuse files that fit.

**Q5. A limit on page objects, so the result stays small (#185 review comment).**
- (a) **Recommended: refuse the file over 100,000 drawings and pictures on one page, or over 500,000 in the whole file**, with the D-394 message style. These are counted while the page's objects are walked, so the walk stops there. The corpus maximum is 1,836 per page, which leaves 50 times headroom. At the limits the result is at most about 430 MB of `Drawing`s, and in practice far less.
- (b) Keep the first 100,000 on a page and drop the rest. The text would still be read, but layout would silently lose rules, tables and figure areas on that page, so labels inside a chart could be read as body text. That goes against D-63 (extraction decides nothing).
- (c) No count, memory limit only. That leaves the parent's 1 GB unpickle measured above.

**Q6. The time limit: 60 s for each step, with no limit for the whole file (recommended).**
- The steps are: open and checks, then each page, then the outline and metadata. The child sends a short message after each one, and the parent kills the child if no message comes within the step limit.
- The densest page the limits allow takes 2.0 s, and an ordinary page about 66 ms, so 60 s is 30 times the worst legitimate page.
- A total limit would refuse long legitimate files: 1,000 pages take 66 s, and `MAX_PAGES` (10,000) allows ten times that.
- Alternatives: 30 s a step, or a total of 10 minutes.

**Q7. Messages.** Each is an `ExtractionError`, in the D-394 style. An error that the child itself raises (cut short, locked, no text, …) reaches the user unchanged.
- Memory: "NAME: the PDF is too large or damaged (reading it needs more than 1 GB of memory)".
- Time: "NAME: the PDF is too large or damaged (page N took more than 60 seconds to read)". Before the first page, it says "opening it took more than 60 seconds".
- Page objects: "NAME: the PDF is too large or damaged (page N holds more than 100,000 drawings and pictures)", or "(more than 500,000 drawings and pictures)" for the whole file.
- Crash, including a hard-limit abort: "NAME: the PDF is damaged (the PDF reader stopped unexpectedly)". This is new and good: a PDFium crash on a malformed file no longer takes the app down with it.
- Child cannot start: "NAME: cannot be read: sci2audio could not start its PDF reader (DETAIL)". I recommend no silent fallback to an in-process read, because that would hide the unguarded path.
- For the cover, any of these gives no cover (None), as today (D-313).

**Q8. #28 is closed by this (recommended).**
- The parent no longer calls PDFium for user files. Each read has its own process, so two jobs, or a job and a preview, read at the same time.
- `_PDFIUM` stays, for in-process `read_pdf` and inside the child, where it costs nothing.
- The alternative from #28, taking the lock per page, is no longer needed.

**Q9. Packaging.**
- Spawn starts the program again for the child, so `cli.main` calls `multiprocessing.freeze_support()` first. It does nothing today and makes the v1.3 installer builds work (#215).
- The child is a daemon. If the parent goes away, the child ends at its next message (after a page) or at its step limit.
- I will measure the start cost on Windows and macOS on the PR's CI runners and add a row to `docs/baseline.md`.

## 3. Changes

- `extraction/isolate.py` (new, about 120 lines). `run(target, args, *, memory, step_seconds) -> result` does the spawn, the pipe, the progress messages, the watchdog and the hard limits for each system, and returns a small `Stopped(kind, step)` result on failure. It uses only the stdlib, plus ctypes on Windows.
- `extraction/pdf.py`:
  - `extract_pdf` and `extract_pdf_cover` go through `isolate.run`.
  - `_pages(document, name, progress=None)` reports each page.
  - `_graphics` / `_walk` count drawings and pictures and stop at the limits.
  - New constants: `MAX_MEMORY` (1 GB), `STEP_SECONDS` (60), `MAX_PAGE_GRAPHICS` (100,000) and `MAX_GRAPHICS` (500,000).
- `cli.py`: `multiprocessing.freeze_support()` at the start of `main`.
- `docs/baseline.md`: extraction time for arsiwalla in-process and in the child, on all three systems.

## 4. Tests (written first; each one marked "fails on main" fails there)

1. **Flate bomb (#185 acceptance)** (fails on main).
   - The 1.1 GB-of-spaces page (1.1 MB, written by `pdf_maker`) fails with the memory message on all three systems.
   - The parent's own peak growth stays under 50 MB. It is measured in a fresh interpreter, because pytest's own peak would hide growth. The peak comes from the same function the watchdog uses.
   - It takes about 1 s, so it stays in the fast suite.
2. **Page-object bombs** (fails on main). Each fails with the page-object message, both in the child and in-process with patched limits, which is fast:
   - 100,001 rectangles in one compressed stream;
   - forms nested 7 deep, which fails with the memory or the page-object message;
   - 100,001 uses of one picture.

   The existing 5-level form test (10⁵ letters) still reads.
3. **Time** (fails on main). A 90,000-character page with the step limit lowered to 0.5 s (limits are passed to the child as arguments) fails with the page time message.
4. **Crash** (fails on main). `isolate.run` with a test target that calls `os.abort()` gives the "stopped unexpectedly" message.
5. **Watchdog and hard limits.**
   - A target that allocates and touches 300 MB under a 100 MB limit stops with the memory result, on all three systems.
   - On Linux and Windows, a single allocation of three times the limit, touched faster than the polling, is stopped as well.
6. **#28** (fails on main).
   - Two threads read at once: a 3-page dense file (about 6 s) and hardt (about 0.6 s). hardt finishes first, well before the long read.
   - The existing `test_threads_reading_at_once_do_not_crash` still passes.
7. **Corpus.**
   - `extract_pdf(path) == read_pdf(bytes)` for all 8 papers, on all three systems.
   - The extraction and layout snapshots are unchanged, and the PDF covers are unchanged.
8. **Broken files.** Every case in `test_extraction_pdf_broken.py` and `test_web_refused_pdfs.py` keeps its message.
9. **Cost of the fast suite.** About 90 test reads go through `extract_pdf`, at about 0.2 s more each, so about 20 s of CPU in total. If that is too much, the corpus fixtures will read once per module. The PR reports the measured number.

## 5. PR split

One PR, "extraction: read PDFs in a separate process with memory and time limits (#185, #28)", `risk:high`, about 200 lines of code plus tests.

A natural split would put the page-object limit (Q5) first on its own, since it is in-process and small, and the child process second. I recommend one PR, because the Q5 numbers only make sense next to the memory limit.

## 6. Out of scope

- Page progress in the web interface: the child already reports pages, but showing them is app-lane work. I will file an issue when the PR opens.
- Killing the child from a cancel button. The job runner has no cancel during extraction today. I will file an issue if one is wanted.
- EPUB, Markdown and text stay in-process. They are bounded by PR #327, and their parsers are pure Python.
- `MAX_CHARS`, `MAX_PAGES` and `MAX_PAGE_CHARS` (D-394) are unchanged.
