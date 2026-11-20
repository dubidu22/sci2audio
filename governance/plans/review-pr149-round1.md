# Review of PR #149 (Issue #33, body-size running heads), round 1

Reviewed head: a1cd7ce (merge of main c39752b). Plan: `plans/issue33-running-heads-plan.md`, decisions D-322 to D-327. KB PR: sci2audio-design #44 (head 108895a).

**Verdict: changes requested (two missing tests, one small code/docstring mismatch).** The rule itself matches D-322 to D-327 and the corpus does not move. No merge yet.

## What I checked myself

- **Whole diff against the plan:** `layout/furniture.py`, `layout/settings.py`, `tests/unit/test_layout.py`. No change to core, layer contracts or other modules. The two tiers, `_exact` (D-323), `head_pages`/`head_share` (D-324), no rule evidence (D-325), the unchanged tier 1 (D-326) and the unchanged footer and page-number rules (D-327) are all as decided.
- **Golden files:** fast suite with `--snapshot-update` on the PR head: 2178 passed, 19 subtests, **54 snapshots passed, `git status` clean** (nothing rewritten).
- **Corpus edge lines, main (c39752b) against the PR:** I extracted the 7 papers, listed every line in the edge bands with its furniture role, and dumped every block (kind, role, text) on both trees. **Identical output.** Roles: 16 running heads (the JOSS footers), 75 page numbers, 9 footers, 85 text. I count **185** edge-band lines, not the plan's 193 (see N2).
- **Edge cases with made-up pages:** "Algorithm 1"/"Algorithm 2" body size on 2 of 6 pages: text. A body-size table header on 2 of 4 pages: text; on 3 of 4: taken (the documented residual). "Algorithm 1" repeated on 3 of 4 pages: taken (same residual). Heads creeping 2 pt per page and drift within 0.5 em: taken, as on main. A body-size line at the bottom of every page: running head.
- **Mutations (14, against `tests/unit/test_layout.py`):** killed: shape instead of exact text in (a), dropping (b), dropping `head_pages`, dropping `head_share`, `max` to `min`, dropping the `apart` filter, dropping the `head_size` filter, tier 1 back to `loose`, (a) with 1 page, dropping the band in the text key, ignoring `body_heads`. **Survived: three** (M1, M2, and the band guard in the pooled count that the PR names).
- **Lint and layers:** ruff, format, lint-imports (3 contracts kept), deptry clean.
- **Nightly Hypothesis profile on `tests/unit/test_layout*.py`:** 329 passed, 7 snapshots passed.
- **CI on a1cd7ce:** all jobs green on ubuntu, macOS and Windows, browser, lint and layers, licences, CodeQL. The PR is behind main now (a0bb69f), so it needs an update-branch merge before the merge.

## Must fix

**M1. The height in the pooled count (D-322 "pooled per height") is not tested.** Mutant: `covered` counts every repeated line in the band, whatever its height. All tests pass. A real case it lets through: a body-size running head on all 6 pages at y 40, and a continued table header "Model Accuracy F1" at y 62 on 2 of those pages, with 1 em of white each side. With the code as it is, the header stays text. With the mutant, the header becomes a running head, which is the exact bug of #33 under a real head. Add this case as a test.

**M2. The pooled count counts pages, but no test fails if it counts lines.** Mutant: `covered` counts lines instead of distinct pages. All tests pass. A real case it lets through: a body-size table header set as two separate cells on one row ("Model" and "Accuracy F1") on 2 of 6 pages. Today that stays text. With the mutant, 4 lines reach `head_pages` = 3 and all four become running heads. Add this case as a test.

## Should fix

**S1. Smaller lines take part in the pooled count, but the docstring says "body-size edge lines".** `_body_heads` keeps every line that is apart and no larger than `head_size`, so lines set smaller than the body also count toward (b). Made-up case: a small "Preprint" head at y 40 on all 6 pages, and a body-size "Model Accuracy F1" on the same row on 2 pages. The header is taken, because the small head's pages count for it. A smaller line never needs `_body_heads`, since tier 1 already takes it. Suggested fix: keep only `line_size(line) >= settings.small * size` in `lines`, and add the case as a test. If you prefer to keep the smaller lines on purpose, say why in the docstring instead.

## Nits

**N1. Per-section heads.** When a body-size head follows the section ("2 Methods" on pages 2 and 3, "3 Results" only on page 4), the one-page head fails (a) and is read aloud. The others are dropped. That fails safe, but the module docstring's residual list should name it in one line. No issue needed.

**N2. 193 or 185 edge lines?** The PR and plan say 193. I count 185 with `_band(line.box, page, LayoutSettings())` over all lines with a box on all 7 papers on c39752b. Please say how you counted. If it was before #133, or counted something else, one line in the PR is enough.

**N3. `repeat_pages` comment in `settings.py`.** It still says "a line in the edge band repeated on this many pages is a running head". That is now true only for lines set smaller than the body. Suggest "... is a running head (body-size lines need more, below)".

## Outside this PR (follow-up issue suggested, coordinator to decide)

**F1. Lines set smaller than the body need no white and only the shape.** A continued table header set in `\small` (0.9 of the body, so under `small` = 0.95) at the top of 2 of 6 pages, with its first row 2 pt below, becomes a running head. So do "Algorithm 1" and "Algorithm 2" set at 0.9. This is unchanged from main and inside D-326 ("smaller heads keep today's rule"). The issue named only the body-size case. But `\small` tables and algorithms are common in papers, and this is #33's bug one size down. Nothing in the corpus is hit (all 16 running heads are the JOSS footers at 0.80). Suggest a v1.1 issue: "smaller-than-body repeated edge lines: continued table headers and algorithm captions". D-327's "no follow-up issues" covered only the footer and page-number rules, so this needs the coordinator's call.

## KB PR #44

The six rows match the plan's §9 and the code. They are newest first, above D-320, "Decided (Claude)", and Colin-informed 2026-11-13 13:26:54 UTC (checked against the chat post). Links are plain, and there is no closing keyword before the code PR link. Clean against main. It merges after KB #38, #39, #40, #42 and #43. If S1 or N1 change the code, D-322 and D-324 still read correctly. If F1 becomes an issue, it needs its own decision row, not a change to D-327.
