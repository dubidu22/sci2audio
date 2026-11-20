# Review of PR #188, round 1 (issue #5, PDF part)

Reviewed head `4a8b84d` (4 commits on `b8e1e3f`), 13 Nov 2026. Critical (golden file, `risk:high`). Plan: `plans/issue5-pdf-broken-plan.md`, decisions D-393 to D-404.

**Verdict: changes needed. 1 must-fix, 4 should-fix.** Everything else checked out (list at the end).

## Must-fix

**M1. A whole, valid PDF followed by 4 KB or more of trailing bytes is now refused as "cut short".** Main reads these files in full.

Measured on all 7 corpus papers: the paper plus 1,024, 2,048, 3,000 or 4,000 zero bytes is read in full; plus 4,096, 4,200, 5,000, 10,000, 100,000 or 1,000,000 zero bytes, or plus 5 KB of HTML, is refused with "the PDF is cut short (an unfinished download?); download it again". On main (`b8e1e3f`) every one of these files reads the same lines as the paper alone (chi 1,335, hardt 602, nowak 1,062, arsiwalla 1,091, liu 770, seaborn 215, pymedphys 211).

The cause: PDFium looks for `startxref` only in the last 4,096 bytes, so with more trailing bytes `FPDF_DocumentHasValidCrossReferenceTable` returns 0 (PDFium rebuilds the table and the file reads fine). The %%EOF is then also outside the last 1,024 bytes, so both halves of the D-395 test fire. The test `junk-after-the-end` adds 2,048 bytes, which is inside PDFium's window, so it doesn't catch this. That breaks D-395's own promise: "trailing junk after a valid file is still read". Files with bytes after %%EOF do turn up: padded files, a web page appended by a server, and files from tools that write trailing data.

Fix wanted (the mechanics are yours, but the rule must cover both):
- Decide "cut short" from the file's structure, not only from the last 1,024 bytes. For example, look at the last `%%EOF` anywhere in the file: there is none, or object data (`<n> <g> obj`) follows it. A whole file with trailing junk has its last %%EOF followed by no object. A cut file has none, or its last %%EOF belongs to an earlier section (linearized first page, earlier revision) and objects follow it.
- Tests: each corpus paper plus 4,096 B, 10 KB and 1 MB of zero bytes, and plus a few KB of HTML, reads the same lines as the paper alone. The existing cut cases are still refused. Keep the search cheap: one `rfind` over the bytes, no per-object Python loop.
- This changes how D-395 is applied, so say in the PR body exactly what the rule now is. The coordinator records it in the KB.

For your check after the fix, my cut sweep on the PR head found no silent loss, and it must stay that way. It cut each of the 7 papers, plus a linearized copy and an object-stream copy of each (made with pikepdf 10.18.1), at 5, 10, 25, 50, 60, 75, 90, 95, 99, 99.5 and 99.9 % and at 1, 3, 6, 7, 8, 20, 100, 500, 1,000, 1,023, 1,024, 1,025, 1,100, 2,000 and 4,000 bytes short of the end. Of the 546 cut files, none was read partly. Each was either refused as "cut short" or, when the cut took only bytes after the content (such as the line end after %%EOF), read in full.

## Should-fix

**S1. A file with an incremental update, cut inside that update, is read without a word as the earlier revision.** I saved each corpus paper with one added page through PDFium's incremental save (`FPDF_INCREMENTAL`, about 600 bytes appended), then cut it 50 bytes after the original end, in the middle of the update, and 30 bytes short of the end. For 6 of 7 papers this reads the earlier revision with one page fewer, and nothing says so. The original's `%%EOF` sits inside the last 1,024 bytes, and PDFium finds the original's `startxref`, so the xref counts as valid. pymedphys, with a 63 KB update, is refused except at the 50-byte cut.

If your M1 rule is "objects follow the last %%EOF", these files are caught too, provided that test does not also require PDFium to have rebuilt the xref. Check that the corpus and the incremental-save variants still read. If you keep the xref condition, file a v1.1 issue for this case with these measurements instead.

**S2. Page-object bombs: add them to #185, with no code change in this PR.** Measured on the PR head:
- one page with 1,000,000 filled 1×1 rectangles in a 26 KB Flate stream: 13.0 s, 861 MB, and 1,000,000 `Drawing`s (PDFium alone: 1.6 s, 362 MB);
- a 4 KB file of forms nested 7 deep, each drawing the next 10 times: 1,000,000 drawings, 19.5 s, 1.96 GB (PDFium alone at page load: 5.9 s, 1.58 GB). An 8th level would be ten times that.
- 200,000 uses of one 2×2 image: 2.4 s, 167 MB, so pictures are the same pattern.

Most of the memory goes into PDFium while it loads the page, before any of our code can count, so a limit in pdf.py can't bound it. Like the Flate bomb, it needs the child process of #185. Please add these cases and numbers to #185 (issue comment or body edit), so its acceptance test covers page loading as well as stream decoding.

**S3. Wrong claim about qpdf in `owner_locked_pdf`'s docstring.** It says "pikepdf and qpdf always allow accessibility from revision 3 on". With pikepdf 10.18.1, `Encryption(R=3, aes=False, metadata=False, allow=Permissions(extract=False, accessibility=False))` writes `/P 0xfffff9ec`, with bit 10 clear. It is from revision 4 on (AES) that qpdf forces bit 10 on: R4 and R6 give `0xfffffbec`. Writing the files in the tests is still right, because it keeps pikepdf out and covers revision 2. Fix the sentence, and mention it in your fix list.

**S4. The character limits aren't pinned at their boundary.** `test_a_page_over_the_character_limit_is_refused_before_it_is_read` uses limit 1,100 with 1,000 and 1,200 characters. `test_too_many_characters_in_all_...` uses 2,500 with roughly 2,400 and 3,600. So turning `count > MAX_PAGE_CHARS` or `total > MAX_CHARS` into `>=` passes every test. Add one case at exactly the limit, read, and one at the limit plus 1, refused, for each. Take the count from `count_chars()` of the made file, because PDFium counts the line ends it adds. The page limit is already pinned this way (2 pages read, 3 refused).

## The three deviations: all accepted

1. **No stored fixture; owner-locked PDFs (RC4, revisions 2 and 3) written in the tests.** Right. I checked the files independently. PDFium opens them without a password and reports the intended `/P`. pikepdf-made copies of a corpus paper with copying and accessibility both forbidden (R2 and R3 RC4) are refused with the owner message. Copies with copying forbidden but accessibility allowed (R3 RC4, R4 AES-128, R6 AES-256) are read in full for all 7 papers, with the same lines as the original. S3 corrects only the reason given.
2. **`metadata.pdf` deleted.** Right. Its blank page is refused under D-393, and the test now writes the same Info dictionary and `/Lang`. The move-only commit `8b78d2c` is a move: the `diff -w` of the removed and added blocks differs only in the module header and imports.
3. **truncated-start and half now say "cut short".** Right under D-395: both start like a PDF and have no %%EOF at the end.

## What I checked and found right

- **Fast suite** on the head: 2,990 passed, 1 skipped (Windows-only), 57 snapshots. ruff, ruff format, lint-imports and deptry are clean. CI is green on all 12 checks.
- **Golden file:** I put main's `.ambr` back and regenerated with `--snapshot-update`. The result is byte-identical to the PR's file. Its diff against main is exactly 7 changed metadata lines (each only gains `language=''`) and 2,604 added `drawing` lines, nothing else. `_graphics` is unchanged, so the drawings are main's own data.
- **Spoken scripts:** `sci2audio script --chapters all` on main and on the PR for all 7 papers gives identical `script.txt` (543, 412, 479, 646, 599, 137 and 73 lines) and identical `report.json`.
- **Hostile files, timed with my own writer** (not `pdf_maker`):

| File | Result |
|---|---|
| page-tree bomb, 19 levels (524,288 pages), 4 KB | refused in 0.00 s, 30 MB |
| 13 levels (8,192 pages) | read in 0.8 s |
| 1,000,000 characters on one page, 4 KB | refused in 0.33 s, 134 MB (PDFium's own share) |
| 99,000 characters on one page | read in 1.9 s, 109 MB |
| 100 pages × 99,000 characters (9.9 M, under the total limit) | read in 192 s, 144 MB: the accepted worst case of about 3.5 minutes |
| two image-only pages (a scan) | refused with the D-393 message; the CLI prints it and exits with code 5 |

  The limits fire before `_lines`: the patched-out `_lines` and `_pages` in the tests confirm it, and so do the timings.
- **Valid files that must read:** for all 7 papers, pikepdf linearized and object-stream copies, PDFium incremental saves, and the owner-locked copies above all read the same lines as the original. Trailing bytes are fine up to 4,000; above that is M1.
- **Messages in English and German:** `test_web_refused_pdfs.py` (14 cases) passes. Each refusal reaches the document page inside the German or English sentence, with the app's words marked `lang="en"` (D-291). The browser tests for damaged files pass in Chromium: `test_a_damaged_file_shows_the_apps_message` and the German damaged-file step in `test_german.py`, 10 tests in all.
- **Timeout guard:** all 10 `test_extraction_*.py` modules set a module-wide timeout (9 at 60 s, the corpus test at 120 s), and the guard's own tests show that it catches a missing timeout.
