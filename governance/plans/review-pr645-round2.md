# Review of PR #645, round 2 (final): approved

Reviewer: B13 review thread, 19 Nov 2026. Reviewed head **bf8dd65** (fix commit; answer `plans/review-pr645-round1-answer.md`).

## M1: fixed

The banded sweep is replaced by a sweep over a segment tree of the page's distinct tops. Each box's span runs from y0 to y1 + `reach`. Two boxes are near down the page exactly when their spans meet, which happens exactly when one top lies in the other's span. The new box therefore asks two things: the path from its top's leaf up, for open spans that hold its top, and the O(log n) cover nodes of its span, for open tops that lie in it. Across, entries keep `x1 + reach` and are dropped once the sweep passes it. These are the same sums the reference compares, so equality holds to the last bit. Each node holds at most one live group after a look, since every live entry found there joins the new box. The amortized work is O(n log n), and it no longer depends on coordinates.

| Check | Result |
|---|---|
| Huge drawings (`plans/b13-review/huge.py`) | ±1e3 to ±1e9 pt: 0.00 s each (round 1: out of memory at ±1e9) |
| Differential fuzz vs main bf25945 (`fuzz645.py`, now with 5 % boxes up to ±1e9/1e30/3.4e38 tall and 3 % that wide) | 9,000 pages, 0 differences in groups or order |
| Corpus, main bf25945 vs bf8dd65 | furniture and every block identical on all 8 papers |
| Speed | benchmark page of 100,000 drawings 2.2 s here; the fast file `test_layout_figure_speed.py` passes (11.5 s with the benchmark) |
| CI on bf8dd65 | `CI passed`, tests on ubuntu, macos and windows (ci:full), browser shards, lint, licences, security, CodeQL: green |
| Nightly (nightly.yml, run 44493449482: property and benchmarks) | success |
| Mutation | GitHub run 44493445534: runner 1 (glob `x_touching*`) was lost ("runner lost communication"), most likely to a hang mutant, while runners 2 and 3 finished. I ran `x_touching*` locally instead (mutmut, `ulimit -v` 3.5 GB, `HYPOTHESIS_PROFILE=ci`, tests `tests/unit/test_layout_figure_speed.py`): 122 killed and 7 survived; `_4` (`parent[i] == i`) and `_86` (`high << 1`) are endless loops (stopped by hand; they count as timeouts) |

## Mutation survivors

- `x_touching__mutmut_11`, `_16`, `_17` (a larger `size`) and `_25`, `_29` (`3 * size` tables): these only add empty leaves or unused slots. Equivalent.
- `x_touching__mutmut_71` (`low | 1`): this adds the left node at every level. That node lies inside the range, or is the node `high` adds anyway, so the cover only gains duplicates. Equivalent.
- `x_touching__mutmut_76` (`low += 2`): for odd `low`, `(low + 2) >> 1 == (low + 1) >> 1`. Equivalent.
- `x_figures__mutmut_11/14/15`, `x__place__mutmut_70/73/74` (`zip(strict=…)`): the lengths are equal by construction. Equivalent.
- `x__place__mutmut_63` (`or True`): `replace` with the same parts. Equivalent.
- `x__place__mutmut_75`–`_84`: the leftover-`pending` block at the end, a line this PR does not change. Pre-existing.
- `x__placeholder__mutmut_14/25/26/27`: a function this PR does not change (the glob matched it). Pre-existing.
- `x__place__mutmut_21` (`joined.append(None)` for a furniture block): this is real. No test has a loose mark joining a running head that `_place` built. Behaviour is unchanged, so after the final round it is filed as **#649** (v1.2.x).

## Base move

Main moved bf25945 → 9f2cbaa (#621 textprep, #631 web), which shares only CHANGELOG.md. The branch was updated through GitHub's merge (65b2efa). Diff-unchanged check: `git diff bf25945 bf8dd65` equals `git diff 9f2cbaa 65b2efa` outside CHANGELOG.md, and the CHANGELOG diff is the same single #354 line. Main 9f2cbaa is green on all three systems.

## Verdict

Approved. Merge on `CI passed` for 65b2efa, squash, pinned. Filed #649.
