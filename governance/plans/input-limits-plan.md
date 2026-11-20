# Plan: input size limits for text, Markdown, EPUB and covers (#174, #158, #165; #298 rides along)

Thread "Make PDF layout more robust for v1.2", 14 Nov 2026. Lane: extraction. Base: main aec6e6a. Picked by the coordinator as D-572 (second after #202). The limit numbers are decisions; the coordinator approves them before code.

**Critical: no.** No golden file changes (every corpus sample is far below every limit, checked), no core dataclass, no layer contract. Extraction only, plus tests. It adds new broken-file tests.

## 1. Measured facts (main aec6e6a, Python 3.12.3, Linux; CPU time and peak RSS growth of one process; the reader alone, then `build_document`)

| Input | Size | Lines / runs | Read | Peak | Layout after it |
|---|---|---|---|---|---|
| text, `"w\n"` × 200,000 | 0.4 MB | 200,000 lines | 0.9 s | +86 MB | 1.6 s, +168 MB |
| text, `"w\n"` × 1,000,000 | 2.0 MB | 1,000,000 | 4.8 s | +425 MB | 10.9 s, +820 MB |
| text, a hard-wrapped book (70-char lines, blank line every 8) | 12.3 MB | 175,000 | 0.9 s | +120 MB | 1.9 s, +205 MB |
| Markdown, `"w\n\n"` × 100,000 | 0.3 MB | 100,000 paragraphs | 4.8 s | +196 MB | 1.3 s |
| Markdown, `"w\n\n"` × 400,000 | 1.2 MB | 400,000 | 20.4 s | +792 MB | 5.9 s |
| Markdown, a hard-wrapped book | 12.3 MB | 25,000 paragraphs | 4.7 s | +213 MB | 0.4 s |
| **Markdown, one line `"*a* "` × 200,000** | 0.8 MB | 400,000 runs | 7.9 s | **+375 MB** | |
| Markdown, one line `` "`a` " `` × 200,000 | 0.8 MB | 400,000 runs | 5.4 s | +266 MB | |
| Markdown, one line `"word "` × 1,000,000 | 5.0 MB | 1 run | 0.6 s | +83 MB | |
| EPUB, one chapter `<p>a</p>` × 200,000 | 1.6 MB XHTML | 200,000 lines | 3.5 s | +105 MB | |
| EPUB, `<p>` + `<i>a</i>` × 200,000 | 1.6 MB | 1 line, 1 run (merged) | 3.2 s | +61 MB | |
| EPUB, the same in a `<p>` with 197 `epub:type` tokens | 1.6 MB | 1 line, 1 run | 3.9 s | **+369 MB** | |

So, per item: text about 425 B and 5 µs per line; Markdown about 2 KB and 50 µs per paragraph (most of it in markdown-it's tokens, before our reader); EPUB about 525 B and 17 µs per line. Everything is linear, but the 64 MB file limit (D-351, `MAX_TEXT`) and the 64 MB EPUB member limit (`MAX_MEMBER`, D-315) allow inputs that need about 14 GB (text), 45 GB (Markdown paragraphs), **30 GB (Markdown inline markup, a case #174 does not name)** and 15 GB (EPUB tags near `MAX_TAGS`).

**New finding:** the line count does not bound Markdown. One line of inline markup ("*a* " repeated) costs about 470 times its size, because markdown-it makes 3 tokens per emphasis and our reader one run per style change. A limit on source lines alone would still let a 64 MB one-line file need about 30 GB.

**Real books, for the numbers** (measured where we have them; estimates marked):
- Corpus EPUB *The Time Machine*: 182,385 characters, 18 chapters, 368 lines, 460 runs (828 items), 1,189 `<` in its XHTML, at most 79 lines in one chapter.
- Our own Markdown (README, CHANGELOG, CONTRIBUTING, docs/, the two corpus notes; 12 files, 67,000 characters): 13 inline marks (`*_`[<$!\&`) per 1,000 characters, 89 characters per line.
- Estimates (not measured, no third-party text fetched): the King James Bible is about 4.3 M characters and 31,000 verses; Project Gutenberg's *Complete Works of Shakespeare* is about 5.5 M characters and about 170,000 hard-wrapped lines; *War and Peace* in English about 3.2 M characters and 66,000 hard-wrapped lines. A 10 M character book is about 300 hours of audio, the size the PDF limit already allows (`MAX_CHARS`, D-394).

Cover (#165, measured in the issue on Linux with the bundled ffmpeg): 10,000 × 10,000 8-bit RGB (0.29 MB file) costs ffmpeg 1 s and 321 MB per run that opens it; 16,000 × 16,000 16-bit RGBA (1.99 MB) costs 6.2 s and 1,989 MB; 20,000 × 20,000 is refused by ffmpeg. Store guidance for covers: about 1,400 to 2,560 px on the long side; 10,000 px is the largest any store asks for (estimate).

## 2. Decisions (with recommendations)

**Q1. What is counted, and when?**
(a) **Recommended: count before the expensive parse, plus a budget while reading.** Text and Markdown: count the line ends of the decoded text before splitting or parsing (one `str.count`, no allocation). Markdown also counts its inline marks before markdown-it runs. EPUB and Markdown: `PageReader` (the HTML reader both use) counts the items it makes, lines + runs + pictures, over the whole book and stops at the limit. `HTMLParser` itself streams and builds no tree, so our items are the memory.
(b) Count only what the readers make. Simpler, but markdown-it's tokens (most of the Markdown cost) are made before our reader sees anything.
(c) Count `<` in each EPUB chapter before reading. Cheap, but MathML or SVG chapters hold many tags for little text, so a real science book could be refused.

**Q2. The limits** (one constant each, in `extraction`, named in the message):

| Limit | Applies to | Recommended | Alternatives | Real-book headroom | Worst case at the limit (measured rates) |
|---|---|---|---|---|---|
| `MAX_LINES` source lines | text, Markdown | **500,000** | 250,000 / 1,000,000 | about 3 × Shakespeare's 170,000 lines (estimate) | text: 2.4 s, about 210 MB, then layout about 5 s, about 410 MB. Markdown (250,000 paragraphs with blank lines): about 12 s, about 500 MB |
| `MAX_MARKS` inline marks `* _ ` [ < $ ! \ &` | Markdown | **1,000,000** | 500,000 / 2,000,000 | 15 × a 5 M character book at our density (65,000 marks) | about 20 s, about 950 MB (the "*a*" row × 2.5) |
| `MAX_ITEMS` lines + runs + pictures read | EPUB (whole book), Markdown | **1,000,000** | 500,000 / 2,000,000 | about 1,200 × The Time Machine; about 10 × a verse-per-paragraph Bible (estimate) | EPUB: 500,000 lines, about 9 s, about 260 MB, then layout about 5 s, about 410 MB |
| cover pixels | EPUB cover | **25 megapixels and at most 10,000 px a side** | 40 MP / 100 MP | 4 × the largest store size (2,560 × 1,600 = 4.1 MP) | 16-bit RGBA at 25 MP: about 200 MB in ffmpeg; 8-bit RGB about 75 MB |

`MAX_TEXT` (64 MB) and the EPUB byte limits stay. The PDF limits (D-394) are untouched.

**Q3. Tag tuples (#158 row 3): intern them.** `PageReader` keeps one tuple per distinct tag list, so 200,000 children of one tagged parent share one 200-tag tuple instead of each holding a copy. Recommended in addition to `MAX_ITEMS`: it fixes the 369 MB row at any size, and the tags stay exactly as today, so no golden changes. `MAX_TAGS` (200) stays.

**Q4. Messages.** Same style as today:
- text/Markdown lines: "NAME: the file is too large; sci2audio reads text files of up to 500,000 lines" (as the 64 MB message, D-347);
- Markdown marks: "NAME: the Markdown holds too much markup to read (more than 1,000,000 marks such as * _ ` [ <)";
- EPUB items: "NAME: the EPUB is too large or damaged (more than 1,000,000 pieces of text)" (the D-315 message with its detail in brackets, as the PDF limits do, D-394).
All are `ExtractionError`, raised before more is read, so the web and the CLI show them as they show today's.

**Q5. A cover over the pixel limit is no cover** (None), like a cover over 20 MB today (D-313). A missing cover never stops a job. The size comes from the PNG IHDR or the JPEG SOF header (stdlib `struct`, in `extraction/cover.py`). A JPEG whose header cannot be read gives no cover: ffmpeg could not decode it either. Recommend. No image library (#134 stays as it is).

**Q6. #298 rides along**: both timing tests move onto `tests/unit/linear_time.py` (`assert_linear`, CPU time, 8 × the base input). The input sizes are kept and stay below the new limits (100,000 text lines; the Markdown cases at N = 20,000). For each converted case, the PR shows the ratio, and shows that a quadratic slow version of the reader fails the test.

## 3. Changes

- `extraction/text.py`: `MAX_LINES`; `decode_text` callers check `decoded.text.count("\n")` (plus lone `\r`) for text and Markdown before splitting or parsing.
- `extraction/markdown.py`: `MAX_MARKS` counted on the decoded text before `parser.parse`; the reader gets the item budget.
- `extraction/markup.py`: `PageReader` takes a shared budget (`Budget(limit)`, counted in `flush` and `picture`) and raises a small internal error that `epub.py` and `markdown.py` turn into the messages above. Tag tuples are interned in the reader (`dict.setdefault`).
- `extraction/epub.py`: one budget for the whole book (`_Book.pages`), message as in Q4.
- `extraction/cover.py`: `pixel_size(data) -> tuple[int, int] | None` from IHDR / SOF0–SOF15 (except C4, C8, CC); `MAX_COVER_PIXELS`, `MAX_COVER_SIDE`; `extract_epub_cover` gives None above them.

## 4. Tests (written first; each fails on main)

1. Broken-file tests, one per format, at the real limits, with `tracemalloc` peak and time bounds like `test_many_tokens_on_many_elements_stay_small_and_fast`:
   - text of 500,001 short lines fails with the lines message. It is refused before splitting: peak below 20 MB, and the input itself is 1 MB.
   - Markdown of 500,001 lines, and Markdown of one line with 1,000,001 marks, each fail before markdown-it runs (peak below 20 MB).
   - an EPUB whose chapters make 1,000,001 items fails with the EPUB message. This one has to read up to the limit, so it is marked `slow`. A fast twin patches `MAX_ITEMS` to 1,000 and checks that the budget counts across chapters and pictures.
   - exactly at each limit, the file still reads (fast twins with patched limits for EPUB).
2. Tag interning: the 197-token row of #158 at 200,000 children stays under 100 MB peak (369 MB on main), and the tags are unchanged (`runs[0].tags` as today).
3. Cover: made-up PNGs (IHDR only plus a tiny IDAT) of 10,001 × 100 and 6,000 × 5,000 give no cover; 2,560 × 1,600 gives one. The same for a JPEG with a baseline SOF0 and with a progressive SOF2. A truncated JPEG gives no cover. These are header-only test images built in the test, so no file is added to the repo and no ffmpeg run is needed.
4. Hypothesis: the existing reader properties (any bytes: Content or ExtractionError, never another error) keep passing. With the limits patched low, any input either reads or fails with one of the Q4 messages.
5. #298: the two converted tests, as in Q6.
6. Corpus: every sample still reads, and the extraction golden files are unchanged (checked: The Time Machine has 828 items, the notes and texts have under 30 lines).

## 5. PR split

One PR, "extraction: refuse text, Markdown and EPUB files too large to read safely, and huge covers (#174, #158, #165)", with #298's test change in the same PR (same test files). It touches only extraction and its tests. Size: about 150 lines of code plus tests. Possible natural split if the reviewer prefers: the cover (#165) on its own.

## 6. Out of scope

- PDF stays with #185 and #28 (the child process), next in this lane.
- `MAX_TEXT` (64 MB) is unchanged; lowering it is not needed once lines, marks and items are bounded.
- Warning the user before a long job (the time estimate) is unchanged.
