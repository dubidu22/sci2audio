# Review PR #600, round 1 (head 2faf117)

PR: layout: a listing caption names its code block; a listing over a page break is one block (#281, #283). Non-critical, layout lane. Reviewer thread: "Review the code block captions PR".
Verdict: **changes requested** (1 must-fix, 1 should-fix). Round 2 is the last round.

## Checked, no finding
- CI on 2faf117: `CI passed` green (tests ubuntu, lint and layers, both Chromium shards, CodeQL, licences, security).
- No golden, snapshot, regression row or sentence-set change: the diff touches `layout/captions.py`, `code.py`, `graphics.py`, four unit test files and CHANGELOG.md only. Non-critical holds.
- Textprep touch is test-only (`tests/unit/test_textprep_placeholders.py`, D-756); no textprep source.
- CHANGELOG Unreleased line present (D-768). PR body names the regression row text (AC-281.2). No closing keyword in the commit message.
- Join rules: the caption cut adds a split at a font-style change (never removes one); the page-break join joins code paragraphs only, refuses furniture between two code paragraphs of one page, refuses a later code paragraph that starts a section, and anything other than furniture between ends the run. A caption next to prose names nothing. Carried furniture keeps every item in exactly one block by construction (members + carried are disjoint, both mapped by `new_of`); section starts are never a joined member, so `_moved` stays monotone where it matters.
- Main moved by uv.lock only (#513, #515) since 678fe3c: no conflict, no shared file, no branch update needed (MRG-03).

## M1 (must fix): a caption picks the code of the other column
`code._listing_captions` takes the neighbour with the smaller `_white`. `_white` is a signed gap, so a code block in the other column of the same page (top of column 2 after a caption at the foot of column 1) has a large negative gap and wins over the code right above the caption.

Probe `plans/review-pr600-twocol-probe.py` (run from the repo root with `.venv/bin/python`): two columns of running text; column 1 ends with listing A ("import a") and "Listing 1: First." below it; column 2 opens with listing B ("import b") and "Listing 2: Second." below it. On 2faf117:
```
1 code 'import a\na.run()'  None
2 caption 'Listing 1: First.'  describes 3   <- names B
3 code 'import b\nb.run()'  None
4 caption 'Listing 2: Second.'  describes None
```
The voice reads "A code block is skipped." for A, "Listing 1 is skipped." for B, and "Listing 2" names nothing.

Fix (exact): in `_white`, return `math.inf` when the caption's edge line and the code's nearest line do not overlap horizontally (`a.x1 <= b.x0 or b.x1 <= a.x0`), i.e. a neighbour in another column counts as farther, as one on another page does. Add the probe as a test in `tests/unit/test_layout_code.py`: Listing 1 names "import a", Listing 2 names "import b". The test must fail on 2faf117.

## S1 (should fix): the property test does not reach the new paths
`test_every_line_of_a_code_block_is_set_in_a_typewriter_font` builds one page of mono/prose lines; it never has furniture inside a code run, a page break, or a listing caption, so the carried-furniture and caption-pairing code have no property coverage.

Fix (exact): add one Hypothesis test in `tests/unit/test_layout_code.py` over 2–4 pages, each with a running head and a page number, whose body is a random sequence of prose lines, code lines and "Listing N: ..." caption lines (the page's last body line and the next page's first may both be code). Assert: every item is in exactly one block; every CODE block's items are wholly monospace lines; each CODE block is named by at most one caption; every `describes` is in range and points at a CODE block for a listing caption.

## Deferred (issues filed)
- #603 (layout): a wrapped caption line that holds only a code name ("compute_loss()" in LMMono, no full stop) is cut into the code. Rare and needs a measured rule; not for this PR.
- #604 (textprep): the AC-281.2 regression row named in the PR body, plus the `textprep/placeholders.py` docstring. `Closes #281` can stay: the row is tracked there.

## Round 2
One fix commit with M1 and S1, Linux CI green, then tell this thread the new head.
