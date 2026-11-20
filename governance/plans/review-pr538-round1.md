# Review of PR #538, round 1 (final)

PR: https://github.com/dubidu22/sci2audio/pull/538 "extraction: positions from the crop box corner, cut-off parts of the sheet not read (#458)"
Branch: extraction/cropbox-offset-458. Reviewed head: d52f0a6 (032ab4a + merge of main 158f1ae). Main tip at review: 158f1ae, so not behind.
Criticality: non-critical (lane:extraction). Opus medium depth. Plan items P1 to P3 (D-755).

## Verdict: APPROVED, 0 blocking findings, 1 follow-up issue (#543)

| Check | Result |
|---|---|
| Golden, regression case, snapshot moved? | No. Diff: `extraction/pdf.py`, `tests/unit/pdf_maker.py` (new `cropped`, the harness change the plan lists), `tests/unit/test_extraction_pdf.py`. |
| Corpus extraction unchanged | Own run: `read_pdf` on all 8 corpus papers, main 96de4a3 vs d52f0a6: every `Content` equal (`==`), all pages, lines, runs, pictures, drawings. |
| New tests fail on main | Copied the test file and `pdf_maker.py` onto main 158f1ae: the offset, cut-off and end-to-end tests fail, the origin guard passes. As the PR body says. |
| Every position goes through the frame | Characters, char origins (baselines), pictures, drawings (`_bounds`, form XObjects via the matrix) all use `_Frame.point`; no `height - y` left in `pdf.py`. Outline destinations use page indexes only, so nothing else needed the frame. |
| Probes | Crop box larger than the media box: PDFium's bbox is clipped to the media, size 600 x 800, positions as on main. Crop box inside a smaller own media box: items outside the sheet kept (consistent with the rule), positions measured from the crop corner. Media box wider than the crop box at the origin: reads as before. |
| Kehren (measuring only) | With #530 on main: same heads, note labels 1 to 5 and I/II/III as in my #530 review; the peDOCS sidebar of the cut-off half of page 2 is gone. |
| CI on d52f0a6 | Linux CI green (tests ubuntu, browser Chromium, lint and layers, licences, security, CodeQL, CI passed). The one browser failure before the re-run is the marker-note reload race filed as #542, not touched by this PR (one re-run allowed for an untouched flaky test). |
| Follow-ups | #537 (/Rotate pages) filed by the author. Commit messages: no closing keywords. |

## Follow-up (filed by the reviewer, not blocking)

- #543: `_Frame.of` cuts only when the page states its own `/MediaBox` (`FPDFPage_GetMediaBox` ignores the inherited value), so a spread whose media box sits on the `/Pages` node still reads the cut-off half. The plan chose "only when the page states one"; the issue makes the inherited case its own small task with acceptance criteria.

## Fix list for the author

None. Branch stays frozen; the review thread merges pinned to d52f0a6.

Merged: 94a4353 (squash, pinned d52f0a6).
