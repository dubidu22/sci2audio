# Review of PR #188, round 2 (issue #5, PDF part)

Reviewed head `dd4e382` (round 1 fixes) after the merge of main in `56ff0ad`, 13 Nov 2026. Author's answer: `plans/review-pr188-round1-answer.md`.

**Verdict: changes needed. 1 new must-fix, 1 should-fix.** I checked all of the round 1 fixes and they are right.

## Must-fix

**M2. The new object regex is quadratic: 100 KB of digits after the last %%EOF takes 53 seconds.** `_OBJECT = re.compile(rb"\d+\s+\d+\s+obj\b")` is searched from the last `%%EOF` to the end of the file. On a run of digits with no whitespace, every start position inside the run makes `\d+` take the rest of the run and then backtrack through it. Measured on the PR head, with waskom plus a tail, calling `pdf._cut_short` alone:

| Tail after %%EOF | Time |
|---|---|
| 10,000 × `1` | 0.6 s |
| 30,000 × `1` | 5.0 s |
| 100,000 × `1` | 53.5 s |
| `1 ` × 50,000, or `1 1 ` × 25,000 | 0.003 s |

At 1 MB that is about an hour and a half. The upload cap is 200 MB, and the check runs before any page is read, both in `_check` and in `_load_message`. A small hostile file therefore hangs a job: the same class of problem the limits in this PR exist to stop.

Fix: anchor each match at the start of a digit run, for example `rb"(?<!\d)\d+\s+\d+\s+obj\b"`. Measured on 1 MB tails: 1,000,000 × `1` takes 0.022 s; `1 ` × 500,000 takes 0.041 s; 1 MB of spaces takes 0.017 s; 500 K digits then 500 K spaces takes 0.024 s; `1` × 1,000 then a space, repeated 1,000 times, takes 0.034 s. `12 0 obj` still matches. Any linear search is fine, for example `find(b"obj")` and then checking the bytes before it. Add a test: a whole PDF followed by 1 MB of digits (and one with 1 MB of `1 ` pairs) is read, and `_cut_short` on it returns within a second. Use a small per-test timeout or measure the time.

## Should-fix

**S5. "Without a %%EOF PDFium rebuilds the table" is not true for real papers, so whole files without %%EOF are now refused.** The answer file says so ("PDFium itself rebuilds the table whenever there is no %%EOF, so that branch added nothing"), and so does the docstring of `test_a_file_without_any_eof_is_cut_short`. I removed only the 5 bytes `%%EOF` from each corpus paper. For 6 of the 7, PDFium still gives `FPDF_DocumentHasValidCrossReferenceTable` = 1 and opens every page: chi, hardt, arsiwalla, liu, seaborn and pymedphys. Only nowak, which is linearized, gets 0. The made-up `one_page_pdf` happens to be rebuilt, so the test doesn't show this. The PR now refuses all 7 as "cut short", although nothing is missing.

Recommended: in the no-%%EOF branch only, bring the xref condition back. The rule would be: cut short if (no `%%EOF` anywhere and PDFium had to rebuild the cross-reference table) or (object data follows the last `%%EOF`). For a file with no %%EOF and a valid table, PDFium found a `startxref` near the end pointing to a valid table, so the file's end is there and at most the marker was lost. Files with an incremental update or a linearized first part have an earlier %%EOF and fall under the second condition, which does not need PDFium. Tests:
- each corpus paper with only its `%%EOF` removed reads the same lines, except where PDFium rebuilds the table, as with nowak;
- the existing cut cases stay refused;
- correct the docstring.

If you would rather keep refusing every file without %%EOF, correct the docstring and the answer's reason, and state the trade-off in the PR body (whole files from writers that leave %%EOF out are refused). Either way, the PR body's rule must match the code, because the coordinator records it as D-419.

## Round 1 fixes: all verified

- **M1:** fixed. My round 1 sweep ran again on `dd4e382`, unchanged: 7 papers as stored, linearized and with object streams, each cut 26 ways, plus 8 tails (1 KB to 1 MB of zeros, HTML, 3 KB of newlines, a comment plus 4 KB of letters). It also read the incremental saves, the owner-locked copies (R3, R4 and R6, copying forbidden, accessibility allowed) and the pikepdf rewrites. No findings: every whole file reads the same lines as the paper alone, and no cut file is read partly.
- **S1:** fixed. For all 7 PDFium incremental saves, cuts at +50, mid-update, −30 and −7 bytes are now all refused as cut short. In round 1, 6 of the 7 read silently as the earlier revision.
- **S2:** deferred correctly. The #185 comment has the numbers and two new acceptance points.
- **S3:** fixed. The docstring now matches what pikepdf 10.18.1 writes.
- **S4:** fixed. Both limits are pinned at PDFium's own count and that count minus 1. The `>=` mutant now fails.
- **Fast suite** on `dd4e382`: 3,043 passed, 1 skipped.
- **Spoken scripts and report.json** for all 7 papers are identical to the current main `5aad4ae`, which now includes #48.
- **Snapshots:** against main, only `test_extraction_corpus.ambr` changes, by the same 7 + 2,604 lines. The layout and app snapshot changes since round 1 came in with the merge of main.
