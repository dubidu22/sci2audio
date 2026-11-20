# Review of PR #179 (issue #136, time estimate cost model), round 1

Head reviewed: 70491ed. Reviewer thread: "Review and merge PR 179 time estimate". 13 Nov 2026.

## What I checked

- **Fit code by hand.** On 6 hand points (20/1.2, 60/1.9, 100/2.4, 150/3.3, 220/4.9, 280/6.6) `Estimate.model()` gives 1.05945 + 0.0099558·c + 3.4782e-5·c², identical to an independent numpy least-squares over the same subsets. On 3,000 random runs (6 to 200 chunks, noise, zero and non-zero true terms) the chosen model's squared error never exceeds the independent exact non-negative fit by more than 1e-14 relative. Enumerating every subset and keeping the best feasible one is exact NNLS for three terms; Gaussian elimination with partial pivoting and the 1/100 scaling are well conditioned for chunks up to 300 characters.
- **Fallbacks.** Fewer than 6 chunks and fewer than 3 lengths return the plain rate (tested). The third guard ("the fit must beat the plain rate") is almost never active: the per-character-only least-squares fit is one of the candidates and is always at least as good as measured seconds / measured characters, so the guard only fires on exact ties. See S1.
- **expect/done bookkeeping.** `needed` holds each key once; every needed key is `done` exactly once, when spoken or failed; cached and repeated chunks never touch the estimate. `characters_total` and the left sums agree.
- **Fake-clock test.** It constrains the estimate tightly: every shown estimate must equal the real time left to 1e-6 relative, with the first 4 calls doubled. Using 3 warm-up calls would measure a doubled call and fail it. It takes the warm-up count from `WARM_UP_CALLS`, though, so it would still pass if the constant changed (S2).
- **Golden change.** Only one snapshot line changes (`characters_per_second` 21.0 → None in the records snapshot). Correct: the note PDF speaks 3 chunks, all inside the 4 warm-up calls, so nothing is measured. None was already a valid record value (`AudioResult.characters_per_second: float | None`, the record writes None, `web/tasks.py` passes it through, the interface and CLI use only `seconds_left`). Real documents with more than 4 spoken chunks still record a measured speed; only inputs of 4 chunks or fewer (a pasted paragraph) now record None. Not a loss of information that matters.
- **Tests and checks.** ruff, format, lint-imports (3 kept), deptry clean. Fast suite: 2772 passed, 1 skipped (Windows only). Estimate, audio job and speed script tests: 54 passed; estimate tests with `HYPOTHESIS_PROFILE=nightly`: 14 passed. CI on 70491ed: all green, ZAP included.
- **speed.py, my own runs** (same kind of container, 4 vCPU Xeon @ 2.10 GHz, CPU torch, af_heart, new code):

| Paper | Live, new code | Replay on the same chunk times: old (D-159) / new (PR) |
|---|---|---|
| pymedphys | first at 26 %: +12 %; largest with a minute left 15 % | 29 % / 15 % |
| hardt | first at 6 %: −9 %; largest with a minute left 9 % | 14 % / 9 % |

Both meet the ±25 % budget. **Hardt attribution:** my hardt run gives the new estimate 9 % (old replayed: 14 %), so the PR's 20 % on hardt was that run's machine slowdown, not the model; the PR's own replay (old also 20 % on those chunk times) agrees. Attribution confirmed.

## Must fix

**M1. The quadratic term is extrapolated beyond the measured chunk lengths, which can make the first estimates far off when the measured stretch has only short chunks.** A curve fitted only on chunks of up to 60 to 120 characters, used for chunks of 150 to 300, can say up to almost twice the real time. Checked on real data: I took the measured chunk times of my hardt and pymedphys runs (263 chunks after warm-up) and replayed a first estimate after 1,000 measured characters drawn only from short chunks (as a first chapter of names, affiliations, headings or a list would give; an EPUB title and copyright page too), predicting the real time of all longer chunks, 2,000 draws each:

| Measured only chunks of at most | Old rate: median / p95 / worst | This PR: median / p95 / worst | PR + clamp: median / p95 / worst |
|---|---|---|---|
| 60 characters | +47 % / 64 % / +87 % | −18 % / 33 % / +82 % | −3 % / 8 % / −13 % |
| 90 characters | +19 % / 33 % / +58 % | 0 % / 42 % / +88 % | −7 % / 16 % / −22 % |
| 120 characters | +4 % / 16 % / +29 % | −14 % / 32 % / +75 % | −14 % / 21 % / −25 % |

With noise like this the PR's p95 is outside the ±25 % budget in all three cases, and worse than the old rate at 90 and 120. The "clamp" column is one fix I tried: for a chunk longer than the longest measured chunk L, cost(c) = model(L) · c / L (the per-character cost at the edge of the measured range, no curve beyond it). On the real runs it changes nothing (pymedphys 15 %, hardt 9 %, the same as the PR), because there the measured stretch already has long chunks.

Required: the estimate must not use the fitted curve beyond the longest measured chunk; any approach that does this is fine (the clamp above, or the plain rate for chunks longer than L). This needs the lengths of the chunks left, not only their three power sums (for example a `Counter` of lengths left; at most 300 distinct lengths, so the time left stays cheap; update the module docstring's "constant time" sentence to match). Add a unit test: measured chunks only short (for example 10 to 60 characters, cost with a squared term plus noise), chunks left long, and the estimate stays within a stated bound of the true time, where the current code fails it. Rerun the replay table in the PR body and in `docs/baseline.md` after the change and update any number that moves.

This is a refinement of how D-380 is applied (the model and its fit stay as decided). The coordinator decides whether it needs its own decision number; name it in the PR body so the daily KB thread can record it.

## Should fix

**S1. The third fallback is described as a real guard but almost never fires.** `estimate.py`'s module docstring and the PR body say the fit falls back when it "does not explain the measured chunks better than the plain rate", and the PR body says this covers the condition that a short run never gets a wild curve. Because the per-character-only least-squares fit is always a candidate, the NNLS fit is never worse than the rate, so this only catches exact ties (the test with an exactly per-character cost). Reword both to say what it does (keeps the plain rate when the fit is no better, which happens only for an exactly per-character cost) and that the short-run protection is `MIN_CHUNKS`, the 3-lengths rule and, after M1, the clamp.

**S2. No test pins D-381's value.** The fake-clock test takes its slow calls from `audio_module.WARM_UP_CALLS`, and the progress test takes the warm-up count from it too, so changing the constant to 2 or 8 keeps every test green. Add `assert audio_module.WARM_UP_CALLS == 4` (D-381) next to the existing literal 1,000 (D-382), or use the literal 4 in the fake-clock test.

## Process

- `main` moved to 955fea1 (#164 merged). Merge main into the branch (no force-push) together with the fixes; I will check CI on the new head.
- Reply with an exact list: each of M1, S1, S2 fixed (how) or deferred (with an issue link).
