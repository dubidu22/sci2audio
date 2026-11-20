# Review of PR #188, round 3 (issue #5, PDF part): approved

Reviewed head `6d64b71`, 13 Nov 2026. Author's answer: `plans/review-pr188-round2-answer.md`.

**Verdict: clean. I'm merging it.** There are no open findings.

## Round 2 fixes: verified

- **M2 (fixed):** `_OBJECT` is now `(?<!\d)\d++\s++\d++\s++obj\b`. I timed `_cut_short` on waskom plus each of these 1 MB tails after its `%%EOF`:

  | Tail | Time |
  |---|---|
  | all digits | 0.011 s |
  | `1 ` pairs | 0.030 s |
  | spaces | 0.014 s |
  | `1`, spaces, `1` | 0.015 s |
  | `1 ` then digits | 0.023 s |
  | runs of 999 digits | 0.024 s |
  | `1 1 ` then digits | 0.023 s |
  | tab/newline mixes | 0.027 s |

  Round 2 measured 53 s for 100 KB.
- **S5 (fixed as recommended):** with only `%%EOF` removed, the papers read the same lines as before: chi 1,335, hardt 602, arsiwalla 1,091, liu 770, seaborn 215, pymedphys 211. nowak, which is linearized and whose table PDFium rebuilds, is refused. That is the trade-off the PR body states.
- **Sweep, rerun on `6d64b71`:**
  - 7 papers as stored, linearized and with object streams, each cut 26 ways: no findings.
  - The same papers given 8 tails: no findings.
  - Incremental saves, owner-locked copies (R3, R4, R6) and pikepdf rewrites: no findings.
  - All 7 incremental saves cut inside their update are refused.
- **Fast suite:** 3,056 passed, 1 skipped.
- **CI:** all 12 checks are green on `6d64b71`, the branch is up to date with main `5aad4ae`, and the mergeable state is clean.
- **Golden file and scripts:** unchanged since round 2. Only `test_extraction_corpus.ambr` differs from main, by 7 metadata lines and 2,604 drawing lines. The spoken scripts and report.json for all 7 papers are identical to main.
- **PR body:** I corrected one leftover sentence myself: it still said qpdf "always allows accessibility" (round 1, S3). Nothing else changed.

## Final cut-short rule as implemented (for D-419, amending D-395)

A PDF is refused as "cut short" when it starts with `%PDF-` within its first 1,024 bytes (`HEADER_ZONE`), and either:

- **(a)** object data matching `(?<!\d)\d++\s++\d++\s++obj\b` (such as `12 0 obj`) follows its **last** `%%EOF`; or
- **(b)** it has no `%%EOF` anywhere, and PDFium either had to rebuild the cross-reference table (`FPDF_DocumentHasValidCrossReferenceTable` = 0) or could not open the file.

The order of the checks:
1. If PDFium can't open the file, the message for a password, then DRM or a certificate (D-397), comes first. Then cut short, using (a), or (b) with the table counted as rebuilt. Otherwise the file is "not a PDF, or the file is damaged".
2. If PDFium opens the file, the cut-short check is the first pre-read check. The owner-permission check (D-396), "no pages" and the page limit (D-394) follow it.

The check is one `rfind` and one linear regex search from the last `%%EOF`. Bytes after a whole file's last `%%EOF` that hold no object, such as zeros or a web page, are not a cut. The one trade-off: a whole file without `%%EOF` whose table PDFium rebuilds is refused, because it can't be told from a cut file (among the corpus papers, only nowak with its marker removed).
