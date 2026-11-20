# Review PR #559 round 1 (#537 + #543, non-critical)

Head reviewed: 0fb3ade3ad7912aac2ca3e9c489d5cf3b3fb5c1c (merges main f919d81 cleanly; main changed no extraction file since base).
Reviewer: B1 review thread, 18 Nov 2026. Linux CI green on the head ("CI passed", tests ubuntu, browser 1/2 and 2/2).

## Verdict: CHANGES REQUESTED (1 must fix)

## Verified

- Rotation maths: (H−v, u) for 90, (W−u, H−v) for 180, (v, W−u) for 270, with width/height the page as shown; `page.get_size()` already gives the shown size, so `Page.width/height` and positions now agree. Inherited `/Rotate` (on `/Pages`) and `/Rotate -270` both read as 90 (probe).
- Corpus differential (plans/b1-review-turn-probe.py): every corpus paper passed through the PR's `turned()` at 90, 180 and 270 and compared field by field with the upright read (`to_data(pages)`, floats within 0.05 pt): 8 papers x 3 turns, 0 differences except one generated space in liu (page 1, line 70, run 6: "π )" vs " π )", at 90 and 180), which comes from PDFium's space guess through the form XObject of the helper, not from the frame. Pictures and drawings included.
- #543: `_media_box` resets the crop box to the box PDFium used before the text page is loaded; `get_size()` is read before; the cover renders from its own document in its own child. No golden moves (extraction + layout snapshots pass locally with main merged).
- Mutants on the new tests: media box hack removed (fails), 270 formula swapped for the 90 one (fails), width/height not swapped (fails), snap in `_Frame.angle` removed (**survives**, also on all 1378 extraction/pdf/layout unit tests): see M1.
- Commit message: no closing keyword; body has Closes #537, Closes #543.

## Findings

**M1 (must fix). Text on a turned page now sits on the 0/2π seam of the angle, so slightly skewed letters split into separate lines.** `_Frame.angle` moves text that reads left to right on a turned page from about 3π/2 (90), π (180) or π/2 (270) to about 0. `_Line.accepts` (pdf.py line 600) compares angles with `abs(char.angle - last.angle) > 0.01`, which is not circular: a word at 0.2° and the next at −0.2° get 0.0035 and 6.2797 and start a new line. The 1e-6 snap only covers float noise, and no test reaches it (mutant `return turned` survives). Probe plans/b1-review-jitter-probe.py (three words on one line, skewed +0.2°, −0.2°, +0.2°):

| page | main | PR |
|---|---|---|
| upright | 3 lines (old bug) | 3 lines |
| `turned(.., 90)` | 1 line "Alpha Beta Gamma" | **3 lines** |
| `turned(.., 270)` | 1 line | **3 lines** |

Scanners often store a landscape scan with `/Rotate` and an OCR layer with a small skew, so this is a reachable regression on the pages this PR is meant to fix.

Exact fix: in `_Line.accepts`, compare the angles around the circle:
```python
turn = abs(char.angle - last.angle)
if min(turn, math.tau - turn) > 0.01:
    return False
```
Add a test in `tests/unit/test_extraction_pdf.py`: the probe's three skewed words read as one line on the upright page and on `turned(.., 90)` and `turned(.., 270)` (fails on 0fb3ade at 90 and 270). Checked locally with the fix: the probe gives one line in all three cases, and 1562 extraction, pdf, layout, corpus and snapshot tests pass with 77 snapshots unchanged. The same line also fixes the upright case (an older bug, same cause); keep it in this PR since it is the one line and no golden moves, and say so in the PR body. Keep or drop the snap in `_Frame.angle` as you like; if kept, the new test should not depend on it.

## Notes (no change asked)

- N1 The liu generated-space difference above is a probe artifact of `turned()`; nothing to do.
- N2 A page with no media box anywhere now gets PDFium's US Letter as its sheet (the PR body says so); text past Letter is still kept. Fine.
