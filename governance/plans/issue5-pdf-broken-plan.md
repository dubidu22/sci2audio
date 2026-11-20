# Plan: Issue #5, PDF part — extraction golden files and broken PDFs

Thread "Add PDF extraction golden and broken files", 13 Nov 2026. Critical (golden file), lane:extraction, `risk:high`. Waiting for the coordinator's approval before any code or tests.

## 1. Where #5 stands today

Issue #5 asks for (a) syrupy golden files of the extracted structure for each corpus file, (b) a folder of broken PDFs and EPUBs (truncated, wrong encoding, empty, password-protected) that fail with a clear message, not a traceback or hang, (c) a timeout on each extraction test.

- **EPUB part: done in #73** (PR #148, D-315, D-316: EPUB golden, broken EPUBs built by `tests/unit/epub_maker.py`).
- **Markdown and text part: done in #74** (PR #169, D-347, D-348).
- **PDF part: mostly done in #23** (D-65 says #23 "also covers the PDF part of testing issue #5"):
  - golden file `tests/unit/__snapshots__/test_extraction_corpus.ambr` for all 7 corpus papers (outline, metadata title/authors/date, page size, each line with box and styled runs, pictures with boxes, drawings counted);
  - broken set in `test_extraction_pdf.py`: empty, plain text, an EPUB named `.pdf`, first 1,000 bytes, first half, AES-256 user password (`tests/fixtures/broken/password-protected.pdf`), zero pages; Hypothesis: any bytes, damaged bytes, damaged outline → `Content` or a clear `ExtractionError`;
  - every extraction test module has `pytestmark = pytest.mark.timeout(...)` (8 of 8). I checked that the signal method does interrupt a long PDFium call (a 2 s timeout fired at 2.26 s inside a PDFium decode).

So the remaining work is the gaps I found by probing hostile and damaged PDFs against `main` (b8e1e3f), listed next.

## 2. What I measured (main, pypdfium2 5.15.2, PDFium 159.0.8149, Linux, Python 3.12)

| Input (all hand-written, tiny) | File | Today | Problem |
|---|---|---|---|
| Image-only page (a scan without text layer) | 11 KB | `Content`, 0 lines; `sci2audio script` exits 0 and the whole "audiobook" is "A figure is skipped." | No clear message for the most common unreadable PDF |
| Corpus paper (liu) cut to 90 % or 99.9 % | 530 KB | `Content`, 769 of 770 lines, no notice | A cut download loses text silently |
| hardt cut to 75–99.9 % | — | "not a PDF, or the file is damaged" | Clear, but could say "cut short" |
| Page tree of shared nodes (`Kids [A A]` 19 levels) | 2.3 KB | 524,288 pages, **218 s**, 614 MB | Practically a hang |
| 1,000,000 characters on one page (Flate) | 2.8 KB | **32 s, 830 MB** (3 M chars: 90 s, 2.4 GB) | Our `_Char` objects (~800 B per char); PDFium itself only 136 MB, 0.3 s |
| 1,000,000 characters over 100 pages | 16 KB | 23 s, 48 MB | Linear; fine for real books (corpus: ~21 µs per char, densest page 5,835 chars) |
| 1.1 GB of spaces in one Flate stream | 1.1 MB | 13 s, **3.3 GB** inside PDFium | Decompression bomb inside PDFium; cannot be bounded from Python |
| 30,000² Flate image on page 1 | 0.9 MB | extraction 0 s; cover 0.6 s, no extra memory (PDFium downsamples) | fine |
| Unsupported security handler (DRM, certificate `/Adobe.PubSec`) | 0.7 KB | "not a PDF, or the file is damaged" | Wrong message |
| Owner password only, copying and accessibility forbidden | 1.4 KB | read in full | Open legal/product question (q4) |
| `Kids` cycle (a page that can't load) | 0.6 KB | "the PDF is damaged (Failed to load page.)" | Clear-ish; PDFium's English leaks |
| Wrong xref offsets, no xref table, garbage `startxref`, trailing junk, bad MediaBox (0, NaN, missing), `/Rotate 90`, broken Flate content, form XObject nesting 10⁵ | < 1 KB | read (PDFium repairs) | fine; worth pinning |
| Font with unknown glyph names (the PDF form of "wrong encoding") | 0.6 KB | read as the file maps it ("A ✁DE") | Expected: extraction records, never guesses (q10) |

## 3. Proposed change (one PR)

**`src/sci2audio/extraction/pdf.py`** (all checks happen before our per-character Python loop, so they cost nothing on real files):

1. **No text at all → refuse** (q1): when no page has a single text line, `"{name}: the PDF holds no text; a scanned PDF needs text recognition, which sci2audio can't do yet"`. Same idea as D-347 ("the file holds no text") for Markdown and text. A scan with an OCR text layer is read (invisible text, render mode 3, counts as text).
2. **Limits → "too large or damaged"** (q2), message as D-315 for EPUB: `MAX_PAGES = 10_000` (checked with `len(document)` before reading, 1 ms even for 524,288 pages); `MAX_PAGE_CHARS = 100_000` per page and `MAX_CHARS = 10_000_000` per file, checked with PDFium's `count_chars()` before building our objects. Message: `"{name}: the PDF is too large or damaged (more than 10,000 pages)"`, `"(page 7 holds more than 100,000 characters)"`, `"(more than 10,000,000 characters)"`. Peak memory per page stays under about 90 MB; the worst file takes about 3.5 minutes instead of unbounded.
3. **Cut-short files → refuse** (q3): a file that starts like a PDF, has no `%%EOF` in its last 1,024 bytes and whose cross-reference table PDFium had to rebuild (`FPDF_DocumentHasValidCrossReferenceTable` = 0), or that PDFium can't open at all, gets `"{name}: the PDF is cut short (an unfinished download?); download it again"`. Checked: all 7 corpus papers have a valid xref and `%%EOF` at the end; a file with only bad xref offsets keeps its `%%EOF` and is still read; trailing junk after a valid file is still read.
4. **DRM or certificate protection → its own message** (q5): PDFium's "Unsupported security scheme" with `/Encrypt` in the file gives `"{name}: the PDF is protected by DRM or a certificate; sci2audio can read only PDFs without it"` (EPUB wording, D-315).
5. **Owner-password permissions** (q4, recommended option): refuse only when the file forbids **both** copying text and accessibility extraction (`FPDF_GetDocPermissions`, bits 5 and 10, security handler revision ≥ 3): `"{name}: the PDF's owner does not allow its text to be read out; ask for a copy without this restriction"`. Files that allow either are read, as now.
6. **A page PDFium can't load** (q6): still fails the whole file, but the message names the page instead of PDFium's text: `"{name}: the PDF is damaged (page 3 cannot be read)"`.

**Tests** (fast suite, no new markers):

- New module `tests/unit/test_extraction_pdf_broken.py` holding the whole broken set, each case one `pytest.param` with its expected message: the existing seven cases move there unchanged (move-only commit first), plus: no text (scan image, blank pages, text drawn as paths), OCR layer is read, page-tree bomb (16,384 pages via shared nodes, fails before reading), too many chars on one page, too many chars in all (limit monkeypatched small, plus one test pinning the three decided values), cut short (liu at 90 % and 99.9 %; hardt at 75 %), trailing junk read, bad xref read, DRM handler, certificate handler, owner forbids both, owner forbids copying only (read), unloadable page, bad MediaBox read, broken content stream read, unknown glyph names read; Hypothesis: random page trees from the raw writer → `Content` or a clear error within the timeout.
- `tests/unit/pdf_maker.py` gains `raw_pdf(objects, ...)`, a ~30-line writer of hand-written PDF objects with a correct xref, because pypdfium2 can't write malformed files.
- One stored fixture: `tests/fixtures/broken/owner-no-copy.pdf` (blank page, owner password only, copying and accessibility forbidden, ~1.4 KB, our own work, CC0-1.0, made once with pikepdf like the existing password file; row in `tests/fixtures/README.md`). pikepdf stays out of the dependencies.
- Golden file (q7, recommended): the metadata line gains `language=`, and each drawing gets its own line with its box, as pictures do. Diff: +2,604 lines (chi 1,863, liu 449, others 40–95), ~110 KB on a 595 KB file; nothing else in it changes.
- Guard test (q11): every `tests/unit/test_extraction_*.py` sets a `pytest.mark.timeout`, so a future module can't drop the criterion.
- App check: I'll grep app/web/CLI tests for image-only `make_pdf(...)` inputs that would now fail (none found yet; any I find gets fixed in the same PR with the reason).

**Runtime cost in CI**: the new tests build files of under 20 KB; measured cost about 1–2 s per system; the golden test stays ~5 s. Nothing goes to `slow` or nightly.

**Out of scope, as new issues** (q8–q10): PDFium decompression bombs (needs extraction in a child process with a memory limit; v1.1), a report warning for partly scanned PDFs listing pages without text (app lane; v1.1 recommended), a warning when a PDF's text looks garbled from broken font encodings (v1.1).

## 4. Alternatives weighed

- **Defer the limits to #174/v1.1 as D-377 did for Markdown/text/EPUB.** Not recommended for PDF: there the file size bounds the cost; here a 2–3 KB file costs minutes or gigabytes, and the checks are a few lines run before our loop.
- **Read a cut-short or partly unloadable file and warn.** Better for the user in theory, but `Content` has no warnings field; adding one is a core change (separate critical PR). Refusing keeps "text is never dropped silently".
- **Store real broken PDFs from the web.** Refused: third-party content and licence trouble; every case here is hand-written or built in the test.
- **pikepdf as a test dependency** (MPL-2.0, allowed) to build encrypted files in tests. Not needed for one file; stays a one-off tool as in #23.
- **Golden with run boxes too.** +12,600 lines for little: line boxes and run text already catch extraction changes.

## 5. Questions

1. **Scanned PDFs (no text on any page):** refuse with the message in 3.1 (recommended), or read and leave it to the app?
2. **Limits now:** `MAX_PAGES = 10,000`, `MAX_PAGE_CHARS = 100,000`, `MAX_CHARS = 10,000,000`, message "too large or damaged (…)" (recommended), or other numbers, or defer to #174 like D-377?
3. **Cut-short files:** refuse when the file lacks `%%EOF` in its last 1,024 bytes and PDFium rebuilt or couldn't read the xref (recommended), or read what PDFium recovers?
4. **Owner-password restrictions:** refuse only when both copying and accessibility are forbidden (recommended; matches the KB's "DRM rejected, no circumvention (§ 95a UrhG)"), always read (today), or refuse whenever copying is forbidden?
5. **DRM or certificate encryption:** the new message in 3.4 (recommended)?
6. **A page PDFium can't load:** keep failing the whole file with the page named (recommended), or skip the page?
7. **Golden file:** add `language` and drawing boxes (recommended), `language` only, or leave it unchanged?
8. **PDFium decompression bombs:** new issue, v1.1 (recommended), or v1.0?
9. **Partly scanned PDFs:** new app-lane issue for a report warning, v1.1 (recommended) or v1.0?
10. **Garbled text from broken font encodings:** read as stored, never fail; new issue for a warning, v1.1 (recommended)?
11. **Timeout guard test** for every extraction module (recommended)?
12. **Issue #5's text:** I update it when the PR opens, to say the EPUB and Markdown/text parts were done in #73 and #74 and this PR closes the PDF part (recommended)?
