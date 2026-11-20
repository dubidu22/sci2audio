# PR #188, answer to review round 2

The fixes are in commit `6d64b71` on `extraction/pdf-broken-files-5`. I did not force-push. Fast suite: 3,056 passed, 1 skipped. ruff, ruff format, lint-imports and deptry are clean.

## Fixed

- **M2, quadratic object search.** `_OBJECT` is now `rb"(?<!\d)\d++\s++\d++\s++obj\b"`. The lookbehind starts each match only at the start of a digit run, and the possessive quantifiers make a long run of white space cost one pass. Measured times for the search on its own:

  | Input | Time |
  |---|---|
  | 1 MB of digits | 0.016 s |
  | 1 MB of `1 ` pairs | 0.040 s |
  | 1,000 runs of 1,000 digits, separated by spaces | 0.018 s |
  | 1 MB of spaces after one digit | 0.024 s |
  | 10 KB of digits (comparison) | 0.0002 s; the old pattern took 0.705 s |

  New test: a whole PDF followed by each of those four 1 MB tails is read. The test checks that `_cut_short` returns within 1 s, and it has a 10 s per-test timeout. Another new test checks the pattern itself: it matches `12 0 obj` and `7\t1   obj<<`, and does not match `endobj`, `12 obj`, `objective` or `1 0 objects`.
- **S5, whole files without `%%EOF` refused.** I took your recommendation. The no-`%%EOF` branch is again cut short only if PDFium rebuilt the table (`FPDF_DocumentHasValidCrossReferenceTable` = 0), or if it could not open the file at all. The docstrings are corrected. My round 1 reason ("PDFium always rebuilds") was wrong: it was based only on the made-up `one_page_pdf`. New tests:
  - each of the 7 papers with only its `%%EOF` removed passes the pre-read checks, and the test asserts that only nowak gets a rebuilt table and is refused;
  - waskom without `%%EOF` reads the same pages as alone;
  - `one_page_pdf` without `%%EOF` (table rebuilt) and cut before its xref are both refused with the exact message.

## The final rule, as written in the PR body for D-419

A file is cut short when it starts with `%PDF-` within its first 1,024 bytes **and** either:

- (a) object data matching `(?<!\d)\d++\s++\d++\s++obj\b` follows its last `%%EOF`; or
- (b) it has no `%%EOF` at all, and PDFium either rebuilt its cross-reference table or could not open the file.

The trade-off: a whole file without `%%EOF` whose table PDFium rebuilds is refused. Among the corpus papers this happens only to nowak, which is linearized.

## Deferred / declined

None.

## Check after the fix

The 882-file sweep from round 1 runs again with no problems. It covers the 7 papers as stored, linearized, with object streams and with an incremental update, each cut 26 ways and given 5 tails.
