# Review of PR #208, round 2

Reviewed head cce228d (main 71b30c2 merged in), 13 Nov 2026, about 22:15 UTC. Verdict: **one more change requested (F4)**. F1, F2 and F3 are done.

## Round 1 items

- **F1: fixed.** I checked all three inputs, and each now reads as main does on both runs. The citations step asks the statistics step which brackets are intervals (`interval_openings`), and `_Rules` is built anew for each `find` call, so the cache holds no state that is shared between jobs.
- **F2: fixed.** There is one limit, `MAX_JOINED_INTERVALS`, and the 9th-pair boundary test is in.
- **F3: fixed.** The ValueError guard test and the four direct `_read_on` tests are in. The `_NUMERIC` chain code is gone.

## F4 (must fix): the two steps still read different text

The statistics step finds intervals in the folded text, as it is read: through `through_unread` (no soft hyphens or zero-width spaces) and `fold` (math letters such as 𝐶𝐼 become CI). `interval_openings(text)` runs `_ci_runs` on the raw block text. So the promise "the citations step leaves alone exactly the intervals the statistics step reads" breaks when an unread character or a math letter is present. That is the same class of input as #159:

| Printed | PR (cce228d) | main |
|---|---|---|
| `two CIs [1, 3] and ​[2, 4] overlap.` (ZWSP before the 2nd bracket) | `… 1 to 3 and overlap.` (the 2nd interval is removed as a citation) | `… intervals and overlap.` |
| `two CIs [1, 3]​ and [2, 4] overlap.` (ZWSP after the 1st) | `… 1 to 3 and references 2 and 4 overlap.` | not checked |
| `two C­Is [1, 3] and [2, 4] overlap.` (soft hyphen in "CIs") | `… intervals and references 2 and 4 overlap.` | same |
| `two 𝐶𝐼s [1, 3] and [2, 4] overlap.` | `… intervals and references 2 and 4 overlap.` | same |

Suggested fix, which I tried locally: all four inputs then read `two confidence intervals 1 to 3 and 2 to 4 overlap.`, and `CI [1, 3] and [12]` still reads `reference 12`.

```python
def interval_openings(text: str) -> frozenset[int]:
    def openings(read: str) -> list[Candidate]:
        return [
            Candidate(at, at + 1, "[", "interval")
            for _, intervals in _ci_runs(fold(read))
            for at in (interval.start("open") for interval in intervals)
        ]

    return frozenset(c.start for c in through_unread(text, openings))
```

Add a test with these four rows that checks both runs of the whole chain. Then rerun the fast suite and the nightly profile on the textprep files.

## Round 2 result (233666c)

F4 is fixed: `interval_openings` runs `_ci_runs(fold(read))` through `through_unread`, and the new test covers all four rows on both runs. My checks on 233666c:
- Probes: the round 1 and round 2 inputs read correctly on both runs. A 20k-bracket block takes 0.31 s.
- Fast suite: 3244 passed.
- Nightly profile on the 8 textprep files: 708 passed, 2 failed. Both failures are on main 71b30c2 too, in steps this PR does not touch. One is units `5x×` (#209). The other is a new counterexample for the numbers step, `3–1999-02-01`, which reads `3 to 1999-02-01` and then `3 to 1 February 1999`.
- CI: 12/12 green.

Merged by squash at 2026-11-13T22:15:14Z as 31b6d16. The repository refuses merge commits (HTTP 405), so squash is used as for every earlier PR. #109, #110, #145, #151, #159 and #160 are closed.
