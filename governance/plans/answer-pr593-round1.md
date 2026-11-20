# Answer to review of PR #593, round 1

Fix commit on top of 6b75aa1 (one commit, no main merge: main moved only by #582, which shares no file with this PR except CHANGELOG.md, no conflict, MRG-03). The prototype `plans/b5-review/round1-prototype.diff` was taken as the base for F1 to F3, formatted and documented.

## F1 long arrows: fixed
- `notation._TWO_GLYPH_ARROW` takes the whole run of U+2212: `←−+→|←−+|−+→`; `_one_arrow` maps by the end glyphs (`↔`, `←`, `→`). Reason text now says "arrow printed in pieces".
- Chosen: English `b ←−−1` reads `b ←1` (both languages alike), as the review accepts.
- Tests: `test_numbers_read_as_said` (en) `X −−→ α and Y ←−− β` → `X → α and Y ← β`, `X ←−−→ Y and −−→AB` → `X ↔ Y and →AB`, `b ←−−1` → `b ←1`; German `test_a_second_run_reads_nothing_new` `X −−→ α und Y ←−− β`, `X ←−−→ Y`, `−−→AB`, `Dann gilt a ←−−1` → `Dann gilt a ←1`. `notation_texts._SIGNS` gains `←−−`, `−−→`.

## F2 German rules deciding on the removed "−": fixed
- `find_numbers_de` runs `arrows(text)` first and gives every other rule `as_one_arrow(text, found)`: each arrow written as its one glyph repeated to the printed length, so spans stay valid (`notation.as_one_arrow`). English is not masked (the grid needs none there).
- `citations._MATHS_SIGNS` holds `↔`.
- Tests: German second-run cases `x ←−1:1` → `x ←1 zu 1`, `x ←−1/2` → `x ←ein halb`, `x ←−3-5` → `x ←3 bis 5`, `x ←−→ [2]` → `x ↔ [2]`; citations stay-as-printed cases en `x ↔ [2] and y ←−→ [3]` (`test_maths_intervals_and_data_in_brackets_are_not_citations`) and de `Es gilt x ↔ [2] und y ←−→ [3].`; `@example` `←−1:1` (de) on `test_a_german_job_reads_the_same_on_a_second_run`.

## F3 clock exception, any space: fixed
- `_AFTER_UHR = \bUhr\s+\Z` and `_CLOCK_UHR = \d[:.]\d\d\s+Uhr\s+\Z`; skip only when the first matches and the second does not, in a window of `_UHR_WINDOW = 24`.
- Tests (German second-run list): `um 13:30  Uhr 3. Mai`, `um 13:30\tUhr 3. Mai`, `um 13:30\nUhr 3. Mai`, each → `um 13 Uhr 30 dritter Mai` (fixed points). In this whole-chain helper the newline and tab forms do not read "Uhr" twice, so no #594 comment was needed; #594 stays as filed.

## F4 survivors: each killed or removed
| survivor | done |
|---|---|
| `_MINUS` look-behind `←`, `↔` | removed from the look-behind; `a ↔−1` reads `a ↔minus 1` as on main |
| `_FRACTION` without `]` / `}` | `It is [a]−1/2 here.`, `It is {a}−1/2 here.` as printed (en fraction second-run list); mutants KILLED |
| `_AFTER_HUNDRED` without look-behind / with `\d+` | `von 211 hundert 5. Jahr` → `von 211 hundert fünftes Jahr`, `von 5 hundert 3. Kapitel` → `von 5 hundert drittes Kapitel` (fixed points); both mutants KILLED |
| `_AFTER_UHR` `\n` look-behind | replaced by `_CLOCK_UHR`; one-space-only, clock-off and window-8 mutants KILLED by the F3 tests |

My own mutants on the new code (targeted unit and regression tests, ci profile): 13 of 13 killed (the six above plus `_TWO_GLYPH_ARROW` single minus, no masking in German, `↔` out of `_MATHS_SIGNS`, `↔` mapped to `←`). Script: scratch `m.py`, same shape as `hand-mutants.py`.

## Checks on the fix head
- `arrowgrid.py`: **unstable 0**.
- Nightly profile seed 31337 on the German second-run test: green. `dev` seeds 1234, 99, 11, 66 on the number and citation test files: green.
- Corpus scripts (13 sources × default / figures off / figures and formulas off): **identical to 6b75aa1**.
- Fast suite 7,594 passed, 8 skipped; ruff, format, lint-imports, deptry clean.
