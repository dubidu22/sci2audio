# PR #188, answer to review round 1

Fixes are in commit `dd4e382` on `extraction/pdf-broken-files-5`, after merging `main` (#48, no conflicts) in `56ff0ad`. Nothing was force-pushed. Fast suite: 3,043 passed, 1 skipped. ruff, ruff format, lint-imports and deptry are clean.

## Fixed

- **M1, whole PDF with 4 KB or more of trailing bytes refused.** `_cut_short` no longer looks at the last 1,024 bytes or at `FPDF_DocumentHasValidCrossReferenceTable`. The rule is now:
  - the file starts with `%PDF-` within its first `HEADER_ZONE = 1024` bytes;
  - and either it has no `%%EOF` at all, or object data (`\d+\s+\d+\s+obj\b`) follows its **last** `%%EOF`.

  The check is one `rfind` and one regex search from that point. Nothing walks the objects. `EOF_TAIL` became `HEADER_ZONE`, and its pin test follows. New tests:
  - all 7 papers plus 4,096 B, 10 KB and 1 MB of zeros and plus a 5 KB web page pass the pre-read checks (`_check`);
  - waskom with each tail reads the same pages as alone (one paper only, to keep the fast suite fast);
  - `one_page_pdf` with 4 KB, 1 MB and HTML after its end is read.

  The PR body states the rule exactly, for the KB.
- **S1, cut inside an incremental update read as the earlier revision.** The same rule catches it, because the update's objects follow the original's `%%EOF`. I dropped the xref condition, because PDFium itself rebuilds the table whenever there is no `%%EOF`, so that branch added nothing. New tests:
  - a made PDF with a page added by PDFium's incremental save (`pdf_maker.with_page_added`), cut 50 bytes into the update and 30 bytes short of its end, is refused with the exact message;
  - waskom with an added page reads 5 pages, and is refused when cut 50 bytes into the update;
  - a file with no `%%EOF` is refused, both when the writer left it out and when the file is cut before its xref.

  Measured on all 7 papers with PDFium incremental saves (the update is 613 B to 63 KB): the whole file reads with the added page, and cuts at +50 B, +200 B, −100 B and −30 B are all refused.
- **S3, wrong qpdf sentence.** `owner_locked_pdf`'s docstring now says that the files are written here so the tests need no pikepdf and cover revision 2 too. It also says that pikepdf can write revision 3 with accessibility forbidden, and that qpdf forces it on from revision 4 (AES).
- **S4, limits not pinned at the boundary.** Two new tests take PDFium's own `count_chars()` of the made file. With the limit at that count the file is read; with count − 1 it is refused with the exact message. One test covers a page and one covers the total (two pages).

## Deferred

- **S2, page-object bombs.** Added to #185 with your numbers and two acceptance points (drawings and nested forms, and many uses of one picture): https://github.com/dubidu22/sci2audio/issues/185#issuecomment-6863638755. No code change in this PR.

## Declined

None.

## Check after the fix

I ran my own sweep in the shape of yours on 882 files. The sources were the 7 papers as stored, linearized and with object streams (both made with pikepdf 10.18.1), and with a PDFium incremental update. Each source was cut at 5 to 99.9 % and at 1 to 4,000 bytes short of the end (26 cuts, plus 2 inside the update), and each whole source was given 5 tails (1 KB, 4 KB, 10 KB and 1 MB of zeros, and HTML). **None was read partly. Every whole file read in full, with the same lines as the paper alone, and every cut file was either refused as cut short or read in full.**
