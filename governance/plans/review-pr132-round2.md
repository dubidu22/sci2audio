# Review of PR #132, round 2 (head 9b3ee4c)

Round 1 answer: https://github.com/dubidu22/sci2audio/pull/132#issuecomment-6855855905

## Round 1 items: checked

1. **Linear time: fixed.** Re-measured on this machine: the PR's 106k test text 0.16 s (was 17.9 s),
   reference lines 0.09 s (11.7 s), results prose 0.05 s (3.3 s); "1–" × 50,000 0.5 s (110 s);
   every other pathological string under 0.3 s. Through `find()` with soft hyphens, zero-width
   spaces and stray accents on 100k characters: under 0.25 s per step, all built-in steps under
   1.5 s. The new tests assert under 3 s with a 60 s timeout.
2. **"95%CI[1.2,3.4]": fixed**, reads "95% confidence interval 1.2 to 3.4".
3. **Short keywords: fixed.** "Fig. II", "Exp. II", "Figs. I–III", "Sec.III", "Chap. IV" read with
   digits on the first run; "the end. II" and "Vol. II" are left; D-185 in KB #38 names them.
4. **"=" next to ∆, ⟨ ⟩: fixed.** The corpus diff (main 586094f against this head) shows only
   these new readings beyond round 1: "∆ equals 0.883", "W equals ⟨A, ⊕, ⊗, 0, 1⟩",
   "⟨ρˆ⟩ equals ρ0", "2∆ equals 1.766" (Nowak, Liu).
5. **#150 filed** with the nits.

About 300 hand-made inputs (rounds 1 and 2) through all built-in steps twice: no second-run
change. Lint, layers and deptry are clean.

## New: two second-run cases, CI red on all three systems

`test_the_built_in_steps_never_fail_and_are_idempotent` (`tests/unit/test_textprep_runner.py`)
fails:

- **CI, `ci` profile (deterministic), Linux, macOS and Windows:** `"00±¸C"`. The first run
  leaves "±", because the cedilla after it is no operand; the Unicode step then composes "¸C"
  into "Ç", and a second run reads "plus or minus". An accent that composes with the letter
  after it (or before it) belongs to the operand: count it as one, or let `through_unread`
  read the composed letter.
- **Locally, nightly profile:** `"00×=0"`. "×" now counts as an operand on the right of a
  sign, but `_LEFT_OF_EQUALS` does not hold `_UNIT_SIGNS`; the units step reads "×" as
  "times", so a second run reads "=" as "equals". Add `_UNIT_SIGNS` to `_LEFT_OF_EQUALS`.

Both need a fix and a unit case; then CI green on the new head and one more nightly round of
the runner, numbers and statistics tests.

## Not this PR

The fast suite here also failed `test_no_citation_is_left_and_no_word_is_lost` only because my
local Hypothesis database replays the #145 example from round 1. Pre-existing, #145.

## KB #38 (head 0d0b539)

D-185 and D-186 wording as asked; main merged (D-320). Approved; it merges after #132.
