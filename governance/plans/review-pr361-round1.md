# Review PR #361, round 1 (textprep follow-ups PR 3, English numbers #336 #340 #210)

Heads reviewed: eca58a9 (base main 6c91465) and 44998bb (main 87c6503 merged in; `git diff 87c6503 44998bb` equals `git diff 6c91465 eca58a9` except for CHANGELOG line offsets). Plan: plans/textprep-v12-followups-plan.md PR 3 (D-605). D-614 accepted: "3 × 10−410^2" is left as printed. Critical.

**Verdict: not approvable yet. No blocker, one should-fix (S1), two nits.**

## What I checked

- Change against the plan: #336 (minus across one line break, and "~" before it), #210 (grouped caret exponent read whole, with the grouped-digits rule skipping a number after "^"), and #340 (`× 10−4` not before "^", D-614). One sibling of #210 is missing, see S1.
- Fast suite on eca58a9 (`HYPOTHESIS_PROFILE=ci`): 5231 passed, 1 skipped, 6 xfailed. The xfails are the four #324 cases plus #320 and #321, which PRs 1 and 2 remove.
- Regression cases in English and German, run twice: 565 passed, 6 xfailed both times. The corpus second-run test passes. ruff, ruff format, lint-imports (3 kept) and deptry are clean.
- The 13 corpus documents, run with `run_script_job` on main 6c91465 and on eca58a9: all 39 files are **byte-identical**.
- Commit messages: no closing keywords in 63a4409, 3f56c76, eca58a9 or 44998bb.
- Nightly seeds (`HYPOTHESIS_PROFILE=nightly`; runner, conformance, numbers, units): seeds **7** (which fails main's numbers contract on `t(3)=310^250 000 000`), 2024 and 123456 are all clean.
- Mutation-style breaks (numbers, units, both regression files): all of these fail the tests: `\n` dropped from `_MINUS`; the grouped alternative removed; one plain group allowed; the narrow-space alternative removed; the grouped-digits skip after "^" removed; "^" dropped from `_TIMES_TEN`'s look-ahead; groups joined with spaces instead of commas; `\n?` dropped after the sign in `_TILDE`. One survived: the grouped exponent's look-ahead `(?![    ]?\d)` (N1).
- Timing: the numbers step on n, 2n, 4n, 8n copies of a long grouped exponent, many grouped carets, minus-at-line-end and "10−410^2" grows the same on main and the branch. The grouped chain is about 4× per doubling on **both** (0.17 s to 0.63 s), which is pre-existing and not from this PR.
- Neighbour probes, whole chain twice, main vs PR (about 70 shapes): "−↵5", "5 −↵3", "x −↵5", "(−↵5)", "−↵0.5", "−↵.5", "−↵5 kg", "−↵5%", "−↵10^3", "−↵1,000", "‒↵5", "~ −↵5", "∼−↵5" all read "minus" on both runs. "− ↵5" (a space before the break), "−↵↵5" and "5−↵3" stay as before. Grouped exponents with 2 to 4 groups, a unit after, a list after, `x^`, `2^` and narrow spaces read whole on both runs. One plain group, braces, parentheses, a 4-digit group and a decimal tail stay as before.
  - `It is −↵3/4 s⁻¹ here.` still differs on run 2, the same on main. That is #335's class and is fixed by PR #359. I will re-probe it in round 2 once both are on main.
  - German never reads "−5" as "minus", so #336 has no German twin.

## Fix list

### Blockers

None.

### Should-fix

**S1. A signed grouped exponent still reads differently on a second run (#210's sibling).** The grouped alternative takes no sign, while the bare one does. The same on main:

| printed | first run | second run |
|---|---|---|
| `It is 10^-250 000 000 here.` | `10^-250,000,000` | `10 to the power of minus 250,000,000` |
| `It is 10^+250 000 000 here.` | `10^+250,000,000` | `10 to the power of 250,000,000` |
| `It is 10^−250 000 000 here.` | `10^minus 250,000,000` (stable, but the caret is left in the script) | same |

Fix: allow the optional sign `[+−-]?` before the grouped exponent, as `bare` does, so all three read `10 to the power of (minus) 250,000,000` on both runs. Add the three rows to `numbers-powers-with-grouped-or-glued-exponents` (or a unit test); they must fail on 44998bb. List the first-run change in the PR table.

### Nits

**N1. The grouped look-ahead is not pinned.** With `(?![    ]?\d)` removed, every test still passes. It is what keeps `It is 10^250 000 000 5 here.` as printed: a trailing single digit after the groups is no grouped number. Add that row to the unit test.

**N2. Two first-run changes are missing from the PR table.** `_TILDE` now also takes "+" before a line break, and it runs in German too:
- `It is ~+↵5 here.` was `~+ 5` and is now `about + 5`.
- `Es ist ~+↵5 hier.` was `~+ 5` and is now `etwa + 5`.
- `Es ist ~−↵5 hier.` was `~− 5` and is now `etwa − 5`.

All three read the same on both runs. List them.

### Deferred

None.

## CI

`ci:full` was added. eca58a9 is green on Linux, macOS and Windows. 44998bb (the main merge) was running at the time of writing, and the head after the fixes needs its own green run on all three.
