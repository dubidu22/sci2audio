# PR #616 review, round 2 (head 1b1982d)

Reviewer: textprep B6 review thread, 19 Nov 2026 ~05:50Z. Final-round checks run on this head.
Verdict: **changes requested, tests only** (T2). F1, F2, T1 and N1 of round 1 are fixed. Round 3 = T2's test commit, then
three systems and the two mutation globs again on that head, and the merge.

## Round 1 items, checked

| item | check | result |
|---|---|---|
| F1 | `gaps.py`, 17 shapes × 30 positions | **0 of 30** for every shape (a1f030b: up to 2/30; "12/20" was 2/30 against main 0/30) |
| F1 | `fuzz5.py` (= fuzz4, counting cut differences apart from script breaks), seeds 1, 2 × 150 per language | cut differences **0 of 300** and **0 of 300** (main 136 and 136); script breaks 32 and 17, the same on main (#614, #617) |
| F1 | corpus utterances (`corpus_utts.py`, 13 sources, 3 settings, both runs) | **byte-identical to a1f030b**, so default settings identical to main and only the accepted chi-plue tables-off change |
| F2 | `perf.py`, 160,000 characters | "-a" 0.24 s, ".a" 0.25 s (a1f030b 1.30 / 1.44 s, main 0.07 s); plain words 400,000: 0.45 s (main 0.21 s). `perf3.py`: unit names, "per", months, "out of", "ein halb" repeated: all linear, at most 0.30 s per 160,000 |
| T1 | the new `_joined` cases | E3, E4, E12, E14, E15, E16, E17 each have a test; the author's `hand_r2.py` reports 50 of 52 killed, E13 and the guard equivalent |
| N1 | | guard dropped, comment says why |
| #479 | `fp.py` | unchanged from round 1 |

## Final-round runs on 1b1982d

- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 8080; the cutter file, both regression files, the sentence gate): 1,323 passed, 6 xfailed, each seed.
- **Three systems** (`ci:full` added at 05:27Z): `tests (ubuntu|macos|windows-latest)` all green on 1b1982d; run again on the round-3 head.
- **Mutation workflow** (`mutation.yml`, one glob per dispatch, tests = the cutter file and both regression files):

| run | glob | killed | survived |
|---|---|---|---|
| 44465355751 | `x__label_again*` | 24 | 2 (12, 14) |
| 44465342397 | `x__joined*` | 50 | 13 |
| 44465363082 | `x__cut_point*` | 80 | 9 |
| 44465349158 | `x__readings*` | none ran | mutmut 3.8.1 skips decorated functions (`@cache`). Accepted: `hand_r2.py` covers `_readings` with 31 hand mutants, all killed but the equivalent E13. No change asked. |

## T2 (tests): surviving mutants of the PR's own code

**`_label_again`**
- **12** `max(0, start - 32)` → `max(1, …)`: **real.** A paragraph that opens with the label, "Abs. 2. Abs. 3 gilt.", is no longer cut (checked: `['Abs. 2. Abs. 3 gilt.']` with the mutant, two utterances without). Add it to the #479 cases (it fails with the mutant).
- **14** `start - 32` → `start - 33`: only a word of 32 or more letters before the number changes. State in the PR body that the window is a speed bound and the longest label words are far shorter; no test asked.

**`_joined`**: killed by a direct `_joined` test each:
- **37** `finditer(text, 1, …)`: a reading at the very start of the text ("unter anderem bbb": "unter | anderem").
- **8**, **26** (`range(2, …)`, `word_end > 1`): a one-character number as the text's first word ("5 Komma 3": "5 | Komma").
- **55** (`last` dropped from the bound): no place past `last` is returned (the docstring's "up to `last`").
- **58** (`len(text) - 2`): a reading place right before the text's last character ("aaa per s": "per | s").

Equivalent, to be stated in the PR body with the reason: **3** and **25** (`word_end` 1 or `>= 0`: only text that starts with white space, where the character checked is white space), **6** (`range(0, …)`: place 0 is never a cut), **14**, **16**, **56**, **57** (upper bounds past `last`: `last` is under `len(text)` for every window over the limit, and `text[k - 1]` is checked first), **36** (no `endpos`: places past `last` are dropped by the bound, speed only).

**`_cut_point`**: **27** (bracket penalty 6 → 7) is equivalent: places inside a bracket then rank 7 to 12, still after 5. State it.
The other eight `_cut_point` survivors (10, 34, 38, 39, 52, 58, 59, 73) are on lines this PR does not change. I filed them as **#619** (v1.2.x), with 73 (the fairness bound, `- 1` → `+ 1`) as a real gap. Not in this PR.

## Round 3

One commit, tests and the PR body only. Then I re-run the three systems on its head, the mutation globs `x__label_again*` and `x__joined*`, and merge pinned to that head.
