# Review of sci2audio PR #57 (head 63ef727), round 1

## Verified

- 495 tests pass; ruff, ruff format, lint-imports and deptry clean; Hypothesis dev profile clean.
- 10 TABLE and 18 FIGURE blocks; 29/29 truth caption labels describe a block of the right kind on their page.
- Every non-placeholder block has the same text, kind and label as on main; every item is in exactly one block.
- The golden-diff cause table matches my own count (47 / 29 / 63 / 44 / 4 / 1 / 1 / 8, and 354 + 218 lines into placeholders), except for point 2 below.

## Must-fix

1. **`_walk` is order-dependent and misses items.** It visits items once, by distance. An item not yet across `[left, right]` is skipped and never revisited after a later item widens the range.
   - Repro A (helpers from `tests/unit/test_layout_graphics.py`): `running(60, 5)`; drawings `Box(LEFT, 200, RIGHT, 200.5)` (frame top) and `Box(LEFT, 400, RIGHT, 400.5)` (axis); ten body-size tick lines `line(str(k), LEFT + 50*k, 404, LEFT + 50*k + 10)`; caption `line("Figure 1: Results.", 270, 420, 330)`; `running(440, 3)`. The FIGURE gets only "4 5" plus the graphics; "0 1 2 3 6 7 8 9" stay in the running paragraph above.
   - Repro B: a 100 × 20 grid of 2.5 pt drawings, 3 pt apart, at y 200 to 260 from LEFT; caption `line("Figure 1: Cloud.", 300, 270, 360)`. The FIGURE takes 420 markers; the other 1,580 join the paragraph above.
   - Fix so the result does not depend on visiting order (for example revisit skipped items when the range widens, or repeat the walk with the grown range until it is stable). Keep it near-linear. Add both repros as tests, rerun the corpus, and explain any golden change.

2. **The PR body's golden table is wrong on footnotes.** It says 29 footnote rules each become the first part of the footnote below. In fact 27 rules are first parts, and nowak `p1-d7` / `p1-d8` (the underbrace of "n times" inside footnote 1, y ≈ 712) join the *end* of footnote 2, because main reads them after footnote 2. Correct the body, and file an issue: a loose graphic joins the block read before it even when it stands inside another block (no audible effect now, but it breaks referenceability).

3. **`_ends` is quadratic in a block's parts** (each part scans all later parts). A partly taken graphic block of thousands of drawings (repro B) reaches it. Make it linear, for example by scanning from the end.

4. **File an issue:** `_is_line` checks thickness only, so dots and small markers count as lines. An uncaptioned scatter plot of small markers is then "lines only" and joins the paragraph before it instead of becoming a FIGURE. There is no corpus case, so an issue is enough unless you fix it cheaply with a setting.

## Optional (say fixed, or declined with a reason)

- `_side` already walks both sides, and `_read_float` walks the chosen side a third time. Reuse the walk.

Reply listing exactly what you fixed and why, with the new head sha. Do not merge.

## Must-fix 5 (added after the nightly Hypothesis run)

`HYPOTHESIS_PROFILE=nightly uv run pytest tests/unit/test_layout.py::test_layout_never_fails_and_keeps_every_line` fails: blocks come out of page order (`[1, 2, 1]`). Minimal case found by Hypothesis:

- page 1: picture `i0` with `Box(0, 0, 0, 0)`, drawing `i1` with `Box(3, 0, 14, 21)`;
- page 2: drawing `i2` with `Box(0, 0, 11, 21)`.

`i1` and `i2` count as a repeated graphic and become RUNNING_HEAD furniture. `i0` is a mark with no block before it, so `_place` holds it as `pending`. But the furniture branch `continue`s without taking `pending`, so the mark travels past the page-1 and page-2 furniture. It ends as a FIGURE block after page 2, or it would join a block on a later page. A pending graphic must not move past the next block. It should join the next block whatever its kind, or stay in place as its own block. Add this case as an `@example` and run the layout property tests under the nightly profile before you reply. The PR body's "nightly 92 passed" did not include this test.
