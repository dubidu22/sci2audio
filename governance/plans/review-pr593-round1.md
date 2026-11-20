# Review of PR #593, round 1 (textprep batch B5: #536 #557 #483 #527)

Reviewed head: **6b75aa1** (rows 6f97995, rules 6b75aa1), base main ad6b94f. Critical (regression rows, golden snapshot). Reviewer: B5 review thread, 19 Nov 2026.
**Verdict: CHANGES REQUESTED.** One fix commit, then round 2. Four items (F1 to F4), all exact.

## What I checked, and what holds

- **ci:full on 6b75aa1:** green on Linux, macOS and Windows (`tests (macos-latest)`, `tests (windows-latest)`, `CI passed`).
- **Plan (D-774):** the PR follows sections 1 to 5. Every new row passes `read_twice`, and `SECOND_RUN_EXCEPTIONS` is unchanged.
- **Row goals are honest:** both arrow rows say that the voice still says "minus one" for the raised `−1` (#589), and the #557 goal names "drei. Mai" as the as-printed alternative. No row locks in a wrong reading.
- **#557:** `um 13:30 Uhr 3. Mai` reads `um 13 Uhr 30 dritter Mai` on both runs. That matches `3. Mai` → `dritter Mai` without the time before it (AC 3). `13 Uhr 30. Jahr` (#253) and `um 13 Uhr 3. Mai` keep their readings.
- **#536:** `im Jahr 1998. Jahr`, `seit 1850. Jahr` and `im Jahr 1998. Auflage` read the same on both runs. `das 98. Jahr`, `am 3. Mai` and `das 1998. Jahr` are unchanged.
- **#483:** `(Koch 2019)`, `(Wagner 2020)`, `(Sommer et al. 2019)`, `(Sommer und Koch 2019)`, `(vgl. Sommer 2019)`, `(Sommer, 2019)`, `(Sommer 2019, S. 3)`, `(Sommer 2019a)` and `(Sommer 2019; Koch 2020)` are still removed. Narrative `Sommer (2019)` is still removed. English is unchanged (#588).
- **#527 shape 2:** `_MINUS` refuses a sign glued after `)`, `]` or `}` (U+2212 only). The spaced forms `(a) − 1` and `x −1` keep "minus". `|x|−1` keeps "minus", as before.
- **Corpus script diff (my own run, 13 sources × default / figures off / figures and formulas off):** only acl2023-nowak changes. It has 6, 17 and 17 changed lines, line for line what the PR lists. The 17 `−→` left in the "figures and formulas off" script sit in formula blocks, which are read as printed by design (`read_as_prose`). That is not this PR's concern.
- **Golden snapshot** `test_textprep_furniture.ambr`: 59 → 65 accepted number edits for nowak. These are the six arrow joins in its read blocks, as explained.
- **Test-harness changes (plan section 6):** all are listed in the PR body. Two differ from the plan, and both are acceptable:
  - One existing input changed: `"X −→ α and x−1"` became `"X → α and x−1"`, since the reading of `X −→ α` changes on purpose and is now pinned in `test_numbers_read_as_said`.
  - `notation_texts` adds `. Jahr`, `. Mai` and the time tails instead of the bare words `Uhr` and `hundert`. They reach the same rules, and nothing is narrowed.
- **CHANGELOG (D-768):** three Unreleased lines cover the four issues.

## Findings (all must be fixed in the round-1 fix commit)

### F1 (blocking, new second-run break): a long arrow with more than one U+2212
`_TWO_GLYPH_ARROW` takes exactly one `−`. PDF text gives longer arrows and vectors (`\overrightarrow{AB}`) as `−−→`, `←−−` or `←−−→`. The PR joins only the last pair, so a second run joins the next one. Main leaves all of these as printed, and stable.

| printed | run 1 (PR) | run 2 (PR) |
|---|---|---|
| `X −−→ α and Y ←−− β` (en, de) | `X −→ α and Y ←− β` | `X → α and Y ← β` |
| `The vector −−→AB` | `−→AB` | `→AB` |
| `Dann gilt a ←−−1` (de) | `a ←−1` | `a ←1` |
| `X ←−−→ Y` | `X ←→ Y` | (stable, but two arrows) |

**Fix:** one arrow takes the whole run of U+2212: `←−+→|←−+|−+→`. Map it by its end glyphs: `↔` when it starts with `←` and ends with `→`, else `←` or `→`.
**Tests:** add these to `test_numbers_read_as_said` (en) and the German `test_a_second_run_reads_nothing_new`:
- `X −−→ α` → `X → α`
- `Y ←−− β` → `Y ← β`
- `X ←−−→ Y` → `X ↔ Y`
- `−−→AB` → `→AB`
- `a ←−−1` → `a ←1` (en and de)

Also add `−−→` and `←−−` to `notation_texts._SIGNS`.
With this regex, English `b ←−−1` reads `←1`, where the PR reads `←minus 1`. Both are stable, and I accept `←1` because both languages then read the same. Say which one you chose.

### F2 (blocking, new second-run break, found by nightly seed 31337): the German rules decide on the `−` that the arrow removes
`test_a_german_job_reads_the_same_on_a_second_run` fails with seed 31337 (nightly profile) on `←−1:1`: run 1 gives `←1:1`, run 2 gives `←1 zu 1`. The German ratio, fraction and hyphen-range rules refuse a number after `−` on run 1. On run 2 they see `←` and read it. Main leaves `←−1:1` as printed, and stable.

My grid (`plans/b5-review/arrowgrid.py`: 5 arrows × 42 number shapes × glued/spaced × two leads, en and de) finds **562 unstable texts on 6b75aa1 and 0 on main**. The German cases:

| printed (de) | run 1 | run 2 |
|---|---|---|
| `x ←−1:1`, `x ←−3:2`, `x ←−13:30` | `←1:1` | `←1 zu 1` |
| `x ←−1/2`, `x ←−3/4` | `←1/2` | `←ein halb` |
| `x ←−3-5` | `←3-5` | `←3 bis 5` |

There is a citations case in both languages too: `x ←−→ [2]` reads `↔ [2]` on run 1 and `↔` on run 2. `citations._MATHS_SIGNS` holds `→` and `←`, so `[2]` stays after the printed `→`. It does not hold `↔`, so on run 2 the bracket is removed.

**Fix:** the other rules must decide on run 1 as they will on run 2. One way that works:
- `find_numbers_de` runs `arrows(text)` first.
- It then gives every other rule the text with each found arrow written as its one glyph, padded to the arrow's length (the spans stay valid).
- Add `↔` to `_MATHS_SIGNS`.

My prototype is `plans/b5-review/round1-prototype.diff` (F1, F2 and F3 together). It is not formatted: the `_one_arrow` line is too long for ruff. Measured on it:
- the grid: 0 unstable;
- the targeted unit and regression tests: 1,922 passed;
- nightly seeds 31337, 1234 and 99: green;
- seed 7: one failure, which is pre-existing on main and filed as #597;
- corpus: all 39 scripts identical to 6b75aa1.

English needed no masking in the grid. Masking English too is fine if you prefer one shape for both.
**Tests:** add these German second-run cases:
- `x ←−1:1` → `x ←1 zu 1`
- `x ←−1/2` → `x ←ein halb`
- `x ←−3-5` → `x ←3 bis 5`

Add citations cases, en and de: `x ←−→ [2]` and `x ↔ [2]` stay as printed. Add `@example` for the seed-31337 document (`←−1:1`, German) on `test_a_german_job_reads_the_same_on_a_second_run`.

### F3 (required): the #557 clock exception covers one space or one newline only
`_AFTER_UHR`'s look-behinds are fixed-width (`\d[:.]\d\d ` and `\d[:.]\d\d\n`). With two spaces or a tab, `um 13:30  Uhr 3. Mai` still reads `13 Uhr 30 3. Mai` on run 1 and `dritter Mai` on run 2, as on main. The fix leaves these whitespace variants of #557 open.
**Fix:** keep `_AFTER_UHR = \bUhr\s+\Z` and add `_CLOCK_UHR = \d[:.]\d\d\s+Uhr\s+\Z`. Skip only when `_AFTER_UHR` matches and `_CLOCK_UHR` does not, searched in a window that holds the clock (16 is enough for the cases below; 24 is safer). This is in the prototype.
**Tests:** add these German second-run cases:
- `um 13:30  Uhr 3. Mai` (two spaces) → `um 13 Uhr 30 dritter Mai`
- `um 13:30\tUhr 3. Mai`
- `um 13:30\nUhr 3. Mai`

The newline and tab cases still read `Uhr` twice. That is pre-existing and filed as #594. Pin today's output and name #594 in a comment.

### F4 (required): guard parts that no test notices
My hand mutants (`plans/b5-review/hand-mutants.py`, targeted unit and regression tests, ci profile) killed 19 of 27. Each survivor below needs a test that fails without it, or the code goes:

| survivor | what to do |
|---|---|
| `_MINUS` look-behind without `←` and `↔` (two mutants) | After F1, a `−` after `←` is always part of an arrow, so `←` is dead code. `↔` changes `a ↔−1` from "minus 1" to as printed, which no test or plan line asks for. **Drop both** from the look-behind, or pin `a ↔−1` in a test and say why. |
| `_FRACTION` look-behind without `]` and without `}` (two mutants) | Add these to the fraction second-run list: `It is [a]−1/2 here.` and `It is {a}−1/2 here.`, both as printed. |
| `_AFTER_HUNDRED` without `(?<![\d.,])`, and with `\d+` for `1[1-9]` (two mutants) | Add these to the German second-run list: `von 211 hundert 5. Jahr` (the ordinal is still read, since `11 hundert` is inside `211`) and `von 5 hundert 3. Kapitel` (still read). Use whatever the step gives on run 1, after checking that it is a fixed point. |
| `_AFTER_UHR` without its `\n` look-behind | Covered by F3's newline test. |

The `_AFTER_UHR` window widened from 8 to 16 survives too. It is equivalent, because a look-behind sees text before `pos`. With F3's separate `_CLOCK_UHR` search the window matters, and the two-space test covers it.

## Not blocking (accepted, or filed)

- Filed: **#594** (a German time with `Uhr` on the next line reads "Uhr" twice), **#595** (German dating brackets of two words, `(Frühjahr und Sommer 2019)` and `(Stand März 2020)`, are removed) and **#597** (`1–1-` / `=1–1` German second run, from seed 7). All are pre-existing on main, proposed for v1.2.x.
- `Sommer`, `Winter` and `Herbst` are also surnames, so `(Winter 2019)` with no other citation cue now stays as printed even when it cites. This is the trade-off AC 1 and the plan accept. A citation read aloud is the faithful direction; removing a real date was not.
- `Laut (Sommer 2019), (Koch 2020)` keeps the first bracket, because the cue looks inside one bracket only. This is rare, and I accept it.
- A formula block whose notice is off keeps `−→` as printed (by design, `read_as_prose`), so the voice says "minus right" there. This is outside #527, which is about read text.

## For round 2
Push one fix commit with F1 to F4, then run Linux CI (ci:full is not needed for the fix commit). In the commit or PR body, list:
- the new tests and which survivor each one kills;
- the grid result on your head (`arrowgrid.py` via `PYTHONPATH=<worktree>/src`, expect 0 unstable);
- the corpus diff if anything changes against 6b75aa1.

Round 2 is planned as the final round: the scoped mutation workflow, nightly seeds, the three-system run on the final head, then the merge.
